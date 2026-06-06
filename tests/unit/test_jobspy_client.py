from __future__ import annotations

from src.services.jobspy_client import parse_jobspy_row


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
