from __future__ import annotations

import re

import requests

from src.utils.domain_utils import guess_domain_from_company

_CLEARBIT_SUGGEST_URL = "https://autocomplete.clearbit.com/v1/companies/suggest"


def _normalize_company_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def pick_best_clearbit_domain(company_name: str, suggestions: list[dict]) -> str:
    """Pick the best-matching domain from Clearbit suggest results."""
    if not suggestions:
        return ""

    target = _normalize_company_name(company_name)
    best_domain = ""
    best_score = -1

    for item in suggestions:
        name = str(item.get("name") or "")
        domain = str(item.get("domain") or "").strip().lower()
        if not domain:
            continue

        normalized_name = _normalize_company_name(name)
        score = 0
        if normalized_name == target:
            score = 100
        elif target and (target in normalized_name or normalized_name in target):
            score = 60 + min(len(target), len(normalized_name))
        elif company_name.lower() in name.lower() or name.lower() in company_name.lower():
            score = 40

        if score > best_score:
            best_score = score
            best_domain = domain

    if best_domain:
        return best_domain

    first_domain = str(suggestions[0].get("domain") or "").strip().lower()
    return first_domain


class CompanyDomainService:
    """Resolves company name to email domain via Clearbit suggest API."""

    def __init__(self, suggest_url: str = _CLEARBIT_SUGGEST_URL) -> None:
        self._suggest_url = suggest_url
        self._cache: dict[str, str] = {}

    def resolve_domain(self, company_name: str) -> str:
        cleaned = company_name.strip()
        if not cleaned:
            return ""

        cache_key = cleaned.lower()
        if cache_key in self._cache:
            return self._cache[cache_key]

        domain = self._resolve_uncached(cleaned)
        self._cache[cache_key] = domain
        return domain

    def _resolve_uncached(self, company_name: str) -> str:
        lowered = company_name.lower()
        if lowered.startswith("www."):
            lowered = lowered[4:]
        if " " not in company_name and "." in company_name:
            return lowered

        clearbit_domain = self._fetch_clearbit_domain(company_name)
        if clearbit_domain:
            return clearbit_domain

        return guess_domain_from_company(company_name)

    def _fetch_clearbit_domain(self, company_name: str) -> str:
        try:
            response = requests.get(
                self._suggest_url,
                params={"query": company_name},
                timeout=15,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError, ConnectionError):
            return ""

        if not isinstance(payload, list):
            return ""

        return pick_best_clearbit_domain(company_name, payload)
