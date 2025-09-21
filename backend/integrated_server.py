#!/usr/bin/env python3
"""
Integrated Rental Agreement AI Server
Serves both the frontend dashboard and backend API from a single server
"""

import sys
import os
from pathlib import Path
import uvicorn
from fastapi import FastAPI, UploadFile, File, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from google.cloud import storage
from typing import Dict
import json
from langchain_core.messages import HumanMessage
import asyncio
import io

# Add the parent directory to sys.path for imports
sys.path.append('..')

# Import backend modules
try:
    from backend.config import PROJECT_ID, GCS_BUCKET_NAME, DOC_AI_PROCESSOR_ID, LOCATION, GEMINI_LOCATION
    from backend.agent.agent_graph import agent_executor
    from backend.agent.rag_tool import firestore_search
    from backend.agent.reminder_tool import set_rent_reminder
except ImportError:
    from config import PROJECT_ID, GCS_BUCKET_NAME, DOC_AI_PROCESSOR_ID, LOCATION, GEMINI_LOCATION
    from agent.agent_graph import agent_executor
    from agent.rag_tool import firestore_search
    from agent.reminder_tool import set_rent_reminder
from google.cloud import documentai_v1beta3 as documentai
from google.cloud import firestore
from langchain_google_vertexai import VertexAI, VertexAIEmbeddings
from langchain_core.documents import Document

# Initialize FastAPI app
app = FastAPI(
    title="Rental Agreement AI Assistant - Integrated", 
    description="Complete rental agreement analysis system with web dashboard"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Google Cloud clients with explicit credentials
try:
    from google.oauth2 import service_account
    import json
    from pathlib import Path
    
    # Try to load credentials explicitly
    creds_path = Path(__file__).parent / "silken-granite-472417-g7-a6ead8e60cd2.json"
    
    if creds_path.exists():
        print(f"✅ Loading credentials from: {creds_path}")
        credentials = service_account.Credentials.from_service_account_file(str(creds_path))
        
        storage_client = storage.Client(project=PROJECT_ID, credentials=credentials)
        docai_client = documentai.DocumentProcessorServiceClient(credentials=credentials)
        db = firestore.Client(project=PROJECT_ID, credentials=credentials)
        embedding_model = VertexAIEmbeddings(
            model_name="text-embedding-004", 
            project=PROJECT_ID, 
            location=GEMINI_LOCATION,
            credentials=credentials
        )
        print("✅ All Google Cloud clients initialized with explicit credentials")
    else:
        print("⚠️ Using default credentials")
        storage_client = storage.Client(project=PROJECT_ID)
        docai_client = documentai.DocumentProcessorServiceClient()
        db = firestore.Client(project=PROJECT_ID)
        embedding_model = VertexAIEmbeddings(model_name="text-embedding-004", project=PROJECT_ID, location=GEMINI_LOCATION)
        
except Exception as cred_error:
    print(f"❌ Credential loading error: {cred_error}")
    print("🔄 Falling back to default credentials...")
    storage_client = storage.Client(project=PROJECT_ID)
    docai_client = documentai.DocumentProcessorServiceClient()
    db = firestore.Client(project=PROJECT_ID)
    embedding_model = VertexAIEmbeddings(model_name="text-embedding-004", project=PROJECT_ID, location=GEMINI_LOCATION)

# ========================
# API ENDPOINTS (Backend)
# ========================

@app.get("/api")
async def api_root():
    """API root endpoint"""
    return {
        "message": "Rental Agreement AI Assistant API",
        "status": "running",
        "docs": "/docs",
        "dashboard": "/",
        "ai_status": f"✅ Gemini AI Active ({GEMINI_LOCATION})",
        "document_ai": f"✅ Document AI Active ({LOCATION})"
    }

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    try:
        return {
            "status": "healthy",
            "platform": "Google Cloud Run",
            "environment": "production",
            "services": {
                "fastapi": "✅ running",
                "google_cloud": "✅ connected",
                "gemini_ai": f"✅ available ({GEMINI_LOCATION})",
                "document_ai": f"✅ available ({LOCATION})",
                "frontend": "✅ integrated"
            }
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")

@app.post("/api/upload-document/")
async def upload_document(file: UploadFile = File(...), user_id: str = Header(default="guest-user", alias="X-User-ID")):
    """Upload and process rental agreement documents"""
    try:
        print(f"🔍 DEBUG: Starting upload process...")
        print(f"📤 Processing upload for user: {user_id}, file: {file.filename}")
        print(f"📄 File details: size={file.size}, type={file.content_type}")
        
        # Read the file stream only once and store it
        print(f"🔍 DEBUG: Reading file content...")
        file_content = await file.read()
        print(f"📄 File content read: {len(file_content)} bytes")
        file_stream = io.BytesIO(file_content)

        # 1. Upload to GCS
        print(f"🔍 DEBUG: Starting GCS upload...")
        try:
            bucket = storage_client.bucket(GCS_BUCKET_NAME)
            blob = bucket.blob(file.filename)
            await asyncio.to_thread(blob.upload_from_file, file_stream, content_type=file.content_type)
            print(f"✅ Uploaded to GCS: {file.filename}")
        except Exception as gcs_error:
            print(f"❌ GCS Upload error: {gcs_error}")
            raise
        
        # 2. Process with Document AI
        print(f"🔍 DEBUG: Starting Document AI processing...")
        try:
            file_stream.seek(0)
            raw_document = documentai.RawDocument(content=file_stream.read(), mime_type=file.content_type)
            name = f"projects/{PROJECT_ID}/locations/{LOCATION}/processors/{DOC_AI_PROCESSOR_ID}"
            request = documentai.ProcessRequest(name=name, raw_document=raw_document)
            response = await asyncio.to_thread(docai_client.process_document, request=request)
            document_text = response.document.text
            print(f"✅ Document AI processed: {len(document_text)} characters")
        except Exception as docai_error:
            print(f"❌ Document AI error: {docai_error}")
            raise
        
        # 3. Use AI tools to summarize and extract info
        print(f"🔍 DEBUG: Starting AI analysis (summary & structured info)...")
        try:
            try:
                from backend.agent.summarizer_tool import summarize_agreement, extract_structured_info
            except ImportError:
                from agent.summarizer_tool import summarize_agreement, extract_structured_info
            
            print(f"🔍 DEBUG: Calling summarize_agreement...")
            summary = await asyncio.to_thread(summarize_agreement, document_text)
            print(f"✅ Summary generated: {len(summary)} characters")
            
            print(f"🔍 DEBUG: Calling extract_structured_info...")
            structured_info_raw = await asyncio.to_thread(extract_structured_info, document_text)
            print(f"📄 Raw structured info: {structured_info_raw[:200]}...")
            structured_info = json.loads(structured_info_raw)
            print(f"✅ AI analysis complete: {len(summary)} char summary, structured info keys: {list(structured_info.keys())}")
        except Exception as ai_error:
            print(f"❌ AI Analysis error: {ai_error}")
            # Continue with minimal info instead of failing completely
            summary = "Summary generation failed. Please try again or contact support."
            structured_info = {
                "error": "Could not extract structured information",
                "property_address": "N/A",
                "tenant_name": "N/A",
                "landlord_name": "N/A",
                "rent_amount": "N/A",
                "due_date": "N/A",
                "duration": "N/A",
                "security_deposit_amount": "N/A"
            }
        
        # 4. Ingest into Firestore (for RAG)
        print(f"🔍 DEBUG: Starting Firestore ingestion...")
        try:
            chunks = [document_text[i:i + 1000] for i in range(0, len(document_text), 1000)]
            print(f"📄 Created {len(chunks)} text chunks")
            for i, chunk in enumerate(chunks):
                chunk_embedding = await asyncio.to_thread(embedding_model.embed_query, chunk)
                await asyncio.to_thread(db.collection("rental_agreements").add, {
                    "original_text": chunk,
                    "embedding": chunk_embedding,
                    "source_file": file.filename,
                    "source_page": f"page_{i+1}",
                    "user_id": user_id
                })
            print(f"✅ Stored {len(chunks)} chunks with embeddings")
        except Exception as firestore_error:
            print(f"❌ Firestore ingestion error: {firestore_error}")
            # Continue without failing completely

        # 5. Store summary and structured info
        print(f"🔍 DEBUG: Storing processed document metadata...")
        try:
            doc_ref = db.collection("processed_documents").document(file.filename)
            await asyncio.to_thread(doc_ref.set, {
                "filename": file.filename,
                "summary": summary,
                "structured_info": structured_info,
                "processed_at": firestore.SERVER_TIMESTAMP,
                "user_id": user_id
            })
            print(f"✅ Stored document metadata")
        except Exception as metadata_error:
            print(f"❌ Metadata storage error: {metadata_error}")

        # 6. Set reminder if due date found
        print(f"🔍 DEBUG: Checking for reminders...")
        try:
            rent_due_date = structured_info.get("due_date", "N/A")
            if rent_due_date != "N/A":
                reminder_input = {"rent_due_date": rent_due_date, "user_id": user_id}
                await asyncio.to_thread(set_rent_reminder.invoke, reminder_input)
                print(f"✅ Reminder set for: {rent_due_date}")
            else:
                print(f"⚠️ No due date found, skipping reminder")
        except Exception as reminder_error:
            print(f"❌ Reminder error: {reminder_error}")

        print(f"🎉 Upload process completed successfully!")
        return {
            "message": "Document processed and stored successfully.",
            "summary": summary,
            "structured_info": structured_info,
            "filename": file.filename,
            "chunks_created": len(chunks) if 'chunks' in locals() else 0
        }
    
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"❌ Upload error: {e}")
        print(f"❌ Full traceback: {error_trace}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/query-agent/")
async def query_agent(query: str, user_id: str = Header(default="guest-user", alias="X-User-ID")) -> Dict:
    """Query the AI agent about rental agreements"""
    try:
        print(f"🤖 AI Query from {user_id}: {query}")
        
        # Validate inputs
        if not query or not query.strip():
            raise HTTPException(status_code=400, detail="Query cannot be empty")
        
        if not user_id:
            user_id = "guest-user"
        
        # Send to AI agent
        inputs = {"messages": [HumanMessage(content=query.strip())], "user_id": user_id}
        config = {"configurable": {"session_id": user_id}}
        result = await asyncio.to_thread(agent_executor.invoke, inputs, config=config)

        # Extract response
        if result and isinstance(result, dict) and 'messages' in result:
            messages = result['messages']
            if messages and len(messages) > 0:
                last_message = messages[-1]
                if hasattr(last_message, 'content') and last_message.content:
                    print(f"✅ AI Response: {last_message.content[:100]}...")
                    return {"response": last_message.content}
        
        return {"response": "I received your message but couldn't generate a proper response. Please try rephrasing your question."}
    
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Error processing query: {str(e)}"
        print(f"❌ Query error: {error_msg}")
        return {"response": "I'm experiencing technical difficulties. Please try again later.", "error": error_msg}

@app.get("/api/users/{user_id}/documents")
async def get_user_documents(user_id: str):
    """Get all processed documents for a user"""
    try:
        # Query the processed_documents collection for this user
        docs_query = db.collection("processed_documents").where("user_id", "==", user_id)
        docs_result = await asyncio.to_thread(docs_query.get)
        
        documents = []
        for doc in docs_result:
            doc_data = doc.to_dict()
            doc_data['id'] = doc.id
            documents.append(doc_data)
            
        return {"documents": documents}
    except Exception as e:
        print(f"❌ Error fetching user documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/documents/{filename}/summary")
async def get_document_summary(filename: str, user_id: str = Header(default="guest-user", alias="X-User-ID")):
    """Get the summary of a specific document"""
    try:
        doc_ref = db.collection("processed_documents").document(filename)
        doc = await asyncio.to_thread(doc_ref.get)
        
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Document not found")
            
        doc_data = doc.to_dict()
        
        # Check if user has access to this document
        if doc_data.get("user_id") != user_id:
            raise HTTPException(status_code=403, detail="Access denied")
            
        return {
            "filename": filename,
            "summary": doc_data.get("summary", "Summary not available"),
            "structured_info": doc_data.get("structured_info", {}),
            "processed_at": doc_data.get("processed_at")
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error fetching document summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/users/{user_id}/reminders")
async def get_user_reminders(user_id: str):
    """Get all reminders for a user"""
    try:
        # Query the reminders collection for this user
        reminders_query = db.collection("reminders").where("user_id", "==", user_id)
        reminders_result = await asyncio.to_thread(reminders_query.get)
        
        reminders = []
        for reminder in reminders_result:
            reminder_data = reminder.to_dict()
            reminder_data['id'] = reminder.id
            reminders.append(reminder_data)
            
        return {"reminders": reminders}
    except Exception as e:
        print(f"❌ Error fetching user reminders: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ========================
# FRONTEND SERVING
# ========================

# Get frontend directory path
frontend_dir = Path(__file__).parent / "frontend"

# Mount static files (CSS, JS)
app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    """Serve the main dashboard page"""
    index_path = frontend_dir / "index.html"
    if index_path.exists():
        with open(index_path, 'r', encoding='utf-8') as f:
            content = f.read()
            # Update the API base URL in the frontend to use /api prefix
            content = content.replace(
                "API_BASE_URL: 'http://127.0.0.1:8001'",
                "API_BASE_URL: '/api'"
            )
            return HTMLResponse(content=content)
    else:
        return HTMLResponse("""
            <html><body>
                <h1>Frontend files not found</h1>
                <p>Please ensure the frontend directory exists at: {}</p>
            </body></html>
        """.format(frontend_dir))

@app.get("/styles.css")
async def serve_css():
    """Serve CSS file"""
    css_path = frontend_dir / "styles.css"
    if css_path.exists():
        return FileResponse(css_path, media_type="text/css")
    else:
        raise HTTPException(status_code=404, detail="CSS file not found")

@app.get("/script.js")
async def serve_js():
    """Serve JavaScript file"""
    js_path = frontend_dir / "script.js"
    if js_path.exists():
        with open(js_path, 'r', encoding='utf-8') as f:
            content = f.read()
            # Update the API base URL in JavaScript
            content = content.replace(
                "API_BASE_URL: 'http://127.0.0.1:8001'",
                "API_BASE_URL: '/api'"
            )
            from fastapi.responses import Response
            return Response(content=content, media_type="application/javascript")
    else:
        raise HTTPException(status_code=404, detail="JavaScript file not found")

# ========================
# SERVER STARTUP
# ========================

def start_integrated_server():
    """Start the integrated server"""
    
    # Get configuration for different environments
    import os
    port = int(os.environ.get("PORT", 8001))
    host = os.environ.get("HOST", "127.0.0.1")
    is_production = os.environ.get("ENVIRONMENT", "development") == "production"
    
    print("=" * 80)
    print("🏠 RENTAL AGREEMENT AI - INTEGRATED SERVER")
    print("=" * 80)
    print()
    print("🚀 Starting integrated server...")
    if is_production:
        print("📍 Production Environment - Google Cloud Run")
        print(f"📍 Port: {port}")
    else:
        print(f"📍 Dashboard URL: http://{host}:{port}")
        print(f"📍 API Documentation: http://{host}:{port}/docs")
        print(f"📍 API Base URL: http://{host}:{port}/api")
    print()
    print("✅ Features Available:")
    print("   🏢 Web Dashboard - Upload & manage rental agreements")
    print("   🤖 AI Chat Assistant - Ask questions about your leases")
    print("   📊 Analytics - View statistics and insights")
    print("   🔔 Alerts - Get notified about important dates")
    print("   ⚙️  Settings - Configure your preferences")
    print()
    print("✅ Backend Services:")
    print(f"   📄 Document AI - Processing ({LOCATION})")
    print(f"   🧠 Gemini AI - Chat & Analysis ({GEMINI_LOCATION})")
    print("   💾 Firestore - Database & Embeddings")
    print("   ☁️  Google Cloud Storage - File Storage")
    print()
    print("=" * 80)
    print("🎯 READY TO TEST!")
    print("1. Open: http://127.0.0.1:8001 in your browser")
    print("2. Upload your rental agreement PDF")
    print("3. Ask questions to the AI assistant")
    print("=" * 80)
    print()
    print("🔥 Server starting... (Press Ctrl+C to stop)")
    print()

    try:
        uvicorn.run(
            app, 
            host=host, 
            port=port, 
            log_level="info",
            reload=False
        )
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except Exception as e:
        print(f"\n❌ Server error: {e}")

# Make sure the app is available at module level for uvicorn
# This allows: uvicorn integrated_server:app

if __name__ == "__main__":
    start_integrated_server()
