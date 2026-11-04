"""fast_act and do_task_segment for the Playwright MCP proxy.

fast_act is one decide() call. An action batch runs through the child.
A tier decision is returned as-is and nothing is clicked.

do_task_segment is one tool call. When this domain, task, and page shape
were stored after a success, it replays that sequence with no model call.
A miss, or any step that cannot be refound or fails, uses the router loop:
observe, decide(), act, then one retry after a failed assertion. A step
that still needs a model uses the cheap Nebius client when a key is present.
Claude is not called. The page summary is one paragraph from the latest snapshot.
"""

from __future__ import annotations

import json
from pathlib import Path

from backends.playwright_mcp import PlaywrightMcpBackend, ToolCall
from core.backend import Element
from loop.actions import (
    ActionBatch,
    ActionError,
    AssertText,
    AssertTitle,
    AssertUrl,
    Assertion,
    Click,
    Fill,
    Goto,
    Observation,
    Press,
    check_url,
)
from loop.decide import TierDecision, decide
from loop.planner import FastClient, PlannerError, load_step5_env
from proxy.page import observation_from_tool_text, page_paragraph, tool_text
from proxy.replay import cache_key, load_sequence, resolve_cache_path, store_sequence

FAST_ACT = "fast_act"
DO_TASK_SEGMENT = "do_task_segment"
_DEFAULT_CYCLES = 8
_MAX_CYCLES = 12
_AUTO = object()

_PREFER = (
    "Prefer do_task_segment for a multi-step sub-task and fast_act for one obvious action. "
    "Do not walk the page with browser_snapshot, browser_click, and browser_type one step at a time."
)


def _schema(properties: dict, required: list[str]) -> dict:
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


PROXY_TOOLS = [
    {
        "name": FAST_ACT,
        "description": (
            "One obvious action, and no model call. "
            "Use fast_act when the next step is a single clear control: a unique link or button "
            "named in the task, or one search box and a Search button. "
            + _PREFER
            + " If this step needs a model, fast_act returns that tier and does not act."
        ),
        "inputSchema": _schema(
            {
                "task": {
                    "type": "string",
                    "description": "The single action, in plain language.",
                },
                "url": {
                    "type": "string",
                    "description": "Open this page first. Omit to use the current page.",
                },
            },
            ["task"],
        ),
    },
    {
        "name": DO_TASK_SEGMENT,
        "description": (
            "One call for a multi-step sub-task. "
            "A stored sequence for this domain, task, and page shape is replayed first, "
            "with no model call. If replay cannot refind a target, the action fails, "
            "or an assertion fails, the call falls back to no-model actions from decide(), "
            "then the cheap Nebius tier when NEBIUS_API_KEY is set. It does not call Claude. "
            + _PREFER
        ),
        "inputSchema": _schema(
            {
                "task": {
                    "type": "string",
                    "description": "The sub-task to finish.",
                },
                "url": {
                    "type": "string",
                    "description": "Open this page first. Omit to use the current page.",
                },
                "max_cycles": {
                    "type": "integer",
                    "description": "Observe-and-act cycles. Default 8, at most 12.",
                },
            },
            ["task"],
        ),
    },
]


def listed_tools(child_tools: list) -> list:
    """Child tools, unchanged and in order, then fast_act and do_task_segment."""
    names = {tool.get("name") for tool in child_tools if isinstance(tool, dict)}
    extra = [tool for tool in PROXY_TOOLS if tool["name"] not in names]
    return list(child_tools) + extra


def tool_result(payload: dict) -> dict:
    return {
        "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}],
        "isError": payload.get("status") == "failed",
    }


def cheap_client(env_path: str | None = None, transport=None) -> FastClient | None:
    """Nebius client when a key is set. None when the cheap tier is unavailable.

    env_path None reads the same file the router uses. A missing file falls
    back to the environment. An empty key returns None and does not call a model.
    """
    values = load_step5_env(env_path)
    key = values.get("NEBIUS_API_KEY", "").strip()
    if not key:
        return None
    base = values.get("NEBIUS_BASE_URL", "").strip() or "https://api.studio.nebius.com/v1"
    return FastClient(
        api_key=key,
        base_url=base,
        model=values.get("NEBIUS_FAST_MODEL", ""),
        transport=transport,
    )


def _arguments(arguments) -> dict:
    if arguments is None:
        return {}
    if isinstance(arguments, dict):
        return arguments
    return dict(arguments)


def _task(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("task must be a non-empty string")
    if len(value) > 4000:
        raise ValueError("task is longer than 4000 characters")
    return value.strip()


def _optional_url(value: object) -> str:
    if value is None or value == "":
        return ""
    if not isinstance(value, str):
        raise ValueError("url must be a string")
    try:
        return check_url(value)
    except ActionError as exc:
        raise ValueError(str(exc)) from exc


def _max_cycles(value: object) -> int:
    if value is None:
        return _DEFAULT_CYCLES
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("max_cycles must be an integer")
    if value < 1 or value > _MAX_CYCLES:
        raise ValueError(f"max_cycles must be from 1 to {_MAX_CYCLES}")
    return value


def _parse_call(arguments, *, cycles: bool) -> tuple[str, str, int]:
    raw = _arguments(arguments)
    task = _task(raw.get("task"))
    url = _optional_url(raw.get("url"))
    limit = _max_cycles(raw.get("max_cycles")) if cycles else 1
    return task, url, limit


def _payload(
    *,
    ok: bool,
    status: str,
    tier: str,
    url: str,
    summary: str,
    page: str,
    actions: list[str],
    cycles: int,
    model_calls: int,
    needs_model: bool,
) -> dict:
    return {
        "ok": ok,
        "status": status,
        "needs_model": needs_model,
        "tier": tier,
        "url": url,
        "summary": summary,
        "page": page,
        "actions": list(actions),
        "cycles": cycles,
        "model_calls": model_calls,
    }


def _failed(
    message: str,
    *,
    url: str = "",
    page: str = "",
    actions: list[str] | None = None,
    cycles: int = 0,
    model_calls: int = 0,
    tier: str = "",
) -> dict:
    return _payload(
        ok=False,
        status="failed",
        tier=tier,
        url=url,
        summary=message,
        page=page,
        actions=actions or [],
        cycles=cycles,
        model_calls=model_calls,
        needs_model=False,
    )


def _sentence(text: str) -> str:
    cleaned = " ".join(text.split())
    if not cleaned:
        return ""
    if cleaned[-1] not in ".!?":
        cleaned += "."
    return cleaned


def _summary(reason: str, actions: list[str], extra: str = "") -> str:
    parts = [part for part in (_sentence(reason), _sentence(extra)) if part]
    if actions:
        parts.append("Ran " + "; ".join(actions) + ".")
    return " ".join(parts) or "No action was taken."


def _history_item(batch: ActionBatch, assertion_ok: bool | None, assertion_detail: str | None, tier: str) -> dict:
    item = {
        "reason": batch.reason,
        "actions": [action.summary() for action in batch.actions],
        "done": batch.done,
        "tier": tier,
    }
    if assertion_detail is not None:
        item["assertion"] = {"ok": assertion_ok, "detail": assertion_detail}
    return item


def _assert_page(observation: Observation, raw: str, assertion: Assertion) -> tuple[bool, str]:
    if isinstance(assertion, AssertUrl):
        ok = assertion.text in observation.url
        return ok, f"url contains {assertion.text!r}"
    if isinstance(assertion, AssertTitle):
        ok = assertion.text in observation.title
        return ok, f"title contains {assertion.text!r}"
    if isinstance(assertion, AssertText):
        ok = assertion.text in raw
        return ok, f"page contains {assertion.text!r}"
    raise ActionError(f"unknown assertion: {assertion!r}")


async def _navigate(child, url: str) -> None:
    result = await child.call_tool("browser_navigate", {"url": url})
    if isinstance(result, dict) and result.get("isError") is True:
        detail = tool_text(result)[:300] or "browser_navigate failed"
        raise ActionError(detail)


async def _read_page(child) -> tuple[Observation, str, str]:
    result = await child.call_tool("browser_snapshot", {})
    if isinstance(result, dict) and result.get("isError") is True:
        detail = tool_text(result)[:300] or "browser_snapshot failed"
        raise ActionError(detail)
    raw = tool_text(result if isinstance(result, dict) else {})
    observation, yaml = observation_from_tool_text(raw)
    return observation, raw, yaml


def _recorded_step(backend: PlaywrightMcpBackend, action: object, call: ToolCall) -> dict:
    """tool, role, name, and value. The live ref stays out of the cache."""
    element = _target_element(backend, action, call)
    if isinstance(action, Fill):
        value = action.text
    elif isinstance(action, Press):
        value = action.key
    elif isinstance(action, Goto):
        value = action.url
    else:
        value = ""
    return {
        "tool": call.name,
        "role": element.role if element is not None else "",
        "name": element.name if element is not None else "",
        "value": value,
    }


def _target_element(backend: PlaywrightMcpBackend, action: object, call: ToolCall):
    target = call.arguments.get("target")
    if not isinstance(target, str) or not target:
        target = getattr(action, "ref", None)
    if not isinstance(target, str) or not target:
        return None
    for element in backend.observe().elements:
        if element.id == target:
            return element
    return None


async def _execute(
    child,
    backend: PlaywrightMcpBackend,
    yaml: str,
    observation: Observation,
    batch: ActionBatch,
) -> list[dict]:
    backend.load_snapshot(yaml, url=observation.url, title=observation.title)
    recorded: list[dict] = []
    for action in batch.actions:
        call = backend.tool_call(action)
        recorded.append(_recorded_step(backend, action, call))
        result = await child.call_tool(call.name, dict(call.arguments))
        if isinstance(result, dict) and result.get("isError") is True:
            detail = tool_text(result)[:300] or "the tool returned an error"
            raise ActionError(f"{action.summary()} failed: {detail}")
    return recorded


def _view(observation: Observation | None) -> tuple[str, str]:
    if observation is None:
        return "", ""
    return observation.url, page_paragraph(observation)


async def fast_act(child, arguments) -> dict:
    """Run one no-model batch, or return the tier decide() asked for."""
    task, url, _cycles = _parse_call(arguments, cycles=False)
    backend = PlaywrightMcpBackend()
    try:
        if url:
            await _navigate(child, url)
        observation, raw, yaml = await _read_page(child)
    except ActionError as exc:
        return _failed(str(exc))
    outcome = decide(task, observation)
    page_url, paragraph = _view(observation)
    if isinstance(outcome, TierDecision):
        return _payload(
            ok=False,
            status="needs_model",
            tier=outcome.tier,
            url=page_url,
            summary=f"This step needs the {outcome.tier} tier. No action was taken.",
            page=paragraph,
            actions=[],
            cycles=0,
            model_calls=0,
            needs_model=True,
        )
    if not isinstance(outcome, ActionBatch):
        return _payload(
            ok=False,
            status="stopped",
            tier="direct",
            url=page_url,
            summary="No direct action matched this page. No action was taken.",
            page=paragraph,
            actions=[],
            cycles=0,
            model_calls=0,
            needs_model=False,
        )
    try:
        if outcome.actions:
            await _execute(child, backend, yaml, observation, outcome)
            after, after_raw, _yaml = await _read_page(child)
        else:
            after, after_raw = observation, raw
    except ActionError as exc:
        return _failed(str(exc), url=page_url, page=paragraph, actions=[action.summary() for action in outcome.actions])
    ran = [action.summary() for action in outcome.actions]
    extra = ""
    ok = True
    status = "done"
    if outcome.assertion is not None:
        passed, detail = _assert_page(after, after_raw, outcome.assertion)
        if not passed:
            ok = False
            status = "failed"
            extra = f"Assertion failed: {detail}"
    final_url, final_page = _view(after)
    return _payload(
        ok=ok,
        status=status,
        tier="direct",
        url=final_url,
        summary=_summary(outcome.reason, ran, extra),
        page=final_page,
        actions=ran,
        cycles=1,
        model_calls=0,
        needs_model=False,
    )


def _needs_cheap(
    tier: str,
    *,
    url: str,
    page: str,
    actions: list[str],
    cycles: int,
    model_calls: int,
) -> dict:
    message = f"Stopped. The next step needs the cheap model ({tier}) and NEBIUS_API_KEY is not set."
    return _payload(
        ok=False,
        status="stopped",
        tier=tier,
        url=url,
        summary=message,
        page=page,
        actions=actions,
        cycles=cycles,
        model_calls=model_calls,
        needs_model=True,
    )


def _controls_for_cheap(outcome: TierDecision, observation: Observation) -> list:
    if outcome.controls:
        return list(outcome.controls)
    return list(observation.controls[:8])


_PROBE_ID = "replay-probe"


class _ReplayAbandoned(Exception):
    """A stored step cannot be replayed. The caller falls back to decide()."""


class _ReplayResult:
    def __init__(
        self,
        kind: str,
        *,
        payload: dict | None = None,
        observation: Observation | None = None,
        raw: str = "",
        yaml: str = "",
        summaries: list[str] | None = None,
    ):
        self.kind = kind
        self.payload = payload
        self.observation = observation
        self.raw = raw
        self.yaml = yaml
        self.summaries = list(summaries or [])


def _assertion_kind(assertion: Assertion) -> str:
    if isinstance(assertion, AssertUrl):
        return "url"
    if isinstance(assertion, AssertTitle):
        return "title"
    if isinstance(assertion, AssertText):
        return "text"
    raise ActionError(f"unknown assertion: {assertion!r}")


def _sequence_usable(stored: dict) -> bool:
    actions = stored.get("actions")
    assertions = stored.get("assertions")
    if not isinstance(actions, list) or not isinstance(assertions, list):
        return False
    if not actions and not assertions:
        return False
    for step in actions:
        if not isinstance(step, dict) or not isinstance(step.get("tool"), str) or not step["tool"]:
            return False
        for field in ("role", "name", "value"):
            if field in step and not isinstance(step[field], str):
                return False
    for item in assertions:
        if not isinstance(item, dict):
            return False
        text = item.get("text")
        after = item.get("after")
        if not isinstance(item.get("type"), str) or not isinstance(text, str) or not text:
            return False
        if isinstance(after, bool) or not isinstance(after, int) or after < 0 or after > len(actions):
            return False
    return True


def _assert_stored(observation: Observation, raw: str, item: dict) -> tuple[bool, str]:
    text = item["text"]
    kind = item["type"]
    if kind == "url":
        return _assert_page(observation, raw, AssertUrl(text))
    if kind == "title":
        return _assert_page(observation, raw, AssertTitle(text))
    if kind == "text":
        return _assert_page(observation, raw, AssertText(text))
    return False, "stored assertion type is not usable"


def _replay_step(
    backend: PlaywrightMcpBackend,
    yaml: str,
    observation: Observation,
    step: dict,
) -> tuple[ToolCall, str]:
    """Refind the stored role and name, then build the child tool call."""
    tool = step.get("tool")
    role = step.get("role") if isinstance(step.get("role"), str) else ""
    name = step.get("name") if isinstance(step.get("name"), str) else ""
    value = step.get("value") if isinstance(step.get("value"), str) else ""
    backend.load_snapshot(yaml, url=observation.url, title=observation.title)
    if tool == "browser_navigate":
        action = Goto(check_url(value))
        return backend.tool_call(action), action.summary()
    if tool == "browser_press_key" and not name.strip():
        action = Press(value)
        return backend.tool_call(action), action.summary()
    if tool not in {"browser_click", "browser_type", "browser_press_key"}:
        raise _ReplayAbandoned(f"stored tool cannot be replayed: {tool!r}")
    if not role or not name.strip():
        raise _ReplayAbandoned(f"stored {tool} has no role and name")
    found = backend.refind(Element(id=_PROBE_ID, role=role, name=name, source="aria"))
    if found is None:
        raise _ReplayAbandoned(f"no unique {role} named {name}")
    if tool == "browser_click":
        played = Click(found.id)
    elif tool == "browser_type":
        played = Fill(found.id, value)
    else:
        played = Press(value, found.id)
    return backend.tool_call(played), played.summary()


async def _replay_sequence(
    child,
    cache_file: Path,
    task: str,
    observation: Observation,
    raw: str,
    yaml: str,
) -> _ReplayResult:
    """Play a stored sequence. This function does not call decide() or a model.

    kind is done, miss, or fallback. fallback with observation None means the
    page could not be read after an action, so the caller reads it again.
    """
    domain, stored_task, shape = cache_key(task, observation)
    stored = load_sequence(cache_file, domain, stored_task, shape)
    if stored is None or not _sequence_usable(stored):
        return _ReplayResult("miss")
    actions = stored["actions"]
    assertions = stored["assertions"]
    backend = PlaywrightMcpBackend()
    summaries: list[str] = []
    executed = 0
    current_obs, current_raw, current_yaml = observation, raw, yaml

    def abandon(_detail: str) -> _ReplayResult:
        return _ReplayResult(
            "fallback",
            observation=current_obs,
            raw=current_raw,
            yaml=current_yaml,
            summaries=summaries,
        )

    while True:
        for item in assertions:
            if item.get("after") != executed:
                continue
            ok, detail = _assert_stored(current_obs, current_raw, item)
            if not ok:
                return abandon(detail)
        if executed == len(actions):
            break
        try:
            call, summary = _replay_step(backend, current_yaml, current_obs, actions[executed])
        except (_ReplayAbandoned, ActionError) as exc:
            return abandon(str(exc))
        result = await child.call_tool(call.name, dict(call.arguments))
        if isinstance(result, dict) and result.get("isError") is True:
            detail = tool_text(result)[:300] or "the tool returned an error"
            try:
                current_obs, current_raw, current_yaml = await _read_page(child)
            except ActionError:
                return _ReplayResult("fallback", observation=None, summaries=summaries)
            return abandon(detail)
        summaries.append(summary)
        executed += 1
        try:
            current_obs, current_raw, current_yaml = await _read_page(child)
        except ActionError:
            return _ReplayResult("fallback", observation=None, summaries=summaries)

    final_url, final_page = _view(current_obs)
    payload = _payload(
        ok=True,
        status="done",
        tier="replay",
        url=final_url,
        summary=_summary("Replayed a stored action sequence", summaries),
        page=final_page,
        actions=summaries,
        cycles=1,
        model_calls=0,
        needs_model=False,
    )
    return _ReplayResult("done", payload=payload)


async def do_task_segment(child, arguments, *, client=_AUTO, env_path=_AUTO, cache_path=_AUTO) -> dict:
    """One call. Replay a stored sequence, then no-model actions, then the cheap tier.

    client, env_path, and cache_path are for tests. The server leaves them unset,
    which reads the same Nebius key the router uses and skips the model when it is empty.
    """
    task, url, max_cycles = _parse_call(arguments, cycles=True)
    if client is _AUTO:
        path = None if env_path is _AUTO else env_path
        client = cheap_client(path)
    chosen = None if cache_path is _AUTO else cache_path
    return await _run_segment(
        child,
        task,
        url=url,
        max_cycles=max_cycles,
        client=client,
        cache_file=resolve_cache_path(chosen),
    )


async def _run_segment(
    child,
    task: str,
    *,
    url: str,
    max_cycles: int,
    client: FastClient | None,
    cache_file: Path,
) -> dict:
    backend = PlaywrightMcpBackend()
    history: list[dict] = []
    previous_batch: ActionBatch | None = None
    previous_observation: Observation | None = None
    retries_used = 0
    awaiting_retry = False
    cycles = 0
    model_calls = 0
    actions: list[str] = []
    last_tier = "direct"
    last_reason = ""
    observation: Observation | None = None
    latest: Observation | None = None
    replay_checked = False
    record_key = None
    recorded_actions: list[dict] = []
    recorded_assertions: list[dict] = []

    def _remember() -> None:
        if record_key is None:
            return
        if not recorded_actions and not recorded_assertions:
            return
        store_sequence(
            cache_file,
            record_key[0],
            record_key[1],
            record_key[2],
            {"actions": list(recorded_actions), "assertions": list(recorded_assertions)},
        )

    try:
        if url:
            await _navigate(child, url)
    except ActionError as exc:
        return _failed(str(exc))

    while cycles < max_cycles:
        try:
            observation, _raw, yaml = await _read_page(child)
        except ActionError as exc:
            page_url, paragraph = _view(observation)
            return _failed(str(exc), url=page_url, page=paragraph, actions=actions, cycles=cycles)
        if not replay_checked:
            replay_checked = True
            replayed = await _replay_sequence(child, cache_file, task, observation, _raw, yaml)
            if replayed.kind == "done" and replayed.payload is not None:
                return replayed.payload
            if replayed.kind == "fallback":
                actions.extend(replayed.summaries)
                if replayed.observation is None:
                    continue
                observation = replayed.observation
                _raw = replayed.raw
                yaml = replayed.yaml
        if record_key is None:
            record_key = cache_key(task, observation)
        retry = awaiting_retry
        awaiting_retry = False
        outcome = decide(
            task,
            observation,
            previous_batch,
            previous_observation,
            retry,
            first=not history,
        )
        page_url, paragraph = _view(observation)
        if isinstance(outcome, ActionBatch):
            tier = "direct"
            batch = outcome
        elif client is None:
            tier = outcome.tier if isinstance(outcome, TierDecision) else "direct"
            return _needs_cheap(tier, url=page_url, page=paragraph, actions=actions, cycles=cycles, model_calls=model_calls)
        elif not isinstance(outcome, TierDecision):
            return _payload(
                ok=False,
                status="stopped",
                tier="direct",
                url=page_url,
                summary="No direct action matched this page. No action was taken.",
                page=paragraph,
                actions=actions,
                cycles=cycles,
                model_calls=model_calls,
                needs_model=False,
            )
        else:
            controls = _controls_for_cheap(outcome, observation)
            if not controls:
                return _payload(
                    ok=False,
                    status="stopped",
                    tier=outcome.tier,
                    url=page_url,
                    summary=(
                        f"Stopped. The next step needs the cheap model ({outcome.tier}) "
                        "and this page has no controls to send."
                    ),
                    page=paragraph,
                    actions=actions,
                    cycles=cycles,
                    model_calls=model_calls,
                    needs_model=True,
                )
            try:
                batch = client.plan(task, controls, history)
            except PlannerError as exc:
                model_calls += 1
                return _payload(
                    ok=False,
                    status="failed",
                    tier="fast",
                    url=page_url,
                    summary=f"Stopped. The cheap model did not return an action. {exc}",
                    page=paragraph,
                    actions=actions,
                    cycles=cycles,
                    model_calls=model_calls,
                    needs_model=True,
                )
            model_calls += 1
            tier = "fast"
        last_tier = tier
        last_reason = batch.reason
        try:
            if batch.actions:
                recorded_actions.extend(await _execute(child, backend, yaml, observation, batch))
                actions.extend(action.summary() for action in batch.actions)
                after, after_raw, _yaml = await _read_page(child)
            else:
                after, after_raw = observation, _raw
        except ActionError as exc:
            page_url, paragraph = _view(latest or observation)
            return _failed(
                str(exc),
                url=page_url,
                page=paragraph,
                actions=actions,
                cycles=cycles,
                model_calls=model_calls,
                tier=tier,
            )
        latest = after
        assertion_ok = None
        assertion_detail = None
        if batch.assertion is not None:
            assertion_ok, assertion_detail = _assert_page(after, after_raw, batch.assertion)
            if assertion_ok:
                recorded_assertions.append(
                    {
                        "type": _assertion_kind(batch.assertion),
                        "text": batch.assertion.text,
                        "after": len(recorded_actions),
                    }
                )
            if not assertion_ok:
                history.append(_history_item(batch, False, assertion_detail, tier))
                previous_observation = observation
                previous_batch = batch
                cycles += 1
                if retries_used >= 1:
                    final_url, final_page = _view(after)
                    detail = assertion_detail or "the check did not pass"
                    if detail.startswith("Assertion failed"):
                        message = detail
                    else:
                        message = f"Assertion failed: {detail}"
                    return _payload(
                        ok=False,
                        status="failed",
                        tier=tier,
                        url=final_url,
                        summary=message,
                        page=final_page,
                        actions=actions,
                        cycles=cycles,
                        model_calls=model_calls,
                        needs_model=False,
                    )
                retries_used += 1
                awaiting_retry = True
                continue
        history.append(_history_item(batch, assertion_ok, assertion_detail, tier))
        previous_observation = observation
        previous_batch = batch
        cycles += 1
        if batch.done:
            final_url, final_page = _view(after)
            _remember()
            return _payload(
                ok=True,
                status="done",
                tier=tier,
                url=final_url,
                summary=_summary(batch.reason, actions),
                page=final_page,
                actions=actions,
                cycles=cycles,
                model_calls=model_calls,
                needs_model=False,
            )
    final_url, final_page = _view(latest or observation)
    return _payload(
        ok=False,
        status="failed",
        tier=last_tier,
        url=final_url,
        summary=_summary(last_reason, actions, f"Stopped after {max_cycles} cycles"),
        page=final_page,
        actions=actions,
        cycles=cycles,
        model_calls=model_calls,
        needs_model=False,
    )


async def dispatch(child, name: str, arguments, *, client=_AUTO, env_path=_AUTO, cache_path=_AUTO) -> dict:
    """fast_act and do_task_segment stay here. Every other name is forwarded."""
    try:
        if name == FAST_ACT:
            return tool_result(await fast_act(child, arguments))
        if name == DO_TASK_SEGMENT:
            return tool_result(
                await do_task_segment(
                    child,
                    arguments,
                    client=client,
                    env_path=env_path,
                    cache_path=cache_path,
                )
            )
    except ValueError as exc:
        return tool_result(_failed(str(exc)))
    args = arguments if isinstance(arguments, dict) else None
    return await child.call_tool(name, args)

