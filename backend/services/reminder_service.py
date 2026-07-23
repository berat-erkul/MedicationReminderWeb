"""Core reminder business logic: send, parse replies, retry, mark missed."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlmodel import Session, col, select

from models.entities import Medicine, Message, Reminder, Schedule, User
from notify.push import push_notifier
from utils.config import get_settings
from utils.constants import (
    NEGATIVE_REPLIES,
    POSITIVE_REPLIES,
    MessageDirection,
    ReminderStatus,
)
from utils.helpers import normalize_phone, normalize_reply, utc_now
from whatsapp.client import whatsapp_client


class ReminderService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def build_message(self, user: User, medicine: Medicine) -> str:
        dosage = f" ({medicine.dosage})" if medicine.dosage else ""
        return (
            f"Merhaba {user.name},\n\n"
            f"💊 {medicine.name}{dosage} zamanı geldi.\n\n"
            f"Aldıysanız *e* veya *aldım*\n"
            f"Almadıysanız *h* veya *almadım* yazın."
        )

    async def send_reminder(self, session: Session, reminder: Reminder) -> Reminder:
        schedule = session.get(Schedule, reminder.schedule_id)
        user = session.get(User, reminder.user_id)
        if not schedule or not user:
            return reminder

        medicine = session.get(Medicine, schedule.medicine_id)
        if not medicine:
            return reminder

        text = self.build_message(user, medicine)
        await whatsapp_client.send_text(user.phone, text)

        dosage = f" ({medicine.dosage})" if medicine.dosage else ""
        await push_notifier.push(
            title=f"💊 İlaç zamanı · {user.name}",
            message=f"{medicine.name}{dosage} zamanı geldi. WhatsApp'tan soruldu.",
            user_id=user.id,
            priority=3,
            tags=["pill"],
        )

        now = utc_now()
        reminder.status = ReminderStatus.SENT
        reminder.sent_at = now
        session.add(
            Message(
                user_id=user.id,
                reminder_id=reminder.id,
                direction=MessageDirection.OUTBOUND,
                content=text,
                phone=user.phone,
            )
        )
        session.add(reminder)
        session.commit()
        session.refresh(reminder)
        return reminder

    async def send_followup(self, session: Session, reminder: Reminder) -> Reminder:
        user = session.get(User, reminder.user_id)
        schedule = session.get(Schedule, reminder.schedule_id)
        if not user or not schedule:
            return reminder

        medicine = session.get(Medicine, schedule.medicine_id)
        medicine_name = medicine.name if medicine else "ilacınız"
        text = (
            f"Hatırlatma ({reminder.retry_count + 1}): "
            f"{medicine_name} alındı mı?\n"
            f"*e* / *aldım* veya *h* / *almadım*"
        )
        await whatsapp_client.send_text(user.phone, text)

        now = utc_now()
        reminder.retry_count += 1
        reminder.last_retry_at = now
        session.add(
            Message(
                user_id=user.id,
                reminder_id=reminder.id,
                direction=MessageDirection.OUTBOUND,
                content=text,
                phone=user.phone,
            )
        )
        session.add(reminder)
        session.commit()
        session.refresh(reminder)
        return reminder

    def classify_reply(self, content: str) -> ReminderStatus | None:
        token = normalize_reply(content)
        if token in POSITIVE_REPLIES:
            return ReminderStatus.COMPLETED
        if token in NEGATIVE_REPLIES:
            return ReminderStatus.SKIPPED
        return None

    def find_open_reminder(self, session: Session, user_id: int) -> Reminder | None:
        stmt = (
            select(Reminder)
            .where(Reminder.user_id == user_id)
            .where(col(Reminder.status).in_([ReminderStatus.SENT, ReminderStatus.PENDING]))
            .order_by(col(Reminder.scheduled_for).desc())
        )
        return session.exec(stmt).first()

    async def handle_incoming(
        self,
        session: Session,
        phone: str,
        content: str,
        raw_payload: str | None = None,
    ) -> dict:
        phone = normalize_phone(phone)
        user = session.exec(select(User).where(User.phone == phone)).first()

        session.add(
            Message(
                user_id=user.id if user else None,
                direction=MessageDirection.INBOUND,
                content=content,
                phone=phone,
                raw_payload=raw_payload,
            )
        )
        session.commit()

        if not user:
            return {"ok": False, "reason": "unknown_user"}

        status = self.classify_reply(content)
        if status is None:
            await whatsapp_client.send_text(
                user.phone,
                "Anlayamadım. Lütfen *e* / *aldım* veya *h* / *almadım* yazın.",
            )
            return {"ok": False, "reason": "unrecognized_reply"}

        reminder = self.find_open_reminder(session, user.id)
        if not reminder:
            return {"ok": False, "reason": "no_open_reminder"}

        reminder.status = status
        reminder.answered_at = utc_now()
        session.add(reminder)
        session.commit()

        if status == ReminderStatus.COMPLETED:
            await push_notifier.push(
                title=f"✅ İlaç alındı · {user.name}",
                message=f"{user.name} ilacını aldığını bildirdi.",
                user_id=user.id,
                priority=2,
                tags=["white_check_mark"],
            )
        else:
            await push_notifier.push(
                title=f"⏭️ İlaç atlandı · {user.name}",
                message=f"{user.name} ilacını almadığını bildirdi.",
                user_id=user.id,
                priority=4,
                tags=["x"],
            )

        ack = "Harika, kaydettim. ✅" if status == ReminderStatus.COMPLETED else "Tamam, not ettim."
        await whatsapp_client.send_text(user.phone, ack)
        return {"ok": True, "reminder_id": reminder.id, "status": status.value}

    async def complete_by_app(
        self, session: Session, reminder: Reminder, *, skipped: bool = False
    ) -> Reminder:
        """Mark a reminder taken/skipped from the mobile app.

        Stops further retries (status leaves SENT). On 'taken' also sends a
        WhatsApp confirmation receipt to the user — this is the extra message
        that only the app path triggers, not the WhatsApp reply path.
        """
        user = session.get(User, reminder.user_id)
        schedule = session.get(Schedule, reminder.schedule_id)
        medicine = session.get(Medicine, schedule.medicine_id) if schedule else None

        reminder.status = ReminderStatus.SKIPPED if skipped else ReminderStatus.COMPLETED
        reminder.answered_at = utc_now()
        session.add(reminder)
        session.commit()
        session.refresh(reminder)

        name = user.name if user else f"#{reminder.user_id}"
        med_name = medicine.name if medicine else "ilaç"

        if skipped:
            await push_notifier.push(
                title=f"⏭️ İlaç atlandı · {name}",
                message=f"{name} {med_name} ilacını uygulamadan 'almadım' işaretledi.",
                user_id=reminder.user_id,
                priority=4,
                tags=["x"],
            )
            return reminder

        await push_notifier.push(
            title=f"✅ İlaç alındı · {name}",
            message=f"{name} {med_name} ilacını uygulamadan aldı olarak işaretledi.",
            user_id=reminder.user_id,
            priority=2,
            tags=["white_check_mark"],
        )

        if user:
            tz = ZoneInfo(user.timezone or self.settings.timezone)
            base = reminder.scheduled_for
            if base.tzinfo is None:
                base = base.replace(tzinfo=ZoneInfo("UTC"))
            local = base.astimezone(tz)
            when = local.strftime("%d.%m.%Y %H:%M")
            dosage = f" ({medicine.dosage})" if medicine and medicine.dosage else ""
            text = (
                f"{name}, {med_name}{dosage} ilacınızı {when} tarihinde/saatinde "
                f"aldığınızı işaretlediniz. Sağlıkla kalın. 🌿"
            )
            await whatsapp_client.send_text(user.phone, text)

        return reminder

    def due_for_retry(self, reminder: Reminder, now: datetime | None = None) -> bool:
        now = now or utc_now()
        if reminder.status != ReminderStatus.SENT:
            return False
        if reminder.retry_count >= self.settings.reminder_max_retries:
            return False

        intervals = self.settings.retry_intervals
        next_index = reminder.retry_count
        if next_index >= len(intervals):
            return False

        wait_minutes = intervals[next_index]
        base = reminder.last_retry_at or reminder.sent_at
        if not base:
            return False
        return now >= base + timedelta(minutes=wait_minutes)

    async def mark_missed_if_exhausted(self, session: Session, reminder: Reminder) -> Reminder:
        if (
            reminder.status == ReminderStatus.SENT
            and reminder.retry_count >= self.settings.reminder_max_retries
        ):
            reminder.status = ReminderStatus.MISSED
            session.add(reminder)
            session.commit()
            session.refresh(reminder)

            user = session.get(User, reminder.user_id)
            name = user.name if user else f"#{reminder.user_id}"

            await push_notifier.push(
                title=f"⚠️ İlaç kaçırıldı · {name}",
                message=f"{name} hatırlatmalara yanıt vermedi. Lütfen kontrol edin.",
                user_id=reminder.user_id,
                priority=5,
                tags=["warning"],
            )

            if self.settings.admin_phone:
                await whatsapp_client.send_text(
                    self.settings.admin_phone,
                    f"⚠️ {name} için hatırlatma yanıtlanmadı (missed).",
                )
        return reminder

    def create_due_reminders(self, session: Session) -> list[Reminder]:
        """Create Reminder rows for schedules that are due in the current minute."""
        tz = ZoneInfo(self.settings.timezone)
        local_now = datetime.now(tz)
        current_time = local_now.time().replace(second=0, microsecond=0)
        weekday = str(local_now.weekday())

        schedules = session.exec(select(Schedule).where(Schedule.is_active == True)).all()  # noqa: E712
        created: list[Reminder] = []

        for schedule in schedules:
            sched_time = schedule.time.replace(second=0, microsecond=0)
            if sched_time.hour != current_time.hour or sched_time.minute != current_time.minute:
                continue

            if schedule.days_of_week:
                allowed = {d.strip() for d in schedule.days_of_week.split(",") if d.strip()}
                if weekday not in allowed:
                    continue

            scheduled_for = local_now.replace(
                hour=sched_time.hour,
                minute=sched_time.minute,
                second=0,
                microsecond=0,
            ).astimezone(ZoneInfo("UTC"))

            # Avoid duplicate for same schedule+minute
            existing = session.exec(
                select(Reminder)
                .where(Reminder.schedule_id == schedule.id)
                .where(Reminder.scheduled_for == scheduled_for)
            ).first()
            if existing:
                continue

            reminder = Reminder(
                user_id=schedule.user_id,
                schedule_id=schedule.id,
                status=ReminderStatus.PENDING,
                scheduled_for=scheduled_for,
            )
            session.add(reminder)
            created.append(reminder)

        if created:
            session.commit()
            for r in created:
                session.refresh(r)
        return created


reminder_service = ReminderService()
