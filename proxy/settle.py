"""Wait until the page is quiet, then let the caller snapshot.

The child stays @playwright/mcp@0.0.84 with --snapshot-mode none. This module
does not snapshot. It asks the page, through browser_evaluate, to watch DOM
mutations and return when nothing meaningful happens for a short interval.
A timeout, a hung evaluate, or a child error still returns. The caller
snapshots either way.
"""

from __future__ import annotations

import asyncio
import json
import re

from proxy.page import tool_text

QUIET_MS = 100
SETTLE_TIMEOUT_MS = 1500
PROXY_TIMEOUT_S = 2.0

# Attribute names that can change the accessibility tree. style, class, and
# data-* are ignored. Mutations inside script, style, noscript, and template
# are ignored. Those are not meaningful for the snapshot.
_MEANINGFUL_ATTR = re.compile(
    r"^(role|alt|title|href|value|placeholder|name|open|tabindex|contenteditable|type|disabled|hidden|checked|selected|aria-)"
)
_IGNORED_TAGS = {"script", "style", "noscript", "template"}


def mutation_is_meaningful(record: dict) -> bool:
    """True when a mutation record can change the accessibility tree.

    record uses the page's terms: type is childList, characterData, or
    attributes; attribute is the attribute name; tag is the element's tag.
    """
    tag = str(record.get("tag") or "").lower()
    if tag in _IGNORED_TAGS or record.get("ignored") is True:
        return False
    kind = record.get("type")
    if kind in {"childList", "characterData"}:
        return True
    if kind != "attributes":
        return False
    name = str(record.get("attribute") or "")
    if not name or name in {"style", "class"} or name.startswith("data-"):
        return False
    return _MEANINGFUL_ATTR.match(name) is not None


def decide_settle(
    events: list[tuple[int, bool]],
    *,
    quiet_ms: int = QUIET_MS,
    timeout_ms: int = SETTLE_TIMEOUT_MS,
) -> str:
    """'quiet' or 'timeout' for a list of (time_ms, meaningful) events.

    The clock starts at 0. A meaningful event resets the quiet timer.
    A gap of quiet_ms after the last meaningful event ends the wait, including
    a page that never mutates. Otherwise the wait ends at timeout_ms.
    """
    last = 0
    for time_ms, meaningful in events:
        if time_ms >= timeout_ms:
            break
        if time_ms - last >= quiet_ms:
            return "quiet"
        if meaningful:
            last = time_ms
    if timeout_ms - last >= quiet_ms:
        return "quiet"
    return "timeout"


def settle_source(quiet_ms: int = QUIET_MS, timeout_ms: int = SETTLE_TIMEOUT_MS) -> str:
    """Page function. Returns a JSON string so the tool text is parseable."""
    return f"""async () => {{
  const quietMs = {int(quiet_ms)};
  const timeoutMs = {int(timeout_ms)};
  const started = Date.now();
  let last = started;
  const skip = new Set(["SCRIPT", "STYLE", "NOSCRIPT", "TEMPLATE"]);
  const attrOk = /^(role|alt|title|href|value|placeholder|name|open|tabindex|contenteditable|type|disabled|hidden|checked|selected|aria-)/;
  const elementOf = (node) => {{
    if (!node) return null;
    return node.nodeType === 1 ? node : node.parentElement;
  }};
  const meaningful = (record) => {{
    const el = elementOf(record.target);
    if (!el || skip.has(el.tagName)) return false;
    if (el.closest && el.closest("script,style,noscript,template")) return false;
    if (record.type === "attributes") {{
      const name = record.attributeName || "";
      if (!name || name === "style" || name === "class" || name.startsWith("data-")) return false;
      return attrOk.test(name);
    }}
    return record.type === "childList" || record.type === "characterData";
  }};
  const outcome = await new Promise((resolve) => {{
    let finished = false;
    const done = (reason) => {{
      if (finished) return;
      finished = true;
      observer.disconnect();
      clearInterval(tick);
      resolve(JSON.stringify({{ settled: reason === "quiet", reason }}));
    }};
    const observer = new MutationObserver((records) => {{
      for (const record of records) {{
        if (meaningful(record)) last = Date.now();
      }}
    }});
    const root = document.documentElement || document;
    observer.observe(root, {{ subtree: true, childList: true, attributes: true, characterData: true }});
    const tick = setInterval(() => {{
      const now = Date.now();
      if (now - started >= timeoutMs) done("timeout");
      else if (now - last >= quietMs) done("quiet");
    }}, 16);
  }});
  return outcome;
}}"""


def parse_settle_result(text: str) -> dict:
    """Read {{settled, reason}} from an evaluate result. Unknown text is quiet."""
    for match in re.finditer(r"\{[^{}]*\}", text or ""):
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("reason") in {"quiet", "timeout"}:
            reason = data["reason"]
            return {"settled": reason == "quiet", "reason": reason}
    return {"settled": True, "reason": "quiet"}


async def settle_page(
    child,
    *,
    quiet_ms: int = QUIET_MS,
    timeout_ms: int = SETTLE_TIMEOUT_MS,
    timeout_s: float | None = None,
) -> dict:
    """Wait for a quiet DOM. Always returns, including when the wait times out."""
    limit = PROXY_TIMEOUT_S if timeout_s is None else timeout_s
    try:
        result = await asyncio.wait_for(
            child.call_tool(
                "browser_evaluate",
                {"function": settle_source(quiet_ms, timeout_ms)},
            ),
            limit,
        )
    except (TimeoutError, asyncio.TimeoutError):
        return {"settled": False, "reason": "timeout"}
    if isinstance(result, dict) and result.get("isError") is True:
        return {"settled": False, "reason": "timeout"}
    raw = tool_text(result if isinstance(result, dict) else {})
    return parse_settle_result(raw)
