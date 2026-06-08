from __future__ import annotations

import pytest

from src.services.contactout_service import ContactOutService
from src.utils.linkedin_search_utils import RecruiterCandidate


class DummyResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


def _candidate() -> RecruiterCandidate:
    return RecruiterCandidate(
        name="Jane Doe",
        first_name="Jane",
        last_name="Doe",
        title="Technical Recruiter",
        linkedin_url="https://www.linkedin.com/in/jane-doe",
    )


def test_contactout_service_returns_work_email(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict] = []

    def fake_get(url: str, **kwargs) -> DummyResponse:
        calls.append({"url": url, **kwargs})
        return DummyResponse({"profile": {"work_email": ["jane@acme.com"]}})

    monkeypatch.setattr("src.services.contactout_service.requests.get", fake_get)

    lead = ContactOutService("token", 3).find_email_for_candidate(_candidate())

    assert lead.email == "jane@acme.com"
    assert lead.contactout_email == "jane@acme.com"
    assert lead.lead_source == "contactout"
    assert calls[0]["headers"]["token"] == "token"
    assert calls[0]["params"]["email_type"] == "work"


def test_contactout_service_respects_per_run_limit() -> None:
    service = ContactOutService("token", 0)

    with pytest.raises(RuntimeError, match="ContactOut search limit"):
        service.find_email_for_candidate(_candidate())
