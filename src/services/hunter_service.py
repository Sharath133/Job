from __future__ import annotations

import requests

from src.models import RecruiterLead
from src.services.company_domain_service import CompanyDomainService
from src.utils.recruiter_utils import pick_best_recruiter


class HunterService:
    """Hunter.io domain search and email finder with per-run cap."""

    _domain_search_url = "https://api.hunter.io/v2/domain-search"
    _email_finder_url = "https://api.hunter.io/v2/email-finder"

    def __init__(
        self,
        api_key: str,
        max_searches_per_run: int,
        domain_resolver: CompanyDomainService | None = None,
    ) -> None:
        self._api_key = api_key
        self._max_searches_per_run = max_searches_per_run
        self._domain_resolver = domain_resolver or CompanyDomainService()
        self._searches_used = 0

    def find_recruiter_for_company(self, company_name: str) -> RecruiterLead:
        domain = self._domain_resolver.resolve_domain(company_name)
        if not domain:
            return RecruiterLead()

        response = self._request(
            self._domain_search_url,
            {
                "domain": domain,
                "department": "hr",
            },
        )
        emails = (response.get("data") or {}).get("emails") or []
        return pick_best_recruiter(emails)

    def find_email_for_person(
        self,
        company_name: str,
        first_name: str,
        last_name: str,
    ) -> RecruiterLead:
        domain = self._domain_resolver.resolve_domain(company_name)
        if not domain or not first_name:
            return RecruiterLead()

        response = self._request(
            self._email_finder_url,
            {
                "domain": domain,
                "first_name": first_name,
                "last_name": last_name,
            },
        )
        data = response.get("data") or {}
        email = (data.get("email") or "").strip()
        if not email:
            return RecruiterLead()

        name = f"{data.get('first_name', first_name)} {data.get('last_name', last_name)}".strip()
        return RecruiterLead(
            name=name,
            email=email,
            title=(data.get("position") or "").strip(),
        )

    def _request(self, url: str, params: dict[str, str]) -> dict:
        if self._searches_used >= self._max_searches_per_run:
            raise RuntimeError("Hunter search limit reached for this run")
        self._searches_used += 1

        response = requests.get(
            url,
            params={**params, "api_key": self._api_key},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
