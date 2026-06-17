import base64
import logging
from dataclasses import dataclass, field
from email.utils import parseaddr
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from src.config.settings import settings

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


@dataclass
class RawAttachment:
    gmail_attachment_id: str
    filename: str
    mime_type: str
    size: int


@dataclass
class RawEmail:
    gmail_message_id: str
    gmail_thread_id: str
    sender_email: str
    subject: str | None
    body_text: str | None
    received_at_ms: int  # internalDate from Gmail (epoch ms)
    attachments: list[RawAttachment] = field(default_factory=list)


class GmailService:
    """
    Wraps the Gmail API. All methods are synchronous (run inside Celery workers).
    Build the service once per task to avoid credential reuse across processes.
    """

    def __init__(self) -> None:
        credentials = Credentials(
            token=None,
            refresh_token=settings.GOOGLE_REFRESH_TOKEN,
            client_id=settings.GOOGLE_CLIENT_ID,
            client_secret=settings.GOOGLE_CLIENT_SECRET,
            token_uri="https://oauth2.googleapis.com/token",
            scopes=SCOPES,
        )
        credentials.refresh(Request())
        self._svc = build("gmail", "v1", credentials=credentials, cache_discovery=False)

    def fetch_email(self, gmail_message_id: str) -> RawEmail:
        """Fetch and parse a single Gmail message by its message ID."""
        try:
            msg = (
                self._svc.users()
                .messages()
                .get(userId="me", id=gmail_message_id, format="full")
                .execute()
            )
        except HttpError as exc:
            logger.error(
                "Gmail API error fetching message %s: %s", gmail_message_id, exc
            )
            raise

        return self._parse_message(msg)

    def download_attachment(self, gmail_message_id: str, attachment_id: str) -> bytes:
        """Download a raw attachment and return its decoded bytes."""
        try:
            resp = (
                self._svc.users()
                .messages()
                .attachments()
                .get(userId="me", messageId=gmail_message_id, id=attachment_id)
                .execute()
            )
        except HttpError as exc:
            logger.error(
                "Gmail API error downloading attachment %s from message %s: %s",
                attachment_id,
                gmail_message_id,
                exc,
            )
            raise

        data = resp.get("data", "")
        # Gmail uses URL-safe base64
        return base64.urlsafe_b64decode(data + "==")

    def _parse_message(self, msg: dict) -> RawEmail:
        headers = {
            h["name"].lower(): h["value"] for h in msg["payload"].get("headers", [])
        }
        # logger.info(msg)
        sender_raw = headers.get("from", "")
        _, sender_email = parseaddr(sender_raw)

        return RawEmail(
            gmail_message_id=msg["id"],
            gmail_thread_id=msg["threadId"],
            sender_email=sender_email,
            subject=headers.get("subject"),
            body_text=self._extract_body(msg["payload"]),
            received_at_ms=int(msg["internalDate"]),
            attachments=self._extract_attachments(msg["payload"]),
        )

    def _extract_body(self, payload: dict) -> str | None:
        """Recursively find the first text/plain part."""
        if payload.get("mimeType") == "text/plain":
            data = payload.get("body", {}).get("data")
            if data:
                return base64.urlsafe_b64decode(data + "==").decode(
                    "utf-8", errors="replace"
                )

        for part in payload.get("parts", []):
            result = self._extract_body(part)
            if result:
                return result

        return None

    def _extract_attachments(self, payload: dict) -> list[RawAttachment]:
        attachments: list[RawAttachment] = []

        for part in payload.get("parts", []):
            attachment_id = part.get("body", {}).get("attachmentId")
            filename = part.get("filename", "")

            if attachment_id and filename:
                attachments.append(
                    RawAttachment(
                        gmail_attachment_id=attachment_id,
                        filename=filename,
                        mime_type=part.get("mimeType", "application/octet-stream"),
                        size=part.get("body", {}).get("size", 0),
                    )
                )

            # Recurse into nested parts
            #  (e.g. multipart/mixed inside multipart/alternative)
            attachments.extend(self._extract_attachments(part))

        return attachments

    def get_profile(self) -> Any:
        try:
            return self._svc.users().getProfile(userId="me").execute()
        except HttpError:
            logger.exception("Failed to fetch Gmail profile")
            raise

    def get_history(self, start_history_id: str) -> dict[str, Any]:
        try:
            history_items: list[dict[str, Any]] = []
            latest_history_id: str | None = None
            page_token: str | None = None

            while True:
                request_kwargs: dict[str, Any] = {
                    "userId": "me",
                    "startHistoryId": start_history_id,
                    "historyTypes": ["messageAdded"],
                }
                if page_token is not None:
                    request_kwargs["pageToken"] = page_token

                response = self._svc.users().history().list(**request_kwargs).execute()

                history_items.extend(response.get("history", []))
                latest_history_id = response.get("historyId", latest_history_id)
                page_token = response.get("nextPageToken")

                if page_token is None:
                    break

            return {
                "history": history_items,
                "historyId": latest_history_id,
            }
        except HttpError:
            logger.exception(
                "Failed to fetch Gmail history for start_history_id=%s",
                start_history_id,
            )
            raise

    # def get_message(self, message_id: str) -> dict[str, Any]:
    #     try:
    #         return self.get_service().users().messages().get(
    #             userId="me",
    #             id=message_id,
    #             format="full",
    #         ).execute()
    #     except HttpError:
    #         logger.exception("Failed to fetch Gmail message %s", message_id)
    #         raise
