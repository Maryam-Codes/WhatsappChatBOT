import os
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# The permissions your bot needs
SCOPES = [
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/spreadsheets'
]

def authenticate():
    creds = None
    # 1. Check for existing token
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    # 2. If no token, log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                print("Token expired and cannot refresh. Delete token.json and try again.")
                return
        else:
            if not os.path.exists('credentials.json'):
                print("❌ MISSING: credentials.json")
                print("👉 Go to Google Cloud Console > APIs & Services > Credentials")
                print("👉 Create OAuth 2.0 Client ID (Desktop App) -> Download JSON -> Rename to 'credentials.json'")
                return

            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save the token for the bot to use later
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
            print("✅ Success! token.json created. Your bot can now access Google.")

if __name__ == '__main__':
    authenticate()