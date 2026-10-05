"""Streamlit UI layer for the equity research RAG system.

Presentation-only helpers that turn validated `CollectedData` into
DataFrames, Plotly figures, and formatted metric strings. All heavy lifting
(collection, ingestion, retrieval, generation) stays in the existing
data/rag/llm packages — this layer never fabricates data.
"""
