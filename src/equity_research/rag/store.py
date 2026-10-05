"""Chroma vector store wrapper.

Uses a local persistent Chroma client with its built-in default embedding
function (an ONNX MiniLM model, downloaded once, then fully offline — no API
key needed for embeddings). Documents are stored with rich metadata so the RAG
agents in later phases can filter by ticker + source type and produce citations.
"""
from __future__ import annotations

from pathlib import Path

import chromadb
from chromadb.config import Settings as ChromaSettings

from ..data.schemas import DocumentChunk
from ..logging_setup import get_logger

log = get_logger(__name__)

COLLECTION_NAME = "equity_documents"


class DocumentStore:
    """Thin wrapper over a persistent Chroma collection."""

    def __init__(self, persist_dir: Path):
        persist_dir.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(
            path=str(persist_dir),
            settings=ChromaSettings(anonymized_telemetry=False, allow_reset=True),
        )
        # Default embedding function is used implicitly when none is passed.
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    def add_chunks(self, ticker: str, chunks: list[DocumentChunk]) -> int:
        """Upsert chunks for a ticker. Returns number stored."""
        if not chunks:
            return 0

        ids: list[str] = []
        docs: list[str] = []
        metadatas: list[dict] = []
        for ch in chunks:
            # Namespacing the id by ticker avoids collisions across tickers.
            ids.append(f"{ticker}::{ch.chunk_id}")
            docs.append(ch.text)
            metadatas.append(
                {
                    "ticker": ticker,
                    "source_type": ch.source_type.value,
                    "title": ch.title,
                    "url": ch.url or "",
                    "section": ch.section or "",
                    "chunk_index": ch.chunk_index,
                    "published": ch.published.isoformat() if ch.published else "",
                }
            )

        self.collection.upsert(ids=ids, documents=docs, metadatas=metadatas)
        return len(ids)

    def count_for_ticker(self, ticker: str) -> int:
        res = self.collection.get(where={"ticker": ticker}, include=[])
        return len(res.get("ids", []))

    def query(
        self,
        ticker: str,
        query_text: str,
        n_results: int = 5,
        source_type: str | None = None,
    ) -> list[dict]:
        """Semantic search within one ticker's documents.

        Returns list of {text, metadata, distance} for citation-friendly use.
        """
        where: dict = {"ticker": ticker}
        if source_type:
            where = {"$and": [{"ticker": ticker}, {"source_type": source_type}]}

        res = self.collection.query(
            query_texts=[query_text],
            n_results=n_results,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        out: list[dict] = []
        docs = (res.get("documents") or [[]])[0]
        metas = (res.get("metadatas") or [[]])[0]
        dists = (res.get("distances") or [[]])[0]
        for text, meta, dist in zip(docs, metas, dists):
            out.append({"text": text, "metadata": meta, "distance": dist})
        return out

    def reset(self) -> None:
        """Drop and recreate the collection (used in tests / re-ingest)."""
        self.client.delete_collection(COLLECTION_NAME)
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
