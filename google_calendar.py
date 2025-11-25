import os
import pickle
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
import requests

# --- Constants ---
CLIENT_SECRETS_FILE = 'client_secret.json'
SCOPES = ['https://www.googleapis.com/auth/calendar']
API_SERVICE_NAME = 'calendar'
API_VERSION = 'v3'

def get_calendar_service(credentials):
    """Builds and returns a Google Calendar service object."""
    return build(API_SERVICE_NAME, API_VERSION, credentials=credentials)



def get_user_credentials(user_id):
    """Retrieves user's stored credentials."""
    creds_path = f'token_{user_id}.pickle'
    if os.path.exists(creds_path):
        with open(creds_path, 'rb') as token:
            return pickle.load(token)
    return None

def save_user_credentials(user_id, credentials):
    """Saves user's credentials for future use."""
    creds_path = f'token_{user_id}.pickle'
    with open(creds_path, 'wb') as token:
        pickle.dump(credentials, token)

def get_authorization_url(redirect_uri):
    """Generates and returns the Google authorization URL."""
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, scopes=SCOPES,
        redirect_uri=redirect_uri)
    auth_url, state = flow.authorization_url(access_type='offline', prompt='consent', include_granted_scopes='true')
    return auth_url, state

def delete_user_credentials(user_id):
    """Deletes stored credentials and attempts token revocation."""
    creds = get_user_credentials(user_id)
    # Remove local token file
    creds_path = f'token_{user_id}.pickle'
    if os.path.exists(creds_path):
        try:
            os.remove(creds_path)
        except Exception:
            pass
    # Attempt to revoke token if available
    try:
        if creds and getattr(creds, 'token', None):
            requests.post(
                'https://oauth2.googleapis.com/revoke',
                params={'token': creds.token},
                headers={'content-type': 'application/x-www-form-urlencoded'}
            )
    except Exception:
        # Best-effort revocation; ignore network errors
        pass
