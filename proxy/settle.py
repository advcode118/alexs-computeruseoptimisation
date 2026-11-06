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
import os
import re

from proxy.page import tool_text

# LangChain's Stagehand settle waits until the page has been quiet for 500ms.
# That stays the accuracy default while the page is still mutating. A short
# page whose meaningful mutation rate is already 0 uses a tight cap, and a
# short page uses a lower quiet window after the first quiet network once
# mutations have stopped. The cap is longer than the quiet window so a slow
# page can still finish; a page that never goes quiet returns at the cap.
# SETTLE_QUIET_MS and SETTLE_TIMEOUT_MS override the defaults. The Python wait
# is longer than the in-page cap so the evaluate is not killed while it is
# still counting.
QUIET_MS = 500
SETTLE_TIMEOUT_MS = 3000
PROXY_TIMEOUT_S = 4.0
# Fast path for a short page only. A page that is still mutating keeps QUIET_MS.
FAST_QUIET_MS = 80
FAST_CAP_MS = 100
SHORT_NODE_LIMIT = 400
QUIET_ENV = "SETTLE_QUIET_MS"
TIMEOUT_ENV = "SETTLE_TIMEOUT_MS"

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


def _env_int(name: str, default: int, *, low: int, high: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    if value < low or value > high:
        return default
    return value


def configured_quiet_ms() -> int:
    """Quiet window in milliseconds. SETTLE_QUIET_MS overrides the 500ms default."""
    return _env_int(QUIET_ENV, QUIET_MS, low=0, high=10_000)


def configured_timeout_ms() -> int:
    """In-page cap. SETTLE_TIMEOUT_MS overrides the 3000ms default."""
    return _env_int(TIMEOUT_ENV, SETTLE_TIMEOUT_MS, low=1, high=30_000)


def plan_settle(
    events: list[tuple[int, bool]],
    *,
    quiet_ms: int = QUIET_MS,
    timeout_ms: int = SETTLE_TIMEOUT_MS,
    short: bool = False,
    network_quiet_ms: int | None = None,
    fast_quiet_ms: int = FAST_QUIET_MS,
    fast_cap_ms: int = FAST_CAP_MS,
) -> tuple[str, int]:
    """'(reason, end_ms)' for (time_ms, meaningful) DOM events.

    quiet_ms, default 500, is the accuracy wait. It stays in force while the
    page is still mutating, and for a page that is not short.

    A short page has two fast paths. When the meaningful mutation rate is
    already 0, the wait ends at fast_cap_ms. After the first quiet network,
    once mutations have stopped, the quiet window drops to fast_quiet_ms.
    Neither path ends the wait between meaningful mutations.
    """
    fast_quiet = min(max(int(fast_quiet_ms), 0), int(quiet_ms))
    fast_cap = min(max(int(fast_cap_ms), 0), int(quiet_ms))
    mutations = sorted(time_ms for time_ms, meaningful in events if meaningful and 0 <= time_ms < timeout_ms)
    network_at = network_quiet_ms

    def can_stop(now: int, last: int, seen: bool) -> bool:
        if now <= 0:
            return False
        if short and not seen:
            return now >= fast_cap
        if (
            short
            and seen
            and network_at is not None
            and network_at < now
            and now - last >= fast_quiet
            and now - network_at >= fast_quiet
        ):
            return True
        return now - last >= quiet_ms

    last = 0
    seen = False
    cursor = 0
    points = {fast_cap, quiet_ms, timeout_ms}
    for time_ms in mutations:
        points.add(time_ms)
        points.add(min(timeout_ms, time_ms + fast_quiet))
        points.add(min(timeout_ms, time_ms + quiet_ms))
    if network_at is not None and 0 <= network_at < timeout_ms:
        points.add(network_at)
        points.add(min(timeout_ms, network_at + fast_quiet))
    for now in sorted(point for point in points if 0 < point <= timeout_ms):
        while cursor < len(mutations) and mutations[cursor] < now:
            seen = True
            last = mutations[cursor]
            cursor += 1
        if cursor < len(mutations) and mutations[cursor] == now:
            seen = True
            last = now
            cursor += 1
            continue
        if can_stop(now, last, seen):
            if short and not seen:
                return "quiet", fast_cap
            return "quiet", now
    while cursor < len(mutations) and mutations[cursor] < timeout_ms:
        seen = True
        last = mutations[cursor]
        cursor += 1
    if can_stop(timeout_ms, last, seen):
        if short and not seen:
            return "quiet", fast_cap
        return "quiet", timeout_ms
    return "timeout", timeout_ms


def decide_settle(
    events: list[tuple[int, bool]],
    *,
    quiet_ms: int = QUIET_MS,
    timeout_ms: int = SETTLE_TIMEOUT_MS,
    short: bool = False,
    network_quiet_ms: int | None = None,
    fast_quiet_ms: int = FAST_QUIET_MS,
    fast_cap_ms: int = FAST_CAP_MS,
) -> str:
    """'quiet' or 'timeout' for a list of (time_ms, meaningful) events.

    The clock starts at 0. A meaningful event resets the quiet timer.
    A gap of quiet_ms after the last meaningful event ends the wait, including
    a page that never mutates, unless the short-page fast path ends sooner.
    Otherwise the wait ends at timeout_ms. A page that is still mutating does
    not take the fast path.
    """
    reason, _end = plan_settle(
        events,
        quiet_ms=quiet_ms,
        timeout_ms=timeout_ms,
        short=short,
        network_quiet_ms=network_quiet_ms,
        fast_quiet_ms=fast_quiet_ms,
        fast_cap_ms=fast_cap_ms,
    )
    return reason


def settle_source(
    quiet_ms: int = QUIET_MS,
    timeout_ms: int = SETTLE_TIMEOUT_MS,
    *,
    fast_quiet_ms: int = FAST_QUIET_MS,
    fast_cap_ms: int = FAST_CAP_MS,
    short_node_limit: int = SHORT_NODE_LIMIT,
) -> str:
    """Page function. Returns a JSON string so the tool text is parseable.

    The 500ms quiet window stays the accuracy default. A short page whose
    meaningful mutation rate is already 0 uses the tight cap. After the first
    quiet network, a short page that has stopped mutating uses the lower quiet
    window. Mutations keep the 500ms window.
    """
    fast_quiet = min(max(int(fast_quiet_ms), 0), int(quiet_ms))
    fast_cap = min(max(int(fast_cap_ms), 0), int(quiet_ms))
    return f"""async () => {{
  const quietMs = {int(quiet_ms)};
  const timeoutMs = {int(timeout_ms)};
  const fastQuietMs = {fast_quiet};
  const fastCapMs = {fast_cap};
  const shortNodeLimit = {int(short_node_limit)};
  const started = Date.now();
  let last = started;
  let seenMutation = false;
  let networkQuietAt = 0;
  let sawNetworkQuiet = false;
  let netCount = 0;
  let lastNet = performance.now();
  try {{
    netCount = performance.getEntriesByType("resource").length;
  }} catch (e) {{
    netCount = 0;
  }}
  const skip = new Set(["SCRIPT", "STYLE", "NOSCRIPT", "TEMPLATE"]);
  const attrOk = /^(role|alt|title|href|value|placeholder|name|open|tabindex|contenteditable|type|disabled|hidden|checked|selected|aria-)/;
  const elementOf = (node) => {{
    if (!node) return null;
    return node.nodeType === 1 ? node : node.parentElement;
  }};
  const isShort = () => {{
    try {{
      return document.getElementsByTagName("*").length <= shortNodeLimit;
    }} catch (e) {{
      return false;
    }}
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
  const markNetwork = () => {{
    try {{
      const entries = performance.getEntriesByType("resource");
      if (entries.length !== netCount) {{
        netCount = entries.length;
        lastNet = performance.now();
      }}
    }} catch (e) {{}}
    const quiet = document.readyState === "complete" && (performance.now() - lastNet) >= 40;
    if (quiet && !sawNetworkQuiet) {{
      sawNetworkQuiet = true;
      networkQuietAt = Date.now();
    }}
  }};
  const outcome = await new Promise((resolve) => {{
    let finished = false;
    const done = (reason, fast) => {{
      if (finished) return;
      finished = true;
      observer.disconnect();
      clearInterval(tick);
      resolve(JSON.stringify({{ settled: reason === "quiet", reason, fast: !!fast }}));
    }};
    const observer = new MutationObserver((records) => {{
      for (const record of records) {{
        if (meaningful(record)) {{
          seenMutation = true;
          last = Date.now();
        }}
      }}
    }});
    const root = document.documentElement || document;
    observer.observe(root, {{ subtree: true, childList: true, attributes: true, characterData: true }});
    const tick = setInterval(() => {{
      const now = Date.now();
      const elapsed = now - started;
      markNetwork();
      const short = isShort();
      if (short && !seenMutation && elapsed >= fastCapMs) {{
        done("quiet", true);
        return;
      }}
      if (short && seenMutation && sawNetworkQuiet) {{
        const anchor = Math.max(last, networkQuietAt);
        if (now - anchor >= fastQuietMs && now - last >= fastQuietMs) {{
          done("quiet", true);
          return;
        }}
      }}
      if (elapsed >= timeoutMs) {{
        if (now - last >= quietMs) done("quiet", false);
        else done("timeout", false);
        return;
      }}
      if (now - last >= quietMs) done("quiet", false);
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
    quiet_ms: int | None = None,
    timeout_ms: int | None = None,
    timeout_s: float | None = None,
) -> dict:
    """Wait for a quiet DOM. Always returns, including when the wait times out.

    Omit quiet_ms and timeout_ms to use SETTLE_QUIET_MS / SETTLE_TIMEOUT_MS,
    which fall back to 500ms and 3000ms.
    """
    quiet = configured_quiet_ms() if quiet_ms is None else quiet_ms
    cap = configured_timeout_ms() if timeout_ms is None else timeout_ms
    limit = PROXY_TIMEOUT_S if timeout_s is None else timeout_s
    if timeout_s is None:
        limit = max(PROXY_TIMEOUT_S, cap / 1000 + 1.0)
    try:
        result = await asyncio.wait_for(
            child.call_tool(
                "browser_evaluate",
                {"function": settle_source(quiet, cap)},
            ),
            limit,
        )
    except (TimeoutError, asyncio.TimeoutError):
        return {"settled": False, "reason": "timeout"}
    if isinstance(result, dict) and result.get("isError") is True:
        return {"settled": False, "reason": "timeout"}
    raw = tool_text(result if isinstance(result, dict) else {})
    return parse_settle_result(raw)
