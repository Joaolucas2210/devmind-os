from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from qdrant_client import QdrantClient
from qdrant_client.http import models

from packages.domain.retrieval import RetrievedChunk, Source
from packages.shared.config import get_settings
from packages.shared.ollama_client import OllamaClient

DEFAULT_COLLECTION_NAME = "devmind_documents"
DEFAULT_QDRANT_URL = "http://localhost:6333"


@dataclass(frozen=True)
class EmbeddedChunk:
    id: str
    text: str
    vector: list[float]
    metadata: dict[str, str | int]


class QueryEmbedder(Protocol):
    async def embed(self, text: str) -> list[float]: ...


class QdrantClientProtocol(Protocol):
    def collection_exists(self, collection_name: str) -> bool: ...

    def create_collection(self, **kwargs: Any) -> Any: ...

    def upsert(self, **kwargs: Any) -> Any: ...

    def query_points(self, **kwargs: Any) -> models.QueryResponse: ...


class QdrantRagClient:
    def __init__(
        self,
        *,
        url: str | None = None,
        collection_name: str | None = None,
        embedder: QueryEmbedder | None = None,
        score_threshold: float | None = None,
        client: QdrantClientProtocol | None = None,
    ) -> None:
        settings = get_settings() if url is None or collection_name is None else None
        self.collection_name = (
            collection_name
            or (settings.qdrant_collection if settings is not None else None)
            or DEFAULT_COLLECTION_NAME
        )
        effective_url = (
            url
            or (str(settings.qdrant_url) if settings is not None else None)
            or DEFAULT_QDRANT_URL
        )
        self._client = client or QdrantClient(url=effective_url.rstrip("/"))
        self._embedder = embedder
        self._score_threshold = score_threshold

    def ensure_collection(self, vector_size: int) -> None:
        if vector_size <= 0:
            raise ValueError("vector_size must be greater than zero")
        if self._client.collection_exists(self.collection_name):
            return

        self._client.create_collection(
            collection_name=self.collection_name,
            vectors_config=models.VectorParams(
                size=vector_size,
                distance=models.Distance.COSINE,
            ),
        )

    def upsert_chunks(self, chunks: list[EmbeddedChunk]) -> int:
        if not chunks:
            return 0

        self.ensure_collection(len(chunks[0].vector))
        points = [
            models.PointStruct(
                id=chunk.id,
                vector=chunk.vector,
                payload={
                    "text": chunk.text,
                    **chunk.metadata,
                },
            )
            for chunk in chunks
        ]
        self._client.upsert(
            collection_name=self.collection_name,
            points=points,
        )
        return len(points)

    async def search(self, query: str, *, limit: int) -> list[RetrievedChunk]:
        if limit <= 0:
            raise ValueError("limit must be greater than zero")
        if not query.strip():
            return []
        if not self._client.collection_exists(self.collection_name):
            return []

        query_vector = await self._get_embedder().embed(query)
        response = self._client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=limit,
            with_payload=True,
            with_vectors=False,
            score_threshold=self._score_threshold,
        )
        return [
            chunk
            for point in response.points
            if (chunk := _retrieved_chunk_from_point(point)) is not None
        ]

    def _get_embedder(self) -> QueryEmbedder:
        if self._embedder is None:
            self._embedder = OllamaClient()
        return self._embedder


def _retrieved_chunk_from_point(point: models.ScoredPoint) -> RetrievedChunk | None:
    payload = point.payload or {}
    text = payload.get("text")
    file_path = payload.get("file_path")
    chunk_index = payload.get("chunk_index")
    document_id = payload.get("document_id")

    if (
        not isinstance(text, str)
        or not isinstance(file_path, str)
        or not isinstance(chunk_index, int)
    ):
        return None
    if document_id is not None and not isinstance(document_id, str):
        document_id = None

    return RetrievedChunk(
        text=text,
        source=Source(
            chunk_id=str(point.id),
            document_id=document_id,
            file_path=file_path,
            chunk_index=chunk_index,
            score=float(point.score),
        ),
    )
