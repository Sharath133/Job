import pytest

from src.services.hunter_service import HunterService
from tests.unit.test_helpers import FakeDomainResolver


class DummyResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


def test_hunter_limit_enforced(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "src.services.hunter_service.requests.get",
        lambda *args, **kwargs: DummyResponse({"data": {"emails": []}}),
    )
    service = HunterService(api_key="x", max_searches_per_run=1, domain_resolver=FakeDomainResolver())
    service.find_recruiter_for_company("Acme")
    with pytest.raises(RuntimeError, match="limit"):
        service.find_recruiter_for_company("Acme")


def test_hunter_prefers_recruiter_title(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "src.services.hunter_service.requests.get",
        lambda *args, **kwargs: DummyResponse(
            {
                "data": {
                    "emails": [
                        {
                            "value": "ceo@acme.com",
                            "first_name": "Bob",
                            "last_name": "CEO",
                            "position": "Chief Executive Officer",
                        },
                        {
                            "value": "jane@acme.com",
                            "first_name": "Jane",
                            "last_name": "Doe",
                            "position": "Technical Recruiter",
                        },
                    ]
                }
            }
        ),
    )
    service = HunterService(api_key="x", max_searches_per_run=3, domain_resolver=FakeDomainResolver())
    lead = service.find_recruiter_for_company("Acme Corp")
    assert lead.email == "jane@acme.com"
    assert lead.name == "Jane Doe"


def test_hunter_passes_domain_and_department(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    def fake_get(url: str, params: dict | None = None, timeout: int = 30) -> DummyResponse:
        captured["url"] = url
        captured["params"] = params or {}
        return DummyResponse({"data": {"emails": []}})

    monkeypatch.setattr("src.services.hunter_service.requests.get", fake_get)
    HunterService(
        api_key="secret", max_searches_per_run=3, domain_resolver=FakeDomainResolver()
    ).find_recruiter_for_company("Acme Inc")
    assert captured["url"] == "https://api.hunter.io/v2/domain-search"
    assert captured["params"]["domain"] == "acme.com"
    assert captured["params"]["department"] == "hr"
    assert captured["params"]["api_key"] == "secret"


def test_hunter_email_finder_returns_email(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    def fake_get(url: str, params: dict | None = None, timeout: int = 30) -> DummyResponse:
        captured["url"] = url
        captured["params"] = params or {}
        return DummyResponse(
            {
                "data": {
                    "first_name": "Jane",
                    "last_name": "Doe",
                    "email": "jane@acme.com",
                    "position": "Technical Recruiter",
                }
            }
        )

    monkeypatch.setattr("src.services.hunter_service.requests.get", fake_get)
    lead = HunterService(
        api_key="secret", max_searches_per_run=3, domain_resolver=FakeDomainResolver()
    ).find_email_for_person("Acme Inc", "Jane", "Doe")
    assert lead.email == "jane@acme.com"
    assert captured["url"] == "https://api.hunter.io/v2/email-finder"
    assert captured["params"]["first_name"] == "Jane"
    assert captured["params"]["last_name"] == "Doe"
