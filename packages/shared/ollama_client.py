from typing import Any

import httpx

from packages.shared.config import get_settings


class OllamaClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        chat_model: str | None = None,
        embed_model: str | None = None,
    ) -> None:
        if base_url is None:
            base_url = str(get_settings().ollama_base_url).rstrip("/")
        if chat_model is None:
            chat_model = get_settings().ollama_chat_model
        if embed_model is None:
            embed_model = get_settings().ollama_embed_model

        self.base_url = base_url
        self.chat_model = chat_model
        self.embed_model = embed_model

    async def generate(self, prompt: str) -> str:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.chat_model,
                    "prompt": prompt,
                    "stream": False,
                },
            )
            response.raise_for_status()
            data: dict[str, Any] = response.json()
            return str(data.get("response", ""))

    async def embed(self, text: str) -> list[float]:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{self.base_url}/api/embeddings",
                json={
                    "model": self.embed_model,
                    "prompt": text,
                },
            )
            response.raise_for_status()
            data: dict[str, Any] = response.json()
            return list(data["embedding"])
