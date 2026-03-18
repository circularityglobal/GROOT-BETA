"""
REFINET Cloud — Auto-Tagger
Extracts semantic tags from document text for LLM-optimized search.
Tags are natural language phrases that GROOT and external agents search for.
Uses keyword frequency (TF-IDF-like) + named entity extraction + embedding diversity.
Zero external API calls. Fully sovereign.
"""

import json
import logging
import math
import os
import re
from collections import Counter
from typing import Optional

logger = logging.getLogger("refinet.auto_tagger")


# ── Stop Words ────────────────────────────────────────────────────────

STOP_WORDS = frozenset({
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "as", "is", "are", "was", "were", "be",
    "been", "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "could", "should", "may", "might", "shall", "can", "need",
    "not", "no", "nor", "so", "if", "then", "than", "too", "very",
    "just", "about", "above", "after", "again", "all", "also", "am",
    "any", "because", "before", "between", "both", "each", "few",
    "further", "get", "got", "here", "how", "into", "it", "its",
    "more", "most", "new", "now", "only", "other", "our", "out",
    "over", "own", "same", "she", "he", "some", "such", "that",
    "their", "them", "there", "these", "they", "this", "those",
    "through", "under", "until", "up", "us", "we", "what", "when",
    "where", "which", "while", "who", "whom", "why", "you", "your",
    "use", "used", "using", "make", "made", "like", "see", "one",
    "two", "three", "well", "also", "back", "even", "still", "way",
    "take", "come", "many", "set", "say", "said", "since", "must",
    "much", "let", "put", "keep", "give", "first", "last", "long",
    "great", "little", "right", "old", "big", "high", "different",
    "small", "large", "next", "early", "young", "important", "public",
    "good", "same", "able", "know", "look", "want", "think", "tell",
    "work", "call", "try", "ask", "help", "show", "turn", "move",
    "play", "run", "change", "close", "open", "point", "read", "hand",
})


# ── Domain Boosters ───────────────────────────────────────────────────

DOMAIN_BOOST_TERMS = frozenset({
    # Blockchain / DeFi
    "blockchain", "ethereum", "solidity", "defi", "token", "nft",
    "staking", "governance", "dao", "bridge", "oracle", "vault",
    "liquidity", "yield", "swap", "amm", "collateral", "lending",
    "borrowing", "erc20", "erc721", "erc1155", "proxy", "upgradeable",
    "multisig", "timelock", "flashloan", "mev", "layer2", "rollup",
    "zk", "optimistic", "arbitrum", "polygon", "base", "solana",
    # REFINET specific
    "refinet", "groot", "quickcast", "agentos", "cifi", "sovereign",
    "bitnet", "siwe", "mcp", "rag", "cag",
    # Tech
    "api", "sdk", "webhook", "websocket", "graphql", "grpc",
    "authentication", "encryption", "jwt", "totp", "iot", "telemetry",
    # ReFi
    "regenerative", "sustainability", "carbon", "impact", "circular",
})


# ── Category Signals ──────────────────────────────────────────────────

CATEGORY_SIGNALS = {
    "blockchain": [
        "smart contract", "solidity", "ethereum", "token", "defi", "nft",
        "blockchain", "on-chain", "abi", "erc20", "erc721", "staking",
        "governance", "dao", "bridge", "oracle", "vault", "liquidity",
        "web3", "dapp", "consensus", "merkle", "hash", "block",
    ],
    "contract": [
        "abi", "function", "event", "modifier", "constructor", "selector",
        "calldata", "interface", "pragma solidity", "mapping", "struct",
        "emit", "require", "revert", "msg.sender", "onlyowner",
    ],
    "docs": [
        "api", "endpoint", "authentication", "configuration", "installation",
        "setup", "guide", "reference", "documentation", "parameter",
        "response", "request", "route", "middleware", "schema",
    ],
    "product": [
        "quickcast", "agentos", "cifi", "wizard", "dashboard",
        "refinet cloud", "feature", "platform", "service", "product",
        "publish", "agent", "inference", "model",
    ],
    "about": [
        "refinet", "mission", "vision", "team", "sovereignty",
        "regenerative", "community", "open source", "free", "zero cost",
        "decentralization", "self-hosted", "circular",
    ],
    "faq": [
        "how to", "what is", "why", "question", "answer", "getting started",
        "troubleshoot", "common", "help", "support", "issue",
    ],
}


# ── Public API ────────────────────────────────────────────────────────

def generate_tags(
    text: str,
    doc_type: str = "txt",
    filename: Optional[str] = None,
    max_tags: int = 15,
) -> list[str]:
    """
    Generate auto-tags from document text.
    Returns list of natural language tag strings, ordered by relevance.
    Tags are optimized for LLM search — agents find documents by matching these.
    """
    if not text or not text.strip():
        return []

    # Step 1: Extract keyword candidates with scores
    keywords = _extract_keywords(text, top_n=30)

    # Step 2: Extract named entities
    entities = _extract_named_entities(text)

    # Step 3: File-type specific tags
    type_tags = _get_type_tags(doc_type, filename)

    # Merge candidates: entities first (high value), then keywords
    all_candidates = []
    seen = set()

    for tag in type_tags:
        tag_lower = tag.lower()
        if tag_lower not in seen:
            all_candidates.append(tag_lower)
            seen.add(tag_lower)

    for entity in entities:
        entity_lower = entity.lower()
        if entity_lower not in seen and len(entity_lower) > 2:
            all_candidates.append(entity_lower)
            seen.add(entity_lower)

    for kw, score in keywords:
        kw_lower = kw.lower()
        if kw_lower not in seen:
            all_candidates.append(kw_lower)
            seen.add(kw_lower)

    if not all_candidates:
        return []

    # Step 4: Diversity selection via embeddings (or fallback to top-N)
    selected = _select_diverse_tags(all_candidates, max_tags)

    return selected


def infer_category(text: str, tags: list[str]) -> str:
    """
    Infer the best knowledge category from text content and tags.
    Returns one of: about | product | docs | blockchain | contract | faq
    """
    text_lower = text.lower()
    combined = text_lower + " " + " ".join(tags)

    scores = {}
    for category, signals in CATEGORY_SIGNALS.items():
        score = sum(1 for signal in signals if signal in combined)
        # Boost by tag matches
        tag_boost = sum(2 for tag in tags if any(signal in tag for signal in signals))
        scores[category] = score + tag_boost

    if not scores or max(scores.values()) == 0:
        return "docs"  # Default category

    return max(scores, key=scores.get)


# ── Internal: Keyword Extraction ──────────────────────────────────────

def _extract_keywords(text: str, top_n: int = 30) -> list[tuple[str, float]]:
    """
    TF-IDF-like keyword extraction.
    Returns (keyword, score) pairs sorted by score descending.
    """
    text_lower = text.lower()

    # Tokenize into words
    words = re.findall(r'[a-z][a-z0-9_]+', text_lower)
    words = [w for w in words if w not in STOP_WORDS and len(w) > 2]

    if not words:
        return []

    total_words = len(words)

    # Unigram frequencies
    unigram_counts = Counter(words)

    # Bigram frequencies
    bigrams = [f"{words[i]} {words[i+1]}" for i in range(len(words) - 1)]
    bigram_counts = Counter(bigrams)
    # Filter bigrams where both parts are stop words or too short
    bigram_counts = {
        bg: count for bg, count in bigram_counts.items()
        if count >= 2 and not all(w in STOP_WORDS or len(w) <= 2 for w in bg.split())
    }

    # Score: TF * domain boost
    scored = {}

    for word, count in unigram_counts.items():
        tf = count / total_words
        # IDF approximation: rare words score higher
        idf = math.log(1 + total_words / count)
        boost = 2.0 if word in DOMAIN_BOOST_TERMS else 1.0
        scored[word] = tf * idf * boost

    for bigram, count in bigram_counts.items():
        tf = count / max(len(bigrams), 1)
        idf = math.log(1 + len(bigrams) / count)
        # Bigrams get a slight boost for being more specific
        boost = 1.5
        if any(w in DOMAIN_BOOST_TERMS for w in bigram.split()):
            boost = 3.0
        scored[bigram] = tf * idf * boost

    # Sort by score
    ranked = sorted(scored.items(), key=lambda x: x[1], reverse=True)
    return ranked[:top_n]


# ── Internal: Named Entity Extraction ─────────────────────────────────

def _extract_named_entities(text: str) -> list[str]:
    """
    Lightweight NER without spaCy. Extracts:
    - Capitalized multi-word phrases (proper nouns)
    - Ethereum addresses
    - camelCase/PascalCase identifiers (contract/function names)
    """
    entities = []
    seen = set()

    # Capitalized multi-word phrases (2-3 words)
    for match in re.finditer(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\b', text):
        phrase = match.group(1)
        if phrase.lower() not in seen and phrase.lower() not in STOP_WORDS:
            entities.append(phrase)
            seen.add(phrase.lower())

    # Ethereum addresses
    for match in re.finditer(r'\b(0x[a-fA-F0-9]{40})\b', text):
        addr = match.group(1)
        short = f"address {addr[:8]}...{addr[-4:]}"
        if short not in seen:
            entities.append(short)
            seen.add(short)

    # camelCase / PascalCase identifiers (likely function/contract names)
    for match in re.finditer(r'\b([a-z]+(?:[A-Z][a-z]+)+)\b', text):
        ident = match.group(1)
        # Convert camelCase to space-separated
        readable = re.sub(r'([A-Z])', r' \1', ident).strip().lower()
        if readable not in seen and len(readable) > 4:
            entities.append(readable)
            seen.add(readable)

    # PascalCase (contract names)
    for match in re.finditer(r'\b([A-Z][a-z]+(?:[A-Z][a-z]+)+)\b', text):
        ident = match.group(1)
        readable = re.sub(r'([A-Z])', r' \1', ident).strip().lower()
        if readable not in seen and len(readable) > 4:
            entities.append(readable)
            seen.add(readable)

    return entities[:15]  # Cap entities


# ── Internal: File-Type Tags ─────────────────────────────────────────

def _get_type_tags(doc_type: str, filename: Optional[str] = None) -> list[str]:
    """Generate tags based on file type."""
    tags = []

    type_map = {
        "pdf": ["pdf document"],
        "docx": ["word document"],
        "xlsx": ["spreadsheet data"],
        "csv": ["tabular data"],
        "sol": ["solidity contract", "smart contract"],
        "json": ["json data"],
        "md": ["documentation"],
        "txt": ["text document"],
    }

    tags.extend(type_map.get(doc_type, []))

    # Add filename-derived tag
    if filename:
        name = os.path.splitext(filename)[0]
        # Clean up filename: replace separators with spaces
        clean = re.sub(r'[-_.]', ' ', name).strip().lower()
        if clean and len(clean) > 2 and clean not in STOP_WORDS:
            tags.append(clean)

    return tags


# ── Internal: Diversity Selection ─────────────────────────────────────

def _select_diverse_tags(candidates: list[str], max_tags: int) -> list[str]:
    """
    Select diverse tags using embedding-based cosine distance.
    Falls back to top-N selection if embeddings unavailable.
    """
    if len(candidates) <= max_tags:
        return candidates

    try:
        from api.services.embedding import embed_batch, cosine_similarity, is_available

        if not is_available():
            return candidates[:max_tags]

        # Embed all candidates
        embeddings = embed_batch(candidates)
        if not embeddings or len(embeddings) != len(candidates):
            return candidates[:max_tags]

        # Greedy diversity selection: pick first, then iteratively pick
        # the candidate most distant from all already-selected
        selected_indices = [0]  # Start with highest-priority candidate

        for _ in range(max_tags - 1):
            if len(selected_indices) >= len(candidates):
                break

            best_idx = -1
            best_min_dist = -1.0

            for i in range(len(candidates)):
                if i in selected_indices:
                    continue
                # Min distance to any selected tag
                min_dist = min(
                    1.0 - cosine_similarity(embeddings[i], embeddings[j])
                    for j in selected_indices
                )
                if min_dist > best_min_dist:
                    best_min_dist = min_dist
                    best_idx = i

            if best_idx >= 0:
                selected_indices.append(best_idx)

        return [candidates[i] for i in sorted(selected_indices)]

    except ImportError:
        return candidates[:max_tags]
    except Exception as e:
        logger.warning(f"Embedding diversity selection failed, using fallback: {e}")
        return candidates[:max_tags]

