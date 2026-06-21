from __future__ import annotations

DEFAULT_CHUNK_OVERLAP = 100
DEFAULT_CHUNK_SIZE = 1000


def chunk_text(
    text: str,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[str]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero")
    if chunk_overlap < 0:
        raise ValueError("chunk_overlap must be greater than or equal to zero")
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")

    source = text.strip()
    if not source:
        return []
    if len(source) <= chunk_size:
        return [source]

    chunks: list[str] = []
    start = 0

    while start < len(source):
        end = min(start + chunk_size, len(source))
        if end < len(source):
            split_at = _best_split(source, start, end)
            if split_at > start:
                end = split_at

        chunk = source[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(source):
            break

        next_start = max(end - chunk_overlap, 0)
        if next_start <= start:
            next_start = end
        start = _skip_whitespace(source, next_start)

    return chunks


def _best_split(text: str, start: int, end: int) -> int:
    for separator in ("\n\n", "\n", " "):
        split_at = text.rfind(separator, start, end)
        if split_at > start:
            return split_at
    return -1


def _skip_whitespace(text: str, start: int) -> int:
    while start < len(text) and text[start].isspace():
        start += 1
    return start
