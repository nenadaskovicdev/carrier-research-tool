import pickle
import os
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# Configuration
CREDENTIALS_FILE = "credentials.json"
TOKEN_PICKLE = "token.pickle"
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

def generate_token():
    """Generate token.pickle file for Gmail API access"""
    creds = None
    
    # Check if token already exists
    if os.path.exists(TOKEN_PICKLE):
        print(f"✅ token.pickle already exists at {TOKEN_PICKLE}")
        with open(TOKEN_PICKLE, "rb") as token:
            creds = pickle.load(token)
        print("✅ Token loaded successfully")
        return True
    
    # Check if credentials file exists
    if not os.path.exists(CREDENTIALS_FILE):
        print(f"❌ credentials.json not found at {CREDENTIALS_FILE}")
        print("Follow these steps to create it:")
        print("1. Go to https://console.cloud.google.com/")
        print("2. Create a project or select existing one")
        print("3. Enable Gmail API")
        print("4. Create OAuth 2.0 credentials (Desktop app type)")
        print("5. Download as credentials.json and save in current folder")
        return False
    
    # Generate new token
    print("🔐 Starting Google OAuth authentication...")
    print("A browser window will open. Please:")
    print("1. Log into your Google account")
    print("2. Grant permission for Gmail access")
    print("3. Complete the authorization")
    
    try:
        flow = InstalledAppFlow.from_client_secrets_file(
            CREDENTIALS_FILE, SCOPES
        )
        creds = flow.run_local_server(port=0)
        
        # Save the credentials for the next run
        with open(TOKEN_PICKLE, "wb") as token:
            pickle.dump(creds, token)
        
        print("✅ Successfully generated token.pickle!")
        print(f"✅ Token saved to: {TOKEN_PICKLE}")
        return True
        
    except Exception as e:
        print(f"❌ Error generating token: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Google OAuth Token Generator")
    print("=" * 60)
    
    success = generate_token()
    
    if success:
        print("\n✅ Token generation successful!")
        print("You can now run the scraper.")
    else:
        print("\n❌ Token generation failed.")
    print("=" * 60)