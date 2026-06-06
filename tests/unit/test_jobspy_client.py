from __future__ import annotations

import pandas as pd

from src.services.jobspy_client import JobSpyClient, parse_jobspy_row


def test_parse_jobspy_row_normalizes_linkedin_job() -> None:
    job = parse_jobspy_row(
        {
            "id": "li-4424905360",
            "title": "Python Developer",
            "company": "Tata Consultancy Services",
            "location": "Hyderabad, Telangana, India",
            "job_url": "https://www.linkedin.com/jobs/view/4424905360",
            "job_url_direct": None,
            "description": "Python, pandas, cloud experience",
            "company_url": "https://www.linkedin.com/company/tata-consultancy-services",
            "company_industry": "IT Services and IT Consulting",
            "company_num_employees": "10001+",
        }
    )

    assert job.job_id == "4424905360"
    assert job.title == "Python Developer"
    assert job.company == "Tata Consultancy Services"
    assert job.description == "Python, pandas, cloud experience"
    assert job.job_url == "https://www.linkedin.com/jobs/view/4424905360"
    assert job.company_info.linkedin_url.endswith("tata-consultancy-services")
    assert job.company_info.headquarters == "Hyderabad, Telangana, India"


def test_jobspy_client_supports_multiple_terms_and_locations(monkeypatch) -> None:
    calls: list[tuple[str, str, int]] = []

    def fake_scrape_jobs(**kwargs):
        calls.append((kwargs["search_term"], kwargs["location"], kwargs["results_wanted"]))
        job_id = f"{len(calls)}"
        return pd.DataFrame(
            [
                {
                    "id": f"li-{job_id}",
                    "title": kwargs["search_term"],
                    "company": "Acme",
                    "location": kwargs["location"],
                    "job_url": f"https://www.linkedin.com/jobs/view/{job_id}",
                    "description": "Build systems",
                }
            ]
        )

    monkeypatch.setattr("src.services.jobspy_client.scrape_jobs", fake_scrape_jobs)

    jobs = JobSpyClient(
        sites="linkedin",
        search_term="software engineer,backend engineer",
        location="India,Bangalore",
        hours_old=24,
        fetch_description=True,
    ).fetch_latest_jobs(3)

    assert [job.job_id for job in jobs] == ["1", "2", "3"]
    assert calls == [
        ("software engineer", "India", 3),
        ("software engineer", "Bangalore", 2),
        ("backend engineer", "India", 1),
    ]
