"""Repeat statistics. Fixture rows only. No network and no model call."""

from __future__ import annotations

import asyncio
import json

from bench.probe import (
    DEFAULT_REPEATS,
    HONEST_ARMS,
    arm_report,
    execute_probe,
    expected_honest_usd,
    main,
    published_arm_usd,
)
from bench.tasks import HELD_OUT_TASK_IDS

# The honest command stays this shape. claude-sonnet-5-5 is the outer model.
HONEST_COMMAND = (
    'CU_SPEND_LEDGER="$CU_SPEND_LEDGER" '
    'ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" '
    "python -m bench.probe --execute --honest"
)


def test_fixture_rows_report_mean_median_p90_and_interval():
    rows = [
        {"arm": "script_first", "pass": "cold", "success": True, "skipped": False, "wall_ms": 10.0, "repeat": 0},
        {"arm": "script_first", "pass": "cold", "success": True, "skipped": False, "wall_ms": 20.0, "repeat": 1},
        {"arm": "script_first", "pass": "cold", "success": True, "skipped": False, "wall_ms": 30.0, "repeat": 2},
        {"arm": "script_first", "pass": "cold", "success": False, "skipped": False, "wall_ms": 999.0, "repeat": 3},
        {"arm": "script_first", "pass": "cold", "success": True, "skipped": True, "wall_ms": 1.0, "repeat": 4},
        {"arm": "playwright_mcp", "pass": "cold", "success": True, "skipped": False, "wall_ms": 5.0, "repeat": 0},
    ]
    report = arm_report(rows, ("script_first", "playwright_mcp", "stagehand"))
    script = report["script_first"]
    assert script["mean_wall_ms_per_success"] == 20.0
    assert script["median_wall_ms_per_success"] == 20.0
    assert script["p90_wall_ms_per_success"] == 28.0
    margin = 4.303 * (100 ** 0.5) / (3 ** 0.5)
    assert script["mean_wall_ms_ci95"] == [round(20 - margin, 6), round(20 + margin, 6)]
    assert report["playwright_mcp"]["mean_wall_ms_ci95"] is None
    assert report["playwright_mcp"]["p90_wall_ms_per_success"] == 5.0
    assert report["stagehand"]["p90_wall_ms_per_success"] is None
    assert report["stagehand"]["mean_wall_ms_ci95"] is None


def test_default_repeat_does_not_multiply_the_scored_set(capsys):
    scored = len(HELD_OUT_TASK_IDS)
    assert scored >= 50
    assert DEFAULT_REPEATS == 1
    one = expected_honest_usd(scored, 1)
    assert expected_honest_usd(scored, DEFAULT_REPEATS) == one
    assert one < expected_honest_usd(scored, 2)
    per_arm = sum(published_arm_usd(arm) for arm in HONEST_ARMS)
    assert one == round(per_arm * scored, 6)
    assert main(["--honest"]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["execute"] is False
    assert printed["network"] == "refused"
    assert printed["measurements"] is None
    assert printed["repeats"] == 1
    assert printed["outer_model"] == "claude-sonnet-5-5"
    assert printed["expected_usd"] == one
    assert printed["expected_within_3_to_5"] is (3.0 <= one <= 5.0)
    assert HONEST_COMMAND in printed["box_commands"]
    blob = json.dumps(printed)
    assert "claude-sonnet-4-6" not in blob
    assert "opus" not in blob.lower()
    assert main(["--repeats", "0"]) == 2
    assert "repeats" in capsys.readouterr().err


def test_later_cold_repeats_do_not_read_the_script_cache(monkeypatch, tmp_path):
    seen: list[tuple[str, bool]] = []

    async def fake(arm, task, **kwargs):
        del task
        seen.append((arm, "script_cache" in kwargs))
        return {
            "arm": arm,
            "task_id": "unused",
            "success": True,
            "skipped": False,
            "wall_ms": 10.0,
            "steps": 1,
            "usd": 0.0,
            "input_tokens": 0,
            "output_tokens": 0,
            "claude": False,
            "model_calls": 1,
        }

    monkeypatch.setenv("ANTHROPIC_API_KEY", "local-test-not-sent")
    monkeypatch.setattr("bench.probe.run_claude_arm", fake)
    rows = asyncio.run(
        execute_probe(
            arms=("script_first",),
            warm_replay=True,
            split="probe",
            repeats=2,
            runs_dir=tmp_path / "runs",
        )
    )
    cold = [flag for _arm, flag in seen[:6]]
    warm = [flag for _arm, flag in seen[6:]]
    assert cold == [True, True, True, False, False, False]
    assert warm == [True, True, True]
    assert [row["repeat"] for row in rows if row["pass"] == "cold"] == [0, 0, 0, 1, 1, 1]
    assert all(row["pass"] == "warm" and row["repeat"] == 0 for row in rows[6:])
    assert json.dumps(rows).find("local-test-not-sent") == -1
