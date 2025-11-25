import os.path
import base64
from email.mime.text import MIMEText
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from langchain_core.tools import tool

# Scopes must match what you used in setup_google.py
SCOPES = [
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/spreadsheets'
]

def get_creds():
    """Gets valid user credentials from token.json."""
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    # Refresh token if expired
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"Error refreshing token: {e}")
                return None
    return creds

# --- TOOL 1: GOOGLE CALENDAR ---
@tool
def add_calendar_event(summary: str, start_time: str, end_time: str, email: str = None):
    """
    Creates a Google Calendar event. 
    Format dates as ISO string: '2025-11-20T14:00:00'.
    Args:
        summary: Title of the meeting (e.g., "Consultation with Ali")
        start_time: ISO format start time
        end_time: ISO format end time
        email: (Optional) Attendee email to invite
    """
    creds = get_creds()
    if not creds: return "❌ Error: Google Token is invalid."
    
    try:
        service = build('calendar', 'v3', credentials=creds)
        
        event = {
            'summary': summary,
            'start': {'dateTime': start_time, 'timeZone': 'Asia/Karachi'},
            'end': {'dateTime': end_time, 'timeZone': 'Asia/Karachi'},
        }
        
        if email:
            event['attendees'] = [{'email': email}]

        created_event = service.events().insert(calendarId='primary', body=event).execute()
        return f"✅ Event created successfully: {created_event.get('htmlLink')}"
    except Exception as e:
        return f"❌ Failed to create event: {str(e)}"

# --- TOOL 2: GMAIL ---
@tool
def send_gmail(to: str, subject: str, body: str):
    """
    Sends an email using the user's Gmail account.
    Args:
        to: Recipient email address
        subject: Email subject line
        body: The plain text content of the email
    """
    creds = get_creds()
    if not creds: return "❌ Error: Google Token is invalid."

    try:
        service = build('gmail', 'v1', credentials=creds)
        
        message = MIMEText(body)
        message['to'] = to
        message['subject'] = subject
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
        
        service.users().messages().send(userId='me', body={'raw': raw_message}).execute()
        return f"✅ Email sent successfully to {to}"
    except Exception as e:
        return f"❌ Failed to send email: {str(e)}"

# --- TOOL 3: GOOGLE SHEETS ---
@tool
def add_expense_row(date: str, item: str, amount: str):
    """
    Appends a row to the connected Google Sheet.
    Args:
        date: The date of the entry
        item: Description of the item or log
        amount: The value or cost associated
    """
    SPREADSHEET_ID = os.getenv("GOOGLE_SHEET_ID") 
    if not SPREADSHEET_ID:
        return "❌ Error: GOOGLE_SHEET_ID is missing in .env file."

    creds = get_creds()
    if not creds: return "❌ Error: Google Token is invalid."

    try:
        service = build('sheets', 'v4', credentials=creds)
        
        values = [[date, item, str(amount)]]
        body = {'values': values}
        
        result = service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID, 
            range="Sheet1!A:C",
            valueInputOption="USER_ENTERED", 
            body=body
        ).execute()
        
        return f"✅ Data logged to sheet. {result.get('updates').get('updatedCells')} cells updated."
    except Exception as e:
        return f"❌ Failed to update sheet: {str(e)}"

# Export list
google_tools = [add_calendar_event, send_gmail, add_expense_row]