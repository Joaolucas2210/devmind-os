from __future__ import annotations

import pytest

from packages.rag.chunking import chunk_text


def test_chunk_text_ignores_empty_text() -> None:
    assert chunk_text("") == []
    assert chunk_text(" \n\t ") == []


def test_chunk_text_returns_trimmed_single_chunk() -> None:
    assert chunk_text("  um texto curto\n") == ["um texto curto"]


def test_chunk_text_splits_on_word_boundaries_when_possible() -> None:
    chunks = chunk_text(
        "alpha beta gamma delta",
        chunk_size=12,
        chunk_overlap=0,
    )

    assert chunks == ["alpha beta", "gamma delta"]


def test_chunk_text_supports_overlap() -> None:
    chunks = chunk_text(
        "abcdefghij",
        chunk_size=4,
        chunk_overlap=1,
    )

    assert chunks == ["abcd", "defg", "ghij"]


def test_chunk_text_validates_configuration() -> None:
    with pytest.raises(ValueError, match="chunk_size"):
        chunk_text("texto", chunk_size=0)

    with pytest.raises(ValueError, match="chunk_overlap"):
        chunk_text("texto", chunk_size=10, chunk_overlap=-1)

    with pytest.raises(ValueError, match="chunk_overlap"):
        chunk_text("texto", chunk_size=10, chunk_overlap=10)
