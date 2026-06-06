from __future__ import annotations

import math
from typing import Any

from jobspy import scrape_jobs

from src.models import CompanyInfo, JobRecord


def _is_empty(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, float):
        return math.isnan(value)
    return False


def _as_str(value: object) -> str:
    if _is_empty(value):
        return ""
    return str(value).strip()


def _job_id_from_row(row: dict[str, Any]) -> str:
    raw_id = _as_str(row.get("id"))
    if raw_id.startswith("li-"):
        return raw_id.removeprefix("li-")

    job_url = _as_str(row.get("job_url"))
    marker = "/jobs/view/"
    if marker in job_url:
        return job_url.split(marker, 1)[1].strip("/")

    return raw_id or job_url


def _site_names(raw_sites: str) -> list[str]:
    sites = [site.strip() for site in raw_sites.split(",") if site.strip()]
    return sites or ["linkedin"]


def _csv_values(raw_value: str, default: str) -> list[str]:
    values = [value.strip() for value in raw_value.split(",") if value.strip()]
    return values or [default]


def parse_jobspy_row(row: dict[str, Any]) -> JobRecord:
    job_url = _as_str(row.get("job_url_direct") or row.get("job_url"))
    company_url = _as_str(row.get("company_url_direct") or row.get("company_url"))
    industry = _as_str(row.get("company_industry"))
    company_size = _as_str(row.get("company_num_employees"))

    return JobRecord(
        job_id=_job_id_from_row(row),
        title=_as_str(row.get("title")),
        company=_as_str(row.get("company")),
        description=_as_str(row.get("description")),
        job_url=job_url,
        application_url=job_url,
        location=_as_str(row.get("location")),
        company_info=CompanyInfo(
            name=_as_str(row.get("company")),
            linkedin_url=company_url,
            industry=industry,
            employee_count=company_size,
            headquarters=_as_str(row.get("location")),
        ),
    )


class JobSpyClient:
    """Fetches jobs with the python-jobspy scraper library."""

    def __init__(
        self,
        sites: str,
        search_term: str,
        location: str,
        hours_old: int,
        fetch_description: bool,
    ) -> None:
        self._sites = _site_names(sites)
        self._search_terms = _csv_values(search_term, "python developer")
        self._locations = _csv_values(location, "India")
        self._hours_old = hours_old
        self._fetch_description = fetch_description

    def fetch_latest_jobs(self, max_jobs: int) -> list[JobRecord]:
        result_limit = max(1, max_jobs)
        jobs_by_key: dict[str, JobRecord] = {}

        for search_term in self._search_terms:
            for location in self._locations:
                remaining = result_limit - len(jobs_by_key)
                if remaining <= 0:
                    return list(jobs_by_key.values())

                rows = scrape_jobs(
                    site_name=self._sites,
                    search_term=search_term,
                    google_search_term=f"{search_term} jobs near {location} since yesterday",
                    location=location,
                    results_wanted=remaining,
                    hours_old=self._hours_old,
                    country_indeed="India",
                    linkedin_fetch_description=self._fetch_description,
                    verbose=0,
                )
                for row in rows.to_dict(orient="records"):
                    job = parse_jobspy_row(row)
                    key = (job.job_url or job.job_id).strip()
                    if key and key not in jobs_by_key:
                        jobs_by_key[key] = job
                    if len(jobs_by_key) >= result_limit:
                        return list(jobs_by_key.values())

        return list(jobs_by_key.values())
