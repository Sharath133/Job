from __future__ import annotations

import re

_COMPANY_SUFFIXES = re.compile(
    r"\b(inc|incorporated|llc|ltd|limited|corp|corporation|co|company|group|"
    r"technologies|technology|tech|solutions|software|systems|international|"
    r"global|pvt|private)\b\.?",
    re.IGNORECASE,
)


def guess_domain_from_company(company: str) -> str:
    """Best-effort domain from company name when no website is available."""
    name = company.strip()
    if not name:
        return ""

    lowered = name.lower()
    if lowered.startswith("www."):
        lowered = lowered[4:]
    if " " not in name and "." in name:
        return lowered

    cleaned = _COMPANY_SUFFIXES.sub("", name)
    slug = re.sub(r"[^a-z0-9]+", "", cleaned.lower())
    return f"{slug}.com" if slug else ""
