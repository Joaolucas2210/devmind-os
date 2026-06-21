from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

from apps.worker import ingest
from packages.rag.qdrant_client import EmbeddedChunk


class FakeEmbedder:
    def __init__(self) -> None:
        self.texts: list[str] = []

    async def embed(self, text: str) -> list[float]:
        self.texts.append(text)
        return [float(len(text)), 1.0]


class FakeQdrantClient:
    def __init__(self) -> None:
        self.chunks: list[EmbeddedChunk] = []

    def upsert_chunks(self, chunks: list[EmbeddedChunk]) -> int:
        self.chunks = chunks
        return len(chunks)


def test_ingest_inbox_embeds_supported_documents_with_metadata(
    tmp_path: Path,
    monkeypatch,
) -> None:
    inbox_dir = tmp_path / "data" / "inbox"
    nested_dir = inbox_dir / "notes"
    nested_dir.mkdir(parents=True)
    document = nested_dir / "status.md"
    document.write_text("alpha beta gamma", encoding="utf-8")
    (inbox_dir / "empty.txt").write_text("  \n", encoding="utf-8")
    (inbox_dir / "ignored.json").write_text('{"ignored": true}', encoding="utf-8")

    embedder = FakeEmbedder()
    qdrant = FakeQdrantClient()
    monkeypatch.setattr(ingest, "REPO_ROOT", tmp_path)

    summary = asyncio.run(
        ingest.ingest_inbox(
            inbox_dir,
            chunk_size=10,
            chunk_overlap=0,
            embedder=embedder,
            qdrant_client=qdrant,
        )
    )

    assert summary == ingest.IngestSummary(
        files_seen=2,
        files_ingested=1,
        chunks_ingested=2,
    )
    assert embedder.texts == ["alpha", "beta gamma"]
    assert [chunk.text for chunk in qdrant.chunks] == embedder.texts
    assert [chunk.metadata for chunk in qdrant.chunks] == [
        {
            "file_path": "data/inbox/notes/status.md",
            "file_name": "status.md",
            "chunk_index": 0,
        },
        {
            "file_path": "data/inbox/notes/status.md",
            "file_name": "status.md",
            "chunk_index": 1,
        },
    ]
    assert [chunk.id for chunk in qdrant.chunks] == [
        str(uuid.uuid5(uuid.NAMESPACE_URL, "data/inbox/notes/status.md:0")),
        str(uuid.uuid5(uuid.NAMESPACE_URL, "data/inbox/notes/status.md:1")),
    ]


def test_ingest_inbox_handles_missing_directory(tmp_path: Path) -> None:
    embedder = FakeEmbedder()
    qdrant = FakeQdrantClient()

    summary = asyncio.run(
        ingest.ingest_inbox(
            tmp_path / "missing",
            embedder=embedder,
            qdrant_client=qdrant,
        )
    )

    assert summary == ingest.IngestSummary(0, 0, 0)
    assert embedder.texts == []
    assert qdrant.chunks == []
