from __future__ import annotations

import uuid

from src.config import settings
from src.models import ExecutionOutcome, JobExecutionContext, JobState
from src.services.apify_client import ApifyJobClient
from src.services.company_domain_service import CompanyDomainService
from src.services.google_search_service import GoogleSearchService
from src.services.hunter_service import HunterService
from src.services.lead_service import LeadService
from src.services.snov_service import SnovService
from src.services.email_service import EmailService
from src.services.groq_service import GroqService
from src.services.playwright_service import PlaywrightApplyService
from src.services.session_store import SessionStore
from src.services.sheets_service import SheetsService
from src.state_machine import StateMachine
from src.utils.logging_utils import get_logger
from src.utils.validators import Validators

RESUME_SUMMARY = (
    "Chakradhar Reddy is an SDE focused on Python, FastAPI, Django, GCP, Redis, "
    "and Elasticsearch. IIT Ropar alumnus, currently working at Infinity Learn "
    "on backend service reliability and APIs."
)


class JobAgentOrchestrator:
    """Main workflow orchestrator for autonomous job processing."""

    def __init__(self) -> None:
        settings.validate_runtime_paths()
        self._logger = get_logger("job_agent", settings.log_level)
        self._run_id = str(uuid.uuid4())

        self._apify = ApifyJobClient(settings.apify_token, settings.apify_actor_id)
        self._groq = GroqService(settings.groq_api_key, settings.groq_model)
        domain_resolver = CompanyDomainService()
        snov = (
            SnovService(
                settings.snov_client_id,
                settings.snov_client_secret,
                settings.snov_search_limit_per_run,
                domain_resolver,
            )
            if settings.snov_enabled
            else None
        )
        google_search = (
            GoogleSearchService(
                settings.google_cse_api_key,
                settings.google_cse_cx,
                settings.google_search_limit_per_run,
            )
            if settings.google_search_enabled
            else None
        )
        self._lead = LeadService(
            HunterService(
                settings.hunter_api_key,
                settings.hunter_search_limit_per_run,
                domain_resolver,
            ),
            snov,
            google_search,
            self._logger,
        )
        self._sheets = SheetsService(
            settings.google_service_account_file,
            settings.google_sheet_id,
            settings.google_worksheet_name,
        )
        self._email = EmailService(
            settings.gmail_smtp_host,
            settings.gmail_smtp_port,
            settings.gmail_sender_email,
            settings.gmail_app_password,
            settings.daily_email_limit,
        )
        self._playwright = PlaywrightApplyService(
            settings.user_agent,
            settings.resume_path,
            settings.manual_review_dir,
            SessionStore(settings.session_cookies_path),
        )

    def run(self) -> None:
        self._logger.info("Starting job agent run_id=%s mode=%s", self._run_id, settings.run_mode)
        jobs = self._apify.fetch_latest_jobs(settings.max_jobs)
        existing_ids = self._sheets.get_existing_job_ids()
        emails_sent_today = self._sheets.count_emails_sent_today()

        for job in jobs:
            context = JobExecutionContext(job=job, run_id=self._run_id, outcome=ExecutionOutcome())
            try:
                self._process_single_job(context, existing_ids, emails_sent_today)
            except Exception as exc:  # noqa: BLE001
                context.outcome.failure_reason = f"Unhandled failure: {exc}"
                context.state = JobState.FINALIZED
            finally:
                self._sheets.append_result(context)

    def _process_single_job(self, context: JobExecutionContext, existing_ids: set[str], emails_sent_today: int) -> None:
        if context.job.job_id in existing_ids:
            context.outcome.failure_reason = "Duplicate job_id"
            context.state = JobState.FINALIZED
            return
        StateMachine.transition(context, JobState.DEDUPED)

        if not Validators.has_non_empty_description(context.job.description):
            context.outcome.failure_reason = "Empty description"
            context.state = JobState.FINALIZED
            return

        score, reason = self._groq.score_job(context.job, RESUME_SUMMARY)
        context.score = score
        context.score_reason = reason
        StateMachine.transition(context, JobState.SCORED)

        if score <= settings.score_threshold:
            context.outcome.failure_reason = f"Below threshold: {score}"
            StateMachine.transition(context, JobState.FINALIZED)
            return

        context.recruiter = self._lead.find_recruiter_for_job(context.job)
        StateMachine.transition(context, JobState.LEAD_SOURCED)

        recruiter_name = context.recruiter.name or "Hiring Team"
        context.email_draft = self._groq.generate_email_draft(context.job, RESUME_SUMMARY, recruiter_name)
        StateMachine.transition(context, JobState.DRAFTED)

        self._execute_email_step(context, emails_sent_today)
        self._execute_portal_step(context)

        StateMachine.transition(context, JobState.EXECUTED)
        StateMachine.transition(context, JobState.FINALIZED)

    def _execute_email_step(self, context: JobExecutionContext, emails_sent_today: int) -> None:
        if not context.recruiter.email or not Validators.is_valid_recruiter_email(context.recruiter.email):
            context.outcome.email_status = "skipped_invalid_recruiter_email"
            return
        if not context.email_draft or not context.email_draft.is_valid:
            context.outcome.email_status = "skipped_invalid_email_draft"
            return
        if not self._email.can_send(emails_sent_today):
            context.outcome.email_status = "skipped_daily_limit_reached"
            return

        try:
            self._email.send_email(context.recruiter.email, context.email_draft)
            context.outcome.email_status = "sent"
        except Exception as exc:  # noqa: BLE001
            context.outcome.email_status = "failed"
            context.outcome.failure_reason = f"SMTP failure: {exc}"

    def _execute_portal_step(self, context: JobExecutionContext) -> None:
        if not context.job.application_url:
            context.outcome.portal_status = "skipped_missing_application_url"
            return

        context.outcome.portal_type = self._playwright.classify_portal(context.job.application_url)
        try:
            portal_status, screenshot_path = self._playwright.apply(
                context.job.application_url,
                context.job.job_id,
                full_name="Sharath Reddy",
                email=settings.gmail_sender_email,
                phone="0000000000",
            )
            context.outcome.portal_status = portal_status
            context.outcome.screenshot_path = screenshot_path
        except Exception as exc:  # noqa: BLE001
            context.outcome.portal_status = "failed"
            if context.outcome.failure_reason:
                context.outcome.failure_reason += " | "
            context.outcome.failure_reason += f"Playwright failure: {exc}"


def main() -> None:
    JobAgentOrchestrator().run()


if __name__ == "__main__":
    main()
