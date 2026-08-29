import secrets
from datetime import datetime, timezone


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def secret_ok(expected: str | None, provided: str | None) -> bool:
    """Constant-time secret check for the access-control gates.

    `expected` unset/blank → gate disabled, always True (LAN/dev).
    Otherwise `provided` must be present and match exactly.
    """
    if not expected:
        return True
    return bool(provided) and secrets.compare_digest(provided, expected)


def normalize_phone(phone: str) -> str:
    """Normalize phone to digits only (WhatsApp-friendly)."""
    digits = "".join(c for c in phone if c.isdigit())
    return digits


def normalize_reply(text: str) -> str:
    return text.strip().lower()
