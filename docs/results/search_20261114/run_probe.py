"""Reproduce one search comparison arm through probe_slot.sh.

Uses the normal probe runner and grader. dev-f only; hard cumulative $1
allowance from the original $5.881834 balance, checked before every API call.
No key is printed or embedded. Run from the repository root.
"""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path.cwd()))

from bench.openai_client import OpenAIClient
from bench.openai_run import _one
from bench.openai_spend import OpenAISpendLedger, price_usd
from bench.probe import probe_tasks
from bench.strategy_search import claims

LEDGER = Path("C:/Users/epicd/.cu-optimisation/openai-spend-dev-f.json")
CEILING = 6.881834


async def run(args):
    assert args.split in ("dev3", "dev4search", "heldout2", "held-out")
    os.environ["CU_OPENAI_SPEND_LEDGER"] = str(LEDGER)
    os.environ["OPENAI_API_KEY"] = Path("C:/Users/epicd/.cu-optimisation/openai.key").read_text().strip()
    os.environ["CU_SF_STRATEGY"] = "search" if args.mode == "on" else ""
    ledger = OpenAISpendLedger.read(LEDGER)
    opening = ledger.running_total_usd
    assert opening >= 5.881834 and opening < CEILING, "ledger outside original allowance"
    billed = 0.0
    original = OpenAIClient.create_message

    async def guarded(self, messages, tools, system=None, **kwargs):
        nonlocal billed
        assert self.model == "gpt-6-luna" and self.effort == "medium"
        # UTF-8 bytes upper-bound tokenized input; reserve additional framing.
        size = len(json.dumps([messages, tools, system], ensure_ascii=False).encode()) + 4000
        reserve = size * 0.00000025 + kwargs.get("max_tokens", 4096) * 0.0000005
        if opening + billed + reserve > CEILING:
            raise RuntimeError("search specialist cumulative $1 ceiling reached")
        response, elapsed = await original(self, messages, tools, system=system, **kwargs)
        usage = response["usage"]
        billed += price_usd(self.model, usage["input_tokens"], usage["output_tokens"], usage.get("cached_tokens", 0), usage.get("cache_write_30m_tokens", 0), usage.get("cache_write_12h_tokens", 0))
        return response, elapsed

    OpenAIClient.create_message = guarded
    tasks = probe_tasks(args.split, only_kind=args.kind)
    if not args.kind:
        tasks = [t for t in tasks if claims(t["description"])]
    assert tasks, "empty selection"
    output = Path(__file__).parent / (args.label + ".jsonl")
    assert not output.exists(), "refuse to overwrite a previous result"
    rows = []
    with output.open("x", encoding="utf-8") as handle:
        def sink(row):
            row["experiment_mode"] = args.mode
            row["experiment_label"] = args.label
            handle.write(json.dumps(row) + "\n")
            handle.flush()
            print(json.dumps({k: row.get(k) for k in ("task_id", "success", "end_state", "wall_ms", "model_calls", "strategy", "usd")}), flush=True)
        for task in tasks:
            await _one("script_first", task, {"model": "gpt-6-luna", "effort": "medium"},
                       api_key=os.environ["OPENAI_API_KEY"], headless=True,
                       destination=Path("bench/runs"), ledger=ledger, rows=rows, sink=sink)
    print(json.dumps({"opening": opening, "closing": ledger.running_total_usd,
                      "cumulative_added": round(ledger.running_total_usd - 5.881834, 6),
                      "output": str(output)}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("split")
    parser.add_argument("mode", choices=("off", "on"))
    parser.add_argument("label")
    parser.add_argument("--kind", default="")
    asyncio.run(run(parser.parse_args()))
