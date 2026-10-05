"""Recent news via Google News RSS.

Google News exposes a keyword RSS feed with no API key. We query for the
company name + ticker, restrict to the lookback window, and return validated
NewsArticle objects. Every article keeps its source URL so downstream
sentiment claims are traceable.
"""
from __future__ import annotations

import urllib.parse
from datetime import datetime, timedelta, timezone

import feedparser

from ..logging_setup import get_logger
from .schemas import NewsArticle

log = get_logger(__name__)

_GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"


def _parse_published(entry) -> datetime | None:
    parsed = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if parsed is None:
        return None
    try:
        return datetime(*parsed[:6], tzinfo=timezone.utc)
    except Exception:  # noqa: BLE001
        return None


def _source_name(entry) -> str | None:
    src = getattr(entry, "source", None)
    if src is not None:
        title = getattr(src, "title", None)
        if title:
            return title
    return None


def fetch_news(
    company_name: str | None,
    base_symbol: str,
    lookback_days: int = 30,
    max_articles: int = 40,
) -> tuple[list[NewsArticle], list[str]]:
    """Fetch news from the last `lookback_days` days."""
    warnings: list[str] = []

    # Build a query biased toward the company; fall back to symbol alone.
    terms = []
    if company_name:
        terms.append(f'"{company_name}"')
    terms.append(base_symbol)
    query = urllib.parse.quote(" ".join(terms) + " stock")
    url = _GOOGLE_NEWS_RSS.format(query=query)

    try:
        feed = feedparser.parse(url)
    except Exception as e:  # noqa: BLE001
        return [], [f"news fetch failed: {e}"]

    if getattr(feed, "bozo", 0) and not feed.entries:
        return [], [f"news feed parse error: {getattr(feed, 'bozo_exception', 'unknown')}"]

    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    articles: list[NewsArticle] = []
    dropped_old = 0

    for entry in feed.entries:
        published = _parse_published(entry)
        if published is not None and published < cutoff:
            dropped_old += 1
            continue
        link = getattr(entry, "link", None)
        title = getattr(entry, "title", None)
        if not link or not title:
            continue
        articles.append(
            NewsArticle(
                title=title,
                url=link,
                source=_source_name(entry),
                published=published,
                summary=getattr(entry, "summary", None),
            )
        )
        if len(articles) >= max_articles:
            break

    if not articles:
        warnings.append(
            f"no news within {lookback_days}d (dropped {dropped_old} older items)"
        )
    return articles, warnings
