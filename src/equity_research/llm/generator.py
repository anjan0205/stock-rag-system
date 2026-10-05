"""RAG Generator using Gemini Flash LLM.

Combines vector store retrieval hits with structured stock metadata
(fundamentals & price summary) and queries Gemini Flash to produce
grounded equity research answers with source citations.
"""
from __future__ import annotations

import json
from typing import Any

from ..logging_setup import get_logger
from .client import GeminiClient

log = get_logger(__name__)

SYSTEM_PROMPT = """You are an expert equity research analyst.
Your task is to answer questions about a target company based STRICTLY on the provided context (retrieved document chunks, financial metrics, and price history).

Strict Rules:
1. Base your answer ONLY on the information provided in the context.
2. Provide precise source citations for your claims. Reference news titles, document sources, or financial metrics in brackets (e.g., [Reliance Q3 Investor Deck] or [News: Financial Express]).
3. If the context does not contain sufficient data to fully answer the query, clearly state what data is available and what information is missing. DO NOT make up financial facts, dates, or numbers.
4. Keep your tone objective, professional, and structured (use section headers and bullet points where helpful).
"""


class RAGGenerator:
    """Combines retrieved data and prompts Gemini Flash for grounded QA."""

    def __init__(self, client: GeminiClient | None = None):
        self.client = client or GeminiClient()

    def format_context(
        self,
        ticker: str,
        retrieved_chunks: list[dict[str, Any]],
        fundamentals: dict[str, Any] | None = None,
        price_summary: dict[str, Any] | None = None,
    ) -> str:
        """Format retrieved evidence into a structured string for the LLM prompt."""
        sections: list[str] = [f"=== TARGET TICKER: {ticker} ==="]

        # 1. Fundamental Financials
        if fundamentals:
            sections.append("\n--- Key Financial Metrics & Fundamentals ---")
            sections.append(json.dumps(fundamentals, indent=2, default=str))

        # 2. Price History Summary
        if price_summary:
            sections.append("\n--- Recent Price Performance ---")
            sections.append(json.dumps(price_summary, indent=2, default=str))

        # 3. Vector Search Retrieved Document Chunks
        sections.append("\n--- Retrieved Document Chunks & News Articles ---")
        if not retrieved_chunks:
            sections.append("(No relevant document chunks retrieved)")
        else:
            for idx, chunk in enumerate(retrieved_chunks, start=1):
                meta = chunk.get("metadata", {})
                text = chunk.get("text", "").strip()
                title = meta.get("title", "Untitled")
                source_type = meta.get("source_type", "unknown")
                published = meta.get("published", "")
                url = meta.get("url", "")

                header = f"[{idx}] Source: {title} | Type: {source_type}"
                if published:
                    header += f" | Date: {published}"
                if url:
                    header += f" | URL: {url}"

                sections.append(f"{header}\nContent:\n{text}\n")

        return "\n".join(sections)

    def generate_answer(
        self,
        ticker: str,
        user_query: str,
        retrieved_chunks: list[dict[str, Any]],
        fundamentals: dict[str, Any] | None = None,
        price_summary: dict[str, Any] | None = None,
        temperature: float = 0.2,
    ) -> str:
        """Generate a grounded equity research response using Gemini Flash.

        Args:
            ticker: Stock ticker symbol (e.g., RELIANCE).
            user_query: The research question asked by the user.
            retrieved_chunks: Output list of dicts from DocumentStore.query().
            fundamentals: Dict of key fundamental metrics.
            price_summary: Dict of price range / performance.
            temperature: Sampling temperature for Gemini.

        Returns:
            The generated response string.
        """
        context_str = self.format_context(
            ticker=ticker,
            retrieved_chunks=retrieved_chunks,
            fundamentals=fundamentals,
            price_summary=price_summary,
        )

        user_prompt = f"""Context Information:
{context_str}

User Question: {user_query}

Provide a comprehensive, factual, and grounded response with explicit citations based on the context above:"""

        log.info("Generating RAG answer for ticker %s query '%s'", ticker, user_query)
        return self.client.generate(
            prompt=user_prompt,
            system_instruction=SYSTEM_PROMPT,
            temperature=temperature,
        )
