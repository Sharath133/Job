from __future__ import annotations

import base64
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any

from src.models import EmailDraft, EmailSendResult, FollowupRow
from src.utils.email_html_utils import markdown_bold_to_html, strip_markdown_bold


GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
]


class GmailService:
    """Gmail API sender and thread reader for reply-aware follow-ups."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        sender_email: str,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._refresh_token = refresh_token
        self._sender_email = sender_email
        self._service: Any | None = None

    def send_email(self, recipient_email: str, draft: EmailDraft, attachment_path: str | None = None) -> EmailSendResult:
        if not draft.is_valid:
            raise ValueError(f"Invalid email draft: {draft.validation_error}")

        message = self._build_message(
            recipient_email=recipient_email,
            subject=draft.subject,
            body=draft.body,
            attachment_path=attachment_path,
        )
        return self._send_raw_message(message)

    def send_followup(self, followup: FollowupRow) -> EmailSendResult:
        subject = followup.email_subject
        if subject and not subject.lower().startswith("re:"):
            subject = f"Re: {subject}"
        elif not subject:
            subject = f"Re: {followup.job_title} at {followup.company}"

        body = self._followup_body(followup)
        message = self._build_message(
            recipient_email=followup.recruiter_email,
            subject=subject,
            body=body,
        )
        return self._send_raw_message(message, thread_id=followup.thread_id)

    def has_reply(self, thread_id: str, sender_email: str | None = None) -> bool:
        if not thread_id:
            return False

        sender = (sender_email or self._sender_email).lower()
        thread = (
            self._gmail()
            .users()
            .threads()
            .get(userId="me", id=thread_id, format="metadata", metadataHeaders=["From"])
            .execute()
        )
        for message in thread.get("messages", []):
            headers = message.get("payload", {}).get("headers", [])
            from_header = self._header_value(headers, "From").lower()
            if from_header and sender not in from_header:
                return True
        return False

    def _send_raw_message(self, message: EmailMessage, thread_id: str = "") -> EmailSendResult:
        body = {"raw": base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")}
        if thread_id:
            body["threadId"] = thread_id
        sent = self._gmail().users().messages().send(userId="me", body=body).execute()
        return EmailSendResult(
            message_id=str(sent.get("id", "")),
            thread_id=str(sent.get("threadId", "")),
        )

    def _build_message(
        self,
        recipient_email: str,
        subject: str,
        body: str,
        attachment_path: str | None = None,
    ) -> EmailMessage:
        message = EmailMessage()
        message["From"] = self._sender_email
        message["To"] = recipient_email
        message["Subject"] = strip_markdown_bold(subject)
        message.set_content(strip_markdown_bold(body))
        message.add_alternative(markdown_bold_to_html(body), subtype="html")
        if attachment_path:
            self._attach_file(message, attachment_path)
        return message

    @staticmethod
    def _attach_file(message: EmailMessage, attachment_path: str) -> None:
        path = Path(attachment_path)
        if not path.is_file():
            raise FileNotFoundError(f"Email attachment not found: {attachment_path}")
        message.add_attachment(
            path.read_bytes(),
            maintype="application",
            subtype="pdf",
            filename=path.name,
        )

    @staticmethod
    def _followup_body(followup: FollowupRow) -> str:
        recruiter_name = followup.recruiter_name or "there"
        next_number = followup.followup_count + 1
        if next_number == 1:
            return (
                f"Hi {recruiter_name},\n\n"
                f"Just following up on my earlier email regarding the {followup.job_title} role at "
                f"{followup.company}. I would be glad to share more details if the role is still open.\n\n"
                "Best,\nSharath"
            )
        if next_number == 2:
            return (
                f"Hi {recruiter_name},\n\n"
                f"I wanted to follow up again on the {followup.job_title} opportunity at {followup.company}. "
                "My backend experience with Python, FastAPI/Django, production APIs, and scalable systems "
                "felt relevant to the role.\n\n"
                "Best,\nSharath"
            )
        return (
            f"Hi {recruiter_name},\n\n"
            f"This is my final follow-up regarding the {followup.job_title} role at {followup.company}. "
            "I remain interested and would be happy to connect if there is a fit.\n\n"
            "Best,\nSharath"
        )

    def _gmail(self) -> Any:
        if self._service is None:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build

            credentials = Credentials(
                token=None,
                refresh_token=self._refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=self._client_id,
                client_secret=self._client_secret,
                scopes=GMAIL_SCOPES,
            )
            credentials.refresh(Request())
            self._service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
        return self._service

    @staticmethod
    def _header_value(headers: list[dict[str, str]], name: str) -> str:
        for header in headers:
            if header.get("name", "").lower() == name.lower():
                return header.get("value", "")
        return ""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
