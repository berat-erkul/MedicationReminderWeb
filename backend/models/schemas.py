from datetime import datetime, time
from typing import Optional

from pydantic import BaseModel, Field

from utils.constants import MessageDirection, RecurrenceType, ReminderStatus


# --- User ---
class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    phone: str = Field(min_length=8, max_length=20)
    timezone: str = "Europe/Istanbul"


class UserUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    timezone: Optional[str] = None
    is_active: Optional[bool] = None


class UserRead(BaseModel):
    id: int
    name: str
    phone: str
    timezone: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Medicine ---
class MedicineCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    dosage: str = ""
    notes: Optional[str] = None


class MedicineUpdate(BaseModel):
    name: Optional[str] = None
    dosage: Optional[str] = None
    notes: Optional[str] = None


class MedicineRead(BaseModel):
    id: int
    name: str
    dosage: str
    notes: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Schedule ---
class ScheduleCreate(BaseModel):
    user_id: int
    medicine_id: int
    time: time
    recurrence: RecurrenceType = RecurrenceType.DAILY
    days_of_week: Optional[str] = None
    is_active: bool = True


class ScheduleUpdate(BaseModel):
    time: Optional[time] = None
    recurrence: Optional[RecurrenceType] = None
    days_of_week: Optional[str] = None
    is_active: Optional[bool] = None


class ScheduleRead(BaseModel):
    id: int
    user_id: int
    medicine_id: int
    time: time
    recurrence: RecurrenceType
    days_of_week: Optional[str]
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Reminder ---
class ReminderRead(BaseModel):
    id: int
    user_id: int
    schedule_id: int
    status: ReminderStatus
    scheduled_for: datetime
    sent_at: Optional[datetime]
    answered_at: Optional[datetime]
    retry_count: int
    notes: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Message ---
class MessageRead(BaseModel):
    id: int
    user_id: Optional[int]
    reminder_id: Optional[int]
    direction: MessageDirection
    content: str
    phone: str
    timestamp: datetime

    model_config = {"from_attributes": True}


class DashboardStats(BaseModel):
    total_users: int
    active_schedules: int
    reminders_today: int
    completed_today: int
    missed_today: int
    pending_replies: int
