"""Replay script_first's runtime self-check offline on saved probe rows.

Each probe row from script_first carries `self_checks`: for every script the
run executed, the payload the self-check read, the live URL, the start URL and
the verdict it gave. This tool re-runs the current self-check on those inputs
and grades each script's end state with the shared grader, so a change to the
self-check can be scored for precision and recall without a live run.

    python -m bench.selfcheck_replay --split dev3 bench/runs/probe_*.jsonl

The unit is one script: self PASS/not-PASS against graded pass/fail of that
script's end state. The self-check never sees the grade.
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
from collections import Counter


def load_rows(paths: list[str]) -> list[dict]:
    rows = []
    for pattern in paths:
        for path in sorted(glob.glob(pattern)) or [pattern]:
            with open(path, encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line.startswith("{"):
                        continue
                    row = json.loads(line)
                    if row.get("arm") == "script_first" and row.get("self_checks"):
                        row["_file"] = path
                        rows.append(row)
    return rows


def grade_check(task: dict, check: dict) -> bool:
    """Would the shared grader pass this script's end state if the run stopped there."""
    from bench.probe import grade_observation
    from bench.script_first import claimed_from_payload

    payload = check.get("payload") or {}
    claim = claimed_from_payload(payload)
    ok, _reason, _sub, _subr = grade_observation(
        task,
        check.get("page_url") or "",
        payload.get("text") or "",
        selector_text=payload.get("selector_text") or "",
        answer=claim.answer,
        run_verdict="PASS",
        claimed=claim,
    )
    return bool(ok)


def replay_check(description: str, check: dict, earlier: list | None = None):
    """The current self-check on the saved inputs. The grade fields are dropped first."""
    from bench.script_first import script_runtime_verdict, task_asks_value

    payload = dict(check.get("payload") or {})
    payload.pop("selector_text", None)
    verdict, _ = script_runtime_verdict(
        json.dumps(payload),
        check.get("page_url") or "",
        check.get("start_url") or "",
        asks_value=task_asks_value(description),
        task=description,
        earlier=[dict(item.get("payload") or {}) for item in earlier or []],
    )
    return verdict


def confusion(units: list[dict], key: str) -> dict:
    counts = Counter()
    for unit in units:
        counts[(unit[key] == "PASS", unit["graded"])] += 1
    tp, fp = counts[(True, True)], counts[(True, False)]
    fn, tn = counts[(False, True)], counts[(False, False)]
    return {
        "self_pass_graded_pass": tp,
        "self_pass_graded_fail": fp,
        "self_fail_graded_pass": fn,
        "self_fail_graded_fail": tn,
        "precision": tp / (tp + fp) if tp + fp else None,
        "recall": tp / (tp + fn) if tp + fn else None,
    }


def check_name(reason: str) -> str:
    """A reason without its page-specific detail: the text before the first '(' or ';'."""
    head = reason.split(";")[0].split("(")[0]
    words = [word for word in head.split() if not any(ch.isdigit() for ch in word)]
    return " ".join(words[:8])


def by_check(units: list[dict]) -> dict:
    """For scripts the old check passed and the new one does not: caught false accepts and rejected true passes."""
    table: dict[str, dict[str, int]] = {}
    for unit in units:
        if unit["before"] != "PASS" or unit["after"] == "PASS":
            continue
        row = table.setdefault(check_name(unit["after_reason"]), {"caught_false_accept": 0, "rejected_true_pass": 0})
        row["rejected_true_pass" if unit["graded"] else "caught_false_accept"] += 1
    return table


def build_units(rows: list[dict], tasks: dict[str, dict]) -> list[dict]:
    units = []
    for row in rows:
        task = tasks.get(row.get("task_id"))
        if task is None:
            continue
        description = row.get("task_description") or task.get("description") or ""
        for index, check in enumerate(row["self_checks"]):
            new = replay_check(description, check, row["self_checks"][:index])
            units.append(
                {
                    "file": row["_file"],
                    "task_id": row["task_id"],
                    "index": index,
                    "description": description,
                    "check": check,
                    "before": check.get("verdict") or "",
                    "before_reason": check.get("reason") or "",
                    "after": new.verdict,
                    "after_reason": new.reason,
                    "graded": grade_check(task, check),
                }
            )
    return units


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", required=True, choices=("dev3", "heldout2", "held-out", "dev"))
    parser.add_argument("--show", choices=("fp", "fn", "changed", "none"), default="none")
    parser.add_argument("rows", nargs="+")
    args = parser.parse_args(argv)
    from bench.tasks import tasks_for_split

    tasks = {task["id"]: task for task in tasks_for_split(args.split)}
    units = build_units(load_rows(args.rows), tasks)
    out = {
        "scripts": len(units),
        "before": confusion(units, "before"),
        "after": confusion(units, "after"),
        "new_fails_by_check": by_check(units),
    }
    print(json.dumps(out, indent=2))
    for unit in units:
        show = (
            (args.show == "fp" and unit["after"] == "PASS" and not unit["graded"])
            or (args.show == "fn" and unit["after"] != "PASS" and unit["graded"])
            or (args.show == "changed" and (unit["after"] == "PASS") != (unit["before"] == "PASS"))
        )
        if show:
            payload = unit["check"].get("payload") or {}
            print(
                f"--- {unit['task_id']} #{unit['index']} graded={unit['graded']} "
                f"before={unit['before']} after={unit['after']} ({unit['after_reason']})"
            )
            print(f"  task: {unit['description'][:200]}")
            print(f"  url: {unit['check'].get('page_url')}  start: {unit['check'].get('start_url')}")
            print(f"  title: {payload.get('title', '')[:120]!r}  h1: {payload.get('h1', '')[:120]!r}")
            print(f"  claimed: {json.dumps(payload.get('claimed') or {})[:300]}")
            print(f"  extracted: {json.dumps(payload.get('extracted') or [])[:300]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
