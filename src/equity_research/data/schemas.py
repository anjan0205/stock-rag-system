"""Pydantic data contracts for the collection layer.

Everything the Data Collector returns is validated against these models so
downstream agents never have to guess about shape or types. Prices/fundamentals
are stored as typed fields; documents/news carry the metadata RAG needs for
citations (source, url, published date, section).
"""
from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class Exchange(str, Enum):
    NSE = "NSE"
    BSE = "BSE"


class DocSourceType(str, Enum):
    """Where a stored document/chunk originated — used for citations."""

    NEWS = "news"
    EARNINGS_PDF = "earnings_pdf"
    INVESTOR_DECK = "investor_deck"
    COMPANY_PROFILE = "company_profile"  # yfinance business summary + financials narrative
    OTHER = "other"


class PriceBar(BaseModel):
    """A single OHLCV daily bar."""

    model_config = ConfigDict(extra="forbid")

    bar_date: date
    open: float
    high: float
    low: float
    close: float
    volume: int


class Fundamentals(BaseModel):
    """Snapshot of valuation + financial-health metrics.

    All fields optional: free data sources routinely omit values, and we would
    rather record a null than fabricate one.
    """

    model_config = ConfigDict(extra="forbid")

    market_cap: float | None = None
    trailing_pe: float | None = None
    forward_pe: float | None = None
    price_to_book: float | None = None
    debt_to_equity: float | None = None
    return_on_equity: float | None = None
    profit_margin: float | None = None
    revenue_growth: float | None = None
    earnings_growth: float | None = None
    dividend_yield: float | None = None
    beta: float | None = None
    fifty_two_week_high: float | None = None
    fifty_two_week_low: float | None = None
    currency: str | None = None

    # Quarterly results: list of {"period": "2024-03-31", "metric": value, ...}
    quarterly_financials: list[dict] = Field(default_factory=list)


class NewsArticle(BaseModel):
    """A single news item. `url` is mandatory so claims are always traceable."""

    model_config = ConfigDict(extra="forbid")

    title: str
    url: str
    source: str | None = None
    published: datetime | None = None
    summary: str | None = None


class DocumentChunk(BaseModel):
    """A chunk of a longer document, ready for embedding/storage."""

    model_config = ConfigDict(extra="forbid")

    chunk_id: str
    text: str
    source_type: DocSourceType
    title: str
    url: str | None = None
    section: str | None = None
    published: datetime | None = None
    chunk_index: int = 0


class Document(BaseModel):
    """A full source document before chunking (e.g. an earnings PDF's text)."""

    model_config = ConfigDict(extra="forbid")

    title: str
    source_type: DocSourceType
    text: str
    url: str | None = None
    published: datetime | None = None


class CollectedData(BaseModel):
    """The complete Phase-1 payload for one ticker."""

    model_config = ConfigDict(extra="forbid")

    ticker: str  # yfinance symbol, e.g. RELIANCE.NS
    base_symbol: str  # without suffix, e.g. RELIANCE
    exchange: Exchange
    company_name: str | None = None
    sector: str | None = None
    industry: str | None = None
    collected_at: datetime

    price_history: list[PriceBar] = Field(default_factory=list)
    fundamentals: Fundamentals = Field(default_factory=Fundamentals)
    news: list[NewsArticle] = Field(default_factory=list)
    documents: list[Document] = Field(default_factory=list)

    # Non-fatal issues encountered during collection (missing data, failed fetches).
    warnings: list[str] = Field(default_factory=list)

    def summary_dict(self) -> dict:
        """Compact, human-readable summary for the smoke test."""
        return {
            "ticker": self.ticker,
            "company_name": self.company_name,
            "exchange": self.exchange.value,
            "sector": self.sector,
            "price_bars": len(self.price_history),
            "latest_close": self.price_history[-1].close if self.price_history else None,
            "news_articles": len(self.news),
            "documents": len(self.documents),
            "has_pe": self.fundamentals.trailing_pe is not None,
            "has_debt_to_equity": self.fundamentals.debt_to_equity is not None,
            "quarters_of_financials": len(self.fundamentals.quarterly_financials),
            "warnings": len(self.warnings),
        }
