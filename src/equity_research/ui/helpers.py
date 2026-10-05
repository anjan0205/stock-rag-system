"""Presentation helpers: CollectedData -> DataFrames, Plotly figures, formatted metrics.

Kept free of Streamlit imports so the functions can be unit-tested headlessly.
Everything here is derived strictly from the validated `CollectedData` payload;
missing values are surfaced as ``None`` / "N/A" rather than invented.
"""
from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from typing import Any

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from ..data.schemas import CollectedData

# Common currency symbols for compact display.
_CURRENCY_SYMBOLS = {"INR": "₹", "USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥"}
_IST = timezone(timedelta(hours=5, minutes=30))


def currency_symbol(currency: str | None) -> str:
    """Map an ISO currency code to a display symbol, defaulting to the code."""
    if not currency:
        return ""
    return _CURRENCY_SYMBOLS.get(currency.upper(), currency + " ")


def market_status() -> dict[str, Any]:
    """Whether NSE/BSE is currently open, based on IST clock (09:15–15:30 Mon–Fri).

    A convenience indicator only — it does not account for exchange holidays.
    """
    now = datetime.now(_IST)
    is_weekday = now.weekday() < 5  # Mon=0 .. Fri=4
    open_t, close_t = time(9, 15), time(15, 30)
    is_open = is_weekday and open_t <= now.time() <= close_t
    return {"is_open": is_open, "ist_time": now.strftime("%H:%M IST"), "weekday": is_weekday}

# Neon-on-dark palette (colorblind-safe hues, tuned for a glass/dark theme).
_UP = "#2ce6a8"       # neon mint, gains
_DOWN = "#ff5d73"     # neon coral, losses
_ACCENT = "#7c5cff"   # electric violet, primary series
_ACCENT2 = "#38bdf8"  # cyan, secondary series
_MUTED = "#5b6478"    # slate grey, volume / secondary
_GRID = "rgba(255,255,255,0.06)"


def _apply_dark(fig: go.Figure, height: int) -> go.Figure:
    """Common transparent dark styling so charts sit on the glass UI."""
    fig.update_layout(
        height=height,
        margin=dict(l=10, r=10, t=30, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#c7cede", family="Inter, sans-serif"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                    bgcolor="rgba(0,0,0,0)"),
        hovermode="x unified",
        hoverlabel=dict(bgcolor="rgba(20,24,34,0.95)", bordercolor="rgba(255,255,255,0.1)"),
    )
    fig.update_xaxes(gridcolor=_GRID, zeroline=False, showline=False)
    fig.update_yaxes(gridcolor=_GRID, zeroline=False, showline=False)
    return fig


# --------------------------------------------------------------------------- #
# Formatting                                                                   #
# --------------------------------------------------------------------------- #
def human_number(value: float | int | None, currency: str | None = None) -> str:
    """Format a large number with K/M/B/T suffixes and optional currency."""
    if value is None:
        return "N/A"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "N/A"

    sign = "-" if v < 0 else ""
    v = abs(v)
    for suffix, threshold in (("T", 1e12), ("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if v >= threshold:
            body = f"{v / threshold:.2f}{suffix}"
            break
    else:
        body = f"{v:,.2f}"

    prefix = currency_symbol(currency)
    return f"{prefix}{sign}{body}"


def as_pct(value: float | None, already_percent: bool = False) -> str:
    """Render a ratio (0.18) or percentage (18.0) as '18.00%'."""
    if value is None:
        return "N/A"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "N/A"
    if not already_percent:
        v *= 100.0
    return f"{v:.2f}%"


def as_ratio(value: float | None, digits: int = 2) -> str:
    """Render a plain numeric ratio (P/E, beta, ...)."""
    if value is None:
        return "N/A"
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "N/A"


# --------------------------------------------------------------------------- #
# Price                                                                        #
# --------------------------------------------------------------------------- #
def price_dataframe(data: CollectedData) -> pd.DataFrame:
    """Build an OHLCV DataFrame (date-indexed) from the collected price bars."""
    if not data.price_history:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    rows = [
        {
            "date": b.bar_date,
            "open": b.open,
            "high": b.high,
            "low": b.low,
            "close": b.close,
            "volume": b.volume,
        }
        for b in data.price_history
    ]
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date").sort_index()


def price_metrics(data: CollectedData) -> dict[str, Any]:
    """Compute headline price stats: latest close, period change, 52w range."""
    df = price_dataframe(data)
    if df.empty:
        return {}
    latest = df["close"].iloc[-1]
    first = df["close"].iloc[0]
    change_abs = latest - first
    change_pct = (change_abs / first * 100.0) if first else None
    return {
        "latest_close": latest,
        "period_start_close": first,
        "period_change_abs": change_abs,
        "period_change_pct": change_pct,
        "period_high": df["high"].max(),
        "period_low": df["low"].min(),
        "avg_volume": df["volume"].mean(),
    }


def candlestick_figure(data: CollectedData, currency: str | None = None) -> go.Figure:
    """Candlestick price chart with a volume subplot underneath."""
    df = price_dataframe(data)
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.75, 0.25],
        subplot_titles=("", ""),
    )

    if df.empty:
        fig.add_annotation(text="No price history available", showarrow=False)
        fig.update_layout(height=520, template="plotly_white")
        return fig

    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            name="Price",
            increasing_line_color=_UP,
            decreasing_line_color=_DOWN,
        ),
        row=1,
        col=1,
    )

    # 50-day simple moving average for trend context (only if enough data).
    if len(df) >= 50:
        sma = df["close"].rolling(window=50).mean()
        fig.add_trace(
            go.Scatter(
                x=df.index, y=sma, name="SMA 50",
                line=dict(color=_ACCENT, width=1.4),
            ),
            row=1,
            col=1,
        )

    # Color volume bars by up/down day.
    vol_colors = [
        _UP if c >= o else _DOWN
        for o, c in zip(df["open"], df["close"])
    ]
    fig.add_trace(
        go.Bar(x=df.index, y=df["volume"], name="Volume", marker_color=vol_colors, opacity=0.6),
        row=2,
        col=1,
    )

    ccy = f" ({currency})" if currency else ""
    fig.update_yaxes(title_text=f"Price{ccy}", row=1, col=1)
    fig.update_yaxes(title_text="Volume", row=2, col=1)
    fig.update_layout(xaxis_rangeslider_visible=False)
    return _apply_dark(fig, height=560)


def area_price_figure(data: CollectedData, currency: str | None = None) -> go.Figure:
    """Glowing gradient area chart of the closing price — the hero visual."""
    df = price_dataframe(data)
    fig = go.Figure()
    if df.empty:
        fig.add_annotation(text="No price history available", showarrow=False,
                           font=dict(color="#8d99ae"))
        return _apply_dark(fig, height=460)

    up = df["close"].iloc[-1] >= df["close"].iloc[0]
    line_color = _UP if up else _DOWN
    fill = "rgba(44,230,168,0.16)" if up else "rgba(255,93,115,0.16)"

    fig.add_trace(
        go.Scatter(
            x=df.index, y=df["close"], mode="lines", name="Close",
            line=dict(color=line_color, width=2.4, shape="spline"),
            fill="tozeroy", fillcolor=fill,
        )
    )
    # Soft glow: a wider, translucent copy of the line underneath.
    fig.add_trace(
        go.Scatter(
            x=df.index, y=df["close"], mode="lines", name="",
            line=dict(color=line_color, width=8), opacity=0.10,
            hoverinfo="skip", showlegend=False,
        )
    )
    if len(df) >= 50:
        sma = df["close"].rolling(50).mean()
        fig.add_trace(
            go.Scatter(x=df.index, y=sma, name="SMA 50",
                       line=dict(color=_ACCENT2, width=1.3, dash="dot"))
        )

    lo, hi = df["close"].min(), df["close"].max()
    pad = (hi - lo) * 0.08 or 1
    fig.update_yaxes(range=[lo - pad, hi + pad])
    fig.update_xaxes(
        rangeselector=dict(
            buttons=[
                dict(count=1, label="1M", step="month", stepmode="backward"),
                dict(count=6, label="6M", step="month", stepmode="backward"),
                dict(count=1, label="1Y", step="year", stepmode="backward"),
                dict(step="all", label="Max"),
            ],
            bgcolor="rgba(124,92,255,0.12)", activecolor="rgba(124,92,255,0.5)",
            font=dict(color="#c7cede"),
        )
    )
    return _apply_dark(fig, height=460)


def range_gauge(data: CollectedData, last_price: float | None) -> go.Figure | None:
    """Gauge showing where the latest price sits within its 52-week range."""
    f = data.fundamentals
    lo, hi = f.fifty_two_week_low, f.fifty_two_week_high
    if last_price is None or lo is None or hi is None or hi <= lo:
        return None
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=last_price,
            number=dict(font=dict(color="#e6e9ef", size=26)),
            gauge=dict(
                axis=dict(range=[lo, hi], tickcolor="#5b6478",
                          tickfont=dict(color="#8d99ae", size=10)),
                bar=dict(color=_ACCENT, thickness=0.28),
                bgcolor="rgba(255,255,255,0.03)",
                borderwidth=0,
                steps=[
                    dict(range=[lo, lo + (hi - lo) / 2], color="rgba(255,93,115,0.12)"),
                    dict(range=[lo + (hi - lo) / 2, hi], color="rgba(44,230,168,0.12)"),
                ],
            ),
            title=dict(text="52-Week Range Position", font=dict(color="#8d99ae", size=13)),
        )
    )
    return _apply_dark(fig, height=240)


# --------------------------------------------------------------------------- #
# Fundamentals                                                                 #
# --------------------------------------------------------------------------- #
def fundamentals_rows(data: CollectedData) -> list[dict[str, str]]:
    """Return a list of {metric, value} rows for a fundamentals table."""
    f = data.fundamentals
    ccy = f.currency
    return [
        {"Metric": "Market Cap", "Value": human_number(f.market_cap, ccy)},
        {"Metric": "Trailing P/E", "Value": as_ratio(f.trailing_pe)},
        {"Metric": "Forward P/E", "Value": as_ratio(f.forward_pe)},
        {"Metric": "Price / Book", "Value": as_ratio(f.price_to_book)},
        {"Metric": "Debt / Equity", "Value": as_ratio(f.debt_to_equity)},
        {"Metric": "Return on Equity", "Value": as_pct(f.return_on_equity)},
        {"Metric": "Profit Margin", "Value": as_pct(f.profit_margin)},
        {"Metric": "Revenue Growth", "Value": as_pct(f.revenue_growth)},
        {"Metric": "Earnings Growth", "Value": as_pct(f.earnings_growth)},
        {"Metric": "Dividend Yield", "Value": as_pct(f.dividend_yield)},
        {"Metric": "Beta", "Value": as_ratio(f.beta)},
        {"Metric": "52-Week High", "Value": human_number(f.fifty_two_week_high, ccy)},
        {"Metric": "52-Week Low", "Value": human_number(f.fifty_two_week_low, ccy)},
    ]


def fundamentals_dict(data: CollectedData) -> dict[str, Any]:
    """Compact fundamentals dict passed to the RAG generator as context."""
    f = data.fundamentals
    return {
        "market_cap": f.market_cap,
        "trailing_pe": f.trailing_pe,
        "forward_pe": f.forward_pe,
        "price_to_book": f.price_to_book,
        "debt_to_equity": f.debt_to_equity,
        "return_on_equity": f.return_on_equity,
        "profit_margin": f.profit_margin,
        "revenue_growth": f.revenue_growth,
        "earnings_growth": f.earnings_growth,
        "beta": f.beta,
        "currency": f.currency,
    }


def price_summary_dict(data: CollectedData, period: str) -> dict[str, Any]:
    """Compact price summary dict passed to the RAG generator as context."""
    if not data.price_history:
        return {}
    p_start, p_end = data.price_history[0], data.price_history[-1]
    return {
        "period": period,
        "start_date": p_start.bar_date,
        "start_close": p_start.close,
        "end_date": p_end.bar_date,
        "end_close": p_end.close,
    }


def quarterly_financials_frame(data: CollectedData) -> pd.DataFrame:
    """Tidy the quarterly financials list-of-dicts into a period-indexed frame."""
    records = data.fundamentals.quarterly_financials
    if not records:
        return pd.DataFrame()
    df = pd.DataFrame(records)
    if "period" not in df.columns:
        return pd.DataFrame()
    df["period"] = pd.to_datetime(df["period"], errors="coerce")
    df = df.dropna(subset=["period"]).sort_values("period").set_index("period")
    return df


def quarterly_financials_figure(data: CollectedData) -> go.Figure | None:
    """Grouped bar chart of Revenue / Operating Income / Net Income per quarter."""
    df = quarterly_financials_frame(data)
    if df.empty:
        return None

    wanted = [c for c in ("Total Revenue", "Operating Income", "Net Income") if c in df.columns]
    if not wanted:
        return None

    colors = {"Total Revenue": _ACCENT, "Operating Income": _UP, "Net Income": _ACCENT2}
    fig = go.Figure()
    for col in wanted:
        fig.add_trace(
            go.Bar(
                x=df.index.strftime("%Y-%m"),
                y=df[col],
                name=col,
                marker_color=colors.get(col, _ACCENT),
                marker_line_width=0,
            )
        )
    fig.update_layout(barmode="group", yaxis_title="Amount")
    return _apply_dark(fig, height=380)


def news_rows(data: CollectedData) -> list[dict[str, Any]]:
    """Return news items sorted newest-first for display."""
    items = [
        {
            "title": a.title,
            "source": a.source or "",
            "published": a.published,
            "url": a.url,
            "summary": a.summary or "",
        }
        for a in data.news
    ]
    items.sort(key=lambda r: (r["published"] is not None, r["published"]), reverse=True)
    return items
