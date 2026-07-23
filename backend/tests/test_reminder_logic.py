"""Unit tests for pure reminder logic — no network, no DB."""

from datetime import timedelta

from models.entities import Reminder
from services.reminder_service import reminder_service
from utils.constants import ReminderStatus
from utils.helpers import normalize_phone, normalize_reply, utc_now


def test_normalize_phone_strips_non_digits():
    assert normalize_phone("+90 (532) 123-45-67") == "905321234567"


def test_normalize_reply_lowercases_and_trims():
    assert normalize_reply("  Aldım  ") == "aldım"


def test_classify_positive_reply():
    assert reminder_service.classify_reply("e") == ReminderStatus.COMPLETED
    assert reminder_service.classify_reply("Aldım") == ReminderStatus.COMPLETED


def test_classify_negative_reply():
    assert reminder_service.classify_reply("h") == ReminderStatus.SKIPPED
    assert reminder_service.classify_reply("almadım") == ReminderStatus.SKIPPED


def test_classify_unknown_reply_returns_none():
    assert reminder_service.classify_reply("belki sonra") is None


def test_due_for_retry_waits_for_interval():
    now = utc_now()
    reminder = Reminder(
        user_id=1,
        schedule_id=1,
        status=ReminderStatus.SENT,
        scheduled_for=now,
        sent_at=now,
        retry_count=0,
    )
    # First interval is 5 min by default — not due right after sending.
    assert reminder_service.due_for_retry(reminder, now=now + timedelta(minutes=2)) is False
    # Due once the first interval has elapsed.
    assert reminder_service.due_for_retry(reminder, now=now + timedelta(minutes=6)) is True


def test_due_for_retry_false_when_answered():
    now = utc_now()
    reminder = Reminder(
        user_id=1,
        schedule_id=1,
        status=ReminderStatus.COMPLETED,
        scheduled_for=now,
        sent_at=now,
    )
    assert reminder_service.due_for_retry(reminder, now=now + timedelta(hours=1)) is False
