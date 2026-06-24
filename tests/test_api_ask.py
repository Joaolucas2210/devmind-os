from __future__ import annotations

import httpx
from fastapi.testclient import TestClient
from qdrant_client.http.exceptions import ResponseHandlingException

from apps.api.main import create_app
from packages.domain.retrieval import RetrievedChunk, Source


class FakeRetriever:
    async def search(self, _query: str, *, limit: int) -> list[RetrievedChunk]:
        assert limit == 4
        return [
            RetrievedChunk(
                text="conteudo recuperado",
                source=Source(
                    chunk_id="chunk-1",
                    document_id="doc-1",
                    file_path="data/inbox/status.md",
                    chunk_index=0,
                    score=0.91,
                ),
            )
        ]


def test_ask_returns_generated_answer() -> None:
    class FakeOllamaClient:
        async def generate(self, prompt: str) -> str:
            assert "qual e o status?" in prompt
            assert "conteudo recuperado" in prompt
            return "ok"

    response = TestClient(
        create_app(generator=FakeOllamaClient(), retriever=FakeRetriever())
    ).post(
        "/ask",
        json={"question": "qual e o status?"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "answer": "ok",
        "sources": [
            {
                "chunk_id": "chunk-1",
                "document_id": "doc-1",
                "file_path": "data/inbox/status.md",
                "chunk_index": 0,
                "score": 0.91,
            }
        ],
    }


def test_ask_returns_fallback_without_sources_when_context_is_missing() -> None:
    class FakeOllamaClient:
        async def generate(self, _prompt: str) -> str:
            raise AssertionError("generator should not be called")

    class EmptyRetriever:
        async def search(self, _query: str, *, limit: int) -> list[RetrievedChunk]:
            return []

    response = TestClient(
        create_app(generator=FakeOllamaClient(), retriever=EmptyRetriever())
    ).post(
        "/ask",
        json={"question": "pergunta"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "answer": (
            "Nao encontrei contexto suficiente nos documentos indexados para "
            "responder."
        ),
        "sources": [],
    }


def test_ask_maps_ollama_connect_error_to_503() -> None:
    class FakeOllamaClient:
        async def generate(self, _prompt: str) -> str:
            request = httpx.Request("POST", "http://localhost:11434/api/generate")
            raise httpx.ConnectError("connection refused", request=request)

    response = TestClient(
        create_app(generator=FakeOllamaClient(), retriever=FakeRetriever())
    ).post(
        "/ask",
        json={"question": "pergunta"},
    )

    assert response.status_code == 503
    assert "Ollama indisponivel" in response.json()["detail"]


def test_ask_maps_qdrant_error_to_503() -> None:
    class FakeOllamaClient:
        async def generate(self, _prompt: str) -> str:
            raise AssertionError("generator should not be called")

    class BrokenRetriever:
        async def search(self, _query: str, *, limit: int) -> list[RetrievedChunk]:
            raise ResponseHandlingException(Exception("connection refused"))

    response = TestClient(
        create_app(generator=FakeOllamaClient(), retriever=BrokenRetriever())
    ).post(
        "/ask",
        json={"question": "pergunta"},
    )

    assert response.status_code == 503
    assert "Qdrant indisponivel" in response.json()["detail"]


def test_ask_maps_ollama_http_error_to_502() -> None:
    class FakeOllamaClient:
        async def generate(self, _prompt: str) -> str:
            request = httpx.Request("POST", "http://localhost:11434/api/generate")
            response = httpx.Response(404, request=request, text="model not found")
            raise httpx.HTTPStatusError("not found", request=request, response=response)

    response = TestClient(
        create_app(generator=FakeOllamaClient(), retriever=FakeRetriever())
    ).post(
        "/ask",
        json={"question": "pergunta"},
    )

    assert response.status_code == 502
    assert "OLLAMA_CHAT_MODEL" in response.json()["detail"]


def test_create_app_preserves_health_contract() -> None:
    class FakeOllamaClient:
        async def generate(self, _prompt: str) -> str:
            return "ok"

    response = TestClient(
        create_app(generator=FakeOllamaClient(), retriever=FakeRetriever())
    ).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
