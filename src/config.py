from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    usvisa_username: str = Field("", alias="USVISA_USERNAME")
    usvisa_password: str = Field("", alias="USVISA_PASSWORD")
    security_a_pet: str = Field("", alias="SECURITY_A_PET")
    security_a_food: str = Field("", alias="SECURITY_A_FOOD")
    security_a_work: str = Field("", alias="SECURITY_A_WORK")

    visa_type: str = Field("Regular", alias="VISA_TYPE")
    visa_category: str = Field("B1/B2", alias="VISA_CATEGORY")
    consulates: str = Field("Kolkata,Mumbai", alias="CONSULATES")
    applicants: int = Field(1, alias="APPLICANTS")

    poll_min_seconds: int = Field(180, alias="POLL_MIN_SECONDS")
    poll_max_seconds: int = Field(420, alias="POLL_MAX_SECONDS")
    backoff_base_seconds: int = Field(600, alias="BACKOFF_BASE_SECONDS")
    backoff_max_seconds: int = Field(3600, alias="BACKOFF_MAX_SECONDS")

    headless: bool = Field(False, alias="HEADLESS")
    slow_mo_ms: int = Field(40, alias="SLOW_MO_MS")
    base_url: str = Field(
        "https://www.usvisascheduling.com/en-US/",
        alias="BASE_URL",
    )
    schedule_url: str = Field("", alias="SCHEDULE_URL")

    # cdp = attach to real Chrome (recommended). launch = Playwright-owned browser.
    browser_mode: str = Field("cdp", alias="BROWSER_MODE")
    cdp_port: int = Field(9222, alias="CDP_PORT")
    chrome_path: str = Field("", alias="CHROME_PATH")

    telegram_bot_token: str = Field("", alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str = Field("", alias="TELEGRAM_CHAT_ID")

    smtp_host: str = Field("", alias="SMTP_HOST")
    smtp_port: int = Field(587, alias="SMTP_PORT")
    smtp_user: str = Field("", alias="SMTP_USER")
    smtp_password: str = Field("", alias="SMTP_PASSWORD")
    alert_email_to: str = Field("", alias="ALERT_EMAIL_TO")

    state_file: Path = Field(Path("data/slot_state.json"), alias="STATE_FILE")
    session_dir: Path = Field(Path("browser_profile"), alias="SESSION_DIR")
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    notify_every_check: bool = Field(True, alias="NOTIFY_EVERY_CHECK")

    @field_validator("consulates", mode="before")
    @classmethod
    def _strip_consulates(cls, value: str) -> str:
        return value or "Kolkata,Mumbai"

    @property
    def consulate_list(self) -> List[str]:
        return [c.strip() for c in self.consulates.split(",") if c.strip()]

    @property
    def cdp_url(self) -> str:
        return f"http://127.0.0.1:{self.cdp_port}"

    def ensure_dirs(self) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.session_dir.mkdir(parents=True, exist_ok=True)
        Path("screenshots").mkdir(parents=True, exist_ok=True)
        Path("data").mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
