from __future__ import annotations

from src.models import FollowupRow, JobRecord


_SKILL_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Python", ("python",)),
    ("FastAPI", ("fastapi", "fast api")),
    ("Django", ("django",)),
    ("Java", ("java", "spring boot", "springboot")),
    ("Spring Boot", ("spring boot", "springboot")),
    ("React", ("react", "react.js", "reactjs")),
    ("Node.js", ("node.js", "nodejs", "node js")),
    ("GCP", ("gcp", "google cloud")),
    ("AWS", ("aws", "amazon web services")),
    ("Docker", ("docker", "kubernetes", "k8s")),
    ("PostgreSQL", ("postgresql", "postgres", "sql")),
    ("MongoDB", ("mongodb", "mongo db")),
    ("Redis", ("redis",)),
    ("Elasticsearch", ("elasticsearch", "elastic search")),
    ("APIs", ("api", "apis", "rest", "microservices")),
)

_DEFAULT_SKILLS = ["Python", "FastAPI", "APIs"]


def subject_for_job(job: JobRecord) -> str:
    role = job.title or "Role"
    company = job.company_info.name or job.company or "Company"
    text = " ".join([job.title, job.company, job.description, *job.skills])
    return format_subject(role, company, _match_skills(text))


def subject_for_followup(followup: FollowupRow) -> str:
    role = followup.job_title or "Role"
    company = followup.company or "Company"
    return format_subject(role, company, _match_skills(followup.email_subject))


def format_subject(role: str, company: str, skills: list[str]) -> str:
    return f"{role} @ {company} | {', '.join(skills[:3])} | IIT Ropar"


def _match_skills(text: str) -> list[str]:
    normalized = text.lower()
    skills: list[str] = []
    for skill, aliases in _SKILL_RULES:
        if any(alias in normalized for alias in aliases):
            skills.append(skill)
        if len(skills) == 3:
            return skills
    return _DEFAULT_SKILLS
