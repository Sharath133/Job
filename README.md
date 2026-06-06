# Autonomous Job Agent

Python 3.11 state-machine pipeline that discovers jobs, filters duplicates, scores fit, sources recruiter leads, drafts and sends outreach, auto-applies to supported portals, and logs every outcome to Google Sheets.

## What it does

1. Ingests latest jobs from Apify and JobSpy.
2. Deduplicates by `job_id` using Google Sheets.
3. Scores role fit via Groq (`llama-3.1-8b-instant`).
4. Enriches recruiter leads using Hunter.
5. Drafts and sends personalized email via SMTP.
6. Submits applications via Playwright for Lever/Greenhouse.
7. Skips Workday and stores screenshot for manual review.
8. Logs success/failure for every job row.

## Guardrails

- Score gate: proceed only when `score > 8`.
- Email safety: max 25 sent emails/day (sheet-derived count).
- Hunter safety: max 3 recruiter searches/run.
- Anti-bot: random 5-15 second jitter between major form actions.
- Hallucination control:
  - Skip empty job descriptions.
  - Skip email if recruiter email is invalid or draft has no `Subject:`.
- Resilience:
  - SMTP and Playwright failures are isolated per job.
  - Processing continues to next job even after failures.

## Project structure

- `src/main.py` orchestrator.
- `src/state_machine.py` deterministic transitions.
- `src/services/*` integrations and execution modules.
- `src/utils/*` logging, retries, validation helpers.
- `tests/unit` and `tests/integration` test coverage.
- `.github/workflows/job-agent.yml` scheduled/manual automation.

## Required environment variables

Copy `.env.example` to `.env` and fill all required secrets.

Minimum required:

- `APIFY_TOKEN`
- `APIFY_ACTOR_ID`
- JobSpy runs without a token by default.
- `GROQ_API_KEY`
- `HUNTER_API_KEY`
- `GMAIL_SENDER_EMAIL`
- `GMAIL_APP_PASSWORD`
- `GOOGLE_SHEET_ID`
- `GOOGLE_SERVICE_ACCOUNT_FILE`

## Google Sheet schema

Worksheet name default: `applied_jobs`.

Expected columns:

`timestamp, job_id, job_title, company, job_url, application_url, score, score_reason, recruiter_name, recruiter_email, email_subject, email_status, portal_status, portal_type, overall_status, failure_reason, screenshot_path, run_id`

## Local setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m playwright install chromium
copy .env.example .env
python -m src.main
```

## GitHub Actions secrets

Configure these repository secrets:

- `APIFY_TOKEN`
- `APIFY_ACTOR_ID`
- JobSpy settings are configured directly in `.github/workflows/job-agent.yml`.
- `GROQ_API_KEY`
- `HUNTER_API_KEY`
- `GMAIL_SENDER_EMAIL`
- `GMAIL_APP_PASSWORD`
- `GOOGLE_SHEET_ID`
- `GOOGLE_SERVICE_ACCOUNT_JSON` (full service account JSON string)

## Notes

- Keep `RUN_MODE=live` only when you are ready for real sends/submissions.
- Store `Resume_Sharath_SDE.pdf` at repository root or update `RESUME_PATH`.
- Workday jobs are intentionally flagged for manual follow-up in `manual_review/`.
