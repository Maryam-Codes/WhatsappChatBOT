import os
import uvicorn
import requests
from dotenv import load_dotenv

from fastapi import FastAPI, Request, HTTPException, BackgroundTasks, Form, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

# Import your Bot Logic and Database Manager
# Ensure bot.py and db_ui.py are in the same folder as this file
from bot import process_ai_response
import db_ui 

# Load environment variables
load_dotenv()

app = FastAPI()

# ==========================================
# 1. CONFIGURATION
# ==========================================
SECRET_KEY = os.getenv("SECRET_KEY", "change_this_to_random_string")
ADMIN_USER = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASSWORD", "admin123")
VERIFY_TOKEN = os.getenv("META_VERIFY_TOKEN")
PHONE_ID = os.getenv("META_PHONE_NUMBER_ID")
ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN")

# ==========================================
# 2. MIDDLEWARE & TEMPLATES
# ==========================================
# This handles the Login Cookies. 3600 seconds = 1 hour session.
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, max_age=3600)

# This tells FastAPI where to find your HTML files
templates = Jinja2Templates(directory="templates")

# ==========================================
# 3. STARTUP LOGIC (Crucial for Admin)
# ==========================================
@app.on_event("startup")
def startup_db():
    """
    Runs automatically when the server starts.
    It tells the database to create the tables and ensure the default Admin exists.
    """
    db_ui.init_db(ADMIN_USER, ADMIN_PASS)
    print(f"✅ Database initialized. Default Admin: {ADMIN_USER}")

# ==========================================
# 4. HELPER FUNCTIONS
# ==========================================
def send_to_whatsapp(recipient_id: str, text: str):
    """Sends a text message back to WhatsApp via Meta's API."""
    url = f"https://graph.facebook.com/v17.0/{PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": recipient_id,
        "type": "text",
        "text": {"body": text}
    }
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
    except Exception as e:
        print(f"❌ Error sending to Meta: {e}")

async def handle_message_logic(sender_id: str, user_message: str):
    """Background task to process AI response without blocking the webhook."""
    ai_response = process_ai_response(user_message, sender_id)
    send_to_whatsapp(sender_id, ai_response)

# ==========================================
# 5. AUTHENTICATION ROUTES (Login/Logout)
# ==========================================
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    # Validate against SQLite Database
    role = db_ui.authenticate_user(username, password)
    
    if role:
        # Success: Save user identity into the session cookie
        request.session["user"] = username
        request.session["role"] = role
        print(f"🔓 Login Success: {username} ({role})")
        return RedirectResponse(url="/", status_code=303)
    
    # Failure
    return templates.TemplateResponse("login.html", {
        "request": request, 
        "error": "Invalid Username or Password"
    })

@app.get("/logout")
async def logout(request: Request):
    request.session.clear() # Destroy cookie
    return RedirectResponse(url="/login")

# ==========================================
# 6. ADMIN USER MANAGEMENT ROUTES
# ==========================================
@app.get("/users", response_class=HTMLResponse)
async def manage_users_view(request: Request):
    # Security: Only Admins can see this page
    if request.session.get("role") != "admin":
        return RedirectResponse(url="/")
        
    users = db_ui.get_all_users()
    return templates.TemplateResponse("users.html", {"request": request, "users": users})

@app.post("/users/add")
async def add_user(request: Request, new_user: str = Form(...), new_pass: str = Form(...), role: str = Form(...)):
    # Security: Only Admins can add users
    if request.session.get("role") != "admin":
        raise HTTPException(status_code=403)
        
    db_ui.create_user(new_user, new_pass, role)
    return RedirectResponse(url="/users", status_code=303)

@app.get("/users/delete/{username}")
async def delete_user(request: Request, username: str):
    # Security: Only Admins can delete users
    if request.session.get("role") != "admin":
        raise HTTPException(status_code=403)
        
    # Prevent deleting yourself
    if username != request.session.get("user"):
        db_ui.delete_user(username)
        
    return RedirectResponse(url="/users", status_code=303)

# ==========================================
# 7. DASHBOARD UI ROUTES
# ==========================================
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    # Check if logged in
    if not request.session.get("user"):
        return RedirectResponse(url="/login")

    contacts = db_ui.get_all_contacts_from_db()
    role = request.session.get("role")
    
    # Pass 'user_role' to the HTML so the "Manage Users" button knows when to show up
    return templates.TemplateResponse("index.html", {
        "request": request, 
        "contacts": contacts,
        "user_role": role 
    })

@app.get("/chat/{phone_number}", response_class=HTMLResponse)
async def chat_view(request: Request, phone_number: str):
    # Check if logged in
    if not request.session.get("user"):
        return RedirectResponse(url="/login")

    history = db_ui.get_chat_history_for_ui(phone_number)
    return templates.TemplateResponse("chat.html", {
        "request": request, 
        "history": history, 
        "contact": phone_number
    })

# ==========================================
# 8. WEBHOOK ROUTES (Meta Integration)
# ==========================================
@app.get("/webhook")
async def verify_webhook(request: Request):
    """
    This handles the 'Handshake' from Meta.
    It verifies that you own the server.
    """
    params = request.query_params
    if params.get("hub.mode") == "subscribe" and params.get("hub.verify_token") == VERIFY_TOKEN:
        return PlainTextResponse(content=params.get("hub.challenge"), status_code=200)
    raise HTTPException(status_code=403, detail="Verification Failed")

@app.post("/webhook")
async def webhook_handler(request: Request, background_tasks: BackgroundTasks):
    """
    This receives the actual WhatsApp messages.
    """
    data = await request.json()
    try:
        # Navigate through Meta's complex JSON structure
        entry = data['entry'][0]['changes'][0]['value']
        
        if 'messages' in entry:
            msg = entry['messages'][0]
            
            # Ensure it's a text message (ignore status updates like 'read' receipts)
            if 'text' in msg:
                # Process logic in background so Meta gets a fast 200 OK response
                background_tasks.add_task(handle_message_logic, msg['from'], msg['text']['body'])
                
    except Exception as e:
        # Use print for simple logging
        print(f"⚠️ Webhook Event Error (Ignored): {e}")
        
    return {"status": "received"}

# ==========================================
# 9. MAIN EXECUTION
# ==========================================
if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=5000, reload=True)