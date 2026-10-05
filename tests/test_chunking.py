"""Unit tests for the chunking logic and ticker normalization."""
import pytest

from equity_research.data.schemas import DocSourceType, Document, Exchange
from equity_research.data.tickers import normalize_ticker
from equity_research.rag.chunking import _split_text, chunk_document


def test_split_short_text_single_chunk():
    chunks = _split_text("hello world", chunk_size=900, overlap=150)
    assert chunks == ["hello world"]


def test_split_empty_text():
    assert _split_text("", 900, 150) == []
    assert _split_text("   ", 900, 150) == []


def test_split_long_text_multiple_chunks_with_overlap():
    text = " ".join(f"word{i}" for i in range(500))  # long
    chunks = _split_text(text, chunk_size=200, overlap=50)
    assert len(chunks) > 1
    # Every chunk within size bound (allow small slack for boundary trimming).
    assert all(len(c) <= 200 for c in chunks)
    # Reconstructable coverage: last word appears somewhere.
    assert "word499" in chunks[-1]


def test_split_rejects_bad_overlap():
    with pytest.raises(ValueError):
        _split_text("abc", chunk_size=10, overlap=10)
    with pytest.raises(ValueError):
        _split_text("abc", chunk_size=0, overlap=0)


def test_chunk_document_metadata_propagates():
    doc = Document(
        title="Q3 FY25 Results",
        source_type=DocSourceType.EARNINGS_PDF,
        text=" ".join(f"token{i}" for i in range(400)),
        url="https://example.com/q3.pdf",
    )
    chunks = chunk_document(doc, chunk_size=200, overlap=40)
    assert len(chunks) > 1
    for i, ch in enumerate(chunks):
        assert ch.source_type == DocSourceType.EARNINGS_PDF
        assert ch.title == "Q3 FY25 Results"
        assert ch.url == "https://example.com/q3.pdf"
        assert ch.chunk_index == i
    # Chunk ids are unique.
    assert len({c.chunk_id for c in chunks}) == len(chunks)


@pytest.mark.parametrize(
    "raw,expected_symbol,expected_base,expected_exchange",
    [
        ("reliance", "RELIANCE.NS", "RELIANCE", Exchange.NSE),
        ("TCS.NS", "TCS.NS", "TCS", Exchange.NSE),
        ("500325.BO", "500325.BO", "500325", Exchange.BSE),
        (" infy ", "INFY.NS", "INFY", Exchange.NSE),
    ],
)
def test_normalize_ticker(raw, expected_symbol, expected_base, expected_exchange):
    sym, base, exch = normalize_ticker(raw)
    assert sym == expected_symbol
    assert base == expected_base
    assert exch == expected_exchange


def test_normalize_ticker_empty():
    with pytest.raises(ValueError):
        normalize_ticker("   ")
