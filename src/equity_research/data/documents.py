"""Document acquisition for RAG (earnings reports, investor decks, profiles).

Reality check: there is no free, reliable, universal API that maps an arbitrary
NSE/BSE ticker to its latest earnings-report/investor-deck PDF. So this module
supports three concrete paths, in priority order:

1. Local PDFs the user drops in ``data/raw/<BASE_SYMBOL>/`` — extracted via pypdf.
2. PDF URLs passed explicitly (e.g. an investor-relations link) — downloaded + extracted.
3. A synthesized "company profile" document built from yfinance's long business
   summary plus a compact financials narrative. This always exists so the
   fundamental/RAG pipeline has something to work with even with zero PDFs.

Every returned Document carries a source_type so citations stay honest about
whether a claim came from a filed PDF or the yfinance-derived profile.
"""
from __future__ import annotations

import io
from datetime import datetime, timezone
from pathlib import Path

import requests
import yfinance as yf
from pypdf import PdfReader

from ..logging_setup import get_logger
from .schemas import DocSourceType, Document

log = get_logger(__name__)

_HEADERS = {"User-Agent": "Mozilla/5.0 (equity-research-desk; research use)"}


def _extract_pdf_text(data: bytes) -> str:
    reader = PdfReader(io.BytesIO(data))
    parts: list[str] = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception as e:  # noqa: BLE001
            log.warning("PDF page extract failed: %s", e)
    return "\n".join(parts).strip()


def load_local_pdfs(base_symbol: str, raw_dir: Path) -> tuple[list[Document], list[str]]:
    """Load any PDFs found under raw_dir/<BASE_SYMBOL>/."""
    warnings: list[str] = []
    docs: list[Document] = []
    folder = raw_dir / base_symbol
    if not folder.exists():
        return docs, warnings

    for pdf_path in sorted(folder.glob("*.pdf")):
        try:
            text = _extract_pdf_text(pdf_path.read_bytes())
            if not text:
                warnings.append(f"no text extracted from {pdf_path.name}")
                continue
            # Heuristic source typing from filename.
            lower = pdf_path.stem.lower()
            stype = (
                DocSourceType.INVESTOR_DECK
                if any(k in lower for k in ("deck", "presentation", "investor"))
                else DocSourceType.EARNINGS_PDF
            )
            docs.append(
                Document(
                    title=pdf_path.stem,
                    source_type=stype,
                    text=text,
                    url=pdf_path.as_uri(),
                    published=datetime.fromtimestamp(
                        pdf_path.stat().st_mtime, tz=timezone.utc
                    ),
                )
            )
        except Exception as e:  # noqa: BLE001
            warnings.append(f"failed to read {pdf_path.name}: {e}")
    return docs, warnings


def load_pdf_url(url: str, title: str | None = None) -> tuple[Document | None, list[str]]:
    """Download and extract a PDF from a URL."""
    warnings: list[str] = []
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=30)
        resp.raise_for_status()
    except Exception as e:  # noqa: BLE001
        return None, [f"failed to download {url}: {e}"]

    try:
        text = _extract_pdf_text(resp.content)
    except Exception as e:  # noqa: BLE001
        return None, [f"failed to parse PDF {url}: {e}"]

    if not text:
        return None, [f"no text extracted from {url}"]

    return (
        Document(
            title=title or url.rsplit("/", 1)[-1],
            source_type=DocSourceType.EARNINGS_PDF,
            text=text,
            url=url,
            published=datetime.now(timezone.utc),
        ),
        warnings,
    )


def build_company_profile(tk: yf.Ticker, company_name: str | None) -> Document | None:
    """Synthesize a profile document from yfinance info + financials narrative."""
    try:
        info: dict = tk.info or {}
    except Exception as e:  # noqa: BLE001
        log.warning("profile info fetch failed: %s", e)
        info = {}

    summary = info.get("longBusinessSummary")
    lines: list[str] = []
    name = company_name or info.get("longName") or info.get("shortName") or "The company"
    lines.append(f"Company profile: {name}")
    if info.get("sector"):
        lines.append(f"Sector: {info['sector']}")
    if info.get("industry"):
        lines.append(f"Industry: {info['industry']}")
    if info.get("fullTimeEmployees"):
        lines.append(f"Full-time employees: {info['fullTimeEmployees']}")
    if summary:
        lines.append("")
        lines.append("Business summary:")
        lines.append(summary)

    # Compact financials narrative so the RAG layer has numeric context too.
    fin_bits = []
    for label, key in [
        ("Market cap", "marketCap"),
        ("Trailing P/E", "trailingPE"),
        ("Forward P/E", "forwardPE"),
        ("Price-to-book", "priceToBook"),
        ("Debt-to-equity", "debtToEquity"),
        ("Return on equity", "returnOnEquity"),
        ("Profit margin", "profitMargins"),
        ("Revenue growth (yoy)", "revenueGrowth"),
        ("Earnings growth (yoy)", "earningsGrowth"),
    ]:
        val = info.get(key)
        if val is not None:
            fin_bits.append(f"{label}: {val}")
    if fin_bits:
        lines.append("")
        lines.append("Key financial metrics (source: yfinance):")
        lines.extend(fin_bits)

    text = "\n".join(lines).strip()
    if len(text) < 40:  # essentially empty
        return None

    return Document(
        title=f"{name} — company profile",
        source_type=DocSourceType.COMPANY_PROFILE,
        text=text,
        url=None,
        published=datetime.now(timezone.utc),
    )
