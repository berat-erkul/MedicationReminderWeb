from datetime import datetime, timezone


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_phone(phone: str) -> str:
    """Normalize phone to digits only (WhatsApp-friendly)."""
    digits = "".join(c for c in phone if c.isdigit())
    return digits


def normalize_reply(text: str) -> str:
    return text.strip().lower()
