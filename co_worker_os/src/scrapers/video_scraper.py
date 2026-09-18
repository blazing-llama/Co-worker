"""Video transcript extractor: YouTube subtitles -> clean Markdown.

Uses yt-dlp with `skip_download=True` — video binaries are never downloaded,
only subtitle/transcript text, per docs/ImplementationPlan.md Sprint 2.

The actual yt-dlp call is behind an injectable `downloader` so tests run
offline (see tests/test_scrapers.py). In production, `default_downloader`
wraps yt_dlp.YoutubeDL.
"""

from __future__ import annotations

import re
from typing import Callable, Protocol


class Downloader(Protocol):
    def __call__(self, video_url: str, ydl_opts: dict) -> dict: ...


def _vtt_to_text(vtt: str) -> str:
    """Strip WEBVTT headers, cue timestamps, and formatting tags, collapsing
    to plain spoken-word text (deduplicating consecutive repeated lines, which
    auto-generated captions commonly produce)."""
    lines = []
    last_line = None
    for raw_line in vtt.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line == "WEBVTT":
            continue
        if "-->" in line:  # cue timing line, e.g. 00:00:00.000 --> 00:00:02.000
            continue
        if re.match(r"^\d+$", line):  # numeric cue index
            continue
        line = re.sub(r"<[^>]+>", "", line)  # inline VTT formatting tags
        if line != last_line:
            lines.append(line)
            last_line = line
    return " ".join(lines)


def default_downloader(video_url: str, ydl_opts: dict) -> dict:
    """Real yt-dlp-backed downloader. Imported lazily so the module can be
    imported (and tests run) even in environments without yt-dlp installed."""
    import yt_dlp

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(video_url, download=False)

    subtitle_text = None
    for track_map in (info.get("subtitles") or {}, info.get("automatic_captions") or {}):
        for _lang, tracks in track_map.items():
            for track in tracks:
                if track.get("ext") == "vtt" and track.get("data"):
                    subtitle_text = track["data"]
                    break
            if subtitle_text:
                break
        if subtitle_text:
            break

    return {"title": info.get("title", "Untitled video"), "subtitle_text": subtitle_text}


def extract_transcript(video_url: str, downloader: Callable[[str, dict], dict] | None = None) -> str:
    """Return a markdown transcript for `video_url`, or raise ValueError if the
    video has no subtitles/captions available."""
    downloader = downloader or default_downloader
    ydl_opts = {
        "skip_download": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitlesformat": "vtt",
        "quiet": True,
        "no_warnings": True,
    }

    result = downloader(video_url, ydl_opts)
    subtitle_text = result.get("subtitle_text")
    if not subtitle_text:
        raise ValueError(f"No subtitles/transcript available for {video_url!r}")

    title = result.get("title", "Untitled video")
    transcript = _vtt_to_text(subtitle_text)
    return f"# {title}\n\n{transcript}"
