"""OpenAI is a computer-use model under test. No network and no Claude ledger rewrite."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from bench.budget import ALLOWED_MODEL, SpendLedger
from bench.openai_client import OpenAIClient, anthropic_shaped, responses_payload
from bench.openai_spend import (
    ALLOWED_OPENAI_MODELS,
    DEFAULT_EFFORT,
    LONG_CONTEXT_INPUT_TOKENS,
    OPENAI_PROJECT_BUDGET_USD,
    OPENAI_RUN_BUDGET_USD,
    OPENAI_SWEEP_BUDGET_USD,
    UNPRICED_CALL_RESERVE_USD,
    UNRECORDED_CALL_ALLOWANCE_USD,
    EffortNotAllowed,
    OpenAIModelNotAllowed,
    OpenAISpendLedger,
    PriceUnknown,
    assert_effort,
    assert_openai_model,
    efforts_for,
    price_usd,
    probe_command,
    sweep_cells,
    sweep_command,
    tokens_at_run_cap,
)
from bench.probe import main
from bench.report import render
from bench.tasks import TUNED_PROBE_TASK_IDS

REFUSED = ("gpt-6-sol", "gpt-5.6-sol", "gpt-5.6-luna", "gpt-4o", "claude-sonnet-5-5", "gpt-6.1-sol-fast", "")


def test_allow_list_is_exactly_the_two_models():
    assert ALLOWED_OPENAI_MODELS == ("gpt-6.1-sol", "gpt-6-luna")
    for model in ALLOWED_OPENAI_MODELS:
        assert assert_openai_model(model) == model
        assert efforts_for(model) == ("low", "medium", "high", "xhigh")
    for name in REFUSED:
        with pytest.raises(OpenAIModelNotAllowed):
            assert_openai_model(name)
        with pytest.raises(OpenAIModelNotAllowed):
            price_usd(name, 1, 1)


def test_unknown_effort_is_refused_and_xhigh_is_accepted():
    for model in ALLOWED_OPENAI_MODELS:
        for effort in ("low", "medium", "high", "xhigh"):
            assert assert_effort(model, effort) == effort
        for effort in ("minimal", "none", "max", "x-high", "Low", ""):
            with pytest.raises(EffortNotAllowed):
                assert_effort(model, effort)


def test_prices_are_the_published_standard_rates():
    assert price_usd("gpt-6.1-sol", 100_000, 0) == 0.2
    assert price_usd("gpt-6.1-sol", 0, 100_000) == 1.0
    assert price_usd("gpt-6.1-sol", 100_000, 0, 100_000) == 0.01
    assert price_usd("gpt-6-luna", 100_000, 0) == 0.01
    assert price_usd("gpt-6-luna", 0, 100_000) == 0.05
    assert price_usd("gpt-6-luna", 100_000, 0, 100_000) == 0.001
    assert price_usd("gpt-6.1-sol", LONG_CONTEXT_INPUT_TOKENS, 0) == 0.544
    long_in = LONG_CONTEXT_INPUT_TOKENS + 1
    assert price_usd("gpt-6.1-sol", long_in, 0) == 1.088004
    assert price_usd("gpt-6-luna", long_in, 2) == 0.054402
    sol = tokens_at_run_cap("gpt-6.1-sol")
    luna = tokens_at_run_cap("gpt-6-luna")
    assert sol["measured_run_usd"] is None
    assert sol["uncached_input_tokens"] == 2_500_000
    assert sol["output_tokens"] == 500_000
    assert luna["uncached_input_tokens"] == 50_000_000
    assert luna["output_tokens"] == 10_000_000
    assert OPENAI_RUN_BUDGET_USD == 5
    assert OPENAI_PROJECT_BUDGET_USD == 20
    assert OPENAI_SWEEP_BUDGET_USD == 15


def _priced(model: str, usage: dict) -> float:
    return price_usd(
        model,
        usage["input_tokens"],
        usage["output_tokens"],
        usage["cached_tokens"],
        usage["cache_write_30m_tokens"],
        usage["cache_write_12h_tokens"],
    )


def test_cache_write_tokens_in_a_real_usage_report_are_priced():
    """The shape that stopped the sweep, plus the published lifetime split.

    Writes are a slice of input_tokens. 30-minute writes are 1.25x input.
    A 12-hour split is 2.5x. An unknown field is still refused.
    """
    reported = {
        "output": [{"type": "message", "content": [{"type": "output_text", "text": "TASK_COMPLETE"}]}],
        "usage": {
            "input_tokens": 12000,
            "output_tokens": 100,
            "total_tokens": 12100,
            "input_tokens_details": {
                "cached_tokens": 4000,
                "cache_write_tokens": 7000,
            },
            "output_tokens_details": {"reasoning_tokens": 20},
        },
    }
    usage = anthropic_shaped(reported)["usage"]
    assert usage["cache_write_30m_tokens"] == 7000
    assert usage["cache_write_12h_tokens"] == 0
    # ordinary 1000 at $2, cached 4000 at $0.10, writes 7000 at $2.50, output 100 at $10.
    assert f"{_priced('gpt-6.1-sol', usage):.6f}" == "0.020900"
    # ordinary 1000 at $0.10, cached 4000 at $0.01, writes 7000 at $0.125, output 100 at $0.50.
    assert f"{_priced('gpt-6-luna', usage):.6f}" == "0.001065"

    split = {
        "output": [{"type": "message", "content": [{"type": "output_text", "text": "done"}]}],
        "usage": {
            "input_tokens": 12000,
            "output_tokens": 100,
            "total_tokens": 12100,
            "input_tokens_details": {
                "cached_tokens": 4000,
                "cache_write_tokens": 7000,
                "cache_write_tokens_details": {"ttl_30m_tokens": 3000, "ttl_12h_tokens": 4000},
            },
            "output_tokens_details": {"reasoning_tokens": 20},
        },
    }
    detailed = anthropic_shaped(split)["usage"]
    assert detailed["cache_write_30m_tokens"] == 3000
    assert detailed["cache_write_12h_tokens"] == 4000
    # 1000*$2 + 4000*$0.10 + 3000*$2.50 + 4000*$5 + 100*$10, per million.
    assert f"{_priced('gpt-6.1-sol', detailed):.6f}" == "0.030900"
    assert f"{_priced('gpt-6-luna', detailed):.6f}" == "0.001565"
    long_write = price_usd("gpt-6-luna", LONG_CONTEXT_INPUT_TOKENS + 1, 0, 0, 1000, 0)
    assert f"{long_write:.6f}" == "0.054450"

    with pytest.raises(PriceUnknown):
        anthropic_shaped(
            {
                "output": [{"type": "message", "content": [{"type": "output_text", "text": "TASK_COMPLETE"}]}],
                "usage": {
                    "input_tokens": 10,
                    "output_tokens": 2,
                    "input_tokens_details": {"cached_tokens": 1, "cache_write_tokens": 4, "audio_tokens": 3},
                },
            }
        )
    with pytest.raises(OpenAIModelNotAllowed):
        price_usd("gpt-6-sol", 10, 2, 0, 4, 0)


def test_client_sends_function_tools_and_effort_without_a_socket(monkeypatch):
    seen = {}

    def transport(url, headers, payload):
        seen["url"] = url
        seen["headers"] = headers
        seen["payload"] = payload
        return json.dumps(
            {
                "output": [
                    {
                        "type": "function_call",
                        "call_id": "call_1",
                        "name": "run_script",
                        "arguments": json.dumps({"code": "page.goto(\"https://example.test\")"}),
                    }
                ],
                "usage": {
                    "input_tokens": 20,
                    "output_tokens": 5,
                    "input_tokens_details": {"cached_tokens": 4},
                    "output_tokens_details": {"reasoning_tokens": 1},
                },
            }
        )

    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("socket")),
    )
    client = OpenAIClient("local-test-not-sent", "gpt-6.1-sol", "low", transport=transport)
    response, _elapsed = asyncio.run(
        client.create_message(
            [{"role": "user", "content": "Task: look"}],
            [{"name": "run_script", "description": "run", "input_schema": {"type": "object"}}],
            system="stay on the page",
        )
    )
    assert seen["url"] == "https://api.openai.com/v1/responses"
    assert seen["payload"]["model"] == "gpt-6.1-sol"
    assert seen["payload"]["reasoning"] == {"effort": "low"}
    assert seen["payload"]["tools"] == [
        {
            "type": "function",
            "name": "run_script",
            "description": "run",
            "parameters": {"type": "object"},
        }
    ]
    assert "computer_use" not in json.dumps(seen["payload"])
    assert seen["headers"]["Authorization"] == "Bearer local-test-not-sent"
    assert response["usage"] == {
        "input_tokens": 20,
        "output_tokens": 5,
        "cached_tokens": 4,
        "cache_write_30m_tokens": 0,
        "cache_write_12h_tokens": 0,
    }
    assert response["content"][0]["type"] == "tool_use"
    assert response["content"][0]["input"] == {"code": "page.goto(\"https://example.test\")"}
    with pytest.raises(OpenAIModelNotAllowed):
        responses_payload("gpt-6-sol", [], [], None, 16, "low")


def test_dry_run_does_not_call_or_rewrite_ledgers(monkeypatch, capsys, isolated_spend_ledger, isolated_openai_spend_ledger):
    before = isolated_spend_ledger.read_bytes()
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("socket")),
    )

    def explode(*_args, **_kwargs):
        raise AssertionError("dry run executed")

    monkeypatch.setattr("bench.probe.execute_probe", explode)
    assert main(["--provider", "openai", "--model", "gpt-6.1-sol", "--effort", "high"]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert isolated_spend_ledger.read_bytes() == before
    assert not isolated_openai_spend_ledger.exists()
    assert printed["provider"] == "openai"
    assert printed["outer_model"] == "gpt-6.1-sol"
    assert printed["effort"] == "high"
    assert printed["tasks"] == list(TUNED_PROBE_TASK_IDS)
    assert printed["allowed_models"] == ["gpt-6.1-sol", "gpt-6-luna"]
    assert printed["measured_run_usd"] is None
    assert printed["per_run_cap_usd"] == 5
    assert printed["network"] == "refused"
    assert "gpt-6-sol" not in json.dumps(printed)
    assert "gpt-5.6" not in json.dumps(printed)
    assert probe_command("gpt-6.1-sol", "medium") in printed["box_commands"]
    assert probe_command("gpt-6-luna", "medium") in printed["box_commands"]

    assert main(["--provider", "openai", "--model", "gpt-6-sol"]) == 2
    assert "Refusing" in capsys.readouterr().err
    assert isolated_spend_ledger.read_bytes() == before

    assert main(["--provider", "openai", "--sweep-effort"]) == 0
    sweep = json.loads(capsys.readouterr().out)
    assert sweep["tasks"] == [TUNED_PROBE_TASK_IDS[0]]
    assert sweep["models"] == ["gpt-6-luna", "gpt-6.1-sol"]
    assert sweep["efforts"] == ["low", "medium", "high", "xhigh", "low", "medium", "high", "xhigh"]
    assert sweep["sweep_cap_usd"] == 15
    assert sweep["per_run_cap_usd"] == 5
    assert sweep_command() in sweep["box_commands"]
    assert len(sweep_cells()) == 8
    assert isolated_spend_ledger.read_bytes() == before
    assert not isolated_openai_spend_ledger.exists()
    assert DEFAULT_EFFORT == "medium"
    assert ALLOWED_MODEL == "claude-sonnet-5-5"


def test_one_run_uses_one_model_and_stops_at_five(monkeypatch, tmp_path, isolated_spend_ledger):
    before = isolated_spend_ledger.read_bytes()
    calls = []
    monkeypatch.setenv("OPENAI_API_KEY", "local-test-not-sent")
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("socket")),
    )

    async def arm(name, task, **kwargs):
        calls.append((name, task["id"], kwargs.get("model"), kwargs.get("effort"), kwargs.get("provider")))
        return {
            "arm": name,
            "task_id": task["id"],
            "success": False,
            "success_reason": "mocked",
            "skipped": False,
            "wall_ms": 1,
            "steps": 1,
            "input_tokens": 0,
            "output_tokens": 300_000,
            "usd": 0,
            "claude": False,
        }

    async def browser(task, **kwargs):
        return await arm("browser_use", task, **kwargs)

    monkeypatch.setattr("bench.probe.run_claude_arm", arm)
    monkeypatch.setattr("bench.browser_use_arm.run_browser_use_task", browser)
    assert (
        main(
            [
                "--execute",
                "--provider",
                "openai",
                "--model",
                "gpt-6.1-sol",
                "--effort",
                "low",
                "--arms",
                "script_first,playwright_mcp,stagehand,browser_use",
            ]
        )
        == 0
    )
    assert isolated_spend_ledger.read_bytes() == before
    models = {item[2] for item in calls}
    efforts = {item[3] for item in calls}
    assert models == {"gpt-6.1-sol"}
    assert efforts == {"low"}
    assert all(item[4] == "openai" for item in calls)
    # 300_000 output tokens at $10 / MTok is $3. The next arm waits until the run has reached $5.
    assert len(calls) == 2
    ledger = OpenAISpendLedger.read()
    assert ledger.running_total_usd == round(6.0 + UNRECORDED_CALL_ALLOWANCE_USD, 6)
    assert ledger.path.name == "openai-spend.json"
    saved = json.loads(ledger.path.read_text(encoding="utf-8"))
    assert saved["provider"] == "openai"
    assert "claude-sonnet-5-5" not in ledger.path.read_text(encoding="utf-8")


def test_opening_allowance_counts_against_the_run_and_sweep_caps(
    monkeypatch, isolated_spend_ledger, isolated_openai_spend_ledger
):
    """The unrecorded call sits inside the $5 cell and the $15 sweep, not beside them."""
    before = isolated_spend_ledger.read_bytes()
    monkeypatch.setenv("OPENAI_API_KEY", "local-test-not-sent")
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("socket")),
    )
    calls = []

    async def arm(name, task, **kwargs):
        del task, kwargs
        calls.append(name)
        return {
            "arm": name,
            "task_id": "wv_wikipedia_search",
            "success": False,
            "success_reason": "mocked",
            "skipped": False,
            "wall_ms": 1,
            "steps": 1,
            "input_tokens": 0,
            "output_tokens": 496_000,
            "usd": 0,
            "claude": False,
        }

    monkeypatch.setattr("bench.probe.run_claude_arm", arm)
    assert (
        main(
            [
                "--execute",
                "--provider",
                "openai",
                "--model",
                "gpt-6.1-sol",
                "--effort",
                "low",
                "--sweep-task",
                "--arms",
                "script_first,playwright_mcp",
            ]
        )
        == 0
    )
    # $4.96 of output plus the $0.05 allowance reaches the $5 cell, so the second arm does not start.
    assert calls == ["script_first"]
    assert isolated_spend_ledger.read_bytes() == before

    calls.clear()
    monkeypatch.setattr("bench.openai_run.OPENAI_SWEEP_BUDGET_USD", UNRECORDED_CALL_ALLOWANCE_USD)
    fresh = isolated_openai_spend_ledger.parent / "sweep-spend.json"
    monkeypatch.setenv("CU_OPENAI_SPEND_LEDGER", str(fresh))
    assert (
        main(
            [
                "--execute",
                "--provider",
                "openai",
                "--sweep-effort",
                "--arms",
                "script_first",
            ]
        )
        == 0
    )
    assert calls == []
    assert OpenAISpendLedger.read().running_total_usd == UNRECORDED_CALL_ALLOWANCE_USD


def test_unpriced_call_is_saved_before_the_abort(monkeypatch, isolated_spend_ledger, isolated_openai_spend_ledger):
    """A pricing refusal still exits 2, and the ledger exists before that exit.

    The first run also keeps the one call that died before any file was written.
    Both amounts sit in the project total the $20 cap reads.
    """
    before = isolated_spend_ledger.read_bytes()
    monkeypatch.setenv("OPENAI_API_KEY", "local-test-not-sent")
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("socket")),
    )

    async def refuse(*args, **kwargs):
        del args, kwargs
        raise PriceUnknown("Input usage has unrecognized fields ['audio_tokens']. Refusing to price.")

    monkeypatch.setattr("bench.probe.run_claude_arm", refuse)
    assert (
        main(
            [
                "--execute",
                "--provider",
                "openai",
                "--model",
                "gpt-6-luna",
                "--effort",
                "low",
                "--sweep-task",
                "--arms",
                "script_first",
            ]
        )
        == 2
    )
    assert isolated_spend_ledger.read_bytes() == before
    assert isolated_openai_spend_ledger.is_file()
    ledger = OpenAISpendLedger.read()
    assert ledger.aborted is True
    assert "audio_tokens" in (ledger.abort_reason or "")
    assert ledger.running_total_usd == round(UNRECORDED_CALL_ALLOWANCE_USD + UNPRICED_CALL_RESERVE_USD, 6)
    assert ledger.running_total_usd < OPENAI_RUN_BUDGET_USD
    assert ledger.running_total_usd < OPENAI_SWEEP_BUDGET_USD
    assert ledger.running_total_usd < OPENAI_PROJECT_BUDGET_USD
    again = OpenAISpendLedger.read()
    assert again.cover_unrecorded_call() == 0.0
    assert again.running_total_usd == ledger.running_total_usd


def test_report_prints_effort_and_claude_rows_stay_the_same():
    text = render(
        [
            {
                "arm": "script_first",
                "task_id": "wv_wikipedia_search",
                "pass": "cold",
                "wall_ms": 10,
                "steps": 1,
                "tier": "fresh",
                "usd": 0.25,
                "provider": "openai",
                "model": "gpt-6-luna",
                "effort": "xhigh",
            }
        ]
    )
    assert "effort=xhigh" in text
    assert "model=gpt-6-luna" in text
    unchanged = render(
        [
            {
                "arm": "stagehand",
                "task_id": "wv_wikipedia_search",
                "pass": "cold",
                "wall_ms": 10,
                "steps": 1,
                "tier": "fresh",
                "usd": 0.25,
            }
        ]
    )
    assert "effort=" not in unchanged
    assert "model=" not in unchanged


def test_claude_plan_is_unchanged(capsys, isolated_spend_ledger):
    del isolated_spend_ledger
    assert main([]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["outer_model"] == "claude-sonnet-5-5"
    assert "gpt-6.1-sol" not in json.dumps(printed)
    assert SpendLedger.load().model == "claude-sonnet-5-5"
