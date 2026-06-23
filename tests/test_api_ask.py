from __future__ import annotations

import httpx
from fastapi.testclient import TestClient

from apps.api.main import create_app


def test_ask_returns_generated_answer() -> None:
    class FakeOllamaClient:
        async def generate(self, prompt: str) -> str:
            assert "qual e o status?" in prompt
            return "ok"

    response = TestClient(create_app(generator=FakeOllamaClient())).post(
        "/ask",
        json={"question": "qual e o status?"},
    )

    assert response.status_code == 200
    assert response.json() == {"answer": "ok"}


def test_ask_maps_ollama_connect_error_to_503() -> None:
    class FakeOllamaClient:
        async def generate(self, _prompt: str) -> str:
            request = httpx.Request("POST", "http://localhost:11434/api/generate")
            raise httpx.ConnectError("connection refused", request=request)

    response = TestClient(create_app(generator=FakeOllamaClient())).post(
        "/ask",
        json={"question": "pergunta"},
    )

    assert response.status_code == 503
    assert "Ollama indisponivel" in response.json()["detail"]


def test_ask_maps_ollama_http_error_to_502() -> None:
    class FakeOllamaClient:
        async def generate(self, _prompt: str) -> str:
            request = httpx.Request("POST", "http://localhost:11434/api/generate")
            response = httpx.Response(404, request=request, text="model not found")
            raise httpx.HTTPStatusError("not found", request=request, response=response)

    response = TestClient(create_app(generator=FakeOllamaClient())).post(
        "/ask",
        json={"question": "pergunta"},
    )

    assert response.status_code == 502
    assert "OLLAMA_CHAT_MODEL" in response.json()["detail"]


def test_create_app_preserves_health_contract() -> None:
    class FakeOllamaClient:
        async def generate(self, _prompt: str) -> str:
            return "ok"

    response = TestClient(create_app(generator=FakeOllamaClient())).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
