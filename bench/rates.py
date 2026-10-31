"""USD list-price estimates for the model this loop calls.

ModelPlanner.from_env uses gpt-4o-mini unless LOOP_MODEL names another one.
Figures from this table are estimates, not an invoice.
"""

from __future__ import annotations

# USD per 1,000,000 tokens. OpenAI published list price for gpt-4o-mini.
RATES: dict[str, dict[str, float]] = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
}


def estimate_dollars(
    model: str | None,
    input_tokens: int,
    output_tokens: int,
    *,
    llm_calls: int,
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
    dollars = (input_tokens * rate["input"] + output_tokens * rate["output"]) / 1_000_000
    priced["estimated_dollars"] = round(dollars, 6)
    return priced
