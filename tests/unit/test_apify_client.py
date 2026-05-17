from src.services.apify_client import parse_job_item


def test_parse_job_item_extracts_nested_company_and_location() -> None:
    job = parse_job_item(
        {
            "job_id": "4415848618",
            "title": "Java Software Engineer",
            "company": {
                "name": "Tata Consultancy Services",
                "linkedin_url": "https://www.linkedin.com/company/tata-consultancy-services",
                "industry": "IT Services and IT Consulting",
                "employee_count": 709155,
                "headquarters": {
                    "city": "Mumbai",
                    "state": "Maharashtra",
                    "country": "India",
                },
            },
            "location": {
                "city": "Bengaluru",
                "state": "Karnataka",
                "country": "India",
            },
            "apply_url": "https://www.linkedin.com/jobs/view/4415848618/",
            "skills": ["Java", "Spring Boot"],
            "description": "TCS is hiring Java Developers.",
        }
    )

    assert job.job_id == "4415848618"
    assert job.company == "Tata Consultancy Services"
    assert job.company_info.linkedin_url.endswith("tata-consultancy-services")
    assert job.company_info.industry == "IT Services and IT Consulting"
    assert job.company_info.headquarters == "Mumbai, Maharashtra, India"
    assert job.location == "Bengaluru, Karnataka, India"
    assert job.skills == ["Java", "Spring Boot"]
