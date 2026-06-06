from __future__ import annotations

from datetime import datetime, timezone

import gspread

from src.models import EmailSendResult, FollowupRow, JobExecutionContext


def _column_letter(column_count: int) -> str:
    """Convert 1-based column count to Excel-style column letters."""
    letters = ""
    while column_count:
        column_count, remainder = divmod(column_count - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


SHEET_COLUMNS = [
    "timestamp",
    "job_id",
    "job_title",
    "company",
    "company_linkedin_url",
    "company_industry",
    "company_headquarters",
    "job_url",
    "application_url",
    "score",
    "recruiter_name",
    "recruiter_title",
    "recruiter_email",
    "hunter_email",
    "lead_source",
    "email_subject",
    "email_status",
    "portal_status",
    "portal_type",
    "overall_status",
    "failure_reason",
    "screenshot_path",
    "run_id",
    "initial_email_sent_at",
    "followup_count",
    "last_followup_sent_at",
    "next_followup_due_at",
    "reply_status",
    "thread_id",
    "message_id",
]


class SheetsService:
    """Google Sheets adapter for dedupe and run logging."""

    def __init__(self, service_account_file: str, sheet_id: str, worksheet_name: str) -> None:
        self._client = gspread.service_account(filename=service_account_file)
        self._sheet = self._client.open_by_key(sheet_id).worksheet(worksheet_name)
        self._ensure_header()

    def _ensure_header(self) -> None:
        values = self._sheet.row_values(1)
        if values != SHEET_COLUMNS:
            self._sheet.update(f"A1:{_column_letter(len(SHEET_COLUMNS))}1", [SHEET_COLUMNS])
        if len(values) > len(SHEET_COLUMNS):
            first_extra = _column_letter(len(SHEET_COLUMNS) + 1)
            last_extra = _column_letter(len(values))
            self._sheet.batch_clear([f"{first_extra}1:{last_extra}1"])

    def _get_records(self) -> list[dict[str, object]]:
        values = self._sheet.get(f"A2:{_column_letter(len(SHEET_COLUMNS))}")
        records: list[dict[str, object]] = []
        for row in values:
            padded_row = [*row, *[""] * (len(SHEET_COLUMNS) - len(row))]
            records.append(dict(zip(SHEET_COLUMNS, padded_row[: len(SHEET_COLUMNS)])))
        return records

    def get_existing_job_ids(self) -> set[str]:
        records = self._get_records()
        return {str(row.get("job_id", "")).strip() for row in records if row.get("job_id")}

    def get_recent_sent_recipients(self, days: int = 14) -> set[str]:
        records = self._get_records()
        now = datetime.now(timezone.utc)
        recipients: set[str] = set()
        for row in records:
            if str(row.get("email_status", "")) != "sent":
                continue
            email = str(row.get("recruiter_email", "")).strip().lower()
            timestamp = str(row.get("timestamp", ""))
            if not email or not timestamp:
                continue
            try:
                sent_at = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                if sent_at.tzinfo is None:
                    sent_at = sent_at.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
            if (now - sent_at).days <= days:
                recipients.add(email)
        return recipients

    def count_emails_sent_today(self) -> int:
        records = self._get_records()
        today = datetime.now(timezone.utc).date()
        count = 0
        for row in records:
            timestamp = str(row.get("timestamp", ""))
            email_status = str(row.get("email_status", ""))
            if email_status != "sent" or not timestamp:
                continue
            try:
                row_day = datetime.fromisoformat(timestamp.replace("Z", "+00:00")).date()
                if row_day == today:
                    count += 1
            except ValueError:
                continue
        return count

    def append_result(self, context: JobExecutionContext) -> None:
        next_row = len(self._sheet.col_values(1)) + 1
        self._sheet.update(
            f"A{next_row}:{_column_letter(len(SHEET_COLUMNS))}{next_row}",
            [context.to_sheet_row()],
            value_input_option="RAW",
        )

    def get_due_followups(self, max_followups: int, now: datetime | None = None) -> list[FollowupRow]:
        now = now or datetime.now(timezone.utc)
        due_rows: list[FollowupRow] = []
        for index, row in enumerate(self._get_records(), start=2):
            if str(row.get("email_status", "")) != "sent":
                continue
            if str(row.get("reply_status", "unknown")).strip().lower() == "replied":
                continue
            if not str(row.get("thread_id", "")).strip():
                continue

            followup_count = self._as_int(row.get("followup_count"))
            if followup_count >= max_followups:
                continue

            due_at = self._parse_datetime(row.get("next_followup_due_at"))
            if not due_at or due_at > now:
                continue

            recruiter_email = str(row.get("recruiter_email", "")).strip()
            if not recruiter_email:
                continue

            due_rows.append(
                FollowupRow(
                    row_number=index,
                    timestamp=str(row.get("timestamp", "")),
                    job_id=str(row.get("job_id", "")),
                    job_title=str(row.get("job_title", "")),
                    company=str(row.get("company", "")),
                    recruiter_name=str(row.get("recruiter_name", "")),
                    recruiter_email=recruiter_email,
                    email_subject=str(row.get("email_subject", "")),
                    followup_count=followup_count,
                    initial_email_sent_at=str(row.get("initial_email_sent_at", "")),
                    last_followup_sent_at=str(row.get("last_followup_sent_at", "")),
                    next_followup_due_at=str(row.get("next_followup_due_at", "")),
                    reply_status=str(row.get("reply_status", "unknown")),
                    thread_id=str(row.get("thread_id", "")),
                    message_id=str(row.get("message_id", "")),
                )
            )
        return due_rows

    def count_followups_sent_today(self) -> int:
        today = datetime.now(timezone.utc).date()
        count = 0
        for row in self._get_records():
            sent_at = self._parse_datetime(row.get("last_followup_sent_at"))
            if sent_at and sent_at.date() == today:
                count += 1
        return count

    def mark_replied(self, row_number: int) -> None:
        self._update_row_fields(row_number, {"reply_status": "replied"})

    def update_followup_sent(
        self,
        row_number: int,
        followup_count: int,
        sent_at: str,
        next_due_at: str,
        result: EmailSendResult,
    ) -> None:
        self._update_row_fields(
            row_number,
            {
                "followup_count": str(followup_count),
                "last_followup_sent_at": sent_at,
                "next_followup_due_at": next_due_at,
                "reply_status": "no_reply",
                "message_id": result.message_id,
                "thread_id": result.thread_id,
            },
        )

    def update_initial_email_metadata(
        self,
        row_number: int,
        sent_at: str,
        next_due_at: str,
        result: EmailSendResult,
    ) -> None:
        self._update_row_fields(
            row_number,
            {
                "initial_email_sent_at": sent_at,
                "followup_count": "0",
                "next_followup_due_at": next_due_at,
                "reply_status": "unknown",
                "message_id": result.message_id,
                "thread_id": result.thread_id,
            },
        )

    def _update_row_fields(self, row_number: int, fields: dict[str, str]) -> None:
        for column_name, value in fields.items():
            column = SHEET_COLUMNS.index(column_name) + 1
            column_letter = _column_letter(column)
            self._sheet.update(
                f"{column_letter}{row_number}:{column_letter}{row_number}",
                [[value]],
                value_input_option="RAW",
            )

    @staticmethod
    def _parse_datetime(value: object) -> datetime | None:
        raw_value = str(value or "").strip()
        if not raw_value:
            return None
        try:
            parsed = datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed

    @staticmethod
    def _as_int(value: object) -> int:
        try:
            return int(str(value or "0").strip())
        except ValueError:
            return 0
