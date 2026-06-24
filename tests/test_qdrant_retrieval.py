from __future__ import annotations

import asyncio
from typing import Any

import pytest
from qdrant_client.http import models

from packages.domain.retrieval import RetrievedChunk, Source
from packages.rag.qdrant_client import QdrantRagClient


class FakeEmbedder:
    def __init__(self) -> None:
        self.texts: list[str] = []

    async def embed(self, text: str) -> list[float]:
        self.texts.append(text)
        return [0.1, 0.2, 0.3]


class FakeQdrantClient:
    def __init__(
        self,
        points: list[models.ScoredPoint],
        *,
        collection_exists: bool = True,
    ) -> None:
        self.points = points
        self._collection_exists = collection_exists
        self.query_kwargs: dict[str, Any] | None = None

    def collection_exists(self, collection_name: str) -> bool:
        return self._collection_exists

    def create_collection(self, **kwargs: Any) -> None:
        return None

    def upsert(self, **kwargs: Any) -> None:
        return None

    def query_points(self, **kwargs: Any) -> models.QueryResponse:
        self.query_kwargs = kwargs
        return models.QueryResponse(points=self.points)


def test_search_embeds_query_and_maps_qdrant_points() -> None:
    embedder = FakeEmbedder()
    qdrant = FakeQdrantClient(
        [
            models.ScoredPoint(
                id="chunk-1",
                version=1,
                score=0.92,
                payload={
                    "text": "conteudo recuperado",
                    "file_path": "data/inbox/status.md",
                    "chunk_index": 3,
                    "document_id": "doc-1",
                },
            )
        ]
    )
    client = QdrantRagClient(
        url="http://qdrant.test",
        collection_name="docs",
        embedder=embedder,
        score_threshold=0.5,
        client=qdrant,
    )

    chunks = asyncio.run(client.search("qual e o status?", limit=4))

    assert embedder.texts == ["qual e o status?"]
    assert qdrant.query_kwargs == {
        "collection_name": "docs",
        "query": [0.1, 0.2, 0.3],
        "limit": 4,
        "with_payload": True,
        "with_vectors": False,
        "score_threshold": 0.5,
    }
    assert chunks == [
        RetrievedChunk(
            text="conteudo recuperado",
            source=Source(
                chunk_id="chunk-1",
                document_id="doc-1",
                file_path="data/inbox/status.md",
                chunk_index=3,
                score=0.92,
            ),
        )
    ]


def test_search_ignores_points_without_required_payload() -> None:
    embedder = FakeEmbedder()
    qdrant = FakeQdrantClient(
        [
            models.ScoredPoint(
                id="missing-text",
                version=1,
                score=0.8,
                payload={
                    "file_path": "data/inbox/status.md",
                    "chunk_index": 0,
                },
            ),
            models.ScoredPoint(
                id="invalid-index",
                version=1,
                score=0.7,
                payload={
                    "text": "texto",
                    "file_path": "data/inbox/status.md",
                    "chunk_index": "0",
                },
            ),
            models.ScoredPoint(
                id="valid",
                version=1,
                score=0.6,
                payload={
                    "text": "texto valido",
                    "file_path": "data/inbox/status.md",
                    "chunk_index": 1,
                    "document_id": 123,
                },
            ),
        ]
    )
    client = QdrantRagClient(
        url="http://qdrant.test",
        collection_name="docs",
        embedder=embedder,
        client=qdrant,
    )

    chunks = asyncio.run(client.search("status", limit=3))

    assert chunks == [
        RetrievedChunk(
            text="texto valido",
            source=Source(
                chunk_id="valid",
                document_id=None,
                file_path="data/inbox/status.md",
                chunk_index=1,
                score=0.6,
            ),
        )
    ]


def test_search_rejects_invalid_limit() -> None:
    client = QdrantRagClient(
        url="http://qdrant.test",
        collection_name="docs",
        embedder=FakeEmbedder(),
        client=FakeQdrantClient([]),
    )

    with pytest.raises(ValueError, match="limit"):
        asyncio.run(client.search("status", limit=0))


def test_search_ignores_blank_query_without_external_calls() -> None:
    embedder = FakeEmbedder()
    qdrant = FakeQdrantClient([])
    client = QdrantRagClient(
        url="http://qdrant.test",
        collection_name="docs",
        embedder=embedder,
        client=qdrant,
    )

    assert asyncio.run(client.search("  \n", limit=3)) == []
    assert embedder.texts == []
    assert qdrant.query_kwargs is None


def test_search_returns_empty_when_collection_is_missing() -> None:
    embedder = FakeEmbedder()
    qdrant = FakeQdrantClient([], collection_exists=False)
    client = QdrantRagClient(
        url="http://qdrant.test",
        collection_name="docs",
        embedder=embedder,
        client=qdrant,
    )

    assert asyncio.run(client.search("status", limit=3)) == []
    assert embedder.texts == []
    assert qdrant.query_kwargs is None
