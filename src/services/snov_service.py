from __future__ import annotations

import requests

from src.models import RecruiterLead
from src.services.company_domain_service import CompanyDomainService
from src.utils.recruiter_utils import pick_best_recruiter


class SnovService:
    """Snov.io domain email search with OAuth and per-run credit cap."""

    _token_url = "https://api.snov.io/v1/oauth/access_token"
    _domain_url = "https://api.snov.io/v1/get-domain-emails-with-info"

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        max_searches_per_run: int,
        domain_resolver: CompanyDomainService | None = None,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._max_searches_per_run = max_searches_per_run
        self._domain_resolver = domain_resolver or CompanyDomainService()
        self._searches_used = 0
        self._access_token = ""

    def find_recruiter_for_company(self, company_name: str) -> RecruiterLead:
        if self._searches_used >= self._max_searches_per_run:
            raise RuntimeError("Snov search limit reached for this run")
        self._searches_used += 1

        domain = self._domain_resolver.resolve_domain(company_name)
        if not domain:
            return RecruiterLead()

        response = requests.post(
            self._domain_url,
            data={
                "access_token": self._get_access_token(),
                "domain": domain,
                "type": "personal",
            },
            timeout=30,
        )
        response.raise_for_status()
        return pick_best_recruiter(self._extract_entries(response.json()))

    def _get_access_token(self) -> str:
        if self._access_token:
            return self._access_token

        response = requests.post(
            self._token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
            },
            timeout=30,
        )
        response.raise_for_status()
        token = (response.json().get("access_token") or "").strip()
        if not token:
            raise RuntimeError("Snov OAuth returned no access token")
        self._access_token = token
        return token

    @staticmethod
    def _extract_entries(payload: dict) -> list[dict]:
        if payload.get("success") is False:
            raise RuntimeError(payload.get("message") or "Snov domain search failed")

        data = payload.get("data")
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ("emails", "result", "items"):
                nested = data.get(key)
                if isinstance(nested, list):
                    return nested
        emails = payload.get("emails")
        if isinstance(emails, list):
            return emails
        return []
