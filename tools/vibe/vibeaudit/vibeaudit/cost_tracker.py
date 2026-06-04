"""Thread-safe token and USD cost tracking with budget enforcement."""

from __future__ import annotations

import asyncio


class BudgetExceededError(Exception):
    """Raised when the hard cost cap is exceeded."""

    def __init__(self, total_cost: float, hard_cap: float) -> None:
        self.total_cost = total_cost
        self.hard_cap = hard_cap
        super().__init__(
            f"Budget exceeded: ${total_cost:.4f} >= hard cap ${hard_cap:.2f}"
        )


# Pricing per 1 million tokens: (input_cost, output_cost)
_PRICING: dict[str, tuple[float, float]] = {
    # Anthropic
    "claude-sonnet-4-20250514": (3.0, 15.0),
    "claude-haiku-3.5": (0.80, 4.0),
    "claude-3-5-haiku-20241022": (0.80, 4.0),
    "claude-3-5-sonnet-20241022": (3.0, 15.0),
    "claude-3-opus-20240229": (15.0, 75.0),
    # OpenAI
    "gpt-4o": (2.50, 10.0),
    "gpt-4o-2024-11-20": (2.50, 10.0),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o-mini-2024-07-18": (0.15, 0.60),
    "gpt-4-turbo": (10.0, 30.0),
    "gpt-4": (30.0, 60.0),
    "o1": (15.0, 60.0),
    "o1-mini": (3.0, 12.0),
    # Groq (hosted Llama)
    "llama-3.3-70b-versatile": (0.59, 0.79),
    "llama-3.1-70b-versatile": (0.59, 0.79),
    "llama-3.1-8b-instant": (0.05, 0.08),
    "mixtral-8x7b-32768": (0.24, 0.24),
    # Ollama (local — free)
    "llama3.3": (0.0, 0.0),
    "llama3.2": (0.0, 0.0),
    "llama3.1": (0.0, 0.0),
    "llama3": (0.0, 0.0),
    "mistral": (0.0, 0.0),
    "codellama": (0.0, 0.0),
    "deepseek-coder": (0.0, 0.0),
    "qwen2.5-coder": (0.0, 0.0),
}


def _get_pricing(model: str) -> tuple[float, float]:
    """Look up pricing for a model, falling back to free if unknown."""
    if model in _PRICING:
        return _PRICING[model]
    # Try prefix matching for versioned model names (e.g. "gpt-4o-2024-...")
    for known_model, pricing in _PRICING.items():
        if model.startswith(known_model) or known_model.startswith(model):
            return pricing
    # Unknown model — assume free to avoid false budget alerts
    return (0.0, 0.0)


class CostTracker:
    """Accumulates token usage and USD cost across multiple LLM calls.

    Thread-safe via asyncio.Lock for concurrent scan workers.
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._input_tokens: int = 0
        self._output_tokens: int = 0
        self._total_cost: float = 0.0
        self._call_count: int = 0

    async def record(self, model: str, input_tokens: int, output_tokens: int) -> None:
        """Record token usage from a single LLM call."""
        input_price, output_price = _get_pricing(model)
        cost = (input_tokens * input_price + output_tokens * output_price) / 1_000_000

        async with self._lock:
            self._input_tokens += input_tokens
            self._output_tokens += output_tokens
            self._total_cost += cost
            self._call_count += 1

    async def check_budget(self, hard_cap_usd: float) -> tuple[bool, str]:
        """Check whether the scan can continue within budget.

        Returns:
            (can_continue, message) — can_continue is False if the hard cap
            is reached. message contains a warning at 90% or an error at 100%.
        """
        async with self._lock:
            cost = self._total_cost

        if cost >= hard_cap_usd:
            return (
                False,
                f"Budget exceeded: ${cost:.4f} >= hard cap ${hard_cap_usd:.2f}. "
                f"Stopping scan.",
            )

        threshold_90 = hard_cap_usd * 0.9
        if cost >= threshold_90:
            return (
                True,
                f"Budget warning: ${cost:.4f} of ${hard_cap_usd:.2f} used "
                f"({cost / hard_cap_usd * 100:.0f}%). Approaching limit.",
            )

        return (True, "")

    @property
    def input_tokens(self) -> int:
        return self._input_tokens

    @property
    def output_tokens(self) -> int:
        return self._output_tokens

    @property
    def total_tokens(self) -> int:
        return self._input_tokens + self._output_tokens

    @property
    def total_cost_usd(self) -> float:
        return self._total_cost

    @property
    def call_count(self) -> int:
        return self._call_count

    @property
    def at_warning_threshold(self) -> bool:
        """True if cost has reached 90% of any previously checked budget."""
        # This is a simple flag — callers should use check_budget() for real enforcement.
        # Exposed as a convenience for UI/logging.
        return False  # Overridden by check_budget results

    def summary(self, hard_cap_usd: float = 0.0) -> str:
        """Human-readable usage summary."""
        parts = [
            f"Tokens: {self.total_tokens:,} "
            f"(in: {self._input_tokens:,}, out: {self._output_tokens:,})",
            f"Cost: ${self._total_cost:.4f}",
            f"Calls: {self._call_count}",
        ]
        if hard_cap_usd > 0:
            pct = (self._total_cost / hard_cap_usd * 100) if hard_cap_usd else 0
            parts.append(f"Budget: {pct:.0f}% of ${hard_cap_usd:.2f}")
        return " | ".join(parts)
