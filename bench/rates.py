"""USD list-price estimates for the model this loop calls.

ModelPlanner.from_env uses gpt-4o-mini unless LOOP_MODEL names another one.
Figures from this table are estimates, not an invoice.
"""

from __future__ import annotations

# USD per 1,000,000 tokens. List prices, used only as an estimate.
# gpt-4o-mini: OpenAI list price.
# deepseek-ai/DeepSeek-V4-Pro-0813: Nebius Token Factory catalog (input 1.32, cached 0.04, output 3.96).
# claude-sonnet-5-5: Anthropic Claude Sonnet 5.5 list price (input 2, cache read 0.10, output 10).
RATES: dict[str, dict[str, float]] = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60, "cached_input": 0.075},
    "deepseek-ai/DeepSeek-V4-Pro-0813": {"input": 1.32, "output": 3.96, "cached_input": 0.04},
    "claude-sonnet-5-5": {"input": 2.0, "output": 10.0, "cached_input": 0.10},
    # High list-price estimate so a Claude Opus retry counts against the spend cap.
    "claude-opus-5-5": {"input": 5.0, "output": 25.0, "cached_input": 0.50},
}


def estimate_dollars(
    model: str | None,
    input_tokens: int,
    output_tokens: int,
    *,
    llm_calls: int,
    cached_input_tokens: int = 0,
) -> dict:
    """Return estimated_dollars and dollars_are='estimate'.

    A run with no model call estimates 0. A named model with no row estimates
    null, and dollars_are stays 'estimate'.
    """
    priced = {
        "estimated_dollars": 0.0,
        "dollars_are": "estimate",
        "model": None,
        "rate_found": True,
    }
    if llm_calls <= 0:
        return priced
    priced["model"] = model
    rate = RATES.get(model or "")
    if rate is None:
        priced["estimated_dollars"] = None
        priced["rate_found"] = False
        return priced
    cached_rate = rate.get("cached_input", rate["input"])
    dollars = (
        input_tokens * rate["input"]
        + cached_input_tokens * cached_rate
        + output_tokens * rate["output"]
    ) / 1_000_000
    priced["estimated_dollars"] = round(dollars, 8)
    return priced


def cached_input_tokens(system_tokens: int, user_tokens: list[int], *, prompt_cache: bool) -> int:
    """Bill the system prompt in full on the first call.

    Later calls bill half of those system tokens when prompt caching is on.
    This is an estimate of a cache discount, not an invoice.
    """
    total = 0
    for index, user in enumerate(user_tokens):
        if prompt_cache and index:
            total += user + system_tokens // 2
        else:
            total += user + system_tokens
    return total
