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
        employee_count = raw_company.get("employee_count")
        return CompanyInfo(
            name=_as_str(raw_company.get("name")),
            linkedin_url=_as_str(raw_company.get("linkedin_url")),
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
        job_url=_as_str(item.get("url") or item.get("job_url") or apply_url),
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
        # dataset_items = self._client.dataset(run["defaultDatasetId"]).list_items().items
        dataset_items= [{
                "jobId": "4415197003",
                "jobUrl": "https://www.linkedin.com/jobs/view/4415197003/",
                "title": "Full Stack / DevOps Developer",
                "jobState": "LISTED",
                "isNew": True,
                "isApplicationLimitReached": False,
                "postedAt": "2026-05-16T12:41:35.000Z",
                "expiresAt": "2026-06-15T12:41:35.000Z",
                "description": {
                "html": "<p>We Are Hiring | Full-Stack Web Developer &amp; DevOps Engineer | R&amp;D</p><p>Vapi, Gujarat.</p><br><p>We are looking for a highly skilled Full-Stack Web Developer &amp; DevOps Engineer to design, develop, and scale the cloud platform powering our connected surgical ecosystem — from surgery licensing and QR-based workflow configuration to device fleet monitoring and long-term surgical record management.</p><br><p>This role combines:</p><p>Cloud Infrastructure</p><p>DevOps Automation</p><p>Full-Stack Engineering</p><p>Healthcare Cybersecurity</p><p>Medical SaaS Platforms</p><br><p>Key Technologies &amp; Skills:</p><p>React / Vue.js + TypeScript + Tailwind CSS</p><p>Node.js / Python Backend Frameworks</p><p>PostgreSQL + Redis</p><p>AWS / Azure / GCP</p><p>Docker + Kubernetes + GitHub Actions</p><p>JWT / OAuth2 / HTTPS / AES-256 Security</p><p>REST APIs &amp; Scalable SaaS Architectures</p><br><p>Preferred Background:</p><p>Full-Stack Development, Cloud Engineering, DevOps, Healthcare SaaS, Cybersecurity, or Medical Device Software Systems.</p><br><p>Strong Advantage:</p><p>Experience with healthcare platforms, HIPAA/GDPR compliance, QR systems, Android deployment workflows, connected device ecosystems, or regulated software environments.</p><br><p>This is not just another SaaS platform — it is infrastructure powering real-world surgical precision.</p><p>Interested candidates can share their profiles or connect directly parijat.patel@merai.co</p>",
                "text": "We Are Hiring | Full-Stack Web Developer & DevOps Engineer | R&DVapi, Gujarat.\nWe are looking for a highly skilled Full-Stack Web Developer & DevOps Engineer to design, develop, and scale the cloud platform powering our connected surgical ecosystem — from surgery licensing and QR-based workflow configuration to device fleet monitoring and long-term surgical record management.\nThis role combines:Cloud InfrastructureDevOps AutomationFull-Stack EngineeringHealthcare CybersecurityMedical SaaS Platforms\nKey Technologies & Skills:React / Vue.js + TypeScript + Tailwind CSSNode.js / Python Backend FrameworksPostgreSQL + RedisAWS / Azure / GCPDocker + Kubernetes + GitHub ActionsJWT / OAuth2 / HTTPS / AES-256 SecurityREST APIs & Scalable SaaS Architectures\nPreferred Background:Full-Stack Development, Cloud Engineering, DevOps, Healthcare SaaS, Cybersecurity, or Medical Device Software Systems.\nStrong Advantage:Experience with healthcare platforms, HIPAA/GDPR compliance, QR systems, Android deployment workflows, connected device ecosystems, or regulated software environments.\nThis is not just another SaaS platform — it is infrastructure powering real-world surgical precision.Interested candidates can share their profiles or connect directly parijat.patel@merai.co"
                },
                "location": {
                "text": "Vapi, Gujarat, India",
                "city": "Vapi",
                "state": "Gujarat",
                "country": "India",
                "countryCode": "in",
                "postalAddress": None
                },
                "workplaceType": "on_site",
                "isRemoteAllowed": False,
                "seniorityLevel": "Associate",
                "employmentType": "full_time",
                "jobFunctions": [
                "IT",
                "RSCH"
                ],
                "applyUrl": "https://www.linkedin.com/jobs/view/4415197003/",
                "isEasyApply": True,
                "applicantCount": 25,
                "applicantCountBucket": "first-25",
                "viewCount": 0,
                "applicantTrackingSystem": "LinkedIn",
                "salary": None,
                "company": {
                "id": "1331952",
                "universalName": "meril",
                "name": "Meril",
                "description": "Meril’s core objective is to design, manufacture and distribute clinically relevant, state-of-the-art and best-in-class medical devices to alleviate human suffering and improve quality of life.\n\nWe thus have a strong commitment towards R & D and adherence to best quality standards in Manufacturing, Scientific Communication and Distribution known today.\n\nOrigin\nEstablished in 2006, Meril was launched in line with the health-care diversification plan by a large format Indian multi-national company.\n\nDisclaimer: Information on Meril Digital / Social Media platform is not intended to be a substitute for professional medical advice, diagnosis or treatment. Meril does not recommend self-management of health issues.\nFor more information, visit: https://www.merillife.com/disclaimer",
                "linkedinUrl": "https://www.linkedin.com/company/meril",
                "jobSearchUrl": "https://www.linkedin.com/company/meril/jobs/",
                "logoUrl": "https://media.licdn.com/dms/image/v2/D4D0BAQHdsSopU_HYFw/company-logo_400_400/B4DZn2FzI9HsAY-/0/1760770343571/meril_logo?e=1780531200&v=beta&t=Sss4IF_by06ykd8BLlSwfhCj84Z1sTyvQCHQ0AXMW_w",
                "industry": "Medical Equipment Manufacturing",
                "industries": [
                    "Medical Equipment Manufacturing"
                ],
                "employeeCount": 6673,
                "employeeCountRange": {
                    "start": 10001,
                    "end": None
                },
                "headcount": "10001+",
                "followerCount": 380903,
                "headquarters": {
                    "city": "Vapi",
                    "state": "Gujarat",
                    "country": "IN",
                    "countryCode": "IN",
                    "line1": "Muktanand Marg,",
                    "line2": "Chala,",
                    "postalCode": "396191"
                },
                "specialities": [
                    "Vascular Interventions",
                    "Non-Vascular Interventions",
                    "Orthopaedics",
                    "Diagnostics",
                    "Endosurgery"
                ]
                }}]
        import json
        from pathlib import Path
        # ... after dataset_items = ...
        debug_path = Path("debug_apify_dataset.json")
        debug_path.write_text(
            json.dumps(dataset_items, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        jobs: list[JobRecord] = []
        for item in dataset_items[:max_jobs]:
            jobs.append(parse_job_item(item))
            
        return jobs
