from datetime import datetime, timezone

from src.models import EmailDraft, EmailSendResult, ExecutionOutcome, FollowupRow, JobExecutionContext, JobRecord, RecruiterLead
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


class EmptyJobSource:
    def fetch_latest_jobs(self, max_jobs: int) -> list[JobRecord]:
        return []


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

    def count_followups_sent_today(self) -> int:
        return 0

    def get_due_followups(self, max_followups: int):
        return []


class DueFollowupSheets(NoopSheets):
    def __init__(self) -> None:
        super().__init__()
        self.updated_followups: list[tuple[int, int, str, str, EmailSendResult]] = []

    def get_due_followups(self, max_followups: int):
        return [
            FollowupRow(
                row_number=4,
                timestamp="2026-01-01T00:00:00+00:00",
                job_id="job-1",
                job_title="Backend Engineer",
                company="Acme",
                recruiter_name="Jane",
                recruiter_email="jane@acme.com",
                email_subject="Interested in Backend Engineer",
                followup_count=0,
                initial_email_sent_at="2026-01-01T00:00:00+00:00",
                last_followup_sent_at="",
                next_followup_due_at="2026-01-02T00:00:00+00:00",
                reply_status="unknown",
                thread_id="thread-1",
                message_id="message-1",
            )
        ]

    def update_followup_sent(
        self,
        row_number: int,
        followup_count: int,
        sent_at: str,
        next_due_at: str,
        result: EmailSendResult,
    ) -> None:
        self.updated_followups.append((row_number, followup_count, sent_at, next_due_at, result))

    def mark_replied(self, row_number: int) -> None:
        raise AssertionError("No reply should be detected in this test")


class ExistingJobSheets(NoopSheets):
    def get_existing_job_ids(self) -> set[str]:
        return {"job-1"}


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
    def __init__(self) -> None:
        self.scored_job_ids: list[str] = []

    def score_job(self, job: JobRecord, resume_summary: str) -> int:
        self.scored_job_ids.append(job.job_id)
        return 100

    def generate_email_draft(self, job: JobRecord, resume_summary: str, recruiter_name: str) -> EmailDraft:
        return EmailDraft(subject=f"Interested in {job.title}", body="Hello", is_valid=True)


class SameRecruiterLead:
    def find_recruiter_for_job(self, job: JobRecord) -> RecruiterLead:
        return RecruiterLead(name="Recruiter", email="Recruiter@Example.com", title="Recruiter")


class RecordingEmail:
    def __init__(self) -> None:
        self.recipients: list[str] = []
        self.subjects: list[str] = []

    def can_send(self, already_sent_today: int) -> bool:
        return True

    def send_email(self, recipient_email: str, draft: EmailDraft, attachment_path: str | None = None) -> None:
        self.recipients.append(recipient_email)
        self.subjects.append(draft.subject)


class NoopPlaywright:
    pass


class FakeGmail:
    def __init__(self) -> None:
        self.sent_followups: list[FollowupRow] = []

    def has_reply(self, thread_id: str, sender_email: str | None = None) -> bool:
        return False

    def send_followup(self, followup: FollowupRow) -> EmailSendResult:
        self.sent_followups.append(followup)
        return EmailSendResult(message_id="message-2", thread_id=followup.thread_id)


def test_run_skips_duplicate_recruiter_email_in_same_run(monkeypatch) -> None:
    monkeypatch.setattr("src.main.settings.skip_email_on_sunday", False)
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
    assert orchestrator._email.subjects == [
        "Backend Engineer @ Acme | Python, FastAPI, Django | IIT Ropar"
    ]
    assert "recruiter@example.com" in orchestrator._sheets.rows[1].outcome.failure_reason


def test_run_filters_existing_jobs_before_processing(monkeypatch) -> None:
    monkeypatch.setattr("src.main.settings.skip_email_on_sunday", False)
    orchestrator = JobAgentOrchestrator.__new__(JobAgentOrchestrator)
    orchestrator._run_id = "run-id"
    orchestrator._logger = FakeLogger()
    orchestrator._sheets = ExistingJobSheets()
    orchestrator._apify = DuplicateRecruiterJobSource()
    orchestrator._jobspy = None
    orchestrator._groq = SuccessfulGroq()
    orchestrator._lead = SameRecruiterLead()
    orchestrator._email = RecordingEmail()
    orchestrator._playwright = NoopPlaywright()

    orchestrator.run()

    assert orchestrator._groq.scored_job_ids == ["job-2"]
    assert [row.job.job_id for row in orchestrator._sheets.rows] == ["job-2"]
    assert orchestrator._email.recipients == ["Recruiter@Example.com"]


def test_run_processes_due_followups_when_gmail_configured(monkeypatch) -> None:
    monkeypatch.setattr("src.main.settings.skip_email_on_sunday", False)
    orchestrator = JobAgentOrchestrator.__new__(JobAgentOrchestrator)
    orchestrator._run_id = "run-id"
    orchestrator._logger = FakeLogger()
    orchestrator._sheets = DueFollowupSheets()
    orchestrator._apify = EmptyJobSource()
    orchestrator._jobspy = None
    orchestrator._gmail = FakeGmail()

    orchestrator.run()

    assert [row.job.job_id for row in orchestrator._sheets.rows] == ["NO_JOBS_run-id"]
    assert len(orchestrator._gmail.sent_followups) == 1
    assert orchestrator._sheets.updated_followups[0][0] == 4
    assert orchestrator._sheets.updated_followups[0][1] == 1


def test_email_pause_day_uses_local_timezone(monkeypatch) -> None:
    monkeypatch.setattr("src.main.settings.skip_email_on_sunday", True)
    monkeypatch.setattr("src.main.settings.local_timezone", "Asia/Calcutta")
    sunday_ist = datetime(2026, 6, 6, 19, 0, tzinfo=timezone.utc)
    monday_ist = datetime(2026, 6, 7, 19, 0, tzinfo=timezone.utc)

    assert JobAgentOrchestrator._is_email_pause_day(sunday_ist)
    assert not JobAgentOrchestrator._is_email_pause_day(monday_ist)
