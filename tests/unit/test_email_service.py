import pytest

from src.models import EmailDraft
from src.services.email_service import EmailService


def test_can_send_respects_daily_limit() -> None:
    service = EmailService("smtp.gmail.com", 587, "a@a.com", "pw", daily_limit=25)
    assert service.can_send(24)
    assert not service.can_send(25)


def test_send_email_rejects_invalid_draft() -> None:
    service = EmailService("smtp.gmail.com", 587, "a@a.com", "pw", daily_limit=25)
    with pytest.raises(ValueError, match="Invalid email draft"):
        service.send_email("r@example.com", EmailDraft(subject="", body="", is_valid=False, validation_error="bad"))


def test_send_email_builds_multipart_html_with_attachment(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    captured: dict = {}

    class FakeSMTP:
        def __init__(self, host: str, port: int, timeout: int = 30) -> None:
            captured["host"] = host

        def __enter__(self):
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def starttls(self) -> None:
            return None

        def login(self, user: str, password: str) -> None:
            captured["login"] = (user, password)

        def send_message(self, message) -> None:
            captured["message"] = message

    monkeypatch.setattr("src.services.email_service.smtplib.SMTP", FakeSMTP)

    draft = EmailDraft(
        subject="Role at **Acme**",
        body="Hi **Jane**,\n\nInterested in **Python**.",
        is_valid=True,
    )
    resume_path = tmp_path / "resume.pdf"
    resume_path.write_bytes(b"%PDF-1.4\n")

    EmailService("smtp.gmail.com", 587, "sender@test.com", "pw", daily_limit=25).send_email(
        "recruiter@test.com", draft, str(resume_path)
    )

    message = captured["message"]
    assert message["Subject"] == "Role at Acme"
    assert message.is_multipart()

    plain_part = ""
    html_part = ""
    attachment_part = None
    for part in message.walk():
        if part.get_content_type() == "text/plain":
            plain_part = part.get_content()
        elif part.get_content_type() == "text/html":
            html_part = part.get_content()
        elif part.get_filename() == "resume.pdf":
            attachment_part = part

    assert "**" not in plain_part
    assert "Jane" in plain_part
    assert "<strong>Jane</strong>" in html_part
    assert "<strong>Python</strong>" in html_part
    assert attachment_part is not None
    assert attachment_part.get_content_type() == "application/pdf"
