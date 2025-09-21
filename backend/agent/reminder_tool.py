import json
from google.cloud import firestore
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.tools import tool
from datetime import datetime

try:
    from backend.config import PROJECT_ID
except ImportError:
    from config import PROJECT_ID

# Initialize Firestore client
db = firestore.Client(project=PROJECT_ID)

# Define the input schema for the reminder tool
class ReminderInput(BaseModel):
    rent_due_date: str = Field(description="The day of the month the rent is due (e.g., '1st', '5th').")
    user_id: str = Field(description="The unique ID of the user to set the reminder for.")

@tool("set_rent_reminder", args_schema=ReminderInput)
def set_rent_reminder(rent_due_date: str, user_id: str) -> str:
    """
    Creates a monthly rent reminder for a user based on the rent due date.
    This tool stores the reminder details in Firestore to simulate a scheduled job.
    """
    try:
        # In a real-world scenario, you would call a Cloud Function here to set up
        # a Cloud Scheduler job and Pub/Sub topic for notifications.

        # For the prototype, we store the reminder details in Firestore to confirm it's been set.
        reminders_ref = db.collection("reminders").document(user_id)
        
        reminders_ref.set({
            "rent_due_date": rent_due_date,
            "status": "scheduled",
            "created_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat()
        })

        return f"Rent reminder successfully set for the {rent_due_date} of each month for user {user_id}."
    
    except Exception as e:
        return f"Failed to set reminder: {str(e)}"