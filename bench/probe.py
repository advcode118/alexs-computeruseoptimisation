"""Small probe: 3 WebVoyager tasks x 4 arms. Prepared here, not launched.

The competitive path is the outer model claude-sonnet-5-5 on every arm.
diff_fast_act and macro_replay use the same loop as playwright_mcp and
stagehand. Their tools are the proxy surface: settle plus a compact diff,
fast_act with a script, and do_task_segment. The tools do not call Claude.
The outer loop does. Opus is never used.

That probe stops once it has spent $5 on Claude, and once the project total
would pass $40. A first snapshot longer than HUGE_SNAPSHOT_CHARS is skipped
before any model call. The skip looks at the returned body length only.
full_snapshot_chars inside a compact diff does not skip the task.
Each Playwright MCP arm uses --isolated only. @playwright/mcp@0.0.84 rejects
--isolated together with --user-data-dir. The Stagehand arm uses its own
user-data-dir. Sequential arms do not share the workspace Chrome profile.

--warm-replay runs after the cold 3x4. It re-runs the same 3 tasks on
macro_replay and diff_fast_act and records replay hit rate and wall. The
replay cache is the same file, so a sequence stored on the cold pass can hit.
When script_first is selected it is re-run too. Its cached-script file is new
for each probe, so the cold pass stays cold and only stores scripts the
evidence judge passed. Cold and warm are summarized separately. Each summary
records the tier that answered (cache_hit, patched, fresh) and the model calls.

--no-model-only is optional. It puts diff_fast_act and macro_replay back on
decide() with no outer model. That path cannot close the Stagehand gap. It
is not the competitive measurement.

Do not pass --execute from a checkout that has no ANTHROPIC_API_KEY. This
tree does not call Claude. Box commands, from the repo root:

    python -m bench.probe
    ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" python -m bench.probe --execute
    ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" python -m bench.probe --execute --warm-replay
    python -m bench.probe --execute --no-model-only
    ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" python -m bench.probe --execute --arms playwright_mcp,script_first,stagehand
    ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" python -m bench.probe --execute --arms script_first --warm-replay

The first prints the plan and exits. The second is the competitive 3x4.
The third is that 3x4 plus the warm second pass. Do not run it from this
checkout. The fourth is the optional no-model path for the two proxy arms only.
The fifth is the script_first comparison. The sixth is script_first cold, then
warm from its cached scripts. Both stop Claude at $2. The project
abort stays $40. The operator envelope is $50. Do not pass --execute from
this VM. script_first writes one Playwright script for the whole task and
runs it with no per-click settle or snapshot.

Environment variables it reads, by name only:

    ANTHROPIC_API_KEY     outer model for every competitive arm
    NEBIUS_API_KEY        optional, do_task_segment's cheap fallback only
    NEBIUS_BASE_URL       optional, with NEBIUS_API_KEY
    NEBIUS_FAST_MODEL     optional, with NEBIUS_API_KEY
    BROWSERBASE_API_KEY   not used to open a session; local Chrome either way
    BROWSERBASE_PROJECT_ID
    SETTLE_QUIET_MS       default 500
    SETTLE_TIMEOUT_MS     default 3000
    REPLAY_CACHE_PATH     macro_replay cache file
    CU_SPEND_LEDGER       shared spend.json. Missing file: live run refuses
    PLAYWRIGHT_MCP_PROXY_CHILD   optional override for the proxy's browser
    PLAYWRIGHT_MCP_HEADLESS      set on the proxy process when the probe is headless

No variable value is printed.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from bench.arms import (
    ARM_ENDPOINT,
    ARM_SCRIPT_FIRST,
    ARMS,
    NO_MODEL_CAPABLE,
    SCRIPT_FIRST_MAX_CALLS,
    SELECTABLE_ARMS,
    arm_needs_claude,
)
from bench.budget import ALLOWED_MODEL, PROJECT_BUDGET_USD, LedgerMissing, SpendLedger, estimate_usd
from bench.judge import check_text_present, check_url_contains
from bench.tasks import get_webvoyager_tasks

PROBE_TASK_IDS = ("wv_wikipedia_search", "wv_python_docs", "wv_hackernews_top")
PROBE_CLAUDE_BUDGET_USD = 5.0
SCRIPT_FIRST_CLAUDE_BUDGET_USD = 2.0
HUGE_SNAPSHOT_CHARS = 40_000
WARM_ARMS = ("macro_replay", "diff_fast_act")
RUNS_DIR = Path(__file__).resolve().parent / "runs"

# Exact commands for a box that has the key. This checkout does not run them.
BOX_COMMANDS = (
    "python -m bench.probe",
    'ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" python -m bench.probe --execute',
    'ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" python -m bench.probe --execute --warm-replay',
    "python -m bench.probe --execute --no-model-only",
    'ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" python -m bench.probe --execute --arms playwright_mcp,script_first,stagehand',
    'ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" python -m bench.probe --execute --arms script_first --warm-replay',
)


def probe_tasks() -> list[dict]:
    """The three modest tasks, in the same shape as the rest of the suite."""
    wanted = set(PROBE_TASK_IDS)
    found = [task for task in get_webvoyager_tasks() if task["id"] in wanted]
    missing = wanted.difference(task["id"] for task in found)
    if missing:
        raise RuntimeError(f"probe tasks missing from the suite: {sorted(missing)}")
    order = {task_id: index for index, task_id in enumerate(PROBE_TASK_IDS)}
    return sorted(found, key=lambda task: order[task["id"]])


def resolve_arms(spec: str | tuple[str, ...] | list[str] | None) -> tuple[str, ...]:
    """Default is the four-arm probe. A comma string selects, including script_first."""
    if spec is None:
        return ARMS
    if isinstance(spec, str):
        if not spec.strip():
            return ARMS
        names = tuple(part.strip() for part in spec.split(",") if part.strip())
    else:
        names = tuple(spec)
    if not names:
        raise ValueError("no arms selected")
    unknown = [name for name in names if name not in SELECTABLE_ARMS]
    if unknown:
        raise ValueError(f"unknown arm {unknown[0]!r}")
    if len(names) != len(set(names)):
        raise ValueError("arms contains a duplicate")
    return names


def warm_arms_for(arms: tuple[str, ...]) -> tuple[str, ...]:
    """The proxy replay arms, plus script_first when it was selected."""
    if ARM_SCRIPT_FIRST in arms:
        return WARM_ARMS + (ARM_SCRIPT_FIRST,)
    return WARM_ARMS


def claude_budget_for(arms: tuple[str, ...]) -> float:
    """script_first's execute path stops at $2. The four-arm probe stays at $5."""
    if ARM_SCRIPT_FIRST in arms:
        return SCRIPT_FIRST_CLAUDE_BUDGET_USD
    return PROBE_CLAUDE_BUDGET_USD


def plan_probe(
    *,
    no_model_only: bool = False,
    warm_replay: bool = False,
    arms: str | tuple[str, ...] | list[str] | None = None,
) -> dict:
    """What --execute would run. This does not start a browser or a model."""
    chosen = resolve_arms(arms)
    spent = SpendLedger.load().running_total_usd
    return {
        "execute": False,
        "mode": "no_model_only" if no_model_only else "outer_claude",
        "tasks": [task["id"] for task in probe_tasks()],
        "arms": list(chosen),
        "available_arms": list(SELECTABLE_ARMS),
        "claude_arms": [arm for arm in chosen if arm_needs_claude(arm, no_model_only=no_model_only)],
        "no_model_arms": [arm for arm in chosen if not arm_needs_claude(arm, no_model_only=no_model_only)],
        "no_model_only_arms": [arm for arm in chosen if arm in NO_MODEL_CAPABLE],
        "outer_model": ALLOWED_MODEL,
        "claude_budget_usd": claude_budget_for(chosen),
        "script_first_claude_budget_usd": SCRIPT_FIRST_CLAUDE_BUDGET_USD,
        "project_budget_usd": PROJECT_BUDGET_USD,
        "project_spent_usd": spent,
        "huge_snapshot_chars": HUGE_SNAPSHOT_CHARS,
        "huge_snapshot_uses_body_length_only": True,
        "warm_replay": warm_replay,
        "warm_arms": list(warm_arms_for(chosen)),
        "browser_isolation": {
            "playwright_mcp": "--isolated only (0.0.84 rejects --user-data-dir with --isolated)",
            "diff_fast_act": "proxy child --isolated only",
            "macro_replay": "proxy child --isolated only",
            "stagehand": "a unique --user-data-dir via launch_persistent_context",
            "script_first": "local Chrome via the Playwright Python API, own user-data-dir, no per-click settle",
            "endpoint": "direct fetch of the task start URL; no browser; the fetch URL is not rewritten",
        },
        "box_commands": list(BOX_COMMANDS),
        "records": [
            "wall_ms",
            "success",
            "steps",
            "input_tokens",
            "output_tokens",
            "usd",
            "model_ignores_tools",
            "no_model",
            "replay_hit",
            "pass",
        ],
    }


def snapshot_is_huge(text: str, limit: int = HUGE_SNAPSHOT_CHARS) -> bool:
    """True only when the returned body is longer than the limit.

    full_snapshot_chars inside a compact diff is the page size, not the text
    the model would read. A short diff of a long page is not skipped.
    """
    return len(text or "") > limit


def claude_block_reason(
    probe_spent_usd: float,
    project_spent_usd: float,
    *,
    budget_usd: float = PROBE_CLAUDE_BUDGET_USD,
) -> str | None:
    """Why the next Claude task must not start. None when it may."""
    if probe_spent_usd >= budget_usd:
        return f"probe Claude spend ${probe_spent_usd:.2f} has reached ${budget_usd:.0f}"
    if project_spent_usd >= PROJECT_BUDGET_USD:
        return f"project total ${project_spent_usd:.2f} has reached ${PROJECT_BUDGET_USD:.0f}"
    return None


def deterministic_success(task: dict, url: str, text: str) -> tuple[bool | None, str]:
    """URL and text checks only. The LLM judge is not called."""
    if task.get("check_url_contains"):
        result = check_url_contains(url, task["check_url_contains"])
        return result.success, result.reason
    if task.get("check_text"):
        result = check_text_present(text, task["check_text"])
        return result.success, result.reason
    return None, "no deterministic check; LLM judge was not called"


def empty_row(
    arm: str,
    task_id: str,
    *,
    reason: str,
    skipped: bool = True,
    no_model_only: bool = False,
) -> dict:
    return {
        "arm": arm,
        "task_id": task_id,
        "success": False,
        "success_reason": reason,
        "skipped": skipped,
        "wall_ms": 0.0,
        "steps": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "usd": 0.0,
        "model_ignores_tools": 0,
        "no_model": not arm_needs_claude(arm, no_model_only=no_model_only),
        "replay_hit": False,
        "claude": False,
    }


async def _peek_snapshot(client, arm: str, url: str) -> tuple[str, float]:
    """Open the page and return the first snapshot text. No model call.

    script_first does not snapshot before the script. An empty peek is not a
    huge page, so the model call is not skipped for length.
    """
    if arm == ARM_SCRIPT_FIRST:
        return "", 0.0
    if arm == "stagehand":
        await client.call_tool("run", {"code": f"page.goto({json.dumps(url)})"})
        return await client.call_tool("snapshot", {})
    text, elapsed = await client.call_tool("browser_navigate", {"url": url})
    return text, elapsed


async def run_no_model_arm(arm: str, task: dict, *, headless: bool = True) -> dict:
    """Optional decide() path. This function does not call Anthropic.

    The competitive probe does not call this. A no-model-only run cannot
    close the Stagehand gap on open WebVoyager tasks.
    """
    if arm_needs_claude(arm, no_model_only=True):
        raise RuntimeError(f"{arm} needs Claude and must not use the no-model runner")
    from bench.arms import build_client

    started = time.perf_counter()
    client = build_client(arm, headless=headless)
    await client.start()
    try:
        peeked, _elapsed = await _peek_snapshot(client, arm, task["start_url"])
        if snapshot_is_huge(peeked):
            row = empty_row(arm, task["id"], reason=f"skipped: first snapshot is {len(peeked)} chars")
            row["wall_ms"] = (time.perf_counter() - started) * 1000
            return row
        tool = "fast_act" if arm == "diff_fast_act" else "do_task_segment"
        body, _tool_ms = await client.call_tool(tool, {"task": task["description"]})
        payload = {}
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = {}
        url = str(payload.get("url") or "")
        page = str(payload.get("page") or "") + "\n" + str(payload.get("diff") or "")
        checked, reason = deterministic_success(task, url, page)
        success = bool(payload.get("ok")) if checked is None else bool(checked)
        if checked is None:
            success = False
        return {
            "arm": arm,
            "task_id": task["id"],
            "success": success,
            "success_reason": reason if checked is not None else payload.get("summary") or reason,
            "skipped": False,
            "wall_ms": (time.perf_counter() - started) * 1000,
            "steps": int(payload.get("cycles") or 0),
            "input_tokens": 0,
            "output_tokens": 0,
            "usd": 0.0,
            "model_ignores_tools": int(payload.get("model_ignores_tools") or 0),
            "no_model": int(payload.get("model_calls") or 0) == 0,
            "replay_hit": payload.get("tier") == "replay",
            "tier": payload.get("tier") or "",
            "claude": False,
        }
    finally:
        await client.stop()


async def run_claude_arm(
    arm: str,
    task: dict,
    *,
    api_key: str,
    headless: bool,
    runs_dir: Path,
    script_cache=None,
) -> dict:
    """Outer claude-sonnet-5-5. Caller has already checked both budgets."""
    from bench.harness import BenchmarkHarness

    started = time.perf_counter()
    # script_first starts at one script plus a completion turn. The harness
    # adds a turn only for a repair or a refused extra script, stops at
    # SCRIPT_FIRST_HARD_CAP, and runs at most one repair script.
    max_steps = SCRIPT_FIRST_MAX_CALLS if arm == ARM_SCRIPT_FIRST else 30
    harness = BenchmarkHarness(
        api_key=api_key,
        headless=headless,
        runs_dir=runs_dir,
        arm=arm,
        max_steps=max_steps,
        script_cache=script_cache if arm == ARM_SCRIPT_FIRST else None,
    )
    await harness.setup()
    try:
        peeked, _elapsed = await _peek_snapshot(harness.mcp_client, arm, task["start_url"])
        if snapshot_is_huge(peeked):
            row = empty_row(arm, task["id"], reason=f"skipped: first snapshot is {len(peeked)} chars")
            row["wall_ms"] = (time.perf_counter() - started) * 1000
            row["claude"] = False
            return row
        result = await harness.run_task(
            task_id=task["id"],
            task_description=task["description"],
            start_url=task["start_url"],
            expected_answer=task.get("expected_answer"),
            judge_prompt=task.get("judge_prompt"),
            check_url_contains=task.get("check_url_contains") or "",
        )
        final_url = result.steps[-1].page_url if result.steps else ""
        final_text = result.steps[-1].snapshot_text if result.steps else ""
        substring_ok, substring_reason = deterministic_success(task, final_url, final_text)
        end_state = result.end_state or ""
        if arm == ARM_SCRIPT_FIRST and end_state:
            # UNKNOWN is its own outcome. It is not a success, and a FAIL
            # is not rescued by the old substring check.
            success = end_state == "PASS"
            reason = result.success_reason or substring_reason
        else:
            success = result.success if substring_ok is None else bool(result.success and substring_ok)
            if substring_ok is not None and not substring_ok:
                reason = substring_reason
            elif result.success_reason:
                reason = result.success_reason
            else:
                reason = substring_reason
        usd = estimate_usd(result.total_input_tokens, result.total_output_tokens)
        return {
            "arm": arm,
            "task_id": task["id"],
            "success": success,
            "success_reason": reason,
            "end_state": end_state,
            "substring_success": substring_ok,
            "substring_reason": substring_reason,
            "skipped": False,
            "wall_ms": result.total_wall_ms or ((time.perf_counter() - started) * 1000),
            "steps": result.total_steps,
            "input_tokens": result.total_input_tokens,
            "output_tokens": result.total_output_tokens,
            "usd": usd,
            "model_ignores_tools": result.model_ignores_tools,
            "no_model": result.tier == "cache_hit" and result.model_calls == 0,
            "replay_hit": result.replay_hits > 0 or result.tier == "cache_hit",
            "tier": result.tier,
            "model_calls": result.model_calls,
            "script_steps": result.script_steps,
            "claude": True,
        }
    finally:
        await harness.teardown()


def _summary_for(rows: list[dict], phase: str, arms: tuple[str, ...]) -> dict:
    """Hit rate, wall, and script_first tier counts for one probe pass."""
    summary = {}
    for arm in arms:
        subset = [row for row in rows if row.get("pass") == phase and row.get("arm") == arm]
        hits = sum(1 for row in subset if row.get("replay_hit"))
        wall_ms = sum(float(row.get("wall_ms") or 0) for row in subset)
        summary[arm] = {
            "tasks": len(subset),
            "replay_hits": hits,
            "replay_hit_rate": (hits / len(subset)) if subset else 0.0,
            "wall_ms": wall_ms,
        }
        if arm == ARM_SCRIPT_FIRST:
            summary[arm]["tiers"] = {
                tier: sum(1 for row in subset if row.get("tier") == tier)
                for tier in ("cache_hit", "patched", "fresh")
            }
            summary[arm]["passed"] = sum(1 for row in subset if row.get("success"))
            summary[arm]["model_calls"] = sum(int(row.get("model_calls") or 0) for row in subset)
            summary[arm]["steps"] = sum(int(row.get("steps") or 0) for row in subset)
    return summary


def warm_summary(rows: list[dict]) -> dict:
    """Replay hit rate and wall for the warm second pass, by arm.

    script_first also reports which tier answered and its model calls.
    Cold rows are not included. See cold_summary.
    """
    arms = WARM_ARMS
    if any(row.get("pass") == "warm" and row.get("arm") == ARM_SCRIPT_FIRST for row in rows):
        arms = WARM_ARMS + (ARM_SCRIPT_FIRST,)
    return _summary_for(rows, "warm", arms)


def cold_summary(rows: list[dict]) -> dict:
    """The cold pass, in the same shape as warm_summary, with its own tier counts."""
    arms: list[str] = []
    for row in rows:
        if row.get("pass") != "cold":
            continue
        arm = row.get("arm")
        if isinstance(arm, str) and arm and arm not in arms:
            arms.append(arm)
    return _summary_for(rows, "cold", tuple(arms))


async def _run_endpoint(
    task: dict,
    *,
    headless: bool,
    api_key: str,
    probe_spent: float,
    ledger: SpendLedger,
    destination: Path,
    budget_usd: float,
    opener,
) -> tuple[dict, float]:
    """Fetch the start URL. A miss runs script_first. No browser on the fetch."""
    del headless
    from bench.endpoint import EndpointError, fetch_start_url, run_endpoint_task

    if opener is None:
        row = empty_row(
            ARM_ENDPOINT,
            task["id"],
            reason="endpoint live fetch is not run from this checkout; refusing to open a browser",
        )
        return row, probe_spent
    selector = ""
    markers = task.get("end_markers") or {}
    if isinstance(markers, dict):
        selector = str(markers.get("answer_equals_selector") or "")
    try:
        page = fetch_start_url(task["start_url"], opener=opener, selector=selector)
    except EndpointError as exc:
        return empty_row(ARM_ENDPOINT, task["id"], reason=str(exc)), probe_spent

    async def fallback(missed: dict) -> dict:
        if not api_key:
            return empty_row(ARM_SCRIPT_FIRST, missed["id"], reason="ANTHROPIC_API_KEY unset", skipped=False)
        blocked = claude_block_reason(probe_spent, ledger.running_total_usd, budget_usd=budget_usd)
        if blocked:
            return empty_row(ARM_SCRIPT_FIRST, missed["id"], reason=blocked, skipped=False)
        return await run_claude_arm(
            ARM_SCRIPT_FIRST,
            missed,
            api_key=api_key,
            headless=True,
            runs_dir=destination,
        )

    row = await run_endpoint_task(task, page, fallback=fallback)
    if row.get("arm") == ARM_SCRIPT_FIRST and row.get("claude") and (row.get("input_tokens") or row.get("output_tokens")):
        ledger.record_task(
            run_id="probe",
            task_id=f"{ARM_SCRIPT_FIRST}:{row['task_id']}",
            input_tokens=row["input_tokens"],
            output_tokens=row["output_tokens"],
        )
        probe_spent += float(row.get("usd") or 0)
        if ledger.running_total_usd >= PROJECT_BUDGET_USD:
            ledger.mark_aborted()
        ledger.save()
    return row, probe_spent


async def _run_one(
    arm: str,
    task: dict,
    *,
    headless: bool,
    no_model_only: bool,
    api_key: str,
    probe_spent: float,
    ledger: SpendLedger,
    destination: Path,
    budget_usd: float,
    script_cache=None,
    endpoint_opener=None,
) -> tuple[dict, float]:
    """One task on one arm. Returns the row and the probe's Claude spend so far."""
    if arm == ARM_ENDPOINT:
        return await _run_endpoint(
            task,
            headless=headless,
            api_key=api_key,
            probe_spent=probe_spent,
            ledger=ledger,
            destination=destination,
            budget_usd=budget_usd,
            opener=endpoint_opener,
        )
    if not arm_needs_claude(arm, no_model_only=no_model_only):
        return await run_no_model_arm(arm, task, headless=headless), probe_spent
    if not api_key:
        return (
            empty_row(
                arm,
                task["id"],
                reason="ANTHROPIC_API_KEY unset",
                no_model_only=no_model_only,
            ),
            probe_spent,
        )
    blocked = claude_block_reason(probe_spent, ledger.running_total_usd, budget_usd=budget_usd)
    if blocked:
        return empty_row(arm, task["id"], reason=blocked, no_model_only=no_model_only), probe_spent
    extra = {"script_cache": script_cache} if script_cache is not None and arm == ARM_SCRIPT_FIRST else {}
    row = await run_claude_arm(
        arm,
        task,
        api_key=api_key,
        headless=headless,
        runs_dir=destination,
        **extra,
    )
    if row.get("claude") and (row["input_tokens"] or row["output_tokens"]):
        ledger.record_task(
            run_id="probe",
            task_id=f"{arm}:{row['task_id']}",
            input_tokens=row["input_tokens"],
            output_tokens=row["output_tokens"],
        )
        probe_spent += row["usd"]
        if ledger.running_total_usd >= PROJECT_BUDGET_USD:
            ledger.mark_aborted()
        ledger.save()
    return row, probe_spent


async def execute_probe(
    *,
    headless: bool = True,
    spend_path: Path | None = None,
    runs_dir: Path | None = None,
    no_model_only: bool = False,
    warm_replay: bool = False,
    arms: tuple[str, ...] | None = None,
    endpoint_opener=None,
) -> list[dict]:
    """Run the matrix. Claude arms are skipped when the key is missing or the cap is hit.

    The default is the competitive outer-Claude matrix, including the two
    proxy arms. no_model_only keeps those two on decide() and still sends
    playwright_mcp and stagehand through Claude when a key is set.
    """
    chosen = resolve_arms(arms)
    budget_usd = claude_budget_for(chosen)
    ledger = SpendLedger.load(spend_path)
    destination = runs_dir or RUNS_DIR
    destination.mkdir(parents=True, exist_ok=True)
    probe_spent = 0.0
    rows: list[dict] = []
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    tasks = probe_tasks()
    script_cache = None
    if warm_replay and ARM_SCRIPT_FIRST in chosen:
        from bench.script_cache import ScriptCache

        # A new file per probe: the cold pass starts empty and the warm pass reads it.
        started = datetime.now().strftime("%Y%m%d_%H%M%S")
        script_cache = ScriptCache(destination / f"script_cache_{started}.json")

    async def take(arm: str, task: dict, phase: str) -> None:
        nonlocal probe_spent
        row, probe_spent = await _run_one(
            arm,
            task,
            headless=headless,
            no_model_only=no_model_only,
            api_key=api_key,
            probe_spent=probe_spent,
            ledger=ledger,
            destination=destination,
            budget_usd=budget_usd,
            script_cache=script_cache,
            endpoint_opener=endpoint_opener,
        )
        row["pass"] = phase
        rows.append(row)

    for task in tasks:
        for arm in chosen:
            await take(arm, task, "cold")
    if warm_replay:
        # Same cache file as the cold pass. Do not delete it between passes.
        for task in tasks:
            for arm in warm_arms_for(chosen):
                if arm not in chosen:
                    continue
                await take(arm, task, "warm")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = destination / f"probe_{stamp}.jsonl"
    with out.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")
        if warm_replay:
            handle.write(
                json.dumps(
                    {
                        "kind": "warm_summary",
                        "cold": cold_summary(rows),
                        "warm": warm_summary(rows),
                    }
                )
                + "\n"
            )
    if not any(row.get("claude") for row in rows):
        ledger.save()
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare the 3x4 probe. Pass --execute to run it.")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Run the probe. Omit this to print the plan and exit.",
    )
    parser.add_argument("--no-headless", action="store_true", help="Show the browser. Only with --execute.")
    parser.add_argument(
        "--no-model-only",
        action="store_true",
        help=(
            "Run diff_fast_act and macro_replay through decide() with no outer model. "
            "Not the competitive measurement. Those arms cannot close the Stagehand gap this way."
        ),
    )
    parser.add_argument(
        "--arms",
        default="",
        help=(
            "Comma-separated arms. Default is the four-arm probe. "
            "script_first is the whole-task script arm. "
            "A selection that includes it stops Claude at $2."
        ),
    )
    parser.add_argument(
        "--warm-replay",
        action="store_true",
        help=(
            "After the cold 3x4, re-run the same 3 tasks on macro_replay and diff_fast_act, "
            "and on script_first when it is selected. Records replay hit rate and wall, and "
            "script_first's tier. Uses the same caches. Not run from this checkout."
        ),
    )
    args = parser.parse_args(argv)
    try:
        chosen = resolve_arms(args.arms)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    try:
        if not args.execute:
            print(
                json.dumps(
                    plan_probe(
                        no_model_only=args.no_model_only,
                        warm_replay=args.warm_replay,
                        arms=chosen,
                    ),
                    indent=2,
                )
            )
            return 0
        rows = asyncio.run(
            execute_probe(
                headless=not args.no_headless,
                no_model_only=args.no_model_only,
                warm_replay=args.warm_replay,
                arms=chosen,
            )
        )
    except LedgerMissing as exc:
        print(str(exc), file=sys.stderr)
        return 2
    spent = sum(row["usd"] for row in rows)
    print(f"probe rows: {len(rows)}")
    print(f"probe claude usd: {spent:.4f}")
    if args.warm_replay:
        print(json.dumps({"cold": cold_summary(rows), "warm": warm_summary(rows)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
