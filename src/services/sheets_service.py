from __future__ import annotations

from datetime import datetime, timezone

import gspread

from src.models import JobExecutionContext


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
    "score_reason",
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
