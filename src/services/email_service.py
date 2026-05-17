from __future__ import annotations

import smtplib
from email.message import EmailMessage

from src.models import EmailDraft
from src.utils.email_html_utils import markdown_bold_to_html, strip_markdown_bold


class EmailService:
    """SMTP sender with daily cap controls and HTML multipart support."""

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        sender_email: str,
        app_password: str,
        daily_limit: int,
    ) -> None:
        self._smtp_host = smtp_host
        self._smtp_port = smtp_port
        self._sender_email = sender_email
        self._app_password = app_password
        self._daily_limit = daily_limit

    def can_send(self, already_sent_today: int) -> bool:
        return already_sent_today < self._daily_limit

    def send_email(self, recipient_email: str, draft: EmailDraft) -> None:
        if not draft.is_valid:
            raise ValueError(f"Invalid email draft: {draft.validation_error}")

        message = EmailMessage()
        message["From"] = self._sender_email
        message["To"] = recipient_email
        message["Subject"] = strip_markdown_bold(draft.subject)
        message.set_content(strip_markdown_bold(draft.body))
        message.add_alternative(markdown_bold_to_html(draft.body), subtype="html")

        with smtplib.SMTP(self._smtp_host, self._smtp_port, timeout=30) as smtp:
            smtp.starttls()
            smtp.login(self._sender_email, self._app_password)
            smtp.send_message(message)
