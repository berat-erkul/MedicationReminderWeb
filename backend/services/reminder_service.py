"""Core reminder business logic — Telegram-driven.

Flow per dose:
  T          dose time → Telegram message with [Aldım] [Ertele] [Almadım] + one push
  T+5,15,45m,             "Lütfen işaretleme yapın." (Telegram text, no buttons)
  T+1,2,3,4h
  T+5h       no answer → status MISSED, caregiver alert, stop

  Aldım   → COMPLETED, stop, confirmation
  Almadım → SKIPPED (o gün almadı), stop
  Ertele  → 1 saat sessizlik, sonra doz saati o anmış gibi taze mesaj + döngü baştan
            (sınırsız tekrar edilebilir)

ntfy push: only key events (dose time / alındı / almadı / kaçırıldı / ertelendi),
NOT the nag repeats — caregiver monitoring stays, nagging is Telegram-only.
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
    SNOOZE_REPLIES,
    MessageDirection,
    ReminderAction,
    ReminderStatus,
)
from utils.helpers import normalize_phone, normalize_reply, utc_now

UTC = ZoneInfo("UTC")


def _aware(dt: datetime | None) -> datetime | None:
    """SQLite döndürdüğü tz-naive datetime'ı UTC-aware yap."""
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


class ReminderService:
    # Doz saatinden (ya da ertele bitişinden) itibaren "Lütfen işaretleme yapın."
    # gönderilecek dakikalar. Değiştirmek serbest — sadece bu tuple.
    NAG_OFFSETS_MIN: tuple[int, ...] = (5, 15, 45, 60, 120, 180, 240)
    # Bu kadar dakika cevapsız → kaçırıldı, bakıcıya haber, dur.
    MISSED_AFTER_MIN = 300
    SNOOZE_MINUTES = 60

    def __init__(self) -> None:
        self.settings = get_settings()

    # ---- pure helpers (test edilebilir) ----

    def nags_due(self, elapsed_min: float) -> int:
        """Geçen süreye göre şu ana kadar KAÇ nag gönderilmiş olmalı."""
        return sum(1 for off in self.NAG_OFFSETS_MIN if elapsed_min >= off)

    def is_missed(self, elapsed_min: float) -> bool:
        return elapsed_min >= self.MISSED_AFTER_MIN

    def elapsed_min(self, reminder: Reminder, now: datetime | None = None) -> float:
        now = _aware(now) or utc_now()
        anchor = _aware(reminder.nag_anchor) or _aware(reminder.sent_at)
        if not anchor:
            return 0.0
        return (now - anchor).total_seconds() / 60.0

    # ---- messaging ----

    def build_message(self, user: User, medicine: Medicine) -> str:
        dosage = f" ({medicine.dosage})" if medicine.dosage else ""
        return (
            f"Merhaba {user.name},\n\n"
            f"💊 {medicine.name}{dosage} zamanı geldi.\n\n"
            f"✅ Aldım · ⏰ Ertele · ❌ Almadım butonlarından birine basın."
        )

    async def _push(self, reminder: Reminder, title: str, message: str,
                    priority: int = 3, tags: list[str] | None = None) -> None:
        await push_notifier.push(
            title=title, message=message, user_id=reminder.user_id,
            priority=priority, tags=tags or ["pill"],
        )

    def _log_out(self, session: Session, reminder: Reminder, user: User, text: str) -> None:
        session.add(Message(
            user_id=user.id, reminder_id=reminder.id,
            direction=MessageDirection.OUTBOUND, content=text, phone=user.phone,
        ))

    async def send_reminder(self, session: Session, reminder: Reminder) -> Reminder:
        """İlk gönderim (doz vakti) veya ertele sonrası taze gönderim."""
        schedule = session.get(Schedule, reminder.schedule_id)
        user = session.get(User, reminder.user_id)
        if not schedule or not user:
            return reminder
        medicine = session.get(Medicine, schedule.medicine_id)
        if not medicine:
            return reminder

        text = self.build_message(user, medicine)
        await telegram_client.send_message(
            user.phone, text, buttons=TelegramClient.reminder_buttons(reminder.id)
        )
        dosage = f" ({medicine.dosage})" if medicine.dosage else ""
        await self._push(
            reminder, f"💊 İlaç zamanı · {user.name}",
            f"{medicine.name}{dosage} zamanı geldi.", priority=3,
        )

        now = utc_now()
        reminder.status = ReminderStatus.SENT
        reminder.sent_at = reminder.sent_at or now
        reminder.nag_anchor = now
        reminder.retry_count = 0
        reminder.last_retry_at = None
        reminder.snoozed_until = None
        self._log_out(session, reminder, user, text)
        session.add(reminder)
        session.commit()
        session.refresh(reminder)
        return reminder

    async def send_nag(self, session: Session, reminder: Reminder) -> Reminder:
        """'Lütfen işaretleme yapın.' — Telegram metni, buton yok."""
        user = session.get(User, reminder.user_id)
        if not user:
            return reminder
        text = "Lütfen işaretleme yapın."
        await telegram_client.send_message(user.phone, text)
        reminder.retry_count += 1
        reminder.last_retry_at = utc_now()
        self._log_out(session, reminder, user, text)
        session.add(reminder)
        session.commit()
        session.refresh(reminder)
        return reminder

    async def mark_missed(self, session: Session, reminder: Reminder) -> Reminder:
        """5 saat cevapsız → kaçırıldı. Bakıcıya Telegram, hastaya bildirim yok."""
        user = session.get(User, reminder.user_id)
        schedule = session.get(Schedule, reminder.schedule_id)
        medicine = session.get(Medicine, schedule.medicine_id) if schedule else None
        name = user.name if user else f"#{reminder.user_id}"
        med_name = medicine.name if medicine else "ilaç"

        reminder.status = ReminderStatus.MISSED
        reminder.answered_at = None
        session.add(reminder)
        session.commit()
        session.refresh(reminder)

        await self._push(
            reminder, f"❌ Doz kaçırıldı · {name}",
            f"{name} {med_name} dozunu 5 saattir işaretlemedi.", priority=4,
            tags=["x", "pill"],
        )
        admin = self.settings.admin_chat_id
        if admin:
            when = self._local_hhmm(reminder, user)
            dosage = f" ({medicine.dosage})" if medicine and medicine.dosage else ""
            await telegram_client.send_message(
                admin,
                f"⚠️ {name}, {med_name}{dosage} ilacını {when} dozunda 5 saattir "
                f"işaretlemedi — kaçırıldı olarak kaydedildi.",
            )
        return reminder

    async def snooze_reminder(self, session: Session, reminder: Reminder) -> Reminder:
        """Ertele: 1 saat sessizlik, sonra tick döngüsü taze gönderir."""
        user = session.get(User, reminder.user_id)
        schedule = session.get(Schedule, reminder.schedule_id)
        medicine = session.get(Medicine, schedule.medicine_id) if schedule else None
        name = user.name if user else f"#{reminder.user_id}"
        med_name = medicine.name if medicine else "ilaç"

        reminder.status = ReminderStatus.SNOOZED
        reminder.snoozed_until = utc_now() + timedelta(minutes=self.SNOOZE_MINUTES)
        reminder.snooze_count += 1
        reminder.answered_at = None
        session.add(reminder)
        session.commit()
        session.refresh(reminder)

        await self._push(
            reminder, f"⏰ Ertelendi · {name}",
            f"{name} {med_name} dozunu 1 saat erteledi.", priority=2, tags=["hourglass"],
        )
        if user:
            text = "Tamam, 1 saat sonra tekrar hatırlatılacak."
            await telegram_client.send_message(user.phone, text)
            self._log_out(session, reminder, user, text)
            session.commit()
        return reminder

    async def resume_from_snooze(self, session: Session, reminder: Reminder) -> Reminder:
        """Ertele süresi doldu → doz saati o anmış gibi taze hatırlatma."""
        return await self.send_reminder(session, reminder)

    async def tick_reminder(
        self, session: Session, reminder: Reminder, now: datetime | None = None
    ) -> Reminder:
        """Her dakika çağrılır. Açık (SENT) bir hatırlatma için: nag ya da missed."""
        if reminder.status != ReminderStatus.SENT:
            return reminder
        elapsed = self.elapsed_min(reminder, now)
        if self.is_missed(elapsed):
            return await self.mark_missed(session, reminder)
        if reminder.retry_count < self.nags_due(elapsed):
            return await self.send_nag(session, reminder)
        return reminder

    # ---- answering (button / text / app) ----

    def classify_reply(self, content: str) -> ReminderAction | None:
        token = normalize_reply(content)
        if token in POSITIVE_REPLIES:
            return ReminderAction.TAKE
        if token in SNOOZE_REPLIES:
            return ReminderAction.SNOOZE
        if token in NEGATIVE_REPLIES:
            return ReminderAction.SKIP
        return None

    def find_open_reminder(self, session: Session, user_id: int) -> Reminder | None:
        open_states = [ReminderStatus.SENT, ReminderStatus.PENDING, ReminderStatus.SNOOZED]
        stmt = (
            select(Reminder)
            .where(Reminder.user_id == user_id)
            .where(col(Reminder.status).in_(open_states))
            .order_by(col(Reminder.scheduled_for).desc())
        )
        return session.exec(stmt).first()

    def _local_hhmm(self, reminder: Reminder, user: User | None) -> str:
        tz = ZoneInfo((user.timezone if user else None) or self.settings.timezone)
        base = _aware(reminder.scheduled_for)
        return base.astimezone(tz).strftime("%H:%M") if base else "?"

    async def mark_reminder(
        self, session: Session, reminder: Reminder, *, taken: bool
    ) -> Reminder:
        """taken=True → COMPLETED. taken=False → SKIPPED (o gün almadı). İkisi de durdurur."""
        user = session.get(User, reminder.user_id)
        schedule = session.get(Schedule, reminder.schedule_id)
        medicine = session.get(Medicine, schedule.medicine_id) if schedule else None
        name = user.name if user else f"#{reminder.user_id}"
        med_name = medicine.name if medicine else "ilaç"
        dosage = f" ({medicine.dosage})" if medicine and medicine.dosage else ""

        reminder.status = ReminderStatus.COMPLETED if taken else ReminderStatus.SKIPPED
        reminder.answered_at = utc_now()
        reminder.snoozed_until = None
        session.add(reminder)
        session.commit()
        session.refresh(reminder)

        if taken:
            await self._push(
                reminder, f"✅ İlaç alındı · {name}",
                f"{name} {med_name} ilacını aldı olarak işaretledi.",
                priority=2, tags=["white_check_mark"],
            )
            if user:
                when = self._local_hhmm(reminder, user)
                await telegram_client.send_message(
                    user.phone,
                    f"{med_name}{dosage} ilacınızı {when} dozunda aldınız. "
                    f"Sağlıkla kalın. 🌿",
                )
        else:
            await self._push(
                reminder, f"❌ İlaç alınmadı · {name}",
                f"{name} {med_name} dozunu almadı olarak işaretledi.",
                priority=3, tags=["x"],
            )
            if user:
                await telegram_client.send_message(
                    user.phone,
                    f"{med_name}{dosage} ilacınızı bugün almadınız olarak işaretlendi.",
                )
        return reminder

    async def apply_action(
        self, session: Session, reminder: Reminder, action: ReminderAction
    ) -> Reminder:
        if action is ReminderAction.TAKE:
            return await self.mark_reminder(session, reminder, taken=True)
        if action is ReminderAction.SKIP:
            return await self.mark_reminder(session, reminder, taken=False)
        return await self.snooze_reminder(session, reminder)

    async def handle_incoming(
        self, session: Session, chat_id: str, content: str, raw_payload: str | None = None,
    ) -> dict:
        chat = normalize_phone(chat_id)
        user = session.exec(select(User).where(User.phone == chat)).first()
        session.add(Message(
            user_id=user.id if user else None, direction=MessageDirection.INBOUND,
            content=content, phone=chat, raw_payload=raw_payload,
        ))
        session.commit()
        if not user:
            return {"ok": False, "reason": "unknown_user"}

        action = self.classify_reply(content)
        if action is None:
            await telegram_client.send_message(
                user.phone,
                "Anlayamadım. 'Aldım' / 'Ertele' / 'Almadım' yazın ya da mesajdaki "
                "butonları kullanın.",
            )
            return {"ok": False, "reason": "unrecognized_reply"}

        reminder = self.find_open_reminder(session, user.id)
        if not reminder:
            await telegram_client.send_message(user.phone, "Şu an bekleyen bir hatırlatma yok.")
            return {"ok": False, "reason": "no_open_reminder"}

        await self.apply_action(session, reminder, action)
        return {"ok": True, "reminder_id": reminder.id, "action": action.value}

    async def handle_callback(self, session: Session, chat_id: str, data: str) -> dict:
        chat = normalize_phone(chat_id)
        user = session.exec(select(User).where(User.phone == chat)).first()
        if not user:
            return {"ok": False, "reason": "unknown_user"}
        try:
            raw_action, rid = data.split(":", 1)
            reminder_id = int(rid)
            action = ReminderAction(raw_action)
        except (ValueError, AttributeError):
            return {"ok": False, "reason": "bad_callback"}

        reminder = session.get(Reminder, reminder_id)
        if not reminder or reminder.user_id != user.id:
            return {"ok": False, "reason": "not_found"}

        session.add(Message(
            user_id=user.id, reminder_id=reminder.id, direction=MessageDirection.INBOUND,
            content=f"[buton] {action.value}", phone=chat,
        ))
        session.commit()

        await self.apply_action(session, reminder, action)
        return {"ok": True, "reminder_id": reminder.id, "action": action.value}

    async def complete_by_app(
        self, session: Session, reminder: Reminder, *, skipped: bool = False
    ) -> Reminder:
        """Mobil app 'Aldım' (skipped=False) / 'Almadım' (skipped=True)."""
        return await self.mark_reminder(session, reminder, taken=not skipped)

    # ---- scheduler entry ----

    def create_due_reminders(self, session: Session) -> list[Reminder]:
        """Bu dakikaya denk gelen aktif programlar için Reminder satırı aç."""
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
                hour=sched_time.hour, minute=sched_time.minute, second=0, microsecond=0,
            ).astimezone(UTC)

            existing = session.exec(
                select(Reminder)
                .where(Reminder.schedule_id == schedule.id)
                .where(Reminder.scheduled_for == scheduled_for)
            ).first()
            if existing:
                continue

            reminder = Reminder(
                user_id=schedule.user_id, schedule_id=schedule.id,
                status=ReminderStatus.PENDING, scheduled_for=scheduled_for,
            )
            session.add(reminder)
            created.append(reminder)

        if created:
            session.commit()
            for r in created:
                session.refresh(r)
        return created


reminder_service = ReminderService()
