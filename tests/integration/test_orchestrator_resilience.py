from src.models import EmailDraft, ExecutionOutcome, JobExecutionContext, JobRecord, RecruiterLead
from src.main import JobAgentOrchestrator
from src.services.groq_service import GroqRateLimitError


class FakeEmail:
    def can_send(self, already_sent_today: int) -> bool:
        return True

    def send_email(self, recipient_email: str, draft: EmailDraft, attachment_path: str | None = None) -> None:
        raise RuntimeError("smtp down")


class FakePlaywright:
    def classify_portal(self, url: str) -> str:
        return "lever"

    def apply(self, application_url: str, job_id: str, full_name: str, email: str, phone: str) -> tuple[str, str]:
        raise RuntimeError("browser crash")


def test_execution_outcome_collects_independent_failures() -> None:
    context = JobExecutionContext(
        job=JobRecord(
            job_id="1",
            title="SDE",
            company="Acme",
            description="x",
            job_url="http://job",
            application_url="http://apply",
        ),
        outcome=ExecutionOutcome(),
    )
    context.email_draft = EmailDraft(subject="s", body="b", is_valid=True)
    context.recruiter.email = "x@example.com"

    email_service = FakeEmail()
    playwright = FakePlaywright()

    try:
        email_service.send_email(context.recruiter.email, context.email_draft)
    except Exception as exc:  # noqa: BLE001
        context.outcome.email_status = "failed"
        context.outcome.failure_reason = f"SMTP failure: {exc}"

    try:
        playwright.apply(context.job.application_url, context.job.job_id, "n", "e", "p")
    except Exception as exc:  # noqa: BLE001
        context.outcome.portal_status = "failed"
        context.outcome.failure_reason += f" | Playwright failure: {exc}"

    assert context.outcome.email_status == "failed"
    assert context.outcome.portal_status == "failed"
    assert "SMTP failure" in context.outcome.failure_reason
    assert "Playwright failure" in context.outcome.failure_reason


class FailingSource:
    def fetch_latest_jobs(self, max_jobs: int) -> list[JobRecord]:
        raise RuntimeError("source down")


class WorkingSource:
    def fetch_latest_jobs(self, max_jobs: int) -> list[JobRecord]:
        return [
            JobRecord(
                job_id="job-1",
                title="Python Developer",
                company="Acme",
                description="Build Python services",
                job_url="https://example.com/job-1",
                application_url="https://example.com/job-1",
            )
        ]


class FakeSheets:
    def __init__(self) -> None:
        self.rows: list[JobExecutionContext] = []

    def append_result(self, context: JobExecutionContext) -> None:
        self.rows.append(context)


class FakeLogger:
    def info(self, *args, **kwargs) -> None:
        pass

    def exception(self, *args, **kwargs) -> None:
        pass


def test_fetch_jobs_continues_when_one_source_fails() -> None:
    orchestrator = JobAgentOrchestrator.__new__(JobAgentOrchestrator)
    orchestrator._run_id = "run-id"
    orchestrator._logger = FakeLogger()
    orchestrator._sheets = FakeSheets()
    orchestrator._apify = FailingSource()
    orchestrator._jobspy = WorkingSource()

    jobs = orchestrator._fetch_jobs_from_sources()

    assert [job.job_id for job in jobs] == ["job-1"]
    assert orchestrator._sheets.rows[0].job.job_id == "APIFY_FETCH_FAILED_run-id"


class FakeJobSource:
    def fetch_latest_jobs(self, max_jobs: int) -> list[JobRecord]:
        return [
            JobRecord(
                job_id=f"job-{idx}",
                title="Python Developer",
                company="Acme",
                description="Build Python services",
                job_url=f"https://example.com/job-{idx}",
                application_url=f"https://example.com/job-{idx}",
            )
            for idx in range(3)
        ]


class RateLimitedGroq:
    def __init__(self) -> None:
        self.score_calls = 0

    def score_job(self, job: JobRecord, resume_summary: str) -> int:
        self.score_calls += 1
        raise GroqRateLimitError("Groq rate limit reached", retry_after_seconds=12.0)


class NoopLead:
    pass


class NoopSheets(FakeSheets):
    def get_existing_job_ids(self) -> set[str]:
        return set()

    def count_emails_sent_today(self) -> int:
        return 0

    def get_recent_sent_recipients(self) -> set[str]:
        return set()


def test_run_stops_groq_calls_after_rate_limit() -> None:
    orchestrator = JobAgentOrchestrator.__new__(JobAgentOrchestrator)
    orchestrator._run_id = "run-id"
    orchestrator._logger = FakeLogger()
    orchestrator._sheets = NoopSheets()
    orchestrator._apify = FakeJobSource()
    orchestrator._jobspy = None
    orchestrator._groq = RateLimitedGroq()
    orchestrator._lead = NoopLead()
    orchestrator._email = object()
    orchestrator._playwright = object()

    orchestrator.run()

    assert orchestrator._groq.score_calls == 1
    assert len(orchestrator._sheets.rows) == 3
    assert "Groq rate limited" in orchestrator._sheets.rows[0].outcome.failure_reason
    assert "Skipped because Groq rate limit" in orchestrator._sheets.rows[1].outcome.failure_reason
    assert "Skipped because Groq rate limit" in orchestrator._sheets.rows[2].outcome.failure_reason


class DuplicateRecruiterJobSource:
    def fetch_latest_jobs(self, max_jobs: int) -> list[JobRecord]:
        return [
            JobRecord(
                job_id="job-1",
                title="Backend Engineer",
                company="Acme",
                description="Build Python services",
                job_url="https://example.com/job-1",
                application_url="",
            ),
            JobRecord(
                job_id="job-2",
                title="Backend Engineer II",
                company="Acme",
                description="Build Python services",
                job_url="https://example.com/job-2",
                application_url="",
            ),
        ]


class SuccessfulGroq:
    def score_job(self, job: JobRecord, resume_summary: str) -> int:
        return 100

    def generate_email_draft(self, job: JobRecord, resume_summary: str, recruiter_name: str) -> EmailDraft:
        return EmailDraft(subject=f"Interested in {job.title}", body="Hello", is_valid=True)


class SameRecruiterLead:
    def find_recruiter_for_job(self, job: JobRecord) -> RecruiterLead:
        return RecruiterLead(name="Recruiter", email="Recruiter@Example.com", title="Recruiter")


class RecordingEmail:
    def __init__(self) -> None:
        self.recipients: list[str] = []

    def can_send(self, already_sent_today: int) -> bool:
        return True

    def send_email(self, recipient_email: str, draft: EmailDraft, attachment_path: str | None = None) -> None:
        self.recipients.append(recipient_email)


class NoopPlaywright:
    pass


def test_run_skips_duplicate_recruiter_email_in_same_run() -> None:
    orchestrator = JobAgentOrchestrator.__new__(JobAgentOrchestrator)
    orchestrator._run_id = "run-id"
    orchestrator._logger = FakeLogger()
    orchestrator._sheets = NoopSheets()
    orchestrator._apify = DuplicateRecruiterJobSource()
    orchestrator._jobspy = None
    orchestrator._groq = SuccessfulGroq()
    orchestrator._lead = SameRecruiterLead()
    orchestrator._email = RecordingEmail()
    orchestrator._playwright = NoopPlaywright()

    orchestrator.run()

    assert orchestrator._email.recipients == ["Recruiter@Example.com"]
    assert [row.outcome.email_status for row in orchestrator._sheets.rows] == [
        "sent",
        "skipped_recently_sent_to_recruiter",
    ]
    assert "recruiter@example.com" in orchestrator._sheets.rows[1].outcome.failure_reason
