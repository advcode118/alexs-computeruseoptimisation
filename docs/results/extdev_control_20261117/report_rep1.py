"""Reproduce the saved-data report and ledger reconciliation without model calls."""

import hashlib
import json
import random
import statistics
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from bench import grade
from bench.tasks import tasks_for_split

HERE = Path(__file__).resolve().parent
SEED = 20261117
BOOTSTRAPS = 50000


def load(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def attempted(path):
    return [r for r in load(path) if "task_id" in r and not r.get("skipped")]


def quantile(values, q):
    values = sorted(values)
    if not values:
        raise ValueError("Cannot calculate a quantile without observations")
    index = (len(values) - 1) * q
    left = int(index)
    right = min(left + 1, len(values) - 1)
    return values[left] + (values[right] - values[left]) * (index - left)


def interval(values):
    return [quantile(values, .025), quantile(values, .975)]


def cash(rows):
    return sum((Decimal(str(r["usd"])) for r in rows), Decimal(0))


def bootstrap(groups, tasks, best):
    if not groups or not all(groups.values()):
        raise ValueError("Bootstrap requires nonempty paired groups")
    ids = sorted(next(iter(groups.values())))
    assert all(sorted(rows) == ids for rows in groups.values())
    clusters = {}
    for task_id in ids:
        host = urlsplit(tasks[task_id]["start_url"]).hostname.removeprefix("www.")
        clusters.setdefault(host, []).append(task_id)
    sites = sorted(clusters)
    site_n = [len(clusters[site]) for site in sites]
    success = {name: [sum(rows[t]["success"] for t in clusters[s]) for s in sites]
               for name, rows in groups.items()}
    elapsed = {name: [sum(rows[t]["wall_ms"] for t in clusters[s]) for s in sites]
               for name, rows in groups.items()}
    draws = {name: [] for name in groups}
    differences = {name: [] for name in groups}
    wall_differences = {name: [] for name in groups}
    rng = random.Random(SEED)
    for _ in range(BOOTSTRAPS):
        sample = [rng.randrange(len(sites)) for _ in sites]
        denominator = sum(site_n[i] for i in sample)
        best_rate = sum(success[best][i] for i in sample) / denominator
        best_time = sum(elapsed[best][i] for i in sample) / denominator
        for name in groups:
            rate = sum(success[name][i] for i in sample) / denominator
            draws[name].append(rate)
            differences[name].append(rate - best_rate)
            wall_differences[name].append(sum(elapsed[name][i] for i in sample) / denominator - best_time)
    return {
        "clusters": {site: len(clusters[site]) for site in sites},
        "pass_rate_ci": {name: interval(v) for name, v in draws.items()},
        "difference_ci": {name: interval(v) for name, v in differences.items()},
        "wall_difference_ci": {name: interval(v) for name, v in wall_differences.items()},
    }


def metrics(rows):
    rows = list(rows)
    if not rows:
        raise ValueError("Metrics require at least one attempted row")
    return {"n": len(rows), "passes": sum(r["success"] for r in rows),
            "pass_rate": sum(r["success"] for r in rows) / len(rows),
            "median_wall_ms": statistics.median(r["wall_ms"] for r in rows),
            "mean_wall_ms": statistics.mean(r["wall_ms"] for r in rows),
            "p90_wall_ms": quantile([r["wall_ms"] for r in rows], .9),
            "mean_usd": float(cash(rows) / len(rows))}


def stage_one_replay(row, task):
    check = (row.get("self_checks") or [{}])[-1]
    payload = check.get("payload") or {}
    claim = payload.get("claimed") or {}
    fields = {key: claim.get(key, "") for key in ("url", "title", "h1", "answer", "key_text")}
    fields.update(values=tuple(claim.get("values") or ()), rejected=bool(claim.get("rejected")))
    verdict = grade.grade_observation(
        task, check.get("page_url", ""), payload.get("text", ""),
        claimed=grade.ClaimedEvidence(**fields), answer=fields["answer"],
    )
    return {"task_id": row["task_id"], "raw_self_check": check.get("verdict"),
            "precision_gate_accepted": row["answered_by"] == "script",
            "stage_one_frozen_replay_success": verdict[0], "stage_one_frozen_replay_reason": verdict[1],
            "final_cascade_success": row["success"]}


def ledger_summary():
    path = Path.home() / ".cu-optimisation/openai-spend-alex15.json"
    ledger = json.loads(path.read_text())
    invocations = [
        ("smoke", HERE / "smoke/probe_20261117_011924.jsonl"),
        ("default_rep1", HERE / "raw/probe_20261117_012232.jsonl"),
        ("ultrafast_rep1", HERE / "raw/probe_20261117_015118.jsonl"),
    ]
    cursor = 0
    running = Decimal(str(ledger["recorded_extra_usd"]))
    summary = []
    for name, source in invocations:
        rows = attempted(source)
        entries = ledger["tasks"][cursor:cursor + len(rows)]
        assert len(entries) == len(rows)
        for entry, row in zip(entries, rows):
            assert entry["task_id"] == f'{row["arm"]}:{row["task_id"]}:medium'
            for field in ("usd", "input_tokens", "output_tokens", "cached_tokens",
                          "cache_write_30m_tokens", "cache_write_12h_tokens"):
                assert entry[field] == row[field], (name, row["task_id"], field)
        usage = cash(entries)
        by_arm = {arm: float(cash([e for e in entries if e["task_id"].split(":")[0] == arm]))
                  for arm in sorted({r["arm"] for r in rows})}
        summary.append({"invocation": name, "raw_jsonl": str(source.relative_to(ROOT)),
                        "ledger_task_indices_0_based": [cursor, cursor + len(rows) - 1],
                        "charged_rows": len(entries), "usage_usd": float(usage),
                        "ledger_before_usd": float(running), "ledger_after_usd": float(running + usage),
                        "per_arm_usage_usd": by_arm})
        running += usage
        cursor += len(rows)
    assert cursor == len(ledger["tasks"]) == 131
    assert running == Decimal(str(ledger["running_total_usd"]))
    entries = ledger["tasks"]
    baseline = cash([e for e in entries if not e["task_id"].startswith("cascade:")])
    cascade = cash([e for e in entries if e["task_id"].startswith("cascade:")])
    assert baseline + cascade + Decimal(str(ledger["recorded_extra_usd"])) == running
    result = {
        "source": "~/.cu-optimisation/openai-spend-alex15.json",
        "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "running_total_usd": ledger["running_total_usd"], "project_cap_usd": ledger["project_budget_usd"],
        "remaining_project_budget_usd": float(Decimal(str(ledger["project_budget_usd"])) - running),
        "opening_allowance_usd": ledger["recorded_extra_usd"],
        "opening_allowance_allocation": "Separate/unallocated; not silently charged to either sub-budget",
        "recorded_model_usage_usd": float(cash(entries)),
        "aborted": ledger["aborted"], "invocations": summary,
        "sub_budgets": {
            "baselines_plus_script_first": {"usage_usd": float(baseline), "budget_usd": 5.0,
                                             "over_budget_usd": float(baseline - Decimal(5)),
                                             "arms": ["browser_use default", "browser_use ultrafast", "playwright_mcp", "script_first"]},
            "cascade": {"usage_usd": float(cascade), "includes_smoke_usd": summary[0]["usage_usd"],
                        "replicate_one_usd": summary[1]["per_arm_usage_usd"]["cascade"]},
        },
        "note": "Recorded estimates copied/reconciled from ledger, not repriced invoices. Existing between-task thresholds can overshoot. No paid calls or ledger changes during reporting.",
    }
    (HERE / "ledger_summary.json").write_text(json.dumps(result, indent=2) + "\n")
    table = "\n".join(f'| {r["invocation"]} | {r["charged_rows"]} | ${r["usage_usd"]:.6f} | ${r["ledger_after_usd"]:.6f} |'
                      for r in summary)
    (HERE / "ledger_summary.md").write_text(f'''# Ledger summary

Source: `~/.cu-optimisation/openai-spend-alex15.json`; 131 charged task records
reconciled in ledger order to the three saved JSONLs, including token counts and
USD. No secrets copied. No repricing or ledger modification.

| Invocation | Charged rows | Recorded usage | Running total after |
|---|---:|---:|---:|
{table}

The separate **$0.050000 opening allowance** precedes the smoke.
Model usage is **${float(cash(entries)):.6f}**; running total is
**${float(running):.6f} / $9.00**, leaving **${result["remaining_project_budget_usd"]:.6f}**.

- Baselines + script_first, including both BU modes and failed MCP attempts:
  **${float(baseline):.6f} / $5.00**, overshoot **${float(baseline - Decimal(5)):.6f}**.
- Cascade, including smoke: **${float(cascade):.6f}**
  (smoke $0.105299 + replicate 1 $1.112435).
- Opening allowance: **$0.050000**, kept separate from the arm sub-budgets.

The run caps check between tasks, allowing in-flight overshoot. Recorded costs
retain the aggregate-long-context accounting caveat in [ANALYSIS.md](ANALYSIS.md).
All paid runs remain stopped; unspent project balance is not authorization.
''')
    return result


def main():
    tasks = {t["id"]: t for t in tasks_for_split("extdev")}
    default = attempted(HERE / "raw/probe_20261117_012232.jsonl")
    ultra = attempted(HERE / "raw/probe_20261117_015118.jsonl")
    groups = {arm: {r["task_id"]: r for r in default if r["arm"] == arm}
              for arm in ("browser_use", "script_first", "cascade")}
    ids = set(groups["cascade"])
    groups["browser_use ultrafast"] = {r["task_id"]: r for r in ultra if r["task_id"] in ids}
    assert len(ids) == 22 and len(ultra) == 40
    assert all(set(rows) == ids for rows in groups.values())
    metrics_by_arm = {name: metrics(rows.values()) for name, rows in groups.items()}
    rank = lambda name: (-metrics_by_arm[name]["pass_rate"], metrics_by_arm[name]["mean_wall_ms"])
    best_baseline = min(("browser_use", "browser_use ultrafast"), key=rank)
    best_arm = min(groups, key=rank)
    boot = bootstrap(groups, tasks, best_arm)
    baseline_boot = bootstrap(groups, tasks, best_baseline)
    all_ultra = {r["task_id"]: r for r in ultra}
    ultra_boot = bootstrap({"ultrafast40": all_ultra}, tasks, "ultrafast40")
    for name, rr in groups.items():
        row = metrics_by_arm[name]
        row["pass_rate_ci"] = boot["pass_rate_ci"][name]
        row["paired_difference_vs_best_arm"] = row["pass_rate"] - metrics_by_arm[best_arm]["pass_rate"]
        row["paired_difference_ci"] = boot["difference_ci"][name]
        if name.startswith("browser_use"):
            claims = [r for r in rr.values() if r.get("claimed_answer", "").strip()]
        else:
            claims = [r for r in rr.values() if (r.get("self_checks") or [{}])[-1].get("verdict") == "PASS"]
        row["claims_or_self_check_passes"] = len(claims)
        if name == "cascade":
            continue
        row["false_accepts"] = sum(not r["success"] for r in claims)
    cascade_rows = groups["cascade"]
    self_passes = [r for r in cascade_rows.values()
                   if (r.get("self_checks") or [{}])[-1].get("verdict") == "PASS"]
    stage_replays = [stage_one_replay(r, tasks[r["task_id"]]) for r in self_passes]
    assert all(not r["stage_one_frozen_replay_success"] for r in stage_replays)
    metrics_by_arm["cascade"]["false_accepts"] = len(stage_replays)
    baseline_metrics = metrics_by_arm[best_baseline]
    cascade_metrics = metrics_by_arm["cascade"]
    delta = cascade_metrics["pass_rate"] - baseline_metrics["pass_rate"]
    time_delta = cascade_metrics["mean_wall_ms"] - baseline_metrics["mean_wall_ms"]
    shares = dict(Counter(r["answered_by"] for r in cascade_rows.values()))
    reasons = dict(Counter(r["handoff_reason"] for r in cascade_rows.values() if r["answered_by"] != "script"))
    result = {"seed": SEED, "bootstrap_draws": BOOTSTRAPS, "paired_task_ids": sorted(ids),
              "paired_site_counts": boot["clusters"], "best_arm": best_arm, "best_baseline": best_baseline,
              "paired": metrics_by_arm, "ultrafast40": {**metrics(ultra),
                  "pass_rate_ci": ultra_boot["pass_rate_ci"]["ultrafast40"],
                  "false_accepts": sum(bool(r.get("claimed_answer", "").strip()) and not r["success"] for r in ultra)},
              "ultrafast40_sites": ultra_boot["clusters"],
              "cascade": {"answered_by": shares, "handoff_reasons": reasons, "stage_one_pass_replays": stage_replays,
                          "precision_gate_false_accepts": sum(r["precision_gate_accepted"] for r in stage_replays),
                          "difference_vs_best_baseline": delta,
                          "difference_vs_best_baseline_ci": baseline_boot["difference_ci"]["cascade"],
                          "mean_wall_difference_vs_best_baseline_ms": time_delta,
                          "mean_wall_difference_ci_ms": baseline_boot["wall_difference_ci"]["cascade"],
                          "meets_point_estimate_2pp_and_lower_mean_wall": delta >= -.02 and time_delta < 0,
                          "mean_stage_wall_ms": {key: statistics.mean(r["stage_wall_ms"][key] for r in cascade_rows.values())
                                                 for key in ("grounding", "script", "browser_use")}}}
    (HERE / "paired_metrics.json").write_text(json.dumps(result, indent=2) + "\n")
    money = ledger_summary()
    for key in ("best_arm", "best_baseline", "paired", "ultrafast40", "cascade"):
        print(key + ": " + json.dumps(result[key]))
    print("Sites:", len(boot["clusters"]), "paired;", len(ultra_boot["clusters"]), "ultrafast full")
    print("Ledger reconciled:", money["running_total_usd"], "131 charged records; no paid calls")


if __name__ == "__main__":
    main()
