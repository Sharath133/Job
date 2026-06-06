from __future__ import annotations

from typing import Any

from apify_client import ApifyClient

from src.models import CompanyInfo, JobRecord


def _as_str(value: object) -> str:
    """Normalize Apify dataset values: strings, nested dicts (description/location), or lists."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in (
            "text",
            "plainText",
            "html",
            "name",
            "label",
            "defaultLocalizedName",
            "fullName",
            "title",
            "url",
            "applyUrl",
            "applicationUrl",
            "linkedin_url",
        ):
            nested = value.get(key)
            if nested is None or nested == "":
                continue
            if isinstance(nested, (str, int, float)):
                s = str(nested).strip()
                if s:
                    return s
            if isinstance(nested, dict):
                inner = _as_str(nested)
                if inner:
                    return inner
        parts: list[str] = []
        for key in ("city", "state", "country", "name"):
            part = value.get(key)
            if part and isinstance(part, str):
                parts.append(part.strip())
        if parts:
            return ", ".join(parts)
        return ""
    if isinstance(value, list):
        joined = ", ".join(_as_str(x) for x in value if x is not None)
        return joined.strip()
    return str(value).strip()


def _format_headquarters(headquarters: object) -> str:
    if not isinstance(headquarters, dict):
        return ""
    parts = [
        str(headquarters.get("city") or "").strip(),
        str(headquarters.get("state") or "").strip(),
        str(headquarters.get("country") or "").strip(),
    ]
    return ", ".join(part for part in parts if part)


def parse_company(raw_company: object) -> CompanyInfo:
    if isinstance(raw_company, dict):
        employee_count = raw_company.get("employee_count") or raw_company.get("employeeCount")
        return CompanyInfo(
            name=_as_str(raw_company.get("name")),
            linkedin_url=_as_str(raw_company.get("linkedin_url") or raw_company.get("linkedinUrl")),
            industry=_as_str(raw_company.get("industry")),
            employee_count=str(employee_count).strip() if employee_count is not None else "",
            headquarters=_format_headquarters(raw_company.get("headquarters")),
        )
    return CompanyInfo(name=_as_str(raw_company))


def parse_skills(raw_skills: object) -> list[str]:
    if not isinstance(raw_skills, list):
        return []
    return [str(skill).strip() for skill in raw_skills if str(skill).strip()]


def parse_job_item(item: dict[str, Any]) -> JobRecord:
    company_info = parse_company(item.get("company") or item.get("companyName"))
    company_name = company_info.name or _as_str(item.get("companyName"))
    apply_url = _as_str(item.get("apply_url") or item.get("applyUrl") or item.get("applicationUrl"))
    job_id = str(item.get("job_id") or item.get("id") or item.get("jobId") or apply_url or "")

    return JobRecord(
        job_id=job_id,
        title=_as_str(item.get("title")),
        company=company_name,
        description=_as_str(item.get("description")),
        job_url=_as_str(item.get("url") or item.get("job_url") or item.get("jobUrl") or apply_url),
        application_url=apply_url,
        location=_as_str(item.get("location")),
        company_info=company_info,
        skills=parse_skills(item.get("skills")),
    )


class ApifyJobClient:
    """Ingests jobs from an Apify actor dataset."""

    def __init__(self, token: str, actor_id: str) -> None:
        self._client = ApifyClient(token)
        self._actor_id = actor_id

    def fetch_latest_jobs(self, max_jobs: int) -> list[JobRecord]:
        run_input = {
            "datePosted": "past_24h",
            "easyApplyOnly": True,
            "jobTypes": ["full_time"],
            "locations": [
                "India",
                "Bangalore, Karnataka, India",
                "Hyderabad, Telangana, India",
                "Pune, Maharashtra, India",
            ],
            "maxResults": 30,
            "mode": "search",
            "searchKeywords": (
                "Software Developer OR Backend Developer OR Full Stack "
                "Developer OR Software Engineer OR Python Developer "
            ),
            "seniorityLevels": ["associate"],
            "sortBy": "relevance",
            "under10Applicants": False,
            "workplaceTypes": [],
            "companyIds": [],
            "jobUrls": [],
        }

        run = self._client.actor(self._actor_id).call(run_input=run_input)
        dataset_id = run.get("defaultDatasetId")
        if not dataset_id:
            return []

        dataset_items = self._client.dataset(dataset_id).list_items(limit=max_jobs).items
        return [parse_job_item(item) for item in dataset_items]
