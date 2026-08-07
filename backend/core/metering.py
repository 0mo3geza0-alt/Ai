"""Usage-based credit metering.

Every AI request's REAL cost on the Emergent Universal Key is estimated from the
model used + token counts, then the org is charged a markup in credits:
  * free users  -> 4x the real cost
  * paid users  -> 3x the real cost

Text-type generations (chat / search / document / code / VibeVerse Pro) are
metered this way. Images / audio / music are feature-gated per plan instead of
credit-metered (see studio/router.py), so "unlimited images" plans stay unlimited.

All tunables (prices, multipliers, credit anchor) live here so pricing is easy to adjust.
"""
import contextvars

# ---- token counting (tiktoken if available, else a rough heuristic) ----
try:
    import tiktoken
    _ENC = tiktoken.get_encoding("cl100k_base")

    def count_tokens(text: str) -> int:
        try:
            return len(_ENC.encode(text or ""))
        except Exception:
            return max(1, len(text or "") // 4)
except Exception:  # pragma: no cover
    def count_tokens(text: str) -> int:
        return max(1, len(text or "") // 4)


# ---- model prices: USD per 1,000,000 tokens (input, output) ----
# Keyed by model name; matched exactly first, then by longest-prefix substring.
MODEL_PRICES = {
    # top tier
    "gpt-5.6-terra": (5.0, 25.0),
    "claude-sonnet-5": (5.0, 25.0),
    "gemini-3.1-pro-preview": (5.0, 25.0),
    # mid tier
    "gpt-5.4": (3.0, 15.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "gpt-5.4-mini": (0.5, 2.0),
    # cheap / flash tier
    "gemini-3.1-flash": (0.15, 0.6),
    "gemini-3-flash-preview": (0.15, 0.6),
}
DEFAULT_PRICE = (1.0, 5.0)

# credits = real_usd * CREDIT_PER_USD * multiplier  (tunable anchor)
CREDIT_PER_USD = 1500.0
MULTIPLIER = {"free": 4.0}      # everything else (paid) => 3x
PAID_MULTIPLIER = 3.0
MIN_CREDITS = 0.1              # tiny floor so trivial calls still cost something


def price_for(model: str) -> tuple[float, float]:
    if not model:
        return DEFAULT_PRICE
    if model in MODEL_PRICES:
        return MODEL_PRICES[model]
    best = None
    for key, price in MODEL_PRICES.items():
        if key in model and (best is None or len(key) > len(best[0])):
            best = (key, price)
    return best[1] if best else DEFAULT_PRICE


def cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    pin, pout = price_for(model)
    return (prompt_tokens / 1_000_000.0) * pin + (completion_tokens / 1_000_000.0) * pout


# ---- per-request usage accumulator (context-local, so it is request-safe) ----
_usage = contextvars.ContextVar("vv_usage_usd", default=None)


def reset():
    """Start a fresh metering window for the current request."""
    _usage.set(0.0)


def record(model: str, prompt_tokens: int, completion_tokens: int):
    """Add one model call's real cost to the current request's running total."""
    cur = _usage.get()
    if cur is None:
        cur = 0.0
    _usage.set(cur + cost_usd(model, prompt_tokens, completion_tokens))


def record_text(model: str, prompt_text: str, completion_text: str):
    record(model, count_tokens(prompt_text), count_tokens(completion_text))


def real_usd() -> float:
    return _usage.get() or 0.0


def multiplier(plan: str) -> float:
    return MULTIPLIER.get((plan or "free").lower(), PAID_MULTIPLIER)


def credits_for(plan: str, usd: float | None = None) -> float:
    """Credits to charge for the current request (or an explicit usd amount)."""
    if usd is None:
        usd = real_usd()
    credits = usd * CREDIT_PER_USD * multiplier(plan)
    return round(max(MIN_CREDITS, credits), 2)
