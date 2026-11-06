"""Engine.run as a tool. The model is allowed only when planner is \"model\"."""

from __future__ import annotations

from datetime import datetime, timezone

from loop.actions import ActionError, PlannerError
from loop.browser import fixture_file_url
from loop.checks import PageProbe, resolve_url
from loop.engine import Controller, Engine, Log
from loop.planner import make_planner


class QuietLog(Log):
    """Same events as Log, without writing to stdout (that stream is MCP JSON)."""

    def _add(self, kind: str, line: str, **data) -> None:
        event = {
            "ts": datetime.now(timezone.utc).strftime("%H:%M:%S"),
            "kind": kind,
            "line": line,
            **data,
        }
        with self._lock:
            self._events.append(event)


def run_loop(
    probe: PageProbe,
    *,
    task: str,
    start_url: str | None = None,
    planner: str = "fake",
    max_cycles: int = 12,
) -> dict:
    """Start: a blank page, or start_url when one is given.

    End: Engine.run finishes done, or fails on its assertion or an action error.
    planner \"fake\" makes zero model calls. planner \"model\" may call the model.
    """
    if not isinstance(task, str) or not task.strip():
        raise ActionError("run_loop needs a task")
    if planner not in ("fake", "model"):
        raise ActionError("planner must be fake or model")
    opened = ""
    if isinstance(start_url, str) and start_url.strip():
        opened = resolve_url(start_url)
        probe.open_url(start_url)
    fixture = opened or fixture_file_url()
    log = QuietLog()
    controller = Controller()
    controller.task = task.strip()
    controller.planner_name = planner
    controller.mode = "running"
    engine = Engine(probe.session, controller, log, max_cycles=max_cycles)
    try:
        engine.planner = make_planner(planner, fixture)
    except PlannerError as exc:
        return _result(False, "failed", str(exc), start_url or "", planner, log)
    log.status(f"run      {controller.task}  planner: {planner}")
    engine.run()
    snapshot = controller.snapshot()
    mode = snapshot["mode"]
    return _result(mode == "done", mode, snapshot.get("detail") or "", start_url or "", planner, log)


def _result(ok: bool, mode: str, detail: str, start_url: str, planner: str, log: Log) -> dict:
    payload = {
        "ok": ok,
        "mode": mode,
        "detail": detail,
        "start": {"url": start_url},
        "end": {"mode": mode, "detail": detail},
        "planner": planner,
        "model_allowed": planner == "model",
        "events": [{"kind": event["kind"], "line": event["line"]} for event in log.snapshot()],
    }
    if planner != "model":
        payload["model_calls"] = 0
    return payload
