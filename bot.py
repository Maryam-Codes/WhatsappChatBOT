import os
import datetime
from dotenv import load_dotenv


from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import SQLChatMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

# Import the REAL Google Tools
from google_tools import google_tools

load_dotenv()

# ------------------------------------------------------------
# 1. Setup Tools
# ------------------------------------------------------------
# Use the real Google tools list
tools = google_tools

# ------------------------------------------------------------
# 2. Create the LLM (Gemini 1.5 Flash)
# ------------------------------------------------------------
if not os.getenv("GOOGLE_API_KEY"):
    print("❌ Error: GOOGLE_API_KEY is missing from .env.")

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0
)

# ------------------------------------------------------------
# 3. Prompt Template
# ------------------------------------------------------------
# Calculate today's date for the bot so it knows what "Tomorrow" means
current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

system_prompt_text = f"""🎓 ROLE & IDENTITY
You are Eva, the AI Executive Assistant for Blackstone School of Law & Business.
Current Date & Time: {current_time}

Your Real-World Capabilities:
1. 📅 **Calendar:** Book real appointments on Google Calendar.
2. 📧 **Email:** Send real emails via Gmail.
3. 📊 **Sheets:** Log data to Google Sheets.

⚠️ IMPORTANT RULES:
- **Dates:** Convert relative terms (e.g., "tomorrow at 5pm") into ISO format (YYYY-MM-DDTHH:MM:SS) for the tools.
- **Missing Info:** If asked to book a meeting, ALWAYS confirm the date/time first if not provided.
- **Formatting:** Keep responses concise and professional. Use emojis (✅, 📅) sparingly.

Tone: Professional, efficient, and polite.
"""

prompt = ChatPromptTemplate.from_messages([
    ("system", system_prompt_text),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])

# ------------------------------------------------------------
# 4. Build Agent
# ------------------------------------------------------------
agent = create_tool_calling_agent(llm, tools, prompt)

agent_executor = AgentExecutor(
    agent=agent, 
    tools=tools, 
    verbose=True  # Keep this True to see tool usage in terminal
)

# ------------------------------------------------------------
# 5. Memory Setup
# ------------------------------------------------------------
def get_session_history(session_id: str):
    return SQLChatMessageHistory(
        session_id=session_id,
        connection="sqlite:///memory.db"
    )

agent_with_history = RunnableWithMessageHistory(
    agent_executor,
    get_session_history,
    input_messages_key="input",
    history_messages_key="chat_history"
)

# ------------------------------------------------------------
# 6. Main Function to Export
# ------------------------------------------------------------
def process_ai_response(user_input: str, user_phone: str) -> str:
    try:
        response = agent_with_history.invoke(
            {"input": user_input},
            config={"configurable": {"session_id": user_phone}}
        )
        return response["output"]
    except Exception as e:
        print(f"AI Error: {e}") 
        return "I'm sorry, I encountered an internal error connecting to my tools. Please try again."