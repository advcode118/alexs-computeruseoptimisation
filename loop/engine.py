"""The loop itself: permit a cycle, observe, plan one batch, act, assert."""

from __future__ import annotations

import threading
from datetime import datetime, timezone

from loop.actions import Action, ActionBatch, ActionError, Assertion, Click, Observation, PlannerError
from loop.browser import BrowserSession, act, check, observe
from loop.planner import route_decision


class Log:
    def __init__(self):
        self._events: list[dict] = []
        self._lock = threading.Lock()

    def clear(self) -> None:
        with self._lock:
            self._events.clear()

    def snapshot(self) -> list[dict]:
        with self._lock:
            return list(self._events[-200:])

    def kinds(self) -> list[str]:
        return [event["kind"] for event in self.snapshot()]

    def _add(self, kind: str, line: str, **data) -> None:
        event = {
            "ts": datetime.now(timezone.utc).strftime("%H:%M:%S"),
            "kind": kind,
            "line": line,
            **data,
        }
        with self._lock:
            self._events.append(event)
        print(f"{event['ts']}  {line}", flush=True)

    def status(self, line: str) -> None:
        self._add("status", line)

    def observe(self, observation: Observation) -> None:
        shown = " ".join(
            f"[{control.ref} {control.role} {control.name}]" for control in observation.controls[:8]
        )
        extra = "" if len(observation.controls) <= 8 else f" +{len(observation.controls) - 8}"
        title = observation.title or "(no title)"
        line = f"observe  {title}  {observation.url}  {len(observation.controls)} controls  {shown}{extra}"
        self._add(
            "observe",
            line,
            url=observation.url,
            title=observation.title,
            controls=[control.to_dict() for control in observation.controls],
        )

    def plan(self, batch: ActionBatch, *, tier: str = "planner") -> None:
        actions = ", ".join(action.summary() for action in batch.actions) or "(none)"
        assertion = batch.assertion.summary() if batch.assertion else "none"
        line = f"plan     {tier:<7} {batch.reason or '(no reason)'}  actions: {actions}  assert: {assertion}"
        self._add("plan", line, done=batch.done, reason=batch.reason, tier=tier)

    def act(self, action: Action, *, ok: bool, error: str | None = None) -> None:
        status = "ok" if ok else f"failed: {error}"
        self._add("act", f"act      {action.summary()}  {status}", ok=ok, action=action.summary(), error=error)

    def assertion(self, ok: bool, detail: str) -> None:
        status = "ok" if ok else "failed"
        self._add("assert", f"assert   {status}  {detail}", ok=ok, detail=detail)

    def error(self, detail: str) -> None:
        self._add("error", f"error    {detail}")


class Controller:
    """Start, pause, step, and stop. The loop thread blocks in permit()."""

    def __init__(self):
        self._cv = threading.Condition()
        self.mode = "idle"
        self.task = ""
        self.planner_name = "fake"
        self.detail = ""
        self.fresh = False
        self.step_requested = False
        self.step_only = False
        self.stop_run = False
        self.quit = False

    def snapshot(self) -> dict:
        with self._cv:
            return {
                "mode": self.mode,
                "task": self.task,
                "planner": self.planner_name,
                "detail": self.detail,
            }

    def start(self, task: str, planner_name: str) -> None:
        with self._cv:
            self.task = task.strip()
            self.planner_name = planner_name
            if self.mode in ("idle", "done", "failed", "stopped"):
                self.fresh = True
                self.detail = ""
            self.mode = "running"
            self.stop_run = False
            self.step_only = False
            self.step_requested = False
            self._cv.notify_all()

    def pause(self) -> None:
        with self._cv:
            if self.mode == "running":
                self.mode = "paused"
            self._cv.notify_all()

    def step(self, task: str, planner_name: str) -> None:
        with self._cv:
            if task.strip():
                self.task = task.strip()
            if planner_name:
                self.planner_name = planner_name
            if self.mode == "running" and not self.step_only and not self.step_requested:
                self.step_only = True
                self._cv.notify_all()
                return
            if self.mode in ("idle", "done", "failed", "stopped"):
                self.fresh = True
                self.detail = ""
            self.stop_run = False
            self.step_requested = True
            # Leave "paused" immediately so a waiter does not treat the previous pause as this step.
            self.mode = "running"
            self._cv.notify_all()

    def stop(self) -> None:
        with self._cv:
            if self.mode in ("running", "paused") or self.step_requested:
                self.stop_run = True
                self.mode = "stopped"
                self.step_requested = False
                self.detail = "Stopped."
            self._cv.notify_all()

    def request_quit(self) -> None:
        with self._cv:
            self.quit = True
            self.stop_run = True
            self._cv.notify_all()

    def wait_until_active(self) -> bool:
        with self._cv:
            while True:
                if self.quit:
                    return False
                if self.mode == "running" or self.step_requested:
                    return True
                self._cv.wait(timeout=0.2)

    def take_fresh(self) -> bool:
        with self._cv:
            fresh = self.fresh
            self.fresh = False
            return fresh

    def current_task(self) -> str:
        with self._cv:
            return self.task

    def permit(self) -> bool:
        with self._cv:
            while True:
                if self.quit or self.stop_run:
                    return False
                if self.step_requested:
                    self.step_requested = False
                    self.mode = "running"
                    self.step_only = True
                    return True
                if self.mode == "running":
                    return True
                self._cv.wait(timeout=0.2)

    def end_cycle(self) -> None:
        with self._cv:
            if self.step_only:
                self.step_only = False
                if self.mode == "running" and not self.stop_run:
                    self.mode = "paused"
            self._cv.notify_all()

    def should_stop(self) -> bool:
        with self._cv:
            return self.quit or self.stop_run

    def finish(self, mode: str, detail: str) -> None:
        with self._cv:
            if self.stop_run or self.mode == "stopped":
                self.mode = "stopped"
                if not self.detail:
                    self.detail = detail or "Stopped."
            else:
                self.mode = mode
                self.detail = detail
            self.stop_run = False
            self.step_only = False
            self.step_requested = False
            self._cv.notify_all()


def _history_item(
    batch: ActionBatch,
    assertion_ok: bool | None,
    assertion_detail: str | None,
    tier: str,
) -> dict:
    item = {
        "reason": batch.reason,
        "actions": [action.summary() for action in batch.actions],
        "done": batch.done,
        "tier": tier,
    }
    if assertion_detail is not None:
        item["assertion"] = {"ok": assertion_ok, "detail": assertion_detail}
    return item


class Engine:
    def __init__(self, session: BrowserSession, controller: Controller, log: Log, *, max_cycles: int = 12):
        self.session = session
        self.controller = controller
        self.log = log
        self.max_cycles = max_cycles
        self.planner = None
        self.history: list[dict] = []
        self._previous_batch: ActionBatch | None = None
        self._previous_observation: Observation | None = None
        self._retries_used = 0
        self._awaiting_retry = False

    def reset_run(self) -> None:
        self.history = []
        self._previous_batch = None
        self._previous_observation = None
        self._retries_used = 0
        self._awaiting_retry = False

    def _remember(self, observation: Observation, batch: ActionBatch) -> None:
        self._previous_observation = observation
        self._previous_batch = batch

    def _next_batch(self, observation: Observation, *, retry: bool) -> tuple[str, ActionBatch]:
        task = self.controller.current_task()
        if not getattr(self.planner, "use_router", False):
            return "planner", self.planner.plan(task, observation, self.history)
        tier, short = route_decision(
            first=not self.history,
            retry=retry,
            previous_batch=self._previous_batch,
            previous_observation=self._previous_observation,
            observation=observation,
        )
        if tier == "direct":
            control = short[0]
            return tier, ActionBatch(
                reason=f"Click the only {control.role} named {control.name}.",
                actions=[Click(control.ref)],
                assertion=None,
                done=False,
            )
        if tier == "fast":
            return tier, self.planner.fast.plan(task, short, self.history)
        return "planner", self.planner.claude.plan(task, observation, self.history)

    def run(self) -> None:
        if self.session.page is None or self.planner is None:
            self.controller.finish("failed", "The browser is not open.")
            return
        cycles = 0
        try:
            while cycles < self.max_cycles:
                if not self.controller.permit():
                    self.controller.finish("stopped", "Stopped.")
                    return
                if self.controller.should_stop():
                    self.controller.finish("stopped", "Stopped.")
                    return
                observation = observe(self.session.page)
                self.log.observe(observation)
                if self.controller.should_stop():
                    self.controller.finish("stopped", "Stopped.")
                    return
                retry = self._awaiting_retry
                self._awaiting_retry = False
                try:
                    tier, batch = self._next_batch(observation, retry=retry)
                except PlannerError as exc:
                    self.log.error(str(exc))
                    self.controller.finish("failed", str(exc))
                    return
                self.log.plan(batch, tier=tier)
                if self.controller.should_stop():
                    self.controller.finish("stopped", "Stopped before the actions ran.")
                    return
                for action in batch.actions:
                    if self.controller.should_stop():
                        self.controller.finish("stopped", "Stopped.")
                        return
                    try:
                        act(self.session.page, action)
                    except ActionError as exc:
                        self.log.act(action, ok=False, error=str(exc))
                        self.controller.finish("failed", str(exc))
                        return
                    self.log.act(action, ok=True)
                assertion_ok = None
                assertion_detail = None
                if batch.assertion is not None:
                    assertion_ok, assertion_detail = self._assert(batch.assertion)
                    if not assertion_ok:
                        self.history.append(_history_item(batch, assertion_ok, assertion_detail, tier))
                        self._remember(observation, batch)
                        cycles += 1
                        if self._retries_used >= 1:
                            self.controller.finish("failed", assertion_detail or "Assertion failed.")
                            return
                        self._retries_used += 1
                        self._awaiting_retry = True
                        self.controller.end_cycle()
                        continue
                self.history.append(_history_item(batch, assertion_ok, assertion_detail, tier))
                self._remember(observation, batch)
                cycles += 1
                if batch.done:
                    self.controller.finish("done", batch.reason or "Done.")
                    return
                self.controller.end_cycle()
        except Exception as exc:
            message = str(exc).split("\n", 1)[0][:300]
            self.log.error(message)
            self.controller.finish("failed", message)
            return
        self.controller.finish("failed", f"Stopped after {self.max_cycles} cycles.")

    def _assert(self, assertion: Assertion) -> tuple[bool, str]:
        ok, detail = check(self.session.page, assertion)
        self.log.assertion(ok, detail)
        if not ok:
            detail = f"Assertion failed: {detail}"
        return ok, detail


class Runner:
    """Browser thread plus the controller the page and the CLI share."""

    def __init__(
        self,
        *,
        fixture_url: str,
        headless: bool = True,
        cdp: str | None = None,
        max_cycles: int = 12,
        planner_factory=None,
        log: Log | None = None,
    ):
        self.fixture_url = fixture_url
        self.headless = headless
        self.cdp = cdp
        self.max_cycles = max_cycles
        self.planner_factory = planner_factory
        self.log = log or Log()
        self.controller = Controller()
        self.session = BrowserSession(headless=headless, cdp=cdp)
        self.engine = Engine(self.session, self.controller, self.log, max_cycles=max_cycles)
        self.open_error = ""
        self._ready = threading.Event()
        self._thread = threading.Thread(target=self._worker, name="browser-loop", daemon=True)

    def open(self, timeout: float = 30) -> None:
        self._thread.start()
        if not self._ready.wait(timeout):
            raise TimeoutError("The browser did not start.")
        if self.open_error:
            raise ActionError(self.open_error)

    def close(self) -> None:
        self.controller.request_quit()
        self._thread.join(timeout=15)

    def _worker(self) -> None:
        try:
            self.session.open()
        except Exception as exc:
            self.open_error = str(exc).split("\n", 1)[0][:300]
            self._ready.set()
            return
        self._ready.set()
        try:
            while self.controller.wait_until_active():
                if self.controller.take_fresh():
                    if self.controller.should_stop():
                        self.controller.finish("stopped", "Stopped.")
                        continue
                    self.log.clear()
                    self.engine.reset_run()
                    try:
                        self.engine.planner = self._new_planner()
                    except PlannerError as exc:
                        self.log.error(str(exc))
                        self.controller.finish("failed", str(exc))
                        continue
                    self.log.status(
                        f"run      {self.controller.current_task()}  planner: {self.controller.planner_name}"
                    )
                if self.engine.planner is None:
                    self.controller.finish("failed", "No planner is loaded.")
                    continue
                self.engine.run()
        finally:
            self.session.close()

    def start(self, task: str, planner_name: str) -> None:
        self.controller.start(task, planner_name)

    def pause(self) -> None:
        self.controller.pause()
        self.log.status("control  pause")

    def step(self, task: str, planner_name: str) -> None:
        self.controller.step(task, planner_name)

    def stop(self) -> None:
        self.log.status("control  stop")
        self.controller.stop()

    def _new_planner(self):
        if self.planner_factory is not None:
            planner = self.planner_factory(self.controller.planner_name, self.fixture_url)
        else:
            from loop.planner import make_planner

            planner = make_planner(self.controller.planner_name, self.fixture_url)
        reset = getattr(planner, "reset", None)
        if reset is not None:
            reset()
        return planner
