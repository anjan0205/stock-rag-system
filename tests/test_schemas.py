"""Unit tests for data-layer schema validation."""
from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from equity_research.data.schemas import (
    CollectedData,
    DocSourceType,
    Document,
    Exchange,
    Fundamentals,
    NewsArticle,
    PriceBar,
)


def test_price_bar_valid():
    bar = PriceBar(
        bar_date=date(2025, 1, 2), open=100.0, high=105.0, low=99.0, close=104.0, volume=12345
    )
    assert bar.close == 104.0
    assert bar.volume == 12345


def test_price_bar_rejects_extra_fields():
    with pytest.raises(ValidationError):
        PriceBar(
            bar_date=date(2025, 1, 2),
            open=1,
            high=2,
            low=0.5,
            close=1.5,
            volume=10,
            bogus="x",  # extra="forbid"
        )


def test_price_bar_requires_all_ohlc():
    with pytest.raises(ValidationError):
        PriceBar(bar_date=date(2025, 1, 2), open=1, high=2, low=0.5, volume=10)  # no close


def test_fundamentals_all_optional():
    f = Fundamentals()
    assert f.trailing_pe is None
    assert f.quarterly_financials == []


def test_news_article_requires_url_and_title():
    art = NewsArticle(title="X reports strong Q3", url="https://example.com/x")
    assert art.url.startswith("https://")
    with pytest.raises(ValidationError):
        NewsArticle(title="missing url")  # url required


def test_document_source_type_enum():
    doc = Document(title="Q3 FY25", source_type=DocSourceType.EARNINGS_PDF, text="...")
    assert doc.source_type == DocSourceType.EARNINGS_PDF
    with pytest.raises(ValidationError):
        Document(title="bad", source_type="not_a_type", text="...")


def test_collected_data_summary_dict():
    data = CollectedData(
        ticker="RELIANCE.NS",
        base_symbol="RELIANCE",
        exchange=Exchange.NSE,
        company_name="Reliance Industries Limited",
        collected_at=datetime.now(timezone.utc),
        price_history=[
            PriceBar(bar_date=date(2025, 1, 2), open=1, high=2, low=0.5, close=1.5, volume=10)
        ],
        news=[NewsArticle(title="t", url="https://e.com")],
    )
    s = data.summary_dict()
    assert s["ticker"] == "RELIANCE.NS"
    assert s["price_bars"] == 1
    assert s["latest_close"] == 1.5
    assert s["news_articles"] == 1


def test_collected_data_defaults():
    data = CollectedData(
        ticker="TCS.NS",
        base_symbol="TCS",
        exchange=Exchange.NSE,
        collected_at=datetime.now(timezone.utc),
    )
    assert data.price_history == []
    assert isinstance(data.fundamentals, Fundamentals)
    assert data.warnings == []
