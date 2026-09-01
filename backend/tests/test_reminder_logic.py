"""Unit tests for pure reminder logic — no network, no DB."""

import asyncio
from datetime import timedelta

import pytest

from ai.service import ai_service
from models.entities import Reminder
from services.reminder_service import reminder_service
from utils.constants import ReminderAction, ReminderStatus
from utils.helpers import normalize_phone, normalize_reply, utc_now


def test_normalize_phone_strips_non_digits():
    assert normalize_phone("+90 (532) 123-45-67") == "905321234567"


def test_normalize_reply_lowercases_and_trims():
    assert normalize_reply("  Aldım  ") == "aldım"


def test_classify_reply_maps_to_actions():
    assert reminder_service.classify_reply("e") is ReminderAction.TAKE
    assert reminder_service.classify_reply("Aldım") is ReminderAction.TAKE
    assert reminder_service.classify_reply("ertele") is ReminderAction.SNOOZE
    assert reminder_service.classify_reply("sonra") is ReminderAction.SNOOZE
    assert reminder_service.classify_reply("h") is ReminderAction.SKIP
    assert reminder_service.classify_reply("almadım") is ReminderAction.SKIP
    assert reminder_service.classify_reply("belki yarın") is None


def test_nags_due_follows_offset_schedule():
    s = reminder_service
    assert s.NAG_OFFSETS_MIN == (5, 15, 45, 60, 120, 180, 240)
    assert s.nags_due(0) == 0
    assert s.nags_due(4) == 0
    assert s.nags_due(5) == 1
    assert s.nags_due(20) == 2
    assert s.nags_due(50) == 3
    assert s.nags_due(61) == 4
    assert s.nags_due(241) == 7   # all seven sent
    assert s.nags_due(999) == 7


def test_missed_cutoff_at_5_hours():
    s = reminder_service
    assert s.is_missed(299) is False
    assert s.is_missed(300) is True


def test_elapsed_min_uses_nag_anchor_over_sent_at():
    now = utc_now()
    reminder = Reminder(
        user_id=1, schedule_id=1, status=ReminderStatus.SENT,
        scheduled_for=now, sent_at=now - timedelta(hours=3),
        nag_anchor=now - timedelta(minutes=10),  # snooze reset the anchor
    )
    # ~10 min since the anchor, not 3h since sent_at
    assert 9 < reminder_service.elapsed_min(reminder, now=now) < 11


def test_elapsed_min_handles_naive_anchor():
    """SQLite tz-naive datetime + aware now birlikte çalışmalı."""
    aware_now = utc_now()
    naive_anchor = aware_now.replace(tzinfo=None) - timedelta(minutes=45)
    reminder = Reminder(
        user_id=1, schedule_id=1, status=ReminderStatus.SENT,
        scheduled_for=aware_now, nag_anchor=naive_anchor,
    )
    assert 44 < reminder_service.elapsed_min(reminder, now=aware_now) < 46


def test_openrouter_refuses_paid_model_when_free_only(monkeypatch):
    """Billing guard: a non-':free' model must never reach the API."""
    monkeypatch.setattr(ai_service.settings, "openrouter_api_key", "sk-or-test")
    monkeypatch.setattr(ai_service.settings, "openrouter_free_only", True)
    monkeypatch.setattr(ai_service.settings, "openrouter_model", "openai/gpt-4o")
    with pytest.raises(RuntimeError, match="ücretsiz"):
        asyncio.run(ai_service._openrouter("merhaba", None))
