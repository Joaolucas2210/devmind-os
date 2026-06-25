from __future__ import annotations

import asyncio
import hashlib
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.rag.chunking import chunk_text  # noqa: E402
from packages.rag.qdrant_client import EmbeddedChunk, QdrantRagClient  # noqa: E402
from packages.shared.config import Settings, get_settings  # noqa: E402
from packages.shared.ollama_client import OllamaClient  # noqa: E402

DEFAULT_INBOX_DIR = REPO_ROOT / "data" / "inbox"
SUPPORTED_EXTENSIONS = {".md", ".markdown", ".txt"}


class Embedder(Protocol):
    async def embed(self, text: str) -> list[float]: ...


class ChunkStore(Protocol):
    def upsert_chunks(self, chunks: list[EmbeddedChunk]) -> int: ...

    def delete_missing_file_paths(
        self,
        active_file_paths: set[str],
        *,
        path_prefix: str,
    ) -> int: ...


@dataclass(frozen=True)
class IngestSummary:
    files_seen: int
    files_ingested: int
    chunks_ingested: int


async def ingest_inbox(
    inbox_dir: Path = DEFAULT_INBOX_DIR,
    *,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
    embedder: Embedder | None = None,
    qdrant_client: ChunkStore | None = None,
    settings: Settings | None = None,
) -> IngestSummary:
    effective_settings = settings or get_settings()
    effective_chunk_size = (
        chunk_size
        if chunk_size is not None
        else effective_settings.rag_chunk_size
    )
    effective_chunk_overlap = (
        chunk_overlap
        if chunk_overlap is not None
        else effective_settings.rag_chunk_overlap
    )

    documents = list(_iter_documents(inbox_dir))
    ollama = embedder or OllamaClient(
        base_url=str(effective_settings.ollama_base_url).rstrip("/"),
        chat_model=effective_settings.ollama_chat_model,
        embed_model=effective_settings.ollama_embed_model,
    )
    qdrant = qdrant_client or QdrantRagClient(
        url=str(effective_settings.qdrant_url).rstrip("/"),
        collection_name=effective_settings.qdrant_collection,
    )

    embedded_chunks: list[EmbeddedChunk] = []
    active_file_paths: set[str] = set()
    files_ingested = 0

    for path in documents:
        file_path = _relative_file_path(path)
        text = path.read_text(encoding="utf-8")
        chunks = chunk_text(
            text,
            chunk_size=effective_chunk_size,
            chunk_overlap=effective_chunk_overlap,
        )
        if not chunks:
            continue

        files_ingested += 1
        active_file_paths.add(file_path)
        document_id = _document_id(file_path)
        content_hash = _content_hash(text)
        document_version_id = _document_version_id(document_id, content_hash)
        for chunk_index, chunk in enumerate(chunks):
            embedded_chunks.append(
                EmbeddedChunk(
                    id=_point_id(file_path, chunk_index),
                    text=chunk,
                    vector=await ollama.embed(chunk),
                    metadata={
                        "file_path": file_path,
                        "file_name": path.name,
                        "chunk_index": chunk_index,
                        "document_id": document_id,
                        "content_hash": content_hash,
                        "document_version_id": document_version_id,
                    },
                )
            )

    chunks_ingested = qdrant.upsert_chunks(embedded_chunks)
    qdrant.delete_missing_file_paths(
        active_file_paths,
        path_prefix=_path_prefix(inbox_dir),
    )
    return IngestSummary(
        files_seen=len(documents),
        files_ingested=files_ingested,
        chunks_ingested=chunks_ingested,
    )


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    inbox_dir = Path(args[0]).resolve() if args else DEFAULT_INBOX_DIR

    try:
        summary = asyncio.run(ingest_inbox(inbox_dir))
    except OSError as exc:
        print(f"Erro ao ler documentos: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    print(
        "Ingestao concluida: "
        f"{summary.files_ingested}/{summary.files_seen} arquivos, "
        f"{summary.chunks_ingested} chunks."
    )
    return 0


def _iter_documents(inbox_dir: Path) -> list[Path]:
    if not inbox_dir.exists():
        return []
    return sorted(
        path
        for path in inbox_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    )


def _relative_file_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def _path_prefix(path: Path) -> str:
    prefix = _relative_file_path(path.resolve())
    return f"{prefix.rstrip('/')}/" if prefix else ""


def _point_id(file_path: str, chunk_index: int) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{file_path}:{chunk_index}"))


def _document_id(file_path: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"document:{file_path}"))


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _document_version_id(document_id: str, content_hash: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{document_id}:{content_hash}"))


if __name__ == "__main__":
    raise SystemExit(main())
