from __future__ import annotations

from typing import cast

from fastapi import Request

from packages.application.answer_question import Generator
from packages.shared.config import Settings
from packages.shared.ollama_client import OllamaClient


def build_generator(settings: Settings) -> Generator:
    return OllamaClient(
        base_url=str(settings.ollama_base_url).rstrip("/"),
        chat_model=settings.ollama_chat_model,
        embed_model=settings.ollama_embed_model,
    )


def get_generator(request: Request) -> Generator:
    return cast(Generator, request.app.state.generator)
