import json
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.tools import tool
from langchain_google_vertexai import VertexAI

try:
    from backend.config import PROJECT_ID, GEMINI_MODEL_NAME, GEMINI_LOCATION
except ImportError:
    from config import PROJECT_ID, GEMINI_MODEL_NAME, GEMINI_LOCATION

# Initialize the LLM client with explicit credentials
try:
    from google.oauth2 import service_account
    from pathlib import Path
    import os

    # Try to load credentials explicitly
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    creds_path = Path(parent_dir) / "silken-granite-472417-g7-a6ead8e60cd2.json"
    
    if creds_path.exists():
        print(f"✅ LLM initialized with explicit credentials from: {creds_path}")
        credentials = service_account.Credentials.from_service_account_file(str(creds_path))
        llm = VertexAI(
            model_name=GEMINI_MODEL_NAME, 
            project=PROJECT_ID, 
            location=GEMINI_LOCATION,
            credentials=credentials
        )
    else:
        print(f"⚠️ Warning: Credentials file not found at {creds_path}, using default")
        llm = VertexAI(model_name=GEMINI_MODEL_NAME, project=PROJECT_ID, location=GEMINI_LOCATION)
except Exception as e:
    print(f"❌ Error initializing LLM with credentials: {e}")
    llm = VertexAI(model_name=GEMINI_MODEL_NAME, project=PROJECT_ID, location=GEMINI_LOCATION)

# Define the input schema for summarization
class SummarizeInput(BaseModel):
    text: str = Field(description="The full text of the rental agreement to be summarized.")

@tool("summarize_agreement", args_schema=SummarizeInput)
def summarize_agreement(text: str) -> str:
    """
    Summarizes a complex rental agreement into plain, easy-to-understand language.
    """
    prompt = f"""Role: You are a expert legal translator and tenant advocate. Your sole purpose is to demystify complex legal documents for everyday people, especially those without any legal background.

Task: I will provide you with the full text of a rental agreement. You will process it according to the following strict instructions:

1. Comprehensive Simplification:

Translate the entire document into simple, clear, and user-friendly English.

Break down every complex legal term (e.g., "force majeure," "indemnification," "joint and several liability", not only this but any other legal jargon and complex logic) into a plain-language definition right in the text.

Unpack complex logic and long sentences into short, easy-to-follow bullet points or numbered lists where ever appropriate.

Do not summarize, cut, or omit any clause, point, or detail from the original text. Your goal is a 1:1 simplified translation, not a summary.

2. Key Term Highlighting:

After simplifying the entire document, create a separate section titled "🔑 Key Terms & Conditions for the Tenant:"

In this section, list the most important clauses a tenant must be aware of (e.g., rent amount and due date, security deposit details, lease term, maintenance responsibilities, pet policies, subletting rules).

Present each key term in a clear bullet point.

3. Tenant Red Flag Analysis:

After the "Key Terms" section, create a section titled "⚠️ Tenant Alert: Potential Red Flags"

In this section, analyze the text and flag any clauses that are unusually harsh, unfair, biased against the tenant, or potentially unenforceable (check against general tenancy laws).

For each red flag:

Clearly state which clause you are referring to.

Explain why it is potentially unfair or unfavorable (e.g., "This clause could allow the landlord to enter without any notice, which violates your right to privacy," or "This waiver of all landlord liability for repairs is extreme and may not be legally enforceable.").

Use simple, warning language like "Be cautious of..." or "This is highly unusual because..."

Formatting: Use clear headings, bullet points, and bold text to make the final output extremely easy to read and scan.

Tone: Be helpful, neutral, and empowering. You are not giving legal advice, but providing a clear understanding so the tenant can make informed decisions or ask better questions. 
the full rental agreement:
\n\n{text}"""
    return llm.invoke(prompt)

# Define the input schema for structured extraction
class ExtractStructuredInfoInput(BaseModel):
    text: str = Field(description="The full text of the rental agreement for extracting key structured information.")

@tool("extract_structured_info", args_schema=ExtractStructuredInfoInput)
def extract_structured_info(text: str) -> str:
    """
    Extracts key structured information from a rental agreement into a JSON format. return only the json file object and nothing else , not even any text 
    The extracted info should include: property_address, tenant_name, landlord_name, rent_amount, due_date, duration, security_deposit_amount.
    """
    prompt = prompt = f"""
Extract the following key information from the provided rental agreement text. You must return a valid JSON object containing only the specified keys. Do not include any other text, explanations, or markdown formatting like ```json.

The JSON keys must be exactly:
{{
  "property_address": "<string or 'N/A'>",
  "tenant_name": "<string or 'N/A'>",
  "landlord_name": "<string or 'N/A'>",
  "rent_amount": "<string with currency or 'N/A'>",
  "due_date": "<string describing the due day or 'N/A'>",
  "duration": "<string describing the lease term or 'N/A'>",
  "security_deposit_amount": "<string with currency or 'N/A'>"
}}

Instructions for extraction:
- **rent_amount** and **security_deposit_amount**: Must include the currency symbol or code (e.g., '$1500', '€1200', '1500 USD').
- **due_date**: Extract the specific day of the month rent is due (e.g., '1st', '5th', 'First of the month'). If a range is given, use the final due date.
- **duration**: Extract the lease term (e.g., '12 months', '1 year', 'Month-to-month'). If start and end dates are provided, include them (e.g., '12 months starting January 1, 2025').
- For all fields: If the information cannot be conclusively found in the text, use the exact string "N/A". Do not infer or create information.

Agreement Text:
{text}
"""
    response = llm.invoke(prompt)
    # The LLM is instructed to return JSON, so we try to parse it.
    try:
        # LangChain may return a string that needs to be parsed
        # This handles cases where the LLM's response is a string representation of JSON
        json_data = json.loads(response.strip().strip("```json").strip("```"))
        return json.dumps(json_data, indent=2)
    except (json.JSONDecodeError, AttributeError):
        # If the LLM doesn't return valid JSON, handle the error gracefully
        return json.dumps({"error": "Could not extract structured info. LLM response was not valid JSON."})