from __future__ import annotations

import requests

from src.utils.linkedin_search_utils import (
    RecruiterCandidate,
    build_recruiter_search_query,
    parse_recruiter_candidate,
)


class GoogleSearchService:
    """Finds LinkedIn recruiter profiles via Google Custom Search JSON API."""

    _url = "https://www.googleapis.com/customsearch/v1"

    def __init__(self, api_key: str, search_engine_id: str, max_searches_per_run: int) -> None:
        self._api_key = api_key
        self._search_engine_id = search_engine_id
        self._max_searches_per_run = max_searches_per_run
        self._searches_used = 0

    def find_recruiter_candidates(self, company_name: str, max_results: int = 5) -> list[RecruiterCandidate]:
        if self._searches_used >= self._max_searches_per_run:
            raise RuntimeError("Google search limit reached for this run")
        self._searches_used += 1

        response = requests.get(
            self._url,
            params={
                "key": self._api_key,
                "cx": self._search_engine_id,
                "q": build_recruiter_search_query(company_name),
                "num": min(max_results, 10),
            },
            timeout=30,
        )
        breakpoint()
        print(response.json())
        response.raise_for_status()
        return self._parse_candidates(response.json(), max_results)

    @staticmethod
    def _parse_candidates(payload: dict, max_results: int) -> list[RecruiterCandidate]:
        candidates: list[RecruiterCandidate] = []
        seen_names: set[str] = set()

        for item in payload.get("items") or []:
            candidate = parse_recruiter_candidate(
                title=str(item.get("title") or ""),
                snippet=str(item.get("snippet") or ""),
                link=str(item.get("link") or ""),
            )
            if not candidate:
                continue
            key = candidate.name.lower()
            if key in seen_names:
                continue
            seen_names.add(key)
            candidates.append(candidate)
            if len(candidates) >= max_results:
                break

        return candidates
