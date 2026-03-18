"""
REFINET Cloud — YouTube Transcript Parser
Extracts transcripts from YouTube videos using yt-dlp (public domain).
Falls back gracefully if yt-dlp is not installed.
Fully sovereign — no YouTube API key needed.
"""

import json
import logging
import re
import subprocess
import tempfile
import os
from typing import Optional

from api.services.document_parser import ParseResult

logger = logging.getLogger("refinet.youtube_parser")

# Regex for YouTube URLs
YOUTUBE_PATTERNS = [
    r'(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
    r'(?:https?://)?youtu\.be/([a-zA-Z0-9_-]{11})',
    r'(?:https?://)?(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]{11})',
]


def is_youtube_url(url: str) -> bool:
    """Check if a URL is a valid YouTube video URL."""
    return any(re.search(p, url) for p in YOUTUBE_PATTERNS)


def extract_video_id(url: str) -> Optional[str]:
    """Extract video ID from a YouTube URL."""
    for pattern in YOUTUBE_PATTERNS:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def _parse_youtube_sync(url: str, video_id: str) -> ParseResult:
    """Synchronous YouTube parsing — runs subprocess calls. Called via asyncio.to_thread."""
    # Check if yt-dlp is available
    try:
        subprocess.run(["yt-dlp", "--version"], capture_output=True, check=True, timeout=5)
    except (FileNotFoundError, subprocess.SubprocessError):
        return ParseResult(
            text="", doc_type="youtube",
            error="yt-dlp not installed. Run: pip install yt-dlp",
        )

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            info_cmd = [
                "yt-dlp", "--skip-download", "--write-auto-sub",
                "--sub-lang", "en", "--sub-format", "vtt",
                "--print-json", "--no-warnings",
                "-o", os.path.join(tmpdir, "%(id)s"), url,
            ]
            result = subprocess.run(info_cmd, capture_output=True, text=True, timeout=30)

            if result.returncode != 0:
                return ParseResult(text="", doc_type="youtube", error=f"yt-dlp error: {result.stderr[:200]}")

            metadata = {}
            title = ""
            try:
                info = json.loads(result.stdout)
                title = info.get("title", "")
                metadata = {
                    "video_title": title, "channel": info.get("channel", ""),
                    "duration": info.get("duration"), "upload_date": info.get("upload_date"),
                    "view_count": info.get("view_count"), "video_id": video_id, "source_url": url,
                }
            except json.JSONDecodeError:
                pass

            transcript = ""
            for f in os.listdir(tmpdir):
                if f.endswith(".vtt") or f.endswith(".srt"):
                    with open(os.path.join(tmpdir, f), "r", encoding="utf-8", errors="replace") as sf:
                        transcript = _parse_subtitles(sf.read())
                    break

            if not transcript:
                return ParseResult(text="", doc_type="youtube", metadata=metadata,
                                   error="No English subtitles/transcript available")

            text_parts = []
            if title:
                text_parts.append(f"# {title}\n")
            text_parts.append(transcript)
            return ParseResult(text="\n".join(text_parts), doc_type="youtube", metadata=metadata)

    except subprocess.TimeoutExpired:
        return ParseResult(text="", doc_type="youtube", error="yt-dlp timed out")
    except Exception as e:
        return ParseResult(text="", doc_type="youtube", error=f"Error: {str(e)}")


async def parse_youtube(url: str) -> ParseResult:
    """
    Extract transcript from a YouTube video using yt-dlp.
    Returns ParseResult with transcript text and video metadata.
    Requires yt-dlp to be installed (pip install yt-dlp).
    Runs blocking subprocess via asyncio.to_thread to avoid blocking the event loop.
    """
    if not is_youtube_url(url):
        return ParseResult(
            text="", doc_type="youtube",
            error=f"Not a valid YouTube URL: {url}",
        )

    video_id = extract_video_id(url)

    # Run blocking subprocess work in a thread to avoid blocking the event loop
    import asyncio
    return await asyncio.to_thread(_parse_youtube_sync, url, video_id)


def _parse_subtitles(raw: str) -> str:
    """Parse VTT/SRT subtitle content into clean text."""
    lines = raw.split("\n")
    text_lines = []
    seen = set()

    for line in lines:
        line = line.strip()
        # Skip VTT headers
        if line.startswith("WEBVTT") or line.startswith("NOTE"):
            continue
        # Skip timestamp lines
        if re.match(r'^\d{2}:\d{2}', line) or re.match(r'^\d+$', line):
            continue
        # Skip empty lines
        if not line:
            continue
        # Strip HTML tags
        clean = re.sub(r'<[^>]+>', '', line)
        clean = clean.strip()
        if clean and clean not in seen:
            seen.add(clean)
            text_lines.append(clean)

    return " ".join(text_lines)
