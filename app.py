"""Equity Research RAG — Streamlit dashboard.

A research workbench over the collect -> ingest -> retrieve -> generate pipeline.
Search any listed Indian company, watch a live (delayed) quote and ticker tape,
explore price / fundamentals / news, and ask grounded, cited questions answered
by Gemini over the Chroma vector store.

Run:
    streamlit run app.py
"""
from __future__ import annotations

import html
import sys
from pathlib import Path

# Ensure `src` is importable (package is run from source, not pip-installed).
ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import streamlit as st  # noqa: E402
import streamlit.components.v1 as components  # noqa: E402

from equity_research.config import get_settings  # noqa: E402
from equity_research.data.collector import collect, ingest_to_chroma  # noqa: E402
from equity_research.data.price import fetch_live_quote, fetch_watchlist_quotes  # noqa: E402
from equity_research.data.schemas import Exchange  # noqa: E402
from equity_research.data.search import CompanyHit, search_companies  # noqa: E402
from equity_research.llm.client import GeminiClient  # noqa: E402
from equity_research.llm.generator import RAGGenerator  # noqa: E402
from equity_research.logging_setup import setup_logging  # noqa: E402
from equity_research.rag.store import DocumentStore  # noqa: E402
from equity_research.ui import helpers as H  # noqa: E402
from equity_research.ui.styles import CSS  # noqa: E402

# --------------------------------------------------------------------------- #
# Page + styling                                                               #
# --------------------------------------------------------------------------- #
st.set_page_config(
    page_title="Equity Research RAG",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(CSS, unsafe_allow_html=True)


@st.cache_resource(show_spinner=False)
def _bootstrap():
    settings = get_settings()
    settings.ensure_dirs()
    setup_logging(settings.log_path)
    store = DocumentStore(settings.chroma_path)
    client = GeminiClient()
    return settings, store, client


settings, store, client = _bootstrap()


@st.cache_data(ttl=300, show_spinner=False)
def _cached_search(query: str) -> list[CompanyHit]:
    return search_companies(query)


@st.cache_data(ttl=15, show_spinner=False)
def _cached_live_quote(symbol: str) -> dict:
    return fetch_live_quote(symbol)


@st.cache_data(ttl=120, show_spinner=False)
def _cached_watchlist() -> list[dict]:
    return fetch_watchlist_quotes()


# --------------------------------------------------------------------------- #
# Session state                                                                #
# --------------------------------------------------------------------------- #
def _init_state() -> None:
    st.session_state.setdefault("data", None)
    st.session_state.setdefault("chunks_stored", 0)
    st.session_state.setdefault("total_chunks", 0)
    st.session_state.setdefault("chat", [])
    st.session_state.setdefault("last_ticker", None)
    st.session_state.setdefault("hits", [])
    st.session_state.setdefault("n_results", 5)


_init_state()


def _fetch(hit: CompanyHit, pdf_urls: list[str]) -> None:
    with st.status(f"Loading {hit.name}...", expanded=True) as status:
        st.write("Collecting prices, fundamentals, news, and documents...")
        data = collect(hit.symbol, settings=settings, default_exchange=hit.exchange, pdf_urls=pdf_urls or None)
        st.write("Ingesting documents into the vector store...")
        stored = ingest_to_chroma(data, store=store)
        total = store.count_for_ticker(data.ticker)
        st.session_state["data"] = data
        st.session_state["chunks_stored"] = stored
        st.session_state["total_chunks"] = total
        if st.session_state["last_ticker"] != data.ticker:
            st.session_state["chat"] = []
        st.session_state["last_ticker"] = data.ticker
        status.update(
            label=f"Loaded {data.company_name or data.ticker} — {stored} new chunks ({total} total)",
            state="complete", expanded=False,
        )


def _answer(user_query: str) -> None:
    data = st.session_state["data"]
    hits = store.query(data.ticker, query_text=user_query, n_results=st.session_state["n_results"])
    generator = RAGGenerator(client=client)
    answer = generator.generate_answer(
        ticker=data.ticker, user_query=user_query, retrieved_chunks=hits,
        fundamentals=H.fundamentals_dict(data),
        price_summary=H.price_summary_dict(data, settings.price_history_period),
    )
    st.session_state["chat"].append({"role": "assistant", "content": answer, "citations": hits})


# --------------------------------------------------------------------------- #
# Ticker tape                                                                  #
# --------------------------------------------------------------------------- #
def render_ticker_tape() -> None:
    """Render the scrolling ticker tape as a self-contained iframe.

    Uses components.html (an isolated iframe) rather than st.markdown so the
    markup and animation are guaranteed to render — no dependency on Streamlit's
    HTML sanitizer or the injected page stylesheet.
    """
    quotes = _cached_watchlist()
    if quotes:
        parts = []
        for q in quotes:
            pct = q.get("change_pct")
            up = pct is not None and pct >= 0
            arrow = "▲" if up else "▼"
            color = "#2ce6a8" if up else "#ff5d73"
            pct_str = f"{arrow} {abs(pct):.2f}%" if pct is not None else ""
            parts.append(
                f'<span class="it"><b>{html.escape(q["symbol"])}</b>'
                f'<span class="px">{q["last"]:,.2f}</span>'
                f'<span class="cg" style="color:{color}">{pct_str}</span></span>'
            )
        row = "".join(parts)
        inner = f'<div class="track">{row}{row}</div>'
    else:
        inner = '<div class="track"><span class="it"><b>Live market feed unavailable — retrying…</b></span></div>'

    doc = f"""
    <!DOCTYPE html><html><head><meta charset="utf-8"><style>
      @import url('https://fonts.googleapis.com/css2?family=Inter:wght@500;700&family=JetBrains+Mono:wght@700&display=swap');
      * {{ margin:0; padding:0; box-sizing:border-box; }}
      html,body {{ background:transparent; overflow:hidden; }}
      .tape {{
        display:flex; align-items:center; height:46px; overflow:hidden; white-space:nowrap;
        border:1px solid rgba(124,92,255,0.4); border-radius:14px;
        background:rgba(23,27,38,0.9); box-shadow:0 4px 20px rgba(0,0,0,0.3);
        font-family:'Inter',sans-serif;
      }}
      .track {{ display:inline-block; white-space:nowrap; will-change:transform;
        animation:tape 42s linear infinite; }}
      .tape:hover .track {{ animation-play-state:paused; }}
      @keyframes tape {{ 0%{{transform:translateX(0);}} 100%{{transform:translateX(-50%);}} }}
      .it {{ display:inline-flex; align-items:baseline; gap:8px; margin:0 26px; font-size:.92rem; }}
      .it b {{ color:#e6e9ef; letter-spacing:.02em; }}
      .px {{ font-family:'JetBrains Mono',monospace; color:#8a93a6; }}
      .cg {{ font-family:'JetBrains Mono',monospace; font-weight:700; }}
    </style></head>
    <body><div class="tape">{inner}</div></body></html>
    """
    components.html(doc, height=56)


# --------------------------------------------------------------------------- #
# Sidebar — search & controls                                                  #
# --------------------------------------------------------------------------- #
with st.sidebar:
    st.title("📈 Equity Research RAG")
    st.caption("Grounded, cited research for any Indian-listed company.")

    query = st.text_input(
        "Search company or symbol",
        placeholder="e.g. Reliance, Tata Motors, INFY",
        help="Searches all NSE/BSE listed equities via Yahoo Finance.",
    ).strip()

    if query:
        found = _cached_search(query)
        st.session_state["hits"] = found
        if not found:
            st.info("No Indian equities matched. Try a different name or symbol.", icon="🔎")

    hits = st.session_state["hits"]
    selected: CompanyHit | None = None
    if hits:
        selected = st.selectbox("Matches", options=hits, format_func=lambda h: h.label)

    with st.expander("Advanced", expanded=False):
        pdf_url_text = st.text_area(
            "Extra PDF URLs (one per line)",
            help="Earnings decks or filings to include in retrieval.",
            placeholder="https://example.com/investor-deck.pdf",
        )
        st.session_state["n_results"] = st.slider("Chunks retrieved per question", 3, 12, 5)
    pdf_urls = [u.strip() for u in pdf_url_text.splitlines() if u.strip()] if pdf_url_text else []

    load_clicked = st.button("Load & analyze", type="primary", use_container_width=True, disabled=selected is None)

    st.divider()
    if client.is_available:
        st.success("Gemini API key detected", icon="✅")
    else:
        st.warning("No GEMINI_API_KEY — chat answers disabled. Set it in .env.", icon="⚠️")
    st.caption(f"Model: `{settings.gemini_model}`")

if load_clicked and selected is not None:
    _fetch(selected, pdf_urls)


# --------------------------------------------------------------------------- #
# Live glass hero (auto-refreshing fragment)                                   #
# --------------------------------------------------------------------------- #
@st.fragment(run_every=30)
def live_hero() -> None:
    data = st.session_state["data"]
    if data is None:
        return
    q = _cached_live_quote(data.ticker)
    sym = H.currency_symbol(q.get("currency") or data.fundamentals.currency)
    ms = H.market_status()

    change, change_pct, price = q.get("change"), q.get("change_pct"), q.get("last_price")
    cls, arrow = "flat", "→"
    if change is not None:
        cls, arrow = ("up", "▲") if change >= 0 else ("down", "▼")

    price_str = f"{sym}{price:,.2f}" if price is not None else "N/A"
    chg_str = (f"{arrow} {sym}{abs(change):,.2f} ({change_pct:+.2f}%)"
               if change is not None and change_pct is not None else "")

    status_chip = ('<span class="chip open">● Market Open</span>' if ms["is_open"]
                   else '<span class="chip closed">● Market Closed</span>')
    meta_chips = "".join(
        f'<span class="chip">{html.escape(str(b))}</span>'
        for b in (data.exchange.value, data.sector, data.industry) if b
    )
    name = html.escape(data.company_name or data.ticker)

    st.markdown(
        f"""
        <div class="hero-wrap"><div class="hero-card">
          <div class="hero-top">
            <div>
              <div class="hero-name">{name}</div>
              <div class="hero-sub">{html.escape(data.ticker)}</div>
            </div>
            <div>{status_chip}</div>
          </div>
          <div class="hero-price-row">
            <span class="hero-price">{price_str}</span>
            <span class="hero-chg {cls}">{chg_str}</span>
          </div>
          <div class="hero-sub" style="margin-top:14px">{meta_chips}</div>
        </div></div>
        """,
        unsafe_allow_html=True,
    )

    cols = st.columns(5)
    cols[0].metric("Open", H.human_number(q.get("open"), q.get("currency")))
    cols[1].metric("Prev Close", H.human_number(q.get("previous_close"), q.get("currency")))
    cols[2].metric("Day High", H.human_number(q.get("day_high"), q.get("currency")))
    cols[3].metric("Day Low", H.human_number(q.get("day_low"), q.get("currency")))
    cols[4].metric("Volume", H.human_number(q.get("volume")))
    st.caption(f"Live quote (Yahoo, ~15-min delayed) · refreshes every 30s · {ms['ist_time']}")


# --------------------------------------------------------------------------- #
# Main area                                                                    #
# --------------------------------------------------------------------------- #
render_ticker_tape()
data = st.session_state["data"]

if data is None:
    st.title("Equity Research RAG")
    st.markdown(
        """
Turn raw market data into **grounded, cited research** for any Indian-listed company.

**Get started**
1. **Search** a company by name or symbol in the sidebar (e.g. *Reliance*, *Tata Motors*, *INFY*).
2. Pick the right match and click **Load & analyze**.
3. Watch the **live quote**, then explore **Overview**, **Financials**, and **News**.
4. Ask questions in **Research Chat** — answers are generated only from retrieved evidence, with citations.
        """
    )
    st.info("No company loaded yet. Search in the sidebar to begin.", icon="👈")
    st.stop()

ccy = data.fundamentals.currency
live_hero()
st.divider()

tab_overview, tab_fin, tab_news, tab_chat, tab_quality = st.tabs(
    ["📊 Overview", "🧮 Financials", "📰 News", "💬 Research Chat", "🔍 Data Quality"]
)

# ---- Overview ----
with tab_overview:
    pm = H.price_metrics(data)
    top_l, top_r = st.columns([2.6, 1])
    with top_l:
        c1, c2 = st.columns([3, 1])
        c1.subheader("Price")
        chart_kind = c2.radio("Chart", ["Area", "Candles"], horizontal=True, label_visibility="collapsed")
        fig = (H.area_price_figure(data, currency=ccy) if chart_kind == "Area"
               else H.candlestick_figure(data, currency=ccy))
        st.plotly_chart(fig, use_container_width=True)
    with top_r:
        gauge = H.range_gauge(data, pm.get("latest_close"))
        if gauge is not None:
            st.plotly_chart(gauge, use_container_width=True)
        else:
            st.info("52-week range unavailable.", icon="ℹ️")

    o1, o2, o3, o4 = st.columns(4)
    o1.metric("Period High", H.human_number(pm.get("period_high"), ccy))
    o2.metric("Period Low", H.human_number(pm.get("period_low"), ccy))
    o3.metric("52W High", H.human_number(data.fundamentals.fifty_two_week_high, ccy))
    o4.metric("52W Low", H.human_number(data.fundamentals.fifty_two_week_low, ccy))
    st.caption(
        f"Price period: {settings.price_history_period} · {len(data.price_history)} trading days · "
        f"avg volume {H.human_number(pm.get('avg_volume'))}"
    )

# ---- Financials ----
with tab_fin:
    left, right = st.columns([1, 1])
    with left:
        st.subheader("Key Metrics")
        st.dataframe(H.fundamentals_rows(data), hide_index=True, use_container_width=True)
    with right:
        st.subheader("Quarterly Results")
        fig = H.quarterly_financials_figure(data)
        if fig is not None:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No quarterly financials available for this ticker.", icon="ℹ️")

    qf = H.quarterly_financials_frame(data)
    if not qf.empty:
        with st.expander("Quarterly financials table"):
            st.dataframe(qf, use_container_width=True)

# ---- News ----
with tab_news:
    st.subheader(f"Recent News ({settings.news_lookback_days}-day lookback)")
    rows = H.news_rows(data)
    if not rows:
        st.info("No recent news articles were found.", icon="ℹ️")
    else:
        for r in rows:
            when = r["published"].strftime("%Y-%m-%d %H:%M") if r["published"] else "date unknown"
            src = f" · {r['source']}" if r["source"] else ""
            st.markdown(f"**[{r['title']}]({r['url']})**")
            st.caption(f"{when}{src}")
            if r["summary"]:
                st.write(r["summary"])
            st.divider()

# ---- Research Chat ----
with tab_chat:
    st.subheader("Ask about this company")
    st.caption(
        "Answers are generated only from retrieved documents, news, fundamentals, "
        "and price data — with citations. Nothing is fabricated."
    )
    for msg in st.session_state["chat"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("citations"):
                with st.expander(f"Sources ({len(msg['citations'])})"):
                    for i, h in enumerate(msg["citations"], start=1):
                        meta = h.get("metadata", {})
                        title = meta.get("title", "Untitled")
                        stype = meta.get("source_type", "unknown")
                        url = meta.get("url", "")
                        dist = h.get("distance")
                        line = f"**[{i}]** {title} · _{stype}_"
                        if dist is not None:
                            line += f" · similarity {max(0.0, 1.0 - dist):.2f}"
                        st.markdown(line)
                        if url:
                            st.caption(url)

    if not client.is_available:
        st.warning("Set GEMINI_API_KEY in your .env to enable chat answers.", icon="⚠️")

    prompt = st.chat_input("e.g. What are the main revenue drivers and key risks?", disabled=not client.is_available)
    if prompt:
        st.session_state["chat"].append({"role": "user", "content": prompt, "citations": []})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Retrieving evidence and generating a grounded answer..."):
                try:
                    _answer(prompt)
                    st.rerun()
                except Exception as e:  # noqa: BLE001
                    st.error(f"Generation failed: {e}")

# ---- Data Quality ----
with tab_quality:
    st.subheader("Collection Report")
    q1, q2, q3, q4 = st.columns(4)
    q1.metric("Price bars", len(data.price_history))
    q2.metric("News articles", len(data.news))
    q3.metric("Documents", len(data.documents))
    q4.metric("Chunks in store", st.session_state["total_chunks"])
    st.caption(
        f"Last fetch ingested {st.session_state['chunks_stored']} new chunks. "
        f"Data collected at {data.collected_at:%Y-%m-%d %H:%M UTC}."
    )
    if data.documents:
        st.markdown("**Source documents**")
        st.dataframe(
            [{"Title": d.title, "Type": d.source_type.value, "URL": d.url or ""} for d in data.documents],
            hide_index=True, use_container_width=True,
        )
    if data.warnings:
        with st.expander(f"⚠️ Collection warnings ({len(data.warnings)})"):
            for w in data.warnings:
                st.write(f"- {w}")
    else:
        st.success("No collection warnings.", icon="✅")
