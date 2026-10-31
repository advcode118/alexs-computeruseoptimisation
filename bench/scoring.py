"""Score the bench. Hidden tasks are loaded only from score()."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from bench.catalog import Task, _load_directory, agent_tasks
from bench.runner import run_tasks


def load_holdout() -> list[Task]:
    directory = Path(__file__).resolve().parent / "holdout"
    return _load_directory(directory, holdout=True)


def score(planner_name: str = "fake", out_dir: Path | None = None) -> dict:
    if planner_name == "model":
        from loop.planner import ModelPlanner

        ModelPlanner.from_env()
    if out_dir is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out_dir = Path(__file__).resolve().parent / "runs" / stamp
    tasks = list(agent_tasks()) + list(load_holdout())
    return run_tasks(tasks, planner_name=planner_name, out_dir=out_dir)
