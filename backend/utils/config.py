"""Application settings loaded from environment variables."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve .env from the project root (one level above backend/)
_env_file = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_env_file) if _env_file.exists() else ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "AI WhatsApp Medication Reminder"
    app_env: str = "development"
    debug: bool = True

    database_url: str = "sqlite:///./data/medication.db"

    whatsapp_service_url: str = "http://whatsapp:3001"
    ollama_base_url: str = "http://ollama:11434"
    ollama_model: str = "llama3.2"
    openrouter_api_key: str | None = None
    openrouter_model: str = "openai/gpt-4o-mini"
    ai_provider: str = "ollama"  # ollama | openrouter

    reminder_retry_intervals_minutes: str = "5,15,30"
    reminder_max_retries: int = 3
    admin_phone: str | None = None

    # Push notifications (ntfy → mobile app)
    push_enabled: bool = True
    ntfy_base_url: str = "http://ntfy:80"
    ntfy_topic: str = "medication-reminders"
    ntfy_token: str | None = None  # optional bearer token if ntfy auth is enabled

    timezone: str = "Europe/Istanbul"
    cors_origins: str = "http://localhost:3000,http://frontend:3000"

    @property
    def retry_intervals(self) -> list[int]:
        return [int(x.strip()) for x in self.reminder_retry_intervals_minutes.split(",") if x.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
