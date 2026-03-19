"""
REFINET Cloud — Context Loader
Cached filesystem loader for root-level control documents
(SOUL.md, SAFETY.md, MEMORY.md, HEARTBEAT.md, AGENTS.md).

Documents are cached with a 60-second TTL to avoid re-reading
on every inference call.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger("refinet.context_loader")

# Project root: from api/services/ go up 2 levels to groot/
_PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Cache: filename → (content, timestamp)
_cache: dict[str, tuple[str, float]] = {}
_CACHE_TTL = 60.0  # seconds


def load_control_document(filename: str) -> str:
    """
    Load a root-level control document (e.g., SOUL.md, SAFETY.md).

    Returns the file content as a string.
    Returns empty string if file doesn't exist (logs warning on first miss).
    Caches content for 60 seconds.
    """
    now = time.monotonic()

    # Check cache
    if filename in _cache:
        content, cached_at = _cache[filename]
        if now - cached_at < _CACHE_TTL:
            return content

    # Read from filesystem
    filepath = _PROJECT_ROOT / filename
    try:
        content = filepath.read_text(encoding="utf-8").strip()
        _cache[filename] = (content, now)
        return content
    except FileNotFoundError:
        logger.warning(f"Control document not found: {filepath}")
        _cache[filename] = ("", now)
        return ""
    except Exception as e:
        logger.error(f"Error reading {filepath}: {e}")
        # Return stale cache if available
        if filename in _cache:
            return _cache[filename][0]
        return ""


def invalidate_cache(filename: Optional[str] = None):
    """
    Invalidate cached control documents.
    If filename is None, invalidates all cached documents.
    """
    if filename:
        _cache.pop(filename, None)
    else:
        _cache.clear()


def load_skills_metadata() -> str:
    """
    Load skill frontmatter summaries from the skills/ directory.
    Returns a compact summary of available skills for context injection.
    """
    skills_dir = _PROJECT_ROOT / "skills"
    if not skills_dir.is_dir():
        return ""

    skills = []
    for skill_dir in sorted(skills_dir.iterdir()):
        if skill_dir.name.startswith("_") or not skill_dir.is_dir():
            continue
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue

        try:
            content = skill_md.read_text(encoding="utf-8")
            # Extract frontmatter (between --- markers)
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    frontmatter = parts[1].strip()
                    skills.append(f"- {skill_dir.name}: {_extract_description(frontmatter)}")
        except Exception as e:
            logger.debug(f"Error reading skill {skill_dir.name}: {e}")

    if not skills:
        return ""

    return "Available skills:\n" + "\n".join(skills)


def _extract_description(frontmatter: str) -> str:
    """Extract the description field from YAML frontmatter."""
    for line in frontmatter.split("\n"):
        line = line.strip()
        if line.startswith("description:"):
            return line[len("description:"):].strip().strip('"').strip("'")
    return "No description"


def get_project_root() -> Path:
    """Return the project root path."""
    return _PROJECT_ROOT
