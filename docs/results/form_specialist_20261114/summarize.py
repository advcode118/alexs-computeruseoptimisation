"""Rebuild aggregate evidence from the eight archived development comparisons.

Offline, standard-library only. Never imports task catalogs or reads gate data.
"""
import hashlib
import json
import math
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SPLITS = ("dev3", "held-out", "heldout2", "dev4form")
COUNTS = (6, 6, 2, 12)


def summarize(rows):
    n = len(rows)
    times = sorted(row["wall_ms"] / 1000 for row in rows)
    calls = [row["model_calls"] for row in rows]
    passes = sum(row["success"] for row in rows)
    usd = sum(row["usd"] for row in rows)
    fallback = [row for row in rows if row.get("strategy") == "form:fallback"]
    return {
        "attempted": n,
        "passed": passes,
        "false_accepts": sum(row["end_state"] == "PASS" and not row["success"] for row in rows),
        "calls_median": statistics.median(calls),
        "calls_mean": statistics.mean(calls),
        "wall_median_s": statistics.median(times),
        "wall_mean_s": statistics.mean(times),
        "wall_p90_s_nearest_rank": times[math.ceil(n * .9) - 1],
        "usd_total": round(usd, 6),
        "usd_per_task": usd / n,
        "usd_per_pass": usd / passes if passes else None,
        "fallback_attempted": len(fallback),
        "fallback_passed": sum(row["success"] for row in fallback),
        "fallback_false_accepts": sum(row["end_state"] == "PASS" and not row["success"] for row in fallback),
    }


def main():
    result = {
        "provider": "openai",
        "model": "gpt-6-luna",
        "effort": "medium",
        "arm": "script_first",
        "runtime_commit": "b42e486",
        "recorded_head": "9bd9402388b0cc45d0a101289f509ba61725344c",
        "baseline_runtime": "56fbcab",
        "order": "dev3 off/on, held-out off/on, heldout2 off/on, dev4form off/on",
        "repetitions_per_task_per_variant": 1,
        "dev4form_checkpoint": "first contact and final; no later retuning or rerun",
        "false_accept_definition": "runtime end_state PASS and shared post-run success false; denominator all attempted",
        "wall_time_population": "all attempted tasks, including failed specialist and generic fallback time",
        "splits": {},
    }
    for split, expected_n in zip(SPLITS, COUNTS):
        entries = {}
        ids = None
        for variant in ("off", "on"):
            path = ROOT / f"{split}_{variant}.jsonl"
            raw = path.read_bytes()
            rows = [json.loads(line) for line in raw.decode("utf-8").splitlines()]
            assert len(rows) == expected_n
            current_ids = [row["task_id"] for row in rows]
            assert len(set(current_ids)) == expected_n
            assert ids is None or current_ids == ids, "off/on task order differs"
            ids = current_ids
            for row in rows:
                assert (row["provider"], row["model"], row["effort"], row["arm"]) == (
                    "openai", "gpt-6-luna", "medium", "script_first")
                assert not row["skipped"]
                assert bool(row.get("strategy")) == (variant == "on")
            entries[variant] = {
                "file": path.name,
                "sha256": hashlib.sha256(raw).hexdigest(),
                **summarize(rows),
            }
        result["splits"][split] = entries
    result["comparison_spend_usd"] = round(sum(
        entry["usd_total"] for pair in result["splits"].values() for entry in pair.values()), 6)
    (ROOT / "summary.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"rows": 52, "comparison_spend_usd": result["comparison_spend_usd"],
                      "splits": {split: {variant: {key: entry[key] for key in (
                          "passed", "attempted", "false_accepts", "fallback_attempted", "fallback_passed",
                          "fallback_false_accepts")} for variant, entry in pair.items()}
                          for split, pair in result["splits"].items()}}, indent=2))


if __name__ == "__main__":
    main()
