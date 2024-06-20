import os
import base64
import requests
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")

def get_access_token():
    """Get access token using client credentials."""
    auth_str = f"{CLIENT_ID}:{CLIENT_SECRET}"
    auth_bytes = auth_str.encode('utf-8')
    auth_base64 = base64.b64encode(auth_bytes).decode('utf-8')

    url = "https://auth.tidal.com/v1/oauth2/token"
    payload = "grant_type=client_credentials"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {auth_base64}"
    }
    
    response = requests.post(url, data=payload, headers=headers)
    response.raise_for_status()
    response_data = response.json()
    return response_data["access_token"]

if __name__ == "__main__":
    access_token = get_access_token()
    print(f"Access token: {access_token}")
