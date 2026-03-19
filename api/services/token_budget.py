"""
REFINET Cloud — Token Budget Tracker
Manages BitNet's context window allocation across injection layers.
Ensures system prompts never exceed the model's context window.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger("refinet.token_budget")


# Default layer budgets (tokens) for a 2048-token context window
# with 512 tokens reserved for completion output.
# Total usable for system prompt + user content: 1536 tokens.
DEFAULT_LAYER_BUDGETS = {
    "soul": 300,        # Layer 0: Root SOUL.md — guaranteed
    "agent_soul": 200,  # Layer 1: Per-agent SOUL — guaranteed
    "memory": 100,      # Layer 2: Memory state — flexible
    "rag": 400,         # Layer 3: RAG context — flexible (first to truncate)
    "skills": 50,       # Layer 4: Skills metadata — flexible
    "safety": 150,      # Layer 5: SAFETY.md — guaranteed
    "runtime": 50,      # Layer 6: Runtime context — guaranteed
    "user_prompt": 286, # Remaining for user content
}

# Layers that can be truncated when over budget (in truncation order)
FLEXIBLE_LAYERS = ["rag", "memory", "skills"]

# Layers that are never truncated
GUARANTEED_LAYERS = ["soul", "safety", "agent_soul", "runtime"]


def estimate_tokens(text: str) -> int:
    """
    Estimate token count using 4-chars-per-token heuristic.
    Matches the pattern used in rag.py chunk_text().
    """
    if not text:
        return 0
    return max(1, len(text) // 4)


def truncate_to_tokens(text: str, max_tokens: int) -> str:
    """
    Truncate text to fit within a token budget.
    Breaks at sentence boundaries when possible.
    """
    if not text:
        return ""

    estimated = estimate_tokens(text)
    if estimated <= max_tokens:
        return text

    # Approximate character limit
    char_limit = max_tokens * 4

    # Try to break at last sentence boundary before limit
    truncated = text[:char_limit]
    last_period = truncated.rfind(". ")
    last_newline = truncated.rfind("\n")
    break_point = max(last_period, last_newline)

    if break_point > char_limit // 2:
        return truncated[:break_point + 1].rstrip()

    return truncated.rstrip()


@dataclass
class TokenBudget:
    """
    Manages token allocation across context injection layers.

    Usage:
        budget = TokenBudget(context_window=2048)
        soul_text = budget.allocate("soul", soul_md_content)
        safety_text = budget.allocate("safety", safety_md_content)
        rag_text = budget.allocate("rag", rag_context)
        report = budget.report()
    """
    context_window: int = 2048
    reserved_for_completion: int = 512
    layer_budgets: dict[str, int] = field(default_factory=lambda: dict(DEFAULT_LAYER_BUDGETS))
    allocations: dict[str, int] = field(default_factory=dict)
    _texts: dict[str, str] = field(default_factory=dict)

    @property
    def total_usable(self) -> int:
        """Total tokens available for system prompt + user content."""
        return self.context_window - self.reserved_for_completion

    @property
    def allocated(self) -> int:
        """Total tokens allocated so far."""
        return sum(self.allocations.values())

    @property
    def remaining(self) -> int:
        """Tokens remaining for additional layers."""
        return max(0, self.total_usable - self.allocated)

    def allocate(self, layer: str, text: str) -> str:
        """
        Allocate tokens for a layer, truncating if needed.
        Returns the (possibly truncated) text.
        """
        if not text:
            self.allocations[layer] = 0
            self._texts[layer] = ""
            return ""

        max_tokens = self.layer_budgets.get(layer, 100)

        # For guaranteed layers, use their budget directly
        # For flexible layers, also consider remaining budget
        if layer in FLEXIBLE_LAYERS:
            max_tokens = min(max_tokens, self.remaining)

        result = truncate_to_tokens(text, max_tokens)
        tokens_used = estimate_tokens(result)
        self.allocations[layer] = tokens_used
        self._texts[layer] = result

        if tokens_used < estimate_tokens(text):
            logger.debug(
                f"Layer '{layer}' truncated: {estimate_tokens(text)} → {tokens_used} tokens"
            )

        return result

    def report(self) -> dict:
        """Return a summary of token allocation across layers."""
        return {
            "context_window": self.context_window,
            "reserved_for_completion": self.reserved_for_completion,
            "total_usable": self.total_usable,
            "allocated": self.allocated,
            "remaining": self.remaining,
            "layers": {
                layer: {
                    "budget": self.layer_budgets.get(layer, 0),
                    "used": tokens,
                    "utilization": f"{tokens / self.layer_budgets.get(layer, 1):.0%}"
                    if self.layer_budgets.get(layer) else "N/A",
                }
                for layer, tokens in self.allocations.items()
            },
        }


def create_budget(model: str = "bitnet-b1.58-2b") -> TokenBudget:
    """
    Create a TokenBudget configured for the given model.
    Reads context window from the provider registry if available.
    """
    try:
        from api.services.providers.registry import _CONTEXT_WINDOWS
        context_window = _CONTEXT_WINDOWS.get(model, 2048)
    except ImportError:
        context_window = 2048

    # Scale budgets if context window is larger than default 2048
    if context_window > 2048:
        scale = min(context_window / 2048, 4.0)  # Cap scaling at 4x
        scaled_budgets = {
            k: int(v * scale) for k, v in DEFAULT_LAYER_BUDGETS.items()
        }
        return TokenBudget(
            context_window=context_window,
            reserved_for_completion=min(1024, context_window // 4),
            layer_budgets=scaled_budgets,
        )

    return TokenBudget(context_window=context_window)
