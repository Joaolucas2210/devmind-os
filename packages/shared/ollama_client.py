import os
from typing import Any

import httpx


class OllamaClient:
    def __init__(self) -> None:
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.chat_model = os.getenv("OLLAMA_CHAT_MODEL", "llama3.2:1b")
        self.embed_model = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")

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
