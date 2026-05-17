from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class SessionStore:
    """Persist browser cookies between runs."""

    def __init__(self, cookies_path: str) -> None:
        self._path = Path(cookies_path)

    def load_cookies(self) -> list[dict[str, Any]]:
        if not self._path.exists():
            return []
        with self._path.open("r", encoding="utf-8") as fp:
            data = json.load(fp)
        if isinstance(data, list):
            return data
        return []

    def save_cookies(self, cookies: list[dict[str, Any]]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("w", encoding="utf-8") as fp:
            json.dump(cookies, fp, indent=2)
