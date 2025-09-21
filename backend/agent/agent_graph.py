import operator
from typing import Annotated, TypedDict, List, Dict
from typing_extensions import Literal
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, ToolMessage
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.tools import tool
from langchain_google_vertexai import ChatVertexAI
from langgraph.prebuilt import ToolNode
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.chat_history import BaseChatMessageHistory
from datetime import datetime
from dateutil.relativedelta import relativedelta
from google.cloud import firestore

# Import all the tools you've created
try:
    from backend.agent.rag_tool import firestore_search
    from backend.agent.summarizer_tool import summarize_agreement, extract_structured_info
    from backend.agent.reminder_tool import set_rent_reminder
    from backend.agent.structured_info_tool import get_structured_info
except ImportError:
    from agent.rag_tool import firestore_search
    from agent.summarizer_tool import summarize_agreement, extract_structured_info
    from agent.reminder_tool import set_rent_reminder
    from agent.structured_info_tool import get_structured_info
try:
    from backend.config import PROJECT_ID, GEMINI_MODEL_NAME, GEMINI_LOCATION
except ImportError:
    from config import PROJECT_ID, GEMINI_MODEL_NAME, GEMINI_LOCATION

# Simple in-memory message history implementation
class InMemoryHistory(BaseChatMessageHistory):
    def __init__(self):
        self.messages: List[BaseMessage] = []
    
    def add_message(self, message: BaseMessage) -> None:
        self.messages.append(message)
    
    def clear(self) -> None:
        self.messages = []

# A simple in-memory store for demonstration purposes.
store = {}
# Initialize Firestore with explicit credentials
try:
    from google.oauth2 import service_account
    from pathlib import Path
    
    creds_path = Path(__file__).parent.parent / "silken-granite-472417-g7-a6ead8e60cd2.json"
    if creds_path.exists():
        credentials = service_account.Credentials.from_service_account_file(str(creds_path))
        db = firestore.Client(project=PROJECT_ID, credentials=credentials)
        print("✅ Agent Firestore client initialized with explicit credentials")
    else:
        db = firestore.Client(project=PROJECT_ID)
        print("⚠️ Agent Firestore using default credentials")
except Exception as e:
    print(f"⚠️ Agent Firestore credential error, using defaults: {e}")
    db = firestore.Client(project=PROJECT_ID)

def get_session_history(session_id: str) -> InMemoryHistory:
    if session_id not in store:
        store[session_id] = InMemoryHistory()
    return store[session_id]

# Define the new tool for date calculation
class DaysUntilRentInput(BaseModel):
    user_id: str = Field(description="The user ID to find the rent due date for.")

@tool("get_days_until_rent", args_schema=DaysUntilRentInput)
def get_days_until_rent(user_id: str) -> str:
    """
    Calculates the number of days remaining until the next rent payment is due.
    """
    try:
        # Retrieve the user's processed documents from Firestore
        docs = db.collection("processed_documents").where("user_id", "==", user_id).limit(1).get()
        if not docs:
            return "No rental agreement found for this user. Please upload a document first."

        doc_data = docs[0].to_dict()
        structured_info = doc_data.get("structured_info", {})
        due_date_str = structured_info.get("due_date")

        if not due_date_str:
            return "No rent due date found in your rental agreement."
        
        # Parse the due date string into a numerical day
        # This is a simplified parser; a more robust one would be needed
        try:
            day_of_month = int(''.join(filter(str.isdigit, due_date_str)))
        except ValueError:
            return "Could not parse the rent due date. The format is not a simple number."

        today = datetime.now().date()
        
        # Find the next rent due date
        next_due_date = today.replace(day=day_of_month)
        if today > next_due_date:
            next_due_date += relativedelta(months=1)
        
        days_left = (next_due_date - today).days
        return f"There are {days_left} days left until your next rent payment, which is due on the {day_of_month} of the month."
    
    except Exception as e:
        return f"An error occurred while calculating the days left: {str(e)}"

# Define the state with an explicit list of messages.
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    user_id: str

# Define the tools the agent can use.
tools = [
    firestore_search,
    summarize_agreement,
    extract_structured_info,
    set_rent_reminder,
    get_days_until_rent,
    get_structured_info  # The new structured info tool
]

# Create the LLM with tool-calling capabilities with explicit credentials
# Use GEMINI_LOCATION for Gemini models
try:
    from google.oauth2 import service_account
    from pathlib import Path
    
    creds_path = Path(__file__).parent.parent / "silken-granite-472417-g7-a6ead8e60cd2.json"
    if creds_path.exists():
        credentials = service_account.Credentials.from_service_account_file(str(creds_path))
        llm = ChatVertexAI(model_name=GEMINI_MODEL_NAME, project=PROJECT_ID, location=GEMINI_LOCATION, credentials=credentials)
        print("✅ LLM initialized with explicit credentials")
    else:
        llm = ChatVertexAI(model_name=GEMINI_MODEL_NAME, project=PROJECT_ID, location=GEMINI_LOCATION)
        print("⚠️ LLM using default credentials")
except Exception as e:
    print(f"⚠️ LLM credential error, using defaults: {e}")
    llm = ChatVertexAI(model_name=GEMINI_MODEL_NAME, project=PROJECT_ID, location=GEMINI_LOCATION)

# Create system prompt to help the LLM understand when to use tools
system_prompt = """
You are a helpful AI assistant for rental agreement analysis. You have several specialized tools available.

🎯 INTELLIGENT TOOL SELECTION - UNDERSTAND THE USER'S INTENT:

1. **For SPECIFIC DATA queries** → Use get_structured_info:
   - When user wants concrete facts: amounts, dates, names, addresses
   - Intent: Getting specific information that's already extracted
   - Examples: rent amount, due date, landlord name, property address, lease duration, security deposit
   - Key concept: "What is...?", "How much...?", "When is...?", "Who is...?", "Where is...?"

2. **For ANALYSIS & INTERPRETATION queries** → Use firestore_search:
   - When user wants understanding, analysis, or concerns about the contract
   - Intent: Analyzing content for problems, risks, unusual terms, explanations
   - Semantic concepts: issues, problems, concerns, risks, dangers, red flags, warnings, unfair terms, harsh clauses, problematic sections, things to watch out for, potential issues, concerning aspects, risky parts
   - Key concept: "What should I worry about?", "Are there problems?", "Explain this clause", "Is this normal?"

3. **For TIME CALCULATIONS** → Use get_days_until_rent:
   - When user wants to know time remaining until payment
   - Intent: Calculating days/time until next rent due
   - Key concept: "How long until...", "When is next...", "Days remaining..."

4. **For SETTING REMINDERS** → Use set_rent_reminder:
   - When user wants to create notifications or alerts
   - Intent: Setting up future reminders
   - Key concept: "Remind me", "Set alert", "Notify me", "Don't let me forget"

🧠 SEMANTIC UNDERSTANDING RULES:
- THINK about what the user is trying to accomplish, not just the exact words
- "dangers" = "red flags" = "risks" = "concerns" = "problems" = "issues" → ALL use firestore_search
- "rent amount" = "how much rent" = "monthly payment" → ALL use get_structured_info  
- "due date" = "when is rent due" = "payment date" → ALL use get_structured_info
- Use your intelligence to map similar concepts to the right tool
- If you're unsure, think: "Is the user asking for a specific fact or asking for analysis?"

🚨 CRITICAL RULES:
- NEVER use exact phrase matching - understand the MEANING and INTENT
- Documents are already uploaded and processed - never say "please upload"
- If get_structured_info doesn't have specific data, then try firestore_search
- Focus on helping the user understand their rental agreement

📋 AVAILABLE TOOLS:
1. get_structured_info - Extract specific facts and data points
2. firestore_search - Analyze, interpret, and find concerning content  
3. get_days_until_rent - Calculate time until rent payment
4. set_rent_reminder - Create payment reminders

Remember: Be intelligent about tool selection - understand INTENT, not just keywords!
"""

llm_with_tools = llm.bind_tools(tools)

# Define the nodes in the graph.
def call_llm_node(state: AgentState) -> dict:
    """Process messages and call LLM with proper error handling."""
    try:
        messages = state['messages']
        
        # Safety check for empty messages
        if not messages:
            print("Warning: No messages found in state")
            return {"messages": [AIMessage(content="I didn't receive any message to process.")]}
        
        last_message = messages[-1]
        print(f"Debug: Processing message type: {type(last_message).__name__}")
        
        # Check if the last message is a ToolMessage (i.e., from a tool call)
        if isinstance(last_message, ToolMessage):
            print("Debug: Processing tool message result")
            # We are coming back from a tool, so we need a new prompt for demystification
            # Find the original user question (search backwards for HumanMessage)
            original_user_question = "the rental agreement question"
            
            # Look for the most recent HumanMessage
            for msg in reversed(messages[:-1]):  # Exclude the last tool message
                if isinstance(msg, HumanMessage):
                    original_user_question = msg.content
                    break
            
            # The tool result is the last message
            tool_result = last_message.content
            print(f"Debug: Tool result length: {len(str(tool_result))}")
            
            demystify_prompt = f"""
The user asked: "{original_user_question}"

I retrieved the following information from their documents:
---
{tool_result}
---

Based on this information, please answer the user's question in a simple, clear, and demystified way.
Simplify complex legal terms and complex logic in a simple way such that even people with no legal experience and basic English knowledge should be able to understand.
If the information is not relevant, say that you cannot help with this specific question.
"""
            try:
                response = llm.invoke(demystify_prompt)
                print("Debug: Generated demystified response")
                return {"messages": [response]}
            except Exception as llm_error:
                print(f"Debug: LLM error in demystification: {llm_error}")
                # If LLM fails due to quota or other issues, provide a helpful fallback
                if "429" in str(llm_error) or "Resource exhausted" in str(llm_error) or "quota" in str(llm_error).lower():
                    fallback_response = f"I found the information you requested:\n\n{tool_result}\n\nNote: I'm experiencing high demand right now, so I provided the raw information. Please try asking again in a moment for a more detailed explanation."
                else:
                    fallback_response = f"Based on your rental agreement:\n\n{tool_result}"
                error_response = AIMessage(content=fallback_response)
                return {"messages": [error_response]}
            
        # If the message is not from a tool, just pass it to the LLM to decide on a tool
        print("Debug: Calling LLM with tools")
        
        # Add system prompt to help LLM understand when to use tools
        from langchain_core.messages import SystemMessage
        messages_with_system = [SystemMessage(content=system_prompt)] + messages
        
        response = llm_with_tools.invoke(messages_with_system)
        print(f"Debug: LLM response type: {type(response).__name__}")
        return {"messages": [response]}
        
    except Exception as e:
        print(f"Error in call_llm_node: {str(e)}")
        # Handle quota exhaustion errors more gracefully
        if "429" in str(e) or "Resource exhausted" in str(e) or "quota" in str(e).lower():
            error_response = AIMessage(content="I'm experiencing high demand right now. Please try your question again in a moment, and I'll be happy to help you analyze your rental agreement.")
        else:
            error_response = AIMessage(content=f"I encountered an error processing your request. Please try rephrasing your question or try again in a moment.")
        return {"messages": [error_response]}

def call_tool_node(state: AgentState) -> dict:
    """Execute tool calls with proper error handling and consistent calling mechanism."""
    try:
        messages = state['messages']
        
        if not messages:
            print("Error: No messages found in call_tool_node")
            return {"messages": [ToolMessage(content="Error: No messages to process", tool_call_id="error")]}
            
        last_message = messages[-1]
        
        if not hasattr(last_message, 'tool_calls') or not last_message.tool_calls:
            print("Error: No tool calls found in last message")
            return {"messages": [ToolMessage(content="Error: No tool calls to execute", tool_call_id="error")]}
            
        tool_calls = last_message.tool_calls
        tool_results = []
        
        print(f"Debug: Executing {len(tool_calls)} tool calls")
        
        for tool_call in tool_calls:
            tool_name = tool_call['name']
            tool_args = tool_call['args']
            tool_call_id = tool_call['id']
            
            print(f"Debug: Calling tool '{tool_name}' with args: {tool_args}")
            print(f"Debug: State user_id is: '{state.get('user_id', 'NOT_FOUND')}'")
            
            try:
                # Use consistent tool calling mechanism for all tools
                if tool_name == "firestore_search":
                    # Add user_id to tool args and use invoke method
                    print(f"Debug: Before override - tool_args user_id: {tool_args.get('user_id', 'NOT_SET')}")
                    tool_args['user_id'] = state['user_id']
                    print(f"Debug: After override - tool_args user_id: {tool_args.get('user_id', 'NOT_SET')}")
                    result = firestore_search.invoke(tool_args)
                elif tool_name == "set_rent_reminder":
                    tool_args['user_id'] = state['user_id']
                    result = set_rent_reminder.invoke(tool_args)
                elif tool_name == "get_days_until_rent":
                    tool_args['user_id'] = state['user_id']
                    result = get_days_until_rent.invoke(tool_args)
                elif tool_name == "get_structured_info":
                    tool_args['user_id'] = state['user_id']
                    result = get_structured_info.invoke(tool_args)
                elif tool_name == "summarize_agreement":
                    result = summarize_agreement(agreement_text=tool_args.get("agreement_text", ""))
                elif tool_name == "extract_structured_info":
                    result = extract_structured_info(agreement_text=tool_args.get("agreement_text", ""))
                else:
                    # Fallback for unknown tools
                    print(f"Warning: Unknown tool '{tool_name}', trying globals lookup")
                    if tool_name in globals():
                        tool_func = globals()[tool_name]
                        if hasattr(tool_func, 'invoke'):
                            result = tool_func.invoke(tool_args)
                        else:
                            result = tool_func(**tool_args)
                    else:
                        result = f"Error: Tool '{tool_name}' not found"
                
                print(f"Debug: Tool '{tool_name}' result: {str(result)[:100]}...")
                tool_results.append(ToolMessage(content=str(result), tool_call_id=tool_call_id))
                
            except Exception as tool_error:
                error_msg = f"Error executing tool '{tool_name}': {str(tool_error)}"
                print(f"Tool Error: {error_msg}")
                tool_results.append(ToolMessage(content=error_msg, tool_call_id=tool_call_id))

        return {"messages": tool_results}
        
    except Exception as e:
        print(f"Error in call_tool_node: {str(e)}")
        error_msg = f"Error in tool execution: {str(e)}"
        return {"messages": [ToolMessage(content=error_msg, tool_call_id="error")]}

# Define the conditional edge logic.
def should_continue(state: AgentState) -> Literal["tools", "end"]:
    last_message = state['messages'][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"
    else:
        return "end"

# Build the graph.
graph_builder = StateGraph(AgentState)
# Use our custom tool node instead of LangChain's ToolNode
# tool_node = ToolNode(tools)  # This doesn't pass user_id correctly

# Add nodes to the graph.
graph_builder.add_node("llm_node", call_llm_node)
graph_builder.add_node("tools", call_tool_node)  # Use our custom tool node

# Set the entry point.
graph_builder.add_edge(START, "llm_node")

# Add the conditional edge for the LLM's response.
graph_builder.add_conditional_edges(
    "llm_node",
    should_continue,
    {
        "tools": "tools",
        "end": END
    }
)

# After a tool is executed, return to the LLM to process the tool's output.
graph_builder.add_edge("tools", "llm_node")

# Compile the graph.
graph_agent = graph_builder.compile()

# Test the graph without memory first to debug the issue
# If this works, we'll add memory back properly
print("Debug: Using graph agent without memory wrapper for debugging")
agent_executor = graph_agent

# Uncomment this when we're ready to add memory back:
# agent_executor = RunnableWithMessageHistory(
#     graph_agent,
#     get_session_history,
#     input_messages_key="messages",
#     history_messages_key="messages"
# )
