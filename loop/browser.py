"""Attach to Chrome with Playwright, then observe and act. No agent framework."""

from __future__ import annotations

from pathlib import Path

from playwright.sync_api import Page, sync_playwright

from loop.actions import (
    Action,
    ActionError,
    AssertText,
    AssertTitle,
    AssertUrl,
    Assertion,
    Click,
    Control,
    Fill,
    Goto,
    Observation,
    Press,
    Scroll,
    check_ref,
    check_url,
)

FIXTURE_PATH = Path(__file__).with_name("fixture") / "packing.html"
MAX_CONTROLS = 40

# One browser round-trip. Interactive controls get short refs (e1, e2, …)
# stored on data-cu-ref so a later click or fill can find the same node.
_OBSERVE_JS = """
() => {
  const selector = [
    "a[href]",
    "button",
    "input:not([type='hidden'])",
    "textarea",
    "select",
    "[role='button']",
    "[role='link']",
    "[role='textbox']",
    "[role='checkbox']",
    "[role='radio']",
    "[role='combobox']",
    "[role='tab']",
    "[contenteditable='true']"
  ].join(",");
  document.querySelectorAll("[data-cu-ref]").forEach((node) => {
    node.removeAttribute("data-cu-ref");
  });
  const controls = [];
  for (const node of document.querySelectorAll(selector)) {
    if (controls.length >= %(max)d) break;
    if (node.getAttribute("aria-hidden") === "true") continue;
    const style = window.getComputedStyle(node);
    if (style.visibility === "hidden" || style.display === "none") continue;
    const rect = node.getBoundingClientRect();
    if (rect.width < 1 || rect.height < 1) continue;
    const tag = node.tagName.toLowerCase();
    let role = node.getAttribute("role");
    if (!role) {
      if (tag === "a") role = "link";
      else if (tag === "button") role = "button";
      else if (tag === "textarea") role = "textbox";
      else if (tag === "select") role = "combobox";
      else if (tag === "input") {
        const type = (node.getAttribute("type") || "text").toLowerCase();
        if (type === "checkbox") role = "checkbox";
        else if (type === "radio") role = "radio";
        else if (type === "button" || type === "submit" || type === "reset") role = "button";
        else role = "textbox";
      } else role = tag;
    }
    let name = node.getAttribute("aria-label") || "";
    if (!name && node.getAttribute("aria-labelledby")) {
      name = node.getAttribute("aria-labelledby").split(/\\s+/).map((id) => {
        const label = document.getElementById(id);
        return label ? label.innerText.trim() : "";
      }).filter(Boolean).join(" ");
    }
    if (!name && node.labels && node.labels.length) {
      name = Array.from(node.labels).map((label) => label.innerText.trim()).filter(Boolean).join(" ");
    }
    if (!name && node.id) {
      const label = document.querySelector("label[for='" + CSS.escape(node.id) + "']");
      if (label) name = label.innerText.trim();
    }
    if (!name) {
      name = (node.innerText || node.getAttribute("placeholder") || node.getAttribute("title") || node.getAttribute("name") || "").trim();
    }
    name = name.replace(/\\s+/g, " ").slice(0, 80);
    let value = "";
    if (tag === "input" || tag === "textarea" || tag === "select") {
      value = String(node.value || "").slice(0, 80);
    }
    const ref = "e" + (controls.length + 1);
    node.setAttribute("data-cu-ref", ref);
    controls.push({ ref, role, name, value });
  }
  return controls;
}
""" % {"max": MAX_CONTROLS}


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
        self.page.set_default_timeout(5000)
        return self.page

    def _launch(self):
        attempts = (
            {"channel": "chrome", "headless": self.headless, "args": ["--disable-dev-shm-usage"]},
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


def observe(page: Page) -> Observation:
    raw = page.evaluate(_OBSERVE_JS)
    controls = [
        Control(
            ref=str(item["ref"]),
            role=str(item["role"]),
            name=str(item["name"]),
            value=str(item["value"]),
        )
        for item in raw
    ]
    return Observation(url=page.url, title=page.title(), controls=controls)


def _locator(page: Page, ref: str):
    check_ref(ref)
    locator = page.locator(f'[data-cu-ref="{ref}"]')
    if locator.count() == 0:
        raise ActionError(f"unknown ref {ref}. Observe again; the page may have changed.")
    return locator.first


def act(page: Page, action: Action) -> None:
    try:
        if isinstance(action, Goto):
            page.goto(check_url(action.url), wait_until="domcontentloaded")
            return
        if isinstance(action, Click):
            _locator(page, action.ref).click()
            return
        if isinstance(action, Fill):
            _locator(page, action.ref).fill(action.text)
            return
        if isinstance(action, Press):
            if action.ref:
                _locator(page, action.ref).press(action.key)
            else:
                page.keyboard.press(action.key)
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
    raise ActionError(f"unknown assertion: {assertion!r}")
