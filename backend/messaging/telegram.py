"""Telegram Bot API client.

Official, free, no QR/session — the backend talks to Telegram directly over
HTTPS and receives replies via long polling (works behind home NAT).
"""

from __future__ import annotations

import logging

import httpx

from utils.config import get_settings

logger = logging.getLogger(__name__)


class TelegramClient:
    def __init__(self) -> None:
        self.settings = get_settings()

    @property
    def token(self) -> str | None:
        return self.settings.telegram_bot_token

    def _url(self, method: str) -> str:
        return f"{self.settings.telegram_api_base.rstrip('/')}/bot{self.token}/{method}"

    @staticmethod
    def take_skip_buttons(reminder_id: int) -> list[list[dict]]:
        """Inline keyboard: one-tap 'Aldım' / 'Almadım' for elderly users."""
        return [[
            {"text": "✅ Aldım", "callback_data": f"take:{reminder_id}"},
            {"text": "❌ Almadım", "callback_data": f"skip:{reminder_id}"},
        ]]

    async def send_message(
        self,
        chat_id: str | int,
        text: str,
        buttons: list[list[dict]] | None = None,
    ) -> dict | None:
        if not self.token:
            logger.warning("TELEGRAM_BOT_TOKEN yok — mesaj gönderilemedi")
            return None
        payload: dict = {"chat_id": chat_id, "text": text}
        if buttons:
            payload["reply_markup"] = {"inline_keyboard": buttons}
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(self._url("sendMessage"), json=payload)
                resp.raise_for_status()
                return resp.json()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Telegram sendMessage başarısız (chat=%s): %s", chat_id, exc)
            return None

    async def answer_callback(self, callback_query_id: str, text: str | None = None) -> None:
        if not self.token:
            return
        payload: dict = {"callback_query_id": callback_query_id}
        if text:
            payload["text"] = text
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(self._url("answerCallbackQuery"), json=payload)
        except Exception as exc:  # noqa: BLE001
            logger.warning("answerCallbackQuery başarısız: %s", exc)

    async def get_updates(self, offset: int | None, timeout: int = 25) -> list[dict]:
        if not self.token:
            return []
        params: dict = {"timeout": timeout}
        if offset is not None:
            params["offset"] = offset
        # Read timeout must exceed the long-poll timeout.
        async with httpx.AsyncClient(timeout=timeout + 10) as client:
            resp = await client.get(self._url("getUpdates"), params=params)
            resp.raise_for_status()
            data = resp.json()
            return data.get("result", [])


telegram_client = TelegramClient()
