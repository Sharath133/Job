from __future__ import annotations

import random
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from src.services.session_store import SessionStore


class PlaywrightApplyService:
    """Automates easy apply flows for Lever/Greenhouse portals."""

    def __init__(self, user_agent: str, resume_path: str, manual_review_dir: str, session_store: SessionStore) -> None:
        self._user_agent = user_agent
        self._resume_path = resume_path
        self._manual_review_dir = Path(manual_review_dir)
        self._session_store = session_store
        self._manual_review_dir.mkdir(parents=True, exist_ok=True)

    def classify_portal(self, url: str) -> str:
        host = urlparse(url).netloc.lower()
        if "workday" in host:
            return "workday"
        if "lever.co" in host:
            return "lever"
        if "greenhouse.io" in host:
            return "greenhouse"
        return "unknown"

    def apply(self, application_url: str, job_id: str, full_name: str, email: str, phone: str) -> tuple[str, str]:
        sync_playwright = self._import_sync_playwright()
        portal_type = self.classify_portal(application_url)
        if portal_type == "workday":
            screenshot = self._capture_manual_review_screenshot(application_url, job_id)
            return "manual_required", screenshot
        if portal_type not in {"lever", "greenhouse"}:
            return "skipped_unsupported", ""

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(user_agent=self._user_agent)
            self._load_session(context)
            page = context.new_page()
            try:
                page.goto(application_url, wait_until="domcontentloaded", timeout=60000)
                self._fill_common_fields(page, full_name, email, phone)
                self._upload_resume(page)
                self._save_session(context)
                return "submitted", ""
            finally:
                context.close()
                browser.close()

    def _fill_common_fields(self, page: Any, full_name: str, email: str, phone: str) -> None:
        self._human_delay()
        for selector in ["input[name='name']", "input[id*='name']"]:
            if page.locator(selector).count() > 0:
                page.fill(selector, full_name)
                break

        self._human_delay()
        for selector in ["input[type='email']", "input[name*='email']"]:
            if page.locator(selector).count() > 0:
                page.fill(selector, email)
                break

        self._human_delay()
        for selector in ["input[type='tel']", "input[name*='phone']"]:
            if page.locator(selector).count() > 0:
                page.fill(selector, phone)
                break

    def _upload_resume(self, page: Any) -> None:
        self._human_delay()
        candidates = [
            "input[type='file']",
            "input[name*='resume']",
            "input[id*='resume']",
        ]
        for selector in candidates:
            locator = page.locator(selector)
            if locator.count() > 0:
                locator.first.set_input_files(self._resume_path)
                return

    def _capture_manual_review_screenshot(self, url: str, job_id: str) -> str:
        sync_playwright = self._import_sync_playwright()
        screenshot_path = self._manual_review_dir / f"{job_id}_workday.png"
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(user_agent=self._user_agent)
            page = context.new_page()
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                page.screenshot(path=str(screenshot_path), full_page=True)
            finally:
                context.close()
                browser.close()
        return str(screenshot_path)

    @staticmethod
    def _human_delay() -> None:
        time.sleep(random.uniform(5, 15))

    def _load_session(self, context: Any) -> None:
        cookies = self._session_store.load_cookies()
        if cookies:
            context.add_cookies(cookies)

    def _save_session(self, context: Any) -> None:
        cookies = context.cookies()
        self._session_store.save_cookies(cookies)

    @staticmethod
    def _import_sync_playwright():
        try:
            from playwright.sync_api import sync_playwright
        except ModuleNotFoundError as exc:
            raise RuntimeError("Playwright is not installed. Run: pip install playwright") from exc
        return sync_playwright
