from __future__ import annotations

import requests

from src.models import RecruiterLead
from src.utils.linkedin_search_utils import RecruiterCandidate


class ContactOutService:
    """ContactOut LinkedIn profile contact lookup with a per-run cap."""

    _profile_url = "https://api.contactout.com/v1/people/linkedin"

    def __init__(self, api_token: str, max_searches_per_run: int) -> None:
        self._api_token = api_token
        self._max_searches_per_run = max_searches_per_run
        self._searches_used = 0

    def find_email_for_candidate(self, candidate: RecruiterCandidate) -> RecruiterLead:
        if self._searches_used >= self._max_searches_per_run:
            raise RuntimeError("ContactOut search limit reached for this run")
        self._searches_used += 1

        if not candidate.linkedin_url:
            return RecruiterLead()

        response = requests.get(
            self._profile_url,
            params={
                "profile": candidate.linkedin_url,
                "email_type": "work",
                "include_phone": "false",
            },
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "token": self._api_token,
            },
            timeout=30,
        )
        response.raise_for_status()

        email = self._extract_email(response.json())
        if not email:
            return RecruiterLead()

        return RecruiterLead(
            name=candidate.name,
            email=email,
            title=candidate.title,
            contactout_email=email,
            lead_source="contactout",
        )

    @staticmethod
    def _extract_email(payload: dict) -> str:
        profile = payload.get("profile") or {}
        for key in ("work_email", "email", "personal_email"):
            value = profile.get(key)
            if isinstance(value, list) and value:
                return str(value[0] or "").strip()
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""
