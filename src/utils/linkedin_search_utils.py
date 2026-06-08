from __future__ import annotations

import re
from dataclasses import dataclass

from src.utils.name_utils import split_full_name

_RECRUITER_KEYWORDS = (
    "recruit",
    "talent",
    "hr",
    "human resources",
    "hiring",
    "hiring manager",
    "engineering manager",
    "software engineering manager",
    "technical recruiter",
    "people operations",
    "talent acquisition",
)

_LINKEDIN_PROFILE_RE = re.compile(r"linkedin\.com/in/([^/?#]+)", re.IGNORECASE)


@dataclass(slots=True)
class RecruiterCandidate:
    name: str
    first_name: str
    last_name: str
    title: str = ""
    linkedin_url: str = ""
    source: str = "google"


def build_recruiter_search_query(company_name: str) -> str:
    roles = (
        '"Talent Acquisition"',
        "Recruiter",
        '"Technical Recruiter"',
        '"Hiring Manager"',
        '"Engineering Manager"',
        '"Software Engineering Manager"',
    )
    return f'site:linkedin.com/in ({" OR ".join(roles)}) "{company_name}" India'


def _looks_like_recruiter_role(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in _RECRUITER_KEYWORDS)


def _extract_name_from_title(title: str) -> str:
    cleaned = title.strip()
    for separator in (" | LinkedIn", " - LinkedIn", " | "):
        if separator in cleaned:
            cleaned = cleaned.split(separator, 1)[0]
    if " - " in cleaned:
        cleaned = cleaned.split(" - ", 1)[0]
    return cleaned.strip()


def _extract_title_from_result(title: str, snippet: str) -> str:
    if " - " in title:
        parts = title.split(" - ")
        if len(parts) > 1:
            role = parts[1].split(" | ")[0].strip()
            if role and _looks_like_recruiter_role(role):
                return role
    for line in (snippet, title):
        if _looks_like_recruiter_role(line):
            return line.strip()[:120]
    return ""


def parse_recruiter_candidate(title: str, snippet: str, link: str) -> RecruiterCandidate | None:
    combined = f"{title} {snippet}"
    if not _looks_like_recruiter_role(combined):
        return None

    match = _LINKEDIN_PROFILE_RE.search(link)
    if not match:
        return None

    full_name = _extract_name_from_title(title)
    if not full_name or full_name.lower() in {"linkedin", "profile"}:
        return None

    first_name, last_name = split_full_name(full_name)
    if not first_name:
        return None

    return RecruiterCandidate(
        name=full_name,
        first_name=first_name,
        last_name=last_name,
        title=_extract_title_from_result(title, snippet),
        linkedin_url=link.strip(),
        source="google",
    )
