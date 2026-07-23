"""Core reminder business logic: send, parse replies, retry, mark missed.

Messaging channel: Telegram Bot API. Reminders carry one-tap 'Aldım / Almadım'
inline buttons; users can also reply with text. 'Almadım' does NOT stop the
reminders — the 5-minute push cycle keeps going until the dose is taken.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlmodel import Session, col, select

from messaging.telegram import TelegramClient, telegram_client
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


class ReminderService:
    # Push reminders repeat every 5 minutes until taken or max retries reached.
    PUSH_REPEAT_MINUTES = 5

    def __init__(self) -> None:
        self.settings = get_settings()

    def build_message(self, user: User, medicine: Medicine) -> str:
        dosage = f" ({medicine.dosage})" if medicine.dosage else ""
        return (
            f"Merhaba {user.name},\n\n"
            f"💊 {medicine.name}{dosage} zamanı geldi.\n\n"
            f"Aldıysanız ✅ Aldım, almadıysanız ❌ Almadım butonuna basın."
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
        await telegram_client.send_message(
            user.phone, text, buttons=TelegramClient.take_skip_buttons(reminder.id)
        )

        dosage = f" ({medicine.dosage})" if medicine.dosage else ""
        await push_notifier.push(
            title=f"💊 İlaç zamanı · {user.name}",
            message=f"{medicine.name}{dosage} zamanı geldi.",
            user_id=user.id,
            priority=3,
            tags=["pill"],
        )

        reminder.status = ReminderStatus.SENT
        reminder.sent_at = utc_now()
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

    async def repeat_push(self, session: Session, reminder: Reminder) -> Reminder:
        """Repeat the mobile PUSH only (Telegram message is sent once at dose time).

        Runs every PUSH_REPEAT_MINUTES until the dose is marked taken.
        """
        user = session.get(User, reminder.user_id)
        schedule = session.get(Schedule, reminder.schedule_id)
        if not user or not schedule:
            return reminder

        medicine = session.get(Medicine, schedule.medicine_id)
        medicine_name = medicine.name if medicine else "ilacınız"

        await push_notifier.push(
            title=f"💊 Hatırlatma · {user.name}",
            message=f"{medicine_name} henüz alınmadı. Lütfen alın ve 'Aldım' işaretleyin.",
            user_id=user.id,
            priority=4,
            tags=["pill"],
        )

        reminder.retry_count += 1
        reminder.last_retry_at = utc_now()
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

    async def mark_reminder(
        self, session: Session, reminder: Reminder, *, taken: bool
    ) -> Reminder:
        """Central mark logic used by Telegram (buttons/text) and the mobile app.

        taken=True  → completed, reminders stop, confirmation sent.
        taken=False → 'almadım': reminders KEEP going (reset 5-min cycle).
        """
        user = session.get(User, reminder.user_id)
        schedule = session.get(Schedule, reminder.schedule_id)
        medicine = session.get(Medicine, schedule.medicine_id) if schedule else None
        name = user.name if user else f"#{reminder.user_id}"
        med_name = medicine.name if medicine else "ilaç"

        if taken:
            reminder.status = ReminderStatus.COMPLETED
            reminder.answered_at = utc_now()
            session.add(reminder)
            session.commit()
            session.refresh(reminder)

            await push_notifier.push(
                title=f"✅ İlaç alındı · {name}",
                message=f"{name} {med_name} ilacını aldı olarak işaretledi.",
                user_id=reminder.user_id,
                priority=2,
                tags=["white_check_mark"],
            )
            if user:
                tz = ZoneInfo(user.timezone or self.settings.timezone)
                base = reminder.scheduled_for
                if base.tzinfo is None:
                    base = base.replace(tzinfo=ZoneInfo("UTC"))
                when = base.astimezone(tz).strftime("%d.%m.%Y %H:%M")
                dosage = f" ({medicine.dosage})" if medicine and medicine.dosage else ""
                await telegram_client.send_message(
                    user.phone,
                    f"{med_name}{dosage} ilacınızı {when} tarihinde/saatinde aldınız. "
                    f"Sağlıkla kalın. 🌿",
                )
            return reminder

        # 'almadım' → keep reminding: reactivate and restart the 5-min cycle.
        reminder.status = ReminderStatus.SENT
        reminder.retry_count = 0
        reminder.last_retry_at = utc_now()
        reminder.answered_at = None
        session.add(reminder)
        session.commit()
        session.refresh(reminder)

        await push_notifier.push(
            title=f"⏰ Hatırlatma sürüyor · {name}",
            message=f"{name} henüz {med_name} almadı; hatırlatmalar devam ediyor.",
            user_id=reminder.user_id,
            priority=4,
            tags=["hourglass"],
        )
        if user:
            await telegram_client.send_message(
                user.phone,
                f"Tamam, {med_name} birazdan tekrar hatırlatılacak. "
                f"Aldığınızda ✅ Aldım butonuna basın.",
            )
        return reminder

    async def handle_incoming(
        self,
        session: Session,
        chat_id: str,
        content: str,
        raw_payload: str | None = None,
    ) -> dict:
        """Handle a text reply from Telegram."""
        chat = normalize_phone(chat_id)
        user = session.exec(select(User).where(User.phone == chat)).first()

        session.add(
            Message(
                user_id=user.id if user else None,
                direction=MessageDirection.INBOUND,
                content=content,
                phone=chat,
                raw_payload=raw_payload,
            )
        )
        session.commit()

        if not user:
            return {"ok": False, "reason": "unknown_user"}

        status = self.classify_reply(content)
        if status is None:
            await telegram_client.send_message(
                user.phone,
                "Anlayamadım. 'Aldım' / 'Almadım' yazın ya da mesajdaki butonları kullanın.",
            )
            return {"ok": False, "reason": "unrecognized_reply"}

        reminder = self.find_open_reminder(session, user.id)
        if not reminder:
            await telegram_client.send_message(user.phone, "Şu an bekleyen bir hatırlatma yok.")
            return {"ok": False, "reason": "no_open_reminder"}

        await self.mark_reminder(session, reminder, taken=(status == ReminderStatus.COMPLETED))
        return {"ok": True, "reminder_id": reminder.id}

    async def handle_callback(self, session: Session, chat_id: str, data: str) -> dict:
        """Handle an inline-button tap (callback_data 'take:<id>' / 'skip:<id>')."""
        chat = normalize_phone(chat_id)
        user = session.exec(select(User).where(User.phone == chat)).first()
        if not user:
            return {"ok": False, "reason": "unknown_user"}

        try:
            action, rid = data.split(":", 1)
            reminder_id = int(rid)
        except (ValueError, AttributeError):
            return {"ok": False, "reason": "bad_callback"}

        reminder = session.get(Reminder, reminder_id)
        if not reminder or reminder.user_id != user.id:
            return {"ok": False, "reason": "not_found"}

        session.add(
            Message(
                user_id=user.id,
                reminder_id=reminder.id,
                direction=MessageDirection.INBOUND,
                content=f"[buton] {action}",
                phone=chat,
            )
        )
        session.commit()

        await self.mark_reminder(session, reminder, taken=(action == "take"))
        return {"ok": True, "reminder_id": reminder.id, "action": action}

    async def complete_by_app(
        self, session: Session, reminder: Reminder, *, skipped: bool = False
    ) -> Reminder:
        """Mobile app 'Aldım' (skipped=False) / 'Almadım' (skipped=True)."""
        return await self.mark_reminder(session, reminder, taken=not skipped)

    def due_for_retry(self, reminder: Reminder, now: datetime | None = None) -> bool:
        now = now or utc_now()
        if reminder.status != ReminderStatus.SENT:
            return False
        if reminder.retry_count >= self.settings.reminder_max_retries:
            return False

        base = reminder.last_retry_at or reminder.sent_at
        if not base:
            return False
        return now >= base + timedelta(minutes=self.PUSH_REPEAT_MINUTES)

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

            if self.settings.admin_chat_id:
                await telegram_client.send_message(
                    self.settings.admin_chat_id,
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
