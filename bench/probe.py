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
    ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" python -m bench.probe --execute --arms playwright_mcp,script_first,stagehand --split held-out

The first prints the plan and exits. The second is the competitive 3x4.
The third is that 3x4 plus the warm second pass. Do not run it from this
checkout. The fourth is the optional no-model path for the two proxy arms only.
The fifth is the script_first comparison. The sixth is script_first cold, then
warm from its cached scripts. Both stop Claude at $2. The project
abort stays $40. The operator envelope is $50. Do not pass --execute from
this VM. script_first writes one Playwright script for the whole task and
runs it with no per-click settle or snapshot.

--split probe is the three tuned tasks and the default. --split dev is the
wider tune set. --split held-out is the scored set. Dev and held-out are
disjoint, so the tasks we tune are not the tasks we score. Do not run the
held-out command from this checkout. It is a live Claude probe.
--split heldout2 selects twenty independently authored public tasks.
--split heldout3a and --split heldout3b select thirty more each, and
--split heldout3c and --split heldout3d forty more each, from
bench/tasks_heldout3_*.py. --split heldout3 is all four: the frozen test
set. --split dev3 selects forty public tune tasks from bench/tasks_dev3.py.
--split val3 selects forty validation tasks from bench/tasks_val3.py,
an aggregate-only gate. Without --execute they only list the plan, like
every other split.

--honest is the live comparison. It selects playwright_mcp, script_first,
stagehand, and browser_use on the held-out scored set, and a warm replay of
script_first only. The dev tasks are not scored. The cold pass leaves the
script cache empty. The per-run ceiling is $8, held under the $50 lifetime
cap and the $40 project abort. A task is not started unless the reserve
still fits under all three. --repeats N runs each cold task N times and
reports the mean, median, p90, and a 95%% confidence interval of the mean
wall time. The default is 1. Later cold repeats do not read the script
cache. The warm pass still reads the cache the first cold pass filled.
At the published PR #18 per-task rate, one cold pass of the scored set is
about $6, which is above $3–$5. Dry run:

    python -m bench.probe --honest

That prints the plan and does not open a network connection. Live, on a
machine that already has the key and the shared ledger:

    CU_SPEND_LEDGER="$CU_SPEND_LEDGER" ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" python -m bench.probe --execute --honest

A ledger below $16.639436 is refused. This file does not write that number.

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
    ARM_BROWSER_USE,
    ARM_ENDPOINT,
    ARM_PLAYWRIGHT,
    ARM_SCRIPT_FIRST,
    ARM_STAGEHAND,
    ARMS,
    BASELINE_ARMS,
    NO_MODEL_CAPABLE,
    SCRIPT_FIRST_MAX_CALLS,
    SELECTABLE_ARMS,
    arm_needs_claude,
)
from bench.budget import (
    ALLOWED_MODEL,
    LAST_RECORDED_TOTAL_USD,
    LIFETIME_CAP_USD,
    PROJECT_BUDGET_USD,
    LedgerBelowRecorded,
    LedgerMissing,
    SpendLedger,
    estimate_usd,
)
from bench.judge import check_text_present, check_url_contains
from bench.tasks import (
    DEV_TASK_IDS,
    HELD_OUT_TASK_IDS,
    SPLIT_DEV3,
    SPLIT_DEV4_FORM,
    SPLIT_HELDOUT2,
    SPLIT_HELDOUT3B,
    SPLIT_HELDOUT3A,
    SPLIT_HELDOUT3D,
    SPLIT_HELDOUT3C,
    SPLIT_HELDOUT3,
    SPLIT_HONEST,
    SPLIT_VAL3,
    SPLIT_PROBE,
    TUNED_PROBE_TASK_IDS,
    resolve_task_split,
    tasks_for_split,
)

PROBE_TASK_IDS = TUNED_PROBE_TASK_IDS
PROBE_CLAUDE_BUDGET_USD = 5.0
SCRIPT_FIRST_CLAUDE_BUDGET_USD = 2.0
# Hard ceiling for --honest. The run is meant to land around $5–$8.
HONEST_PROBE_BUDGET_USD = 8.0
HONEST_ARMS = (ARM_PLAYWRIGHT, ARM_SCRIPT_FIRST, ARM_BROWSER_USE)
# One cold pass. A second pass would double the scored-set bill.
DEFAULT_REPEATS = 1
# Published dollars from the PR #18 probe, three tasks, at the ledger rate.
# browser_use was not in that probe. This is not a new measurement.
PUBLISHED_TASK_USD = {
    ARM_PLAYWRIGHT: 0.165 / 3,
    ARM_SCRIPT_FIRST: 0.047 / 3,
    ARM_STAGEHAND: 0.074 / 3,
}
# Two-sided 95% Student t critical values, df = n - 1. df above 30 uses 1.96.
_T_95 = {
    1: 12.706,
    2: 4.303,
    3: 3.182,
    4: 2.776,
    5: 2.571,
    6: 2.447,
    7: 2.365,
    8: 2.306,
    9: 2.262,
    10: 2.228,
    11: 2.201,
    12: 2.179,
    13: 2.160,
    14: 2.145,
    15: 2.131,
    16: 2.120,
    17: 2.110,
    18: 2.101,
    19: 2.093,
    20: 2.086,
    21: 2.080,
    22: 2.074,
    23: 2.069,
    24: 2.064,
    25: 2.060,
    26: 2.056,
    27: 2.052,
    28: 2.048,
    29: 2.045,
    30: 2.042,
}
REPORT_FIELDS = (
    "success_count",
    "mean_wall_ms_per_success",
    "median_wall_ms_per_success",
    "p90_wall_ms_per_success",
    "mean_wall_ms_ci95",
    "steps_one_shot",
    "steps_repair",
    "warm_replay_wall_ms",
)
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
    'ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" python -m bench.probe --execute --arms playwright_mcp,script_first,stagehand --split held-out',
    'ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" python -m bench.probe --execute --arms script_first --warm-replay',
    "python -m bench.probe --honest",
    'CU_SPEND_LEDGER="$CU_SPEND_LEDGER" ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" python -m bench.probe --execute --honest',
)


def probe_tasks(split: str | None = None) -> list[dict]:
    """Tasks for this split. The default is the three tuned probe tasks.

    CU_PROBE_ONLY_KIND (set by --only-kind) keeps tasks whose id's second word
    is that kind, for example form.
    """
    tasks = tasks_for_split(split)
    kind = os.environ.get("CU_PROBE_ONLY_KIND", "").strip().casefold()
    if kind:
        tasks = [task for task in tasks if task_kind(task["id"]) == kind]
    return tasks


def task_kind(task_id: str) -> str:
    """The task type: the second word of the task id."""
    parts = task_id.split("_")
    return parts[1].casefold() if len(parts) > 1 else ""


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


def warm_arms_for(arms: tuple[str, ...], *, honest: bool = False) -> tuple[str, ...]:
    """The proxy replay arms, plus script_first when it was selected.

    The honest probe warms script_first only. The cached-script tier is the
    warm pass. The other honest arms stay cold.
    """
    if honest:
        return (ARM_SCRIPT_FIRST,)
    if ARM_SCRIPT_FIRST in arms:
        return WARM_ARMS + (ARM_SCRIPT_FIRST,)
    return WARM_ARMS


def honest_task_reserve_usd() -> float:
    """Dollars that must still fit before another Claude task starts.

    The figure is a ceiling from the harness caps, not a measured cost.
    One call may carry the last MAX_HISTORY_PAIRS tool results, each capped
    at MAX_SNAPSHOT_CHARS, and max_tokens of output. The call count is the
    wider of the harness default and the browser-use step cap. The price is
    the recorded ledger rate. browser-use does not use the snapshot cap, so
    a task already started can still cost more than this; the next one does
    not start.
    """
    import inspect

    from bench.browser_use_arm import BROWSER_USE_MAX_STEPS
    from bench.harness import MAX_HISTORY_PAIRS, MAX_SNAPSHOT_CHARS, AnthropicClient, BenchmarkHarness

    widest = max(
        int(inspect.signature(BenchmarkHarness.__init__).parameters["max_steps"].default),
        int(BROWSER_USE_MAX_STEPS),
    )
    per_call_in = max(1, (MAX_SNAPSHOT_CHARS * MAX_HISTORY_PAIRS) // 4)
    per_call_out = int(inspect.signature(AnthropicClient.create_message).parameters["max_tokens"].default)
    return round(estimate_usd(widest * per_call_in, widest * per_call_out), 6)


def honest_run_budget(project_spent: float) -> float | None:
    """Per-run ceiling that cannot be planned past $50 or $40.

    None when the ledger is below the last recorded total, or when the
    room left under either cap is inside the per-task reserve. None means
    do not start a task. This does not write the ledger.
    """
    spent = round(float(project_spent), 6)
    if spent < LAST_RECORDED_TOTAL_USD:
        return None
    room = min(
        HONEST_PROBE_BUDGET_USD,
        round(LIFETIME_CAP_USD - spent, 6),
        round(PROJECT_BUDGET_USD - spent, 6),
    )
    if room <= honest_task_reserve_usd():
        return None
    return room


def honest_refusal(project_spent: float) -> str | None:
    """Why --execute --honest must stop before any task. None when it may start."""
    spent = round(float(project_spent), 6)
    if spent < LAST_RECORDED_TOTAL_USD:
        return (
            f"ledger total ${spent:.6f} is below the last recorded "
            f"${LAST_RECORDED_TOTAL_USD:.6f}; live execute refuses and does not "
            "write a new total"
        )
    if honest_run_budget(spent) is None:
        return (
            "remaining room under the $50 lifetime cap or the $40 project abort "
            "is inside the per-task reserve; live execute refuses before any task"
        )
    return None


def claude_budget_for(arms: tuple[str, ...]) -> float:
    """script_first's execute path stops at $2. The four-arm probe stays at $5."""
    if ARM_SCRIPT_FIRST in arms:
        return SCRIPT_FIRST_CLAUDE_BUDGET_USD
    return PROBE_CLAUDE_BUDGET_USD


def published_arm_usd(arm: str) -> float:
    """Per-task dollars from the PR #18 probe.

    An arm that probe did not measure uses the median of the three that it did.
    """
    if arm in PUBLISHED_TASK_USD:
        return PUBLISHED_TASK_USD[arm]
    ordered = sorted(PUBLISHED_TASK_USD.values())
    return ordered[len(ordered) // 2]


def expected_honest_usd(n_tasks: int, repeats: int = DEFAULT_REPEATS) -> float:
    """Ledger-rate dollars for the cold honest matrix.

    Warm replay is not included. A cache hit does not call the model.
    This multiplies the published PR #18 rates. It is not a new measurement.
    """
    per_task = sum(published_arm_usd(arm) for arm in HONEST_ARMS)
    return round(per_task * int(n_tasks) * int(repeats), 6)


def resolve_repeats(spec: int | None) -> int:
    """Default is one cold pass. Zero and negative values are refused."""
    if spec is None:
        return DEFAULT_REPEATS
    if isinstance(spec, bool) or not isinstance(spec, int) or spec < 1:
        raise ValueError(f"repeats must be an integer >= 1, got {spec!r}")
    return spec


def plan_probe(
    *,
    no_model_only: bool = False,
    warm_replay: bool = False,
    arms: str | tuple[str, ...] | list[str] | None = None,
    split: str | None = None,
    honest: bool = False,
    repeats: int | None = None,
) -> dict:
    """What --execute would run. This does not start a browser or a model."""
    chosen_repeats = resolve_repeats(repeats)
    if honest:
        chosen = HONEST_ARMS
        chosen_split = SPLIT_HONEST
        warm_replay = True
    else:
        chosen = resolve_arms(arms)
        chosen_split = resolve_task_split(split)
    try:
        spent = SpendLedger.load().running_total_usd
    except LedgerMissing:
        if chosen_split not in (SPLIT_HELDOUT2, SPLIT_HELDOUT3B, SPLIT_HELDOUT3A, SPLIT_HELDOUT3D, SPLIT_HELDOUT3C, SPLIT_HELDOUT3, SPLIT_DEV3, SPLIT_DEV4_FORM, SPLIT_VAL3):
            raise
        # Listing the new catalog needs no spend authority. Unknown is not
        # zero; live execution and existing splits retain strict ledger checks.
        spent = None
    reserve = honest_task_reserve_usd() if honest else 0.0
    room = honest_run_budget(spent) if honest else None
    if honest:
        budget = room
    else:
        budget = claude_budget_for(chosen)
    plan = {
        "execute": False,
        "mode": "no_model_only" if no_model_only else "outer_claude",
        "split": chosen_split,
        "tasks": [task["id"] for task in probe_tasks(chosen_split)],
        "arms": list(chosen),
        "available_arms": list(SELECTABLE_ARMS),
        "baseline_arms": list(BASELINE_ARMS),
        "claude_arms": [arm for arm in chosen if arm_needs_claude(arm, no_model_only=no_model_only)],
        "no_model_arms": [arm for arm in chosen if not arm_needs_claude(arm, no_model_only=no_model_only)],
        "no_model_only_arms": [arm for arm in chosen if arm in NO_MODEL_CAPABLE],
        "outer_model": ALLOWED_MODEL,
        "honest": honest,
        "claude_budget_usd": budget,
        "script_first_claude_budget_usd": SCRIPT_FIRST_CLAUDE_BUDGET_USD,
        "project_budget_usd": PROJECT_BUDGET_USD,
        "project_spent_usd": spent,
        "lifetime_cap_usd": LIFETIME_CAP_USD,
        "last_recorded_total_usd": LAST_RECORDED_TOTAL_USD,
        "huge_snapshot_chars": HUGE_SNAPSHOT_CHARS,
        "huge_snapshot_uses_body_length_only": True,
        "warm_replay": warm_replay,
        "warm_arms": list(warm_arms_for(chosen, honest=honest)),
        "repeats": chosen_repeats,
        "browser_isolation": {
            "playwright_mcp": "--isolated only (0.0.84 rejects --user-data-dir with --isolated)",
            "diff_fast_act": "proxy child --isolated only",
            "macro_replay": "proxy child --isolated only",
            "stagehand": "a unique --user-data-dir via launch_persistent_context",
            "script_first": "local Chrome via the Playwright Python API, own user-data-dir, no per-click settle",
            "endpoint": "direct fetch of the task start URL; no browser; the fetch URL is not rewritten",
            "browser_use": (
                "browser-use 1.0.3 local Chrome over CDP via Browser('chromium'); "
                "model claude-sonnet-5-5"
            ),
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
    if honest:
        plan["per_run_budget_usd"] = room
        plan["task_reserve_usd"] = reserve
        plan["execute_allowed"] = honest_refusal(spent) is None
        plan["execute_refused"] = honest_refusal(spent)
        plan["network"] = "refused"
        plan["measurements"] = None
        plan["report_fields"] = list(REPORT_FIELDS)
        plan["dev_tasks"] = list(DEV_TASK_IDS)
        plan["tuned_tasks"] = list(TUNED_PROBE_TASK_IDS)
        plan["held_out_tasks"] = list(HELD_OUT_TASK_IDS)
        plan["expected_usd"] = expected_honest_usd(len(plan["tasks"]), chosen_repeats)
        plan["expected_usd_basis"] = (
            "PR #18 published per-task ledger rate; browser_use uses the median "
            "of the three measured arms; warm replay is not included"
        )
        plan["expected_within_3_to_5"] = 3.0 <= plan["expected_usd"] <= 5.0
    return plan


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
    task_reserve_usd: float = 0.0,
    lifetime_cap_usd: float | None = None,
) -> str | None:
    """Why the next Claude task must not start. None when it may.

    task_reserve_usd is headroom that must still fit. The default 0 keeps
    the old stop, which fires once spend has reached the budget. A reserve
    above 0 refuses the task before that headroom would cross the budget,
    the $40 abort, or the lifetime cap.
    """
    reserve = float(task_reserve_usd or 0.0)
    if probe_spent_usd + reserve >= budget_usd:
        if reserve and probe_spent_usd < budget_usd:
            return (
                f"probe Claude spend ${probe_spent_usd:.2f} plus ${reserve:.2f} "
                f"reserve would reach ${budget_usd:.2f}"
            )
        return f"probe Claude spend ${probe_spent_usd:.2f} has reached ${budget_usd:.0f}"
    if project_spent_usd + reserve >= PROJECT_BUDGET_USD:
        if reserve and project_spent_usd < PROJECT_BUDGET_USD:
            return (
                f"project total ${project_spent_usd:.2f} plus ${reserve:.2f} "
                f"reserve would pass ${PROJECT_BUDGET_USD:.0f}"
            )
        return f"project total ${project_spent_usd:.2f} has reached ${PROJECT_BUDGET_USD:.0f}"
    if lifetime_cap_usd is not None and project_spent_usd + reserve >= lifetime_cap_usd:
        return (
            f"project total ${project_spent_usd:.2f} plus ${reserve:.2f} "
            f"reserve would pass the ${lifetime_cap_usd:.0f} lifetime cap"
        )
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


def _grade_claim(answer: str, claimed):
    """The claim the shared check sees. A bare answer stays an answer-only claim."""
    from bench.script_first import ClaimedEvidence

    if claimed is None:
        return ClaimedEvidence(answer=answer or "")
    if answer and not claimed.answer:
        return ClaimedEvidence(
            url=claimed.url,
            title=claimed.title,
            h1=claimed.h1,
            answer=answer,
            key_text=claimed.key_text,
            values=claimed.values,
            rejected=claimed.rejected,
        )
    return claimed


def _live_return_failure(url: str, text: str, claimed) -> str:
    """Why the script's own return is not on the live page. Empty when it is.

    URL, key text, and values are the live-page evidence check. A claim that
    returned none of them leaves the task's own check alone. Title rides along
    on the same object. UNKNOWN is not a failure here.
    """
    if claimed is None:
        return ""
    returned = bool(
        claimed.rejected
        or (claimed.key_text or "").strip()
        or any((item or "").strip() for item in claimed.values)
        or (claimed.url or "").startswith(("http://", "https://"))
    )
    if not returned:
        return ""
    from bench.script_first import FAIL, PageEvidence, evidence_verdict

    verdict = evidence_verdict({}, PageEvidence(url=url, text=text), claimed)
    if verdict.verdict == FAIL:
        return verdict.reason
    return ""


def shared_end_state(
    task: dict,
    url: str,
    text: str,
    *,
    selector_text: str = "",
    answer: str = "",
    page_text: str = "",
    claimed=None,
) -> tuple[bool | None, str]:
    """The one shared check. A missing check is None, which is not a pass.

    URL and text checks use the same strings they always have. A task whose
    end state is the live value of answer_equals_selector, and which has no
    URL or text check, is decided by that read. An empty read is a failure.
    A script return (URL, title, key text, values) is checked against that
    same page. Text that is not on the page fails the check.
    """
    claim = _grade_claim(answer, claimed)
    body = page_text or text
    checked, reason = deterministic_success(task, url, text)
    if checked is not None:
        if checked is True:
            problem = _live_return_failure(url, body, claim)
            if problem:
                return False, problem
        return checked, reason
    markers = task.get("end_markers") if isinstance(task.get("end_markers"), dict) else {}
    if not (markers or {}).get("answer_equals_selector"):
        return None, reason
    from bench.script_first import PASS, PageEvidence, evidence_verdict

    verdict = evidence_verdict(
        markers,
        PageEvidence(url=url, text=body, selector_text=selector_text),
        claim,
    )
    if verdict.verdict == PASS:
        return True, verdict.reason
    return False, verdict.reason


def shared_check_passes(
    task_id: str,
    url: str,
    text: str,
    *,
    selector: str = "",
    answer: str = "",
    claimed=None,
) -> bool:
    """True only when this task's shared check passes on the page the script left.

    None and False are not a pass. The evidence judge is a separate signal.
    """
    from bench.tasks import task_by_id

    task = task_by_id(task_id)
    if task is None:
        return False
    ok, _reason = shared_end_state(
        task,
        url,
        text or "",
        selector_text=selector,
        answer=answer,
        page_text=text or "",
        claimed=claimed,
    )
    return ok is True


def grade_arm(
    task: dict,
    url: str,
    text: str,
    *,
    evidence: str | None = None,
    evidence_reason: str = "",
    completed: bool | None = None,
    completion_reason: str = "",
    selector_text: str = "",
    answer: str = "",
    page_text: str = "",
    claimed=None,
) -> tuple[bool, str, bool | None, str]:
    """One rule for every arm. Pass only when the applicable signals agree.

    The shared check must be True. None and False are failures. When the arm
    has an evidence verdict, that verdict must be PASS. UNKNOWN is not a pass.
    `completed` is the harness completion bit for arms that have one. True is
    not a pass by itself. False blocks a pass. None means the arm has no such bit.
    """
    shared_ok, shared_reason = shared_end_state(
        task,
        url,
        text,
        selector_text=selector_text,
        answer=answer,
        page_text=page_text,
        claimed=claimed,
    )
    if shared_ok is not True:
        if shared_ok is None:
            return False, "no shared end-state check", shared_ok, shared_reason
        return False, shared_reason, shared_ok, shared_reason
    if evidence is not None and evidence != "PASS":
        if evidence == "UNKNOWN":
            reason = evidence_reason if evidence_reason.startswith("UNKNOWN") else "UNKNOWN is not success"
            return False, reason, shared_ok, shared_reason
        return False, evidence_reason or "evidence judge did not pass", shared_ok, shared_reason
    if completed is False:
        return False, completion_reason or "the run did not finish", shared_ok, shared_reason
    return True, shared_reason, shared_ok, shared_reason


def grade_observation(
    task: dict,
    url: str,
    text: str,
    *,
    selector_text: str = "",
    answer: str = "",
    completed: bool | None = None,
    completion_reason: str = "",
    run_verdict: str | None = None,
    claimed=None,
) -> tuple[bool, str, bool | None, str]:
    """The one grade for every arm.

    `text` is the page text read after the run. A task with end markers gets
    one evidence verdict from that read and the full claim. A task with no
    markers gets no marker gate. UNKNOWN is not a pass. TASK_COMPLETE is not
    a pass by itself: `completed` False still blocks, and True does not.
    `run_verdict` is script_first's own end state. It has to be PASS, and the
    shared page check has to pass too. The claim's URL, title, key text, and
    values are part of that page check.
    """
    claim = _grade_claim(answer, claimed)
    markers = task.get("end_markers") if isinstance(task.get("end_markers"), dict) else {}
    evidence = None
    evidence_reason = ""
    if markers:
        from bench.script_first import PageEvidence, evidence_verdict

        verdict = evidence_verdict(
            markers,
            PageEvidence(url=url, text=text or "", selector_text=selector_text),
            claim,
        )
        evidence = verdict.verdict
        evidence_reason = verdict.reason
    if run_verdict is not None:
        own = run_verdict if run_verdict in {"PASS", "FAIL", "UNKNOWN"} else "UNKNOWN"
        if own != "PASS":
            evidence = own
            if own == "UNKNOWN":
                if completion_reason.startswith("UNKNOWN"):
                    evidence_reason = completion_reason
                elif completion_reason:
                    evidence_reason = f"UNKNOWN: {completion_reason}"
                else:
                    evidence_reason = "UNKNOWN is not success"
            else:
                evidence_reason = completion_reason or evidence_reason or "evidence judge did not pass"
    return grade_arm(
        task,
        url,
        text or "",
        evidence=evidence,
        evidence_reason=evidence_reason,
        completed=completed,
        completion_reason=completion_reason,
        selector_text=selector_text,
        answer=claim.answer,
        page_text=text or "",
        claimed=claim,
    )


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
        success, grade_reason, checked, reason = grade_arm(task, url, page)
        if checked is None:
            grade_reason = payload.get("summary") or reason
        return {
            "arm": arm,
            "task_id": task["id"],
            "success": success,
            "success_reason": grade_reason,
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
    provider: str = "anthropic",
    model: str | None = None,
    effort: str | None = None,
) -> dict:
    """Outer model for one arm. The default is claude-sonnet-5-5."""
    from bench.harness import BenchmarkHarness, claim_from_step

    started = time.perf_counter()
    # script_first starts at one script plus a completion turn. The harness
    # adds a turn only for a repair or a refused extra script, stops at
    # SCRIPT_FIRST_HARD_CAP, and runs at most SCRIPT_FIRST_MAX_REPAIRS repair scripts.
    max_steps = SCRIPT_FIRST_MAX_CALLS if arm == ARM_SCRIPT_FIRST else 30
    openai_model = None
    openai_effort = None
    if provider == "openai":
        from bench.openai_spend import assert_effort, assert_openai_model

        openai_model = assert_openai_model(model or "")
        openai_effort = assert_effort(openai_model, effort or "")
        harness = BenchmarkHarness(
            api_key=api_key,
            model=openai_model,
            headless=headless,
            runs_dir=runs_dir,
            arm=arm,
            max_steps=max_steps,
            script_cache=script_cache if arm == ARM_SCRIPT_FIRST else None,
            provider="openai",
            effort=openai_effort,
        )
    else:
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
        last = result.steps[-1] if result.steps else None
        final_url = last.page_url if last else ""
        selector_text = last.selector_text if last else ""
        claimed_answer = last.claimed_answer if last else ""
        page_text = last.page_text if last else ""
        # The same post-run page text for every arm. The snapshot is not the check.
        graded_text = page_text
        end_state = result.end_state or ""
        # script_first has to end on its own PASS and pass the shared page
        # check. Its returned URL, title, key text, and values go into that
        # check. The other arms still cannot pass on TASK_COMPLETE alone.
        run_verdict = end_state if arm == ARM_SCRIPT_FIRST else None
        claimed = claim_from_step(last) if arm == ARM_SCRIPT_FIRST and last is not None else None
        completed = None if arm == ARM_SCRIPT_FIRST else result.success
        success, reason, substring_ok, substring_reason = grade_observation(
            task,
            final_url,
            graded_text,
            selector_text=selector_text,
            answer=claimed_answer,
            completed=completed,
            completion_reason=result.success_reason,
            run_verdict=run_verdict,
            claimed=claimed,
        )
        usd = estimate_usd(result.total_input_tokens, result.total_output_tokens)
        row = {
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
            "claimed_answer": claimed_answer,
            "final_url": final_url,
            "final_title": last.page_title if last else "",
            "expected_value": selector_text,
        }
        if arm == ARM_SCRIPT_FIRST:
            row["scripts"] = [
                step.tool_args["code"]
                for step in result.steps
                if step.tool_name == "run_script"
                and isinstance(step.tool_args, dict)
                and isinstance(step.tool_args.get("code"), str)
            ]
            row["repair_sent"] = result.repair_sent
            row["repair_reply"] = result.repair_reply
            row["script_turns"] = result.script_turns
            # Every script's self-check inputs and verdict, for offline replay.
            row["self_checks"] = [step.self_check for step in result.steps if step.self_check]
            row["task_description"] = task.get("description") or ""
            row["start_url"] = task.get("start_url") or ""
            if result.strategy:
                row["strategy"] = result.strategy
                row["strategy_reason"] = result.strategy_reason
                row["strategy_steps"] = [
                    {"action": step.tool_args, "result": step.snapshot_text}
                    for step in result.steps if step.tool_name == "form_step"
                ]
        if provider == "openai":
            from bench.openai_spend import price_usd

            row["usd"] = price_usd(
                openai_model or "",
                result.total_input_tokens,
                result.total_output_tokens,
                result.total_cached_tokens,
                result.total_cache_write_30m_tokens,
                result.total_cache_write_12h_tokens,
            )
            row["claude"] = False
            row["provider"] = "openai"
            row["model"] = openai_model
            row["effort"] = openai_effort
            row["cached_tokens"] = result.total_cached_tokens
            row["cache_write_30m_tokens"] = result.total_cache_write_30m_tokens
            row["cache_write_12h_tokens"] = result.total_cache_write_12h_tokens
        return row
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
    task_reserve_usd: float = 0.0,
    lifetime_cap_usd: float | None = None,
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
        blocked = claude_block_reason(
            probe_spent,
            ledger.running_total_usd,
            budget_usd=budget_usd,
            task_reserve_usd=task_reserve_usd,
            lifetime_cap_usd=lifetime_cap_usd,
        )
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


async def _run_browser_use(
    task: dict,
    *,
    headless: bool,
    api_key: str,
    probe_spent: float,
    ledger: SpendLedger,
    budget_usd: float,
    task_reserve_usd: float = 0.0,
    lifetime_cap_usd: float | None = None,
) -> tuple[dict, float]:
    """browser-use 1.0 on local Chrome. The outer Playwright loop is not used."""
    if not api_key:
        return (
            empty_row(ARM_BROWSER_USE, task["id"], reason="ANTHROPIC_API_KEY unset"),
            probe_spent,
        )
    blocked = claude_block_reason(
        probe_spent,
        ledger.running_total_usd,
        budget_usd=budget_usd,
        task_reserve_usd=task_reserve_usd,
        lifetime_cap_usd=lifetime_cap_usd,
    )
    if blocked:
        return empty_row(ARM_BROWSER_USE, task["id"], reason=blocked), probe_spent
    from bench.browser_use_arm import run_browser_use_task

    row = await run_browser_use_task(task, api_key=api_key, headless=headless)
    if row.get("claude") and (row.get("input_tokens") or row.get("output_tokens")):
        ledger.record_task(
            run_id="probe",
            task_id=f"{ARM_BROWSER_USE}:{row['task_id']}",
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
    task_reserve_usd: float = 0.0,
    lifetime_cap_usd: float | None = None,
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
            task_reserve_usd=task_reserve_usd,
            lifetime_cap_usd=lifetime_cap_usd,
        )
    if arm == ARM_BROWSER_USE:
        return await _run_browser_use(
            task,
            headless=headless,
            api_key=api_key,
            probe_spent=probe_spent,
            ledger=ledger,
            budget_usd=budget_usd,
            task_reserve_usd=task_reserve_usd,
            lifetime_cap_usd=lifetime_cap_usd,
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
    blocked = claude_block_reason(
        probe_spent,
        ledger.running_total_usd,
        budget_usd=budget_usd,
        task_reserve_usd=task_reserve_usd,
        lifetime_cap_usd=lifetime_cap_usd,
    )
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


class ProbeRefused(RuntimeError):
    """The honest probe stops before a browser or a model call."""


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[mid])
    return (float(ordered[mid - 1]) + float(ordered[mid])) / 2


def _percentile(values: list[float], pct: float) -> float | None:
    """Linear percentile. pct is 0-100. An empty sample is None."""
    if not values:
        return None
    ordered = sorted(float(item) for item in values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * (pct / 100.0)
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    weight = rank - low
    return ordered[low] * (1.0 - weight) + ordered[high] * weight


def _p90(values: list[float]) -> float | None:
    return _percentile(values, 90)


def _mean_ci95(values: list[float]) -> list[float] | None:
    """95% Student-t interval of the mean. None when the sample has one point."""
    n = len(values)
    if n < 2:
        return None
    mean = sum(values) / n
    var = sum((item - mean) ** 2 for item in values) / (n - 1)
    margin = _T_95.get(n - 1, 1.96) * ((var ** 0.5) / (n ** 0.5))
    return [round(mean - margin, 6), round(mean + margin, 6)]


def _wall_ms(row: dict) -> float | None:
    value = row.get("wall_ms")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _as_int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def row_took_repair(row: dict) -> bool:
    """A second script, a cache patch, or any step after the first."""
    if row.get("tier") == "patched":
        return True
    if _as_int(row.get("repairs")) > 0:
        return True
    if _as_int(row.get("model_calls")) >= 2:
        return True
    return _as_int(row.get("steps")) >= 2


def _attempted(rows: list[dict]) -> list[dict]:
    return [row for row in rows if not row.get("skipped")]


def _walls(rows: list[dict], *, successes_only: bool) -> list[float]:
    found = []
    for row in rows:
        if successes_only and not row.get("success"):
            continue
        wall = _wall_ms(row)
        if wall is not None:
            found.append(wall)
    return found


def arm_report(rows: list[dict], arms: tuple[str, ...] | list[str]) -> dict:
    """Per-arm figures from rows already recorded. Missing runs stay null.

    Nothing here is filled in from a previous probe. An arm with no attempted
    task has null success and wall fields. Warm times are null when that arm
    had no warm pass.
    """
    report = {}
    for arm in arms:
        cold = [row for row in rows if row.get("arm") == arm and row.get("pass", "cold") == "cold"]
        attempted = _attempted(cold)
        successes = [row for row in attempted if row.get("success")]
        walls = _walls(successes, successes_only=False)
        if attempted:
            one_shot = [row for row in attempted if not row_took_repair(row)]
            repair = [row for row in attempted if row_took_repair(row)]
            steps = {
                "one_shot": [_as_int(row.get("steps")) for row in one_shot],
                "repair": [_as_int(row.get("steps")) for row in repair],
            }
            success_count: int | None = len(successes)
        else:
            steps = {"one_shot": None, "repair": None}
            success_count = None
        warm = [row for row in rows if row.get("arm") == arm and row.get("pass") == "warm"]
        warm_attempted = _attempted(warm)
        if not warm:
            warm_report = {
                "ran": False,
                "success_count": None,
                "wall_ms": None,
                "mean_wall_ms_per_success": None,
                "median_wall_ms_per_success": None,
            }
        elif not warm_attempted:
            warm_report = {
                "ran": True,
                "success_count": None,
                "wall_ms": None,
                "mean_wall_ms_per_success": None,
                "median_wall_ms_per_success": None,
            }
        else:
            warm_walls = _walls(warm_attempted, successes_only=False)
            warm_ok = _walls(warm_attempted, successes_only=True)
            warm_report = {
                "ran": True,
                "success_count": sum(1 for row in warm_attempted if row.get("success")),
                "wall_ms": warm_walls,
                "mean_wall_ms_per_success": _mean(warm_ok),
                "median_wall_ms_per_success": _median(warm_ok),
            }
        report[arm] = {
            "success_count": success_count,
            "attempted": len(attempted),
            "mean_wall_ms_per_success": _mean(walls) if attempted else None,
            "median_wall_ms_per_success": _median(walls) if attempted else None,
            "p90_wall_ms_per_success": _p90(walls) if attempted else None,
            "mean_wall_ms_ci95": _mean_ci95(walls) if attempted else None,
            "steps": steps,
            "warm_replay": warm_report,
        }
        efforts = []
        for row in cold + warm:
            name = row.get("effort")
            if isinstance(name, str) and name and name not in efforts:
                efforts.append(name)
        if efforts:
            report[arm]["effort"] = efforts
    return report


async def execute_probe(
    *,
    headless: bool = True,
    spend_path: Path | None = None,
    runs_dir: Path | None = None,
    no_model_only: bool = False,
    warm_replay: bool = False,
    arms: tuple[str, ...] | None = None,
    endpoint_opener=None,
    split: str | None = None,
    honest: bool = False,
    provider: str = "anthropic",
    model: str | None = None,
    effort: str | None = None,
    sweep: bool = False,
    one_task: bool = False,
    repeats: int = DEFAULT_REPEATS,
) -> list[dict]:
    """Run the matrix. Claude arms are skipped when the key is missing or the cap is hit.

    The default is the competitive outer-Claude matrix, including the two
    proxy arms. no_model_only keeps those two on decide() and still sends
    playwright_mcp and stagehand through Claude when a key is set.
    --honest refuses before any task when the ledger is below the last
    recorded total, the key is unset, or the reserve no longer fits under
    the run ceiling, the $40 abort, or the $50 lifetime cap.
    """
    if provider == "openai":
        from bench.openai_run import execute_openai_probe

        if honest:
            chosen = HONEST_ARMS
            chosen_split = SPLIT_HONEST
        else:
            chosen = resolve_arms(arms)
            chosen_split = resolve_task_split(split)
        return await execute_openai_probe(
            arms=chosen,
            split=chosen_split,
            sweep=sweep,
            model=model,
            effort=effort,
            one_task=one_task,
            headless=headless,
            spend_path=spend_path,
            runs_dir=runs_dir,
            no_model_only=no_model_only,
            warm_replay=warm_replay,
            honest=honest,
        )
    if honest:
        chosen = HONEST_ARMS
        chosen_split = SPLIT_HONEST
        warm_replay = True
        no_model_only = False
    else:
        chosen = resolve_arms(arms)
        chosen_split = resolve_task_split(split)
    ledger = SpendLedger.load(spend_path)
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    task_reserve = 0.0
    lifetime_cap = None
    if honest:
        if round(ledger.running_total_usd, 6) < LAST_RECORDED_TOTAL_USD:
            raise LedgerBelowRecorded(ledger.running_total_usd)
        if not api_key:
            raise ProbeRefused("ANTHROPIC_API_KEY unset. Refusing before any browser or model call.")
        room = honest_run_budget(ledger.running_total_usd)
        refusal = honest_refusal(ledger.running_total_usd)
        if room is None or refusal is not None:
            raise ProbeRefused(refusal or "Refusing before any task.")
        budget_usd = room
        task_reserve = honest_task_reserve_usd()
        lifetime_cap = LIFETIME_CAP_USD
    else:
        budget_usd = claude_budget_for(chosen)
    destination = runs_dir or RUNS_DIR
    destination.mkdir(parents=True, exist_ok=True)
    probe_spent = 0.0
    rows: list[dict] = []
    tasks = probe_tasks(chosen_split)
    script_cache = None
    if warm_replay and ARM_SCRIPT_FIRST in chosen:
        from bench.script_cache import ScriptCache

        # A new file per probe: the cold pass starts empty and the warm pass reads it.
        started = datetime.now().strftime("%Y%m%d_%H%M%S")
        script_cache = ScriptCache(destination / f"script_cache_{started}.json")

    async def take(arm: str, task: dict, phase: str, cache, repeat_index: int) -> None:
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
            script_cache=cache,
            endpoint_opener=endpoint_opener,
            task_reserve_usd=task_reserve,
            lifetime_cap_usd=lifetime_cap,
        )
        row["pass"] = phase
        row["repeat"] = repeat_index
        rows.append(row)

    for repeat_index in range(repeats):
        # Only the first cold pass may fill the cache the warm pass reads.
        # A later repeat is a fresh model run.
        cache = script_cache if repeat_index == 0 else None
        for task in tasks:
            for arm in chosen:
                await take(arm, task, "cold", cache, repeat_index)
    if warm_replay:
        # Same cache file as the first cold pass. Do not delete it between passes.
        for task in tasks:
            for arm in warm_arms_for(chosen, honest=honest):
                if arm not in chosen:
                    continue
                await take(arm, task, "warm", script_cache, 0)
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
        handle.write(json.dumps({"kind": "arm_report", "report": arm_report(rows, chosen)}) + "\n")
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
            "A selection that includes it stops Claude at $2. "
            "browser_use is the browser-use 1.0 local Chrome baseline "
            "beside playwright_mcp and stagehand."
        ),
    )
    parser.add_argument(
        "--split",
        default=SPLIT_PROBE,
        help=(
            "Task split. probe is the three tuned tasks and the default. "
            "dev is the wider tune set. held-out is the scored set. "
            "heldout2 is the independent twenty-task set. "
            "heldout3a and heldout3b are further independent thirty-task sets. "
            "heldout3d is a further independent forty-task set. "
            "heldout3c is a further independent forty-task set. "
            "heldout3 is a, b, c and d together, the frozen test set. "
            "dev3 is a forty-task public tune set. "
            "dev4form is the form specialist's twelve fresh form tasks. "
            "val3 is the forty-task validation set, an aggregate-only gate. "
            "Printing the plan does not run it."
        ),
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=DEFAULT_REPEATS,
        help=(
            "Cold repeats per task. The default is 1. "
            "The report adds the mean, median, p90, and a 95%% confidence interval. "
            "Not a live run by itself."
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
    parser.add_argument(
        "--honest",
        action="store_true",
        help=(
            "The live comparison: playwright_mcp, script_first cold then warm, "
            "stagehand, and browser_use, on the held-out scored set. "
            "The dev tasks are not scored. "
            "Stops before a task can cross the $8 ceiling, the $40 abort, or the $50 cap. "
            "Without --execute, prints the plan and does not use the network."
        ),
    )
    parser.add_argument(
        "--provider",
        default="anthropic",
        help="anthropic is the Claude path. openai runs the computer-use model under test.",
    )
    parser.add_argument(
        "--model",
        default="",
        help="OpenAI model. gpt-6.1-sol or gpt-6-luna. The Claude path stays claude-sonnet-5-5.",
    )
    parser.add_argument(
        "--effort",
        default="",
        help="OpenAI reasoning effort: low, medium, or high. xhigh only when that model accepts it.",
    )
    parser.add_argument(
        "--sweep-effort",
        action="store_true",
        help="Run gpt-6-luna and gpt-6.1-sol at every accepted effort. One task. Caps at $5 and $15.",
    )
    parser.add_argument(
        "--sweep-task",
        action="store_true",
        help="With one OpenAI model, use the one-task sweep subset instead of the full Claude split.",
    )
    parser.add_argument(
        "--only-kind",
        default="",
        help="Keep only tasks of this type (the second word of the task id), for example form.",
    )
    args = parser.parse_args(argv)
    if args.only_kind:
        os.environ["CU_PROBE_ONLY_KIND"] = args.only_kind
    from bench.openai_run import plan_openai_probe, resolve_openai_request
    from bench.openai_spend import EffortNotAllowed, OpenAIModelNotAllowed, PriceUnknown

    try:
        request = resolve_openai_request(
            provider=args.provider,
            model=args.model,
            effort=args.effort,
            sweep=args.sweep_effort,
            one_task=args.sweep_task,
        )
        chosen_repeats = resolve_repeats(args.repeats)
        if args.honest:
            chosen = HONEST_ARMS
            chosen_split = SPLIT_HONEST
            warm = True
        else:
            chosen = resolve_arms(args.arms)
            chosen_split = resolve_task_split(args.split)
            warm = args.warm_replay
    except (ValueError, OpenAIModelNotAllowed, EffortNotAllowed, PriceUnknown) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    try:
        if request["provider"] == "openai":
            if not args.execute:
                print(
                    json.dumps(
                        plan_openai_probe(
                            arms=chosen,
                            split=chosen_split,
                            sweep=request["sweep"],
                            model=request.get("model") or "",
                            effort=request.get("effort") or "",
                            one_task=request["one_task"],
                            no_model_only=args.no_model_only,
                            warm_replay=warm,
                            honest=args.honest,
                        ),
                        indent=2,
                    )
                )
                return 0
            rows = asyncio.run(
                execute_probe(
                    headless=not args.no_headless,
                    no_model_only=args.no_model_only,
                    warm_replay=warm,
                    arms=chosen,
                    split=chosen_split,
                    honest=args.honest,
                    provider="openai",
                    model=request.get("model"),
                    effort=request.get("effort"),
                    sweep=request["sweep"],
                    one_task=request["one_task"],
                    repeats=chosen_repeats,
                )
            )
        elif not args.execute:
            print(
                json.dumps(
                    plan_probe(
                        no_model_only=args.no_model_only,
                        warm_replay=warm,
                        arms=chosen,
                        split=chosen_split,
                        honest=args.honest,
                        repeats=chosen_repeats,
                    ),
                    indent=2,
                )
            )
            return 0
        else:
            rows = asyncio.run(
                execute_probe(
                    headless=not args.no_headless,
                    no_model_only=args.no_model_only,
                    warm_replay=warm,
                    arms=chosen,
                    split=chosen_split,
                    honest=args.honest,
                    repeats=chosen_repeats,
                )
            )
    except (LedgerMissing, LedgerBelowRecorded, ProbeRefused, OpenAIModelNotAllowed, EffortNotAllowed, PriceUnknown) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    spent = sum(row["usd"] for row in rows)
    print(f"probe rows: {len(rows)}")
    label = "probe openai usd" if request["provider"] == "openai" else "probe claude usd"
    print(f"{label}: {spent:.4f}")
    if warm:
        print(json.dumps({"cold": cold_summary(rows), "warm": warm_summary(rows)}, indent=2))
    print(json.dumps({"report": arm_report(rows, chosen)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
