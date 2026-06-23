from __future__ import annotations

from typing import Protocol


class Generator(Protocol):
    async def generate(self, prompt: str) -> str: ...


class AnswerQuestion:
    def __init__(self, generator: Generator) -> None:
        self._generator = generator

    async def execute(self, question: str) -> str:
        prompt = f"Responda de forma objetiva em português:\n\n{question}"
        return await self._generator.generate(prompt)
