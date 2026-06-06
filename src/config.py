from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralized, typed application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    run_mode: str = Field(default="live", alias="RUN_MODE")
    max_jobs: int = Field(default=10, alias="MAX_JOBS")

    apify_token: str = Field(alias="APIFY_TOKEN")
    apify_actor_id: str = Field(alias="APIFY_ACTOR_ID")

    jobspy_enabled: bool = Field(default=True, alias="JOBSPY_ENABLED")
    jobspy_sites: str = Field(default="linkedin", alias="JOBSPY_SITES")
    jobspy_search_term: str = Field(default="python developer", alias="JOBSPY_SEARCH_TERM")
    jobspy_location: str = Field(default="India", alias="JOBSPY_LOCATION")
    jobspy_hours_old: int = Field(default=24, alias="JOBSPY_HOURS_OLD")
    jobspy_fetch_description: bool = Field(default=True, alias="JOBSPY_FETCH_DESCRIPTION")

    groq_api_key: str = Field(alias="GROQ_API_KEY")
    groq_model: str = Field(default="llama-3.1-8b-instant", alias="GROQ_MODEL")

    hunter_api_key: str = Field(alias="HUNTER_API_KEY")
    snov_client_id: str = Field(default="", alias="SNOV_CLIENT_ID")
    snov_client_secret: str = Field(default="", alias="SNOV_CLIENT_SECRET")
    google_cse_api_key: str = Field(default="", alias="GOOGLE_CSE_API_KEY")
    google_cse_cx: str = Field(default="", alias="GOOGLE_CSE_CX")

    gmail_smtp_host: str = Field(default="smtp.gmail.com", alias="GMAIL_SMTP_HOST")
    gmail_smtp_port: int = Field(default=587, alias="GMAIL_SMTP_PORT")
    gmail_sender_email: str = Field(alias="GMAIL_SENDER_EMAIL")
    gmail_app_password: str = Field(alias="GMAIL_APP_PASSWORD")

    google_sheet_id: str = Field(alias="GOOGLE_SHEET_ID")
    google_service_account_file: str = Field(alias="GOOGLE_SERVICE_ACCOUNT_FILE")
    google_worksheet_name: str = Field(default="applied_jobs", alias="GOOGLE_WORKSHEET_NAME")

    resume_path: str = Field(default="./resume.pdf", alias="RESUME_PATH")
    session_cookies_path: str = Field(default="./session_cookies.json", alias="SESSION_COOKIES_PATH")
    manual_review_dir: str = Field(default="./manual_review", alias="MANUAL_REVIEW_DIR")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    user_agent: str = Field(
        default=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        alias="PLAYWRIGHT_USER_AGENT",
    )

    daily_email_limit: int = 25
    hunter_search_limit_per_run: int = Field(default=3, alias="HUNTER_SEARCH_LIMIT_PER_RUN")
    snov_search_limit_per_run: int = Field(default=3, alias="SNOV_SEARCH_LIMIT_PER_RUN")
    google_search_limit_per_run: int = Field(default=3, alias="GOOGLE_SEARCH_LIMIT_PER_RUN")

    score_threshold: int = 4

    @property
    def snov_enabled(self) -> bool:
        return bool(self.snov_client_id.strip() and self.snov_client_secret.strip())

    @property
    def google_search_enabled(self) -> bool:
        return bool(self.google_cse_api_key.strip() and self.google_cse_cx.strip())

    def validate_runtime_paths(self) -> None:
        """Ensure expected runtime folders exist."""
        Path(self.manual_review_dir).mkdir(parents=True, exist_ok=True)


settings = Settings()
