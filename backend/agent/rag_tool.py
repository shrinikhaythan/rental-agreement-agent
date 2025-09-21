from google.cloud import firestore
from google.cloud.firestore_v1.vector import Vector
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.tools import tool
from langchain_google_vertexai import VertexAIEmbeddings
from typing import List

try:
    from backend.config import PROJECT_ID, GEMINI_LOCATION
except ImportError:
    from config import PROJECT_ID, GEMINI_LOCATION

# Initialize Firestore client with explicit credentials
_credentials = None
try:
    from google.oauth2 import service_account
    from pathlib import Path
    
    creds_path = Path(__file__).parent.parent / "silken-granite-472417-g7-a6ead8e60cd2.json"
    if creds_path.exists():
        _credentials = service_account.Credentials.from_service_account_file(str(creds_path))
        db = firestore.Client(project=PROJECT_ID, credentials=_credentials)
        print("✅ Firestore client initialized with explicit credentials")
    else:
        db = firestore.Client(project=PROJECT_ID)
        print("⚠️ Firestore using default credentials")
except Exception as e:
    print(f"⚠️ Firestore credential error, using defaults: {e}")
    db = firestore.Client(project=PROJECT_ID)

# Define the input schema for the tool, now including user_id
class FirestoreSearchInput(BaseModel):
    query: str = Field(description="A natural language query about the rental agreement.")
    user_id: str = Field(description="The unique ID of the user whose documents to search.")

@tool("firestore_search", args_schema=FirestoreSearchInput)
def firestore_search(query: str, user_id: str) -> str:
    """
    Searches the Firestore database for relevant information about the rental agreement 
    based on a user's query, ensuring only the user's documents are retrieved.
    Returns the most relevant text chunks.
    """
    try:
        print(f"Debug: Firestore search - User ID received: '{user_id}', Query: '{query}'")
        
        # Additional debug to catch any issues
        if not user_id or user_id == 'your_user_id' or user_id == 'None':
            print(f"Warning: Invalid user_id received: '{user_id}'")
            return "Error: Invalid user ID received. Please ensure you're logged in correctly."
        
        # Use a Vertex AI embedding model to convert the query into a vector
        try:
            if _credentials:
                embedding_model = VertexAIEmbeddings(model_name="text-embedding-004", project=PROJECT_ID, location=GEMINI_LOCATION, credentials=_credentials)
            else:
                embedding_model = VertexAIEmbeddings(model_name="text-embedding-004", project=PROJECT_ID, location=GEMINI_LOCATION)
        except:
            embedding_model = VertexAIEmbeddings(model_name="text-embedding-004", project=PROJECT_ID, location=GEMINI_LOCATION)
        
        query_vector = embedding_model.embed_query(query)
        print(f"Debug: Generated query vector with {len(query_vector)} dimensions")
        
        # Reference the correct collection where embeddings are stored
        collection_ref = db.collection("rental_agreements")
        
        # IMPORTANT: Use a 'where' clause to filter the documents by user_id
        # before performing the vector search. This is crucial for privacy.
        user_docs_query = collection_ref.where("user_id", "==", user_id)
        
        # Perform the Firestore vector search on the filtered query results
        # Try different distance measures in order of preference
        try:
            vector_query = user_docs_query.find_nearest(
                vector_field="embedding",
                query_vector=Vector(query_vector),
                distance_measure="COSINE",  # Most common and widely supported
                limit=5,
            )
        except Exception as distance_error:
            print(f"Debug: COSINE failed, trying EUCLIDEAN: {distance_error}")
            try:
                vector_query = user_docs_query.find_nearest(
                    vector_field="embedding",
                    query_vector=Vector(query_vector),
                    distance_measure="EUCLIDEAN",
                    limit=5,
                )
            except Exception as euclidean_error:
                print(f"Debug: EUCLIDEAN failed, trying DOT_PRODUCT: {euclidean_error}")
                vector_query = user_docs_query.find_nearest(
                    vector_field="embedding",
                    query_vector=Vector(query_vector),
                    distance_measure="DOT_PRODUCT",
                    limit=5,
                )
        
        results = vector_query.get()
        print(f"Debug: Vector search returned {len(results)} results")
        
        if not results:
            print("Debug: No vector search results, checking if user has any documents")
            # Check if user has any documents at all
            user_docs_check = collection_ref.where("user_id", "==", user_id).limit(1).get()
            if not user_docs_check:
                return "No rental agreements found for your account. Please upload a document first."
            else:
                return "No relevant information found in your rental agreements for this specific query."
            
        # Format the retrieved documents for the LLM
        retrieved_texts = [
            f"Text: {doc.get('original_text')}\nSource: {doc.get('source_file')}"
            for doc in results
        ]
        
        return "\n\n".join(retrieved_texts)
    
    except Exception as e:
        print(f"Debug: Firestore vector search failed: {str(e)}")
        
        # Fallback: Manually retrieve stored embeddings and calculate similarity
        # The embeddings are ALREADY stored in the database from the upload process!
        try:
            print("Debug: Using manual similarity calculation with stored embeddings")
            
            # Generate query vector for comparison with explicit credentials
            try:
                if _credentials:
                    embedding_model = VertexAIEmbeddings(model_name="text-embedding-004", project=PROJECT_ID, location=GEMINI_LOCATION, credentials=_credentials)
                else:
                    embedding_model = VertexAIEmbeddings(model_name="text-embedding-004", project=PROJECT_ID, location=GEMINI_LOCATION)
            except:
                embedding_model = VertexAIEmbeddings(model_name="text-embedding-004", project=PROJECT_ID, location=GEMINI_LOCATION)
            query_vector = embedding_model.embed_query(query)
            
            # Retrieve user documents WITH their stored embeddings
            collection_ref = db.collection("rental_agreements")
            user_docs = collection_ref.where("user_id", "==", user_id).limit(50).get()
            
            print(f"Debug: Found {len(user_docs)} documents with stored embeddings")
            
            if not user_docs:
                return "No rental agreements found for your account. Please upload a document first."
            
            # Calculate cosine similarity using the STORED embeddings
            import numpy as np
            
            similarities = []
            for doc in user_docs:
                doc_data = doc.to_dict()
                stored_embedding = doc_data.get('embedding')
                
                if stored_embedding and len(stored_embedding) > 0:
                    # Calculate cosine similarity between query and stored embedding
                    query_norm = np.linalg.norm(query_vector)
                    doc_norm = np.linalg.norm(stored_embedding)
                    
                    if query_norm > 0 and doc_norm > 0:
                        similarity = np.dot(query_vector, stored_embedding) / (query_norm * doc_norm)
                        similarities.append({
                            'similarity': similarity,
                            'text': doc_data.get('original_text', ''),
                            'source': doc_data.get('source_file', 'Unknown'),
                            'page': doc_data.get('source_page', '')
                        })
            
            print(f"Debug: Calculated similarity for {len(similarities)} documents")
            
            if similarities:
                # Sort by similarity (highest first) and get top 5
                similarities.sort(key=lambda x: x['similarity'], reverse=True)
                top_results = similarities[:5]
                
                print(f"Debug: Top similarities: {[r['similarity'] for r in top_results[:3]]}")
                
                # Format results for the LLM
                retrieved_texts = []
                for result in top_results:
                    if result['similarity'] > 0.3:  # Only include reasonably similar results
                        text = result['text'][:800] + ('...' if len(result['text']) > 800 else '')
                        retrieved_texts.append(f"Text: {text}\nSource: {result['source']} ({result['page']})")
                
                if retrieved_texts:
                    return "\n\n".join(retrieved_texts)
                else:
                    return "No sufficiently relevant information found for your query in the rental agreements."
            
            return "No documents with embeddings found. Please re-upload your documents."
            
        except Exception as fallback_error:
            print(f"Debug: Manual similarity calculation failed: {fallback_error}")
            return f"Search failed: {str(e)}. Manual calculation error: {str(fallback_error)}"
