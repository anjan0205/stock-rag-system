"""Ticker normalization for NSE/BSE via yfinance suffixes.

yfinance uses `.NS` for NSE and `.BO` for BSE. Users may pass a bare symbol
(RELIANCE), an exchange-qualified one (RELIANCE.NS), or specify the exchange
separately. This normalizes all of that.
"""
from __future__ import annotations

from .schemas import Exchange

_SUFFIX = {Exchange.NSE: ".NS", Exchange.BSE: ".BO"}
_SUFFIX_TO_EXCHANGE = {".NS": Exchange.NSE, ".BO": Exchange.BSE}


def normalize_ticker(
    ticker: str, default_exchange: Exchange = Exchange.NSE
) -> tuple[str, str, Exchange]:
    """Return (yf_symbol, base_symbol, exchange).

    >>> normalize_ticker("reliance")
    ('RELIANCE.NS', 'RELIANCE', <Exchange.NSE: 'NSE'>)
    >>> normalize_ticker("TCS.BO")
    ('TCS.BO', 'TCS', <Exchange.BSE: 'BSE'>)
    """
    raw = ticker.strip().upper()
    if not raw:
        raise ValueError("Empty ticker")

    for suffix, exch in _SUFFIX_TO_EXCHANGE.items():
        if raw.endswith(suffix):
            base = raw[: -len(suffix)]
            return raw, base, exch

    exch = default_exchange
    return f"{raw}{_SUFFIX[exch]}", raw, exch
