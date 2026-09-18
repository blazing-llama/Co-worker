"""Web scraper: HTML -> clean, token-efficient Markdown, zero paid APIs.

Primary path: Crawl4AI's AsyncWebCrawler (local, browser-driven extraction).
Fallback path: requests + BeautifulSoup static extraction, used automatically
when Crawl4AI is not importable/available in the current environment — see
CLAUDE.md's "Unverified External Packages" policy.

Every public function accepts an injectable `http_get` / `crawl4ai_fn` so tests
run fully offline (see tests/test_scrapers.py).
"""

from __future__ import annotations

import asyncio
import re
from typing import Callable, Protocol

import requests
from bs4 import BeautifulSoup, Comment

try:
    from crawl4ai import AsyncWebCrawler  # noqa: F401

    CRAWL4AI_AVAILABLE = True
except ImportError:
    CRAWL4AI_AVAILABLE = False


class HttpGet(Protocol):
    def __call__(self, url: str, timeout: int = 10): ...


_BLOCK_TAGS_TO_DROP = ("script", "style", "noscript", "svg")
_BOILERPLATE_TAGS_TO_DROP = ("nav", "footer", "header", "aside", "form")


def _html_to_markdown(html: str) -> str:
    """Static HTML -> markdown, stripping scripts/styles/boilerplate and
    preserving heading structure so the output stays token-efficient and
    grounded (no invented content, just re-formatted source text)."""
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(_BLOCK_TAGS_TO_DROP):
        tag.decompose()
    for tag in soup(_BOILERPLATE_TAGS_TO_DROP):
        tag.decompose()
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()

    lines: list[str] = []
    for element in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li"]):
        text = element.get_text(strip=True)
        if not text:
            continue
        if element.name.startswith("h") and element.name[1:].isdigit():
            level = int(element.name[1])
            lines.append(f"{'#' * level} {text}")
        elif element.name == "li":
            lines.append(f"- {text}")
        else:
            lines.append(text)

    markdown = "\n\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", markdown).strip()


def scrape_with_bs4(url: str, http_get: HttpGet = requests.get) -> str:
    """Fallback extractor: fetch `url` and convert its HTML to markdown."""
    response = http_get(url, timeout=10)
    response.raise_for_status()
    return _html_to_markdown(response.text)


def _scrape_with_crawl4ai_sync(url: str) -> str:
    """Run Crawl4AI's async crawler synchronously and return its markdown."""

    async def _run() -> str:
        async with AsyncWebCrawler() as crawler:
            result = await crawler.arun(url=url)
            return result.markdown or ""

    return asyncio.run(_run())


def scrape_url(
    url: str,
    http_get: HttpGet = requests.get,
    crawl4ai_available: bool | None = None,
    crawl4ai_fn: Callable[[str], str] | None = None,
) -> str:
    """Scrape `url` into markdown. Uses Crawl4AI when available, otherwise falls
    back to the local BeautifulSoup extractor — never requires a paid API.

    `crawl4ai_available` / `crawl4ai_fn` are injectable for testing; in
    production they default to the real Crawl4AI availability/call.
    """
    available = CRAWL4AI_AVAILABLE if crawl4ai_available is None else crawl4ai_available
    if available:
        crawl_fn = crawl4ai_fn or _scrape_with_crawl4ai_sync
        markdown = crawl_fn(url)
        if markdown.strip():
            return markdown

    return scrape_with_bs4(url, http_get=http_get)
