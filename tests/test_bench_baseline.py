"""Baseline policy, key gate, and the quick split. No live model call."""

import hashlib
import json
from pathlib import Path

import pytest

from bench.baseline_agent import OneActionPlanner, make_baseline_planner
from bench.keys import load_live_keys
from bench.rates import estimate_dollars
from bench.scoring import baseline_code_sha256, select_tasks
from loop.actions import ActionBatch, FillNamed, Observation, PlannerError
from loop.planner import ModelPlanner

ROOT = Path(__file__).resolve().parents[1]


def test_one_action_planner_keeps_a_single_step():
    class Inner:
        calls = 0
        input_tokens = 0
        output_tokens = 0
        cached_input_tokens = 0
        model = "gpt-4o-mini"

        def plan(self, task, observation, history):
            del task, observation, history
            self.calls += 1
            self.input_tokens += 3
            self.output_tokens += 1
            return ActionBatch(
                "both",
                [FillNamed("textbox", "City", "London"), FillNamed("textbox", "Name", "Ada")],
                None,
                True,
            )

    planner = OneActionPlanner(Inner())
    batch = planner.plan("Fill the form.", Observation("file:///local", "Form", []), [])
    assert planner.calls == 1
    assert len(batch.actions) == 1
    assert batch.done is False
    assert batch.actions[0].name == "City"


def test_quick_selection_does_not_load_holdout(monkeypatch):
    import bench.scoring as scoring

    def boom():
        raise AssertionError("holdout loaded")

    monkeypatch.setattr(scoring, "load_holdout", boom)
    tasks = select_tasks(quick=True)
    assert len(tasks) == 10
    assert all(not task.holdout for task in tasks)


def test_missing_provider_keys_fail(monkeypatch):
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr("bench.keys.live_env_path", lambda: None)
    with pytest.raises(PlannerError):
        load_live_keys()


def test_from_env_prefers_nebius(monkeypatch):
    monkeypatch.setenv("NEBIUS_API_KEY", "test-nebius-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
    monkeypatch.setenv("RUN_MODEL", "deepseek-ai/DeepSeek-V4-Pro-0813")
    monkeypatch.delenv("LOOP_MODEL", raising=False)
    planner = ModelPlanner.from_env()
    assert planner.model == "deepseek-ai/DeepSeek-V4-Pro-0813"
    assert planner.api_style == "openai"
    assert "tokenfactory.nebius.com" in planner.base_url
    assert "test-nebius-key" not in planner.base_url


def test_baseline_factory_uses_the_one_action_prompt(monkeypatch):
    monkeypatch.setenv("NEBIUS_API_KEY", "test-nebius-key")
    monkeypatch.setenv("RUN_MODEL", "deepseek-ai/DeepSeek-V4-Pro-0813")
    monkeypatch.delenv("LOOP_MODEL", raising=False)
    planner = make_baseline_planner()
    assert isinstance(planner, OneActionPlanner)
    assert "exactly one action" in planner.inner.system


def test_dated_nebius_model_has_an_estimate():
    priced = estimate_dollars(
        "deepseek-ai/DeepSeek-V4-Pro-0813",
        1_000_000,
        0,
        llm_calls=1,
        cached_input_tokens=1_000_000,
    )
    assert priced["dollars_are"] == "estimate"
    assert priced["estimated_dollars"] == 1.36


def test_pin_hash_matches_the_baseline_file():
    digest = hashlib.sha256((ROOT / "bench" / "baseline_agent.py").read_bytes()).hexdigest()
    assert baseline_code_sha256() == digest
    pin = json.loads((ROOT / "bench" / "baseline.json").read_text(encoding="utf-8"))
    assert pin["frozen"] is True
    assert pin["code_sha256"] == digest
    assert pin["planner"] == "model"
    assert pin["task_count"] == 30
    assert pin["holdout_count"] == 6
    assert pin["llm_calls"] > 0
    text = (ROOT / "bench" / "baseline.json").read_text(encoding="utf-8")
    from bench.scoring import load_holdout

    for task in load_holdout():
        assert task.instruction not in text
