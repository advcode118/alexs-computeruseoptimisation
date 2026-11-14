"""Forgiving target resolution and waits for script_first's executor.

One page.evaluate scores every control on the page against the name the
script gave, marks the best one, and Playwright then acts on that mark.
Exact names beat partial ones; ambiguous visible matches fail before acting.
A name that is not on the
page yet is looked for again for a few seconds. A miss lists the visible
controls, so a repair turn can use a real name.

Nothing here knows a site, a task, or the judge's markers.
"""

from __future__ import annotations

import asyncio
import inspect
import re

from bench.script_helpers import HelperCall
from proxy.script import ScriptError

RESOLVE_JS = r"""(args) => {
  const op = args.op, mark = args.mark;
  const norm = (s) => String(s == null ? "" : s).replace(/[\s ]+/g, " ").trim().toLowerCase()
    .replace(/^[\s:*•·›»>\-–—]+/, "").replace(/[\s:*?!.…›»>]+$/, "").trim();
  const words = (s) => norm(s).split(/[^\p{L}\p{N}]+/u).filter(Boolean);
  const want = norm(args.target);
  const wantWords = words(args.target);
  let re = null;
  if (args.pattern) { try { re = new RegExp(args.pattern, args.flags || ""); } catch (e) { re = null; } }
  const all = [];
  const walk = (root) => {
    for (const el of root.querySelectorAll("*")) {
      all.push(el);
      if (el.shadowRoot) walk(el.shadowRoot);
    }
  };
  walk(document);
  for (const old of document.querySelectorAll("[data-cu-mark]")) old.removeAttribute("data-cu-mark");
  const NOT_TEXT = new Set(["hidden", "submit", "button", "reset", "image", "checkbox", "radio", "file", "range", "color"]);
  const tag = (el) => el.tagName.toLowerCase();
  const role = (el) => (el.getAttribute("role") || "").toLowerCase();
  const isField = (el) => {
    const t = tag(el);
    if (t === "input") return !NOT_TEXT.has((el.getAttribute("type") || "text").toLowerCase());
    if (t === "textarea" || t === "select") return true;
    if (el.isContentEditable && el.getAttribute("contenteditable") !== null) return true;
    return ["textbox", "searchbox", "combobox", "spinbutton"].includes(role(el));
  };
  const isCheck = (el) => {
    const t = (el.getAttribute("type") || "").toLowerCase();
    return (tag(el) === "input" && (t === "checkbox" || t === "radio")) || ["checkbox", "radio", "switch"].includes(role(el));
  };
  const CLICK_ROLES = ["button", "link", "tab", "menuitem", "menuitemcheckbox", "menuitemradio", "option", "checkbox", "radio", "switch", "treeitem"];
  const isClickable = (el) => {
    const t = tag(el);
    if (t === "a" && el.hasAttribute("href")) return true;
    if (t === "button" || t === "summary" || t === "select") return true;
    if (t === "input") return ["submit", "button", "reset", "image", "checkbox", "radio"].includes((el.getAttribute("type") || "").toLowerCase());
    if (CLICK_ROLES.includes(role(el))) return true;
    return el.hasAttribute("onclick");
  };
  const visible = (el) => {
    if (tag(el) === "option") { const sel = el.closest("select"); return !!sel && visible(sel); }
    if (!el.getClientRects().length) return false;
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) return false;
    const st = getComputedStyle(el);
    return st.visibility !== "hidden" && st.visibility !== "collapse" && st.display !== "none" && Number(st.opacity) > 0.05;
  };
  const disabled = (el) => !!(el.disabled || el.getAttribute("aria-disabled") === "true");
  const ownText = (el) => String((el.innerText != null ? el.innerText : el.textContent) || "").slice(0, 300);
  const byId = (id) => { const n = document.getElementById(id); return n ? ownText(n) : ""; };
  const names = (el) => {
    const out = [];
    const add = (v, w) => { if (v && String(v).trim()) out.push([String(v), w]); };
    const field = isField(el);
    add(el.getAttribute("aria-label"), 1);
    const lb = el.getAttribute("aria-labelledby");
    if (lb) add(lb.split(/\s+/).map(byId).join(" "), 1);
    if (el.labels) for (const l of el.labels) add(ownText(l), 1);
    add(el.getAttribute("placeholder"), 1);
    if (!field && tag(el) !== "select") add(ownText(el), 1);
    if (tag(el) === "input" && !field) add(el.value, 1);
    add(el.getAttribute("title"), 0.9);
    add(el.getAttribute("alt"), 0.9);
    const img = !field ? el.querySelector("img[alt], svg[aria-label]") : null;
    if (img) add(img.getAttribute("alt") || img.getAttribute("aria-label"), 0.85);
    // A form's submit button also answers to "Submit", whatever its own text is.
    const type = (el.getAttribute("type") || "").toLowerCase();
    if ((tag(el) === "button" && (type === "submit" || (!type && el.form))) || (tag(el) === "input" && (type === "submit" || type === "image"))) add("submit", 0.75);
    const nm = el.getAttribute("name") || el.id || "";
    if (nm) add(nm.replace(/[-_.\[\]]+/g, " ").replace(/([a-z])([A-Z])/g, "$1 $2"), 0.6);
    return out;
  };
  const score = (name) => {
    const n = norm(name);
    if (!n) return 0;
    if (re) return (re.test(String(name)) || re.test(n)) ? 90 - Math.min(20, Math.max(0, n.length - 20) / 4) : 0;
    if (!want) return 0;
    if (n === want) return 100;
    const pen = Math.min(30, Math.max(0, n.length - want.length) / 3);
    const nw = words(name);
    if (nw.length && wantWords.length) {
      const joined = " " + nw.join(" ") + " ";
      const ww = " " + wantWords.join(" ") + " ";
      if (joined === ww) return 96;
      if (joined.startsWith(ww)) return 85 - pen;
      if (joined.includes(ww)) return 78 - pen;
    }
    const nc = n.replace(/[^\p{L}\p{N}]+/gu, ""), wc = want.replace(/[^\p{L}\p{N}]+/gu, "");
    if (wc && nc === wc) return 94;
    if (wc.length >= 4 && nc.startsWith(wc)) return 80 - pen;
    if (want.length >= 3 && n.includes(want)) return 62 - pen;
    if (wc.length >= 4 && nc.includes(wc)) return 60 - pen;
    if (n.length >= 3 && want.includes(n)) return 45 + 20 * (n.length / want.length);
    if (nw.length && wantWords.length) {
      const set = new Set(nw);
      const hit = wantWords.filter((w) => set.has(w)).length;
      const frac = hit / wantWords.length;
      if (frac >= 0.6) return 40 * frac + 10 * (hit / nw.length);
    }
    return 0;
  };
  const best = (el) => {
    let s = 0;
    for (const [v, w] of names(el)) s = Math.max(s, score(v) * w);
    return s;
  };
  const FIELD_SEL = "input, textarea, select, [contenteditable], [role=textbox], [role=searchbox], [role=combobox], [role=spinbutton]";
  const fieldNear = (el) => {
    if (tag(el) === "label" && el.control) return el.control;
    let box = el;
    for (let i = 0; i < 3 && box; i++) {
      box = box.parentElement;
      if (!box || box === document.body) break;
      const found = Array.from(box.querySelectorAll(FIELD_SEL)).filter(isField);
      const after = found.filter((f) => el.compareDocumentPosition(f) & Node.DOCUMENT_POSITION_FOLLOWING);
      if (after.length) return after[0];
      if (found.length === 1) return found[0];
    }
    return null;
  };
  const wantsField = op === "fill" || op === "press";
  const wantsCheck = op === "check";
  const cands = new Map();
  // s ranks a candidate; raw is how well its name alone matched (94 and up: the same words).
  const put = (el, s, why, raw) => {
    if (!el || s <= 0) return;
    const prev = cands.get(el);
    if (!prev || prev.s < s) cands.set(el, { s, why, raw });
  };
  for (const el of all) {
    const field = isField(el);
    const click = isClickable(el);
    if (wantsField) {
      if (field) { const b = best(el); put(el, b + 20, "field", b); }
      else if (!click || tag(el) === "label") {
        if (el.children.length <= 2) {
          const own = ownText(el);
          if (own && own.length <= 120) {
            const s = score(own);
            if (s > 0) put(fieldNear(el), s * 0.8, "near text", s);
          }
        }
      }
    } else if (wantsCheck) {
      if (isCheck(el)) { const b = best(el); put(el, b + 20, "checkbox", b); }
      else if (tag(el) === "label") {
        const s = score(ownText(el));
        if (s > 0) put(el.control && isCheck(el.control) ? el.control : el, s, "label", s);
      }
    } else {
      if (click) { const b = best(el); put(el, b + 15, "control", b); }
      else if (el.children.length <= 3) {
        const own = ownText(el);
        if (own && own.length <= 200) {
          const s = score(own) * 0.9;
          if (s > 0) {
            const up = el.closest("a[href], button, [role=button], [role=link], [role=tab], [role=menuitem], [role=option], summary, label, [onclick]");
            put(up || el, s, up ? "text in control" : "text", s / 0.9);
          }
        }
      }
    }
  }
  const ranked = [];
  for (const [el, c] of cands) {
    if (c.s < 38) continue;
    // Text wrappers repeat their descendants' names; they are not another
    // actionable target. Keep distinct controls even when their names match.
    if (c.why === "text" && Array.from(cands).some(([child, match]) =>
      child !== el && el.contains(child) && match.raw > 0 &&
      (isClickable(child) || isField(child)))) continue;
    const vis = visible(el);
    ranked.push({ el, s: c.s + (vis ? 40 : -60) - (disabled(el) ? 30 : 0), vis, raw: c.raw || 0 });
  }
  // Ties stay in document order: the Map keeps insertion order and sort is stable.
  ranked.sort((a, b) => b.s - a.s);
  const describe = (el) => {
    const n = names(el).map((p) => p[0]).find((v) => v && v.trim()) || ownText(el);
    return (role(el) || tag(el)) + " " + JSON.stringify(String(n).replace(/\s+/g, " ").trim().slice(0, 60));
  };
  let pick = ranked.length && ranked[0].s >= 60 ? ranked[0] : null;
  const exactHits = ranked.filter((c) => c.vis && (re ? c.raw > 0 : c.raw >= 88));
  const ties = ranked.filter((c) => pick && c.s === pick.s).length;
  let ambiguous = [];
  if (args.strict && pick) {
    // Exact and unique first. Several different exact matches, or a partial
    // match with a close rival, is ambiguous: fail and list them.
    const pool = exactHits.length ? exactHits : ranked.filter((c) => c.vis && c.raw >= pick.raw - 10);
    // The Map already deduplicates DOM elements. Identical display names (or
    // hrefs) do not make distinct controls interchangeable.
    if (pool.length > 1) { ambiguous = pool.slice(0, 8).map((c) => describe(c.el)); pick = null; }
    else if (pool.length === 1) pick = pool[0];
  }
  if (ambiguous.length) return { found: false, ambiguous: true, near: ambiguous };
  if (pick) {
    const top = pick;
    top.el.setAttribute("data-cu-mark", mark);
    let covered = false;
    if (top.vis) {
      const r = top.el.getBoundingClientRect();
      const x = r.left + r.width / 2, y = r.top + r.height / 2;
      if (x >= 0 && y >= 0 && x < innerWidth && y < innerHeight) {
        const hit = document.elementFromPoint(x, y);
        covered = !!hit && hit !== top.el && !top.el.contains(hit) && !hit.contains(top.el)
          && !(top.el.labels && Array.from(top.el.labels).some((l) => l.contains(hit)));
      }
    }
    return { found: true, desc: describe(top.el), score: Math.round(top.s), exact: top.raw >= 88, ties, covered, visible: top.vis, field: isField(top.el), tag: tag(top.el) };
  }
  const near = [];
  const seen = new Set();
  const note = (el) => {
    const d = describe(el);
    if (!seen.has(d) && d.length > 4) { seen.add(d); near.push(d); }
  };
  for (const c of ranked) {
    if (near.length >= 8) break;
    if (c.vis) note(c.el);
  }
  for (const el of all) {
    if (near.length >= 8) break;
    const ok = wantsField ? isField(el) : wantsCheck ? isCheck(el) : (isClickable(el) && tag(el) !== "a");
    if (ok && visible(el)) note(el);
  }
  return { found: false, near };
}"""

# Close a cookie or consent banner, or a modal, that sits over the page. It
# clicks one visible button whose whole name is a plain accept or close word,
# inside a dialog, a fixed overlay, or a container named for cookies or consent.
DISMISS_JS = r"""() => {
  const words = /^(accept|accept all|accept all cookies|accept cookies|allow|allow all|allow all cookies|allow cookies|agree|i agree|agree and close|agree & close|i accept|accept and close|accept & close|accept and continue|got it|ok|okay|i understand|understood|continue|close|dismiss|no thanks|no, thanks|not now|maybe later|reject all|decline|deny|only necessary|necessary only|reject|×|✕|✖|x)$/i;
  const norm = (s) => String(s || "").replace(/[\s ]+/g, " ").trim();
  const visible = (el) => {
    if (!el.getClientRects().length) return false;
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) return false;
    const st = getComputedStyle(el);
    return st.visibility !== "hidden" && st.display !== "none" && Number(st.opacity) > 0.05;
  };
  const boxSel = "[role=dialog], [role=alertdialog], [aria-modal=true], dialog[open], [id*=cookie i], [class*=cookie i], [id*=consent i], [class*=consent i], [id*=gdpr i], [class*=gdpr i], [id*=onetrust i], [class*=banner i], [class*=modal i], [class*=popup i], [class*=overlay i], [id*=privacy i], [class*=privacy i]";
  const boxes = Array.from(document.querySelectorAll(boxSel)).filter(visible);
  let scanned = 0;
  for (const el of document.querySelectorAll("body *")) {
    if (++scanned > 5000 || boxes.length > 60) break;
    const st = getComputedStyle(el);
    if ((st.position === "fixed" || st.position === "sticky") && Number(st.zIndex || 0) >= 10 && visible(el)) boxes.push(el);
  }
  const rank = (t) => /^(accept|allow|agree|i agree|i accept|got it|ok|okay)/i.test(t) ? 0 : /^(close|dismiss|×|✕|✖|x)$/i.test(t) ? 1 : 2;
  let pick = null, pickRank = 9;
  for (const box of boxes) {
    for (const b of box.querySelectorAll("button, [role=button], a, input[type=button], input[type=submit]")) {
      if (!visible(b)) continue;
      const t = norm(b.getAttribute("aria-label") || b.innerText || b.value || b.getAttribute("title"));
      if (!words.test(t)) continue;
      const r = rank(t);
      if (r < pickRank) { pick = b; pickRank = r; }
    }
  }
  if (!pick) return "";
  const label = norm(pick.getAttribute("aria-label") || pick.innerText || pick.value);
  pick.click();
  return label || "button";
}"""

# Resolve when the DOM has been quiet for `quiet` ms, or after `cap` ms.
QUIET_JS = r"""(args) => new Promise((resolve) => {
  let last = performance.now();
  const start = last;
  const obs = new MutationObserver(() => { last = performance.now(); });
  try { obs.observe(document.documentElement || document, { childList: true, subtree: true, characterData: true }); } catch (e) {}
  const tick = () => {
    const now = performance.now();
    if (now - last >= args.quiet || now - start >= args.cap) { obs.disconnect(); resolve(document.readyState); return; }
    setTimeout(tick, 40);
  };
  setTimeout(tick, 40);
})"""

# The site's own search box: a search-typed or search-named field.
SEARCH_JS = r"""(mark) => {
  for (const old of document.querySelectorAll("[data-cu-mark]")) old.removeAttribute("data-cu-mark");
  const visible = (el) => {
    if (!el.getClientRects().length) return false;
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) return false;
    const st = getComputedStyle(el);
    return st.visibility !== "hidden" && st.display !== "none" && Number(st.opacity) > 0.05;
  };
  const attrs = (el) => [el.getAttribute("placeholder"), el.getAttribute("aria-label"), el.getAttribute("title"), el.getAttribute("name"), el.id, typeof el.className === "string" ? el.className : "", el.labels ? Array.from(el.labels).map((l) => l.innerText).join(" ") : ""].join(" ").toLowerCase();
  const all = [];
  const walk = (root) => {
    for (const el of root.querySelectorAll("input, textarea, [role=searchbox], [role=combobox], [contenteditable]")) all.push(el);
    for (const h of root.querySelectorAll("*")) if (h.shadowRoot) walk(h.shadowRoot);
  };
  walk(document);
  let top = null, topScore = 0;
  for (const el of all) {
    const type = (el.getAttribute("type") || "text").toLowerCase();
    if (el.tagName === "INPUT" && !["text", "search"].includes(type)) continue;
    let s = 0;
    const a = attrs(el);
    if (type === "search") s += 50;
    if ((el.getAttribute("role") || "") === "searchbox") s += 50;
    if (el.closest("[role=search], form[action*=search i], form[class*=search i], form[id*=search i]")) s += 30;
    if (/search|find|query|look ?up/.test(a)) s += 40;
    if (/^(q|query|search|s|k|kw|keyword|keywords|term|terms|searchterm|search_query|search-query)$/i.test(el.getAttribute("name") || "")) s += 30;
    if (s === 0) continue;
    if (visible(el)) s += 40; else s -= 30;
    if (el.disabled || el.readOnly) s -= 40;
    if (s > topScore) { top = el; topScore = s; }
  }
  if (top && topScore >= 60) {
    top.setAttribute("data-cu-mark", mark);
    return { found: true, visible: visible(top) };
  }
  for (const b of document.querySelectorAll("button, [role=button], summary, label, a")) {
    if (!visible(b)) continue;
    const a = [b.getAttribute("aria-label"), b.getAttribute("title"), b.innerText, typeof b.className === "string" ? b.className : "", b.id].join(" ").toLowerCase();
    if (!/search/.test(a)) continue;
    if (b.tagName === "A" && /^https?:/i.test(b.getAttribute("href") || "")) continue;
    b.setAttribute("data-cu-mark", mark);
    return { found: false, toggle: true };
  }
  return { found: false, toggle: false };
}"""

_SET_VALUE_JS = r"""(el, value) => {
  el.focus();
  if (el.isContentEditable) { el.textContent = value; }
  else {
    const proto = el.tagName === "TEXTAREA" ? HTMLTextAreaElement.prototype : el.tagName === "SELECT" ? HTMLSelectElement.prototype : HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(proto, "value").set.call(el, value);
  }
  el.dispatchEvent(new Event("input", { bubbles: true }));
  el.dispatchEvent(new Event("change", { bubbles: true }));
}"""

_PICK_OPTION_JS = r"""(el, want) => {
  const low = (s) => String(s || "").replace(/\s+/g, " ").trim().toLowerCase();
  const w = low(want);
  const opts = Array.from(el.options || []);
  const o = opts.find((x) => low(x.text) === w || low(x.value) === w)
    || opts.find((x) => low(x.text) && (low(x.text).includes(w) || w.includes(low(x.text))));
  return o ? o.value : null;
}"""

_CHOOSE_OPTION_JS = r"""(el) => {
  const select = el.closest("select");
  if (!select) return false;
  select.value = el.value;
  select.dispatchEvent(new Event("input", { bubbles: true }));
  select.dispatchEvent(new Event("change", { bubbles: true }));
  return true;
}"""

_SUBMIT_FORM_JS = r"""(el) => {
  const form = el.form || el.closest("form");
  if (!form) return false;
  const btn = form.querySelector("button[type=submit], input[type=submit], button:not([type]), input[type=image]");
  if (btn) { btn.click(); return true; }
  return false;
}"""

# Read-only page functions may run again when they come back empty or throw
# while the page is still changing. A function with one of these is not re-run.
_SIDE_EFFECT = re.compile(
    r"\.click\s*\(|\.submit\s*\(|requestSubmit|dispatchEvent|\.focus\s*\(|\.value\s*=[^=]|\.checked\s*=[^=]"
    r"|\.selected\s*=[^=]|location(?:\.href)?\s*=[^=]|location\.(?:assign|replace|reload)|history\."
    r"|\.innerHTML\s*=[^=]|\.textContent\s*=[^=]|setAttribute|removeAttribute|\.remove\s*\(|appendChild|scroll|fetch"
)

_POLL_S = 0.25
# True: a name must match one control exactly, or one control clearly better
# than any other; otherwise the step fails and lists the candidates.
STRICT_MATCH = True
# A name that is not on the page yet is looked for again until this cap.
FIND_CAP_S = 3.0
_SETTLE_QUIET_MS = 150
SETTLE_CAP_MS = 1000


def side_effect_free(function: str) -> bool:
    return not _SIDE_EFFECT.search(function or "")


async def _await(value, timeout: float | None = None):
    if asyncio.iscoroutine(value) or isinstance(value, asyncio.Future):
        if timeout is None:
            return await value
        return await asyncio.wait_for(value, timeout=timeout)
    return value


async def _try(fn, *args, timeout: float | None = None, **kwargs):
    """Call a page method that may be absent on a fake page. Errors become None."""
    if not callable(fn):
        return None
    try:
        return await _await(fn(*args, **kwargs), timeout)
    except Exception:
        return None


def page_url(page) -> str:
    url = getattr(page, "url", "") or ""
    return url if isinstance(url, str) else ""


def _real_page(page) -> bool:
    """True for a Playwright page. Test fakes without load-state waits skip the waits."""
    wait = getattr(page, "wait_for_load_state", None)
    return callable(wait) and inspect.iscoroutinefunction(wait)


async def settle(page, *, cap_ms: int = SETTLE_CAP_MS) -> None:
    """Wait for a navigation an action started, then for the DOM to go quiet.

    Both waits are capped. A page with no navigation and no changes costs one
    quiet window.
    """
    if not _real_page(page):
        return
    await _try(page.wait_for_load_state, "domcontentloaded", timeout=10)
    for _ in range(2):
        try:
            await asyncio.wait_for(page.evaluate(QUIET_JS, {"quiet": _SETTLE_QUIET_MS, "cap": cap_ms}), cap_ms / 1000 + 1)
            return
        except Exception:
            # The document changed under the wait: a navigation. Wait for it once more.
            await _try(page.wait_for_load_state, "domcontentloaded", timeout=10)


async def dismiss_obstacles(page) -> str:
    """Close one consent banner or modal over the page. Returns what was clicked."""
    if not _real_page(page):
        return ""
    found = await _try(page.evaluate, DISMISS_JS, timeout=2)
    if isinstance(found, str) and found:
        await settle(page, cap_ms=600)
        return found
    return ""


_COUNTER = [0]


def _new_mark() -> str:
    _COUNTER[0] += 1
    return f"cu{_COUNTER[0]}"


def mark_locator(page, mark: str):
    return page.locator(f'[data-cu-mark="{mark}"]')


def _blocked(exc: Exception) -> bool:
    text = str(exc)
    return any(
        word in text
        for word in ("intercepts pointer events", "not visible", "Timeout", "outside of the viewport", "not stable")
    )


async def resolve(page, target: str, op: str, *, pattern: str = "", flags: str = "", cap_s: float = FIND_CAP_S) -> tuple[str, dict]:
    """Mark the best control for `target`, looking again while the page renders.

    Returns (mark, info). mark is "" when nothing matched; info["near"] then
    lists visible controls the repair turn can use.
    """
    loop = asyncio.get_running_loop()
    deadline = loop.time() + cap_s
    dismissed = False
    info: dict = {}
    while True:
        mark = _new_mark()
        try:
            got = await _await(
                page.evaluate(
                    RESOLVE_JS,
                    {"target": target, "op": op, "mark": mark, "pattern": pattern, "flags": flags, "strict": STRICT_MATCH},
                ),
                5,
            )
        except Exception:
            got = None
            await _try(getattr(page, "wait_for_load_state", None), "domcontentloaded", timeout=5)
        info = got if isinstance(got, dict) else {"found": False, "near": []}
        if info.get("ambiguous"):
            return "", info
        now = loop.time()
        if info.get("found"):
            if info.get("covered") and not dismissed:
                dismissed = True
                if await dismiss_obstacles(page):
                    continue
            if info.get("visible") or now >= deadline:
                return mark, info
        else:
            if not dismissed and now >= deadline - cap_s / 2:
                dismissed = True
                if await dismiss_obstacles(page):
                    continue
            if now >= deadline:
                return "", info
        await asyncio.sleep(_POLL_S)


def miss_error(line: int, what: str, target: str, info: dict) -> RuntimeError:
    near = [str(item) for item in (info.get("near") or []) if str(item).strip()][:8]
    if info.get("ambiguous"):
        return RuntimeError(f"line {line}: {len(near)} {what}s match {target!r}: {', '.join(near)}; use a unique name or an explicitly scoped/positioned locator")
    hint = f"; visible: {', '.join(near)}" if near else ""
    return RuntimeError(f"line {line}: no {what} named {target!r}{hint}")


async def _fill(locator, value: str, timeout_ms: int) -> None:
    try:
        await _await(locator.fill(value, timeout=timeout_ms))
    except Exception as exc:
        text = str(exc)
        if "<select>" in text:
            await select_option(locator, value, timeout_ms)
            return
        if "not an <input>" in text or "not editable" in text:
            await _await(locator.evaluate(_SET_VALUE_JS, value), 3)
            return
        raise


async def select_option(locator, value, timeout_ms: int) -> None:
    """Select by value or label, then by an option whose text or value matches loosely.

    Playwright waits the whole timeout for an option that does not exist, so
    on a live page the exact try is short and the loose match follows.
    """
    evaluate = getattr(locator, "evaluate", None)
    exact_ms = 1500 if callable(evaluate) and inspect.iscoroutinefunction(evaluate) else timeout_ms
    want = value
    try:
        if isinstance(value, dict):
            await _await(locator.select_option(timeout=exact_ms, **value))
        elif isinstance(value, (list, tuple)):
            await _await(locator.select_option(list(value), timeout=exact_ms))
        else:
            await _await(locator.select_option(value, timeout=exact_ms))
        return
    except Exception as exc:
        first = exc
    if isinstance(value, dict):
        want = next((str(value[key]) for key in ("label", "value") if isinstance(value.get(key), (str, int, float))), "")
    elif isinstance(value, (list, tuple)):
        want = str(value[0]) if len(value) == 1 else ""
    if not want or not callable(evaluate):
        raise first
    picked = await _try(evaluate, _PICK_OPTION_JS, want, timeout=3)
    if not isinstance(picked, str):
        raise first
    await _await(locator.select_option(picked, timeout=timeout_ms))


async def act_on(page, locator, op: str, value="", *, timeout_ms: int) -> None:
    """Act on one element. A blocked action closes an overlay and tries again,
    then uses the page's own click or value setter, which an overlay cannot block.
    """
    real = _real_page(page)
    first = min(timeout_ms, 2500) if real else timeout_ms
    try:
        if op == "click":
            await _await(locator.click(timeout=first))
        elif op == "fill":
            await _fill(locator, value, first)
        elif op == "press":
            await _await(locator.press(value, timeout=first))
        elif op == "check":
            await _await(locator.check(timeout=first))
        elif op == "uncheck":
            await _await(locator.uncheck(timeout=first))
        elif op == "select":
            await select_option(locator, value, first)
        else:
            raise ScriptError(f"unsupported action {op}")
        return
    except ScriptError:
        raise
    except Exception as exc:
        if not real or not _blocked(exc):
            raise
        error = exc
    await dismiss_obstacles(page)
    try:
        if op == "click":
            await _await(locator.click(timeout=1500))
            return
        if op == "fill":
            await _fill(locator, value, 1500)
            return
        if op == "press":
            await _await(locator.press(value, timeout=1500))
            return
        if op in {"check", "uncheck"}:
            await _await(getattr(locator, op)(timeout=1500))
            return
    except Exception as exc:
        error = exc
    if "not visible" in str(error) or "Timeout" in str(error):
        if op in {"click", "check", "uncheck"}:
            await _await(locator.evaluate("(el) => { el.scrollIntoView({block: 'center'}); el.click(); }"), 3)
            return
        if op == "fill":
            await _await(locator.evaluate(_SET_VALUE_JS, value), 3)
            return
    raise error


async def submit_if_still(page, locator, before: str) -> None:
    """Enter in a field that did nothing: click its form's submit control."""
    if not _real_page(page):
        return
    await settle(page)
    if page_url(page) != before:
        return
    await _try(locator.evaluate, _SUBMIT_FORM_JS, timeout=3)


# A page that is not Playwright (the offline replay DOM, test fakes) has no
# page function to score controls with. There a helper uses the one control
# with exactly that name, by role, then text, label, or placeholder.
_EXACT_CLICK = (
    ("role", "link"), ("role", "button"), ("role", "tab"), ("role", "menuitem"),
    ("role", "checkbox"), ("role", "radio"), ("text", ""),
)
_EXACT_TYPE = (("role", "textbox"), ("role", "searchbox"), ("role", "combobox"), ("label", ""), ("placeholder", ""))


def _exact_locator(page, kind: str, role: str, name: str):
    if kind == "role":
        return page.get_by_role(role, name=name, exact=True)
    if kind == "text":
        return page.get_by_text(name, exact=True)
    if kind == "label":
        return page.get_by_label(name, exact=True)
    return page.get_by_placeholder(name, exact=True)


async def _exact_helper(page, call: HelperCall, *, timeout_ms: int) -> None:
    if call.op == "search":
        raise RuntimeError(f"line {call.line}: cu.search needs a live page")
    for kind, role in _EXACT_CLICK if call.op == "click" else _EXACT_TYPE:
        locator = _exact_locator(page, kind, role, call.target)
        count = int(await _await(locator.count()))
        if count == 0:
            continue
        if count != 1:
            raise RuntimeError(f"line {call.line}: {count} matches for {role or kind} named {call.target!r}")
        await act_on(page, locator, call.op, call.value, timeout_ms=timeout_ms)
        return
    raise RuntimeError(f"line {call.line}: no control named {call.target!r}")


async def run_helper(page, call: HelperCall, *, timeout_ms: int) -> None:
    """Find the best control for the name and act on it.

    Exact names win over partial ones and visible controls over hidden ones;
    the first of equal matches is used. A miss lists the visible controls.
    """
    if not _real_page(page):
        await _exact_helper(page, call, timeout_ms=timeout_ms)
        return
    if call.op == "search":
        await run_search(page, call, timeout_ms=timeout_ms)
        return
    op = call.op
    flags = call.regex_flags
    mark, info = await resolve(
        page,
        call.target,
        op,
        pattern=call.target if flags is not None else "",
        flags="i" if flags and "i" in flags else "",
    )
    if not mark:
        what = "field" if op in {"fill", "press"} else "control"
        raise miss_error(call.line, what, call.target, info)
    locator = mark_locator(page, mark)
    before = page_url(page)
    if op == "fill" and info.get("tag") == "select":
        await select_option(locator, call.value, timeout_ms)
        return
    if op == "click" and info.get("tag") == "option":
        # An option cannot be clicked; choose it in its select instead.
        await _await(locator.evaluate(_CHOOSE_OPTION_JS), 3)
        return
    await act_on(page, locator, op, call.value, timeout_ms=timeout_ms)
    if op == "press" and call.value.casefold() == "enter" and info.get("field"):
        await submit_if_still(page, locator, before)


async def run_search(page, call: HelperCall, *, timeout_ms: int) -> None:
    """Type the query into the site's own search box and submit it."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + FIND_CAP_S
    toggled = False
    while True:
        mark = _new_mark()
        got = await _try(page.evaluate, SEARCH_JS, mark, timeout=5)
        got = got if isinstance(got, dict) else {}
        if got.get("found") and got.get("visible"):
            break
        if got.get("toggle") and not toggled:
            toggled = True
            await _try(mark_locator(page, mark).click, timeout=3)
            await asyncio.sleep(0.3)
            continue
        if got.get("found") and loop.time() >= deadline:
            break
        if loop.time() >= deadline:
            raise RuntimeError(f"line {call.line}: no search box on this page; page.goto a search URL instead")
        await asyncio.sleep(_POLL_S)
    locator = mark_locator(page, mark)
    before = page_url(page)
    await act_on(page, locator, "fill", call.target, timeout_ms=timeout_ms)
    await act_on(page, locator, "press", "Enter", timeout_ms=timeout_ms)
    await submit_if_still(page, locator, before)
