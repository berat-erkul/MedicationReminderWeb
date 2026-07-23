from datetime import datetime, time
from typing import Optional

from sqlmodel import Field, Relationship, SQLModel

from utils.constants import MessageDirection, RecurrenceType, ReminderStatus
from utils.helpers import utc_now


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    phone: str = Field(unique=True, index=True)
    timezone: str = Field(default="Europe/Istanbul")
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=utc_now)

    schedules: list["Schedule"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    reminders: list["Reminder"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    messages: list["Message"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class Medicine(SQLModel, table=True):
    __tablename__ = "medicines"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    dosage: str = Field(default="")
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)

    schedules: list["Schedule"] = Relationship(
        back_populates="medicine",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class Schedule(SQLModel, table=True):
    __tablename__ = "schedules"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    medicine_id: int = Field(foreign_key="medicines.id", index=True)
    time: time
    recurrence: RecurrenceType = Field(default=RecurrenceType.DAILY)
    days_of_week: Optional[str] = Field(
        default=None,
        description="Comma-separated weekdays 0=Mon..6=Sun for weekly/custom",
    )
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=utc_now)

    user: Optional[User] = Relationship(back_populates="schedules")
    medicine: Optional[Medicine] = Relationship(back_populates="schedules")
    reminders: list["Reminder"] = Relationship(
        back_populates="schedule",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class Reminder(SQLModel, table=True):
    __tablename__ = "reminders"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    schedule_id: int = Field(foreign_key="schedules.id", index=True)
    status: ReminderStatus = Field(default=ReminderStatus.PENDING, index=True)
    scheduled_for: datetime = Field(index=True)
    sent_at: Optional[datetime] = None
    answered_at: Optional[datetime] = None
    retry_count: int = Field(default=0)
    last_retry_at: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)

    user: Optional[User] = Relationship(back_populates="reminders")
    schedule: Optional[Schedule] = Relationship(back_populates="reminders")


class Message(SQLModel, table=True):
    __tablename__ = "messages"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="users.id", index=True)
    reminder_id: Optional[int] = Field(default=None, foreign_key="reminders.id", index=True)
    direction: MessageDirection
    content: str
    phone: str = Field(index=True)
    timestamp: datetime = Field(default_factory=utc_now, index=True)
    raw_payload: Optional[str] = None

    user: Optional[User] = Relationship(back_populates="messages")
