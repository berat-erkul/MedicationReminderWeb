from enum import Enum


class ReminderStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
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


# Simple Turkish reply tokens accepted from elderly users
POSITIVE_REPLIES = {"e", "evet", "aldım", "aldim", "aldım.", "ok", "tamam"}
NEGATIVE_REPLIES = {"h", "hayır", "hayir", "almadım", "almadim", "yok"}
