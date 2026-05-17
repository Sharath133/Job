from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class JobState(str, Enum):
    INGESTED = "INGESTED"
    DEDUPED = "DEDUPED"
    SCORED = "SCORED"
    LEAD_SOURCED = "LEAD_SOURCED"
    DRAFTED = "DRAFTED"
    EXECUTED = "EXECUTED"
    FINALIZED = "FINALIZED"


@dataclass(slots=True)
class CompanyInfo:
    name: str = ""
    linkedin_url: str = ""
    industry: str = ""
    employee_count: str = ""
    headquarters: str = ""


@dataclass(slots=True)
class JobRecord:
    job_id: str
    title: str
    company: str
    description: str
    job_url: str
    application_url: str
    location: str = ""
    company_info: CompanyInfo = field(default_factory=CompanyInfo)
    skills: list[str] = field(default_factory=list)


@dataclass(slots=True)
class RecruiterLead:
    name: str = ""
    email: str = ""
    title: str = ""
    hunter_email: str = ""
    lead_source: str = ""


@dataclass(slots=True)
class EmailDraft:
    subject: str
    body: str
    is_valid: bool
    validation_error: str = ""


@dataclass(slots=True)
class ExecutionOutcome:
    email_status: str = "not_attempted"
    portal_status: str = "not_attempted"
    portal_type: str = "unknown"
    failure_reason: str = ""
    screenshot_path: str = ""


@dataclass(slots=True)
class JobExecutionContext:
    job: JobRecord
    state: JobState = JobState.INGESTED
    score: int = 0
    score_reason: str = ""
    recruiter: RecruiterLead = field(default_factory=RecruiterLead)
    email_draft: EmailDraft | None = None
    outcome: ExecutionOutcome = field(default_factory=ExecutionOutcome)
    run_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_sheet_row(self) -> list[str]:
        email_subject = self.email_draft.subject if self.email_draft else ""
        return [
            self.timestamp,
            self.job.job_id,
            self.job.title,
            self.job.company,
            self.job.company_info.linkedin_url,
            self.job.company_info.industry,
            self.job.company_info.headquarters,
            self.job.job_url,
            self.job.application_url,
            str(self.score),
            self.score_reason,
            self.recruiter.name,
            self.recruiter.title,
            self.recruiter.email,
            self.recruiter.hunter_email,
            self.recruiter.lead_source,
            email_subject,
            self.outcome.email_status,
            self.outcome.portal_status,
            self.outcome.portal_type,
            self.state.value,
            self.outcome.failure_reason,
            self.outcome.screenshot_path,
            self.run_id,
        ]
