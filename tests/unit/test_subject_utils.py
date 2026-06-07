from __future__ import annotations

from src.models import JobRecord
from src.utils.subject_utils import subject_for_job


def test_subject_for_job_uses_matching_python_skills() -> None:
    subject = subject_for_job(
        JobRecord(
            job_id="1",
            title="Backend Engineer",
            company="Acme",
            description="Build services with Python, FastAPI, Django, and PostgreSQL.",
            job_url="",
            application_url="",
        )
    )

    assert subject == "Backend Engineer @ Acme | Python, FastAPI, Django | IIT Ropar"


def test_subject_for_job_changes_skills_for_java_jd() -> None:
    subject = subject_for_job(
        JobRecord(
            job_id="2",
            title="Software Engineer",
            company="Target",
            description="Work on Java, Spring Boot, REST APIs, Docker, and AWS systems.",
            job_url="",
            application_url="",
        )
    )

    assert subject == "Software Engineer @ Target | Java, Spring Boot, AWS | IIT Ropar"
