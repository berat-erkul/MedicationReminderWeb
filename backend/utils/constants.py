from enum import Enum


class ReminderStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    SNOOZED = "snoozed"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    MISSED = "missed"
    CANCELLED = "cancelled"


class MessageDirection(str, Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class RecurrenceType(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    CUSTOM = "custom"


class ReminderAction(str, Enum):
    TAKE = "take"
    SNOOZE = "snooze"
    SKIP = "skip"


# Simple Turkish reply tokens accepted from elderly users
POSITIVE_REPLIES = {"e", "evet", "aldım", "aldim", "aldım.", "ok", "tamam", "aldi", "aldık"}
NEGATIVE_REPLIES = {"h", "hayır", "hayir", "almadım", "almadim", "yok", "alamadım", "alamadim"}
SNOOZE_REPLIES = {"ertele", "sonra", "birazdan", "beklet", "1 saat", "erteledi"}
