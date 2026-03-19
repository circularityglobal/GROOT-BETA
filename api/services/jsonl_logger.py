"""
REFINET Cloud — JSONL Episodic Logger
Append-only JSONL file writer for episodic memory and audit trails.

Writes to data/episodes/{date}/{agent}.jsonl alongside DB-backed storage.
Thread-safe with file locking.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("refinet.jsonl_logger")

# Base path for JSONL episode files
_BASE_PATH = Path(__file__).resolve().parents[2] / "data" / "episodes"

# Thread lock for file writes
_write_lock = threading.Lock()


def append_episode(
    agent_id: str,
    event_type: str,
    summary: str,
    context: Optional[dict] = None,
    outcome: Optional[str] = None,
    tokens_used: int = 0,
    task_id: Optional[str] = None,
) -> bool:
    """
    Append an episodic event to the JSONL log file.

    Files are organized as: data/episodes/{YYYY-MM-DD}/{agent_id}.jsonl

    Returns True on success, False on failure (non-fatal).
    """
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")

    # Build the log entry
    entry = {
        "timestamp": now.isoformat(),
        "agent_id": agent_id,
        "event_type": event_type,
        "summary": summary,
        "outcome": outcome,
        "tokens_used": tokens_used,
    }
    if task_id:
        entry["task_id"] = task_id
    if context:
        entry["context"] = context

    # Determine file path
    dir_path = _BASE_PATH / date_str
    file_path = dir_path / f"{_sanitize_filename(agent_id)}.jsonl"

    try:
        with _write_lock:
            dir_path.mkdir(parents=True, exist_ok=True)
            with open(file_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")
        return True
    except Exception as e:
        logger.warning(f"JSONL write failed for {file_path}: {e}")
        return False


def append_task_result(
    agent_id: str,
    task_id: str,
    trigger: str,
    source: str,
    started: str,
    completed: str,
    iterations: int,
    input_tokens: int,
    output_tokens: int,
    tools_called: list[str],
    outcome: str,
) -> bool:
    """
    Append a completed task record to the JSONL store.
    Matches PRD Section 9.3 format.
    """
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")

    entry = {
        "task_id": task_id,
        "agent": agent_id,
        "trigger": trigger,
        "source": source,
        "started": started,
        "completed": completed,
        "iterations": iterations,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "tools_called": tools_called,
        "outcome": outcome,
    }

    dir_path = _BASE_PATH / date_str
    file_path = dir_path / "tasks.jsonl"

    try:
        with _write_lock:
            dir_path.mkdir(parents=True, exist_ok=True)
            with open(file_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")
        return True
    except Exception as e:
        logger.warning(f"JSONL task write failed: {e}")
        return False


def append_tool_call(
    agent_id: str,
    task_id: str,
    tool_name: str,
    tool_input: dict,
    tool_output: dict,
    latency_ms: int,
    success: bool,
) -> bool:
    """
    Append a tool call record to the JSONL log.
    Matches PRD Section 9.1 format.
    """
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")

    entry = {
        "timestamp": now.isoformat(),
        "task_id": task_id,
        "agent": agent_id,
        "tool": tool_name,
        "input": tool_input,
        "output": tool_output,
        "latency_ms": latency_ms,
        "success": success,
    }

    dir_path = _BASE_PATH / date_str
    file_path = dir_path / "tool_calls.jsonl"

    try:
        with _write_lock:
            dir_path.mkdir(parents=True, exist_ok=True)
            with open(file_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")
        return True
    except Exception as e:
        logger.warning(f"JSONL tool call write failed: {e}")
        return False


def _sanitize_filename(name: str) -> str:
    """Sanitize a string for use as a filename."""
    return "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in name)
