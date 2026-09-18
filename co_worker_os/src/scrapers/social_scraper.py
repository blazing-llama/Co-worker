"""Social scraper: unauthenticated Reddit RSS / forum feeds -> clean Markdown.

No Reddit API key, no auth token — just the public `.rss` feed endpoint any
subreddit/search exposes (e.g. https://www.reddit.com/r/productivity/.rss).
"""

from __future__ import annotations

import feedparser
import requests
from bs4 import BeautifulSoup

from .web_scraper import HttpGet


def _clean_entry_content(html_or_text: str) -> str:
    """Reddit RSS entry `content` is HTML-escaped HTML; strip tags to plain text."""
    return BeautifulSoup(html_or_text, "html.parser").get_text(separator=" ", strip=True)


def fetch_reddit_feed(feed_url: str, http_get: HttpGet = requests.get) -> str:
    """Fetch a public Reddit (or any Atom/RSS) feed and format entries as
    markdown: one section per post, with title, source link, and cleaned body
    text — ready for the GTM & Research agent's grounded-claims context.

    Raises ValueError if the feed has no entries (nothing to ground claims in).
    """
    response = http_get(feed_url, timeout=10)
    response.raise_for_status()

    parsed = feedparser.parse(response.content)
    if not parsed.entries:
        raise ValueError(f"No entries found in feed: {feed_url!r}")

    sections = []
    for entry in parsed.entries:
        title = getattr(entry, "title", "Untitled post")
        link = getattr(entry, "link", "")
        author = getattr(entry, "author", "unknown")
        raw_content = ""
        if getattr(entry, "content", None):
            raw_content = entry.content[0].value
        elif getattr(entry, "summary", None):
            raw_content = entry.summary
        body = _clean_entry_content(raw_content) if raw_content else ""

        section = f"## {title}\n\nSource: {link}\nAuthor: {author}"
        if body:
            section += f"\n\n{body}"
        sections.append(section)

    return "\n\n---\n\n".join(sections)
