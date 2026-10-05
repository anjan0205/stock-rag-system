"""Price history + fundamentals via yfinance.

Returns validated schema objects. Missing values are recorded as warnings
rather than fabricated, so downstream agents can reason about data gaps.
"""
from __future__ import annotations

import math
from datetime import date
from typing import Any

import pandas as pd
import yfinance as yf

from ..logging_setup import get_logger
from .schemas import Fundamentals, PriceBar

log = get_logger(__name__)


def _clean_float(value: Any) -> float | None:
    """Coerce to float, mapping NaN/inf/None to None."""
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return f


# A spread of large-cap NSE names for the scrolling ticker tape.
POPULAR_NSE = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
    "SBIN.NS", "BHARTIARTL.NS", "ITC.NS", "LT.NS", "HINDUNILVR.NS",
    "MARUTI.NS", "WIPRO.NS",
]


def fetch_watchlist_quotes(symbols: list[str] | None = None) -> list[dict[str, Any]]:
    """Batch-fetch last price + daily % change for a set of tickers in one call.

    Powers the marquee ticker tape. Never raises — returns [] on failure.
    """
    symbols = symbols or POPULAR_NSE
    try:
        df = yf.download(
            symbols, period="5d", interval="1d",
            group_by="ticker", auto_adjust=False, progress=False, threads=True,
        )
    except Exception as e:  # noqa: BLE001
        log.warning("watchlist download failed: %s", e)
        return []

    out: list[dict[str, Any]] = []
    multi = len(symbols) > 1
    for s in symbols:
        try:
            closes = (df[s]["Close"] if multi else df["Close"]).dropna()
            if len(closes) < 2:
                continue
            last = _clean_float(closes.iloc[-1])
            prev = _clean_float(closes.iloc[-2])
            if last is None or prev is None or not prev:
                continue
            out.append(
                {
                    "symbol": s.rsplit(".", 1)[0],
                    "last": last,
                    "change_pct": (last - prev) / prev * 100.0,
                }
            )
        except Exception:  # noqa: BLE001
            continue
    return out


def fetch_live_quote(yf_symbol: str) -> dict[str, Any]:
    """Fetch a near-real-time quote snapshot for one symbol via yfinance fast_info.

    Yahoo data is delayed (typically ~15 min for NSE/BSE), not true tick data.
    Never raises — returns {} with an "error" key on failure so the UI can
    degrade gracefully.
    """
    try:
        fi = yf.Ticker(yf_symbol).fast_info
    except Exception as e:  # noqa: BLE001
        return {"error": f"live quote fetch failed: {e}"}

    def _g(key: str) -> float | None:
        try:
            return _clean_float(fi.get(key)) if hasattr(fi, "get") else _clean_float(fi[key])
        except (KeyError, AttributeError, TypeError):
            return None

    last = _g("lastPrice")
    prev = _g("previousClose") or _g("regularMarketPreviousClose")
    change = (last - prev) if (last is not None and prev is not None) else None
    change_pct = (change / prev * 100.0) if (change is not None and prev) else None

    currency = None
    try:
        currency = fi.get("currency") if hasattr(fi, "get") else fi["currency"]
    except (KeyError, AttributeError, TypeError):
        currency = None

    return {
        "last_price": last,
        "previous_close": prev,
        "change": change,
        "change_pct": change_pct,
        "open": _g("open"),
        "day_high": _g("dayHigh"),
        "day_low": _g("dayLow"),
        "volume": _g("lastVolume"),
        "market_cap": _g("marketCap"),
        "currency": currency,
    }


def fetch_price_history(tk: yf.Ticker, period: str) -> tuple[list[PriceBar], list[str]]:
    """Fetch daily OHLCV bars for the given period (e.g. '2y')."""
    warnings: list[str] = []
    try:
        df: pd.DataFrame = tk.history(period=period, interval="1d", auto_adjust=False)
    except Exception as e:  # noqa: BLE001 - network/parse errors vary widely
        warnings.append(f"price history fetch failed: {e}")
        return [], warnings

    if df is None or df.empty:
        warnings.append("price history empty")
        return [], warnings

    bars: list[PriceBar] = []
    for idx, row in df.iterrows():
        try:
            bar_date = idx.date() if hasattr(idx, "date") else date.fromisoformat(str(idx)[:10])
            o, h, low_, c = (
                _clean_float(row.get("Open")),
                _clean_float(row.get("High")),
                _clean_float(row.get("Low")),
                _clean_float(row.get("Close")),
            )
            vol = row.get("Volume")
            if None in (o, h, low_, c):
                continue  # skip incomplete bar
            bars.append(
                PriceBar(
                    bar_date=bar_date,
                    open=o,
                    high=h,
                    low=low_,
                    close=c,
                    volume=int(vol) if vol is not None and not math.isnan(vol) else 0,
                )
            )
        except Exception as e:  # noqa: BLE001
            warnings.append(f"skipped a price bar: {e}")
            continue

    if not bars:
        warnings.append("no valid price bars parsed")
    return bars, warnings


def _quarterly_financials(tk: yf.Ticker) -> tuple[list[dict], list[str]]:
    """Extract quarterly income-statement rows as period-keyed dicts."""
    warnings: list[str] = []
    try:
        qf = tk.quarterly_financials  # DataFrame: rows=metrics, cols=period timestamps
    except Exception as e:  # noqa: BLE001
        return [], [f"quarterly financials fetch failed: {e}"]

    if qf is None or qf.empty:
        return [], ["quarterly financials empty"]

    # Keep a curated set of widely-available line items.
    wanted = [
        "Total Revenue",
        "Gross Profit",
        "Operating Income",
        "Net Income",
        "Basic EPS",
        "Diluted EPS",
    ]
    records: list[dict] = []
    try:
        for period in qf.columns:
            rec: dict = {"period": str(getattr(period, "date", lambda: period)())[:10]}
            for metric in wanted:
                if metric in qf.index:
                    rec[metric] = _clean_float(qf.loc[metric, period])
            records.append(rec)
    except Exception as e:  # noqa: BLE001
        warnings.append(f"quarterly financials parse issue: {e}")
    return records, warnings


def fetch_fundamentals(tk: yf.Ticker) -> tuple[Fundamentals, list[str]]:
    """Fetch valuation + financial-health metrics."""
    warnings: list[str] = []
    try:
        info: dict = tk.info or {}
    except Exception as e:  # noqa: BLE001
        info = {}
        warnings.append(f"info fetch failed: {e}")

    f = Fundamentals(
        market_cap=_clean_float(info.get("marketCap")),
        trailing_pe=_clean_float(info.get("trailingPE")),
        forward_pe=_clean_float(info.get("forwardPE")),
        price_to_book=_clean_float(info.get("priceToBook")),
        debt_to_equity=_clean_float(info.get("debtToEquity")),
        return_on_equity=_clean_float(info.get("returnOnEquity")),
        profit_margin=_clean_float(info.get("profitMargins")),
        revenue_growth=_clean_float(info.get("revenueGrowth")),
        earnings_growth=_clean_float(info.get("earningsGrowth")),
        dividend_yield=_clean_float(info.get("dividendYield")),
        beta=_clean_float(info.get("beta")),
        fifty_two_week_high=_clean_float(info.get("fiftyTwoWeekHigh")),
        fifty_two_week_low=_clean_float(info.get("fiftyTwoWeekLow")),
        currency=info.get("currency"),
    )

    quarters, qwarn = _quarterly_financials(tk)
    f.quarterly_financials = quarters
    warnings.extend(qwarn)

    # Flag the most important gaps explicitly.
    if f.trailing_pe is None and f.forward_pe is None:
        warnings.append("no P/E available")
    if f.debt_to_equity is None:
        warnings.append("no debt-to-equity available")

    return f, warnings
