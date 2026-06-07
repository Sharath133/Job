from __future__ import annotations

import time

import requests

from src.models import RecruiterLead
from src.services.company_domain_service import CompanyDomainService
from src.utils.recruiter_utils import pick_best_recruiter


class SnovService:
    """Snov.io domain email search with OAuth and per-run credit cap."""

    _token_url = "https://api.snov.io/v1/oauth/access_token"
    _domain_start_url = "https://api.snov.io/v2/domain-search/domain-emails/start"
    _domain_result_url = "https://api.snov.io/v2/domain-search/domain-emails/result"

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

        payload = self._domain_emails_search(domain)
        return pick_best_recruiter(self._extract_entries(payload))

    def _domain_emails_search(self, domain: str) -> dict:
        headers = {"authorization": f"Bearer {self._get_access_token()}"}
        response = requests.post(
            self._domain_start_url,
            params={"domain": domain},
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()
        start_payload = response.json()
        entries = self._extract_entries(start_payload)
        if entries:
            return start_payload

        result_url = str(start_payload.get("result") or "").strip()
        task_hash = str(start_payload.get("task_hash") or "").strip()
        if not result_url and task_hash:
            result_url = f"{self._domain_result_url}/{task_hash}"
        if not result_url:
            return start_payload

        for attempt in range(3):
            result_response = requests.get(result_url, headers=headers, timeout=30)
            result_response.raise_for_status()
            result_payload = result_response.json()
            status = str(result_payload.get("status", "")).lower()
            if status != "in_progress":
                return result_payload
            if attempt < 2:
                time.sleep(2)
        return result_payload

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
            for key in ("emails", "result", "items", "contacts"):
                nested = data.get(key)
                if isinstance(nested, list):
                    return nested
        emails = payload.get("emails")
        if isinstance(emails, list):
            return emails
        return []
