"""Explicitly authorized replicate-one extdev control runs."""

import argparse
import asyncio
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bench.openai_run import execute_openai_probe
from bench.openai_spend import OpenAISpendLedger, openai_run_budget_usd


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("default", "ultrafast"), required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    mode = os.environ.get("CU_BU_MODE", "").strip() or "default"
    if mode != args.mode:
        parser.error("CU_BU_MODE does not match --mode")
    ledger = OpenAISpendLedger.read()
    expected = Path.home() / ".cu-optimisation/openai-spend-alex15.json"
    if ledger.path != expected or ledger.project_budget_usd != 9 or openai_run_budget_usd() != 3:
        parser.error("Requires the alex15 ledger, $9 project cap and $3 run cap")
    if mode == "ultrafast" and ledger.running_total_usd > 4.50:
        parser.error("Ledger exceeds $4.50; ultrafast invocation refused")
    arms = ("browser_use",) if mode == "ultrafast" else ("browser_use", "playwright_mcp", "script_first", "cascade")
    if not args.execute:
        print(json.dumps({"execute": False, "arms": arms, "split": "extdev", "mode": mode}))
        return
    destination = ROOT / "docs/results/extdev_control_20261117/raw"
    destination.mkdir(parents=True, exist_ok=True)
    metadata_path = destination / f"{mode}_rep1.json"
    if metadata_path.exists():
        parser.error("Replicate metadata already exists; refusing an accidental rerun")
    metadata = {"replicate": 1, "browser_use_mode": mode, "arms": arms,
                "ledger_before_usd": ledger.running_total_usd,
                "project_cap_usd": 9, "run_cap_usd": 3, "status": "running"}
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n")
    try:
        rows = await execute_openai_probe(
            arms=arms, split="extdev", sweep=False, model="gpt-6.1-sol",
            effort="medium", one_task=False, headless=True, spend_path=None,
            runs_dir=destination, warm_replay=False, honest=False,
        )
        metadata.update(status="completed", rows=len(rows))
    finally:
        metadata["ledger_after_usd"] = OpenAISpendLedger.read().running_total_usd
        metadata_path.write_text(json.dumps(metadata, indent=2) + "\n")
        print(json.dumps(metadata), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
