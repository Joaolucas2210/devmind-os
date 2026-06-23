from __future__ import annotations

from typing import Protocol

from packages.domain.retrieval import RetrievedChunk


class Retriever(Protocol):
    async def search(self, query: str, *, limit: int) -> list[RetrievedChunk]: ...
