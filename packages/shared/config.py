from __future__ import annotations

from functools import lru_cache
from typing import Self

from pydantic import AnyHttpUrl, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        case_sensitive=False,
        extra="ignore",
    )

    app_env: str = Field(default="local", min_length=1)
    api_base_url: AnyHttpUrl = AnyHttpUrl("http://localhost:8000")
    ollama_base_url: AnyHttpUrl = AnyHttpUrl("http://localhost:11434")
    ollama_chat_model: str = Field(default="llama3.2:1b", min_length=1)
    ollama_embed_model: str = Field(default="nomic-embed-text", min_length=1)
    qdrant_url: AnyHttpUrl = AnyHttpUrl("http://localhost:6333")
    qdrant_collection: str = Field(default="devmind_documents", min_length=1)
    rag_chunk_size: int = Field(default=1000, gt=0)
    rag_chunk_overlap: int = Field(default=100, ge=0)
    postgres_dsn: str = "postgresql://devmind:devmind@localhost:5433/devmind"

    @model_validator(mode="after")
    def validate_chunking(self) -> Self:
        if self.rag_chunk_overlap >= self.rag_chunk_size:
            raise ValueError("RAG_CHUNK_OVERLAP must be smaller than RAG_CHUNK_SIZE")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
