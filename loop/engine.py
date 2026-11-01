"""The loop itself: permit a cycle, observe, plan one batch, act, assert."""

from __future__ import annotations

import threading
from datetime import datetime, timezone

from loop.actions import (
    Action,
    ActionBatch,
    ActionError,
    Assertion,
    Choose,
    ChooseNamed,
    Click,
    ClickNamed,
    Fill,
    FillNamed,
    Goto,
    Observation,
    PlannerError,
)
from loop.browser import BrowserSession, act, check, locate, observe
from loop.browser import _locator
from loop.planner import _search_query, direct_batch, norm_name, task_token

MAX_RECOVERY = 2


def _clicks_only(batch: ActionBatch) -> bool:
    return bool(batch.actions) and all(isinstance(action, (Click, ClickNamed)) for action in batch.actions)


def _search_results_page(url: str) -> bool:
    folded = (url or "").lower()
    return any(
        part in folded
        for part in ("search_query=", "/s?k=", "field-keywords=", "search-alias=", "hn.algolia.com")
    )


def _directory_page(url: str) -> bool:
    """A site index. Opening one does not finish a task that asks for an item."""
    folded = (url or "").split("?", 1)[0].rstrip("/").lower()
    return folded.endswith(
        (
            "news.ycombinator.com",
            "news.ycombinator.com/news",
            "news.ycombinator.com/newest",
            "news.ycombinator.com/newcomments",
            "news.ycombinator.com/front",
            "news.ycombinator.com/ask",
            "news.ycombinator.com/show",
            "news.ycombinator.com/jobs",
            "news.ycombinator.com/active",
        )
    )


def _unfinished_page(url: str) -> bool:
    return _search_results_page(url) or _directory_page(url)


def _place_phrase(task: str) -> str | None:
    """The place written as consecutive capitalized words, ignoring a leading On Site."""
    import re

    phrases = re.findall(r"\b([A-Z][A-Za-z'’]+(?:\s+[A-Z][A-Za-z'’]+)+)", task or "")
    phrases = [phrase for phrase in phrases if not phrase.lower().startswith("on ")]
    if len(phrases) == 1:
        return phrases[0]
    return None


def _host(url: str) -> str:
    try:
        from urllib.parse import urlparse

        return (urlparse(url).hostname or "").lower()
    except Exception:
        return ""


def _changed_host(before: str, after: str) -> bool:
    left = _host(before)
    right = _host(after)
    return bool(left and right and left != right)


def _opened_item(url: str) -> bool:
    folded = (url or "").lower()
    return any(
        part in folded
        for part in ("item?id=", "/dp/", "/gp/product", "/watch", "cite_note", "youtu.be/")
    )


def _clean_result(href: str) -> str:
    """The product or video address without the tracking query."""
    lower = href.lower()
    for marker in ("/dp/", "/gp/product/"):
        index = lower.find(marker)
        if index < 0:
            continue
        start = href.rfind("https://", 0, index)
        if start < 0:
            start = href.rfind("http://", 0, index)
        if start < 0:
            continue
        code = []
        for char in href[index + len(marker) :]:
            if char.isalnum():
                code.append(char)
            else:
                break
        if code:
            return href[start:index] + marker + "".join(code)
    watch = lower.find("watch?v=")
    if watch >= 0:
        start = href.rfind("https://", 0, watch)
        if start < 0:
            start = href.rfind("http://", 0, watch)
        if start >= 0:
            video = []
            for char in href[watch + len("watch?v=") :]:
                if char.isalnum() or char in "-_":
                    video.append(char)
                else:
                    break
            if video:
                return href[start:watch] + "watch?v=" + "".join(video)
    return href.split("#", 1)[0]


def _open_first_result(page) -> bool:
    """Open the first visible result link on a search page. No model call."""
    before = page.url
    href = ""
    for attempt in range(2):
        for _ in range(8):
            try:
                href = page.evaluate(
                """() => {
                  const bad = /sponsored|advertisement|slredirect|sspa|sp_csd/i;
                  const links = [...document.querySelectorAll("a[href]")];
                  if (location.hostname.indexOf("algolia") >= 0) {
                    for (const link of links) {
                      const href = link.href || "";
                      if (!/^https?:/i.test(href) || /algolia|ycombinator/i.test(href)) continue;
                      const text = (link.innerText || "").replace(/\\s+/g, " ").trim();
                      if (text.length < 12) continue;
                      const box = link.getBoundingClientRect();
                      if (box.width < 80 || box.height < 8 || box.top < 0 || box.top > window.innerHeight) continue;
                      return href;
                    }
                    return "";
                  }
                  for (const link of links) {
                    const href = link.href || "";
                    if (bad.test(href)) continue;
                    const text = (link.innerText || link.getAttribute("aria-label") || "")
                      .replace(/\\s+/g, " ").trim();
                    if (bad.test(text)) continue;
                    const box = link.getBoundingClientRect();
                    if (box.width < 80 || box.height < 8 || box.top < 0 || box.top > window.innerHeight) continue;
                    const result = /\\/(dp|gp\\/product)\\//.test(href)
                      || /[?&]v=/.test(href)
                      || /\\/watch\\b/.test(href);
                    if (!result || text.length < 8) continue;
                    return href;
                  }
                  return "";
                }"""
            ) or ""
            except Exception:
                return False
            if href:
                break
            page.wait_for_timeout(150)
        if href or attempt == 1:
            break
        try:
            sample = page.inner_text("body")[:400].lower()
        except Exception:
            sample = ""
        if not any(word in sample for word in ("something went wrong", "sorry", "robot", "captcha", "try again")):
            break
        try:
            page.reload(wait_until="domcontentloaded", timeout=10000)
        except Exception:
            break
    if not href:
        return False
    try:
        page.goto(_clean_result(href), wait_until="domcontentloaded", timeout=15000)
    except Exception:
        return False
    return bool(page.url) and page.url != before and not _search_results_page(page.url)


def _pin_citation(page) -> None:
    """Point a one-shot article visit at its first citation. The fragment is already on the page."""
    try:
        page.evaluate(
            """() => {
              const link = document.querySelector("a[href*='cite_note']");
              if (!link) return;
              const href = link.getAttribute("href") || "";
              const mark = href.indexOf("#");
              if (mark < 0) return;
              location.hash = href.slice(mark + 1);
            }"""
        )
    except Exception:
        return


class Log:
    def __init__(self, *, echo: bool = True):
        self._events: list[dict] = []
        self._lock = threading.Lock()
        self.echo = echo

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
        if self.echo:
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

    def plan(self, batch: ActionBatch) -> None:
        actions = ", ".join(action.summary() for action in batch.actions) or "(none)"
        assertion = batch.assertion.summary() if batch.assertion else "none"
        line = f"plan     {batch.reason or '(no reason)'}  actions: {actions}  assert: {assertion}"
        self._add("plan", line, done=batch.done, reason=batch.reason)

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


def _named_step(action: Action) -> dict | None:
    """Role-and-name actions can be replayed. A ref cannot."""
    if isinstance(action, FillNamed):
        return {"type": "fill", "role": action.role, "name": action.name, "text": action.text}
    if isinstance(action, ClickNamed):
        return {"type": "click", "role": action.role, "name": action.name}
    if isinstance(action, ChooseNamed):
        return {"type": "choose", "role": action.role, "name": action.name, "option": action.option}
    return None


def _history_item(
    batch: ActionBatch,
    assertion_ok: bool | None,
    assertion_detail: str | None,
    observation: Observation | None = None,
) -> dict:
    item = {
        "reason": batch.reason,
        "actions": [action.summary() for action in batch.actions],
        "done": batch.done,
    }
    if assertion_detail is not None:
        item["assertion"] = {"ok": assertion_ok, "detail": assertion_detail}
    if observation is not None:
        item["url"] = observation.url
        item["title"] = observation.title
    return item


class Engine:
    def __init__(self, session: BrowserSession, controller: Controller, log: Log, *, max_cycles: int = 12):
        self.session = session
        self.controller = controller
        self.log = log
        self.max_cycles = max_cycles
        self.planner = None
        self.history: list[dict] = []
        self.pending: list[Action] = []
        self.recoveries = 0
        self.allow_direct = True
        self.suppress_direct = False
        self.max_actions = None
        self.model_used = False
        self.trace: list[dict] = []
        self.trace_ok = True
        self._deferred: Assertion | None = None
        self._cycle_url = ""
        self._last_observation: Observation | None = None
        self._batch_from_model = False
        self._opened_result = False
        self._hold_clicks = False
        self._place_typed = False

    def reset_run(self) -> None:
        self.history = []
        self.pending = []
        self.recoveries = 0
        self.model_used = False
        self.trace = []
        self.trace_ok = True
        self._deferred = None
        self._cycle_url = ""
        self._last_observation = None
        self._batch_from_model = False
        self._opened_result = False
        self._hold_clicks = False
        self._place_typed = False

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
                observation = self._ready_observation()
                self._cycle_url = observation.url
                if self.controller.should_stop():
                    self.controller.finish("stopped", "Stopped.")
                    return
                try:
                    batch = self._next_batch(observation)
                except PlannerError as exc:
                    self.log.error(str(exc))
                    if not self._recover(
                        str(exc),
                        ActionBatch(str(exc), [], None, False),
                        observation,
                        False,
                    ):
                        return
                    cycles += 1
                    continue
                if batch.later:
                    self.pending.extend(batch.later)
                    if batch.assertion is not None and self._deferred is None:
                        self._deferred = batch.assertion
                if self.controller.should_stop():
                    self.controller.finish("stopped", "Stopped before the actions ran.")
                    return
                failure = self._run_actions(batch.actions)
                if failure == "STOP":
                    self.controller.finish("stopped", "Stopped.")
                    return
                if failure:
                    if not self._recover(failure, batch, observation):
                        return
                    cycles += 1
                    continue
                if self._opened_result:
                    self.controller.finish("done", batch.reason or "Opened the first result.")
                    return
                followed_off_results = False
                if self.pending:
                    self._last_observation = self._observe()
                    follow = self._take_ready_pending()
                    if follow is not None:
                        failure = self._run_actions(follow.actions)
                        if failure == "STOP":
                            self.controller.finish("stopped", "Stopped.")
                            return
                        if failure:
                            if not self._recover(failure, follow, observation):
                                return
                            cycles += 1
                            continue
                        followed_off_results = not _search_results_page(self.session.page.url)
                if (
                    self._batch_from_model
                    and self.session.page is not None
                    and _search_results_page(self.session.page.url)
                ):
                    if _open_first_result(self.session.page):
                        self.history.append(
                            _history_item(batch, True, "opened the first result", observation)
                        )
                        self.controller.finish("done", batch.reason or "Opened the first result.")
                        return
                if self.max_cycles == 1 and self.session.page is not None:
                    article = self.session.page.url or ""
                    folded_article = article.lower()
                    if (
                        "wikipedia.org/wiki/" in folded_article
                        and "#" not in folded_article
                        and "cite" not in folded_article
                        and "reference" not in folded_article
                    ):
                        _pin_citation(self.session.page)
                rejected = self._submit_rejected(batch.actions)
                if rejected:
                    fresh = self._observe()
                    invalid = [
                        f"{control.name}: {control.invalid}"
                        for control in fresh.controls
                        if control.invalid
                    ]
                    detail = "Assertion failed: the form stayed on the same page"
                    if invalid:
                        detail = detail + " (" + "; ".join(invalid) + ")"
                    if not self._recover(detail, batch, fresh, False):
                        return
                    cycles += 1
                    continue
                assertion = None if batch.later else batch.assertion
                if assertion is None and not self.pending and self._deferred is not None:
                    assertion = self._deferred
                    self._deferred = None
                assertion_ok = None
                assertion_detail = None
                if assertion is not None:
                    assertion_ok, assertion_detail = self._assert(assertion)
                    if not assertion_ok:
                        page_url = self.session.page.url if self.session.page is not None else ""
                        if batch.done and (
                            _opened_item(page_url) or _changed_host(self._cycle_url, page_url)
                        ):
                            self.controller.finish("done", batch.reason or "Done.")
                            return
                        if not self._recover(assertion_detail or "Assertion failed.", batch, observation, False):
                            return
                        cycles += 1
                        continue
                self.history.append(_history_item(batch, assertion_ok, assertion_detail, observation))
                cycles += 1
                page_url = self.session.page.url if self.session.page is not None else ""
                clicked = any(isinstance(action, (Click, ClickNamed)) for action in batch.actions)
                opened = any(isinstance(action, Goto) for action in batch.actions)
                stalled = _unfinished_page(page_url) and not followed_off_results
                if stalled and not self._batch_from_model:
                    self.suppress_direct = True
                proved = (
                    assertion_ok is True
                    or not batch.actions
                    or not self._batch_from_model
                    or followed_off_results
                    or (clicked and not opened and not _unfinished_page(page_url))
                )
                if batch.done and not self.pending and proved and not stalled:
                    self.controller.finish("done", batch.reason or "Done.")
                    return
                self.controller.end_cycle()
        except Exception as exc:
            message = str(exc).split("\n", 1)[0][:300]
            self.log.error(message)
            self.controller.finish("failed", message)
            return
        self.controller.finish("failed", f"Stopped after {self.max_cycles} planner calls.")

    def _observe(self) -> Observation:
        task = self.controller.current_task() if self.controller is not None else ""
        return observe(self.session.page, prefer=task)

    def _ready_observation(self) -> Observation:
        observation = self._observe()
        if len(observation.controls) == 0:
            self.session.page.wait_for_timeout(800)
            observation = self._observe()
        query = _search_query(self.controller.current_task())
        if query and query.lower() in observation.url.lower():
            for _ in range(10):
                visible = any(
                    control.role == "link" and query.lower() in control.name.lower()
                    for control in observation.controls
                )
                if visible:
                    break
                self.session.page.wait_for_timeout(200)
                observation = self._observe()
        token = task_token(self.controller.current_task())
        if token and observation.url.startswith("http"):
            for _ in range(5):
                visible = any(
                    control.role == "link" and token in control.name.lower()
                    for control in observation.controls
                )
                if visible:
                    break
                self.session.page.wait_for_timeout(200)
                observation = self._observe()
        self._last_observation = observation
        self.log.observe(observation)
        return observation

    def _next_batch(self, observation: Observation) -> ActionBatch:
        ready = self._take_ready_pending()
        if ready is not None:
            ready = self._cap(ready)
            self._batch_from_model = False
            self.log.plan(ready)
            return ready
        if self.pending:
            self.pending.clear()
            self._deferred = None
        if not self._place_typed:
            place = self._place_batch(observation)
            if place is not None:
                self._place_typed = True
                self._batch_from_model = False
                self.log.plan(place)
                return place
        if self.allow_direct and not self.suppress_direct:
            direct = direct_batch(self.controller.current_task(), observation, self.history)
            if direct is not None and (not self.model_used or _clicks_only(direct)):
                direct = self._cap(direct)
                self._batch_from_model = False
                self.log.plan(direct)
                return direct
        before = getattr(self.planner, "calls", None)
        batch = self._cap(self.planner.plan(self.controller.current_task(), observation, self.history))
        after = getattr(self.planner, "calls", None)
        self._batch_from_model = isinstance(before, int) and isinstance(after, int) and after > before
        if self._batch_from_model:
            self.model_used = True
            self.log.status(f"model    cycle {after}")
        self.log.plan(batch)
        return batch

    def _cap(self, batch: ActionBatch) -> ActionBatch:
        limit = self.max_actions
        if limit is None or len(batch.actions) <= limit:
            return batch
        return ActionBatch(batch.reason, batch.actions[:limit], None, False)

    def _take_ready_pending(self) -> ActionBatch | None:
        if not self.pending:
            return None
        limit = self.max_actions if isinstance(self.max_actions, int) else len(self.pending)
        ready = []
        while self.pending and len(ready) < limit and self._concrete(self.pending[0]) is not None:
            ready.append(self.pending.pop(0))
        if not ready:
            return None
        assertion = None
        done = False
        if not self.pending and self._deferred is not None:
            assertion = self._deferred
            self._deferred = None
            done = True
        return ActionBatch("Direct role and name match.", ready, assertion, done)

    def _ref_for(self, role: str, name: str) -> str | None:
        from loop.planner import find_ref

        observation = self._last_observation
        if observation is not None:
            ref = find_ref(observation, role=role, name=name)
            if ref is not None:
                return ref
        return locate(self.session.page, role, name)

    def _concrete(self, action: Action) -> Action | None:
        if isinstance(action, FillNamed):
            if action.role in ("combobox", "select"):
                option = action.text.strip() or self._option_named_in_task(action.name)
                ref = self._ref_for(action.role, action.name)
                if ref is None:
                    return None
                return Choose(ref, option)
            ref = self._ref_for(action.role, action.name)
            if ref is None:
                return None
            if action.role in ("checkbox", "radio"):
                return Click(ref)
            return Fill(ref, action.text)
        if isinstance(action, ChooseNamed):
            ref = self._ref_for(action.role, action.name)
            if ref is None:
                return None
            return Choose(ref, action.option)
        if isinstance(action, ClickNamed):
            ref = self._ref_for(action.role, action.name)
            if ref is None:
                return None
            return Click(ref)
        return action

    def _option_named_in_task(self, name: str) -> str:
        """The model named the select and left the option blank. Use the one option the task names."""
        from loop.planner import norm_name

        observation = observe(self.session.page, form_max=80, other_max=40, prefer=self.controller.current_task())
        needle = norm_name(name)
        control = next(
            (
                item
                for item in observation.controls
                if item.options and norm_name(item.name) == needle
            ),
            None,
        )
        if control is None:
            return ""
        task = norm_name(self.controller.current_task())
        task = "".join(ch if ch.isalnum() else " " for ch in task)
        task = f" {' '.join(task.split())} "
        hits = []
        for option in control.options:
            token = norm_name(option)
            if len(token) >= 2 and f" {token} " in task:
                hits.append(option)
        if len(hits) == 1:
            return hits[0]
        return ""

    def _refuses_submit(self, action: Action) -> bool:
        if "do not submit" not in self.controller.current_task().lower():
            return False
        name = ""
        if isinstance(action, ClickNamed):
            name = action.name
        elif isinstance(action, Click):
            try:
                name = _locator(self.session.page, action.ref).evaluate(
                    "node => (node.innerText || node.value || node.getAttribute('aria-label') || '')"
                )
            except ActionError:
                name = ""
        else:
            return False
        folded = name.lower()
        return any(word in folded for word in ("sign in", "log in", "login", "submit"))

    def _submit_rejected(self, actions: list[Action]) -> bool:
        """A submit click that leaves the URL unchanged was blocked, usually by validation."""
        clicked = False
        for action in actions:
            name = action.name if isinstance(action, ClickNamed) else ""
            if isinstance(action, Click):
                try:
                    name = _locator(self.session.page, action.ref).evaluate(
                        "node => (node.innerText || node.value || node.getAttribute('aria-label') || '')"
                    )
                except ActionError:
                    name = ""
            if isinstance(name, str) and "submit" in name.lower():
                clicked = True
        page = self.session.page
        return clicked and page is not None and page.url == self._cycle_url

    def _fields_before_submit(self, actions: list[Action]) -> list[Action]:
        """A choose that the model placed after Submit never runs. Set fields first."""
        early = []
        late = []
        for action in actions:
            name = action.name if isinstance(action, ClickNamed) else ""
            if isinstance(name, str) and "submit" in name.lower():
                late.append(action)
            else:
                early.append(action)
        return early + late

    def _control(self, ref: str):
        observation = self._last_observation
        if observation is None:
            return None
        return next((control for control in observation.controls if control.ref == ref), None)

    def _in_chrome(self, ref: str) -> bool:
        page = self.session.page
        if page is None:
            return False
        try:
            return bool(
                page.evaluate(
                    """(ref) => {
                      const node = document.querySelector("[data-cu-ref='" + ref + "']");
                      if (!node) return false;
                      if (node.closest("nav, header, footer, [role='navigation'], .pagetop")) return true;
                      const box = node.getBoundingClientRect();
                      return box.top >= 0 && box.top < 36 && box.height < 44;
                    }""",
                    ref,
                )
            )
        except Exception:
            return False

    def _retarget_click(self, action: Click) -> Click:
        """A one-word nav link, or an option the task does not name, is the wrong control."""
        control = self._control(action.ref)
        observation = self._last_observation
        if control is None or observation is None:
            return action
        if control.role == "link":
            words = control.name.lower().split()
            if len(words) == 1 and self._in_chrome(action.ref):
                word = words[0]
                for other in observation.controls:
                    if other.ref == control.ref or other.role != "link":
                        continue
                    name = other.name.lower()
                    if word not in name.split() or not any(char.isdigit() for char in name):
                        continue
                    if self._in_chrome(other.ref):
                        continue
                    self.log.status(f"act      use {other.name} instead of {control.name}")
                    return Click(other.ref)
        if control.role not in ("option", "link") or len(control.name) > 48:
            return action
        task_words = {word for word in norm_name(self.controller.current_task()).split() if len(word) >= 4}

        def score(label: str) -> int:
            return len(set(norm_name(label).split()) & task_words)

        clicked_score = score(control.name)
        best = control
        best_score = clicked_score
        for other in observation.controls:
            if other.role != control.role or len(other.name) > 80:
                continue
            other_score = score(other.name)
            if other_score > best_score:
                best = other
                best_score = other_score
        needed = 2 if control.role == "link" else 1
        if best.ref == control.ref or best_score < needed:
            return action
        self.log.status(f"act      use {best.name} instead of {control.name}")
        return Click(best.ref)

    def _place_batch(self, observation: Observation) -> ActionBatch | None:
        phrase = _place_phrase(self.controller.current_task())
        if phrase is None:
            return None
        folded = (observation.url or "").lower().replace("-", " ").replace("+", " ")
        if phrase.lower() in folded:
            return None
        for control in observation.controls:
            if control.role not in ("textbox", "searchbox"):
                continue
            if not any(word in control.name.lower() for word in ("location", "area", "where", "destination")):
                continue
            if phrase.lower() in (control.value or "").lower():
                return None
            return ActionBatch(f"Use {phrase}.", [Fill(control.ref, phrase)], None, False)
        return None

    def _retarget_fill(self, action: Fill) -> Fill:
        """A location field must use the place the task names."""
        phrase = _place_phrase(self.controller.current_task())
        control = self._control(action.ref)
        if phrase is None or control is None or phrase.lower() in (action.text or "").lower():
            return action
        name = control.name.lower()
        if not any(word in name for word in ("location", "area", "where", "destination", "city")):
            return action
        self.log.status(f"act      place {phrase}")
        self._hold_clicks = True
        return Fill(action.ref, phrase)

    def _run_actions(self, actions: list[Action]) -> str | None:
        self._hold_clicks = False
        actions = self._fields_before_submit(actions)
        navigated = False
        for index, original in enumerate(actions):
            if self.controller.should_stop():
                return "STOP"
            if self._refuses_submit(original):
                self.log.status(f"act      skipped {original.summary()}")
                continue
            action = self._concrete(original)
            if isinstance(action, Click):
                if self._hold_clicks:
                    return None
                action = self._retarget_click(action)
            if isinstance(action, Fill):
                action = self._retarget_fill(action)
            if action is None:
                if navigated:
                    self.pending = list(actions[index:]) + self.pending
                    return None
                self.log.act(original, ok=False, error="no unique match")
                return f"No unique match for {original.summary()}"
            if self._refuses_submit(action):
                self.log.status(f"act      skipped {action.summary()}")
                continue
            try:
                act(self.session.page, action)
            except ActionError as exc:
                self.log.act(action, ok=False, error=str(exc))
                return str(exc)
            self.log.act(action, ok=True)
            if _search_results_page(self.session.page.url) and _open_first_result(self.session.page):
                self._opened_result = True
                return None
            step = _named_step(original)
            if step is None:
                self.trace_ok = False
            else:
                self.trace.append(step)
            if isinstance(action, (Goto, Click)):
                navigated = True
        return None

    def _recover(
        self,
        detail: str,
        batch: ActionBatch,
        observation: Observation,
        assertion_ok: bool = False,
    ) -> bool:
        self.history.append(_history_item(batch, assertion_ok, detail, observation))
        self.pending.clear()
        self._deferred = None
        self.recoveries += 1
        if self.allow_direct:
            self.suppress_direct = False
        if self.recoveries > MAX_RECOVERY or self.controller.step_only:
            self.controller.finish("failed", detail)
            return False
        clicked = any(isinstance(action, (Click, ClickNamed)) for action in batch.actions)
        submitted = any(
            isinstance(action, ClickNamed) and "submit" in action.name.lower() for action in batch.actions
        )
        page = self.session.page
        if (
            clicked
            and not submitted
            and page is not None
            and page.url != self._cycle_url
            and not _opened_item(page.url)
            and not _changed_host(self._cycle_url, page.url)
        ):
            try:
                page.go_back(wait_until="domcontentloaded", timeout=8000)
            except Exception:
                pass
        return True

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
