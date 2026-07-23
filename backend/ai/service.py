"""AI provider abstraction — Ollama (default) or OpenRouter."""

from __future__ import annotations

import httpx

from utils.config import get_settings


class AIService:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def generate(self, prompt: str, system: str | None = None) -> str:
        provider = self.settings.ai_provider.lower()
        if provider == "openrouter":
            return await self._openrouter(prompt, system)
        return await self._ollama(prompt, system)

    async def _ollama(self, prompt: str, system: str | None) -> str:
        payload: dict = {
            "model": self.settings.ollama_model,
            "prompt": prompt,
            "stream": False,
        }
        if system:
            payload["system"] = system

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.settings.ollama_base_url.rstrip('/')}/api/generate",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("response", "").strip()

    async def _openrouter(self, prompt: str, system: str | None) -> str:
        if not self.settings.openrouter_api_key:
            raise RuntimeError("OPENROUTER_API_KEY is not configured")

        model = self.settings.openrouter_model
        # Hard guard: never call a paid model when free-only is on → no billing.
        if self.settings.openrouter_free_only and not model.endswith(":free"):
            raise RuntimeError(
                f"OPENROUTER_FREE_ONLY aktif ama model ücretsiz değil: '{model}'. "
                "Sonu ':free' ile biten bir model kullan (örn. "
                "meta-llama/llama-3.3-70b-instruct:free)."
            )

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.settings.openrouter_api_key}",
                    "Content-Type": "application/json",
                },
                json={"model": model, "messages": messages},
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()

    async def weekly_adherence_summary(self, stats_text: str) -> str:
        system = (
            "Sen aileler için ilaç uyum asistanısın. Kısa, net ve teşvik edici Türkçe "
            "gözlemler yaz. Tıbbi tavsiye verme."
        )
        prompt = (
            "Aşağıdaki haftalık ilaç uyum verisine bakarak 3-5 maddelik bir özet yaz:\n\n"
            f"{stats_text}"
        )
        try:
            return await self.generate(prompt, system)
        except Exception as exc:  # noqa: BLE001
            return f"AI özeti şu an üretilemedi: {exc}"


ai_service = AIService()
