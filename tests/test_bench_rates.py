from pathlib import Path

from bench.rates import RATES, estimate_dollars

ROOT = Path(__file__).resolve().parents[1]


def test_rate_table_covers_the_model_this_loop_calls():
    source = (ROOT / "loop" / "planner.py").read_text(encoding="utf-8")
    assert 'os.environ.get("LOOP_MODEL", "gpt-4o-mini")' in source
    assert "gpt-4o-mini" in RATES


def test_gpt_4o_mini_dollars_are_an_estimate():
    priced = estimate_dollars("gpt-4o-mini", 1_000_000, 2_000_000, llm_calls=1)
    assert priced["dollars_are"] == "estimate"
    assert priced["model"] == "gpt-4o-mini"
    assert priced["estimated_dollars"] == 1.35


def test_no_model_call_estimates_zero_dollars():
    priced = estimate_dollars(None, 0, 0, llm_calls=0)
    assert priced["estimated_dollars"] == 0.0
    assert priced["dollars_are"] == "estimate"
    assert priced["model"] is None


def test_unknown_model_has_no_dollar_figure():
    priced = estimate_dollars("missing-model", 10, 10, llm_calls=1)
    assert priced["estimated_dollars"] is None
    assert priced["dollars_are"] == "estimate"
    assert priced["rate_found"] is False
