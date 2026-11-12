"""Recompute site figures from the saved JSONL and check data/measured.json.

Latency populations are named on every aggregate:
- all: every non-skipped task row
- successes: rows with success true

Median is statistics.median of wall seconds. p90 is nearest-rank:
the value at index ceil(0.9 * n) - 1 of the sorted list.
"""

from __future__ import annotations

import ast
import hashlib
import json
import math
import statistics
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "measured.json"
TASKS = ROOT / "data" / "measured-tasks.json"

TIP = "94427222b9fb9ce7b1e04f5dd62336321a745e00"
DECISIONS = "6b59b525ea279041158b5fc2d320594cdb11261e"
REPO = "https://github.com/advcode118/alexs-computeruseoptimisation"

HELDOUT_FILES = {
    "gpt-6-luna": "docs/results/heldout_luna_medium_20261111.jsonl",
    "gpt-6.1-sol": "docs/results/heldout_sol_medium_20261111.jsonl",
}
RULE_FILES = [
    ("off", 1, "docs/results/rules_off_run1_luna_medium_20261111.jsonl"),
    ("off", 2, "docs/results/rules_off_run2_luna_medium_20261111.jsonl"),
    ("off", 3, "docs/results/rules_off_run3_luna_medium_20261111.jsonl"),
    ("on", 1, "docs/results/rules_on_run1_luna_medium_20261111.jsonl"),
    ("on", 2, "docs/results/rules_on_run2_luna_medium_20261111.jsonl"),
    ("on", 3, "docs/results/rules_on_run3_luna_medium_20261111.jsonl"),
]
ARMS = ["script_first", "playwright_mcp", "browser_use"]
TARGETED = {"answer_needed", "answer_needed_unknown", "answer_needed_returned"}


def git_show(rev: str, path: str) -> bytes:
    return subprocess.check_output(["git", "show", f"{rev}:{path}"])


def load_rows(rev: str, path: str) -> list[dict]:
    rows = []
    for line in git_show(rev, path).decode("utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if "arm" in row:
            rows.append(row)
    return rows


def r4(value: float) -> float:
    return round(value + 0.0, 4)


def r3(value: float) -> float:
    return round(value + 0.0, 3)


def r6(value: float) -> float:
    return round(value + 0.0, 6)


def nearest_rank(values: list[float], p: float) -> float:
    ordered = sorted(values)
    index = math.ceil(p * len(ordered)) - 1
    index = min(max(index, 0), len(ordered) - 1)
    return ordered[index]


def population(rows: list[dict]) -> dict:
    seconds = [row["wall_ms"] / 1000.0 for row in rows]
    return {
        "n": len(rows),
        "medianS": r4(statistics.median(seconds)),
        "meanS": r4(statistics.mean(seconds)),
        "p90S": r4(nearest_rank(seconds, 0.9)),
    }


def bucket(reason: str) -> str:
    if reason == "Model ended without completing task":
        return "Model ended without finishing"
    if reason == "returned evidence is not on the page":
        return "Returned evidence not on the page"
    if reason in (
        "answer does not satisfy the marker",
        "claimed URL does not match the live page",
        "answer is not in the page text",
        "returned value is not text",
        "the script returned no answer or key_text",
    ):
        return "Answer or claimed URL wrong"
    if reason == "empty answer":
        return "Empty answer"
    if reason.startswith("the script stopped"):
        return "Script error"
    if reason.startswith("URL ") or reason.startswith("URL is a search page") or reason == "the URL marker does not match the live page":
        return "Ended on the wrong page"
    if reason.startswith("Task failed:"):
        return "Run stopped with a task error"
    return "Other"


def arm_block(rows: list[dict]) -> dict:
    passed = [row for row in rows if row.get("success") is True]
    steps = [row["steps"] for row in rows if row.get("steps") is not None]
    calls = [row["model_calls"] for row in rows if row.get("model_calls") is not None]
    scripts = [row["script_steps"] for row in rows if row.get("script_steps") is not None]
    failures = [row for row in rows if row.get("success") is not True]
    counts = Counter(bucket(row.get("success_reason") or "") for row in failures)
    block = {
        "pass": len(passed),
        "of": len(rows),
        "usd": r6(sum(float(row.get("usd") or 0) for row in rows)),
        "all": population(rows),
        "successes": population(passed),
        "stepsMedian": r4(statistics.median(steps)) if steps else None,
        "stepsSum": sum(steps) if steps else None,
        "modelCallsMedian": r4(statistics.median(calls)) if calls else None,
        "modelCallsSum": sum(calls) if calls else None,
        "scriptStepsMedian": r4(statistics.median(scripts)) if scripts else None,
        "scriptStepsSum": sum(scripts) if scripts else None,
        "failureBuckets": [
            {"reason": reason, "n": counts[reason]}
            for reason in (
                "Model ended without finishing",
                "Ended on the wrong page",
                "Returned evidence not on the page",
                "Answer or claimed URL wrong",
                "Empty answer",
                "Script error",
                "Run stopped with a task error",
                "Other",
            )
            if counts[reason]
        ],
    }
    other = [row.get("success_reason") or "" for row in failures if bucket(row.get("success_reason") or "") == "Other"]
    if other:
        raise SystemExit(f"unbucketed failure: {other[:3]}")
    if sum(item["n"] for item in block["failureBuckets"]) != len(failures):
        raise SystemExit("failure buckets do not sum to the miss count")
    return block


def task_descriptions() -> dict[str, str]:
    text = git_show(TIP, "bench/tasks.py").decode("utf-8")
    tree = ast.parse(text)
    found: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        data: dict[str, str] = {}
        for key, value in zip(node.keys, node.values):
            if not isinstance(key, ast.Constant) or key.value not in ("id", "description"):
                continue
            if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
                continue
            data[key.value] = value.value
        task_id = data.get("id", "")
        if task_id.startswith("ho_") and "description" in data:
            found[task_id] = data["description"]
    return found


def cell(row: dict, arm: str) -> dict:
    item = {
        "pass": bool(row.get("success")),
        "wallS": r3(row["wall_ms"] / 1000.0),
        "steps": row.get("steps"),
        "modelCalls": row.get("model_calls"),
        "scriptSteps": row.get("script_steps") if arm == "script_first" else None,
    }
    return item


def build() -> dict:
    for path in HELDOUT_FILES.values():
        tip = hashlib.sha256(git_show(TIP, path)).hexdigest()
        decisions = hashlib.sha256(git_show(DECISIONS, path)).hexdigest()
        if tip != decisions:
            raise SystemExit(f"{path} differs between tip and decisions-second-opinion")

    descriptions = task_descriptions()
    held_out = []
    for model, path in HELDOUT_FILES.items():
        rows = load_rows(TIP, path)
        if any(row.get("skipped") for row in rows):
            raise SystemExit(f"skipped row in {path}")
        if any(row.get("pass") != "cold" for row in rows):
            raise SystemExit(f"non-cold row in {path}")
        if any(row.get("effort") != "medium" for row in rows):
            raise SystemExit(f"non-medium row in {path}")
        if {row.get("model") for row in rows} != {model}:
            raise SystemExit(f"unexpected model in {path}")
        by_arm: dict[str, list[dict]] = defaultdict(list)
        for row in rows:
            by_arm[row["arm"]].append(row)
        if set(by_arm) != set(ARMS):
            raise SystemExit(f"unexpected arms in {path}: {sorted(by_arm)}")
        order = [row["task_id"] for row in by_arm["script_first"]]
        if len(order) != 50 or len(set(order)) != 50:
            raise SystemExit(f"{path} script_first is not 50 unique tasks")
        tasks = []
        for task_id in order:
            arms = {}
            for arm in ARMS:
                match = [row for row in by_arm[arm] if row["task_id"] == task_id]
                if len(match) != 1:
                    raise SystemExit(f"{path} {arm} {task_id} count {len(match)}")
                arms[arm] = cell(match[0], arm)
            if task_id not in descriptions:
                raise SystemExit(f"no description for {task_id}")
            tasks.append({"id": task_id, "description": descriptions[task_id], "arms": arms})
        held_out.append(
            {
                "model": model,
                "file": path,
                "arms": {arm: arm_block(by_arm[arm]) for arm in ARMS},
                "tasks": tasks,
            }
        )

    rules = {"off": [], "on": []}
    on_rows: list[dict] = []
    rule_hits = Counter()
    for gate, run, path in RULE_FILES:
        rows = load_rows(DECISIONS, path)
        if len(rows) != 50 or any(row.get("arm") != "script_first" for row in rows):
            raise SystemExit(f"{path} is not 50 script_first rows")
        if any(row.get("decisions_check") != gate for row in rows):
            raise SystemExit(f"{path} decisions_check is not {gate}")
        if any(row.get("model") != "gpt-6-luna" or row.get("effort") != "medium" or row.get("pass") != "cold" for row in rows):
            raise SystemExit(f"{path} is not luna medium cold")
        rules[gate].append({"run": run, "file": path, **arm_block(rows)})
        if gate == "on":
            on_rows.extend(rows)
        for row in rows:
            reason = row.get("first_runtime_reason") or ""
            if reason in (
                "answer is the live page URL",
                "answer is in the page title or h1",
            ) or "live page URL" in reason or "title or h1" in reason or "title or main heading" in reason:
                rule_hits[reason] += 1
                if row.get("success") is not True:
                    raise SystemExit(f"rule pass failed the grade: {row['task_id']} {reason}")

    # Discover the exact rule phrases if the expected ones were not used.
    if not rule_hits:
        seen = Counter()
        for _gate, _run, path in RULE_FILES:
            for row in load_rows(DECISIONS, path):
                seen[row.get("first_runtime_reason") or ""] += 1
        interesting = {k: v for k, v in seen.items() if "url" in k.lower() or "title" in k.lower() or "h1" in k.lower() or "rule" in k.lower()}
        raise SystemExit(f"rule phrases not found. interesting reasons: {interesting}")

    overturns = [row for row in on_rows if row.get("decisions_overturned") is True]
    repairs = [row for row in on_rows if row.get("decisions_blocked") in TARGETED]
    call_rows = [row for row in on_rows if int(row.get("decisions_calls") or 0) > 0]
    single = [row for row in call_rows if int(row.get("decisions_calls") or 0) == 1]
    call_ms = [float(row["decisions_ms"]) for row in call_rows]
    single_ms = [float(row["decisions_ms"]) for row in single]

    off_passes = [item["pass"] for item in rules["off"]]
    on_passes = [item["pass"] for item in rules["on"]]
    blob = {
        "asOf": "11 November 2026",
        "populationNote": "Median is the statistical median. p90 is nearest-rank (index ceil(0.9*n)-1). 'all' is every task. 'successes' is graded passes only.",
        "sources": {
            "repo": REPO,
            "heldOutCommit": TIP,
            "decisionsCommit": DECISIONS,
            "heldOutCommitUrl": f"{REPO}/commit/{TIP}",
            "decisionsCommitUrl": f"{REPO}/commit/{DECISIONS}",
            "heldOutWriteUp": f"{REPO}/blob/{TIP}/docs/TEST_RESULTS.md",
            "decisionsWriteUp": f"{REPO}/blob/{DECISIONS}/docs/TEST_RESULTS.md",
        },
        "setup": {
            "tasks": 50,
            "effort": "medium",
            "provider": "openai",
            "cold": True,
            "arms": ARMS,
            "stagehand": "not in this run",
            "answerKeyInScriptFirstRuntime": False,
            "repeats": "one run per model and arm",
        },
        "heldOut": held_out,
        "rules": {
            "model": "gpt-6-luna",
            "arm": "script_first",
            "codeNote": "Plain runtime rules on a different code variant from the held-out baseline. These six runs are not a rerun of that baseline.",
            "off": rules["off"],
            "on": rules["on"],
            "offPasses": off_passes,
            "onPasses": on_passes,
            "offMean": r4(statistics.mean(off_passes)),
            "onMean": r4(statistics.mean(on_passes)),
            "offGraded": f"{sum(off_passes)}/150",
            "onGraded": f"{sum(on_passes)}/150",
            "ruleFirstPasses": dict(rule_hits),
            "ruleFirstGradedPass": sum(rule_hits.values()),
            "decisions": {
                "overturns": len(overturns),
                "overturnsGradedPass": sum(1 for row in overturns if row.get("success") is True),
                "precisionBar": 0.9,
                "targetedRepairs": len(repairs),
                "targetedRepairsPassed": sum(1 for row in repairs if row.get("success") is True),
                "calls": sum(int(row.get("decisions_calls") or 0) for row in on_rows),
                "errors": sum(int(row.get("decisions_errors") or 0) for row in on_rows),
                "tasksWithCalls": len(call_rows),
                "perTaskMsMedian": r3(statistics.median(call_ms)),
                "perTaskMsMax": r3(max(call_ms)),
                "singleCallTasks": len(single),
                "singleCallMsMedian": r3(statistics.median(single_ms)),
            },
        },
        "ledgers": {
            "openai": {
                "used": 3.2185,
                "cap": 20,
                "recordedIn": f"{REPO}/blob/{DECISIONS}/docs/TEST_RESULTS.md",
                "note": "Recorded after the six plain-rule runs in section 7d. Not re-read from the live ledger.",
            },
            "claude": {
                "used": 26.022488,
                "cap": 50,
                "abortAt": 40,
                "recordedIn": f"{REPO}/blob/{TIP}/docs/TEST_RESULTS.md",
                "note": "Recorded running_total_usd in the 11 Nov write-up. Not re-read from the live ledger. The OpenAI runs in that write-up did not change it.",
            },
        },
    }
    writeup = git_show(DECISIONS, "docs/TEST_RESULTS.md").decode("utf-8")
    if "$3.2185" not in writeup:
        raise SystemExit("section 7d no longer records $3.2185")
    tip_writeup = git_show(TIP, "docs/TEST_RESULTS.md").decode("utf-8")
    if "26.022488" not in tip_writeup:
        raise SystemExit("tip write-up no longer records 26.022488")
    decisions = blob["rules"]["decisions"]
    if decisions["overturns"] != 9 or decisions["overturnsGradedPass"] != 3:
        raise SystemExit(f"overturns {decisions['overturns']} passed {decisions['overturnsGradedPass']}")
    if decisions["targetedRepairs"] != 14 or decisions["targetedRepairsPassed"] != 1:
        raise SystemExit(f"repairs {decisions['targetedRepairs']} passed {decisions['targetedRepairsPassed']}")
    if decisions["calls"] != 149:
        raise SystemExit(f"calls {decisions['calls']}")
    if off_passes != [31, 36, 31] or on_passes != [29, 35, 37]:
        raise SystemExit(f"passes off {off_passes} on {on_passes}")
    if sum(rule_hits.values()) != 20:
        raise SystemExit(f"rule hits {dict(rule_hits)}")
    return blob


def split_blob(blob: dict) -> tuple[dict, list[dict]]:
    summary_runs = []
    task_runs = []
    for run in blob["heldOut"]:
        summary_runs.append({key: value for key, value in run.items() if key != "tasks"})
        task_runs.append({"model": run["model"], "tasks": run["tasks"]})
    summary = {**blob, "heldOut": summary_runs}
    return summary, task_runs


def main() -> None:
    summary, task_runs = split_blob(build())
    summary_text = json.dumps(summary, indent=2) + "\n"
    tasks_text = json.dumps(task_runs, indent=2) + "\n"
    if "--write" in sys.argv:
        OUT.write_text(summary_text, encoding="utf-8")
        TASKS.write_text(tasks_text, encoding="utf-8")
        print(f"wrote {OUT} and {TASKS}")
        return
    if OUT.read_text(encoding="utf-8") != summary_text or TASKS.read_text(encoding="utf-8") != tasks_text:
        raise SystemExit("measured JSON does not match the recomputed JSONL. Run: python scripts/check_measured.py --write")
    print("measured JSON matches the raw rows")


if __name__ == "__main__":
    main()
