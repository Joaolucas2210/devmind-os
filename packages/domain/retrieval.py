from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Source:
    chunk_id: str
    file_path: str
    chunk_index: int
    score: float
    document_id: str | None = None


@dataclass(frozen=True)
class RetrievedChunk:
    text: str
    source: Source
