from __future__ import annotations

import pytest
from pydantic import ValidationError

from packages.shared.config import Settings


def test_settings_load_environment_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_CHAT_MODEL", "test-model")
    monkeypatch.setenv("RAG_CHUNK_SIZE", "200")
    monkeypatch.setenv("RAG_CHUNK_OVERLAP", "20")

    settings = Settings()

    assert settings.ollama_chat_model == "test-model"
    assert settings.rag_chunk_size == 200
    assert settings.rag_chunk_overlap == 20


def test_settings_reject_invalid_chunk_overlap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RAG_CHUNK_SIZE", "100")
    monkeypatch.setenv("RAG_CHUNK_OVERLAP", "100")

    with pytest.raises(ValidationError, match="RAG_CHUNK_OVERLAP"):
        Settings()


def test_settings_reject_invalid_service_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OLLAMA_BASE_URL", "not-a-url")

    with pytest.raises(ValidationError, match="ollama_base_url"):
        Settings()
