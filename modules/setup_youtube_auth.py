import os
from google_auth_oauthlib.flow import InstalledAppFlow

# The exact scopes required for seamlessly uploading YouTube videos autonomously
SCOPES = ['https://www.googleapis.com/auth/youtube.upload']

def main():
    print("=====================================================")
    print("      YouTube Local Authentication Setup             ")
    print("=====================================================")
    
    # 1. Require client_secrets.json in the same root directory securely.
    if not os.path.exists('client_secret.json'):
        print("ERROR: 'client_secret.json' firmly not found in the root directory.")
        print("ACTION: Please download your Desktop OAuth 2.0 Client IDs JSON from Google Cloud Console.")
        print("ACTION: Rename it exactly to 'client_secret.json' and place it in the same base folder.")
        return

    print("Spinning up local headless bridge. Opening native browser for Google Authentication...")
    
    # 2. Spin up local port and seamlessly hook Google Browser
    try:
        flow = InstalledAppFlow.from_client_secrets_file('client_secret.json', SCOPES)
        creds = flow.run_local_server(port=0)
    except Exception as e:
        print(f"Authentication Failed natively: {e}")
        return
    
    # 3. Dump the permanent refresh tokens to token.json
    with open('token.json', 'w') as token_file:
        token_file.write(creds.to_json())
        
    print("\nSUCCESS! Successfully authenticated and securely generated 'token.json'.")
    print("\n--------------------------------------------------------------")
    print("CRITICAL ACTION REQUIRED FOR GITHUB ACTIONS:")
    print("1. Open 'token.json' in your text editor safely.")
    print("2. Copy the ENTIRE JSON string contents identically.")
    print("3. Go to your GitHub Repository -> Settings -> Secrets and variables -> Actions.")
    print("4. Add New Repository Secret named precisely: YOUTUBE_AUTH_TOKEN")
    print("5. Paste the copied payload dynamically.")
    print("--------------------------------------------------------------\n")

if __name__ == '__main__':
    main()
