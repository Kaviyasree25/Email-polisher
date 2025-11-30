# authorize.py
import os
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

def main():
    if not os.path.exists("credentials.json"):
        print("Place your OAuth client JSON as 'credentials.json' in project root.")
        return
    flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
    creds = flow.run_local_server(port=0)
    with open("token.json", "w") as token:
        token.write(creds.to_json())
    print("token.json created successfully. Keep it private.")

if __name__ == "__main__":
    main()
