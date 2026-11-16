"""Opt-in, bounded script segments. Expectations are constraints, never a judge."""

from __future__ import annotations

import asyncio
import json
import os
import time
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from bench.script_first import EvidenceVerdict, TaskStep

SEG_MAX_SCRIPTS = 6
SEG_MAX_CALLS = 8
SEG_MAX_LOOKS = 2
SEG_WALL_S = 45.0
SEG_WAIT_S = 3.0
SEG_WAIT_TASK_S = 10.0
SEG_POLL_S = 0.1
SEG_MAX_CHECKS = 4
# Leave time for the mandatory post-tail read even when readiness times out.
SEG_RECHECK_S = 0.1


def segments_enabled() -> bool:
    return os.environ.get("CU_SF_SEGMENTS") == "1" and os.environ.get("CU_SF_REPAIR") != "blind"


def _valid_text(value: Any) -> bool:
    return isinstance(value, str) and 1 <= len(value) <= 200 and bool(value.strip())


def parse_segment_args(args: Any) -> tuple[bool, list[dict], list[str]]:
    """Validate before any browser action; preserve only supported check fields."""
    if not isinstance(args, dict):
        return True, [], ["arguments must be an object"]
    errors: list[str] = []
    final = args.get("final", True)
    if type(final) is not bool:
        errors.append("final must be a boolean")
        final = True
    raw = args.get("expect", [])
    if not isinstance(raw, list) or len(raw) > SEG_MAX_CHECKS:
        return final, [], errors + [f"expect must be an array of at most {SEG_MAX_CHECKS} checks"]
    checks: list[dict] = []
    for index, check in enumerate(raw, 1):
        if not isinstance(check, dict) or len(check) != 1:
            errors.append(f"expect {index} must have exactly one supported key")
            continue
        kind, arg = next(iter(check.items()))
        valid = False
        if kind in {"url_contains", "text", "gone_text"}:
            valid = _valid_text(arg)
        elif kind == "control" and isinstance(arg, dict):
            valid = (
                set(arg) <= {"name", "role"}
                and _valid_text(arg.get("name"))
                and ("role" not in arg or _valid_text(arg["role"]))
            )
        if not valid:
            errors.append(f"expect {index} is invalid (supported keys: url_contains, text, gone_text, control)")
            continue
        checks.append({kind: dict(arg) if isinstance(arg, dict) else arg})
    return final, checks, errors


def segment_request_key(args: Any) -> str:
    """Keep literal whitespace and readiness/finality changes in the repeat key."""
    final, checks, errors = parse_segment_args(args)
    code = (args.get("code") or args.get("script") or "") if isinstance(args, dict) else ""
    return json.dumps(
        [code.strip() if isinstance(code, str) else "", final, checks, errors],
        sort_keys=True, ensure_ascii=False,
    )


def segment_made_progress(previous: dict | None, current: dict, receipt: dict) -> bool:
    """Bound continuation without mistaking same-URL interaction for a stall.

    Issued mutations are a reason to permit another observation, not proof of
    task completion. Script/call budgets still bound unchanged-state actions.
    """
    from bench.script_first import script_made_progress

    if script_made_progress(previous, current):
        return True
    if receipt["ok"] and receipt["mutations_run"]:
        return True
    fields = ("url", "title", "h1", "text", "controls")
    return previous is not None and any(previous.get(key) != current.get(key) for key in fields)


def expect_schema() -> dict:
    """A fresh schema so callers cannot mutate later tool definitions."""
    text = {"type": "string", "minLength": 1, "maxLength": 200, "pattern": r"\S"}
    variants = []
    for key in ("url_contains", "text", "gone_text", "control"):
        value = dict(text) if key != "control" else {
            "type": "object",
            "properties": {"name": dict(text), "role": dict(text)},
            "required": ["name"],
            "additionalProperties": False,
        }
        variants.append({
            "type": "object", "properties": {key: value}, "required": [key], "additionalProperties": False,
        })
    return {"type": "array", "maxItems": SEG_MAX_CHECKS, "items": {"oneOf": variants}}


def _check_result(check: dict, *, ok: bool = False, waited_ms: int = 0, error: str = "") -> dict:
    kind, value = next(iter(check.items()))
    arg = json.dumps(value, sort_keys=True, ensure_ascii=False) if isinstance(value, dict) else value
    result = {"kind": kind, "arg": arg, "ok": ok, "waited_ms": waited_ms}
    if error:
        result["error"] = error[:300]
    return result


_VISIBLE_COUNT_JS = """nodes => nodes.filter(el => {
  if (!el.getClientRects().length || el.closest('[hidden], [aria-hidden="true"], [inert]')) return false;
  const style = getComputedStyle(el);
  return style.display !== "none" && style.visibility !== "hidden" && style.visibility !== "collapse";
}).length"""


async def _read_check(page: Any, check: dict) -> bool:
    kind, arg = next(iter(check.items()))
    if kind == "url_contains":
        return arg in page.url
    if kind in {"text", "gone_text"}:
        # Do not use the evidence reader: it swallows read errors as empty text,
        # which would incorrectly satisfy an absence check.
        text = await page.locator("body").inner_text()
        if not isinstance(text, str):
            raise ValueError("page text was not read")
        found = arg in text
        return found if kind == "text" else not found
    locator = (
        page.get_by_role(arg["role"], name=arg["name"], exact=True)
        if "role" in arg else page.get_by_text(arg["name"], exact=True)
    )
    # Count visible exact matches, rather than letting a hidden duplicate veto
    # a unique visible control or accepting the first of two visible matches.
    return await locator.evaluate_all(_VISIBLE_COUNT_JS) == 1


async def read_checks(page: Any, checks: list[dict], budget_s: float) -> list[dict]:
    """One simultaneous, bounded read. Errors (including absence reads) fail closed."""
    deadline = time.perf_counter() + max(0.0, budget_s)

    async def read(check: dict) -> dict:
        remaining = deadline - time.perf_counter()
        if remaining <= 0:
            return _check_result(check, error="check budget exhausted")
        try:
            ok = await asyncio.wait_for(_read_check(page, check), timeout=remaining)
            return _check_result(check, ok=ok)
        except Exception as exc:
            return _check_result(check, error=str(exc) or type(exc).__name__)

    return list(await asyncio.gather(*(read(check) for check in checks)))


async def poll_checks(page: Any, checks: list[dict], budget_s: float) -> list[dict]:
    """All checks share one deadline and must hold in the same poll round."""
    start = time.perf_counter()
    deadline = start + max(0.0, min(SEG_WAIT_S, budget_s))
    while True:
        results = await read_checks(page, checks, max(0.0, deadline - time.perf_counter()))
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        for result in results:
            result["waited_ms"] = elapsed_ms
        remaining = deadline - time.perf_counter()
        if all(result["ok"] for result in results) or remaining <= 0:
            return results
        await asyncio.sleep(min(SEG_POLL_S, remaining))


def _mutation_op(step: TaskStep) -> str:
    if step.helper is not None:
        return step.helper.op
    action = step.action
    if action is None:
        return ""
    if action.finder == "keyboard":
        return "key"
    return {"selectOption": "select", "goBack": "back"}.get(action.op, action.op) if action.op in {
        "click", "fill", "press", "check", "uncheck", "selectOption", "goBack",
    } else ""


def mutations_run(steps: Sequence[TaskStep], done: int) -> list[dict]:
    return [
        {"index": index, "op": op}
        for index, step in enumerate(steps[:done], 1)
        if (op := _mutation_op(step))
    ]


def build_receipt(
    *,
    segment: int = 1,
    final: bool = True,
    ok: bool = False,
    steps: Sequence[TaskStep] = (),
    done: int = 0,
    attempted: int = 0,
    error: str = "",
    checks: Sequence[dict] = (),
    url_before: str = "",
    url_after: str = "",
    wait_left: float = SEG_WAIT_TASK_S,
    looks: int = 0,
    effects_uncertain: bool = False,
    steps_run: int | None = None,
    steps_total: int | None = None,
    failed_step: dict | None = None,
    wait_ms_left: int | None = None,
    segments_left: int | None = None,
    looks_left: int | None = None,
) -> dict:
    """Execution facts only: no page body or returned claims in a receipt."""
    done = done if steps_run is None else steps_run
    total = len(steps) if steps_total is None else steps_total
    if failed_step is None and not ok and done < attempted <= len(steps):
        failed_step = {
            "index": attempted,
            "source": " ".join(steps[attempted - 1].source.split())[:200],
            "error": " ".join(error.split())[:300],
        }
    issued = steps[:max(done, attempted)]
    uncertain = effects_uncertain or any(step.kind == "evaluate" for step in issued)
    if done < attempted <= len(steps):
        uncertain = uncertain or bool(_mutation_op(steps[attempted - 1])) or steps[attempted - 1].kind == "goto"
    return {
        "segment": segment,
        "final": final,
        "ok": bool(ok and done == total and all(check.get("ok") is True for check in checks)),
        "steps_run": done,
        "steps_total": total,
        "failed_step": failed_step,
        "mutations_run": mutations_run(steps, done),
        "url_before": url_before,
        "url_after": url_after,
        "moved": url_before != url_after,
        "checks": list(checks),
        "wait_ms_left": max(0, int(wait_left * 1000) if wait_ms_left is None else wait_ms_left),
        "segments_left": max(0, SEG_MAX_SCRIPTS - segment if segments_left is None else segments_left),
        "looks_left": max(0, SEG_MAX_LOOKS - looks if looks_left is None else looks_left),
        "effects_uncertain": bool(uncertain),
    }


def valid_receipt(receipt: Any) -> bool:
    if not isinstance(receipt, dict):
        return False
    for key in ("segment", "steps_run", "steps_total", "wait_ms_left", "segments_left", "looks_left"):
        if type(receipt.get(key)) is not int or receipt[key] < 0:
            return False
    if not 1 <= receipt["segment"] <= SEG_MAX_SCRIPTS or receipt["steps_run"] > receipt["steps_total"]:
        return False
    if any(type(receipt.get(key)) is not bool for key in ("final", "ok", "moved", "effects_uncertain")):
        return False
    if any(not isinstance(receipt.get(key), str) for key in ("url_before", "url_after")):
        return False
    if receipt["moved"] != (receipt["url_before"] != receipt["url_after"]):
        return False
    if "failed_step" not in receipt or not isinstance(receipt.get("mutations_run"), list):
        return False
    failure = receipt["failed_step"]
    if failure is not None and (
        not isinstance(failure, dict) or type(failure.get("index")) is not int
        or not isinstance(failure.get("source"), str) or not isinstance(failure.get("error"), str)
        or not receipt["steps_run"] < failure["index"] <= receipt["steps_total"]
        or len(failure["source"]) > 200 or len(failure["error"]) > 300
    ):
        return False
    for mutation in receipt["mutations_run"]:
        if (
            not isinstance(mutation, dict) or type(mutation.get("index")) is not int
            or not 1 <= mutation["index"] <= receipt["steps_run"]
            or mutation.get("op") not in {"click", "fill", "press", "check", "uncheck", "select", "key", "back"}
        ):
            return False
    checks = receipt.get("checks")
    if not isinstance(checks, list) or len(checks) > SEG_MAX_CHECKS:
        return False
    for check in checks:
        if isinstance(check, dict) and check.get("kind") == "invalid":
            if (
                receipt["ok"] or check.get("ok") is not False
                or not _valid_text(check.get("arg"))
                or type(check.get("waited_ms")) is not int or check["waited_ms"] < 0
            ):
                return False
            continue
        if (
            not isinstance(check, dict) or check.get("kind") not in {"url_contains", "text", "gone_text", "control"}
            or not isinstance(check.get("arg"), str)
            or type(check.get("ok")) is not bool or type(check.get("waited_ms")) is not int or check["waited_ms"] < 0
        ):
            return False
        arg = check["arg"]
        if check["kind"] == "control":
            try:
                arg = json.loads(arg)
            except (ValueError, TypeError):
                return False
        if parse_segment_args({"expect": [{check["kind"]: arg}]})[2]:
            return False
    return True


def gate_final(verdict: EvidenceVerdict, receipt: Any) -> EvidenceVerdict:
    """Only downgrade. Expectations cannot supply semantic correctness."""
    from bench.script_first import EvidenceVerdict, FAIL

    if verdict.verdict == FAIL:
        return verdict
    reason = ""
    if not valid_receipt(receipt):
        reason = "missing or malformed segment receipt"
    elif receipt["final"] is not True:
        reason = "non-final segment is not completion"
    elif (
        not receipt["ok"] or receipt["failed_step"] is not None
        or receipt["steps_run"] != receipt["steps_total"] or receipt["steps_total"] == 0
    ):
        reason = "segment execution or expectation failed"
    elif any(check["ok"] is not True for check in receipt["checks"]):
        reason = "segment expectation failed"
    return EvidenceVerdict(FAIL, reason, verdict.scored_url) if reason else verdict


def segment_continue_text(receipt: dict, snapshot: str) -> str:
    from bench.script_first import SNAPSHOT_BEGIN, SNAPSHOT_END

    return "\n".join([
        f"SEGMENT_CONTINUE: segment {receipt.get('segment')} ran; the task is not complete.",
        "Continue from the current page. Keep completed actions; do not replay them.",
        SNAPSHOT_BEGIN, snapshot or "(the page could not be read)", SNAPSHOT_END,
        "Send the next run_script; final:false is allowed while work remains. "
        "Use final:true only when the task is finished, with evidence from this page.",
    ])


def segment_repair_note(receipt: dict) -> str:
    failure = receipt.get("failed_step")
    failed = f" Step {failure['index']} failed." if isinstance(failure, dict) and "index" in failure else ""
    checks = [check.get("kind", "invalid") for check in receipt.get("checks", []) if check.get("ok") is not True]
    if checks:
        failed += " Failed checks: " + ", ".join(checks) + "."
    if receipt.get("wait_ms_left") == 0:
        failed += " The task's expectation-read budget is exhausted."
    return (
        f"SEGMENT_RECOVERY: {receipt.get('steps_run', 0)} completed steps are retained.{failed} "
        "A failed input may already have taken effect, and evaluate code may have changed the page. "
        "Inspect the current snapshot before deciding what to retry; do not replay completed mutations "
        "or unconditionally restart. Continue locally; final:false is allowed while work remains."
    )
