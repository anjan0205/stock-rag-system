"""Live company search across Indian exchanges via Yahoo Finance.

Lets the UI resolve a free-text company name (or partial symbol) to concrete
NSE/BSE tickers, so a user can research *any* listed Indian company without
knowing its exact yfinance symbol. Results are live from Yahoo's search API.
"""
from __future__ import annotations

from dataclasses import dataclass

import yfinance as yf

from ..logging_setup import get_logger
from .schemas import Exchange

log = get_logger(__name__)

# Yahoo exchange codes -> our Exchange enum. NSI = NSE, BSE = BSE.
_EXCHANGE_MAP = {"NSI": Exchange.NSE, "BSE": Exchange.BSE}


@dataclass(frozen=True)
class CompanyHit:
    """A single search result for a listed Indian company."""

    symbol: str            # full yfinance symbol, e.g. RELIANCE.NS
    base_symbol: str       # without suffix, e.g. RELIANCE
    name: str              # company display name
    exchange: Exchange     # NSE or BSE

    @property
    def label(self) -> str:
        return f"{self.name} — {self.base_symbol} ({self.exchange.value})"


def search_companies(query: str, max_results: int = 12) -> list[CompanyHit]:
    """Search Yahoo Finance for Indian equities matching `query`.

    Returns only NSE/BSE equities (no futures, indices, or foreign listings),
    de-duplicated by symbol. Never raises — returns an empty list on failure.
    """
    query = (query or "").strip()
    if not query:
        return []

    try:
        res = yf.Search(query, max_results=max_results * 3)
        quotes = getattr(res, "quotes", None) or []
    except Exception as e:  # noqa: BLE001 - network/parse errors vary
        log.warning("company search failed for %r: %s", query, e)
        return []

    hits: list[CompanyHit] = []
    seen: set[str] = set()
    for q in quotes:
        symbol = (q.get("symbol") or "").strip()
        quote_type = (q.get("quoteType") or "").upper()
        yahoo_exch = (q.get("exchange") or "").upper()

        if quote_type != "EQUITY":
            continue
        exchange = _EXCHANGE_MAP.get(yahoo_exch)
        if exchange is None:  # not NSE/BSE
            continue
        if symbol in seen:
            continue

        name = q.get("shortname") or q.get("longname") or symbol
        base = symbol.rsplit(".", 1)[0]
        hits.append(CompanyHit(symbol=symbol, base_symbol=base, name=name, exchange=exchange))
        seen.add(symbol)
        if len(hits) >= max_results:
            break

    log.info("company search %r -> %d Indian equity hits", query, len(hits))
    return hits
