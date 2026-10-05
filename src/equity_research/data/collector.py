"""Data Collector — orchestrates price, fundamentals, news, and documents.

Given a ticker it produces a validated CollectedData payload and (optionally)
ingests the documents into Chroma for RAG. This is the single entry point the
rest of the system (and the smoke test) calls.
"""
from __future__ import annotations

from datetime import datetime, timezone

import yfinance as yf

from ..config import Settings, get_settings
from ..logging_setup import get_logger
from ..rag.chunking import chunk_documents
from ..rag.store import DocumentStore
from . import documents as docmod
from . import news as newsmod
from . import price as pricemod
from .schemas import CollectedData, Exchange
from .tickers import normalize_ticker

log = get_logger(__name__)


def collect(
    ticker: str,
    settings: Settings | None = None,
    default_exchange: Exchange = Exchange.NSE,
    include_documents: bool = True,
    pdf_urls: list[str] | None = None,
) -> CollectedData:
    """Collect all Phase-1 data for one ticker into a validated payload."""
    settings = settings or get_settings()
    yf_symbol, base_symbol, exchange = normalize_ticker(ticker, default_exchange)
    log.info("Collecting data for %s (%s / %s)", yf_symbol, base_symbol, exchange.value)

    warnings: list[str] = []
    tk = yf.Ticker(yf_symbol)

    # --- Company identity ---
    company_name = sector = industry = None
    try:
        info = tk.info or {}
        company_name = info.get("longName") or info.get("shortName")
        sector = info.get("sector")
        industry = info.get("industry")
    except Exception as e:  # noqa: BLE001
        warnings.append(f"company info fetch failed: {e}")

    # --- Price history ---
    bars, w = pricemod.fetch_price_history(tk, settings.price_history_period)
    warnings.extend(w)

    # --- Fundamentals ---
    fundamentals, w = pricemod.fetch_fundamentals(tk)
    warnings.extend(w)

    # --- News ---
    articles, w = newsmod.fetch_news(company_name, base_symbol, settings.news_lookback_days)
    warnings.extend(w)

    # --- Documents ---
    docs = []
    if include_documents:
        local_docs, w = docmod.load_local_pdfs(base_symbol, settings.raw_data_path)
        docs.extend(local_docs)
        warnings.extend(w)

        for url in pdf_urls or []:
            doc, w = docmod.load_pdf_url(url)
            warnings.extend(w)
            if doc:
                docs.append(doc)

        profile = docmod.build_company_profile(tk, company_name)
        if profile:
            docs.append(profile)
        else:
            warnings.append("could not build company profile document")

    data = CollectedData(
        ticker=yf_symbol,
        base_symbol=base_symbol,
        exchange=exchange,
        company_name=company_name,
        sector=sector,
        industry=industry,
        collected_at=datetime.now(timezone.utc),
        price_history=bars,
        fundamentals=fundamentals,
        news=articles,
        documents=docs,
        warnings=warnings,
    )
    log.info("Collected %s: %s", yf_symbol, data.summary_dict())
    return data


def ingest_to_chroma(data: CollectedData, store: DocumentStore | None = None) -> int:
    """Chunk the collected documents + news and store them in Chroma.

    News items are treated as short documents so sentiment RAG can cite them.
    Returns the number of chunks stored.
    """
    from .schemas import DocSourceType, Document

    settings = get_settings()
    store = store or DocumentStore(settings.chroma_path)

    docs = list(data.documents)
    # Represent each news article as a tiny document for retrieval + citation.
    for art in data.news:
        body = art.summary or art.title
        docs.append(
            Document(
                title=art.title,
                source_type=DocSourceType.NEWS,
                text=f"{art.title}\n\n{body}",
                url=art.url,
                published=art.published,
            )
        )

    chunks = chunk_documents(docs)
    stored = store.add_chunks(data.ticker, chunks)
    log.info("Ingested %d chunks for %s into Chroma", stored, data.ticker)
    return stored
