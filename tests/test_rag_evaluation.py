from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from packages.domain.retrieval import RetrievedChunk, Source
from packages.rag.evaluation import (
    ExpectedSource,
    RetrievalEvalCase,
    evaluate_retrieval,
    load_retrieval_eval_cases,
)


class FakeRetriever:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    async def search(self, query: str, *, limit: int) -> list[RetrievedChunk]:
        self.calls.append((query, limit))
        if query == "hit":
            return [
                RetrievedChunk(
                    text="wrong",
                    source=Source(
                        chunk_id="chunk-wrong",
                        file_path="data/samples/wrong.md",
                        chunk_index=0,
                        score=0.99,
                    ),
                ),
                RetrievedChunk(
                    text="right",
                    source=Source(
                        chunk_id="chunk-right",
                        file_path="data/samples/right.md",
                        chunk_index=0,
                        score=0.8,
                    ),
                ),
            ]
        return [
            RetrievedChunk(
                text="miss",
                source=Source(
                    chunk_id="chunk-miss",
                    file_path="data/samples/miss.md",
                    chunk_index=0,
                    score=0.7,
                ),
            )
        ]


def test_load_retrieval_eval_cases(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset.json"
    dataset.write_text(
        """
        {
          "version": 1,
          "cases": [
            {
              "id": "case-1",
              "question": "pergunta",
              "expected_facts": ["fato"],
              "expected_sources": [
                {
                  "file_path": "data/samples/doc.md",
                  "chunk_index": 0,
                  "document_id": "doc-1"
                }
              ]
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    cases = load_retrieval_eval_cases(dataset)

    assert cases == [
        RetrievalEvalCase(
            id="case-1",
            question="pergunta",
            expected_facts=["fato"],
            expected_sources=[
                ExpectedSource(
                    file_path="data/samples/doc.md",
                    chunk_index=0,
                    document_id="doc-1",
                )
            ],
        )
    ]


def test_load_retrieval_eval_cases_rejects_missing_sources(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset.json"
    dataset.write_text(
        '{"cases":[{"id":"case-1","question":"pergunta","expected_sources":[]}]}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="expected_sources"):
        load_retrieval_eval_cases(dataset)


def test_evaluate_retrieval_calculates_recall_and_mrr() -> None:
    retriever = FakeRetriever()
    cases = [
        RetrievalEvalCase(
            id="case-hit",
            question="hit",
            expected_facts=["right"],
            expected_sources=[
                ExpectedSource(file_path="data/samples/right.md", chunk_index=0)
            ],
        ),
        RetrievalEvalCase(
            id="case-miss",
            question="miss",
            expected_facts=["missing"],
            expected_sources=[
                ExpectedSource(file_path="data/samples/absent.md", chunk_index=0)
            ],
        ),
    ]

    report = asyncio.run(evaluate_retrieval(retriever, cases, top_k=4))

    assert retriever.calls == [("hit", 4), ("miss", 4)]
    assert report.total_cases == 2
    assert report.recall_at_k == 0.5
    assert report.mrr == 0.25
    assert [case.hit for case in report.cases] == [True, False]
    assert report.cases[0].reciprocal_rank == 0.5


def test_evaluate_retrieval_rejects_invalid_top_k() -> None:
    with pytest.raises(ValueError, match="top_k"):
        asyncio.run(evaluate_retrieval(FakeRetriever(), [], top_k=0))
