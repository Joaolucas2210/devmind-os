from __future__ import annotations

import httpx
from fastapi.testclient import TestClient

from apps.api import main


def test_ask_returns_generated_answer(monkeypatch) -> None:
    class FakeOllamaClient:
        async def generate(self, prompt: str) -> str:
            assert "qual e o status?" in prompt
            return "ok"

    monkeypatch.setattr(main, "OllamaClient", FakeOllamaClient)

    response = TestClient(main.app).post("/ask", json={"question": "qual e o status?"})

    assert response.status_code == 200
    assert response.json() == {"answer": "ok"}


def test_ask_maps_ollama_connect_error_to_503(monkeypatch) -> None:
    class FakeOllamaClient:
        async def generate(self, _prompt: str) -> str:
            request = httpx.Request("POST", "http://localhost:11434/api/generate")
            raise httpx.ConnectError("connection refused", request=request)

    monkeypatch.setattr(main, "OllamaClient", FakeOllamaClient)

    response = TestClient(main.app).post("/ask", json={"question": "pergunta"})

    assert response.status_code == 503
    assert "Ollama indisponivel" in response.json()["detail"]


def test_ask_maps_ollama_http_error_to_502(monkeypatch) -> None:
    class FakeOllamaClient:
        async def generate(self, _prompt: str) -> str:
            request = httpx.Request("POST", "http://localhost:11434/api/generate")
            response = httpx.Response(404, request=request, text="model not found")
            raise httpx.HTTPStatusError("not found", request=request, response=response)

    monkeypatch.setattr(main, "OllamaClient", FakeOllamaClient)

    response = TestClient(main.app).post("/ask", json={"question": "pergunta"})

    assert response.status_code == 502
    assert "OLLAMA_CHAT_MODEL" in response.json()["detail"]
