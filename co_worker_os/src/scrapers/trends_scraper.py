"""Google Trends scraper: free, unofficial, no API key -- via `pytrends`, a
thin wrapper over Google Trends' public (unauthenticated) endpoints. Same
zero-paid-API posture as web_scraper.py/social_scraper.py (see CLAUDE.md
invariant 2).

Feeds demand-signal data (interest over time + related queries) into the GTM
& Research agent's `scraped_context`, alongside Reddit/web research -- never
invented market statistics, only what Google Trends actually reports.
"""

from __future__ import annotations

from typing import Protocol


class TrendsClient(Protocol):
    """Shape pytrends' TrendReq exposes, narrowed to what this module uses --
    lets tests inject a fake without needing pytrends/network access."""

    def build_payload(self, kw_list: list[str], timeframe: str = "today 12-m") -> None: ...
    def interest_over_time(self): ...  # returns a pandas.DataFrame
    def related_queries(self) -> dict: ...


def _default_client() -> TrendsClient:
    from pytrends.request import TrendReq

    return TrendReq(hl="en-US", tz=360)


def fetch_trends_summary(
    keywords: list[str],
    timeframe: str = "today 12-m",
    client: TrendsClient | None = None,
) -> str:
    """Fetch Google Trends interest-over-time and related queries for up to 5
    keywords, formatted as markdown for the GTM agent's scraped_context.

    Raises ValueError for an empty keyword list (nothing to ground). Network/
    pytrends errors propagate to the caller -- never silently swallowed into
    a fabricated "no data" result.
    """
    if not keywords:
        raise ValueError("fetch_trends_summary requires at least one keyword")
    if len(keywords) > 5:
        keywords = keywords[:5]  # Google Trends' own hard limit per query

    trends = client or _default_client()
    trends.build_payload(keywords, timeframe=timeframe)

    sections = [f"## Google Trends: interest over time ({timeframe})"]

    interest_df = trends.interest_over_time()
    if interest_df is None or interest_df.empty:
        sections.append("No interest-over-time data returned for these keywords.")
    else:
        latest = interest_df.iloc[-1]
        for kw in keywords:
            if kw in latest:
                sections.append(f"- {kw}: latest relative interest = {latest[kw]}")

    related = trends.related_queries() or {}
    for kw in keywords:
        kw_related = related.get(kw) or {}
        top = kw_related.get("top")
        if top is not None and not top.empty:
            sections.append(f"\n### Related queries for {kw!r}")
            for _, row in top.head(5).iterrows():
                sections.append(f"- {row['query']} (score: {row['value']})")

    return "\n".join(sections)
