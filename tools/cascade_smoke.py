"""Three authorized extdev tasks through the budgeted OpenAI probe runner."""

import asyncio
import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bench.openai_run import execute_openai_probe
from bench.openai_spend import OpenAISpendLedger
from bench.tasks import tasks_for_split


TASK_IDS = (
    "extdev_value_hf_tei_strengths",
    "extdev_value_cambridge_gestalt",
    "extdev_value_icse_2002_chairs",
)


async def main():
    tasks = {task["id"]: task for task in tasks_for_split("extdev")}
    selected = [tasks[task_id] for task_id in TASK_IDS]
    with patch("bench.openai_run._tasks", return_value=selected):
        rows = await execute_openai_probe(
            arms=("cascade",), split="extdev", sweep=False, model="gpt-6.1-sol",
            effort="medium", one_task=False, headless=True, spend_path=None,
            runs_dir=ROOT / "docs/results/extdev_control_20261117/smoke",
            warm_replay=False, honest=False,
        )
    for row in rows:
        print(json.dumps({key: row.get(key) for key in (
            "task_id", "answered_by", "handoff_reason", "wall_ms", "usd", "success",
            "handoff_url", "browser_use_initial_url", "handoff_target_id",
            "browser_use_initial_target_id", "success_reason",
        )}))
    print("ledger_total_usd", OpenAISpendLedger.read().running_total_usd)


if __name__ == "__main__":
    asyncio.run(main())
