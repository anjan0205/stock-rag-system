"""Document chunking for RAG.

Word-boundary-aware character chunking with overlap. Kept deliberately simple
and dependency-free (no tokenizer needed) so it is easy to unit-test and reason
about. Each chunk inherits its parent document's citation metadata.
"""
from __future__ import annotations

import hashlib

from ..data.schemas import Document, DocumentChunk

DEFAULT_CHUNK_SIZE = 900  # characters
DEFAULT_OVERLAP = 150  # characters


def _split_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be >= 0 and < chunk_size")

    chunks: list[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + chunk_size, n)
        # Prefer to break on whitespace near the end for cleaner chunks.
        if end < n:
            window = text.rfind(" ", start, end)
            if window != -1 and window > start + int(chunk_size * 0.5):
                end = window
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= n:
            break
        start = max(end - overlap, start + 1)
    return chunks


def _chunk_id(doc_title: str, source_type: str, index: int, text: str) -> str:
    h = hashlib.sha1(f"{doc_title}|{source_type}|{index}|{text}".encode()).hexdigest()[:16]
    return f"{source_type}_{index}_{h}"


def chunk_document(
    doc: Document,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_OVERLAP,
) -> list[DocumentChunk]:
    """Split one Document into DocumentChunks with citation metadata."""
    pieces = _split_text(doc.text, chunk_size, overlap)
    out: list[DocumentChunk] = []
    for i, piece in enumerate(pieces):
        out.append(
            DocumentChunk(
                chunk_id=_chunk_id(doc.title, doc.source_type.value, i, piece),
                text=piece,
                source_type=doc.source_type,
                title=doc.title,
                url=doc.url,
                published=doc.published,
                chunk_index=i,
            )
        )
    return out


def chunk_documents(
    docs: list[Document],
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_OVERLAP,
) -> list[DocumentChunk]:
    chunks: list[DocumentChunk] = []
    for doc in docs:
        chunks.extend(chunk_document(doc, chunk_size, overlap))
    return chunks
