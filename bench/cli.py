"""Bench command.

    python -m bench list
    python -m bench run --planner fake
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from bench.catalog import format_agent_list
from loop.actions import ActionError, PlannerError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bench", description="Repeatable local browser bench.")
    sub = parser.add_subparsers(dest="command", required=True)

    listed = sub.add_parser("list", help="Print the agent-facing task list.")
    listed.set_defaults(func=cmd_list)

    run = sub.add_parser("run", help="Run the tasks through the loop and write a log.")
    run.add_argument("--planner", choices=("fake", "model"), default="fake")
    run.add_argument("--out", default=None, help="Directory for the per-task log.")
    run.set_defaults(func=cmd_run)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (ActionError, PlannerError) as exc:
        print(exc)
        return 1


def cmd_list(args) -> int:
    del args
    print(format_agent_list())
    return 0


def cmd_run(args) -> int:
    from bench.scoring import score

    out = Path(args.out) if args.out else None
    summary = score(planner_name=args.planner, out_dir=out)
    print(json.dumps(summary, indent=2))
    return 0
