"""Offline spend/destination guards: no API calls or browser setup."""

import importlib.util
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

spec = importlib.util.spec_from_file_location(
    "sol_subset_run", Path(__file__).parents[1] / "extdev_gpt62_20261117" / "run.py"
)
run = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run)


@pytest.fixture
def setup_run(monkeypatch, tmp_path):
    ledger = SimpleNamespace(created=True, aborted=False, running_total_usd=9.418014)
    calls = []

    async def execute(**kwargs):
        calls.append((kwargs, run.openai_run._tasks()))
        return []

    monkeypatch.setattr(run.OpenAISpendLedger, "read", lambda: ledger)
    monkeypatch.setattr(run.openai_run, "execute_openai_probe", execute)
    monkeypatch.setattr(run.openai_run, "_tasks", None)
    monkeypatch.setenv("CU_OPENAI_RUN_BUDGET_USD", "99")
    argv = ["run.py", "gpt-6.2-sol", "--effort", "low", "--output-root", str(tmp_path),
            "--spend-baseline", "8.583958", "--spend-limit", "3", "--run-cap", "1.25",
            "--headroom", "0.5"]
    monkeypatch.setattr(sys, "argv", argv)
    return ledger, calls, argv, tmp_path


def test_forwards_fixed_subset_and_approved_shape(setup_run):
    ledger, calls, argv, root = setup_run
    run.main()
    assert len(calls) == 1
    kwargs, tasks = calls[0]
    assert [t["id"] for t in tasks] == [t["id"] for t in run.probe_tasks("extdev")[::3][:12]]
    assert kwargs == dict(arms=("browser_use",), split="extdev", sweep=False,
                         model="gpt-6.2-sol", effort="low", one_task=False,
                         headless=True, spend_path=None,
                         runs_dir=root / "gpt-6.2-sol-low-browser_use",
                         warm_replay=False, honest=False)
    assert float(os.environ["CU_OPENAI_RUN_BUDGET_USD"]) == 1.25


def test_remaining_allowance_reduces_run_cap(setup_run):
    ledger, calls, argv, root = setup_run
    ledger.running_total_usd = 10.5
    run.main()
    assert len(calls) == 1
    assert float(os.environ["CU_OPENAI_RUN_BUDGET_USD"]) == pytest.approx(.583958)


@pytest.mark.parametrize("change", ["missing", "stale", "aborted", "headroom", "existing"])
def test_refuses_unsafe_or_repeat_run_before_execution(setup_run, change):
    ledger, calls, argv, root = setup_run
    if change == "missing":
        ledger.created = False
    elif change == "stale":
        ledger.running_total_usd = 8
    elif change == "aborted":
        ledger.aborted = True
    elif change == "headroom":
        ledger.running_total_usd = 11.1
    else:
        (root / "gpt-6.2-sol-low-browser_use").mkdir()
    with pytest.raises(RuntimeError):
        run.main()
    assert not calls


@pytest.mark.parametrize("flag,value", [("--spend-limit", "nan"), ("--run-cap", "-1"),
                                        ("--headroom", "inf"), ("--spend-baseline", "0")])
def test_invalid_budget_never_executes(setup_run, flag, value):
    ledger, calls, argv, root = setup_run
    argv[argv.index(flag) + 1] = value
    with pytest.raises(SystemExit):
        run.main()
    assert not calls
