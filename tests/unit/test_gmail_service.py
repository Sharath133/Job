from __future__ import annotations

import base64
from email import message_from_bytes
from email.policy import default

from src.models import EmailDraft, FollowupRow
from src.services.gmail_service import GmailService


class FakeExecute:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def execute(self) -> dict:
        return self._payload


class FakeMessages:
    def __init__(self, captured: dict) -> None:
        self._captured = captured

    def send(self, userId: str, body: dict) -> FakeExecute:  # noqa: N803
        self._captured["send"] = {"userId": userId, "body": body}
        return FakeExecute({"id": "message-1", "threadId": body.get("threadId", "thread-1")})


class FakeThreads:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def get(self, **kwargs) -> FakeExecute:
        return FakeExecute(self._payload)


class FakeUsers:
    def __init__(self, captured: dict, thread_payload: dict) -> None:
        self._captured = captured
        self._thread_payload = thread_payload

    def messages(self) -> FakeMessages:
        return FakeMessages(self._captured)

    def threads(self) -> FakeThreads:
        return FakeThreads(self._thread_payload)


class FakeGmail:
    def __init__(self, captured: dict, thread_payload: dict | None = None) -> None:
        self._captured = captured
        self._thread_payload = thread_payload or {}

    def users(self) -> FakeUsers:
        return FakeUsers(self._captured, self._thread_payload)


def test_gmail_send_email_returns_message_metadata() -> None:
    captured: dict = {}
    service = GmailService("client", "secret", "refresh", "sender@example.com")
    service._service = FakeGmail(captured)  # type: ignore[assignment]

    result = service.send_email(
        "recruiter@example.com",
        EmailDraft(subject="Role at **Acme**", body="Hi **Jane**", is_valid=True),
    )

    assert result.message_id == "message-1"
    assert result.thread_id == "thread-1"
    assert captured["send"]["userId"] == "me"
    assert captured["send"]["body"]["raw"]


def test_gmail_followup_uses_existing_thread() -> None:
    captured: dict = {}
    service = GmailService("client", "secret", "refresh", "sender@example.com")
    service._service = FakeGmail(captured)  # type: ignore[assignment]

    result = service.send_followup(
        FollowupRow(
            row_number=2,
            timestamp="",
            job_id="job-1",
            job_title="Backend Engineer",
            company="Acme",
            recruiter_name="Jane",
            recruiter_email="jane@acme.com",
        email_subject="Backend Engineer @ Acme | Python, FastAPI, Django | IIT Ropar",
            followup_count=0,
            initial_email_sent_at="",
            last_followup_sent_at="",
            next_followup_due_at="",
            reply_status="unknown",
            thread_id="thread-123",
            message_id="message-1",
        )
    )

    assert result.thread_id == "thread-123"
    assert captured["send"]["body"]["threadId"] == "thread-123"
    raw_message = base64.urlsafe_b64decode(captured["send"]["body"]["raw"])
    message = message_from_bytes(raw_message, policy=default)
    assert message["Subject"] == "Backend Engineer @ Acme | Python, FastAPI, Django | IIT Ropar"


def test_gmail_has_reply_detects_non_sender_message() -> None:
    captured: dict = {}
    service = GmailService("client", "secret", "refresh", "sender@example.com")
    service._service = FakeGmail(  # type: ignore[assignment]
        captured,
        {
            "messages": [
                {"payload": {"headers": [{"name": "From", "value": "sender@example.com"}]}},
                {"payload": {"headers": [{"name": "From", "value": "Jane <jane@acme.com>"}]}},
            ]
        },
    )

    assert service.has_reply("thread-1")


def test_followup_template_is_consistent_for_all_followups() -> None:
    followup = FollowupRow(
        row_number=2,
        timestamp="",
        job_id="job-1",
        job_title="Backend Engineer",
        company="Acme",
        recruiter_name="Jane",
        recruiter_email="jane@acme.com",
            email_subject="Backend Engineer @ Acme | Python, FastAPI, Django | IIT Ropar",
        followup_count=2,
        initial_email_sent_at="",
        last_followup_sent_at="",
        next_followup_due_at="",
        reply_status="unknown",
        thread_id="thread-123",
        message_id="message-1",
    )

    body = GmailService._followup_body(followup)

    assert body == (
        "Hi Jane,\n\n"
        "I wanted to follow up again on my previous email regarding the Backend Engineer opportunity at Acme. "
        "My backend experience with Python, FastAPI/Django, production APIs, and scalable systems "
        "felt relevant to the role.\n\n"
        "Thank you for your time and consideration.\n\n"
        "Thankyou,\n"
        "Sharath,\n"
        "9347485455"
    )
