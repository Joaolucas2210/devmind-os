from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from packages.application.retrieval import Retriever
from packages.domain.retrieval import Source


@dataclass(frozen=True)
class ExpectedSource:
    file_path: str
    chunk_index: int | None = None
    document_id: str | None = None

    def matches(self, source: Source) -> bool:
        if source.file_path != self.file_path:
            return False
        if self.chunk_index is not None and source.chunk_index != self.chunk_index:
            return False
        if self.document_id is not None and source.document_id != self.document_id:
            return False
        return True


@dataclass(frozen=True)
class RetrievalEvalCase:
    id: str
    question: str
    expected_sources: list[ExpectedSource]
    expected_facts: list[str]


@dataclass(frozen=True)
class RetrievalCaseResult:
    id: str
    hit: bool
    reciprocal_rank: float
    expected_sources: list[ExpectedSource]
    retrieved_sources: list[Source]

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "hit": self.hit,
            "reciprocal_rank": self.reciprocal_rank,
            "expected_sources": [
                {
                    "file_path": source.file_path,
                    "chunk_index": source.chunk_index,
                    "document_id": source.document_id,
                }
                for source in self.expected_sources
            ],
            "retrieved_sources": [
                {
                    "chunk_id": source.chunk_id,
                    "file_path": source.file_path,
                    "chunk_index": source.chunk_index,
                    "score": source.score,
                    "document_id": source.document_id,
                }
                for source in self.retrieved_sources
            ],
        }


@dataclass(frozen=True)
class RetrievalEvaluationReport:
    top_k: int
    total_cases: int
    recall_at_k: float
    mrr: float
    cases: list[RetrievalCaseResult]

    def as_dict(self) -> dict[str, object]:
        return {
            "top_k": self.top_k,
            "total_cases": self.total_cases,
            "recall_at_k": self.recall_at_k,
            "mrr": self.mrr,
            "cases": [case.as_dict() for case in self.cases],
        }


def load_retrieval_eval_cases(path: Path) -> list[RetrievalEvalCase]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid evaluation dataset JSON: {path}") from exc

    if not isinstance(data, dict):
        raise ValueError("evaluation dataset must be a JSON object")

    raw_cases = data.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise ValueError("evaluation dataset must contain at least one case")

    cases: list[RetrievalEvalCase] = []
    for index, raw_case in enumerate(raw_cases):
        if not isinstance(raw_case, dict):
            raise ValueError(f"case at index {index} must be an object")

        case_id = _required_str(raw_case.get("id"), f"cases[{index}].id")
        question = _required_str(raw_case.get("question"), f"{case_id}.question")
        expected_sources = _parse_expected_sources(
            raw_case.get("expected_sources"),
            case_id,
        )
        expected_facts = _parse_string_list(
            raw_case.get("expected_facts", []),
            f"{case_id}.expected_facts",
        )
        cases.append(
            RetrievalEvalCase(
                id=case_id,
                question=question,
                expected_sources=expected_sources,
                expected_facts=expected_facts,
            )
        )
    return cases


async def evaluate_retrieval(
    retriever: Retriever,
    cases: list[RetrievalEvalCase],
    *,
    top_k: int,
) -> RetrievalEvaluationReport:
    if top_k <= 0:
        raise ValueError("top_k must be greater than zero")
    if not cases:
        raise ValueError("cases must not be empty")

    results: list[RetrievalCaseResult] = []
    for case in cases:
        chunks = await retriever.search(case.question, limit=top_k)
        retrieved_sources = [chunk.source for chunk in chunks]
        rank = _first_match_rank(case.expected_sources, retrieved_sources)
        results.append(
            RetrievalCaseResult(
                id=case.id,
                hit=rank is not None,
                reciprocal_rank=0.0 if rank is None else 1.0 / rank,
                expected_sources=case.expected_sources,
                retrieved_sources=retrieved_sources,
            )
        )

    total_cases = len(results)
    return RetrievalEvaluationReport(
        top_k=top_k,
        total_cases=total_cases,
        recall_at_k=sum(1 for result in results if result.hit) / total_cases,
        mrr=sum(result.reciprocal_rank for result in results) / total_cases,
        cases=results,
    )


def _first_match_rank(
    expected_sources: list[ExpectedSource],
    retrieved_sources: list[Source],
) -> int | None:
    for rank, source in enumerate(retrieved_sources, start=1):
        if any(expected.matches(source) for expected in expected_sources):
            return rank
    return None


def _parse_expected_sources(raw_value: object, case_id: str) -> list[ExpectedSource]:
    if not isinstance(raw_value, list) or not raw_value:
        raise ValueError(f"{case_id}.expected_sources must contain at least one source")

    sources: list[ExpectedSource] = []
    for index, raw_source in enumerate(raw_value):
        if not isinstance(raw_source, dict):
            raise ValueError(
                f"{case_id}.expected_sources[{index}] must be an object"
            )

        file_path = _required_str(
            raw_source.get("file_path"),
            f"{case_id}.expected_sources[{index}].file_path",
        )
        chunk_index = raw_source.get("chunk_index")
        if chunk_index is not None and not _is_int(chunk_index):
            raise ValueError(
                f"{case_id}.expected_sources[{index}].chunk_index must be an integer"
            )
        document_id = raw_source.get("document_id")
        if document_id is not None and not isinstance(document_id, str):
            raise ValueError(
                f"{case_id}.expected_sources[{index}].document_id must be a string"
            )

        sources.append(
            ExpectedSource(
                file_path=file_path,
                chunk_index=chunk_index,
                document_id=document_id,
            )
        )
    return sources


def _parse_string_list(raw_value: object, field: str) -> list[str]:
    if not isinstance(raw_value, list):
        raise ValueError(f"{field} must be a list")
    values: list[str] = []
    for index, item in enumerate(raw_value):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{field}[{index}] must be a non-empty string")
        values.append(item)
    return values


def _required_str(raw_value: object, field: str) -> str:
    if not isinstance(raw_value, str) or not raw_value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return raw_value


def _is_int(raw_value: object) -> bool:
    return isinstance(raw_value, int) and not isinstance(raw_value, bool)
