"""
REFINET Cloud — Timeline Extractor
Extracts dates and events from document text using regex-based date NER.
Pure Python, no external dependencies.
"""

import logging
import re
from datetime import datetime
from typing import Optional

logger = logging.getLogger("refinet.timeline_extractor")

# Month name mappings
MONTH_NAMES = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4,
    "jun": 6, "jul": 7, "aug": 8, "sep": 9, "sept": 9,
    "oct": 10, "nov": 11, "dec": 12,
}

# Regex patterns for date detection
DATE_PATTERNS = [
    # ISO: 2024-01-15
    (r'\b(\d{4})-(\d{1,2})-(\d{1,2})\b', "iso"),
    # US written: January 15, 2024 / Jan 15, 2024
    (r'\b(' + '|'.join(MONTH_NAMES.keys()) + r')\s+(\d{1,2}),?\s+(\d{4})\b', "written"),
    # US numeric: 01/15/2024 or 1/15/2024
    (r'\b(\d{1,2})/(\d{1,2})/(\d{4})\b', "us_numeric"),
    # Quarter: Q1 2024, Q2 2023
    (r'\b(Q[1-4])\s+(\d{4})\b', "quarter"),
    # Half: H1 2024, H2 2023
    (r'\b(H[12])\s+(\d{4})\b', "half"),
    # Year-month: 2024-01
    (r'\b(\d{4})-(\d{1,2})\b(?!-\d)', "year_month"),
    # Standalone year in context: "in 2024" or "by 2025"
    (r'\b(?:in|by|since|from|until|before|after|during)\s+(\d{4})\b', "year_context"),
]


def extract_timeline(content: str) -> list[dict]:
    """
    Extract dates and associated events from document text.
    Returns chronologically sorted list of {date, date_display, event, raw_text}.
    """
    if not content or not content.strip():
        return []

    # Split content into sentences for event extraction
    sentences = re.split(r'(?<=[.!?])\s+|\n', content)
    sentence_map: list[tuple[int, int, str]] = []
    pos = 0
    for sent in sentences:
        start = content.find(sent, pos)
        if start == -1:
            start = pos
        sentence_map.append((start, start + len(sent), sent.strip()))
        pos = start + len(sent)

    events: list[dict] = []
    seen_dates = set()

    for pattern, pattern_type in DATE_PATTERNS:
        for match in re.finditer(pattern, content, re.IGNORECASE):
            parsed = _parse_date_match(match, pattern_type)
            if not parsed:
                continue

            date_obj, date_display = parsed

            # Deduplicate by date string
            date_key = date_display
            if date_key in seen_dates:
                continue
            seen_dates.add(date_key)

            # Find the sentence containing this date
            match_pos = match.start()
            event_text = ""
            for sent_start, sent_end, sent_text in sentence_map:
                if sent_start <= match_pos < sent_end:
                    event_text = sent_text
                    break

            if not event_text:
                # Fall back to surrounding text
                start = max(0, match_pos - 100)
                end = min(len(content), match.end() + 200)
                event_text = content[start:end].strip()

            # Clean up the event text
            event_text = re.sub(r'\s+', ' ', event_text).strip()
            if len(event_text) > 300:
                event_text = event_text[:300] + "..."

            events.append({
                "date": date_obj.isoformat() if date_obj else date_display,
                "date_display": date_display,
                "event": event_text,
                "sort_key": date_obj.timestamp() if date_obj else 0,
            })

    # Sort chronologically
    events.sort(key=lambda e: e["sort_key"])

    # Remove sort_key from output
    for e in events:
        del e["sort_key"]

    return events


def _parse_date_match(match: re.Match, pattern_type: str) -> Optional[tuple[Optional[datetime], str]]:
    """Parse a regex match into (datetime_object, display_string)."""
    try:
        if pattern_type == "iso":
            year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
            if 1900 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31:
                return datetime(year, month, day), f"{year}-{month:02d}-{day:02d}"

        elif pattern_type == "written":
            month_name = match.group(1).lower()
            day = int(match.group(2))
            year = int(match.group(3))
            month = MONTH_NAMES.get(month_name)
            if month and 1900 <= year <= 2100 and 1 <= day <= 31:
                return datetime(year, month, day), f"{match.group(1).title()} {day}, {year}"

        elif pattern_type == "us_numeric":
            month, day, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
            if 1900 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31:
                return datetime(year, month, day), f"{month:02d}/{day:02d}/{year}"

        elif pattern_type == "quarter":
            quarter = match.group(1)
            year = int(match.group(2))
            if 1900 <= year <= 2100:
                q_num = int(quarter[1])
                month = (q_num - 1) * 3 + 1
                return datetime(year, month, 1), f"{quarter} {year}"

        elif pattern_type == "half":
            half = match.group(1)
            year = int(match.group(2))
            if 1900 <= year <= 2100:
                month = 1 if half == "H1" else 7
                return datetime(year, month, 1), f"{half} {year}"

        elif pattern_type == "year_month":
            year, month = int(match.group(1)), int(match.group(2))
            if 1900 <= year <= 2100 and 1 <= month <= 12:
                return datetime(year, month, 1), f"{year}-{month:02d}"

        elif pattern_type == "year_context":
            year = int(match.group(1))
            if 1900 <= year <= 2100:
                return datetime(year, 1, 1), f"{year}"

    except (ValueError, OverflowError):
        pass

    return None
