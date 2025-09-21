import os
from dotenv import load_dotenv, find_dotenv
from pathlib import Path

# Use find_dotenv() to make sure the .env file is found
load_dotenv(find_dotenv())

# Set Google Cloud credentials path explicitly
creds_file = Path(__file__).parent / "silken-granite-472417-g7-a6ead8e60cd2.json"
if creds_file.exists():
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(creds_file)
    print(f"✅ Google Cloud credentials set: {creds_file}")
else:
    print(f"❌ Credentials file not found: {creds_file}")

# Define the required environment variables
required_vars = [
    "GCP_PROJECT_ID",
    "GCS_BUCKET_NAME",
    "DOC_AI_PROCESSOR_ID",
]

# Get the values from the environment
PROJECT_ID = os.getenv("GCP_PROJECT_ID")
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME")
DOC_AI_PROCESSOR_ID = os.getenv("DOC_AI_PROCESSOR_ID")
LOCATION = os.getenv("GCP_LOCATION", "us")  # For Document AI
GEMINI_LOCATION = os.getenv("GEMINI_LOCATION", "europe-west2")  # For Gemini AI

# Check if any required variables are missing and raise a specific error
missing_vars = []
if not PROJECT_ID:
    missing_vars.append("GCP_PROJECT_ID")
if not GCS_BUCKET_NAME:
    missing_vars.append("GCS_BUCKET_NAME")
if not DOC_AI_PROCESSOR_ID:
    missing_vars.append("DOC_AI_PROCESSOR_ID")

if missing_vars:
    raise ValueError(f"Missing one or more required environment variables: {', '.join(missing_vars)}")

# You can add other configs here, e.g., for Vertex AI models
GEMINI_MODEL_NAME = "gemini-1.5-pro"