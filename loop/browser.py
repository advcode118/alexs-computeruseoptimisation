"""Attach to Chrome with Playwright, then observe and act. No agent framework."""

from __future__ import annotations

import re
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

from loop.actions import (
    Action,
    ActionError,
    AssertAll,
    AssertText,
    AssertTitle,
    AssertUrl,
    AssertValues,
    Assertion,
    Choose,
    ChooseError,
    Click,
    Control,
    Fill,
    Goto,
    Observation,
    Press,
    Scroll,
    StaleRefError,
    check_ref,
    check_url,
)

FIXTURE_PATH = Path(__file__).with_name("fixture") / "packing.html"
FORM_MAX = 40
MAX_CONTROLS = 80
SECTION_MAX = 24

# One browser round-trip. Form controls are collected first so a long nav
# cannot push them off the list. Interactive controls get short refs (e1, e2, …)
# stored on data-cu-ref so a later click or fill can find the same node.
_OBSERVE_JS = """
({formMax, otherMax, sectionMax, prefer}) => {
  const formSelector = "input:not([type='hidden']), textarea, select, button";
  const otherSelector = [
    "a[href]",
    "[role='button']",
    "[role='link']",
    "[role='textbox']",
    "[role='checkbox']",
    "[role='radio']",
    "[role='combobox']",
    "[role='option']",
    "[role='tab']",
    "[contenteditable='true']"
  ].join(",");
  document.querySelectorAll("[data-cu-ref]").forEach((node) => {
    node.removeAttribute("data-cu-ref");
  });
  const controls = [];
  const seen = new Set();
  function add(node) {
    if (seen.has(node)) return;
    if (node.getAttribute("aria-hidden") === "true") return;
    if (node.disabled) return;
    const tag = node.tagName.toLowerCase();
    if ((tag === "input" || tag === "textarea") && node.readOnly) return;
    const style = window.getComputedStyle(node);
    if (style.visibility === "hidden" || style.display === "none") return;
    const rect = node.getBoundingClientRect();
    if (rect.width < 1 || rect.height < 1) return;
    seen.add(node);
    let role = node.getAttribute("role");
    if ((tag === "input" || tag === "textarea") && role === "combobox") role = "";
    if (tag === "select") role = "combobox";
    const type = (node.getAttribute("type") || "").toLowerCase();
    if (!role) {
      if (tag === "a") role = "link";
      else if (tag === "button") role = "button";
      else if (tag === "textarea") role = "textbox";
      else if (tag === "select") role = "combobox";
      else if (tag === "input") {
        if (type === "checkbox") role = "checkbox";
        else if (type === "radio") role = "radio";
        else if (type === "button" || type === "submit" || type === "reset") role = "button";
        else role = "textbox";
      } else role = tag;
    }
    let name = node.getAttribute("aria-label") || "";
    if (name === "true" || name === "false") name = "";
    if (!name && node.getAttribute("aria-labelledby")) {
      name = node.getAttribute("aria-labelledby").split(/\\s+/).map((id) => {
        const label = document.getElementById(id);
        return label ? label.innerText.trim() : "";
      }).filter(Boolean).join(" ");
    }
    if (!name && node.labels && node.labels.length) {
      name = Array.from(node.labels).map((label) => {
        const clone = label.cloneNode(true);
        clone.querySelectorAll("input, textarea, select, button").forEach((child) => child.remove());
        return clone.innerText.trim();
      }).filter(Boolean).join(" ");
    }
    if (!name && node.id) {
      const label = document.querySelector("label[for='" + CSS.escape(node.id) + "']");
      if (label) name = label.innerText.trim();
    }
    if (!name && (tag === "button" || type === "submit" || type === "button" || type === "reset")) {
      name = node.value || node.innerText || "";
    }
    if (!name) {
      name = (node.innerText || node.getAttribute("placeholder") || node.getAttribute("title") || node.getAttribute("name") || "").trim();
    }
    name = name.replace(/\\s+/g, " ").slice(0, 120);
    let value = "";
    let options = [];
    if (tag === "select") {
      options = Array.from(node.options || [])
        .map((option) => (option.label || option.text || "").replace(/\\s+/g, " ").trim())
        .filter(Boolean)
        .slice(0, 20);
      const selected = node.options && node.selectedIndex >= 0 ? node.options[node.selectedIndex] : null;
      if (selected) value = (selected.label || selected.text || node.value || "").replace(/\\s+/g, " ").trim();
    } else if (tag === "input" || tag === "textarea") {
      value = String(node.value || "");
    }
    value = value.slice(0, 120);
    let invalid = "";
    if (typeof node.validationMessage === "string" && String(node.value || "") && !node.checkValidity()) {
      invalid = node.validationMessage.replace(/\\s+/g, " ").trim().slice(0, 160);
    }
    const ref = "e" + (controls.length + 1);
    node.setAttribute("data-cu-ref", ref);
    controls.push({ ref, role, name, value, options, invalid });
  }
  for (const node of document.querySelectorAll(formSelector)) {
    if (controls.length >= formMax) break;
    add(node);
  }
  const sectionSelector = [
    "#toc a[href*='#']",
    ".vector-toc a[href*='#']",
    "#mw-panel-toc a[href*='#']",
    "nav.vector-toc a[href*='#']",
    ".toc a[href*='#']",
    ".toctree-wrapper a[href*='#']"
  ].join(",");
  let sectionAdded = 0;
  for (const node of document.querySelectorAll(sectionSelector)) {
    if (sectionAdded >= sectionMax) break;
    const before = controls.length;
    add(node);
    if (controls.length > before) sectionAdded += 1;
  }
  const priority = controls.length;
  const preferText = String(prefer || "").toLowerCase();
  const stop = new Set(["open","click","find","page","link","long","first","search","button","more","learn","that","this","from","with","your","into","today","story","made","fill","demo","form","order","submit","read","stop","before","about","have","been","when","what","where","their","there","which","most","recent","section","result","isnt"]);
  const words = preferText.split(/[^a-z0-9]+/).filter((word) => word.length >= 4 && !stop.has(word));
  const phrases = preferText.match(/[a-z0-9]+(?:-[a-z0-9]+)+/g) || [];
  function inChrome(node) {
    if (node.closest("nav, header, footer, [role='navigation'], .pagetop")) return true;
    const box = node.getBoundingClientRect();
    return box.top >= 0 && box.top < 36 && box.height < 44;
  }
  function matchesPrefer(node) {
    if (!words.length && !phrases.length) return false;
    if (inChrome(node)) return false;
    const name = (node.innerText || node.getAttribute("aria-label") || "").toLowerCase();
    const href = (node.getAttribute("href") || "").toLowerCase();
    const blob = name + " " + href;
    for (const phrase of phrases) {
      if (blob.includes(phrase)) return true;
    }
    for (const word of words) {
      if (blob.includes(word)) return true;
    }
    return false;
  }
  let citeAdded = 0;
  for (const node of document.querySelectorAll("a[href*='cite_note'], sup.reference a[href], .reference a[href]")) {
    if (citeAdded >= 6 || controls.length >= priority + otherMax) break;
    const before = controls.length;
    add(node);
    if (controls.length > before) citeAdded += 1;
  }
  let optionAdded = 0;
  for (const node of document.querySelectorAll("[role='option']")) {
    if (optionAdded >= 16 || controls.length >= priority + otherMax) break;
    const before = controls.length;
    add(node);
    if (controls.length > before) optionAdded += 1;
  }
  let preferred = 0;
  for (const node of document.querySelectorAll("a[href], [role='link']")) {
    if (preferred >= 16 || controls.length >= priority + otherMax) break;
    if (!matchesPrefer(node)) continue;
    const before = controls.length;
    add(node);
    if (controls.length > before) preferred += 1;
  }
  const mainSelector = "main a[href], article a[href], [role='main'] a[href], #mw-content-text a[href]";
  for (const node of document.querySelectorAll(mainSelector)) {
    if (controls.length >= priority + otherMax) break;
    add(node);
  }
  for (const node of document.querySelectorAll(otherSelector)) {
    if (controls.length >= priority + otherMax) break;
    add(node);
  }
  return controls;
}
"""


def fixture_file_url() -> str:
    return FIXTURE_PATH.resolve().as_uri()


class BrowserSession:
    """One Chrome, owned by the thread that calls open()."""

    def __init__(self, *, headless: bool = True, cdp: str | None = None):
        self.headless = headless
        self.cdp = cdp
        self.attached = False
        self.page: Page | None = None
        self._pw = None
        self._browser = None
        self._context = None

    def open(self) -> Page:
        self._pw = sync_playwright().start()
        if self.cdp:
            self._browser = self._pw.chromium.connect_over_cdp(self.cdp)
            self.attached = True
            if not self._browser.contexts:
                raise ActionError("The attached Chrome has no browser context.")
            self._context = self._browser.contexts[0]
            if self._context.pages:
                self.page = self._context.pages[0]
            else:
                self.page = self._context.new_page()
        else:
            self._browser = self._launch()
            self._context = self._browser.new_context(viewport={"width": 1280, "height": 720})
            self.page = self._context.new_page()
        self.page.set_default_timeout(15000)
        return self.page

    def _launch(self):
        attempts = (
            {
                "channel": "chrome",
                "headless": self.headless,
                "args": ["--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled"],
            },
            {"headless": self.headless, "args": ["--disable-dev-shm-usage"]},
        )
        errors = []
        for kwargs in attempts:
            try:
                return self._pw.chromium.launch(**kwargs)
            except Exception as exc:
                label = kwargs.get("channel", "bundled-chromium")
                errors.append(f"{label}: {exc}")
        joined = " | ".join(errors)
        raise ActionError(
            "Could not launch Chrome. Install Google Chrome, or run "
            f"`python -m playwright install chromium`. {joined}"
        )

    def close(self) -> None:
        if self._pw is None:
            return
        try:
            if not self.attached:
                if self._context is not None:
                    self._context.close()
                if self._browser is not None:
                    self._browser.close()
            # An attached Chrome belongs to the user. Stopping Playwright drops
            # the DevTools connection and leaves that browser process running.
        finally:
            self._pw.stop()
            self._pw = None
            self._browser = None
            self._context = None
            self.page = None


def _dialog_controls(page: Page, form_max: int, other_max: int) -> list | None:
    """Controls inside a large overlay frame. The page behind it is left out."""

    def scan() -> list | None:
        for frame in page.frames:
            if frame == page.main_frame:
                continue
            url = frame.url or ""
            if not url or url == "about:blank":
                continue
            try:
                box = frame.frame_element().bounding_box()
            except Exception:
                continue
            if not box or box["width"] < 240 or box["height"] < 120:
                continue
            try:
                raw = frame.evaluate(
                    _OBSERVE_JS,
                    {"formMax": form_max, "otherMax": other_max, "sectionMax": SECTION_MAX},
                )
            except Exception:
                continue
            names = " ".join(item.get("name", "") for item in raw).lower()
            if not any(word in names for word in ("accept", "reject", "agree", "cookie", "consent", "subscribe")):
                continue
            if any(item.get("role") == "button" and item.get("name") for item in raw):
                return raw
        return None

    if len(page.frames) <= 1:
        return None
    found = scan()
    if found is not None:
        return found
    # A frame that already loaded and is not a consent dialog must not block.
    pending = False
    for frame in page.frames:
        if frame == page.main_frame:
            continue
        url = frame.url or ""
        if url and url != "about:blank":
            continue
        try:
            box = frame.frame_element().bounding_box()
        except Exception:
            continue
        if box and box["width"] >= 240 and box["height"] >= 120:
            pending = True
            break
    if not pending:
        return None
    for _ in range(4):
        page.wait_for_timeout(250)
        found = scan()
        if found is not None:
            return found
    return None


def observe(
    page: Page,
    *,
    form_max: int = FORM_MAX,
    other_max: int = MAX_CONTROLS,
    prefer: str = "",
) -> Observation:
    raw = _dialog_controls(page, form_max, other_max)
    if raw is None:
        raw = page.evaluate(
            _OBSERVE_JS,
            {
                "formMax": form_max,
                "otherMax": other_max,
                "sectionMax": SECTION_MAX,
                "prefer": prefer,
            },
        )
    controls = []
    for item in raw:
        options = item.get("options") or []
        if not isinstance(options, list):
            options = []
        controls.append(
            Control(
                ref=str(item["ref"]),
                role=str(item["role"]),
                name=str(item["name"]),
                value=str(item.get("value") or ""),
                options=tuple(str(option) for option in options if option),
                invalid=str(item.get("invalid") or ""),
            )
        )
    return Observation(url=page.url, title=page.title(), controls=controls)


def locate(page: Page, role: str, name: str) -> str | None:
    """Find a control by role and accessible name, including ones past the prompt cap."""
    from loop.planner import find_ref

    observation = observe(page, form_max=80, other_max=200)
    return find_ref(observation, role=role, name=name)


def _locator(page: Page, ref: str):
    check_ref(ref)
    for frame in page.frames:
        locator = frame.locator(f'[data-cu-ref="{ref}"]')
        try:
            if locator.count() > 0:
                return locator.first
        except Exception:
            continue
    raise StaleRefError(f"unknown ref {ref}. Observe again; the page may have changed.")


def _is_select(locator) -> bool:
    try:
        return locator.evaluate("node => node.tagName === 'SELECT'")
    except Exception:
        return False


def _choose(locator, option: str) -> None:
    """Set a select by its visible option name. Fill cannot do this."""
    label = " ".join(option.split())
    if not label:
        try:
            names = locator.evaluate(
                "node => Array.from(node.options || []).map((item) => (item.label || item.text || '').trim()).filter(Boolean)"
            )
        except Exception:
            names = []
        shown = ", ".join(str(name) for name in names[:12]) or "the visible options"
        raise ChooseError(f"choose needs one of: {shown}")
    try:
        if _is_select(locator):
            locator.select_option(label=label, timeout=3000)
            return
    except ChooseError:
        raise
    except Exception:
        pass
    wanted = label.lower()
    try:
        picked = locator.evaluate(
            """(node, wanted) => {
              if (!node.options || !wanted) return "";
              const norm = (text) => text.toLowerCase().replace(/\\s+/g, " ").trim();
              const options = Array.from(node.options);
              const hit = options.find((item) => norm(item.label || item.text) === wanted)
                || options.find((item) => {
                  const name = norm(item.label || item.text);
                  return wanted.length >= 3 && name.length >= 3
                    && (name.includes(wanted) || wanted.includes(name));
                });
              if (!hit) return "";
              node.value = hit.value;
              node.dispatchEvent(new Event("input", { bubbles: true }));
              node.dispatchEvent(new Event("change", { bubbles: true }));
              return hit.label || hit.text || hit.value;
            }""",
            wanted,
        )
    except Exception as exc:
        raise ChooseError(f"choose {label!r} failed: {exc}") from exc
    if not picked:
        raise ChooseError(f"choose {label!r} failed: that option is not in the list")


_PLACE_FIELD = re.compile(r"postcode|\btown\b|station|destination|\blocation\b|\barea\b", re.I)


def _fold_place(text: str) -> str:
    folded = (text or "").lower().replace("’", "'").replace("`", "'")
    return folded.replace("'", "").strip()


def _is_place_field(locator) -> bool:
    """A place box asks for a postcode, town, station, or destination. Its suggestions come from the site."""
    try:
        blob = locator.evaluate(
            """(node) => {
              let name = node.getAttribute("aria-label") || "";
              if (name === "true" || name === "false") name = "";
              const ids = node.getAttribute("aria-labelledby") || "";
              const fromLabel = ids.split(/\\s+/).map((id) => {
                const label = id && document.getElementById(id);
                return label ? label.innerText : "";
              }).join(" ");
              const wrapped = node.labels && node.labels.length
                ? Array.from(node.labels).map((label) => label.innerText || "").join(" ")
                : "";
              return [
                name,
                fromLabel,
                wrapped,
                node.getAttribute("placeholder") || "",
                node.getAttribute("name") || "",
              ].join(" ");
            }"""
        )
    except Exception:
        return False
    return bool(_PLACE_FIELD.search(blob or ""))


def _any_place_filled(page: Page) -> bool:
    try:
        blobs = page.evaluate(
            """() => {
              const out = [];
              for (const node of document.querySelectorAll("input, textarea")) {
                if (!String(node.value || "").trim()) continue;
                let name = node.getAttribute("aria-label") || "";
                if (name === "true" || name === "false") name = "";
                const ids = node.getAttribute("aria-labelledby") || "";
                const fromLabel = ids.split(/\\s+/).map((id) => {
                  const label = id && document.getElementById(id);
                  return label ? label.innerText : "";
                }).join(" ");
                out.push([name, fromLabel, node.getAttribute("placeholder") || "", node.getAttribute("name") || ""].join(" "));
              }
              return out;
            }"""
        )
    except Exception:
        return False
    return any(_PLACE_FIELD.search(blob or "") for blob in blobs or [])


def _dismiss_consent(page: Page) -> None:
    """Accept a consent banner, then drop it if it still covers the page."""
    try:
        page.evaluate(
            """() => {
              const accept = document.querySelector("#onetrust-accept-btn-handler");
              if (accept) accept.click();
              document.querySelectorAll("#onetrust-consent-sdk").forEach((node) => node.remove());
            }"""
        )
    except Exception:
        return


def _suggestion_point(page: Page, text: str) -> dict | None:
    wanted = _fold_place(text)
    if not wanted:
        return None
    try:
        return page.evaluate(
            """(wanted) => {
              const fold = (value) => value.toLowerCase().replace(/['’`]/g, "").trim();
              const items = [];
              for (const node of document.querySelectorAll("li[role='button'], [role='option']")) {
                const label = (node.innerText || "").replace(/\\s+/g, " ").trim();
                if (!label || label.length > 160) continue;
                const box = node.getBoundingClientRect();
                if (box.width < 20 || box.height < 8 || box.top < 0 || box.top > window.innerHeight) continue;
                items.push({
                  label,
                  x: box.x + box.width / 2,
                  y: box.y + box.height / 2,
                });
                if (items.length >= 12) break;
              }
              let hit = items.findIndex((item) => fold(item.label).startsWith(wanted));
              if (hit < 0) hit = items.findIndex((item) => fold(item.label).includes(wanted));
              if (hit < 0) return null;
              return { x: items[hit].x, y: items[hit].y, label: items[hit].label, index: hit };
            }""",
            wanted,
        )
    except Exception:
        return None


def _search_if_still(page: Page, before: str) -> None:
    """A place suggestion does not leave the form. Search does."""
    if page.url != before:
        return
    if not _click_visible_button(page, "Search"):
        return
    try:
        page.wait_for_function(
            "(before) => location.href !== before",
            arg=before,
            timeout=4000,
        )
    except Exception:
        return


def _accept_place(page: Page, locator, text: str) -> None:
    """Type a place and accept the site's own suggestion. The typed text is the caller's."""
    before = page.url
    _dismiss_consent(page)
    try:
        locator.click(timeout=3000)
    except Exception:
        _dismiss_consent(page)
        locator.click(timeout=3000, force=True)
    locator.fill("")
    locator.press_sequentially(text, delay=25)
    for _ in range(12):
        point = _suggestion_point(page, text)
        if point is None:
            page.wait_for_timeout(150)
            continue
        page.mouse.click(point["x"], point["y"])
        page.wait_for_timeout(200)
        grown = page.url != before or "," in (locator.input_value() or "")
        if not grown:
            locator.click(timeout=2000, force=True)
            for _step in range(int(point.get("index") or 0) + 1):
                page.keyboard.press("ArrowDown")
            page.keyboard.press("Enter")
            page.wait_for_timeout(200)
        break
    _search_if_still(page, before)


def _click_visible_button(page: Page, label: str) -> bool:
    try:
        point = page.evaluate(
            """(label) => {
              const wanted = label.toLowerCase();
              for (const node of document.querySelectorAll("button, [role='button'], input[type='submit']")) {
                const text = (node.innerText || node.value || node.getAttribute("aria-label") || "")
                  .replace(/\\s+/g, " ").trim().toLowerCase();
                if (text !== wanted) continue;
                const box = node.getBoundingClientRect();
                if (box.width < 20 || box.height < 8 || box.top < 0 || box.top > window.innerHeight) continue;
                return { x: box.x + box.width / 2, y: box.y + box.height / 2 };
              }
              return null;
            }""",
            label,
        )
    except Exception:
        return False
    if point:
        page.mouse.click(point["x"], point["y"])
        return True
    try:
        page.get_by_role("button", name=label, exact=True).first.click(timeout=2000, force=True)
    except Exception:
        return False
    return True


def act(page: Page, action: Action, *, place: bool = False) -> None:
    try:
        if isinstance(action, Goto):
            page.goto(check_url(action.url), wait_until="domcontentloaded", timeout=25000)
            return
        if isinstance(action, Click):
            locator = _locator(page, action.ref)
            before = page.url
            try:
                locator.click(timeout=3000)
            except Exception:
                try:
                    locator.scroll_into_view_if_needed(timeout=1000)
                except Exception:
                    pass
                locator.click(timeout=5000, force=True)
            if page.url != before:
                return
            try:
                info = locator.evaluate(
                    """(node) => ({
                      label: (node.innerText || node.value || '').replace(/\\s+/g, ' ').trim(),
                      suggestion: node.tagName === 'LI' && (node.getAttribute('role') || '') === 'button'
                    })"""
                )
            except Exception:
                return
            label = str((info or {}).get("label") or "")
            if label.lower() == "search properties" and _click_visible_button(page, "Search properties"):
                try:
                    page.wait_for_function(
                        "(before) => location.href !== before",
                        arg=before,
                        timeout=8000,
                    )
                except Exception:
                    pass
                return
            if (info or {}).get("suggestion"):
                _search_if_still(page, before)
            return
        if isinstance(action, Fill):
            locator = _locator(page, action.ref)
            if _is_select(locator):
                _choose(locator, action.text)
            elif place:
                _accept_place(page, locator, action.text)
            else:
                locator.fill(action.text)
            return
        if isinstance(action, Choose):
            locator = _locator(page, action.ref)
            before = page.url
            _choose(locator, action.option)
            try:
                sorts = locator.evaluate(
                    """(node) => {
                      if (!node.options) return false;
                      const label = node.labels && node.labels[0] ? node.labels[0].innerText : "";
                      const blob = label + " " + (node.name || "") + " " + (node.getAttribute("aria-label") || "");
                      return /sort/i.test(blob);
                    }"""
                )
            except Exception:
                sorts = False
            if sorts:
                try:
                    page.wait_for_function(
                        "(before) => location.href !== before",
                        arg=before,
                        timeout=2500,
                    )
                    page.wait_for_load_state("domcontentloaded", timeout=8000)
                except Exception:
                    pass
            return
        if isinstance(action, Press):
            before = page.url
            place = False
            if action.ref:
                field = _locator(page, action.ref)
                place = action.key == "Enter" and _is_place_field(field)
                field.press(action.key)
            else:
                page.keyboard.press(action.key)
            if action.key == "Enter":
                try:
                    page.wait_for_function(
                        "(before) => location.href !== before",
                        arg=before,
                        timeout=800,
                    )
                except Exception:
                    pass
                if page.url == before and (place or (action.ref is None and _any_place_filled(page))):
                    _search_if_still(page, before)
            return
        if isinstance(action, Scroll):
            amount = action.amount if action.direction == "down" else -action.amount
            if action.ref:
                _locator(page, action.ref).evaluate("(node, dy) => node.scrollBy(0, dy)", amount)
            else:
                page.evaluate("(dy) => window.scrollBy(0, dy)", amount)
            return
    except ActionError:
        raise
    except Exception as exc:
        message = str(exc).split("\n", 1)[0][:300]
        raise ActionError(f"{action.summary()} failed: {message}") from exc
    raise ActionError(f"unknown action: {action!r}")


def check(page: Page, assertion: Assertion) -> tuple[bool, str]:
    if isinstance(assertion, AssertUrl):
        ok = assertion.text in page.url
        return ok, f"url contains {assertion.text!r}"
    if isinstance(assertion, AssertTitle):
        title = page.title()
        ok = assertion.text in title
        return ok, f"title contains {assertion.text!r}"
    if isinstance(assertion, AssertText):
        body = page.locator("body").inner_text()
        ok = assertion.text in body
        return ok, f"page contains {assertion.text!r}"
    if isinstance(assertion, AssertAll):
        body = page.locator("body").inner_text()
        missing = [text for text in assertion.texts if text not in body]
        detail = "page contains " + " and ".join(repr(text) for text in assertion.texts)
        if missing:
            detail = "missing " + ", ".join(repr(text) for text in missing)
        return not missing, detail
    if isinstance(assertion, AssertValues):
        missing = []
        for role, name, text in assertion.checks:
            ref = locate(page, role, name)
            if ref is None:
                missing.append(name)
                continue
            value = _locator(page, ref).input_value()
            if value != text:
                missing.append(f"{name}={value!r}")
        detail = "field values match" if not missing else "missing " + ", ".join(missing)
        return not missing, detail
    raise ActionError(f"unknown assertion: {assertion!r}")
