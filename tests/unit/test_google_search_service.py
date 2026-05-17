import pytest

from src.services.google_search_service import GoogleSearchService


class DummyResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


def test_google_search_returns_recruiter_candidates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "src.services.google_search_service.requests.get",
        lambda *args, **kwargs: DummyResponse(
            {
                "items": [
                    {
                        "title": "Jane Doe - Technical Recruiter - Acme | LinkedIn",
                        "snippet": "HR and talent acquisition",
                        "link": "https://www.linkedin.com/in/jane-doe",
                    }
                ]
            }
        ),
    )
    candidates = GoogleSearchService("key", "cx", max_searches_per_run=3).find_recruiter_candidates(
        "Acme Corp"
    )
    assert len(candidates) == 1
    assert candidates[0].first_name == "Jane"
