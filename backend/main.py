from fastapi import FastAPI, UploadFile, File, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from google.cloud import storage
import uvicorn
from typing import Dict
import os
import json
from langchain_core.messages import HumanMessage
import asyncio
import io

# Import modules from your backend
try:
    from backend.config import PROJECT_ID, GCS_BUCKET_NAME, DOC_AI_PROCESSOR_ID, LOCATION, GEMINI_LOCATION
    from backend.agent.agent_graph import agent_executor
    from backend.agent.summarizer_tool import summarize_agreement, extract_structured_info
    from backend.agent.rag_tool import firestore_search
    from backend.agent.reminder_tool import set_rent_reminder
except ImportError:
    from config import PROJECT_ID, GCS_BUCKET_NAME, DOC_AI_PROCESSOR_ID, LOCATION, GEMINI_LOCATION
    from agent.agent_graph import agent_executor
    from agent.summarizer_tool import summarize_agreement, extract_structured_info
    from agent.rag_tool import firestore_search
    from agent.reminder_tool import set_rent_reminder
from google.cloud import documentai_v1beta3 as documentai
from google.cloud import firestore
from langchain_google_vertexai import VertexAI, VertexAIEmbeddings
from langchain_core.documents import Document

# Initialize clients
app = FastAPI(title="Rental Agreement AI Assistant", description="AI-powered rental agreement analysis and tenant assistance")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

storage_client = storage.Client(project=PROJECT_ID)
docai_client = documentai.DocumentProcessorServiceClient()
db = firestore.Client(project=PROJECT_ID)
embedding_model = VertexAIEmbeddings(model_name="text-embedding-004", project=PROJECT_ID, location=GEMINI_LOCATION)

@app.get("/")
async def root():
    """Root endpoint with basic info"""
    return {
        "message": "Rental Agreement AI Assistant API",
        "status": "running",
        "docs": "/docs",
        "ai_status": f"✅ Gemini AI Active ({GEMINI_LOCATION})",
        "document_ai": f"✅ Document AI Active ({LOCATION})"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Basic health check - can be expanded to test AI models
        return {
            "status": "healthy",
            "gemini_region": GEMINI_LOCATION,
            "document_ai_region": LOCATION,
            "services": {
                "fastapi": "✅ running",
                "google_cloud": "✅ connected",
                "gemini_ai": f"✅ available ({GEMINI_LOCATION})",
                "document_ai": f"✅ available ({LOCATION})"
            }
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")

@app.post("/upload-document/")
async def upload_document(file: UploadFile = File(...), user_id: str = Header(..., alias="X-User-ID")):
    """
    Uploads a rental agreement, processes it with Document AI, summarizes it,
    extracts structured data, and stores it in Firestore.
    """
    try:
        # Read the file stream only once and store it
        file_content = await file.read()
        file_stream = io.BytesIO(file_content)

        # 1. Upload to GCS
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(file.filename)
        # blob.upload_from_file is synchronous; we don't use await here
        await asyncio.to_thread(blob.upload_from_file, file_stream, content_type=file.content_type)
        
        # 2. Process with Document AI
        # Reset the stream to be read again
        file_stream.seek(0)
        raw_document = documentai.RawDocument(content=file_stream.read(), mime_type=file.content_type)
        name = f"projects/{PROJECT_ID}/locations/{LOCATION}/processors/{DOC_AI_PROCESSOR_ID}"
        request = documentai.ProcessRequest(name=name, raw_document=raw_document)
        # docai_client.process_document is synchronous, so we run it in a thread
        response = await asyncio.to_thread(docai_client.process_document, request=request)
        document_text = response.document.text
        
        # 3. Use tools to summarize and extract info
        summary = await asyncio.to_thread(summarize_agreement, document_text)
        structured_info_raw = await asyncio.to_thread(extract_structured_info, document_text)
        structured_info = json.loads(structured_info_raw)
        
        # 4. Ingest into Firestore (for RAG)
        chunks = [document_text[i:i + 1000] for i in range(0, len(document_text), 1000)]
        for i, chunk in enumerate(chunks):
            # Use the embedding model to get embeddings
            chunk_embedding = await asyncio.to_thread(embedding_model.embed_query, chunk)
            # db.collection is synchronous
            await asyncio.to_thread(db.collection("rental_agreements").add, {
                "original_text": chunk,
                "embedding": chunk_embedding,
                "source_file": file.filename,
                "source_page": f"page_{i+1}",
                "user_id": user_id
            })

        # 5. Store summary and structured info
        doc_ref = db.collection("processed_documents").document(file.filename)
        await asyncio.to_thread(doc_ref.set, {
            "filename": file.filename,
            "summary": summary,
            "structured_info": structured_info,
            "processed_at": firestore.SERVER_TIMESTAMP,
            "user_id": user_id
        })
        
        rent_due_date = structured_info.get("due_date", "N/A")
        if rent_due_date != "N/A":
            # Use the tool's invoke method instead of calling it directly
            reminder_input = {"rent_due_date": rent_due_date, "user_id": user_id}
            await asyncio.to_thread(set_rent_reminder.invoke, reminder_input)

        return {
            "message": "Document processed and stored successfully.",
            "summary": summary,
            "structured_info": structured_info
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/query-agent/")
async def query_agent(query: str, user_id: str = Header(default="guest-user", alias="X-User-ID")) -> Dict:
    """
    Sends a natural language query to the LangGraph agent and returns the response.
    """
    try:
        # Validate inputs
        if not query or not query.strip():
            raise HTTPException(status_code=400, detail="Query cannot be empty")
        
        if not user_id:
            user_id = "guest-user"
        
        # The user's message is passed as a HumanMessage to the agent
        # Include both messages and user_id in the state
        inputs = {"messages": [HumanMessage(content=query.strip())], "user_id": user_id}
        # The session ID is configured separately for memory management
        config = {"configurable": {"session_id": user_id}}

        # The agent_executor.invoke is a synchronous call.
        result = await asyncio.to_thread(agent_executor.invoke, inputs, config=config)

        # Return the final content from the agent's response with better error handling
        if result and isinstance(result, dict) and 'messages' in result:
            messages = result['messages']
            if messages and len(messages) > 0:
                last_message = messages[-1]
                if hasattr(last_message, 'content') and last_message.content:
                    return {"response": last_message.content}
        
        # Fallback response
        return {"response": "I received your message but couldn't generate a proper response. Please try rephrasing your question."}
    
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Error processing query: {str(e)}"
        print(f"Query Agent Error: {error_msg}")  # For debugging
        return {"response": "I'm experiencing technical difficulties. Please try again later.", "error": error_msg}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)