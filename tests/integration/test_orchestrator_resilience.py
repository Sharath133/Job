from src.models import EmailDraft, ExecutionOutcome, JobExecutionContext, JobRecord


class FakeEmail:
    def can_send(self, already_sent_today: int) -> bool:
        return True

    def send_email(self, recipient_email: str, draft: EmailDraft) -> None:
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
