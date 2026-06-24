from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

import httpx
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.rag.evaluation import (  # noqa: E402
    RetrievalEvalCase,
    RetrievalEvaluationReport,
    evaluate_retrieval,
    load_retrieval_eval_cases,
)
from packages.rag.qdrant_client import QdrantRagClient  # noqa: E402
from packages.shared.config import get_settings  # noqa: E402
from packages.shared.ollama_client import OllamaClient  # noqa: E402

DEFAULT_DATASET = REPO_ROOT / "data" / "evaluation" / "retrieval-baseline.json"


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    dataset_path = args.dataset.resolve()

    try:
        cases = load_retrieval_eval_cases(dataset_path)
        report = asyncio.run(_evaluate(cases, top_k=args.top_k))
    except (OSError, ValueError) as exc:
        print(f"Falha na avaliacao de retrieval: {exc}", file=sys.stderr)
        return 2
    except (
        httpx.HTTPError,
        ResponseHandlingException,
        UnexpectedResponse,
    ) as exc:
        print(f"Falha ao consultar dependencias de retrieval: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    return 0


async def _evaluate(
    cases: list[RetrievalEvalCase],
    *,
    top_k: int,
) -> RetrievalEvaluationReport:
    settings = get_settings()
    ollama = OllamaClient(
        base_url=str(settings.ollama_base_url).rstrip("/"),
        chat_model=settings.ollama_chat_model,
        embed_model=settings.ollama_embed_model,
    )
    retriever = QdrantRagClient(
        url=str(settings.qdrant_url).rstrip("/"),
        collection_name=settings.qdrant_collection,
        embedder=ollama,
    )
    return await evaluate_retrieval(retriever, cases, top_k=top_k)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate retrieval quality against a JSON dataset.",
    )
    parser.add_argument(
        "dataset",
        nargs="?",
        type=Path,
        default=DEFAULT_DATASET,
        help=f"dataset path, default: {DEFAULT_DATASET.relative_to(REPO_ROOT)}",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=4,
        help="number of chunks to retrieve for each question",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
