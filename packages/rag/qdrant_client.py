from __future__ import annotations

from dataclasses import dataclass

from qdrant_client import QdrantClient
from qdrant_client.http import models

from packages.shared.config import get_settings

DEFAULT_COLLECTION_NAME = "devmind_documents"
DEFAULT_QDRANT_URL = "http://localhost:6333"


@dataclass(frozen=True)
class EmbeddedChunk:
    id: str
    text: str
    vector: list[float]
    metadata: dict[str, str | int]


class QdrantRagClient:
    def __init__(
        self,
        *,
        url: str | None = None,
        collection_name: str | None = None,
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
        self._client = QdrantClient(url=effective_url.rstrip("/"))

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
