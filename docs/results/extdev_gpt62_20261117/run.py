"""Fixed paired subset, using the existing OpenAI probe and its cap enforcement."""

import argparse
import asyncio
import json
import math
import os
from pathlib import Path

from bench import openai_run
from bench.openai_spend import OpenAISpendLedger
from bench.probe import probe_tasks

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("model", choices=("gpt-6.2-astra", "gpt-6.2-sol", "gpt-6.1-sol"))
    parser.add_argument("--effort", choices=("low", "medium"), default="medium")
    parser.add_argument("--output-root", type=Path, default=HERE)
    parser.add_argument("--spend-baseline", type=float, default=2.942581)
    parser.add_argument("--spend-limit", type=float, default=7.0)
    parser.add_argument("--run-cap", type=float, default=4.5)
    parser.add_argument("--headroom", type=float, default=0.0)
    args = parser.parse_args()
    for name in ("spend_baseline", "spend_limit", "run_cap", "headroom"):
        value = getattr(args, name)
        if not math.isfinite(value) or value < 0 or (name != "headroom" and value == 0):
            parser.error(f"--{name.replace('_', '-')} must be finite and positive (headroom may be zero)")
    tasks = probe_tasks("extdev")[::3][:12]
    manifest = HERE / "tasks.json"
    task_ids = [t["id"] for t in tasks]
    if manifest.exists():
        assert json.loads(manifest.read_text()) == task_ids
    else:
        manifest.write_text(json.dumps(task_ids, indent=2) + "\n")
    ledger = OpenAISpendLedger.read()
    if not ledger.created or ledger.running_total_usd < args.spend_baseline or ledger.aborted:
        raise RuntimeError("Missing, stale or aborted spend ledger")
    remaining = args.spend_limit - (ledger.running_total_usd - args.spend_baseline)
    if remaining <= args.headroom:
        raise RuntimeError("New-spend safety threshold reached")
    os.environ["CU_OPENAI_RUN_BUDGET_USD"] = str(min(remaining - args.headroom, args.run_cap))
    destination = args.output_root / (args.model + "-" + args.effort + "-browser_use")
    if destination.exists():
        raise RuntimeError("Use a fresh output directory; refusing a repeat run")
    openai_run._tasks = lambda *a, **kw: tasks
    rows = asyncio.run(openai_run.execute_openai_probe(
        arms=("browser_use",), split="extdev", sweep=False, model=args.model,
        effort=args.effort, one_task=False, headless=True, spend_path=None,
        runs_dir=destination, warm_replay=False, honest=False,
    ))
    print(json.dumps({"model": args.model, "effort": args.effort, "rows": len(rows),
                      "usd": sum(r.get("usd", 0) for r in rows),
                      "ledger": OpenAISpendLedger.read().running_total_usd}))


if __name__ == "__main__":
    main()
