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
tools = google_tools

# ------------------------------------------------------------
# 2. Create the LLM
# ------------------------------------------------------------
if not os.getenv("GOOGLE_API_KEY"):
    print("❌ Error: GOOGLE_API_KEY is missing from .env.")

# Using 1.5 Flash (2.5 does not exist yet)
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0
)

# ------------------------------------------------------------
# 3. Prompt Template
# ------------------------------------------------------------
# Calculate today's date
current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

# We use f-string for time, but we must DOUBLE ESCAPE {{ }} for JSON parts
system_prompt_text = f"""🎓 ROLE & IDENTITY
You represent Blackstone School of Law & Business, Lahore.

Identity: Professional staff member.
Tone: Polite, professional, clear, and very concise.
Language: English or Roman Urdu.

⚠️ STRICT FORMATTING RULES (CRITICAL):
1. DO NOT USE ASTERISKS (*) anywhere.
2. DO NOT bold text.
3. DO NOT use Markdown formatting.
4. DO NOT write long paragraphs. Use line breaks.
5. Use hyphens (-) or emojis (👉, 🔹) for lists.

⏳ DATE & TIME LOGIC (CRITICAL)
- Current Context: Today is {current_time}.
- Year Rule: ALWAYS assume the year is 2025 for upcoming appointments.
- If user says "Tomorrow": Calculate date based on current date.
- Past Dates: If a user asks for a date that has already passed, politely ask for a future date.

📍 CONTACT & LOCATION
Address: 5 Ahmed Block, Garden Town, Lahore.
Map: https://www.google.com/maps/search/?api=1&query=5+Ahmed+Block,+Garden+Town,+Lahore

🕓 BUSINESS HOURS (Asia/Karachi)
Mon-Fri: 09:00-17:00
Sat: 10:00-14:00
Sun: Closed

📘 PROGRAM — ACCA (Quick Overview)
- Papers: 13
- Duration: 2.5 to 3 years
- Sessions: March, June, Sept, Dec
- Modes: Physical, Online, Hybrid
- Careers: Analyst, Auditor, CFO

💰 SCHOLARSHIPS & DISCOUNTS
- 90% Talent Scholarship: 20% off
- 80% High Achiever: 10% off Early Bird
- Foundation Batches (FA1-F3) starting Jan 1, 2026: 20% off full year fee
- Skill Level (F5-F9 + F4) starting Dec 1, 2025: 20% off

🧾 ADMISSION DOCUMENTS
- Previous result card
- CNIC
- Passport size photo

💰 FEE-STRUCTURE BEHAVIOR
- Do NOT send the full fee list in text.
- General Inquiry: Share this link: [Google Drive Document Link]
- Specific Paper Inquiry: Use the "ACCA_Fee_Structure" tool. Return ONLY the exact amount.

🗓 APPOINTMENT LOGIC (Google Meet)
Offer free online consultation via Google Meet.
Required details: Name, Phone, Email, Program, Purpose, Date, Time.

Validation:
- Check if date/time is in the past.
- Check if outside business hours.
- If Closed: "We are closed then. Hours are Mon-Fri 09:00-17:00, Sat 10:00-14:00."

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
    verbose=True
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
# 6. Main Function
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
        return "I'm sorry, I encountered an internal error. Please try again."
