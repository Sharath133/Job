from __future__ import annotations

from src.services.public_contact_service import (
    PublicContactService,
    extract_public_emails,
    pick_best_public_email,
)
from tests.unit.test_helpers import FakeDomainResolver


class FakePage:
    def __init__(self, text: str) -> None:
        self.text = text


def test_extract_public_emails_filters_to_expected_domain() -> None:
    emails = extract_public_emails(
        "Contact careers@acme.com or support@other.com for help.",
        expected_domain="acme.com",
    )

    assert emails == ["careers@acme.com"]


def test_pick_best_public_email_prefers_recruiting_address() -> None:
    assert pick_best_public_email(["info@acme.com", "talent@acme.com", "jane.doe@acme.com"]) == "talent@acme.com"


def test_public_contact_service_extracts_from_job_description_before_fetching() -> None:
    service = PublicContactService(
        domain_resolver=FakeDomainResolver("acme.com"),
        fetcher=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("fetcher should not run")),
    )

    lead = service.find_recruiter_for_job("Acme", "Send your resume to hiring@acme.com")

    assert lead.email == "hiring@acme.com"
    assert lead.lead_source == "job_description"


def test_public_contact_service_fetches_public_pages() -> None:
    fetched_urls: list[str] = []

    def fake_fetcher(url: str, **kwargs) -> FakePage:
        fetched_urls.append(url)
        return FakePage("Reach our talent team at talent@acme.com")

    service = PublicContactService(
        domain_resolver=FakeDomainResolver("acme.com"),
        max_pages=2,
        fetcher=fake_fetcher,
    )

    lead = service.find_recruiter_for_job("Acme", "")

    assert fetched_urls == ["https://acme.com", "https://acme.com/contact"]
    assert lead.email == "talent@acme.com"
    assert lead.lead_source == "public_contact"
