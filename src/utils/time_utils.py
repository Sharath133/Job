from __future__ import annotations

import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


DEFAULT_LOCAL_TIMEZONE = "Asia/Calcutta"


def local_timezone() -> ZoneInfo:
    timezone_name = os.getenv("LOCAL_TIMEZONE", DEFAULT_LOCAL_TIMEZONE)
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return ZoneInfo(DEFAULT_LOCAL_TIMEZONE)


def local_now() -> datetime:
    return datetime.now(timezone.utc).astimezone(local_timezone())


def sheet_now_iso() -> str:
    return local_now().isoformat()


def parse_sheet_datetime(value: object) -> datetime | None:
    raw_value = str(value or "").strip()
    if not raw_value:
        return None
    try:
        parsed = datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=local_timezone())
    return parsed
