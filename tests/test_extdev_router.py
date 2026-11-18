"""Saved-row routing keeps labels and timings on the selected arm row."""

import csv
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

DIRECTORY = Path(__file__).resolve().parents[1] / "docs/results/extdev_router_20261117"


@pytest.fixture
def simulation():
    spec = importlib.util.spec_from_file_location("extdev_router", DIRECTORY / "simulate.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_router_reproduces_outputs(tmp_path):
    result = subprocess.run([sys.executable, str(DIRECTORY / "simulate.py"), "--output-dir", str(tmp_path)],
                            capture_output=True, text=True, check=True)
    assert "not human spot-checked; indicative only" in result.stdout
    for filename in ("tasks.csv", "results.json"):
        assert (tmp_path / filename).read_bytes() == (DIRECTORY / filename).read_bytes()
    report = json.loads((tmp_path / "results.json").read_text())
    assert report["model_calls"] == report["browser_runs"] == 0
    for policies in report["summaries"].values():
        for score in policies.values():
            assert score["tasks"] == score["correct"] + score["partial"] + score["wrong"] == 22
        cascade = policies["always_cascade"]
        assert (cascade["correct"], cascade["partial"], cascade["handoffs"]) == (20, 2, 20)
        assert cascade["script_s_on_handoff_total"] == pytest.approx(167.947526462)
        assert policies["always_browser_use"]["script_s_on_handoff_total"] == 0
        assert policies["always_browser_use"]["correct"] == 21
        assert policies["oracle_quality_then_time"]["correct"] == 22
    with (tmp_path / "tasks.csv").open() as handle:
        assert len(list(csv.DictReader(handle))) == 220


def test_pre_run_rules_need_only_task_category(simulation):
    for category in ("value", "nav", "filter", "spa", "search"):
        features = {"category": category}
        assert simulation.choose_pre_run("bypass_value", features) == ("browser_use" if category == "value" else "cascade")
        assert simulation.choose_pre_run("nav_only", features) == ("cascade" if category == "nav" else "browser_use")
    with pytest.raises(ValueError, match="not a pre-run policy"):
        simulation.choose_pre_run("oracle_quality_then_time", {})
    with pytest.raises(ValueError, match="expected extdev"):
        simulation.pre_run_features({"task_id": "invalid"})
    assert simulation.summarize([])["mean_s"] is None
    assert simulation.quantile([], .9) is None
    assert simulation.quantile([1, 2, 3], .9) == pytest.approx(2.8)


def test_selected_row_supplies_truth_time_cost_and_waste(simulation):
    pairs = simulation.load_inputs()
    records = simulation.simulate(pairs)
    indexed = {pair["task_id"]: pair for pair in pairs}
    for row in records:
        pair = indexed[row["task_id"]]
        selected = pair["arms"][row["selected_row"]]
        assert row["hand_label"] == pair["truth"][row["selected_row"]]
        assert row["wall_s"] == selected["wall_ms"] / 1000
        assert row["usd"] == selected["usd"]
        if row["selected_row"] != "cascade" or selected["answered_by"] == "script":
            assert row["script_s_on_handoff"] == 0
