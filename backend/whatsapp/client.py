"""WhatsApp client that talks to the Baileys microservice."""

import httpx

from utils.config import get_settings


class WhatsAppClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.base_url = self.settings.whatsapp_service_url.rstrip("/")

    async def send_text(self, phone: str, message: str) -> dict:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/send",
                json={"phone": phone, "message": message},
            )
            response.raise_for_status()
            return response.json()

    async def health(self) -> dict:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{self.base_url}/health")
            response.raise_for_status()
            return response.json()

    async def status(self) -> dict:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{self.base_url}/status")
            response.raise_for_status()
            return response.json()


whatsapp_client = WhatsAppClient()
