from __future__ import annotations

import asyncio

from packages.application.answer_question import AnswerQuestion
from packages.domain.retrieval import RetrievedChunk, Source


class FakeGenerator:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return "resposta com base no contexto"


class FakeRetriever:
    def __init__(self, chunks: list[RetrievedChunk]) -> None:
        self.chunks = chunks
        self.queries: list[tuple[str, int]] = []

    async def search(self, query: str, *, limit: int) -> list[RetrievedChunk]:
        self.queries.append((query, limit))
        return self.chunks


def test_answer_question_uses_retrieved_context_and_sources() -> None:
    source = Source(
        chunk_id="chunk-1",
        document_id="doc-1",
        file_path="data/inbox/status.md",
        chunk_index=0,
        score=0.91,
    )
    generator = FakeGenerator()
    retriever = FakeRetriever(
        [RetrievedChunk(text="O projeto esta em MVP.", source=source)]
    )

    result = asyncio.run(
        AnswerQuestion(generator, retriever, top_k=2).execute("qual e o status?")
    )

    assert retriever.queries == [("qual e o status?", 2)]
    assert generator.prompts == [
        (
            "Voce responde perguntas copiando apenas informacoes do contexto.\n\n"
            "Contexto:\n"
            "[1] data/inbox/status.md#chunk-0\n"
            "O projeto esta em MVP.\n\n"
            "Pergunta:\n"
            "qual e o status?"
            "\nResposta direta:"
        )
    ]
    assert result.answer == "resposta com base no contexto"
    assert result.sources == [source]


def test_answer_question_falls_back_without_context() -> None:
    generator = FakeGenerator()
    retriever = FakeRetriever([])

    result = asyncio.run(AnswerQuestion(generator, retriever).execute("pergunta"))

    assert result.answer == (
        "Nao encontrei contexto suficiente nos documentos indexados para responder."
    )
    assert result.sources == []
    assert generator.prompts == []
