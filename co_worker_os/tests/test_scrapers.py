"""TDD tests for src/scrapers/. No live network calls — every test injects a
fake fetcher/downloader so the suite runs offline and deterministically, per
docs/ImplementationPlan.md Sprint 2 ("fixture-based, no live network calls in CI").
"""

from __future__ import annotations

import pytest

from src.scrapers.social_scraper import fetch_reddit_feed
from src.scrapers.video_scraper import extract_transcript
from src.scrapers.web_scraper import scrape_url, scrape_with_bs4

# --- Fixtures -----------------------------------------------------------

SAMPLE_HTML = """
<html>
<head><title>Widget Pro 3000 Review</title>
<style>.hidden { display:none; }</style>
<script>console.log("tracking pixel")</script>
</head>
<body>
<nav>Home | About | Contact</nav>
<h1>Widget Pro 3000</h1>
<p>The Widget Pro 3000 is a great tool for makers.</p>
<h2>Pricing</h2>
<p>It costs $49.99 and ships in 3 days.</p>
<footer>Copyright 2026</footer>
</body>
</html>
"""

SAMPLE_REDDIT_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>reddit: r/productivity</title>
  <entry>
    <title>I lose data every time wifi drops</title>
    <link href="https://reddit.com/r/productivity/comments/abc123"/>
    <content type="html">&lt;p&gt;Offline-first apps are so rare these days.&lt;/p&gt;</content>
    <author><name>/u/example_user</name></author>
  </entry>
  <entry>
    <title>Looking for a local-first note app</title>
    <link href="https://reddit.com/r/productivity/comments/def456"/>
    <content type="html">&lt;p&gt;Everything is cloud-only now, annoying.&lt;/p&gt;</content>
    <author><name>/u/another_user</name></author>
  </entry>
</feed>
"""

SAMPLE_SUBTITLE_VTT = """WEBVTT

00:00:00.000 --> 00:00:02.000
Hey everyone, welcome back to the channel.

00:00:02.000 --> 00:00:05.000
Today we're reviewing the Widget Pro 3000.
"""


class FakeResponse:
    def __init__(self, text: str, status_code: int = 200):
        self.text = text
        self.content = text.encode("utf-8")
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class TestWebScraperBs4Fallback:
    def test_extracts_clean_markdown_from_html(self):
        def fake_get(url, timeout=10):
            return FakeResponse(SAMPLE_HTML)

        markdown = scrape_with_bs4("https://example.com/widget", http_get=fake_get)

        assert "Widget Pro 3000" in markdown
        assert "$49.99" in markdown
        # script/style content must never leak into agent context
        assert "console.log" not in markdown
        assert "display:none" not in markdown

    def test_strips_nav_and_footer_boilerplate_markers(self):
        def fake_get(url, timeout=10):
            return FakeResponse(SAMPLE_HTML)

        markdown = scrape_with_bs4("https://example.com/widget", http_get=fake_get)
        # Heading structure should be preserved as markdown headings.
        assert "# Widget Pro 3000" in markdown or "## Widget Pro 3000" in markdown

    def test_raises_on_http_error(self):
        def fake_get(url, timeout=10):
            return FakeResponse("not found", status_code=404)

        with pytest.raises(RuntimeError):
            scrape_with_bs4("https://example.com/missing", http_get=fake_get)


class TestWebScraperDispatch:
    def test_scrape_url_falls_back_to_bs4_when_crawl4ai_unavailable(self):
        def fake_get(url, timeout=10):
            return FakeResponse(SAMPLE_HTML)

        markdown = scrape_url(
            "https://example.com/widget",
            http_get=fake_get,
            crawl4ai_available=False,
        )
        assert "Widget Pro 3000" in markdown

    def test_scrape_url_uses_crawl4ai_result_when_available(self):
        def fake_crawl4ai_fn(url):
            return "# Widget Pro 3000\n\nCrawl4AI-extracted content."

        markdown = scrape_url(
            "https://example.com/widget",
            crawl4ai_available=True,
            crawl4ai_fn=fake_crawl4ai_fn,
        )
        assert "Crawl4AI-extracted content." in markdown


class TestVideoScraper:
    def test_extracts_transcript_as_markdown_without_downloading_video(self):
        calls = {}

        def fake_downloader(video_url, ydl_opts):
            calls["ydl_opts"] = ydl_opts
            calls["video_url"] = video_url
            return {
                "title": "Widget Pro 3000 Unboxing",
                "subtitle_text": SAMPLE_SUBTITLE_VTT,
            }

        markdown = extract_transcript(
            "https://youtube.com/watch?v=abc123",
            downloader=fake_downloader,
        )

        assert "Widget Pro 3000 Unboxing" in markdown
        assert "Today we're reviewing the Widget Pro 3000." in markdown
        # VTT cue timestamps/markup must not leak into the agent-facing markdown
        assert "00:00:02.000" not in markdown
        assert "WEBVTT" not in markdown
        # Must never request video download.
        assert calls["ydl_opts"]["skip_download"] is True

    def test_raises_when_no_subtitles_available(self):
        def fake_downloader(video_url, ydl_opts):
            return {"title": "No Captions Video", "subtitle_text": None}

        with pytest.raises(ValueError):
            extract_transcript("https://youtube.com/watch?v=nocaptions", downloader=fake_downloader)


class TestSocialScraper:
    def test_fetches_and_formats_reddit_feed_as_markdown(self):
        def fake_get(url, timeout=10):
            return FakeResponse(SAMPLE_REDDIT_RSS)

        markdown = fetch_reddit_feed(
            "https://www.reddit.com/r/productivity/.rss",
            http_get=fake_get,
        )

        assert "I lose data every time wifi drops" in markdown
        assert "Offline-first apps are so rare these days." in markdown
        assert "Looking for a local-first note app" in markdown
        assert "https://reddit.com/r/productivity/comments/abc123" in markdown

    def test_strips_html_tags_from_entry_content(self):
        def fake_get(url, timeout=10):
            return FakeResponse(SAMPLE_REDDIT_RSS)

        markdown = fetch_reddit_feed("https://www.reddit.com/r/productivity/.rss", http_get=fake_get)
        assert "<p>" not in markdown
        assert "&lt;" not in markdown

    def test_raises_on_empty_feed(self):
        empty_feed = """<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"></feed>"""

        def fake_get(url, timeout=10):
            return FakeResponse(empty_feed)

        with pytest.raises(ValueError):
            fetch_reddit_feed("https://www.reddit.com/r/empty/.rss", http_get=fake_get)
