"""Offline comparison; new AI labels plus #103's unchanged Sol medium labels."""

import csv
import hashlib
import importlib.util
import json
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "extdev_gpt62_20261117"
spec = importlib.util.spec_from_file_location("prior_report", PRIOR / "build_labels.py")
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)


def main():
    labels = {}
    for line in (HERE / "labels_input.txt").read_text().splitlines():
        if not line.strip():
            continue
        head, note = line.split("|", 1)
        setting, task_id, label = head.split()
        assert task_id not in labels.setdefault(setting, {}), "duplicate label"
        labels[setting][task_id] = (label, note.strip())
    medium = "gpt-6.2-sol-medium"
    with (PRIOR / "hand_labels.csv").open() as f:
        labels[medium] = {r["task_id"]: (r["hand_label"], r["note"])
                          for r in csv.DictReader(f) if r["model"] == "gpt-6.2-sol"}
    manifest = json.loads((HERE / "raw_manifest.json").read_text())
    task_ids = json.loads((HERE / "tasks.json").read_text())
    assert set(manifest) == set(labels), "setting coverage mismatch"
    result, metrics = [], {}
    for setting, filename in manifest.items():
        raw = [json.loads(s) for s in (HERE / filename).read_text().splitlines()]
        attempts = [r for r in raw if "task_id" in r]
        assert [r["task_id"] for r in attempts] == task_ids, "task order mismatch"
        assert not any(r.get("skipped") for r in attempts), "incomplete setting"
        model, effort = setting.rsplit("-", 1)
        assert all(r["model"] == model and r["effort"] == effort
                   and r["arm"] == "browser_use" and r["pass"] == "cold"
                   and r["browser_use_mode"] == "default" for r in attempts)
        joined = prior.join_labels(raw, labels[setting])
        for row in joined:
            row["effort"] = effort
            row["setting"] = setting
        result.extend(joined)
        metrics[setting] = prior.summarize(joined)
        metrics[setting]["usd_per_task"] = round(metrics[setting]["usd"] / len(joined), 6)
        metrics[setting]["accuracy"] = metrics[setting]["correct"] / len(joined)
        metrics[setting]["reused_from_pr103"] = setting == medium
    with (HERE / "hand_labels.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(result[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(result)
    (HERE / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    opening = json.loads((HERE / "opening_ledger.json").read_text())
    final = json.loads((HERE / "final_ledger.json").read_text())
    summary = json.loads((HERE / "ledger_summary.json").read_text())
    assert hashlib.sha256((PRIOR / "ledger_summary.json").read_bytes()).hexdigest() == summary["source_pr103_summary_sha256"]
    assert hashlib.sha256((HERE / "opening_ledger.json").read_bytes()).hexdigest() == summary["opening_ledger_sha256"]
    assert final["tasks"][:len(opening["tasks"])] == opening["tasks"], "opening charges changed"
    assert final["recorded_extra_usd"] == opening["recorded_extra_usd"], "reserve changed"
    new = final["tasks"][len(opening["tasks"]):]
    assert len(new) == 24 and not final["aborted"]
    new_spend = sum((Decimal(str(t["usd"])) for t in new), Decimal(0))
    reported_spend = sum((Decimal(str(m["usd"])) for k, m in metrics.items() if k != medium), Decimal(0))
    assert new_spend == reported_spend == Decimal(str(summary["new_usd"])) < Decimal(3)
    assert Decimal(str(final["running_total_usd"])) == Decimal(str(opening["running_total_usd"])) + new_spend
    assert final["running_total_usd"] == summary["final_usd"]
    assert final["project_budget_usd"] == summary["cap_usd"] == 22
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
