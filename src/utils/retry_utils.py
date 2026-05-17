from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


def retry(operation: Callable[[], T], attempts: int = 3, delay_seconds: float = 1.0) -> T:
    """Execute operation with bounded retries."""
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return operation()
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt == attempts:
                break
            time.sleep(delay_seconds * attempt)
    raise RuntimeError(f"Retry exhausted: {last_error}") from last_error
