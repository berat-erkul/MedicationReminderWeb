"""APScheduler jobs: create+send due reminders, then tick (nag / snooze-resume / missed)."""

from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlmodel import Session, select

from database.session import engine
from models.entities import Reminder
from services.reminder_service import reminder_service
from utils.constants import ReminderStatus
from utils.helpers import utc_now

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def job_create_and_send() -> None:
    with Session(engine) as session:
        created = reminder_service.create_due_reminders(session)
        for reminder in created:
            try:
                await reminder_service.send_reminder(session, reminder)
                logger.info("Sent reminder %s", reminder.id)
            except Exception:  # noqa: BLE001
                logger.exception("Failed to send reminder %s", reminder.id)


async def job_reminders_tick() -> None:
    """Her dakika: ertele süresi dolanları taze gönder, açıkları nag'le/missed'le."""
    now = utc_now()
    with Session(engine) as session:
        # 1) Ertele süresi dolmuş → doz saati o anmış gibi tekrar hatırlat
        for reminder in session.exec(
            select(Reminder).where(Reminder.status == ReminderStatus.SNOOZED)
        ).all():
            due = reminder.snoozed_until
            if due is not None and due.tzinfo is None:
                due = due.replace(tzinfo=now.tzinfo)
            if due is None or now >= due:
                try:
                    await reminder_service.resume_from_snooze(session, reminder)
                    logger.info("Resumed snoozed reminder %s", reminder.id)
                except Exception:  # noqa: BLE001
                    logger.exception("Snooze resume failed for %s", reminder.id)

        # 2) Açık hatırlatmalar → nag ya da missed
        for reminder in session.exec(
            select(Reminder).where(Reminder.status == ReminderStatus.SENT)
        ).all():
            try:
                await reminder_service.tick_reminder(session, reminder, now)
            except Exception:  # noqa: BLE001
                logger.exception("Tick failed for reminder %s", reminder.id)


def start_scheduler() -> None:
    if scheduler.running:
        return
    scheduler.add_job(job_create_and_send, "cron", second=0, id="create_send", replace_existing=True)
    scheduler.add_job(job_reminders_tick, "interval", minutes=1, id="tick", replace_existing=True)
    scheduler.start()
    logger.info("Scheduler started")


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
