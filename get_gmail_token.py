import os
import json
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/gmail.send']

def main():
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('credentials.json'):
                print("❌ 錯誤: 找不到 'credentials.json' (GCP Client Secret File)。")
                print("請先前往 Google Cloud Console 下載憑證，並將其重新命名為 'credentials.json' 放置於此目錄。")
                return

            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
            
    print("\n✅ OAuth 認證成功！")
    print("----------------------------------------------------------------")
    print("請複製以下 JSON 內容 (包含大括號)，並貼到 Hugging Face 的 Secrets 中：")
    print("Key: GMAIL_CREDENTIALS")
    print("Value:")
    print("----------------------------------------------------------------")
    print(creds.to_json())
    print("----------------------------------------------------------------")

if __name__ == '__main__':
    main()
