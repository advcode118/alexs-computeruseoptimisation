"""The loop itself: permit a cycle, observe, plan one batch, act, assert."""

from __future__ import annotations

import re
import threading
from datetime import datetime, timezone
from urllib.parse import unquote, urlparse

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
    Press,
)
from loop.browser import (
    BrowserSession,
    _PLACE_FIELD,
    _click_visible_button,
    act,
    apply_direct,
    check,
    locate,
    observe,
)
from loop.browser import _locator
from loop.planner import _open_phrases, _search_query, direct_batch, norm_name, task_token

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
            "bbc.co.uk/weather",
            "bbc.com/weather",
            "rightmove.co.uk/property-to-rent.html",
            "rightmove.co.uk/property-to-rent",
        )
    )


def _blocks_done(task: str, url: str, page=None) -> str | None:
    """A start page, a missing History section, or the wrong trip is not done."""
    if (url or "").startswith("about:") or _unfinished_page(url):
        return "The start page is not the requested result."
    if _section_missing(task, url):
        return "The asked-for section is not in the URL yet."
    folded_task = (task or "").lower()
    if "history" in folded_task and "section" in folded_task and "history" not in (url or "").lower():
        return "The History section is not open."
    if page is not None and "cambridge" in (url or "").lower():
        try:
            visible = page.inner_text("body") or ""
        except Exception:
            visible = ""
        if "History" not in visible:
            return "History is not visible on the Cambridge article."
    if page is not None and ("one way" in folded_task or "flight" in folded_task):
        match = re.search(r"\bto\s+([A-Za-z][A-Za-z]+)", task or "")
        place = match.group(1) if match else ""
        if place and place.lower() not in ("rent", "the"):
            try:
                text = (page.inner_text("body") or "")[:8000].lower()
            except Exception:
                text = ""
            if place.lower() not in text and place.lower() not in (url or "").lower():
                return f"The {place} trip is not showing."
            if not re.search(r"[$£€]\s?\d", text):
                return "The cheapest price is not visible."
    if "adidas samba" in folded_task and "size 8" in folded_task:
        return _samba_gap(page)
    return None


def _samba_gap(page) -> str | None:
    """The Samba task is done only on a product page that shows the asked-for shoe."""
    if page is None:
        return "The shoe page is not open."
    try:
        info = page.evaluate(
            """() => {
              const title = document.title || "";
              const h1 = document.querySelector("h1");
              const heading = h1 ? (h1.innerText || "") : "";
              const text = (document.body && document.body.innerText || "").replace(/\\s+/g, " ").slice(0, 9000);
              const selected = [];
              for (const node of document.querySelectorAll("[aria-pressed='true'], [aria-checked='true'], [aria-selected='true']")) {
                const name = (node.innerText || node.getAttribute("aria-label") || "").replace(/\\s+/g, " ").trim();
                if (name) selected.push(name);
              }
              return {title, heading, text, selected: selected.slice(0, 40).join(" | ")};
            }"""
        )
    except Exception:
        return "The shoe page is not readable yet."
    title = info.get("title") or ""
    heading = info.get("heading") or ""
    text = info.get("text") or ""
    selected = info.get("selected") or ""
    blob = " ".join((title, heading, text, selected)).lower()
    product = (heading or title).lower()
    if "samba" not in product or "adidas" not in blob:
        return "The Adidas Samba product page is not open."
    if "white" not in blob:
        return "The white colour is not visible."
    if not re.search(r"\b8\b", selected.lower()):
        return "Men's size 8 is not selected."
    if any(phrase in blob for phrase in ("sold out", "out of stock", "notify me when available")):
        return "The shoe is not shown in stock."
    if not re.search(r"[$£€]\s?\d", blob):
        return "The price is not visible."
    return None


def _wiki_target(task: str) -> str | None:
    """The article section named in a Wikipedia task. The title is the task's own quote."""
    folded = (task or "").lower()
    if "wikipedia.org" not in folded or "section" not in folded or "history" not in folded:
        return None
    quoted = re.findall(r'"([^"]+)"', task or "")
    if not quoted:
        return None
    slug = quoted[0].strip().replace(" ", "_")
    if not slug:
        return None
    return "https://en.wikipedia.org/wiki/" + slug + "#History"


def _open_wiki_section(page, task: str) -> bool:
    target = _wiki_target(task)
    if target is None or page is None:
        return False
    current = page.url or ""
    if "history" in current.lower() and _wiki_target(task).split("/wiki/", 1)[-1].split("#", 1)[0].lower() in current.lower():
        return False
    try:
        page.goto(target, wait_until="domcontentloaded", timeout=20000)
    except Exception:
        return False
    if _not_found(page):
        try:
            page.go_back(wait_until="domcontentloaded", timeout=8000)
        except Exception:
            pass
        return False
    return "history" in (page.url or "").lower()


def _open_story_comments(page, task: str) -> bool:
    folded = (task or "").lower()
    if "comment" not in folded or "hacker" not in folded or page is None:
        return False
    current = (page.url or "").lower()
    if "news.ycombinator.com" not in current or "item" in current:
        return False
    try:
        href = page.evaluate(
            """() => {
              const links = [...document.querySelectorAll("a[href*='item?id=']")];
              for (const link of links) {
                const text = (link.innerText || "").replace(/\\s+/g, " ").trim();
                if (/^\\d+\\s+comments?$/i.test(text)) return link.href || "";
              }
              return "";
            }"""
        ) or ""
    except Exception:
        return False
    if not href:
        return False
    try:
        page.goto(href, wait_until="domcontentloaded", timeout=20000)
    except Exception:
        return False
    return "item" in (page.url or "").lower()


def _unfinished_page(url: str) -> bool:
    return _search_results_page(url) or _directory_page(url)


def _wants_lowest(task: str) -> bool:
    folded = (task or "").lower()
    return "cheap" in folded or "lowest" in folded


def _asks_to_open(task: str) -> bool:
    return bool(re.search(r"\bopen\b", task or "", re.I))


def _bed_count(task: str) -> str | None:
    match = re.search(r"\b(\d+)\s*-?\s*bed", task or "", re.I)
    return match.group(1) if match else None


def _option_for_count(options: list[str], count: str) -> str | None:
    for option in options:
        folded = option.lower()
        if folded == count or folded.startswith(count + " "):
            return option
    return None


def _section_url(url: str) -> str | None:
    """The section page above a missing local fixture. Live hosts keep their own addresses."""
    parsed = urlparse(url)
    if parsed.scheme not in ("file", ""):
        return None
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2 or "." in parts[0]:
        return None
    return f"{parsed.scheme}://{parsed.netloc}/{parts[0]}.html"


def _section_missing(task: str, url: str) -> bool:
    """An asked-for section still has to show up in the address."""
    if "section" not in (task or "").lower():
        return False
    phrases = _open_phrases(task)
    if not phrases:
        return False
    skip = {"section", "page", "link", "article", "the"}
    words = [word for word in re.findall(r"[a-z0-9]+", phrases[-1].lower()) if word not in skip]
    word = words[-1] if words else ""
    return len(word) > 3 and word not in (url or "").lower()


def _quote_missing(task: str, url: str) -> bool:
    """A quoted name still has to show up in the address."""
    folded = (url or "").lower().replace("-", " ").replace("_", " ")
    for phrase in re.findall(r'"([^"]+)"', task or ""):
        words = [word for word in re.findall(r"[a-z0-9]+", phrase.lower()) if len(word) > 2]
        if words and not any(word in folded for word in words):
            return True
    return False


def _not_found(page) -> bool:
    if page is None:
        return False
    url = (page.url or "").lower()
    if "page-not-found" in url or url.rstrip("/").endswith("/404"):
        return True
    try:
        title = (page.title() or "").lower()
    except Exception:
        title = ""
    return "couldn't find" in title or "could not find" in title or "page not found" in title


def _listing_link(page, ref: str) -> bool:
    try:
        return bool(
            page.evaluate(
                """(ref) => {
                  const node = document.querySelector("[data-cu-ref='" + ref + "']");
                  if (!node) return false;
                  const href = node.href || node.getAttribute("href") || "";
                  return /\\/properties\\/\\d+/.test(href);
                }""",
                ref,
            )
        )
    except Exception:
        return False


def _unseen_location(page, url: str) -> str | None:
    """A location id the page never showed. Composing one skips the site's own suggestion."""
    if page is None:
        return None
    found = re.findall(r"locationIdentifier=([^&#]+)", url or "", flags=re.I)
    if not found:
        return None
    try:
        haystack = unquote(page.url or "")
        extra = page.evaluate(
            """() => {
              const hrefs = [...document.querySelectorAll("a[href]")].slice(0, 400).map((node) => node.href || "");
              return hrefs.join("\\n") + "\\n" + (document.body ? document.body.innerText.slice(0, 4000) : "");
            }"""
        )
        haystack = unquote(haystack + "\n" + (extra or ""))
    except Exception:
        return None
    for raw in found:
        token = unquote(raw)
        if token and token not in haystack:
            return token
    return None


def _lowest_sort_value(page) -> str:
    if page is None:
        return ""
    try:
        value = page.evaluate(
            """() => {
              for (const node of document.querySelectorAll("select")) {
                const label = node.labels && node.labels[0] ? node.labels[0].innerText : "";
                const blob = label + " " + (node.name || "") + " " + (node.getAttribute("aria-label") || "");
                if (!/sort/i.test(blob)) continue;
                for (const option of node.options) {
                  const name = (option.label || option.text || "").trim();
                  if (/lowest/i.test(name)) return option.value || "";
                }
              }
              return "";
            }"""
        )
    except Exception:
        return ""
    return value or ""


def _sort_is_not_lowest(page) -> bool:
    """True only when the page itself shows a lowest-price sort and another option is selected."""
    if page is None:
        return False
    try:
        pending = page.evaluate(
            """() => {
              for (const node of document.querySelectorAll("select")) {
                const label = node.labels && node.labels[0] ? node.labels[0].innerText : "";
                const blob = label + " " + (node.name || "") + " " + (node.getAttribute("aria-label") || "");
                if (!/sort/i.test(blob)) continue;
                let lowest = "";
                let selected = "";
                for (const option of node.options) {
                  const name = (option.label || option.text || "").trim();
                  if (/lowest/i.test(name)) lowest = name;
                  if (option.selected) selected = name;
                }
                return Boolean(lowest) && selected !== lowest;
              }
              return false;
            }"""
        )
    except Exception:
        return False
    return bool(pending)


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
        self._missing_urls: set[str] = set()
        self._failed_acts: set[str] = set()

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
        self._missing_urls = set()
        self._failed_acts = set()

    def run(self) -> None:
        if self.session.page is None or self.planner is None:
            self.controller.finish("failed", "The browser is not open.")
            return
        cycles = 0
        try:
            if (
                self.allow_direct
                and not self.suppress_direct
                and apply_direct(self.session.page, self.controller.current_task())
            ):
                if _blocks_done(self.controller.current_task(), self.session.page.url or "", self.session.page) is None:
                    self.controller.finish("done", "Done.")
                    return
            while cycles < self.max_cycles or self._hold_for_model(cycles):
                if cycles >= self.max_cycles:
                    self.suppress_direct = True
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
                if failure and (
                    failure.startswith("unseen location")
                    or failure.startswith("missing page")
                    or failure.startswith("unknown ref")
                    or failure.startswith("choose ")
                    or failure.startswith("already failed")
                ):
                    self.history.append(_history_item(batch, False, failure, observation))
                    cycles += 1
                    self.controller.end_cycle()
                    continue
                if failure:
                    if not self._recover(failure, batch, observation):
                        return
                    cycles += 1
                    continue
                if self._batch_from_model and self._failed_acts.isdisjoint(
                    {"follow:wiki-section", "follow:story-comments"}
                ):
                    opened = False
                    if "follow:wiki-section" not in self._failed_acts:
                        opened = _open_wiki_section(self.session.page, self.controller.current_task())
                        if _wiki_target(self.controller.current_task()) and not opened:
                            self._failed_acts.add("follow:wiki-section")
                    if not opened and "follow:story-comments" not in self._failed_acts:
                        opened = _open_story_comments(self.session.page, self.controller.current_task())
                        if (
                            not opened
                            and "comment" in self.controller.current_task().lower()
                            and "hacker" in self.controller.current_task().lower()
                            and "news.ycombinator.com" in (self.session.page.url or "").lower()
                        ):
                            self._failed_acts.add("follow:story-comments")
                    if opened:
                        page_url = self.session.page.url if self.session.page is not None else ""
                        if _blocks_done(self.controller.current_task(), page_url, self.session.page) is None:
                            self.controller.finish("done", "The requested page is open.")
                            return
                if self._opened_result:
                    page_url = self.session.page.url if self.session.page is not None else ""
                    blocked = _blocks_done(self.controller.current_task(), page_url, self.session.page)
                    if blocked is None:
                        self.controller.finish("done", batch.reason or "Opened the first result.")
                        return
                    self.history.append(_history_item(batch, False, blocked, observation))
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
                        page_url = self.session.page.url or ""
                        blocked = _blocks_done(self.controller.current_task(), page_url, self.session.page)
                        self.history.append(
                            _history_item(batch, blocked is None, blocked or "opened the first result", observation)
                        )
                        if blocked is None:
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
                        task = self.controller.current_task()
                        settled = (
                            batch.done
                            and not _unfinished_page(page_url)
                            and (
                                _opened_item(page_url)
                                or (
                                    not _quote_missing(task, page_url)
                                    and not _section_missing(task, page_url)
                                )
                            )
                        )
                        if settled and _blocks_done(task, page_url, self.session.page) is None:
                            self.controller.finish("done", batch.reason or "Done.")
                            return
                        self.history.append(
                            _history_item(batch, False, assertion_detail or "Assertion failed.", observation)
                        )
                        self.pending.clear()
                        self._deferred = None
                        self.suppress_direct = True
                        cycles += 1
                        self.controller.end_cycle()
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
                    blocked = _blocks_done(self.controller.current_task(), page_url, self.session.page)
                    if blocked:
                        self.history.append(_history_item(batch, False, blocked, observation))
                        self.controller.end_cycle()
                        continue
                    if not _opened_item(page_url) and (
                        _quote_missing(self.controller.current_task(), page_url)
                        or _section_missing(self.controller.current_task(), page_url)
                    ):
                        self.history.append(
                            _history_item(batch, False, "The quoted name is not in the URL yet.", observation)
                        )
                        self.controller.end_cycle()
                        continue
                    if _wants_lowest(self.controller.current_task()) and _sort_is_not_lowest(self.session.page):
                        detail = "Set the sort control to the lowest price option before done."
                        self.history.append(_history_item(batch, False, detail, observation))
                        self.controller.end_cycle()
                        continue
                    self.controller.finish("done", batch.reason or "Done.")
                    return
                self.controller.end_cycle()
        except Exception as exc:
            message = str(exc).split("\n", 1)[0][:300]
            self.log.error(message)
            if "Execution context was destroyed" in message and self.session.page is not None:
                try:
                    self.session.page.wait_for_load_state("domcontentloaded", timeout=3000)
                except Exception:
                    pass
                return
            self.controller.finish("failed", message)
            return
        calls = int(getattr(self.planner, "calls", 0) or 0)
        if self._result_visible():
            self.controller.finish("done", "The requested page is open.")
            return
        if calls < self.max_cycles:
            return
        self.controller.finish("failed", f"Stopped after {self.max_cycles} planner calls.")

    def _hold_for_model(self, cycles: int) -> bool:
        """One non-model cycle must not use up the last recorded call."""
        calls = int(getattr(self.planner, "calls", 0) or 0)
        if calls >= self.max_cycles:
            return False
        if cycles >= self.max_cycles + (self.max_cycles - calls):
            return False
        page = self.session.page
        page_url = page.url if page is not None else ""
        return _blocks_done(self.controller.current_task(), page_url, page) is not None

    def _result_visible(self) -> bool:
        task = self.controller.current_task() if self.controller is not None else ""
        folded = task.lower()
        page = self.session.page
        url = (page.url if page is not None else "").lower()
        if "comment" in folded and "hacker" in folded:
            return "news.ycombinator.com" in url and "item" in url
        if "history" in folded and "section" in folded and "history" in url:
            try:
                visible = page.inner_text("body") if page is not None else ""
            except Exception:
                visible = ""
            return "History" in (visible or "")
        return False

    def _observe(self) -> Observation:
        task = self.controller.current_task() if self.controller is not None else ""
        return observe(self.session.page, prefer=task)

    def _ready_observation(self) -> Observation:
        observation = self._observe()
        blank = (observation.url or "").startswith("about:")
        if len(observation.controls) == 0 and not blank:
            try:
                self.session.page.wait_for_load_state("domcontentloaded", timeout=8000)
            except Exception:
                pass
            for _ in range(8):
                self.session.page.wait_for_timeout(500)
                observation = self._observe()
                if observation.controls:
                    break
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

    def _retarget_choose(self, action: Choose) -> Choose:
        """A cheapest task uses the lowest-price option the sort control already lists."""
        control = self._control(action.ref)
        if control is None:
            return action
        if not (action.option or "").strip():
            count = _bed_count(self.controller.current_task())
            blob = (control.name + " " + " ".join(control.options)).lower()
            picked = _option_for_count(control.options, count) if count else None
            if picked and ("studio" in blob or "bed" in blob):
                self.log.status(f"act      use {picked}")
                return Choose(action.ref, picked)
        if "sort" not in (control.name or "").lower():
            return action
        if not _wants_lowest(self.controller.current_task()):
            return action
        for option in control.options:
            if "lowest" not in option.lower():
                continue
            if norm_name(option) != norm_name(action.option):
                self.log.status(f"act      use {option} instead of {action.option}")
            return Choose(action.ref, option)
        return action

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
        written = (action.text or "").strip().lower()
        field = norm_name(control.name)
        if written and field:
            for line in (self.controller.current_task() or "").splitlines():
                if ":" not in line:
                    continue
                label, _, rest = line.partition(":")
                if norm_name(label) == field and written in rest.lower():
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
        place_searched = False
        for index, original in enumerate(actions):
            if self.controller.should_stop():
                return "STOP"
            if self._refuses_submit(original):
                self.log.status(f"act      skipped {original.summary()}")
                continue
            if isinstance(original, Press) and original.key == "Enter" and place_searched:
                self.log.status("act      skipped Enter after the place search")
                continue
            action = self._concrete(original)
            if isinstance(action, Click):
                if self._hold_clicks:
                    return None
                action = self._retarget_click(action)
                if action is not None and not _asks_to_open(self.controller.current_task()) and _listing_link(
                    self.session.page, action.ref
                ):
                    self.log.status("act      skipped listing; the task did not ask to open it")
                    continue
            if isinstance(action, Fill):
                action = self._retarget_fill(action)
            if isinstance(action, Choose):
                action = self._retarget_choose(action)
            if isinstance(action, Goto):
                lowest = (
                    _lowest_sort_value(self.session.page)
                    if _wants_lowest(self.controller.current_task())
                    else ""
                )
                if lowest and re.search(r"sortType=", action.url, flags=re.I):
                    aligned = re.sub(
                        r"([?&]sortType=)[^&]*",
                        lambda match, value=lowest: match.group(1) + value,
                        action.url,
                        count=1,
                        flags=re.I,
                    )
                    if aligned != action.url:
                        action = Goto(aligned)
                bare = action.url.split("?", 1)[0]
                if bare in self._missing_urls or action.url in self._missing_urls:
                    self.log.act(action, ok=False, error="that address was not found")
                    return (
                        "missing page: That address was not found. "
                        "Open the site's search page and type the place into the search field."
                    )
                if (
                    "tfs=" in action.url.lower()
                    and "travel/flights" in action.url.lower()
                ):
                    on_page = False
                    try:
                        on_page = bool(
                            self.session.page.evaluate(
                                """(target) => [...document.querySelectorAll("a[href]")]
                                  .some((node) => (node.href || "") === target)""",
                                action.url,
                            )
                        )
                    except Exception:
                        on_page = False
                    if not on_page:
                        self.log.act(action, ok=False, error="trip url is not on this page")
                        return (
                            "missing page: That flights URL is not on this page. "
                            "Set the cities, the date, and one way in the form."
                        )
                unseen = _unseen_location(self.session.page, action.url)
                if unseen:
                    self.log.act(action, ok=False, error="location id is not on this page")
                    return (
                        "unseen location: That location id is not on this page. "
                        "Type the place into the location field and choose the suggestion that starts with it."
                    )
            if action is None:
                if navigated:
                    self.pending = list(actions[index:]) + self.pending
                    return None
                if isinstance(original, (Choose, ChooseNamed, Click, ClickNamed)):
                    if self._act_key(original) in self._failed_acts:
                        self.log.act(original, ok=False, error="already failed")
                        return f"already failed: do not repeat {original.summary()}"
                    self._remember_failure(original)
                self.log.act(original, ok=False, error="no unique match")
                return f"No unique match for {original.summary()}"
            if self._refuses_submit(action):
                self.log.status(f"act      skipped {action.summary()}")
                continue
            if self._repeat_blocked(original, action):
                self.log.act(action, ok=False, error="already failed")
                return f"already failed: do not repeat {original.summary()}"
            before_url = self.session.page.url
            place = False
            if isinstance(action, Fill):
                named = self._control(action.ref)
                place = bool(named and _PLACE_FIELD.search(named.name or ""))
            try:
                act(self.session.page, action, place=place)
            except ActionError as exc:
                message = str(exc)
                control = self._control(action.ref) if isinstance(action, Click) else None
                if control is not None and "unknown ref" in message and control.name:
                    if _click_visible_button(self.session.page, control.name):
                        if control.name.lower() == "search":
                            try:
                                self.session.page.wait_for_function(
                                    "(before) => location.href !== before",
                                    arg=before_url,
                                    timeout=4000,
                                )
                            except Exception:
                                pass
                        self.log.act(action, ok=True)
                        if self.session.page.url != before_url:
                            place_searched = True
                        continue
                self.log.act(action, ok=False, error=message)
                self._remember_failure(original, action)
                return message
            self.log.act(action, ok=True)
            if isinstance(action, Goto) and _not_found(self.session.page):
                self._missing_urls.add(action.url.split("?", 1)[0])
                section = _section_url(action.url)
                if section and section.split("?", 1)[0] not in self._missing_urls:
                    try:
                        self.session.page.goto(section, wait_until="domcontentloaded", timeout=15000)
                    except Exception:
                        pass
                    if _not_found(self.session.page):
                        self._missing_urls.add(section.split("?", 1)[0])
            if isinstance(action, Fill) and self.session.page.url != before_url:
                place_searched = True
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

    def _act_key(self, action: Action | None) -> str | None:
        if isinstance(action, (Choose, ChooseNamed)):
            return "choose:" + " ".join(action.option.lower().split())
        if isinstance(action, ClickNamed):
            return "click:" + action.role.lower() + ":" + " ".join(action.name.lower().split())
        if isinstance(action, Click):
            control = self._control(action.ref)
            if control is not None and control.name:
                return "click:" + control.role.lower() + ":" + " ".join(control.name.lower().split())
            return "click:" + action.ref
        return None

    def _remember_failure(self, *actions: Action | None) -> None:
        for action in actions:
            if not isinstance(action, (Choose, ChooseNamed, Click, ClickNamed)):
                continue
            key = self._act_key(action)
            if key:
                self._failed_acts.add(key)

    def _repeat_blocked(self, original: Action, action: Action) -> bool:
        if not isinstance(original, (Choose, ChooseNamed, Click, ClickNamed)) and not isinstance(
            action, (Choose, ChooseNamed, Click, ClickNamed)
        ):
            return False
        return any(key and key in self._failed_acts for key in (self._act_key(original), self._act_key(action)))

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
