"""Bench command.

    python -m bench list
    python -m bench run
    python -m bench run --quick
    python -m bench baseline
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from bench.catalog import format_agent_list
from bench.runner import RunSpec, baseline_spec, candidate_spec
from loop.actions import ActionError, PlannerError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bench", description="Repeatable local browser bench.")
    sub = parser.add_subparsers(dest="command", required=True)

    listed = sub.add_parser("list", help="Print the agent-facing task list.")
    listed.set_defaults(func=cmd_list)

    run = sub.add_parser("run", help="Run the counted bench with the model planner.")
    run.add_argument("--planner", choices=("fake", "model"), default="model")
    run.add_argument("--out", default=None, help="Directory for the per-task log.")
    run.add_argument("--quick", action="store_true", help="First 10 public tasks. Does not load the holdout.")
    run.add_argument(
        "--mode",
        choices=("candidate", "one-action", "cold", "replay", "handoff"),
        default="candidate",
    )
    run.add_argument("--replay-from", default=None, help="Directory of named-step traces.")
    run.set_defaults(func=cmd_run)

    base = sub.add_parser("baseline", help="Pin the one-action model baseline.")
    base.add_argument("--out", default=None)
    base.set_defaults(func=cmd_baseline)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (ActionError, PlannerError) as exc:
        print(exc, file=sys.stderr)
        return 1


def cmd_list(args) -> int:
    del args
    print(format_agent_list())
    return 0


def cmd_run(args) -> int:
    from bench.scoring import score

    spec = _spec(args)
    out = Path(args.out) if args.out else None
    summary = score(planner_name=args.planner, out_dir=out, quick=bool(args.quick), spec=spec)
    print(json.dumps(summary, indent=2))
    if args.planner == "model" and summary.get("llm_calls", 0) <= 0:
        print("Counted run made 0 model calls. The keys did not reach the planner.", file=sys.stderr)
        return 1
    return 0 if summary["failed"] == 0 else 1


def cmd_baseline(args) -> int:
    from bench.scoring import run_baseline

    out = Path(args.out) if args.out else None
    summary, pin = run_baseline(out)
    print(json.dumps({"pin": _pin_public(pin), "passed": summary["passed"], "failed": summary["failed"]}, indent=2))
    if summary.get("llm_calls", 0) <= 0:
        print("Baseline made 0 model calls. The keys did not reach the planner.", file=sys.stderr)
        return 1
    return 0 if summary["failed"] == 0 else 1


def _spec(args) -> RunSpec | None:
    if args.planner != "model":
        return RunSpec(name="fake")
    if args.mode == "candidate":
        spec = candidate_spec()
    elif args.mode == "one-action":
        spec = candidate_spec()
        spec.name = "one-action"
        spec.max_actions = 1
    elif args.mode == "cold":
        spec = candidate_spec()
        spec.name = "cold"
        spec.warm_browser = False
    elif args.mode == "handoff":
        spec = candidate_spec()
        spec.name = "handoff"
        spec.handoff = True
    else:
        spec = candidate_spec()
        spec.name = "replay"
    if args.replay_from:
        spec.replay_from = Path(args.replay_from)
        spec.name = "replay"
    if args.mode == "candidate" and args.replay_from:
        spec.save_traces = False
    return spec


def _pin_public(pin: dict) -> dict:
    shown = dict(pin)
    shown["tasks"] = [
        {key: value for key, value in task.items() if key != "check_detail"}
        for task in pin.get("tasks", [])
    ]
    return shown
