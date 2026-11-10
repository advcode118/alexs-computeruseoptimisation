"""Offline plan for the honest live probe. No network and no ledger rewrite."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from bench.budget import (
    LAST_RECORDED_TOTAL_USD,
    LIFETIME_CAP_USD,
    PROJECT_BUDGET_USD,
    LedgerBelowRecorded,
    SpendLedger,
    estimate_usd,
)
from bench.probe import (
    HONEST_ARMS,
    HONEST_PROBE_BUDGET_USD,
    ProbeRefused,
    arm_report,
    execute_probe,
    honest_run_budget,
    honest_task_reserve_usd,
    main,
    row_took_repair,
)
from bench.tasks import DEV_TASK_IDS, HELD_OUT_TASK_IDS, HONEST_TASK_IDS, TUNED_PROBE_TASK_IDS

LIVE_COMMAND = (
    'CU_SPEND_LEDGER="$CU_SPEND_LEDGER" '
    'ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" '
    "python -m bench.probe --execute --honest"
)


def _set_total(path: Path, total: float) -> None:
    ledger = SpendLedger.load(path)
    base = round(ledger.running_total_usd - ledger.recorded_extra_usd, 6)
    ledger.recorded_extra_usd = round(total - base, 6)
    ledger.recompute()
    assert ledger.running_total_usd == total
    ledger.save()


def test_reserve_is_the_harness_ceiling_and_the_run_stops_inside_five_to_eight():
    import inspect

    from bench.browser_use_arm import BROWSER_USE_MAX_STEPS
    from bench.harness import MAX_HISTORY_PAIRS, MAX_SNAPSHOT_CHARS, AnthropicClient, BenchmarkHarness

    widest = max(
        int(inspect.signature(BenchmarkHarness.__init__).parameters["max_steps"].default),
        int(BROWSER_USE_MAX_STEPS),
    )
    per_call_in = max(1, (MAX_SNAPSHOT_CHARS * MAX_HISTORY_PAIRS) // 4)
    per_call_out = int(inspect.signature(AnthropicClient.create_message).parameters["max_tokens"].default)
    assert honest_task_reserve_usd() == round(estimate_usd(widest * per_call_in, widest * per_call_out), 6)
    stop_at = HONEST_PROBE_BUDGET_USD - honest_task_reserve_usd()
    assert 5.0 <= stop_at < HONEST_PROBE_BUDGET_USD == 8.0


def test_run_budget_uses_the_recorded_total_and_both_caps():
    assert honest_run_budget(LAST_RECORDED_TOTAL_USD) == HONEST_PROBE_BUDGET_USD
    assert honest_run_budget(33) == 7.0
    assert honest_run_budget(9.645) is None
    assert honest_run_budget(46) is None
    assert LAST_RECORDED_TOTAL_USD + HONEST_PROBE_BUDGET_USD < PROJECT_BUDGET_USD
    assert LAST_RECORDED_TOTAL_USD + HONEST_PROBE_BUDGET_USD < LIFETIME_CAP_USD


def test_dry_run_prints_the_plan_and_does_not_measure(monkeypatch, capsys, isolated_spend_ledger):
    def explode(*_args, **_kwargs):
        raise AssertionError("dry run must not execute")

    monkeypatch.setattr("bench.probe.execute_probe", explode)
    _set_total(isolated_spend_ledger, LAST_RECORDED_TOTAL_USD)
    before = isolated_spend_ledger.read_bytes()
    assert main(["--honest", "--arms", "nope", "--split", "held-out"]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert isolated_spend_ledger.read_bytes() == before
    assert printed["execute"] is False
    assert printed["network"] == "refused"
    assert printed["measurements"] is None
    assert printed["execute_allowed"] is True
    assert printed["execute_refused"] is None
    assert printed["outer_model"] == "claude-sonnet-5-5"
    assert printed["arms"] == list(HONEST_ARMS)
    assert printed["warm_replay"] is True
    assert printed["warm_arms"] == ["script_first"]
    assert printed["tasks"] == list(HONEST_TASK_IDS)
    assert printed["dev_tasks"] == list(DEV_TASK_IDS)
    assert printed["tuned_tasks"] == list(TUNED_PROBE_TASK_IDS)
    assert printed["held_out_tasks"] == list(HELD_OUT_TASK_IDS)
    assert set(printed["tasks"]).isdisjoint(DEV_TASK_IDS)
    assert printed["tasks"] == list(HELD_OUT_TASK_IDS)
    assert printed["claude_budget_usd"] == 8.0
    assert printed["project_budget_usd"] == 40.0
    assert printed["lifetime_cap_usd"] == 50.0
    assert printed["project_spent_usd"] == LAST_RECORDED_TOTAL_USD
    assert printed["last_recorded_total_usd"] == LAST_RECORDED_TOTAL_USD
    blob = json.dumps(printed)
    assert "opus" not in blob.lower()
    assert "claude-sonnet-4-6" not in blob
    assert "selector_text" not in blob
    assert "Ada_Lovelace" not in blob
    assert ".titleline" not in blob
    assert LIVE_COMMAND in printed["box_commands"]
    assert set(printed["report_fields"]) == {
        "success_count",
        "mean_wall_ms_per_success",
        "median_wall_ms_per_success",
        "p90_wall_ms_per_success",
        "mean_wall_ms_ci95",
        "steps_one_shot",
        "steps_repair",
        "warm_replay_wall_ms",
    }
    assert printed["repeats"] == 1


def test_a_lower_ledger_is_refused_and_not_rewritten(capsys, isolated_spend_ledger):
    before = isolated_spend_ledger.read_bytes()
    assert main(["--honest"]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["execute_allowed"] is False
    assert printed["measurements"] is None
    assert printed["per_run_budget_usd"] is None
    assert "below the last recorded" in printed["execute_refused"]
    assert main(["--execute", "--honest"]) == 2
    assert "will not write" in capsys.readouterr().err
    assert isolated_spend_ledger.read_bytes() == before


def test_no_room_under_the_caps_refuses_before_a_task(tmp_path, monkeypatch):
    path = tmp_path / "ledger.json"
    SpendLedger.seed(path).save()
    _set_total(path, 38.5)
    before = path.read_bytes()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "local-test-not-sent")
    monkeypatch.setenv("CU_SPEND_LEDGER", str(path))

    async def explode(*_args, **_kwargs):
        raise AssertionError("a task started")

    monkeypatch.setattr("bench.probe.run_claude_arm", explode)
    monkeypatch.setattr("bench.browser_use_arm.run_browser_use_task", explode)
    try:
        asyncio.run(
            execute_probe(spend_path=path, runs_dir=tmp_path / "runs", honest=True)
        )
    except ProbeRefused as exc:
        assert "reserve" in str(exc)
    else:
        raise AssertionError("the run should refuse before a task")
    assert path.read_bytes() == before
    assert not (tmp_path / "runs").exists()


def test_execute_stops_before_another_task_can_cross_the_run_ceiling(tmp_path, monkeypatch):
    path = tmp_path / "ledger.json"
    SpendLedger.seed(path).save()
    _set_total(path, LAST_RECORDED_TOTAL_USD)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "local-test-not-sent")
    seen: list[str] = []
    reserve = honest_task_reserve_usd()

    async def fake(arm, task, **kwargs):
        del kwargs
        seen.append(arm)
        return {
            "arm": arm,
            "task_id": task["id"],
            "success": True,
            "skipped": False,
            "wall_ms": 10.0,
            "steps": 1,
            "usd": 3.0,
            "input_tokens": 1_000_000,
            "output_tokens": 0,
            "claude": True,
            "model_calls": 1,
        }

    monkeypatch.setattr("bench.probe.run_claude_arm", fake)
    monkeypatch.setattr("bench.browser_use_arm.run_browser_use_task", fake)
    rows = asyncio.run(
        execute_probe(spend_path=path, runs_dir=tmp_path / "runs", honest=True)
    )
    spent = 0.0
    started = 0
    for row in rows:
        if row.get("skipped"):
            assert spent + reserve >= HONEST_PROBE_BUDGET_USD
            assert "reserve" in row["success_reason"]
            continue
        assert spent + reserve < HONEST_PROBE_BUDGET_USD
        spent += float(row["usd"])
        started += 1
    assert started == 2
    assert seen == ["playwright_mcp", "script_first"]
    assert spent + reserve >= HONEST_PROBE_BUDGET_USD
    recorded = SpendLedger.load(path)
    assert recorded.running_total_usd == round(LAST_RECORDED_TOTAL_USD + spent, 6)
    assert recorded.running_total_usd < PROJECT_BUDGET_USD
    assert recorded.running_total_usd < LIFETIME_CAP_USD
    report = arm_report(rows, HONEST_ARMS)
    assert report["playwright_mcp"]["success_count"] == 1
    assert report["script_first"]["success_count"] == 1
    assert report["stagehand"]["success_count"] is None
    assert report["browser_use"]["success_count"] is None
    assert report["stagehand"]["mean_wall_ms_per_success"] is None
    assert report["script_first"]["warm_replay"]["success_count"] is None


def test_report_uses_only_recorded_rows():
    rows = [
        {
            "arm": "playwright_mcp",
            "pass": "cold",
            "success": True,
            "skipped": False,
            "wall_ms": 10.0,
            "steps": 1,
            "model_calls": 1,
        },
        {
            "arm": "playwright_mcp",
            "pass": "cold",
            "success": True,
            "skipped": False,
            "wall_ms": 30.0,
            "steps": 2,
            "model_calls": 2,
        },
        {
            "arm": "playwright_mcp",
            "pass": "cold",
            "success": True,
            "skipped": False,
            "steps": 1,
        },
        {
            "arm": "script_first",
            "pass": "warm",
            "success": True,
            "skipped": False,
            "wall_ms": 4.0,
            "steps": 1,
            "model_calls": 0,
            "tier": "cache_hit",
        },
        {
            "arm": "script_first",
            "pass": "cold",
            "success": True,
            "skipped": False,
            "wall_ms": 8.0,
            "steps": 1,
            "model_calls": 1,
            "tier": "patched",
        },
    ]
    assert row_took_repair(rows[0]) is False
    assert row_took_repair(rows[1]) is True
    assert row_took_repair(rows[4]) is True
    report = arm_report(rows, HONEST_ARMS)
    playwright = report["playwright_mcp"]
    assert playwright["success_count"] == 3
    assert playwright["mean_wall_ms_per_success"] == 20.0
    assert playwright["median_wall_ms_per_success"] == 20.0
    assert playwright["steps"]["one_shot"] == [1, 1]
    assert playwright["steps"]["repair"] == [2]
    assert playwright["warm_replay"]["ran"] is False
    assert playwright["warm_replay"]["wall_ms"] is None
    script = report["script_first"]
    assert script["success_count"] == 1
    assert script["steps"]["repair"] == [1]
    assert script["steps"]["one_shot"] == []
    assert script["warm_replay"]["ran"] is True
    assert script["warm_replay"]["wall_ms"] == [4.0]
    assert script["warm_replay"]["success_count"] == 1
    assert script["warm_replay"]["mean_wall_ms_per_success"] == 4.0
    assert script["warm_replay"]["median_wall_ms_per_success"] == 4.0
    assert report["stagehand"]["success_count"] is None
    assert report["browser_use"]["mean_wall_ms_per_success"] is None


def test_printed_report_comes_from_the_rows(monkeypatch, capsys, isolated_spend_ledger):
    del isolated_spend_ledger

    async def fake(**_kwargs):
        return [
            {
                "arm": "stagehand",
                "pass": "cold",
                "success": False,
                "skipped": False,
                "wall_ms": 12.0,
                "steps": 4,
                "usd": 0.0,
                "model_calls": 4,
            }
        ]

    monkeypatch.setattr("bench.probe.execute_probe", fake)
    assert main(["--execute", "--honest"]) == 0
    out = capsys.readouterr().out
    report = json.loads(out[out.index('{\n  "report"') :])["report"]
    assert report["stagehand"]["success_count"] == 0
    assert report["stagehand"]["mean_wall_ms_per_success"] is None
    assert report["stagehand"]["steps"]["repair"] == [4]
    assert report["playwright_mcp"]["success_count"] is None
    assert report["script_first"]["warm_replay"]["wall_ms"] is None


def test_execute_below_the_recorded_total_raises_without_saving(tmp_path):
    path = tmp_path / "ledger.json"
    SpendLedger.seed(path).save()
    before = path.read_bytes()
    try:
        asyncio.run(execute_probe(spend_path=path, runs_dir=tmp_path / "runs", honest=True))
    except LedgerBelowRecorded as exc:
        assert exc.found < LAST_RECORDED_TOTAL_USD
    else:
        raise AssertionError("a lower total must not run")
    assert path.read_bytes() == before
