"""Phase 1 smoke test.

Fetches data for 3 sample NSE tickers, prints a summary of what was collected,
ingests documents into Chroma, and runs one sample RAG query to prove the
vector store works end to end.

Run from project root:
    .venv/Scripts/python.exe scripts/phase1_smoke_test.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Windows consoles default to cp1252 and choke on ₹ / other Unicode in
# headlines. Force UTF-8 so printing never crashes on valid data.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Make `src` importable without installing the package.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from equity_research.config import get_settings  # noqa: E402
from equity_research.data.collector import collect, ingest_to_chroma  # noqa: E402
from equity_research.logging_setup import setup_logging  # noqa: E402
from equity_research.rag.store import DocumentStore  # noqa: E402

SAMPLE_TICKERS = ["RELIANCE", "TCS", "INFY"]


def _print_header(text: str) -> None:
    print("\n" + "=" * 70)
    print(text)
    print("=" * 70)


def main() -> int:
    settings = get_settings()
    settings.ensure_dirs()
    log_file = setup_logging(settings.log_path)
    print(f"Logging to: {log_file}")

    store = DocumentStore(settings.chroma_path)

    for ticker in SAMPLE_TICKERS:
        _print_header(f"TICKER: {ticker}")
        data = collect(ticker, settings=settings)

        summary = data.summary_dict()
        print("\n-- Summary --")
        print(json.dumps(summary, indent=2, default=str))

        if data.price_history:
            first, last = data.price_history[0], data.price_history[-1]
            print(
                f"\n-- Price range: {first.bar_date} close={first.close:.2f} "
                f"-> {last.bar_date} close={last.close:.2f}"
            )

        f = data.fundamentals
        print("\n-- Fundamentals (selected) --")
        print(
            json.dumps(
                {
                    "market_cap": f.market_cap,
                    "trailing_pe": f.trailing_pe,
                    "forward_pe": f.forward_pe,
                    "debt_to_equity": f.debt_to_equity,
                    "return_on_equity": f.return_on_equity,
                    "revenue_growth": f.revenue_growth,
                    "currency": f.currency,
                    "quarters": len(f.quarterly_financials),
                },
                indent=2,
                default=str,
            )
        )

        print("\n-- Top 3 news headlines --")
        for art in data.news[:3]:
            when = art.published.date() if art.published else "n/a"
            print(f"  [{when}] {art.title}  ({art.source or 'unknown'})")
            print(f"        {art.url}")
        if not data.news:
            print("  (none)")

        print("\n-- Documents collected --")
        for d in data.documents:
            print(f"  [{d.source_type.value}] {d.title}  ({len(d.text)} chars)")

        # Ingest into Chroma and prove retrieval works.
        stored = ingest_to_chroma(data, store=store)
        total = store.count_for_ticker(data.ticker)
        print(f"\n-- RAG: ingested {stored} chunks; {total} total for {data.ticker}")

        hits = store.query(data.ticker, "revenue growth and profitability", n_results=2)
        print("-- Sample RAG query: 'revenue growth and profitability' --")
        for h in hits:
            meta = h["metadata"]
            snippet = h["text"][:160].replace("\n", " ")
            print(f"  ({meta.get('source_type')}) dist={h['distance']:.3f}: {snippet}...")

        if data.warnings:
            print("\n-- Warnings --")
            for wmsg in data.warnings:
                print(f"  ! {wmsg}")

    _print_header("DONE")
    print(f"Tickers processed: {', '.join(SAMPLE_TICKERS)}")
    print(f"Chroma persisted at: {settings.chroma_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
