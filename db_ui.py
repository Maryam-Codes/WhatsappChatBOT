import sqlite3
import json
import os
from passlib.context import CryptContext

DB_FILE = "memory.db"
# Use bcrypt for password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ==========================================
# 1. USER MANAGEMENT (The Missing Part)
# ==========================================

def init_db(default_admin, default_pass):
    """Creates tables and ensures default admin exists."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Create Users Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL
        )
    ''')
    
    # Create Message Store (if LangChain hasn't yet)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS message_store (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            message TEXT
        )
    ''')

    # Check if admin exists, if not, create
    cursor.execute("SELECT * FROM users WHERE username = ?", (default_admin,))
    if not cursor.fetchone():
        hashed = pwd_context.hash(default_pass)
        cursor.execute("INSERT INTO users VALUES (?, ?, ?)", (default_admin, hashed, 'admin'))
        print(f"✅ Default Admin '{default_admin}' created.")
    
    conn.commit()
    conn.close()

def authenticate_user(username, password):
    """Returns user role if valid, else None."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT password_hash, role FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    conn.close()

    if row and pwd_context.verify(password, row[0]):
        return row[1] # Return role (e.g., 'admin')
    return None

def create_user(username, password, role='viewer'):
    conn = sqlite3.connect(DB_FILE)
    try:
        hashed = pwd_context.hash(password)
        conn.execute("INSERT INTO users VALUES (?, ?, ?)", (username, hashed, role))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False # User exists
    finally:
        conn.close()

def delete_user(username):
    conn = sqlite3.connect(DB_FILE)
    conn.execute("DELETE FROM users WHERE username = ?", (username,))
    conn.commit()
    conn.close()

def get_all_users():
    """Returns a list of all users and their roles."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT username, role FROM users")
    users = [{"username": r[0], "role": r[1]} for r in cursor.fetchall()]
    conn.close()
    return users

# ==========================================
# 2. CHAT HISTORY FUNCTIONS (Your Existing Logic)
# ==========================================

def get_all_contacts_from_db():
    if not os.path.exists(DB_FILE): return []
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT session_id FROM message_store")
        rows = cursor.fetchall()
        conn.close()
        return [row[0] for row in rows if row[0]]
    except Exception as e:
        print(f"DB Error: {e}")
        return []

def get_chat_history_for_ui(session_id):
    if not os.path.exists(DB_FILE): return []
    history = []
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT message FROM message_store WHERE session_id = ? ORDER BY id ASC", (session_id,))
        for row in cursor.fetchall():
            try:
                msg_json = row[0]
                msg_data = json.loads(msg_json)
                
                # Robust parsing for different LangChain versions
                msg_type = msg_data.get('type', 'unknown')
                content = ""
                
                if 'data' in msg_data and 'content' in msg_data['data']:
                     content = msg_data['data']['content']
                elif 'content' in msg_data:
                     content = msg_data['content']
                elif 'kwargs' in msg_data:
                     content = msg_data['kwargs'].get('content', '')
                
                if content:
                    history.append({"type": msg_type, "text": content})
            except Exception:
                continue
        conn.close()
    except Exception as e: 
        print(f"Error reading chat history: {e}")
    return history