from google.cloud import firestore
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.tools import tool
from typing import Dict, Any
import json

try:
    from backend.config import PROJECT_ID
except ImportError:
    from config import PROJECT_ID

# Initialize Firestore client with explicit credentials
_credentials = None
try:
    from google.oauth2 import service_account
    from pathlib import Path
    
    creds_path = Path(__file__).parent.parent / "silken-granite-472417-g7-a6ead8e60cd2.json"
    if creds_path.exists():
        _credentials = service_account.Credentials.from_service_account_file(str(creds_path))
        db = firestore.Client(project=PROJECT_ID, credentials=_credentials)
        print("✅ Structured Info tool - Firestore client initialized with explicit credentials")
    else:
        db = firestore.Client(project=PROJECT_ID)
        print("⚠️ Structured Info tool - Firestore using default credentials")
except Exception as e:
    print(f"⚠️ Structured Info tool - Firestore credential error, using defaults: {e}")
    db = firestore.Client(project=PROJECT_ID)

# Define the input schema for the tool
class StructuredInfoInput(BaseModel):
    user_id: str = Field(description="The unique ID of the user whose document info to retrieve.")

@tool("get_structured_info", args_schema=StructuredInfoInput)
def get_structured_info(user_id: str) -> str:
    """
    Retrieves structured information from user's processed rental agreements.
    Use this tool when users ask for specific details like:
    - Rent amount
    - Due dates
    - Lease duration
    - Tenant/landlord names
    - Property address
    - Security deposit amounts
    - Any other specific structured data from their agreements
    """
    try:
        print(f"Debug: Getting structured info for user: '{user_id}'")
        
        # Validate user_id
        if not user_id or user_id in ['your_user_id', 'None', 'user_id']:
            print(f"Warning: Invalid user_id received: '{user_id}'")
            return "Error: Invalid user ID received. Please ensure you're logged in correctly."
        
        # Query processed documents for this user
        collection_ref = db.collection("processed_documents")
        user_docs = collection_ref.where("user_id", "==", user_id).get()
        
        print(f"Debug: Found {len(user_docs)} processed documents for user")
        
        if not user_docs:
            return "No rental agreements found for your account. Please upload a document first."
        
        # Compile structured information from all user documents
        all_structured_info = []
        
        for doc in user_docs:
            doc_data = doc.to_dict()
            filename = doc_data.get('filename', 'Unknown')
            structured_info = doc_data.get('structured_info', {})
            
            if structured_info:
                # Format the structured information nicely
                info_summary = f"📄 **{filename}**:\n"
                
                # Key information fields
                key_fields = {
                    'rent_amount': 'Monthly Rent',
                    'due_date': 'Rent Due Date',
                    'tenant_name': 'Tenant Name',
                    'landlord_name': 'Landlord Name',
                    'property_address': 'Property Address',
                    'duration': 'Lease Duration',
                    'security_deposit_amount': 'Security Deposit',
                    'start_date': 'Lease Start Date',
                    'end_date': 'Lease End Date'
                }
                
                found_info = False
                for field_key, field_label in key_fields.items():
                    value = structured_info.get(field_key)
                    if value and value != 'N/A' and str(value).strip():
                        info_summary += f"   • {field_label}: {value}\n"
                        found_info = True
                
                # Add any other fields not in the key list
                for key, value in structured_info.items():
                    if key not in key_fields and value and value != 'N/A' and str(value).strip():
                        # Format key nicely (convert snake_case to Title Case)
                        formatted_key = key.replace('_', ' ').title()
                        info_summary += f"   • {formatted_key}: {value}\n"
                        found_info = True
                
                if found_info:
                    all_structured_info.append(info_summary)
                else:
                    all_structured_info.append(f"📄 **{filename}**: No structured information available\n")
        
        if not all_structured_info:
            return "No structured information found in your rental agreements. The documents may need to be reprocessed."
        
        result = "Here's the structured information from your rental agreements:\n\n" + "\n".join(all_structured_info)
        print(f"Debug: Returning structured info (length: {len(result)})")
        return result
        
    except Exception as e:
        error_msg = f"Error retrieving structured information: {str(e)}"
        print(f"Debug: {error_msg}")
        return error_msg
