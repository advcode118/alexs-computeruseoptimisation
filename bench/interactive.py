"""Owned interactive stage: short script segments on the same page, after the script stage is rejected.

One model call sends one short segment. The segment runs through the same
ScriptFirstClient.call_tool("run_script") executor and ActionGate as the script
stage, and is judged by the same runtime verdict and precision check. After each
segment the stage evaluates the goal checkpoints and reads a fresh page snapshot
(plus a screenshot, only for visual task profiles). Hard cap: four model calls.
A gate block ends the task as needing approval. No answer key is read here.
"""

from __future__ import annotations

import base64

INTERACTIVE_MAX_CALLS = 4
SEGMENT_MAX_STEPS = 6

INTERACTIVE_PROMPT = f"""You are a browser automation agent finishing a task in a browser that is already open.
A first scripted attempt did not confirm the result. You now work in short segments.

Rules:
- Each reply calls run_script once with a short segment of at most {SEGMENT_MAX_STEPS} lines, or calls task_failed({{reason}}).
- After each segment you see the live page (url, title, headings, forms, controls, links, text). Use the names shown there; do not guess selectors.
- Allowed lines: page.goto("https://..."), page.locator, page.getByRole, page.getByLabel, page.getByText, page.getByPlaceholder (with .first()/.nth()), cu.click("name"), cu.fill("name", "text"), cu.press("name", "Enter"), and page.evaluate(() => {{ ... }}).
- Do not call page.waitForTimeout, page.waitForLoadState, page.waitForSelector, or networkidle.
- When the page holds the asked value, end that segment with the evidence object:
  page.evaluate(() => ({{url: location.href, title: document.title, h1: document.querySelector("h1")?.innerText, key_text: "", values: [], answer: ""}}))
  Put a phrase that is on the page in key_text and the asked value, copied exactly, in answer. The run stops when the runner accepts it.
- Buying, paying, deleting, sending, confirming, subscribing and submitting data are blocked by the runner. A blocked action ends the task as needing the user's approval. Do not try another way around it.
- You have at most {INTERACTIVE_MAX_CALLS} replies in total."""

_SEGMENT_TOOL = {
    "name": "run_script",
    "description": (
        f"Run one short segment of at most {SEGMENT_MAX_STEPS} lines on the open page. The browser stays where the "
        "segment leaves it, and the next reply sees the live page. End the segment that finishes the task with "
        "the page.evaluate evidence object."
    ),
    "input_schema": {
        "type": "object",
        "properties": {"code": {"type": "string", "description": "A short Playwright segment."}},
        "required": ["code"],
    },
}
_FAILED_TOOL = {
    "name": "task_failed",
    "description": "Stop the task when it cannot be completed and explain why.",
    "input_schema": {"type": "object", "properties": {"reason": {"type": "string"}}, "required": ["reason"]},
}
TOOLS = [_SEGMENT_TOOL, _FAILED_TOOL]
_TOKEN_KEYS = ("input_tokens", "output_tokens", "cached_tokens", "cache_write_30m_tokens", "cache_write_12h_tokens")


async def _screenshot_block(page) -> dict | None:
    shoot = getattr(page, "screenshot", None)
    if not callable(shoot):
        return None
    try:
        data = await shoot(type="jpeg", quality=60, full_page=False)
    except Exception:
        return None
    return {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                        "data": base64.b64encode(data).decode("ascii")}}


def _drop_old_images(messages: list[dict]) -> None:
    for message in messages:
        content = message.get("content")
        if isinstance(content, list):
            for index, block in enumerate(content):
                if isinstance(block, dict) and block.get("type") == "image":
                    content[index] = {"type": "text", "text": "(older screenshot dropped)"}


def _unmet(checks: list[dict]) -> str:
    missing = [f'{c["kind"]} {c["value"]!r}' if c["value"] else c["kind"] for c in checks if not c["passed"]]
    return ("Goal checks not met yet: " + "; ".join(missing) + ".") if missing else "All goal checks are met."


async def run_interactive(task, *, harness, profile, checkpoints, reason, visited=(), earlier=(),
                          max_calls: int = INTERACTIVE_MAX_CALLS) -> dict:
    """Up to max_calls segments on harness.mcp_client's page. Returns the stage outcome and its usage."""
    from bench.cascade import handoff_note, precision_check
    from bench.harness import page_url_from_result, self_check_record
    from bench.openai_spend import PriceUnknown
    from bench.recovery import evaluate_checkpoints
    from bench.script_first import (
        PASS, SNAPSHOT_BEGIN, SNAPSHOT_END, ScriptError, UNKNOWN, _claimed_note, _page_url,
        claimed_from_payload, drop_old_snapshots, failed_step_note, model_visible_script_result,
        parse_task_script, script_runtime_verdict, task_asks_value,
    )

    client, model = harness.mcp_client, harness.anthropic
    gate = client.gate
    description, start_url = task["description"], task["start_url"]
    asks_value = task_asks_value(description)
    visual = getattr(profile, "modality", "") == "visual"
    tool_choice = "required" if getattr(harness, "provider", "") == "openai" else {"type": "any"}
    earlier_payloads = [p for p in earlier if isinstance(p, dict)]
    out = {key: 0 for key in _TOKEN_KEYS}
    out.update(model_calls=0, model_ms=0.0, tool_ms=0.0, segments=[], self_checks=[], checkpoints=[],
               scripts=[], success=False, end_state="", success_reason="", needs_approval=False,
               blocked_actions=[], final_url=_page_url(client._page), claimed=None)

    async def look() -> tuple[str, dict | None]:
        """The live page as a snapshot block, plus a screenshot only for visual profiles."""
        snapshot, ms = await client.page_snapshot(description)
        out["tool_ms"] += ms
        block = SNAPSHOT_BEGIN + "\n" + (snapshot or "(the page could not be read)") + "\n" + SNAPSHOT_END
        image = await _screenshot_block(client._page) if visual else None
        return block, image

    page_block, image = await look()
    opening = (handoff_note(task, out["final_url"], list(visited), reason)
               + "\n\n" + page_block
               + f"\nSend the first short segment (at most {SEGMENT_MAX_STEPS} lines).")
    messages: list[dict] = [{"role": "user", "content": [{"type": "text", "text": opening}] + ([image] if image else [])}]

    try:
        while out["model_calls"] < max_calls:
            response, model_ms = await model.create_message(messages, TOOLS, system=INTERACTIVE_PROMPT,
                                                            tool_choice=tool_choice)
            out["model_calls"] += 1
            out["model_ms"] += model_ms
            usage = response.get("usage") or {}
            for key in _TOKEN_KEYS:
                out[key] += int(usage.get(key) or 0)
            content = response.get("content") or []
            texts = [b for b in content if b.get("type") == "text"]
            uses = [b for b in content if b.get("type") == "tool_use"]
            if not uses:
                out.update(end_state="FAIL", success_reason="interactive: model sent no segment")
                break
            use = uses[0]
            messages.append({"role": "assistant", "content": texts + [use]})
            if use.get("name") == "task_failed":
                out.update(end_state="FAIL", success_reason="Task failed: " + str((use.get("input") or {}).get("reason", "")))
                break
            code = str((use.get("input") or {}).get("code") or "")
            out["scripts"].append(code)
            try:
                length = len(parse_task_script(code))
            except ScriptError:
                length = 0  # The executor reports the parse error itself.
            left = max_calls - out["model_calls"]
            if length > SEGMENT_MAX_STEPS:
                out["segments"].append({"refused": True, "ok": False, "steps": 0, "lines": length})
                feedback = (f"Refused, nothing ran: the segment has {length} lines; send at most {SEGMENT_MAX_STEPS}. "
                            f"{left} replies left.")
                messages.append({"role": "user", "content": [{"type": "tool_result", "tool_use_id": use.get("id", ""), "content": feedback}]})
                continue

            result_text, tool_ms = await client.call_tool("run_script", {"code": code})
            out["tool_ms"] += tool_ms
            page_url = page_url_from_result(result_text) or _page_url(client._page)
            verdict, payload = script_runtime_verdict(result_text, page_url, start_url, asks_value=asks_value,
                                                      task=description, earlier=earlier_payloads)
            earlier_payloads.append(payload)
            record = self_check_record(payload, page_url, start_url, verdict)
            checks = evaluate_checkpoints(checkpoints, {**record["payload"], "url": page_url,
                                                        "blocked_actions": list(gate.blocked)})
            out["self_checks"].append(record)
            out["checkpoints"].append(checks)
            out["final_url"] = page_url
            out["claimed"] = claimed_from_payload(payload)
            out["segments"].append({"refused": False, "ok": payload.get("ok") is not False,
                                    "steps": int(payload.get("steps") or 0), "lines": length,
                                    "verdict": verdict.verdict, "reason": verdict.reason, "url": page_url})
            if gate.blocked or payload.get("blocked_actions"):
                out.update(end_state=UNKNOWN, success_reason="UNKNOWN: needs approval: blocked action",
                           needs_approval=True, blocked_actions=list(gate.blocked or payload.get("blocked_actions")))
                break
            accept, rule = precision_check(description, record)
            if accept:
                out.update(success=True, end_state=PASS, success_reason="Task completed successfully")
                break
            if not left:
                out.update(end_state=verdict.verdict if verdict.verdict != PASS else UNKNOWN,
                           success_reason=f"interactive: call cap {max_calls} reached ({rule})")
                break
            page_block, image = await look()
            drop_old_snapshots(messages)
            if image:
                _drop_old_images(messages)
            rejected = "" if verdict.verdict != PASS else f" The runner did not accept this end state: {rule}."
            try:
                visible = model_visible_script_result(result_text, failed=verdict.verdict != PASS, hide_page=True)
            except ValueError:
                # budget_script_result refuses to cut oversized JSON; the notes and snapshot below still apply.
                visible = "(the raw script result was too large to show; the live page is below)"
            feedback = "\n".join([
                visible,
                failed_step_note(code, payload) + " " + _claimed_note(payload),
                f"Self-check: {verdict.verdict}: {verdict.reason}.{rejected}",
                _unmet(checks),
                page_block,
                f"{left} replies left. Send the next short segment, or task_failed.",
            ])
            messages.append({"role": "user", "content": [{"type": "tool_result", "tool_use_id": use.get("id", ""), "content": feedback}]
                             + ([image] if image else [])})
        else:
            out.update(end_state=out["end_state"] or "FAIL",
                       success_reason=out["success_reason"] or f"interactive: call cap {max_calls} reached")
    except PriceUnknown:
        raise
    except Exception as exc:
        # Like the script stage and run_recovery: any model, executor or formatting error ends the
        # stage as FAIL and keeps the usage counted so far, so the row and its spend are not lost.
        out.update(end_state="FAIL", success_reason=f"interactive error: {type(exc).__name__}: {exc}"[:300])
    return out
