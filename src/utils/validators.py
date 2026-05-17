from __future__ import annotations

import re

from src.models import EmailDraft
from src.utils.email_html_utils import strip_markdown_bold


class Validators:
    @staticmethod
    def has_non_empty_description(description: str) -> bool:
        return bool(description and description.strip())

    @staticmethod
    def is_valid_recruiter_email(email: str) -> bool:
        return bool(email and "@" in email and "." in email.split("@")[-1])

    @staticmethod
    def parse_subject_and_body(raw_email: str) -> EmailDraft:
        if "Subject:" not in raw_email:
            return EmailDraft(subject="", body=raw_email, is_valid=False, validation_error="Missing Subject line")

        subject_match = re.search(r"^Subject:\s*(.+)$", raw_email, flags=re.MULTILINE)
        if not subject_match:
            return EmailDraft(subject="", body=raw_email, is_valid=False, validation_error="Invalid Subject format")

        subject = strip_markdown_bold(subject_match.group(1).strip())
        body = raw_email.replace(subject_match.group(0), "", 1).strip()
        if not body:
            return EmailDraft(subject=subject, body=body, is_valid=False, validation_error="Missing email body")
        return EmailDraft(subject=subject, body=body, is_valid=True)
