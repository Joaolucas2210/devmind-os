from __future__ import annotations

import asyncio
from typing import Any

import pytest
from qdrant_client.http import models

from packages.domain.retrieval import RetrievedChunk, Source
from packages.rag.qdrant_client import EmbeddedChunk, QdrantRagClient


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
        records: list[models.Record] | None = None,
    ) -> None:
        self.points = points
        self.records = records or []
        self._collection_exists = collection_exists
        self.delete_kwargs: list[dict[str, Any]] = []
        self.upsert_kwargs: dict[str, Any] | None = None
        self.query_kwargs: dict[str, Any] | None = None
        self.scroll_kwargs: list[dict[str, Any]] = []

    def collection_exists(self, collection_name: str) -> bool:
        return self._collection_exists

    def create_collection(self, **kwargs: Any) -> None:
        return None

    def upsert(self, **kwargs: Any) -> None:
        self.upsert_kwargs = kwargs
        return None

    def delete(self, **kwargs: Any) -> None:
        self.delete_kwargs.append(kwargs)
        return None

    def query_points(self, **kwargs: Any) -> models.QueryResponse:
        self.query_kwargs = kwargs
        return models.QueryResponse(points=self.points)

    def scroll(self, **kwargs: Any) -> tuple[list[models.Record], None]:
        self.scroll_kwargs.append(kwargs)
        return self.records, None


def test_upsert_chunks_replaces_existing_chunks_for_file_path() -> None:
    qdrant = FakeQdrantClient([])
    client = QdrantRagClient(
        url="http://qdrant.test",
        collection_name="docs",
        client=qdrant,
    )

    count = client.upsert_chunks(
        [
            EmbeddedChunk(
                id="chunk-0",
                text="novo",
                vector=[0.1, 0.2],
                metadata={
                    "file_path": "data/inbox/status.md",
                    "file_name": "status.md",
                    "chunk_index": 0,
                },
            )
        ]
    )

    assert count == 1
    assert len(qdrant.delete_kwargs) == 1
    assert qdrant.delete_kwargs[0]["collection_name"] == "docs"
    assert qdrant.delete_kwargs[0]["wait"] is True
    assert qdrant.delete_kwargs[0]["points_selector"] == models.FilterSelector(
        filter=models.Filter(
            must=[
                models.FieldCondition(
                    key="file_path",
                    match=models.MatchValue(value="data/inbox/status.md"),
                )
            ]
        )
    )
    assert qdrant.upsert_kwargs is not None


def test_delete_missing_file_paths_removes_indexed_paths_not_seen_in_scope() -> None:
    qdrant = FakeQdrantClient(
        [],
        records=[
            models.Record(
                id="stale",
                payload={"file_path": "data/inbox/deleted.md"},
            ),
            models.Record(
                id="active",
                payload={"file_path": "data/inbox/active.md"},
            ),
            models.Record(
                id="sample",
                payload={"file_path": "data/samples/keep.md"},
            ),
        ],
    )
    client = QdrantRagClient(
        url="http://qdrant.test",
        collection_name="docs",
        client=qdrant,
    )

    count = client.delete_missing_file_paths(
        {"data/inbox/active.md"},
        path_prefix="data/inbox/",
    )

    assert count == 1
    assert qdrant.scroll_kwargs == [
        {
            "collection_name": "docs",
            "limit": 100,
            "offset": None,
            "with_payload": ["file_path"],
            "with_vectors": False,
        }
    ]
    assert len(qdrant.delete_kwargs) == 1
    assert qdrant.delete_kwargs[0]["points_selector"] == models.FilterSelector(
        filter=models.Filter(
            must=[
                models.FieldCondition(
                    key="file_path",
                    match=models.MatchValue(value="data/inbox/deleted.md"),
                )
            ]
        )
    )


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
