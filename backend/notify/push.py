"""Push notifications to the mobile app via a self-hosted ntfy server.

The mobile APK (or the official ntfy app) subscribes to a topic and receives
these notifications. No third-party keys required — everything runs on the
home-server.

Docs: https://docs.ntfy.sh/publish/
"""

from __future__ import annotations

import logging

import httpx

from utils.config import get_settings

logger = logging.getLogger(__name__)


class PushNotifier:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.base_url = self.settings.ntfy_base_url.rstrip("/")
        self.topic = self.settings.ntfy_topic

    def _topic_for(self, user_id: int | None) -> str:
        """Global topic plus an optional per-user topic so caregivers can
        subscribe to a single person if they want (e.g. medication-reminders-3)."""
        if user_id is None:
            return self.topic
        return f"{self.topic}-{user_id}"

    async def push(
        self,
        title: str,
        message: str,
        *,
        user_id: int | None = None,
        priority: int = 3,
        tags: list[str] | None = None,
    ) -> None:
        """Fire-and-forget push. Never raises — a failed push must not break
        the reminder flow (WhatsApp is the primary channel)."""
        if not self.settings.push_enabled:
            return

        topic = self._topic_for(user_id)
        # Use ntfy's JSON publishing endpoint so UTF-8 (Turkish) titles work —
        # HTTP headers can't safely carry non-latin-1 characters.
        body: dict = {
            "topic": topic,
            "title": title,
            "message": message,
            "priority": priority,
        }
        if tags:
            body["tags"] = tags
        headers: dict[str, str] = {}
        if self.settings.ntfy_token:
            headers["Authorization"] = f"Bearer {self.settings.ntfy_token}"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(self.base_url, json=body, headers=headers)
                resp.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Push notification failed (topic=%s): %s", topic, exc)


push_notifier = PushNotifier()
