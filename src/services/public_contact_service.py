from __future__ import annotations

import re
from collections.abc import Callable
from urllib.parse import urljoin

from scrapling.fetchers import Fetcher

from src.models import RecruiterLead
from src.services.company_domain_service import CompanyDomainService
from src.utils.validators import Validators

_EMAIL_RE = re.compile(r"(?i)\b[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}\b")
_HR_KEYWORDS = (
    "recruit",
    "talent",
    "hiring",
    "career",
    "careers",
    "jobs",
    "hr",
    "people",
    "ta",
)
_LOW_VALUE_PREFIXES = (
    "noreply",
    "no-reply",
    "donotreply",
    "do-not-reply",
    "support",
    "help",
    "sales",
    "info",
    "privacy",
    "legal",
    "admin",
    "webmaster",
)
_PUBLIC_PATHS = (
    "",
    "/contact",
    "/contact-us",
    "/careers",
    "/career",
    "/jobs",
    "/join-us",
    "/about",
    "/team",
)


class PublicContactService:
    """Finds recruiter-style emails on public company pages before paid enrichment APIs."""

    def __init__(
        self,
        domain_resolver: CompanyDomainService | None = None,
        max_pages: int = 5,
        fetcher: Callable[..., object] | None = None,
    ) -> None:
        self._domain_resolver = domain_resolver or CompanyDomainService()
        self._max_pages = max(1, max_pages)
        self._fetcher = fetcher or Fetcher.get

    def find_recruiter_for_job(self, company_name: str, job_description: str = "") -> RecruiterLead:
        lead = self._lead_from_text(job_description, "job_description")
        if lead.email:
            return lead

        domain = self._domain_resolver.resolve_domain(company_name)
        if not domain:
            return RecruiterLead()

        return self.find_recruiter_for_domain(domain)

    def find_recruiter_for_domain(self, domain: str) -> RecruiterLead:
        base_url = f"https://{domain.strip().removeprefix('https://').removeprefix('http://').strip('/')}"
        candidates: list[str] = []

        for url in self._candidate_urls(base_url):
            try:
                page = self._fetcher(url, timeout=15)
            except Exception:  # noqa: BLE001
                continue
            candidates.extend(extract_public_emails(_page_text(page), domain))

        email = pick_best_public_email(candidates)
        if not email:
            return RecruiterLead()

        return RecruiterLead(email=email, title="Public contact", lead_source="public_contact")

    def _candidate_urls(self, base_url: str) -> list[str]:
        return [urljoin(base_url, path) for path in _PUBLIC_PATHS[: self._max_pages]]

    @staticmethod
    def _lead_from_text(text: str, source: str) -> RecruiterLead:
        email = pick_best_public_email(extract_public_emails(text))
        if not email:
            return RecruiterLead()
        return RecruiterLead(email=email, title="Public contact", lead_source=source)


def _page_text(page: object) -> str:
    text_attr = getattr(page, "text", "")
    if callable(text_attr):
        try:
            return str(text_attr())
        except TypeError:
            return ""
    return str(text_attr or page)


def extract_public_emails(text: str, expected_domain: str = "") -> list[str]:
    expected_domain = expected_domain.lower().strip()
    emails: list[str] = []
    seen: set[str] = set()

    for match in _EMAIL_RE.finditer(text or ""):
        email = match.group(0).lower().strip(".,;:)")
        if email in seen or not Validators.is_valid_recruiter_email(email):
            continue
        if expected_domain and email.split("@", 1)[1] != expected_domain:
            continue
        seen.add(email)
        emails.append(email)

    return emails


def pick_best_public_email(emails: list[str]) -> str:
    ranked = sorted(
        {email.lower() for email in emails if Validators.is_valid_recruiter_email(email)},
        key=_email_rank,
        reverse=True,
    )
    return ranked[0] if ranked else ""


def _email_rank(email: str) -> tuple[int, str]:
    local_part = email.split("@", 1)[0].lower()
    if any(keyword in local_part for keyword in _HR_KEYWORDS):
        return (100, email)
    if any(local_part == prefix or local_part.startswith(f"{prefix}.") for prefix in _LOW_VALUE_PREFIXES):
        return (10, email)
    if "." in local_part and not any(char.isdigit() for char in local_part):
        return (70, email)
    return (40, email)
