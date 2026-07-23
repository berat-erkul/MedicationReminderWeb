"""APScheduler jobs for due reminders and retries."""

from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlmodel import Session, select

from database.session import engine
from models.entities import Reminder
from services.reminder_service import reminder_service
from utils.constants import ReminderStatus

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


async def job_retries() -> None:
    with Session(engine) as session:
        open_reminders = session.exec(
            select(Reminder).where(Reminder.status == ReminderStatus.SENT)
        ).all()
        for reminder in open_reminders:
            try:
                if reminder_service.due_for_retry(reminder):
                    await reminder_service.repeat_push(session, reminder)
                    logger.info("Push repeat sent for reminder %s", reminder.id)
                await reminder_service.mark_missed_if_exhausted(session, reminder)
            except Exception:  # noqa: BLE001
                logger.exception("Retry/missed handling failed for %s", reminder.id)


def start_scheduler() -> None:
    if scheduler.running:
        return
    scheduler.add_job(job_create_and_send, "cron", second=0, id="create_send", replace_existing=True)
    scheduler.add_job(job_retries, "interval", minutes=1, id="retries", replace_existing=True)
    scheduler.start()
    logger.info("Scheduler started")


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
