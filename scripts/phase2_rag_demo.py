"""Phase 2 RAG Demo: Gemini Flash Integration.

Fetches data for a stock ticker, ingests into Chroma vector store,
retrieves relevant document chunks, and passes context + query to
Google Gemini Flash to generate grounded equity research analysis.

Usage:
    .venv/Scripts/python.exe scripts/phase2_rag_demo.py --ticker RELIANCE --query "What are the major revenue drivers and risks?"
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Fix Windows console UTF-8 printing
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Ensure `src` is in python path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from equity_research.config import get_settings  # noqa: E402
from equity_research.data.collector import collect, ingest_to_chroma  # noqa: E402
from equity_research.llm.client import GeminiClient  # noqa: E402
from equity_research.llm.generator import RAGGenerator  # noqa: E402
from equity_research.logging_setup import setup_logging  # noqa: E402
from equity_research.rag.store import DocumentStore  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Equity Research RAG Demo using Gemini Flash")
    parser.add_argument("--ticker", default="RELIANCE", help="NSE ticker symbol (e.g. RELIANCE, TCS, INFY)")
    parser.add_argument(
        "--query",
        default="What are the main business highlights, financial performance, and key risk factors?",
        help="Research query for Gemini RAG",
    )
    parser.add_argument("--n-results", type=int, default=5, help="Number of RAG document chunks to retrieve")
    args = parser.parse_args()

    settings = get_settings()
    settings.ensure_dirs()
    setup_logging(settings.log_path)

    print("\n" + "=" * 75)
    print(f" STOCK RAG DEMO - GEMINI FLASH LLM INTEGRATION")
    print(f" Ticker: {args.ticker} | Model: {settings.gemini_model}")
    print("=" * 75)

    # 1. Initialize Vector Store & Gemini Client
    store = DocumentStore(settings.chroma_path)
    client = GeminiClient()

    if not client.is_available:
        print("\n[ERROR] GEMINI_API_KEY is not set in environment or .env file.")
        print("Please configure GEMINI_API_KEY to proceed.")
        return 1

    # 2. Collect Data & Ingest into Chroma
    print(f"\n[1/4] Fetching latest market & document data for {args.ticker}...")
    data = collect(args.ticker, settings=settings)

    print(f"[2/4] Ingesting documents into Chroma vector store...")
    stored = ingest_to_chroma(data, store=store)
    total_stored = store.count_for_ticker(data.ticker)
    print(f"       -> Ingested {stored} new chunks (Total in vector store: {total_stored})")

    # 3. Vector Retrieval
    print(f"\n[3/4] Retrieving top {args.n_results} chunks for query: '{args.query}'...")
    hits = store.query(data.ticker, query_text=args.query, n_results=args.n_results)

    print(f"       -> Retrieved {len(hits)} relevant context chunks.")
    for idx, h in enumerate(hits, start=1):
        meta = h["metadata"]
        print(f"          [{idx}] {meta.get('title')} (dist={h['distance']:.3f})")

    # Prepare fundamentals and price summary dicts
    f = data.fundamentals
    fundamentals_dict = {
        "market_cap": f.market_cap,
        "trailing_pe": f.trailing_pe,
        "forward_pe": f.forward_pe,
        "debt_to_equity": f.debt_to_equity,
        "return_on_equity": f.return_on_equity,
        "revenue_growth": f.revenue_growth,
        "currency": f.currency,
    }

    price_summary_dict = {}
    if data.price_history:
        p_start, p_end = data.price_history[0], data.price_history[-1]
        price_summary_dict = {
            "period": settings.price_history_period,
            "start_date": p_start.bar_date,
            "start_close": p_start.close,
            "end_date": p_end.bar_date,
            "end_close": p_end.close,
        }

    # 4. Generate RAG Answer with Gemini Flash
    print(f"\n[4/4] Generating grounded analysis using Gemini Flash LLM...")
    generator = RAGGenerator(client=client)

    answer = generator.generate_answer(
        ticker=data.ticker,
        user_query=args.query,
        retrieved_chunks=hits,
        fundamentals=fundamentals_dict,
        price_summary=price_summary_dict,
    )

    print("\n" + "=" * 75)
    print(" GEMINI FLASH GROUNDED ANSWER & CITATIONS:")
    print("=" * 75 + "\n")
    print(answer)
    print("\n" + "=" * 75)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
