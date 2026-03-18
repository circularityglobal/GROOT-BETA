"""
REFINET Cloud — Document Generator
Uses BitNet inference to generate summaries, FAQs, and overviews from knowledge base documents.
Runs locally on sovereign infrastructure — zero external API calls.
"""

import logging

from api.services.inference import call_bitnet

logger = logging.getLogger("refinet.document_generator")

# Maximum chars to send to BitNet (model context limit consideration)
MAX_CONTENT_CHARS = 3000


SUMMARIZE_PROMPT = """You are a document analyst. Provide a concise summary of the following document in 3-5 key bullet points. Each point should capture a distinct important idea. Be specific and factual.

Document:
{content}

Summary:"""

FAQ_PROMPT = """You are a document analyst. Based on the following document, generate 5 frequently asked questions and their answers. Each Q&A should address a different aspect of the document. Format as:

Q1: [question]
A1: [answer]

Q2: [question]
A2: [answer]

(and so on)

Document:
{content}

FAQ:"""

OVERVIEW_PROMPT = """You are a document analyst. Create a structured overview of the following document. Include:
1. **Title/Subject** - What this document is about
2. **Key Topics** - The main topics covered (3-5 items)
3. **Important Details** - Critical facts, numbers, or specifications
4. **Conclusions** - Key takeaways or action items

Document:
{content}

Overview:"""


async def generate_summary(content: str, title: str = "") -> dict:
    """Generate a summary of a document using BitNet."""
    truncated = content[:MAX_CONTENT_CHARS]
    prompt = SUMMARIZE_PROMPT.format(content=truncated)

    result = await call_bitnet(
        messages=[
            {"role": "system", "content": "You are a precise document analyst. Be concise and factual."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
        max_tokens=512,
    )

    return {
        "type": "summary",
        "title": title,
        "content": result.get("content", ""),
        "tokens_used": result.get("completion_tokens", 0),
    }


async def generate_faq(content: str, title: str = "") -> dict:
    """Generate FAQ from a document using BitNet."""
    truncated = content[:MAX_CONTENT_CHARS]
    prompt = FAQ_PROMPT.format(content=truncated)

    result = await call_bitnet(
        messages=[
            {"role": "system", "content": "You are a precise document analyst. Generate clear Q&A pairs."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.4,
        max_tokens=768,
    )

    return {
        "type": "faq",
        "title": title,
        "content": result.get("content", ""),
        "tokens_used": result.get("completion_tokens", 0),
    }


async def generate_overview(content: str, title: str = "") -> dict:
    """Generate a structured overview of a document using BitNet."""
    truncated = content[:MAX_CONTENT_CHARS]
    prompt = OVERVIEW_PROMPT.format(content=truncated)

    result = await call_bitnet(
        messages=[
            {"role": "system", "content": "You are a precise document analyst. Create structured overviews."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
        max_tokens=768,
    )

    return {
        "type": "overview",
        "title": title,
        "content": result.get("content", ""),
        "tokens_used": result.get("completion_tokens", 0),
    }
