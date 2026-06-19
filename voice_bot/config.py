import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is not set in .env")
    return value


def webhook_base_url() -> str:
    return require_env("WEBHOOK_BASE_URL").rstrip("/")


def webhook_host() -> str:
    """Public host for wss:// media stream URLs (no scheme)."""
    return webhook_base_url().removeprefix("https://").removeprefix("http://")


@dataclass(frozen=True)
class Settings:
    openai_api_key: str
    openai_model: str
    openai_voice: str
    telnyx_api_key: str
    telnyx_app_id: str
    telnyx_phone_number: str
    target_phone_number: str
    webhook_base_url: str


def get_settings() -> Settings:
    return Settings(
        openai_api_key=require_env("OPENAI_API_KEY"),
        openai_model=os.getenv("OPENAI_REALTIME_MODEL", "gpt-realtime").strip(),
        openai_voice=os.getenv("OPENAI_VOICE", "alloy").strip(),
        telnyx_api_key=require_env("TELNYX_API_KEY"),
        telnyx_app_id=require_env("TELNYX_APP_ID"),
        telnyx_phone_number=require_env("TELNYX_PHONE_NUMBER"),
        target_phone_number=require_env("TARGET_PHONE_NUMBER"),
        webhook_base_url=webhook_base_url(),
    )
