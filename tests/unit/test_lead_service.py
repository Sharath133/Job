import logging

import pytest

from src.models import JobRecord, RecruiterLead
from src.services.google_search_service import GoogleSearchService
from src.services.hunter_service import HunterService
from src.services.lead_service import LeadService
from src.services.snov_service import SnovService
from src.utils.linkedin_search_utils import RecruiterCandidate
from tests.unit.test_helpers import FakeDomainResolver


class DummyResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


@pytest.fixture
def logger() -> logging.Logger:
    return logging.getLogger("test_lead_service")


def _job(company: str = "Acme Corp") -> JobRecord:
    return JobRecord(
        job_id="1",
        title="SDE",
        company=company,
        description="x",
        job_url="http://job",
        application_url="http://apply",
    )


def test_lead_service_uses_hunter_when_email_found(logger: logging.Logger) -> None:
    resolver = FakeDomainResolver()
    hunter = HunterService(api_key="x", max_searches_per_run=3, domain_resolver=resolver)
    snov = SnovService(
        client_id="id", client_secret="secret", max_searches_per_run=3, domain_resolver=resolver
    )

    hunter.find_recruiter_for_company = lambda company: RecruiterLead(  # type: ignore[method-assign]
        name="Jane", email="jane@acme.com", title="Recruiter"
    )
    snov.find_recruiter_for_company = lambda company: RecruiterLead(  # type: ignore[method-assign]
        name="Should Not Run", email="skip@acme.com"
    )

    lead = LeadService(hunter, snov, None, logger).find_recruiter_for_company("Acme")
    assert lead.email == "jane@acme.com"


def test_lead_service_google_then_hunter_email_finder(logger: logging.Logger) -> None:
    hunter = HunterService(api_key="x", max_searches_per_run=5, domain_resolver=FakeDomainResolver())
    google = GoogleSearchService("key", "cx", max_searches_per_run=3)

    google.find_recruiter_candidates = lambda company, max_results=5: [  # type: ignore[method-assign]
        RecruiterCandidate(
            name="Jane Doe",
            first_name="Jane",
            last_name="Doe",
            title="Technical Recruiter",
            linkedin_url="https://www.linkedin.com/in/jane-doe",
        )
    ]
    hunter.find_email_for_person = lambda company, first, last: RecruiterLead(  # type: ignore[method-assign]
        name="Jane Doe", email="jane@acme.com", title="Technical Recruiter"
    )
    hunter.find_recruiter_for_company = lambda company: RecruiterLead()  # type: ignore[method-assign]

    lead = LeadService(hunter, None, google, logger).find_recruiter_for_job(_job())
    assert lead.email == "jane@acme.com"


def test_lead_service_falls_back_to_snov_on_hunter_failure(
    monkeypatch: pytest.MonkeyPatch, logger: logging.Logger
) -> None:
    monkeypatch.setattr(
        "src.services.hunter_service.requests.get",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("hunter down")),
    )

    def fake_snov_post(url: str, data: dict | None = None, timeout: int = 30) -> DummyResponse:
        if url.endswith("access_token"):
            return DummyResponse({"access_token": "token"})
        return DummyResponse(
            {
                "data": [
                    {
                        "email": "recruiter@acme.com",
                        "firstName": "Sam",
                        "lastName": "Recruiter",
                        "position": "Talent Acquisition",
                    }
                ]
            }
        )

    monkeypatch.setattr("src.services.snov_service.requests.post", fake_snov_post)

    resolver = FakeDomainResolver()
    lead = LeadService(
        HunterService(api_key="x", max_searches_per_run=3, domain_resolver=resolver),
        SnovService(
            client_id="id", client_secret="secret", max_searches_per_run=3, domain_resolver=resolver
        ),
        None,
        logger,
    ).find_recruiter_for_company("Acme Corp")
    assert lead.email == "recruiter@acme.com"


def test_lead_service_falls_back_when_hunter_returns_empty(
    monkeypatch: pytest.MonkeyPatch, logger: logging.Logger
) -> None:
    monkeypatch.setattr(
        "src.services.hunter_service.requests.get",
        lambda *args, **kwargs: DummyResponse({"data": {"emails": []}}),
    )

    def fake_snov_post(url: str, data: dict | None = None, timeout: int = 30) -> DummyResponse:
        if url.endswith("access_token"):
            return DummyResponse({"access_token": "token"})
        return DummyResponse(
            {
                "data": [
                    {
                        "email": "hr@acme.com",
                        "firstName": "Pat",
                        "lastName": "HR",
                        "position": "HR Manager",
                    }
                ]
            }
        )

    monkeypatch.setattr("src.services.snov_service.requests.post", fake_snov_post)

    resolver = FakeDomainResolver()
    lead = LeadService(
        HunterService(api_key="x", max_searches_per_run=3, domain_resolver=resolver),
        SnovService(
            client_id="id", client_secret="secret", max_searches_per_run=3, domain_resolver=resolver
        ),
        None,
        logger,
    ).find_recruiter_for_company("Acme Corp")
    assert lead.email == "hr@acme.com"
