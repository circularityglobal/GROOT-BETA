"""
REFINET Cloud — TTS Audio Overview Generator
Generates audio overviews from documents using Piper TTS (MIT, runs locally).
Falls back gracefully if Piper is not installed.
Fully sovereign — zero external API calls.
"""

import logging
import subprocess
import tempfile
import os
from typing import Optional

from api.services.inference import call_bitnet

logger = logging.getLogger("refinet.tts_generator")

# Max content to send to BitNet for script generation
MAX_SCRIPT_CHARS = 2500

PODCAST_SCRIPT_PROMPT = """You are a podcast host creating an audio overview. Convert the following document into a natural, conversational summary that sounds good when read aloud. Keep it under 2 minutes of speaking time (~300 words). Use a friendly, informative tone. Do NOT use markdown formatting, bullet points, or special characters — write in flowing paragraphs meant to be spoken.

Document title: {title}

Document content:
{content}

Audio script:"""


def is_tts_available() -> bool:
    """Check if Piper TTS is installed and available."""
    try:
        result = subprocess.run(
            ["piper", "--help"],
            capture_output=True, timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.SubprocessError):
        return False


async def generate_audio_overview(
    content: str,
    title: str = "",
    voice_model: str = "en_US-lessac-medium",
) -> dict:
    """
    Generate an audio overview of a document.
    Steps:
    1. Generate a podcast-style script via BitNet
    2. Convert script to audio via Piper TTS
    Returns {audio_bytes, script, format, duration_estimate}
    """
    # Check TTS availability
    if not is_tts_available():
        return {
            "error": "Piper TTS not installed. Install with: pip install piper-tts",
            "script": None,
            "audio_bytes": None,
        }

    # Step 1: Generate podcast script via BitNet
    truncated = content[:MAX_SCRIPT_CHARS]
    prompt = PODCAST_SCRIPT_PROMPT.format(title=title, content=truncated)

    script_result = await call_bitnet(
        messages=[
            {"role": "system", "content": "You are a podcast host. Write clear, spoken-word scripts."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.6,
        max_tokens=512,
    )

    script = script_result.get("content", "")
    if not script.strip():
        return {
            "error": "Failed to generate podcast script",
            "script": None,
            "audio_bytes": None,
        }

    # Step 2: Convert script to audio via Piper TTS
    # Run blocking subprocess in a thread to avoid blocking the event loop
    import asyncio
    return await asyncio.to_thread(_run_piper_tts, script, voice_model)


def _run_piper_tts(script: str, voice_model: str) -> dict:
    """Synchronous Piper TTS execution. Called via asyncio.to_thread."""
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            wav_path = os.path.join(tmpdir, "output.wav")

            proc = subprocess.run(
                ["piper", "--model", voice_model, "--output_file", wav_path],
                input=script.encode("utf-8"),
                capture_output=True,
                timeout=60,
            )

            if proc.returncode != 0:
                return {"error": f"Piper TTS error: {proc.stderr.decode()[:200]}", "script": script, "audio_bytes": None}

            if not os.path.exists(wav_path):
                return {"error": "Piper TTS produced no output", "script": script, "audio_bytes": None}

            with open(wav_path, "rb") as f:
                audio_bytes = f.read()

            word_count = len(script.split())
            duration_estimate = round(word_count / 150 * 60)

            return {
                "audio_bytes": audio_bytes, "script": script, "format": "wav",
                "duration_estimate": duration_estimate, "word_count": word_count,
            }

    except subprocess.TimeoutExpired:
        return {"error": "Piper TTS timed out", "script": script, "audio_bytes": None}
    except Exception as e:
        logger.error(f"TTS generation error: {e}")
        return {"error": f"TTS error: {str(e)}", "script": script, "audio_bytes": None}
