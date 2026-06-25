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

    def delete(self, **kwargs: Any) -> Any: ...

    def query_points(self, **kwargs: Any) -> models.QueryResponse: ...

    def scroll(self, **kwargs: Any) -> tuple[list[models.Record], Any]: ...


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
        self.delete_file_paths(_file_paths(chunks))
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

    def delete_missing_file_paths(
        self,
        active_file_paths: set[str],
        *,
        path_prefix: str,
    ) -> int:
        if not self._client.collection_exists(self.collection_name):
            return 0

        indexed_file_paths = self._indexed_file_paths(path_prefix=path_prefix)
        return self.delete_file_paths(indexed_file_paths - active_file_paths)

    def delete_file_paths(self, file_paths: set[str]) -> int:
        for file_path in sorted(file_paths):
            self._client.delete(
                collection_name=self.collection_name,
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="file_path",
                                match=models.MatchValue(value=file_path),
                            )
                        ]
                    )
                ),
                wait=True,
            )
        return len(file_paths)

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

    def _indexed_file_paths(self, *, path_prefix: str) -> set[str]:
        file_paths: set[str] = set()
        offset: Any = None
        while True:
            # ponytail: O(n) payload scan; replace with a catalog table when Postgres lifecycle lands.
            records, offset = self._client.scroll(
                collection_name=self.collection_name,
                limit=100,
                offset=offset,
                with_payload=["file_path"],
                with_vectors=False,
            )
            for record in records:
                payload = record.payload or {}
                file_path = payload.get("file_path")
                if isinstance(file_path, str) and file_path.startswith(path_prefix):
                    file_paths.add(file_path)
            if offset is None:
                return file_paths


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


def _file_paths(chunks: list[EmbeddedChunk]) -> set[str]:
    return {
        file_path
        for chunk in chunks
        if isinstance(file_path := chunk.metadata.get("file_path"), str)
    }
