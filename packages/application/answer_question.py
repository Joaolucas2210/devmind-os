from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from packages.application.retrieval import Retriever
from packages.domain.retrieval import RetrievedChunk, Source


class Generator(Protocol):
    async def generate(self, prompt: str) -> str: ...


@dataclass(frozen=True)
class AnswerQuestionResult:
    answer: str
    sources: list[Source]


class AnswerQuestion:
    def __init__(
        self,
        generator: Generator,
        retriever: Retriever,
        *,
        top_k: int = 4,
        max_context_chars: int = 4000,
    ) -> None:
        self._generator = generator
        self._retriever = retriever
        self._top_k = top_k
        self._max_context_chars = max_context_chars

    async def execute(self, question: str) -> AnswerQuestionResult:
        chunks = await self._retriever.search(question, limit=self._top_k)
        context, sources = self._context_from_chunks(chunks)
        if not context:
            return AnswerQuestionResult(
                answer=(
                    "Nao encontrei contexto suficiente nos documentos indexados "
                    "para responder."
                ),
                sources=[],
            )

        prompt = (
            "Voce responde perguntas copiando apenas informacoes do contexto.\n\n"
            f"Contexto:\n{context}\n\n"
            f"Pergunta:\n{question}"
            "\nResposta direta:"
        )
        answer = await self._generator.generate(prompt)
        return AnswerQuestionResult(
            answer=answer,
            sources=sources,
        )

    def _context_from_chunks(
        self,
        chunks: list[RetrievedChunk],
    ) -> tuple[str, list[Source]]:
        parts: list[str] = []
        sources: list[Source] = []
        used_chars = 0
        for chunk in chunks:
            text = chunk.text.strip()
            if not text:
                continue
            index = len(parts) + 1
            source = (
                f"[{index}] {chunk.source.file_path}#chunk-{chunk.source.chunk_index}"
            )
            part = f"{source}\n{text}"
            if used_chars + len(part) > self._max_context_chars:
                break
            parts.append(part)
            sources.append(chunk.source)
            used_chars += len(part)
        return "\n\n".join(parts), sources
