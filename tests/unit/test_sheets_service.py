from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.services import sheets_service
from src.services.sheets_service import SHEET_COLUMNS, SheetsService, _column_letter
from src.models import EmailSendResult, JobExecutionContext, JobRecord


class FakeWorksheet:
    def __init__(self, header: list[str], rows: list[list[str]]) -> None:
        self.header = header
        self.rows = rows
        self.updates: list[tuple[str, list[list[str]]]] = []
        self.cleared_ranges: list[str] = []

    def row_values(self, row: int) -> list[str]:
        assert row == 1
        return self.header

    def update(
        self,
        range_name: str,
        values: list[list[str]],
        value_input_option: str | None = None,
    ) -> None:
        assert value_input_option in (None, "RAW")
        self.updates.append((range_name, values))

    def batch_clear(self, ranges: list[str]) -> None:
        self.cleared_ranges.extend(ranges)

    def get(self, range_name: str) -> list[list[str]]:
        assert range_name == f"A2:{_column_letter(len(SHEET_COLUMNS))}"
        return self.rows

    def append_row(self, row: list[str], value_input_option: str) -> None:
        assert value_input_option == "RAW"
        self.rows.append(row)

    def col_values(self, col: int) -> list[str]:
        assert col == 1
        return [self.header[0], *[row[0] for row in self.rows if row and row[0]]]


class FakeClient:
    def __init__(self, worksheet: FakeWorksheet) -> None:
        self._worksheet = worksheet

    def open_by_key(self, sheet_id: str) -> "FakeClient":
        assert sheet_id == "sheet-id"
        return self

    def worksheet(self, worksheet_name: str) -> FakeWorksheet:
        assert worksheet_name == "applied_jobs"
        return self._worksheet


def test_sheets_service_reads_known_columns_when_header_has_duplicate_extra(monkeypatch) -> None:
    today = datetime.now(timezone.utc).isoformat()
    today_row = [""] * len(SHEET_COLUMNS)
    today_row[SHEET_COLUMNS.index("timestamp")] = today
    today_row[SHEET_COLUMNS.index("job_id")] = "job-1"
    today_row[SHEET_COLUMNS.index("job_title")] = "Backend Engineer"
    today_row[SHEET_COLUMNS.index("company")] = "Acme"
    today_row[SHEET_COLUMNS.index("recruiter_email")] = "Recruiter@Example.com"
    today_row[SHEET_COLUMNS.index("email_status")] = "sent"

    old_row = [""] * len(SHEET_COLUMNS)
    old_row[SHEET_COLUMNS.index("timestamp")] = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    old_row[SHEET_COLUMNS.index("job_id")] = "job-2"
    old_row[SHEET_COLUMNS.index("job_title")] = "Old Job"
    old_row[SHEET_COLUMNS.index("company")] = "Acme"
    old_row[SHEET_COLUMNS.index("recruiter_email")] = "old@example.com"
    old_row[SHEET_COLUMNS.index("email_status")] = "sent"

    worksheet = FakeWorksheet(
        header=[*SHEET_COLUMNS, "job_id"],
        rows=[today_row, old_row],
    )

    monkeypatch.setattr(
        sheets_service.gspread,
        "service_account",
        lambda filename: FakeClient(worksheet),
    )

    service = SheetsService("service_account.json", "sheet-id", "applied_jobs")

    first_extra = _column_letter(len(SHEET_COLUMNS) + 1)
    assert worksheet.cleared_ranges == [f"{first_extra}1:{first_extra}1"]
    assert service.get_existing_job_ids() == {"job-1", "job-2"}
    assert service.count_emails_sent_today() == 1
    assert service.get_recent_sent_recipients() == {"recruiter@example.com"}


def test_append_result_updates_first_empty_schema_row(monkeypatch) -> None:
    worksheet = FakeWorksheet(
        header=SHEET_COLUMNS,
        rows=[["2026-01-01T00:00:00", "existing-job"]],
    )
    monkeypatch.setattr(
        sheets_service.gspread,
        "service_account",
        lambda filename: FakeClient(worksheet),
    )

    service = SheetsService("service_account.json", "sheet-id", "applied_jobs")
    context = JobExecutionContext(
        job=JobRecord(
            job_id="new-job",
            title="Diagnostic",
            company="Local",
            description="",
            job_url="",
            application_url="",
        ),
        run_id="run-id",
    )

    service.append_result(context)

    assert worksheet.updates[-1][0] == f"A3:{_column_letter(len(SHEET_COLUMNS))}3"
    assert worksheet.updates[-1][1][0][1] == "new-job"
    assert worksheet.updates[-1][1][0][0].endswith("+05:30")


def test_followup_rows_and_updates(monkeypatch) -> None:
    due_at = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    future_due_at = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()

    due_row = [""] * len(SHEET_COLUMNS)
    due_row[SHEET_COLUMNS.index("timestamp")] = "2026-01-01T00:00:00+00:00"
    due_row[SHEET_COLUMNS.index("job_id")] = "job-1"
    due_row[SHEET_COLUMNS.index("job_title")] = "Backend Engineer"
    due_row[SHEET_COLUMNS.index("company")] = "Acme"
    due_row[SHEET_COLUMNS.index("recruiter_name")] = "Jane"
    due_row[SHEET_COLUMNS.index("recruiter_email")] = "jane@acme.com"
    due_row[SHEET_COLUMNS.index("email_subject")] = "Interested in Backend Engineer"
    due_row[SHEET_COLUMNS.index("email_status")] = "sent"
    due_row[SHEET_COLUMNS.index("initial_email_sent_at")] = "2026-01-01T00:00:00+00:00"
    due_row[SHEET_COLUMNS.index("followup_count")] = "1"
    due_row[SHEET_COLUMNS.index("next_followup_due_at")] = due_at
    due_row[SHEET_COLUMNS.index("reply_status")] = "no_reply"
    due_row[SHEET_COLUMNS.index("thread_id")] = "thread-1"
    due_row[SHEET_COLUMNS.index("message_id")] = "message-1"

    future_row = [*due_row]
    future_row[SHEET_COLUMNS.index("job_id")] = "job-2"
    future_row[SHEET_COLUMNS.index("next_followup_due_at")] = future_due_at

    worksheet = FakeWorksheet(header=SHEET_COLUMNS, rows=[due_row, future_row])
    monkeypatch.setattr(
        sheets_service.gspread,
        "service_account",
        lambda filename: FakeClient(worksheet),
    )

    service = SheetsService("service_account.json", "sheet-id", "applied_jobs")

    due_followups = service.get_due_followups(max_followups=3)

    assert len(due_followups) == 1
    assert due_followups[0].row_number == 2
    assert due_followups[0].job_id == "job-1"

    service.mark_replied(2)
    service.update_followup_sent(
        2,
        2,
        "2026-01-02T00:00:00+00:00",
        "2026-01-03T00:00:00+00:00",
        EmailSendResult(message_id="message-2", thread_id="thread-1"),
    )

    updated_ranges = [range_name for range_name, _values in worksheet.updates]
    reply_column = _column_letter(SHEET_COLUMNS.index("reply_status") + 1)
    count_column = _column_letter(SHEET_COLUMNS.index("followup_count") + 1)
    assert f"{reply_column}2:{reply_column}2" in updated_ranges
    assert f"{count_column}2:{count_column}2" in updated_ranges
