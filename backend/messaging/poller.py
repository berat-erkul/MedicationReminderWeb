"""Telegram long-polling loop.

Runs as a background asyncio task (started in the FastAPI lifespan). Pulls
updates via getUpdates and dispatches text replies / button taps to the
reminder service. Works behind home NAT — no public webhook needed.
"""

from __future__ import annotations

import asyncio
import logging

from sqlmodel import Session

from database.session import engine
from messaging.telegram import telegram_client
from services.reminder_service import reminder_service
from utils.config import get_settings

logger = logging.getLogger(__name__)

_task: asyncio.Task | None = None


async def _process_update(update: dict) -> None:
    # Button tap
    if "callback_query" in update:
        cq = update["callback_query"]
        data = cq.get("data", "")
        chat_id = str(cq.get("message", {}).get("chat", {}).get("id", ""))
        with Session(engine) as session:
            await reminder_service.handle_callback(session, chat_id, data)
        await telegram_client.answer_callback(cq["id"], "Kaydedildi ✅")
        return

    # Text message
    message = update.get("message") or update.get("edited_message")
    if not message:
        return
    chat_id = str(message.get("chat", {}).get("id", ""))
    text = (message.get("text") or "").strip()
    if not text:
        return

    # /start → reply with the chat id so the family can register this person.
    if text.startswith("/start") or text.lower() == "/id":
        first = message.get("from", {}).get("first_name", "")
        await telegram_client.send_message(
            chat_id,
            f"Merhaba {first}! 👋\n\nTelegram Chat ID'niz: {chat_id}\n\n"
            f"Bu numarayı İlaç Hatırlatıcı uygulamasında kişiye girin.",
        )
        return

    with Session(engine) as session:
        await reminder_service.handle_incoming(session, chat_id, text)


async def _poll_loop() -> None:
    settings = get_settings()
    if not settings.telegram_bot_token:
        logger.warning("TELEGRAM_BOT_TOKEN yok — Telegram polling başlatılmadı")
        return

    logger.info("Telegram polling başladı")
    offset: int | None = None
    while True:
        try:
            updates = await telegram_client.get_updates(offset)
            for update in updates:
                offset = update["update_id"] + 1
                try:
                    await _process_update(update)
                except Exception:  # noqa: BLE001
                    logger.exception("Update işlenemedi")
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            logger.exception("getUpdates hatası; 3 sn sonra tekrar")
            await asyncio.sleep(3)


def start_polling() -> None:
    global _task
    if _task and not _task.done():
        return
    _task = asyncio.create_task(_poll_loop())


def stop_polling() -> None:
    global _task
    if _task and not _task.done():
        _task.cancel()
    _task = None
