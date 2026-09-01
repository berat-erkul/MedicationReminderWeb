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

    # Access control — REQUIRED on a public deployment.
    # registration_secret: unset → registration is open (LAN/dev only).
    #   set → POST /api/register must carry a matching `invite_code`.
    # admin_token: unset → /api/users, /api/admin, /api/dashboard/* are open.
    #   set → those endpoints require the `X-Admin-Token` header.
    registration_secret: str | None = None
    admin_token: str | None = None

    # Telegram bot (messaging channel)
    telegram_bot_token: str | None = None
    telegram_api_base: str = "https://api.telegram.org"
    admin_chat_id: str | None = None  # optional: notify a caregiver on missed

    ollama_base_url: str = "http://ollama:11434"
    ollama_model: str = "llama3.2"
    openrouter_api_key: str | None = None
    openrouter_model: str = "nvidia/nemotron-3-ultra-550b-a55b:free"
    # Safety: refuse any non-"":free"" model so a paid model can never bill you.
    openrouter_free_only: bool = True
    ai_provider: str = "ollama"  # ollama | openrouter

    reminder_max_retries: int = 3

    # Push notifications (ntfy → mobile app)
    push_enabled: bool = True
    ntfy_base_url: str = "http://ntfy:80"
    ntfy_topic: str = "medication-reminders"
    ntfy_token: str | None = None  # optional bearer token if ntfy auth is enabled

    timezone: str = "Europe/Istanbul"
    cors_origins: str = "http://localhost:3000,http://frontend:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
