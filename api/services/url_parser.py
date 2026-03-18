"""
REFINET Cloud — URL Parser
Fetches web pages and extracts text content.
Uses httpx (already in requirements) + stdlib html.parser.
Zero external dependencies. Fully sovereign.
"""

import logging
import re
from html.parser import HTMLParser
from typing import Optional
from urllib.parse import urlparse

import httpx

from api.services.document_parser import ParseResult

logger = logging.getLogger("refinet.url_parser")

# Max page size to download (5MB)
MAX_DOWNLOAD_SIZE = 5 * 1024 * 1024

# Tags to skip content from
SKIP_TAGS = {"script", "style", "nav", "footer", "header", "aside", "noscript", "svg", "form"}

# Tags whose text content we extract
TEXT_TAGS = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "td", "th", "blockquote", "pre", "code", "figcaption", "dt", "dd"}


class _HTMLTextExtractor(HTMLParser):
    """Extract text from HTML, skipping scripts/styles/nav."""

    def __init__(self):
        super().__init__()
        self.text_parts: list[str] = []
        self.title = ""
        self._skip_depth = 0
        self._in_title = False
        self._current_tag = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]):
        tag_lower = tag.lower()
        self._current_tag = tag_lower
        if tag_lower in SKIP_TAGS:
            self._skip_depth += 1
        if tag_lower == "title":
            self._in_title = True
        # Add line breaks for block elements
        if tag_lower in {"p", "br", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr"}:
            self.text_parts.append("\n")
        if tag_lower in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self.text_parts.append(f"{'#' * int(tag_lower[1])} ")

    def handle_endtag(self, tag: str):
        tag_lower = tag.lower()
        if tag_lower in SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1
        if tag_lower == "title":
            self._in_title = False
        if tag_lower in {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6"}:
            self.text_parts.append("\n")

    def handle_data(self, data: str):
        if self._in_title and not self.title:
            self.title = data.strip()
        if self._skip_depth > 0:
            return
        text = data.strip()
        if text:
            self.text_parts.append(text + " ")

    def get_text(self) -> str:
        raw = "".join(self.text_parts)
        # Clean up excessive whitespace
        raw = re.sub(r'\n{3,}', '\n\n', raw)
        raw = re.sub(r' {2,}', ' ', raw)
        return raw.strip()


async def parse_url(url: str) -> ParseResult:
    """
    Fetch a URL and extract text content.
    Supports HTML pages and PDF URLs.
    Returns ParseResult compatible with the document ingestion pipeline.
    """
    # Validate URL
    parsed = urlparse(url)
    if not parsed.scheme or parsed.scheme not in ("http", "https"):
        return ParseResult(text="", doc_type="url", error=f"Invalid URL scheme: {parsed.scheme}. Use http or https.")
    if not parsed.netloc:
        return ParseResult(text="", doc_type="url", error="Invalid URL: no domain")

    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(url, headers={
                "User-Agent": "REFINET-Cloud/1.0 (Knowledge Ingestion)",
            })
            resp.raise_for_status()

            # Check size
            content_length = len(resp.content)
            if content_length > MAX_DOWNLOAD_SIZE:
                return ParseResult(text="", doc_type="url", error=f"Page too large: {content_length / 1024 / 1024:.1f}MB (max 5MB)")

            content_type = resp.headers.get("content-type", "")

            # PDF detection
            if "application/pdf" in content_type or url.lower().endswith(".pdf"):
                from api.services.document_parser import parse_pdf
                result = parse_pdf(resp.content, url.split("/")[-1] or "download.pdf")
                result.metadata["source_url"] = url
                return result

            # HTML parsing
            if "text/html" in content_type or "text/plain" in content_type or not content_type:
                html = resp.text
                extractor = _HTMLTextExtractor()
                extractor.feed(html)
                text = extractor.get_text()

                if not text.strip():
                    return ParseResult(text="", doc_type="url", error="No text content extracted from page")

                metadata = {
                    "source_url": url,
                    "domain": parsed.netloc,
                }
                if extractor.title:
                    metadata["page_title"] = extractor.title

                return ParseResult(
                    text=text,
                    doc_type="url",
                    metadata=metadata,
                )

            return ParseResult(text="", doc_type="url", error=f"Unsupported content type: {content_type}")

    except httpx.TimeoutException:
        return ParseResult(text="", doc_type="url", error=f"Timeout fetching URL: {url}")
    except httpx.HTTPStatusError as e:
        return ParseResult(text="", doc_type="url", error=f"HTTP {e.response.status_code} fetching URL")
    except Exception as e:
        logger.error(f"URL parse error for {url}: {e}")
        return ParseResult(text="", doc_type="url", error=f"Error: {str(e)}")
