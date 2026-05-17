import pytest

from src.services.snov_service import SnovService
from tests.unit.test_helpers import FakeDomainResolver


class DummyResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


def test_snov_limit_enforced(monkeypatch: pytest.MonkeyPatch) -> None:
    service = SnovService(
        client_id="id", client_secret="secret", max_searches_per_run=1, domain_resolver=FakeDomainResolver()
    )
    service._access_token = "token"
    monkeypatch.setattr(
        "src.services.snov_service.requests.post",
        lambda *args, **kwargs: DummyResponse({"data": []}),
    )
    service.find_recruiter_for_company("Acme")
    with pytest.raises(RuntimeError, match="limit"):
        service.find_recruiter_for_company("Acme")


def test_snov_prefers_recruiter_title(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def fake_post(url: str, data: dict | None = None, timeout: int = 30) -> DummyResponse:
        calls.append(url)
        if url.endswith("access_token"):
            return DummyResponse({"access_token": "token"})
        return DummyResponse(
            {
                "data": [
                    {
                        "email": "ceo@acme.com",
                        "firstName": "Bob",
                        "lastName": "CEO",
                        "position": "Chief Executive Officer",
                    },
                    {
                        "email": "jane@acme.com",
                        "firstName": "Jane",
                        "lastName": "Doe",
                        "position": "Technical Recruiter",
                    },
                ]
            }
        )

    monkeypatch.setattr("src.services.snov_service.requests.post", fake_post)
    lead = SnovService(
        client_id="id", client_secret="secret", max_searches_per_run=3, domain_resolver=FakeDomainResolver()
    ).find_recruiter_for_company("Acme Corp")
    assert lead.email == "jane@acme.com"
    assert calls[0].endswith("oauth/access_token")
