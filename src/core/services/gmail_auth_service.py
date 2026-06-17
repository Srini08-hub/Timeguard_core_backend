# src/core/services/gmail_auth_service.py

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from src.config.settings import settings

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


class GmailAuthService:
    @staticmethod
    def get_credentials() -> Credentials:

        creds = Credentials(
            token=None,
            refresh_token=settings.GOOGLE_REFRESH_TOKEN,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.GOOGLE_CLIENT_ID,
            client_secret=settings.GOOGLE_CLIENT_SECRET,
            scopes=SCOPES,
        )

        creds.refresh(Request())

        return creds
