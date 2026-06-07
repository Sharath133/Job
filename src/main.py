from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
import uuid
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from src.config import settings
from src.models import EmailDraft, EmailSendResult, ExecutionOutcome, JobExecutionContext, JobRecord, JobState
from src.services.apify_client import ApifyJobClient
from src.services.company_domain_service import CompanyDomainService
from src.services.google_search_service import GoogleSearchService
from src.services.gmail_service import GmailService
from src.services.groq_service import GroqRateLimitError
from src.services.hunter_service import HunterService
from src.services.jobspy_client import JobSpyClient
from src.services.lead_service import LeadService
from src.services.snov_service import SnovService
from src.services.email_service import EmailService
from src.services.groq_service import GroqService
from src.services.playwright_service import PlaywrightApplyService
from src.services.public_contact_service import PublicContactService
from src.services.session_store import SessionStore
from src.services.sheets_service import SheetsService
from src.state_machine import StateMachine
from src.utils.logging_utils import get_logger
from src.utils.subject_utils import subject_for_job
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
        self._jobspy = (
            JobSpyClient(
                settings.jobspy_sites,
                settings.jobspy_search_term,
                settings.jobspy_location,
                settings.jobspy_hours_old,
                settings.jobspy_fetch_description,
                settings.jobspy_results_per_search,
            )
            if settings.jobspy_enabled
            else None
        )
        self._groq = GroqService(
            settings.groq_api_key,
            settings.groq_model,
            settings.groq_request_delay_seconds,
        )
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
        public_contacts = (
            PublicContactService(domain_resolver, settings.public_contact_max_pages)
            if settings.public_contact_enabled
            else None
        )
        hunter = (
            HunterService(
                settings.hunter_api_key,
                settings.hunter_search_limit_per_run,
                domain_resolver,
            )
            if settings.hunter_enabled
            else None
        )
        self._lead = LeadService(
            hunter,
            snov,
            google_search,
            public_contacts,
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
        self._gmail = (
            GmailService(
                settings.gmail_api_client_id,
                settings.gmail_api_client_secret,
                settings.gmail_api_refresh_token,
                settings.gmail_api_from_email,
            )
            if settings.gmail_api_enabled
            else None
        )
        self._playwright = PlaywrightApplyService(
            settings.user_agent,
            settings.resume_path,
            settings.manual_review_dir,
            SessionStore(settings.session_cookies_path),
        )

    def run(self) -> None:
        self._logger.info("Starting job agent run_id=%s mode=%s", self._run_id, settings.run_mode)
        jobs = self._fetch_jobs_from_sources()
        existing_ids = self._sheets.get_existing_job_ids()

        if not jobs:
            self._logger.info("No jobs returned by any source for run_id=%s", self._run_id)
            self._sheets.append_result(
                JobExecutionContext(
                    job=JobRecord(
                        job_id=f"NO_JOBS_{self._run_id}",
                        title="No jobs returned by any source",
                        company="",
                        description="",
                        job_url="",
                        application_url="",
                    ),
                    state=JobState.FINALIZED,
                    outcome=ExecutionOutcome(failure_reason="No jobs returned by any source"),
                    run_id=self._run_id,
                )
            )
            self._process_due_followups()
            return

        new_jobs = [job for job in jobs if job.job_id not in existing_ids]
        jobs_to_process = new_jobs[: settings.max_jobs]
        skipped_existing = len(jobs) - len(new_jobs)
        self._logger.info(
            "Fetched %s job(s), skipped %s already processed job(s), processing %s new job(s)",
            len(jobs),
            skipped_existing,
            len(jobs_to_process),
        )
        if not jobs_to_process:
            self._sheets.append_result(
                JobExecutionContext(
                    job=JobRecord(
                        job_id=f"NO_NEW_JOBS_{self._run_id}",
                        title="No new jobs after dedupe",
                        company="",
                        description="",
                        job_url="",
                        application_url="",
                    ),
                    state=JobState.FINALIZED,
                    outcome=ExecutionOutcome(
                        failure_reason=f"All {len(jobs)} fetched job(s) were already processed"
                    ),
                    run_id=self._run_id,
                )
            )
            self._process_due_followups()
            return

        emails_sent_today = self._sheets.count_emails_sent_today()
        recent_sent_recipients = self._sheets.get_recent_sent_recipients()

        groq_rate_limited = False
        for job in jobs_to_process:
            context = JobExecutionContext(job=job, run_id=self._run_id, outcome=ExecutionOutcome())
            if groq_rate_limited:
                context.outcome.failure_reason = "Skipped because Groq rate limit was reached earlier in this run"
                context.state = JobState.FINALIZED
                self._sheets.append_result(context)
                continue

            try:
                self._process_single_job(context, existing_ids, emails_sent_today, recent_sent_recipients)
            except GroqRateLimitError as exc:
                context.outcome.failure_reason = f"Groq rate limited: {exc}"
                context.state = JobState.FINALIZED
                groq_rate_limited = True
            except Exception as exc:  # noqa: BLE001
                context.outcome.failure_reason = f"Unhandled failure: {exc}"
                context.state = JobState.FINALIZED
            finally:
                self._sheets.append_result(context)

        self._process_due_followups()

    def _fetch_jobs_from_sources(self) -> list[JobRecord]:
        fetchers = {"apify": (self._apify.fetch_latest_jobs, settings.max_jobs)}
        if self._jobspy:
            fetchers["jobspy"] = (self._jobspy.fetch_latest_jobs, settings.jobspy_max_fetched_jobs)

        jobs_by_key: dict[str, JobRecord] = {}
        with ThreadPoolExecutor(max_workers=len(fetchers)) as executor:
            futures = {
                executor.submit(fetcher, limit): source
                for source, (fetcher, limit) in fetchers.items()
            }
            for future in as_completed(futures):
                source = futures[future]
                try:
                    source_jobs = future.result()
                except Exception as exc:  # noqa: BLE001
                    self._logger.exception("%s fetch failed for run_id=%s", source, self._run_id)
                    self._append_source_failure(source, exc)
                    continue

                self._logger.info("%s returned %s job(s)", source, len(source_jobs))
                for job in source_jobs:
                    key = (job.job_url or job.job_id).strip()
                    if key and key not in jobs_by_key:
                        jobs_by_key[key] = job

        return list(jobs_by_key.values())

    def _append_source_failure(self, source: str, exc: Exception) -> None:
        source_label = source.upper()
        self._sheets.append_result(
            JobExecutionContext(
                job=JobRecord(
                    job_id=f"{source_label}_FETCH_FAILED_{self._run_id}",
                    title=f"{source_label} fetch failed",
                    company="",
                    description="",
                    job_url="",
                    application_url="",
                ),
                state=JobState.FINALIZED,
                outcome=ExecutionOutcome(failure_reason=f"{source_label} fetch failed: {exc}"),
                run_id=self._run_id,
            )
        )

    def _process_single_job(
        self,
        context: JobExecutionContext,
        existing_ids: set[str],
        emails_sent_today: int,
        recent_sent_recipients: set[str],
    ) -> None:
        if context.job.job_id in existing_ids:
            context.outcome.failure_reason = "Duplicate job_id"
            context.state = JobState.FINALIZED
            return
        StateMachine.transition(context, JobState.DEDUPED)

        if not Validators.has_non_empty_description(context.job.description):
            context.outcome.failure_reason = "Empty description"
            context.state = JobState.FINALIZED
            return

        score = self._groq.score_job(context.job, RESUME_SUMMARY)
        context.score = score
        StateMachine.transition(context, JobState.SCORED)

        if score <= settings.score_threshold:
            context.outcome.failure_reason = f"Below threshold: {score}"
            StateMachine.transition(context, JobState.FINALIZED)
            return

        context.recruiter = self._lead.find_recruiter_for_job(context.job)
        StateMachine.transition(context, JobState.LEAD_SOURCED)

        recruiter_name = context.recruiter.name or "Hiring Team"
        context.email_draft = self._groq.generate_email_draft(context.job, RESUME_SUMMARY, recruiter_name)
        context.email_draft = self._with_standard_subject(context.email_draft, context.job)
        StateMachine.transition(context, JobState.DRAFTED)

        self._execute_email_step(context, emails_sent_today, recent_sent_recipients)
        self._execute_portal_step(context)

        StateMachine.transition(context, JobState.EXECUTED)
        StateMachine.transition(context, JobState.FINALIZED)

    def _execute_email_step(
        self,
        context: JobExecutionContext,
        emails_sent_today: int,
        recent_sent_recipients: set[str],
    ) -> None:
        if not context.recruiter.email or not Validators.is_valid_recruiter_email(context.recruiter.email):
            context.outcome.email_status = "skipped_invalid_recruiter_email"
            return
        recipient = context.recruiter.email.strip().lower()
        if recipient in recent_sent_recipients:
            context.outcome.email_status = "skipped_recently_sent_to_recruiter"
            context.outcome.failure_reason = f"Recently sent to recruiter: {recipient}"
            return
        if not context.email_draft or not context.email_draft.is_valid:
            context.outcome.email_status = "skipped_invalid_email_draft"
            return
        if not self._email.can_send(emails_sent_today):
            context.outcome.email_status = "skipped_daily_limit_reached"
            return
        if self._is_email_pause_day():
            context.outcome.email_status = "skipped_sunday"
            context.outcome.failure_reason = "Email sending skipped on Sunday"
            return

        try:
            sent_at = self._utc_now()
            sender = getattr(self, "_gmail", None) or self._email
            result = sender.send_email(context.recruiter.email, context.email_draft, settings.resume_path)
            if result is None:
                result = EmailSendResult()
            context.outcome.email_status = "sent"
            context.initial_email_sent_at = sent_at
            context.next_followup_due_at = self._next_followup_due_at(sent_at, 0)
            context.reply_status = "unknown"
            context.thread_id = result.thread_id
            context.message_id = result.message_id
            recent_sent_recipients.add(recipient)
        except Exception as exc:  # noqa: BLE001
            context.outcome.email_status = "failed"
            context.outcome.failure_reason = f"Email failure: {exc}"

    def _process_due_followups(self) -> None:
        if not settings.followup_enabled:
            return
        if self._is_email_pause_day():
            self._logger.info("Email sending is skipped on Sunday; skipping follow-up processing")
            return
        gmail = getattr(self, "_gmail", None)
        if not gmail:
            self._logger.info("Gmail API is not configured; skipping follow-up processing")
            return

        followups_sent_today = self._sheets.count_followups_sent_today()
        if followups_sent_today >= settings.followup_daily_limit:
            self._logger.info("Follow-up daily limit reached; skipping follow-up processing")
            return

        due_followups = self._sheets.get_due_followups(settings.followup_max_count)
        for followup in due_followups:
            if followups_sent_today >= settings.followup_daily_limit:
                break
            try:
                if gmail.has_reply(followup.thread_id, settings.gmail_api_from_email):
                    self._sheets.mark_replied(followup.row_number)
                    continue

                result = gmail.send_followup(followup)
                sent_at = self._utc_now()
                next_count = followup.followup_count + 1
                next_due_at = self._next_followup_due_at(
                    followup.initial_email_sent_at or followup.timestamp,
                    next_count,
                )
                self._sheets.update_followup_sent(
                    followup.row_number,
                    next_count,
                    sent_at,
                    next_due_at,
                    result,
                )
                followups_sent_today += 1
            except Exception as exc:  # noqa: BLE001
                self._logger.warning(
                    "Follow-up processing failed for row %s job_id=%s: %s",
                    followup.row_number,
                    followup.job_id,
                    exc,
                )

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

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _parse_datetime(value: str) -> datetime:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return datetime.now(timezone.utc)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed

    def _next_followup_due_at(self, initial_sent_at: str, followup_count: int) -> str:
        if followup_count >= settings.followup_max_count:
            return ""

        offsets = settings.followup_due_day_offsets
        offset_index = min(followup_count, len(offsets) - 1)
        initial_time = self._parse_datetime(initial_sent_at)
        return (initial_time + timedelta(days=offsets[offset_index])).isoformat()

    @staticmethod
    def _standard_subject(job: JobRecord) -> str:
        return subject_for_job(job)

    @classmethod
    def _with_standard_subject(cls, draft: EmailDraft, job: JobRecord) -> EmailDraft:
        return EmailDraft(
            subject=cls._standard_subject(job),
            body=draft.body,
            is_valid=draft.is_valid,
            validation_error=draft.validation_error,
        )

    @staticmethod
    def _is_email_pause_day(now: datetime | None = None) -> bool:
        if not settings.skip_email_on_sunday:
            return False
        current_time = now or datetime.now(timezone.utc)
        try:
            local_time = current_time.astimezone(ZoneInfo(settings.local_timezone))
        except ZoneInfoNotFoundError:
            local_time = current_time.astimezone(timezone.utc)
        return local_time.weekday() == 6


def main() -> None:
    JobAgentOrchestrator().run()


if __name__ == "__main__":
    main()
