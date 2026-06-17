from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

flow = InstalledAppFlow.from_client_secrets_file("credential.json", SCOPES)

creds = flow.run_local_server(port=0, access_type="offline")

print("REFRESH TOKEN:")
print(creds.refresh_token)
