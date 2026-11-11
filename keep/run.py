"""Separate runner. Does not change loop/.

Starts each task on a blank page. One model call returns the next actions.
A search URL is not success. Done requires the requested text on the page.
Sort clicks and a repeated failed click are dropped.
"""

from __future__ import annotations

import os
import re
import time

from loop.actions import (
    ActionError,
    AssertText,
    Click,
    Control,
    Goto,
    Observation,
    PlannerError,
)
from loop.browser import BrowserSession, act, check

TASKS = [
    {
        "name": "samba",
        "task": (
            "From a blank page, find a cheap pair of white Adidas Samba shoes "
            "in stock for size 8 mens. Open the product page. Stop only when "
            "that page shows white Samba, men's size 8, in stock, and a price. "
            "If a list of results is showing, open one matching shoe. "
            "Do not click Sort."
        ),
        "need": "Samba",
        "cart": False,
    },
    {
        "name": "walmart",
        "cart": True,
        "item": "milk",
        "task": (
            "From a blank page, search Walmart for milk and add one product "
            "to the cart. Stop only when the cart shows milk. "
            "If a list of results is showing, open one matching product. "
            "Do not click Sort."
        ),
        "need": "cart",
    },
    {
        "name": "etsy",
        "cart": True,
        "item": "usb",
        "task": (
            "From a blank page, search Etsy for a USB-C cable and add one "
            "product to the cart. Stop only when the cart shows that cable. "
            "If a list of results is showing, open one matching product. "
            "Do not click Sort."
        ),
        "need": "cart",
    },
    {
        "name": "nike",
        "cart": True,
        "item": "sock",
        "task": (
            "From a blank page, search Nike for training socks and add one "
            "product to the cart. Stop only when the cart shows the socks. "
            "If a list of results is showing, open one matching product. "
            "Do not click Sort."
        ),
        "need": "cart",
    },
    {
        "name": "playstation",
        "cart": True,
        "item": "dualsense",
        "task": (
            "From a blank page, open the PlayStation website, choose a "
            "DualSense controller, and add one to the cart. Stop only when "
            "the cart shows a DualSense. If a list of results is showing, "
            "open one matching product. Do not click Sort."
        ),
        "need": "DualSense",
    },
    {
        "name": "alza",
        "cart": True,
        "item": "usb",
        "task": (
            "From a blank page, search Alza for a USB-C charging cable and "
            "add one product to the cart. Stop only when the cart shows the "
            "cable. If a list of results is showing, open one matching product. "
            "Do not click Sort."
        ),
        "need": "cart",
    },
]

MAX_CYCLES = 16
TASK_LIMIT_S = 150
MODEL = "claude-sonnet-4-6"
_SKIP = {
    "from", "blank", "page", "find", "cheap", "pair", "search", "product",
    "stop", "only", "when", "that", "this", "shows", "show", "list", "results",
    "showing", "open", "matching", "click", "sort", "with", "into", "your",
    "have", "been", "size", "stock", "price", "cart", "item", "named", "task",
    "does", "dont", "not", "and", "the", "for", "one", "add",
}


def _control(observation, ref: str):
    for control in observation.controls:
        if control.ref == ref:
            return control
    return None


def _is_sort(observation, action) -> bool:
    if not isinstance(action, Click):
        return False
    control = _control(observation, action.ref)
    if control is None:
        return False
    return "sort" in control.name.lower()


_LOGO = {"walmart", "etsy", "nike", "adidas", "alza", "playstation", "home", "logo"}


def _is_logo(observation, action) -> bool:
    if not isinstance(action, Click):
        return False
    control = _control(observation, action.ref)
    if control is None or control.role != "link":
        return False
    return control.name.strip().lower() in _LOGO


def _host(url: str) -> str:
    try:
        from urllib.parse import urlparse

        host = urlparse(url).netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return ""


def _rootish(url: str) -> bool:
    from urllib.parse import urlparse

    return urlparse(url).path in ("", "/")


def _cartish(url: str) -> bool:
    lowered = url.lower()
    return any(part in lowered for part in ("/cart", "/bag", "/basket", "checkout", "kosik", "/order"))


def _productish(url: str) -> bool:
    if _search_page(url) or _rootish(url) or _cartish(url):
        return False
    lowered = url.lower()
    if any(part in lowered for part in ("/t/", "/dp/", "/ip/", "/listing/", "/product", "/p/", "/buy")):
        return True
    path = lowered.split("?", 1)[0]
    return path.endswith(".htm") or path.endswith(".html")


def _can_leave(url: str) -> bool:
    if not url or url.lower().startswith("about:"):
        return True
    from urllib.parse import urlparse

    path = urlparse(url).path.lower()
    return any(
        part in path
        for part in ("gdpr", "consent", "cookie", "captcha", "cf_chl", "challenge")
    )


def _goto_ok(here: str, dest: str) -> bool:
    if _can_leave(here):
        return True
    if _host(here) != _host(dest) or not _host(dest):
        return False
    if _rootish(dest):
        return False
    if _cartish(dest):
        return True
    if _productish(here):
        return False
    if _search_page(dest):
        return not _search_page(here)
    return _productish(dest)


def _search_page(url: str) -> bool:
    lowered = url.lower()
    return "/search" in lowered or "search?" in lowered or "s?k=" in lowered


def _stage(url: str, cart: bool) -> str:
    lowered = url.lower()
    if not url or lowered.startswith("about:"):
        return "Blank page. The only action is goto the site named in the task."
    if _cartish(url):
        return (
            "Cart page. If page_text shows the requested item, set done with that text. "
            "If the cart is empty, leave it and add the item from its product page."
        )
    if _search_page(url):
        return "Results list. Click one product link whose name matches the task. Do not click a filter."
    if _productish(url) and cart:
        return (
            "Product page. Click the requested size if one is listed, then Add to bag or Add to cart, "
            "then open the cart. Do not search again."
        )
    if _productish(url):
        return (
            "Product page. Click men's size 8 if it is listed. "
            "Stay on this page until it shows white, size 8, in stock, and a price. Do not search again."
        )
    return "Site page. Fill the search box with the item, then press Enter."


def _ready(spec: dict, url: str, text: str) -> str:
    if not text or _search_page(url):
        return ""
    low = text.lower()
    if spec["name"] == "samba":
        if not _productish(url) or "samba" not in low or "white" not in low:
            return ""
        if not re.search(r"(?:size|mens?)\s*:?\s*8(?!\d)|m\s*8\s*/\s*w", low):
            return ""
        if re.search(r"out of stock|sold out|currently unavailable", low):
            return ""
        price = re.search(r"[$£€]\s?\d+(?:[.,]\d{2})?", text)
        if not price:
            return ""
        return f"white Samba size 8 {price.group(0)}"
    if not spec.get("cart") or not _cartish(url):
        return ""
    item = str(spec.get("item", "")).lower()
    if not item or item not in low:
        return ""
    return f"{spec['item']} in the cart"


def _hints(spec: dict) -> list[str]:
    words = []
    for raw in spec["task"].replace("'", " ").split():
        word = "".join(ch for ch in raw.lower() if ch.isalnum() or ch == "-")
        if word in _SKIP or word in words:
            continue
        if len(word) < 4 and not word.isdigit():
            continue
        words.append(word)
    need = spec["need"].lower()
    if need != "cart" and need not in words:
        words.append(need)
    return words[:12]


_PICK_JS = """
({ hints, mode }) => {
  const selector = [
    "a[href]", "button", "input:not([type='hidden'])", "textarea", "select",
    "[role='button']", "[role='link']", "[role='textbox']", "[role='searchbox']",
    "[role='combobox']"
  ].join(",");
  document.querySelectorAll("[data-cu-ref]").forEach((node) => {
    node.removeAttribute("data-cu-ref");
  });
  const words = (hints || []).map((w) => String(w).toLowerCase()).filter((w) => w.length > 2 || /^[0-9]+$/.test(w));
  const product = mode === "product";
  const nodes = [];
  for (const node of document.querySelectorAll(selector)) {
    if (node.getAttribute("aria-hidden") === "true") continue;
    const style = window.getComputedStyle(node);
    if (style.visibility === "hidden" || style.display === "none") continue;
    const rect = node.getBoundingClientRect();
    if (rect.width < 1 || rect.height < 1) continue;
    const tag = node.tagName.toLowerCase();
    if (tag === "a" && node.href) {
      try {
        const dest = new URL(node.href, location.href);
        if (dest.host === location.host && (dest.pathname === "/" || dest.pathname === "")) continue;
      } catch (e) {}
    }
    let role = node.getAttribute("role") || "";
    if (!role) {
      if (tag === "a") role = "link";
      else if (tag === "button") role = "button";
      else if (tag === "input" || tag === "textarea") role = "textbox";
      else role = tag;
    }
    let name = node.getAttribute("aria-label") || node.getAttribute("placeholder") || "";
    if (!name) name = node.innerText || node.getAttribute("title") || node.getAttribute("name") || "";
    name = String(name).trim().replace(/\\s+/g, " ").slice(0, 80);
    const value = (tag === "input" || tag === "textarea" || tag === "select")
      ? String(node.value || "").slice(0, 80) : "";
    const blob = (name + " " + value).toLowerCase();
    let score = 0;
    if (role === "textbox" || role === "searchbox" || role === "combobox" || tag === "input" || tag === "textarea") score += 30;
    if (blob.includes("search")) score += 25;
    if (blob.includes("add to bag") || blob.includes("add to cart") || blob.includes("add to basket")) score += 120;
    if (product && (role === "textbox" || role === "searchbox" || blob.includes("search"))) score -= 80;
    if (product && (blob.includes("view cart") || blob.includes("view bag") || blob.includes("view basket"))) score += 140;
    if (product && /^(?:uk|us|eu|size)?\\s*\\d{1,2}(?:\\.5)?$/.test(blob)) score += 90;
    const inChrome = node.closest("nav, header, footer");
    if (inChrome) score -= product ? 180 : 60;
    if (role === "link" && !inChrome && rect.top > 120 && name.length > 12) score += 45;
    for (const word of words) if (blob.includes(word)) score += 40;
    if (blob.includes("sort")) score -= 40;
    nodes.push({ node, role, name, value, score });
  }
  nodes.sort((a, b) => b.score - a.score);
  const controls = [];
  nodes.slice(0, 40).forEach((item, index) => {
    const ref = "e" + (index + 1);
    item.node.setAttribute("data-cu-ref", ref);
    controls.push({ ref, role: item.role, name: item.name, value: item.value });
  });
  return controls;
}
"""


def _observe(page, hints: list[str], mode: str) -> Observation:
    raw = page.evaluate(_PICK_JS, {"hints": hints, "mode": mode})
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


def _page_text(page, limit: int = 1500) -> str:
    try:
        text = page.locator("body").inner_text(timeout=3000)
    except Exception:
        return ""
    return " ".join(text.split())[:limit]


def _glitch(exc: BaseException) -> bool:
    text = str(exc).lower()
    return (
        "execution context was destroyed" in text
        or "navigation" in text
        or "target closed" in text
        or "frame was detached" in text
    )


def _url(page) -> str:
    try:
        return page.url
    except Exception:
        return ""


def run_task(session: BrowserSession, planner, spec: dict) -> dict:
    page = session.page
    page.goto("about:blank")
    history: list[dict] = []
    calls = 0
    failed_click = None
    fact = ""
    started = time.perf_counter()
    hints = _hints(spec)
    for _ in range(MAX_CYCLES):
        if time.perf_counter() - started > TASK_LIMIT_S:
            return _row(spec, False, started, calls, f"time limit at {_url(page)}")
        url_now = _url(page)
        ready = _ready(spec, url_now, _page_text(page, 8000))
        if ready:
            print(f"trace\t{spec['name']}\t{calls}\t{url_now}\tfact {ready}", flush=True)
            return _row(spec, True, started, calls, ready)
        try:
            observation = _observe(page, hints, "product" if _productish(url_now) else "other")
        except Exception as exc:
            if not _glitch(exc):
                return _row(spec, False, started, calls, str(exc))
            history.append({"rejected": "page navigated during read"})
            continue
        try:
            batch = planner.plan(
                spec["task"],
                observation,
                history,
                _page_text(page),
                bool(spec.get("cart")),
            )
        except PlannerError as exc:
            calls += 1
            history.append({"rejected": str(exc)})
            reason = str(exc).replace("\n", " ")[:120]
            print(
                f"trace\t{spec['name']}\t{calls}\t{_url(page)}\trejected {reason}",
                flush=True,
            )
            continue
        calls += 1
        actions = []
        for action in batch.actions:
            if _is_sort(observation, action):
                history.append({"rejected": action.summary(), "why": "sort"})
                continue
            if _is_logo(observation, action):
                history.append({"rejected": action.summary(), "why": "logo"})
                continue
            if isinstance(action, Click) and action.ref == failed_click:
                history.append({"rejected": action.summary(), "why": "repeat"})
                continue
            if isinstance(action, Goto) and not _goto_ok(observation.url, action.url):
                why = (
                    "stay on this website"
                    if _host(observation.url) != _host(action.url)
                    else "open a product or the cart"
                )
                history.append({"rejected": action.summary(), "why": why, "next": "click or fill"})
                continue
            actions.append(action)
        if not actions and batch.actions:
            last = history[-1] if history else {}
            print(
                f"trace\t{spec['name']}\t{calls}\t{_url(page)}\t"
                f"dropped {last.get('why', '')} {last.get('rejected', '')}",
                flush=True,
            )
            continue
        summary = ", ".join(action.summary() for action in actions) or (
            "done" if batch.done else "wait"
        )
        print(f"trace\t{spec['name']}\t{calls}\t{_url(page)}\t{summary}", flush=True)
        for action in actions:
            try:
                act(page, action)
            except Exception as exc:
                if not isinstance(exc, ActionError) and not _glitch(exc):
                    return _row(spec, False, started, calls, str(exc))
                if isinstance(action, Click):
                    failed_click = action.ref
                history.append({"failed": action.summary(), "error": str(exc)})
                break
            failed_click = None
            history.append({"did": action.summary()})
        else:
            if not batch.done:
                continue
            if not isinstance(batch.assertion, AssertText):
                history.append({"rejected_done": "no text assertion"})
                continue
            try:
                ok, detail = check(page, batch.assertion)
                url = _url(page)
            except Exception as exc:
                if not _glitch(exc):
                    return _row(spec, False, started, calls, str(exc))
                history.append({"rejected_done": "page navigated during check"})
                continue
            if not ok or _search_page(url):
                history.append({"rejected_done": detail, "url": url})
                continue
            try:
                body = page.locator("body").inner_text()
            except Exception as exc:
                if not _glitch(exc):
                    return _row(spec, False, started, calls, str(exc))
                history.append({"rejected_done": "page navigated during read"})
                continue
            ready = _ready(spec, url, body)
            if not ready:
                history.append({"rejected_done": "fact not visible"})
                continue
            print(f"trace\t{spec['name']}\t{calls}\t{url}\tfact {ready}", flush=True)
            return _row(spec, True, started, calls, ready)
    url_now = _url(page)
    ready = _ready(spec, url_now, _page_text(page, 8000))
    if ready:
        print(f"trace\t{spec['name']}\t{calls}\t{url_now}\tfact {ready}", flush=True)
        return _row(spec, True, started, calls, ready)
    return _row(
        spec,
        False,
        started,
        calls,
        fact or f"requested fact not visible at {_url(page)}",
    )


def _row(spec: dict, passed: bool, started: float, calls: int, fact: str) -> dict:
    return {
        "task": spec["name"],
        "pass": "yes" if passed else "no",
        "seconds": round(time.perf_counter() - started, 3),
        "calls": calls,
        "fact": fact.replace("\n", " ")[:180],
    }


def _load_keys(path: str) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path or not os.path.isfile(path):
        return values
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text or text.startswith("#") or "=" not in text:
                continue
            key, value = text.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


class _DirectClaude:
    """One Anthropic call per cycle, used when loop.planner has no Router."""

    def __init__(self, api_key: str):
        if not api_key:
            raise PlannerError("The planner tier needs ANTHROPIC_API_KEY.")
        self.api_key = api_key

    def plan(self, task: str, observation, history: list[dict], page_text: str = "", cart: bool = False):
        import json
        import socket
        import urllib.error
        import urllib.request

        import loop.planner as planner

        payload = {
            "model": MODEL,
            "max_tokens": 800,
            "temperature": 0,
            "system": (
                "You are a browser planner. Reply with JSON only. "
                "Schema: "
                '{"reason":"short","done":false,"actions":['
                '{"type":"goto","url":"https://example.com"},'
                '{"type":"click","ref":"e1"},'
                '{"type":"fill","ref":"e1","text":"milk"},'
                '{"type":"press","key":"Enter","ref":"e1"},'
                '{"type":"scroll","direction":"down","amount":400}'
                '],"assertion":{"type":"text","text":"expected"}}. '
                "Refs must be copied from the observation and look like e1. "
                "Follow the stage field. "
                "page_text is the visible text. "
                "From a blank page, goto the site named in the task. "
                "Do not leave the site for a different website. "
                "On a site page, fill the search box, then press Enter. "
                "On a results list, click one product link below the menu, or goto that product on the same website. Do not scroll past the results. "
                "On a product page, follow the stage field. Do not search again. "
                "A cart task is done only on the cart page. "
                "Do not click Sort, a logo, or a control that already failed. "
                "If the last action was dropped, click or fill a control from the observation instead of goto. "
                "Set done true only when page_text shows the requested fact, "
                "with assertion type text and an empty actions list. "
                "A search page is never done."
            ),
            "messages": [
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "task": task,
                            "stage": _stage(getattr(observation, "url", ""), cart),
                            "page_text": page_text,
                            "observation": observation.to_dict(),
                            "history": history[-6:],
                        },
                        ensure_ascii=False,
                    ),
                }
            ],
        }
        request = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=json.dumps(payload).encode(),
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
        )
        socket.setdefaulttimeout(25)
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                body = json.loads(response.read().decode())
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise PlannerError(f"model call failed: {exc}") from exc
        parts = [
            block.get("text", "")
            for block in body.get("content", [])
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        text = "".join(parts)
        if hasattr(planner, "parse_model_content"):
            return planner.parse_model_content(text)
        from loop.actions import parse_batch

        data = json.loads(text)
        return parse_batch(data)


def build_planner():
    keys = _load_keys(os.environ.get("KEEP_ENV", ""))
    return _DirectClaude(keys.get("ANTHROPIC_API_KEY", ""))


def main() -> int:
    planner = build_planner()
    session = BrowserSession(headless=True)
    session.open()
    rows = []
    try:
        for spec in TASKS:
            rows.append(run_task(session, planner, spec))
            print(
                f"{rows[-1]['task']}\t{rows[-1]['pass']}\t{rows[-1]['seconds']}\t"
                f"{rows[-1]['calls']}\t{rows[-1]['fact']}"
            )
    finally:
        session.close()
    print("task\tpass\tseconds\tcalls\tfact")
    for row in rows:
        print(f"{row['task']}\t{row['pass']}\t{row['seconds']}\t{row['calls']}\t{row['fact']}")
    return 0 if all(row["pass"] == "yes" for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
