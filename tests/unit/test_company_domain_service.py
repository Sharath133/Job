import pytest

from src.services.company_domain_service import CompanyDomainService, pick_best_clearbit_domain


class FakeResponse:
    def __init__(self, payload: list[dict] | dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> list[dict] | dict:
        return self._payload


class TestPickBestClearbitDomain:
    def test_prefers_exact_name_match(self) -> None:
        suggestions = [
            {"name": "Infinity Learn", "domain": "infinitylearn.com", "logo": None},
            {"name": "INFINITY LEARNING", "domain": "infinitylearning.online", "logo": None},
        ]
        assert pick_best_clearbit_domain("Infinity Learn", suggestions) == "infinitylearn.com"

    def test_returns_first_domain_when_no_name_match(self) -> None:
        suggestions = [
            {"name": "Unrelated Co", "domain": "meril.eu", "logo": None},
            {"name": "Other", "domain": "other.com", "logo": None},
        ]
        assert pick_best_clearbit_domain("Meril", suggestions) == "meril.eu"


class TestCompanyDomainService:
    def test_resolves_domain_from_clearbit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "src.services.company_domain_service.requests.get",
            lambda url, params=None, timeout=15: FakeResponse(
                [
                    {"name": "Infinity Learn", "domain": "infinitylearn.com", "logo": None},
                    {"name": "INFINITY LEARNING", "domain": "infinitylearning.online", "logo": None},
                ]
            ),
        )
        domain = CompanyDomainService().resolve_domain("Infinity Learn")
        assert domain == "infinitylearn.com"

    def test_caches_domain_per_company(self, monkeypatch: pytest.MonkeyPatch) -> None:
        call_count = {"n": 0}

        def fake_get(url: str, params: dict | None = None, timeout: int = 15) -> FakeResponse:
            call_count["n"] += 1
            return FakeResponse([{"name": "Acme", "domain": "acme.com", "logo": None}])

        monkeypatch.setattr("src.services.company_domain_service.requests.get", fake_get)
        service = CompanyDomainService()
        assert service.resolve_domain("Acme") == "acme.com"
        assert service.resolve_domain("Acme") == "acme.com"
        assert call_count["n"] == 1

    def test_falls_back_to_guess_when_clearbit_fails(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fake_get(url: str, params: dict | None = None, timeout: int = 15) -> FakeResponse:
            raise ConnectionError("clearbit down")

        monkeypatch.setattr("src.services.company_domain_service.requests.get", fake_get)
        domain = CompanyDomainService().resolve_domain("Acme Technologies Inc")
        assert domain == "acme.com"
