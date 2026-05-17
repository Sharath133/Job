from __future__ import annotations

from src.models import RecruiterLead

_RECRUITER_TITLE_KEYWORDS = (
    "recruit",
    "talent",
    "hr",
    "human resources",
    "hiring",
    "people",
    "engineering manager",
    "talent acquisition",
)


def rank_recruiter_entry(position: str = "", department: str = "") -> int:
    position_lower = position.lower()
    if any(keyword in position_lower for keyword in _RECRUITER_TITLE_KEYWORDS):
        return 2
    dept = department.lower().replace("_", " ")
    if dept in {"hr", "human resources"}:
        return 1
    return 0


def pick_best_recruiter(entries: list[dict]) -> RecruiterLead:
    ranked = sorted(
        entries,
        key=lambda entry: rank_recruiter_entry(
            str(
                entry.get("position")
                or entry.get("title")
                or entry.get("jobTitle")
                or ""
            ),
            str(entry.get("department") or ""),
        ),
        reverse=True,
    )
    for entry in ranked:
        email = (
            entry.get("value") or entry.get("email") or entry.get("emailAddress") or ""
        ).strip()
        if not email:
            continue
        first = (entry.get("first_name") or entry.get("firstName") or "").strip()
        last = (entry.get("last_name") or entry.get("lastName") or "").strip()
        title = (
            entry.get("position") or entry.get("title") or entry.get("jobTitle") or ""
        ).strip()
        return RecruiterLead(name=f"{first} {last}".strip(), email=email, title=title)
    return RecruiterLead()
