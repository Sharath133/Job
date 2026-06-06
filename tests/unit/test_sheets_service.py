from __future__ import annotations

from datetime import datetime, timezone

from src.services import sheets_service
from src.services.sheets_service import SHEET_COLUMNS, SheetsService
from src.models import JobExecutionContext, JobRecord


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
        assert range_name == "A2:X"
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
    worksheet = FakeWorksheet(
        header=[*SHEET_COLUMNS, "job_id"],
        rows=[
            [today, "job-1", "Backend Engineer", "Acme", *[""] * 13, "sent"],
            ["2020-01-01T00:00:00+00:00", "job-2", "Old Job", "Acme", *[""] * 13, "sent"],
        ],
    )

    monkeypatch.setattr(
        sheets_service.gspread,
        "service_account",
        lambda filename: FakeClient(worksheet),
    )

    service = SheetsService("service_account.json", "sheet-id", "applied_jobs")

    assert worksheet.cleared_ranges == ["Y1:Y1"]
    assert service.get_existing_job_ids() == {"job-1", "job-2"}
    assert service.count_emails_sent_today() == 1


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

    assert worksheet.updates[-1][0] == "A3:X3"
    assert worksheet.updates[-1][1][0][1] == "new-job"
