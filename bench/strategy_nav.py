"""The nav specialist: read by selection, after the script has arrived.

script_first's script writes its extraction blind, so on value and title tasks
it often returns a whole table row, a neighbouring cell, a heading, or a long
phrase that only contains the words. This step runs after the script's own
self-check says PASS, or rejects an extraction the reader can fix:

1. With no model, build a short numbered view of the live page: the lines
   around the task's key words, table rows with their column labels attached
   to each cell, definition lists as ``term: value``, and the page's headings.
2. One small model call picks the line and copies the exact value from it.
3. With no model, check that the value is literally on that line, is one value
   (not a row, not a label), and is not the page title or a heading unless the
   task asks for one. Then the self-check runs again on the new answer.

Title tasks take the heading at the URL's #fragment, or the page's own h1 when
the task asks for the main heading, with no model call.

Turned on by ``CU_SF_STRATEGY`` containing ``nav``. Off, nothing here runs.
When the step is unsure it keeps the script's answer, so the generic path is
never made worse by this step failing. When the model says the value is not
on the page at all, the step returns FAIL with a reason the grounded repair
loop can act on (``CU_SF_NAV_MISSING=keep`` turns that off).

No host names, site names, task ids, or task markers are used here.
"""

from __future__ import annotations

import json
import math
import os
import re
import time
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from bench.script_first import (
    FAIL,
    PASS,
    ClaimedEvidence,
    EvidenceVerdict,
    _evaluate_value,
    _norm_runtime,
    runtime_verdict,
    trusted_from_payload,
)

STRATEGY = "nav"

# --- switches -----------------------------------------------------------------


def enabled() -> bool:
    """True when CU_SF_STRATEGY (a comma list) names this strategy."""
    raw = os.environ.get("CU_SF_STRATEGY") or ""
    return STRATEGY in {part.strip().casefold() for part in raw.split(",")}


def read_mode() -> str:
    """Both modes rescue extraction FAILs; always also reads every claimed PASS."""
    value = (os.environ.get("CU_SF_NAV_READ") or "always").strip().casefold()
    return value if value in ("always", "suspect") else "always"


def model_free_tables() -> bool:
    """Pick a table cell or a definition with no model when the row and column are both unique."""
    return (os.environ.get("CU_SF_NAV_MF") or "1").strip() != "0"


def missing_fails() -> bool:
    return (os.environ.get("CU_SF_NAV_MISSING") or "fail").strip().casefold() != "keep"


# --- router ---------------------------------------------------------------------

_FORM_WORDS = re.compile(
    r"\b(?:fill(?:\s+in|\s+out)?|submit|sign\s+up|log\s*in|register|form|purchase|check\s*out|"
    r"type\s+\S+\s+into|enter\s+\S+\s+(?:in|into)|add\s+\S+\s+to\s+(?:the\s+)?cart|tick|toggle|drag|upload)\b",
    re.IGNORECASE,
)
_REPORT = re.compile(
    r"\b(?:report|identify|what|which|who|how\s+(?:many|much)|(?:give|tell)\s+(?:me\s+)?(?:the|its|their)|"
    r"(?:name|state)\s+(?:the|its|their))\b",
    re.IGNORECASE,
)
_FIND_VALUE = re.compile(
    r"\bfind\s+(?:the|its|their)\s+(?!page\b|article\b|section\b|documentation\b|document\b)\w+", re.IGNORECASE
)
_OPEN = re.compile(r"\b(?:open|go\s+to|navigate\s+to)\b[^.]*\b(?:page|article|section|docs?|documentation)\b", re.IGNORECASE)
_TITLE_WORDS = re.compile(r"\b(?:heading|headline|title|caption)\b", re.IGNORECASE)
_MAIN_HEADING = re.compile(
    r"\b(?:main|page'?s?|top|first)\s+(?:heading|headline|title)\b|\bthe\s+(?:page|article|entry)\s+title\b",
    re.IGNORECASE,
)


def claims(description: str) -> bool:
    """Take tasks that end by reporting a value or a title read off a page, not form work."""
    text = " ".join((description or "").split())
    if not text or _FORM_WORDS.search(text):
        return False
    if text.endswith("?") or _REPORT.search(text):
        return True
    # "find the year it was first released" asks for a value; "find X and open its page" does not.
    return bool(_FIND_VALUE.search(text)) and not _OPEN.search(text)


def asks_title(description: str) -> bool:
    return bool(_TITLE_WORDS.search(description or ""))


# --- the page view ----------------------------------------------------------------

_VIEW_JS = r"""() => {
  const clean = (s) => (s || "").replace(/[\t ]+/g, " ").replace(/\s*\n\s*/g, " ").trim();
  const root = document.querySelector('main, [role="main"]') || document.body;
  const text = root ? (root.innerText || "") : "";
  const headings = [];
  for (const h of document.querySelectorAll("h1, h2, h3, h4, h5, h6")) {
    if (headings.length >= 300) break;
    const t = clean(h.innerText);
    if (t) headings.push([Number(h.tagName[1]), t]);
  }
  const h1 = document.querySelector("h1");
  let anchor = "";
  const hash = decodeURIComponent((location.hash || "").slice(1));
  if (hash) {
    let target = document.getElementById(hash) || document.getElementsByName(hash)[0] || null;
    if (target) {
      let head = target.closest("h1, h2, h3, h4, h5, h6");
      if (!head && /^H[1-6]$/.test(target.tagName)) head = target;
      if (!head) {
        const inner = target.querySelector && target.querySelector("h1, h2, h3, h4, h5, h6");
        if (inner) head = inner;
      }
      if (!head) {
        const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT);
        walker.currentNode = target;
        let node;
        let steps = 0;
        while ((node = walker.nextNode()) && steps < 60) {
          steps += 1;
          if (/^H[1-6]$/.test(node.tagName)) { head = node; break; }
        }
      }
      if (head) anchor = clean(head.innerText);
    }
  }
  const cellText = (c) => clean(c.innerText);
  const tables = [];
  for (const t of (root || document).querySelectorAll("table")) {
    if (tables.length >= 40) break;
    if (t.querySelector("table")) continue;
    const rows = Array.from(t.rows || []);
    if (!rows.length) continue;
    let header = null;
    const headRow = t.tHead && t.tHead.rows.length ? t.tHead.rows[t.tHead.rows.length - 1] : null;
    if (headRow) header = Array.from(headRow.cells).map(cellText);
    else if (Array.from(rows[0].cells).every((c) => c.tagName === "TH") && rows[0].cells.length > 1) header = Array.from(rows[0].cells).map(cellText);
    const body = [];
    for (const r of rows.slice(0, 600)) {
      if (headRow && r.parentElement === t.tHead) continue;
      if (!headRow && header && r === rows[0]) continue;
      const cells = Array.from(r.cells).map(cellText);
      if (!cells.some((c) => c)) continue;
      body.push(cells);
    }
    const lines = (t.innerText || "").split("\n").map((l) => l.trim()).filter(Boolean);
    tables.push({ header, rows: body, lines: lines.slice(0, 3000) });
  }
  const dls = [];
  for (const d of (root || document).querySelectorAll("dl")) {
    if (dls.length >= 60) break;
    const pairs = [];
    let term = "";
    for (const child of d.children) {
      if (child.tagName === "DT") term = clean(child.innerText);
      else if (child.tagName === "DD" && term) pairs.push([term, clean(child.innerText).slice(0, 400)]);
      if (pairs.length >= 300) break;
    }
    if (pairs.length) dls.push(pairs);
  }
  return {
    url: location.href,
    title: document.title || "",
    h1: h1 ? clean(h1.innerText) : "",
    anchor,
    headings,
    tables,
    dls,
    text: text.slice(0, 400000)
  };
}"""


@dataclass
class ViewLine:
    text: str  # what the model sees (labels attached)
    raw: str  # the page text the value must come from
    kind: str = "text"  # text, row, term, heading
    cells: tuple = ()  # (label, value) pairs for a row or a term


def _norm(value: str) -> str:
    return _norm_runtime(value)


def _row_line(header, cells) -> ViewLine:
    pairs = []
    for index, cell in enumerate(cells):
        label = header[index] if header and index < len(header) else ""
        pairs.append((label, cell))
    shown = " | ".join(f"{label}: {cell}" if label else cell for label, cell in pairs if cell or label)
    return ViewLine(text=shown, raw="\t".join(cells), kind="row", cells=tuple(pairs))


def page_lines(data: dict) -> list[ViewLine]:
    """The page's text as lines, with tables and definition lists rewritten in place."""
    raw_lines = [line.strip() for line in (data.get("text") or "").split("\n")]
    raw_lines = [line for line in raw_lines if line]
    norm_lines = [_norm(line) for line in raw_lines]
    replace: dict[int, tuple[int, list[ViewLine]]] = {}
    tail: list[ViewLine] = []
    cursor = 0
    for table in data.get("tables") or []:
        if not isinstance(table, dict):
            continue
        header = table.get("header") or None
        rows = [_row_line(header, cells) for cells in table.get("rows") or [] if isinstance(cells, list)]
        if not rows:
            continue
        tlines = [_norm(line) for line in table.get("lines") or [] if str(line).strip()]
        placed = False
        if tlines:
            start = cursor
            while True:
                try:
                    at = norm_lines.index(tlines[0], start)
                except ValueError:
                    break
                if norm_lines[at : at + len(tlines)] == tlines:
                    replace[at] = (len(tlines), rows)
                    cursor = at + len(tlines)
                    placed = True
                    break
                start = at + 1
        if not placed:
            tail.extend(rows)
    out: list[ViewLine] = []
    index = 0
    while index < len(raw_lines):
        if index in replace:
            span, rows = replace[index]
            out.extend(rows)
            index += span
            continue
        out.append(ViewLine(text=raw_lines[index], raw=raw_lines[index]))
        index += 1
    out.extend(tail)
    for pairs in data.get("dls") or []:
        for item in pairs or []:
            if isinstance(item, list) and len(item) == 2 and item[0] and item[1]:
                term, value = str(item[0]), str(item[1])
                out.append(ViewLine(text=f"{term}: {value}", raw=value, kind="term", cells=((term, value),)))
    headings = {_norm(text) for _level, text in data.get("headings") or [] if isinstance(text, str)}
    for line in out:
        if line.kind == "text" and _norm(line.raw) in headings:
            line.kind = "heading"
    return out


_STOP = frozenset(
    "the and for with from that this what which when where there their then than into onto your about after "
    "before page site open find give tell show report name state value values return answer task text link "
    "click visit search using under over each some only also does have will would should could exact exactly "
    "written listed shown given look lists list how much many need needs".split()
)


def key_terms(description: str) -> list[tuple[str, float]]:
    """Words and identifiers from the task, weighted. Identifiers with digits weigh most."""
    terms: list[tuple[str, float]] = []
    seen = set()
    for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9.+#_/'-]*[A-Za-z0-9+#]|[A-Za-z0-9]", description or ""):
        word = token.casefold().strip(".'")
        if word.endswith("'s"):
            word = word[:-2]
        if not word or word in seen or word in _STOP:
            continue
        seen.add(word)
        if any(ch.isdigit() for ch in word) or any(ch in word for ch in "._+#") and len(word) > 2:
            terms.append((word, 3.0))
        elif len(word) >= 3:
            terms.append((word, 1.0))
    return terms


def _term_hit(term: str, low: str) -> bool:
    if any(ch.isdigit() for ch in term) or not term.isalpha():
        pattern = r"(?<![0-9a-z.])" + re.escape(term) + r"(?![0-9a-z]|\.[0-9])"
        return re.search(pattern, low) is not None
    stem = term if len(term) <= 5 else term[: max(5, len(term) - 3)]
    return re.search(r"(?<![a-z])" + re.escape(stem), low) is not None


def score_line(line: ViewLine, terms: list[tuple[str, float]]) -> float:
    low = _norm(line.text)
    return sum(weight for term, weight in terms if _term_hit(term, low))


def _host_words(url: str) -> set[str]:
    host = urlsplit(url or "").hostname or ""
    return {part for part in re.split(r"[.-]", host.casefold()) if len(part) >= 3 and part not in ("www", "com", "org", "net")}


def _names_site(term: str, host_words: set[str]) -> bool:
    """The site's own name ("IBAN.com's", "W3Schools'"): it matches headers and footers, not the value."""
    parts = {part for part in re.split(r"[.-]", term) if part}
    return bool(parts) and bool(parts & host_words)


def page_weights(
    lines: list[ViewLine], terms: list[tuple[str, float]], title: str, url: str = ""
) -> list[tuple[str, float]]:
    """Rare words on this page weigh more. Words in the page title describe arrival, not the value."""
    total = max(1, len(lines))
    folded = [_norm(line.text) for line in lines]
    head = _norm(title)
    host_words = _host_words(url)
    out = []
    for term, base in terms:
        if _names_site(term, host_words):
            continue
        df = sum(1 for low in folded if _term_hit(term, low))
        if df == 0:
            continue
        weight = base * math.log((total + 1) / df)
        if _term_hit(term, head):
            weight *= 0.3
        out.append((term, max(weight, 0.05)))
    return out


_LINE_CAP = 260
_VIEW_LINES = 36
_VIEW_CHARS = 6000


def _clip(text: str, terms) -> str:
    if len(text) <= _LINE_CAP:
        return text
    low = text.casefold()
    first = min((low.find(term) for term, _w in terms if low.find(term) >= 0), default=0)
    start = max(0, first - 80)
    return ("…" if start else "") + text[start : start + _LINE_CAP] + "…"


@dataclass
class View:
    url: str
    title: str
    h1: str
    anchor: str
    lines: list[ViewLine]  # the numbered lines, 1-based in the prompt
    headings: list[str] = field(default_factory=list)

    def render(self, terms) -> str:
        out = [f"URL: {self.url}", f"Document title: {self.title}", f"Main heading (h1): {self.h1 or '(none)'}"]
        if self.anchor:
            out.append(f"Heading at the URL's #fragment: {self.anchor}")
        out.append("Lines:")
        for number, line in enumerate(self.lines, 1):
            tag = {"heading": "[heading] ", "row": "[table row] ", "term": "[definition] "}.get(line.kind, "")
            out.append(f"{number}. {tag}{_clip(line.text, terms)}")
        return "\n".join(out)


def build_view(data: dict, description: str, *, prior_answer: str = "") -> View:
    """The numbered lines the read call sees. No model call."""
    lines = page_lines(data)
    terms = page_weights(lines, key_terms(description), str(data.get("title") or ""), str(data.get("url") or ""))
    title_task = asks_title(description)
    scores = [score_line(line, terms) for line in lines]
    best = max(scores, default=0.0)
    floor = max(0.5, best * 0.45)
    picked: list[int] = []
    order = sorted(range(len(lines)), key=lambda i: (-scores[i], i))
    for i in order:
        if scores[i] < floor or len(picked) >= _VIEW_LINES:
            break
        picked.append(i)
        # The value is often on the line after its label, or the label on the line before.
        for j in (i - 1, i + 1):
            if 0 <= j < len(lines) and lines[i].kind != "row" and len(picked) < _VIEW_LINES:
                picked.append(j)
    if prior_answer:
        needle = _norm(prior_answer)
        for i, line in enumerate(lines):
            if needle and needle in _norm(line.raw) and i not in picked:
                picked.append(i)
                break
    if title_task:
        # Headings, and the line under each one ("the entry under its Name heading").
        for i, line in enumerate(lines):
            if line.kind == "heading" and len(picked) < _VIEW_LINES + 24:
                picked.extend(j for j in (i, i + 1) if j < len(lines))
    if not picked:
        picked = list(range(min(len(lines), 25)))
    chosen: list[ViewLine] = []
    seen = set()
    size = 0
    for i in sorted(set(picked)):
        line = lines[i]
        key = (line.kind, line.text)
        if key in seen:
            continue
        seen.add(key)
        size += min(len(line.text), _LINE_CAP) + 8
        if size > _VIEW_CHARS:
            break
        chosen.append(line)
    headings = [text for _level, text in data.get("headings") or [] if isinstance(text, str)]
    return View(
        url=str(data.get("url") or ""),
        title=" ".join(str(data.get("title") or "").split()),
        h1=str(data.get("h1") or ""),
        anchor=str(data.get("anchor") or ""),
        lines=chosen,
        headings=headings,
    )


# --- model-free choices and checks -------------------------------------------------


def title_without_model(view: View, description: str) -> str:
    """The heading a title task asks for, when the page makes it plain. Empty when unsure."""
    if not asks_title(description):
        return ""
    if _MAIN_HEADING.search(description or "") and view.h1:
        return view.h1
    if view.anchor and re.search(r"\b(?:section|chapter|subsection)\b", description, re.IGNORECASE):
        generic = _words("full numbered section chapter subsection heading headline title")
        if (_words(view.anchor) - generic) & (_words(description) - generic):
            return view.anchor
    return ""


def _strip_label(value: str, line: ViewLine) -> str:
    for label, cell in line.cells:
        if label and _norm(value).startswith(_norm(label) + ":"):
            return value.split(":", 1)[1].strip()
        if _norm(value) == _norm(f"{label}: {cell}"):
            return cell
    return value


def check_value(value: str, line: ViewLine | None, view: View, description: str, *, column=None) -> str:
    """Empty when the value is one exact value from that line. Otherwise why not."""
    if not value or not value.strip():
        return "empty value"
    if "\t" in value or "\n" in value:
        return "value spans several cells or lines"
    if len(value) > 200:
        return "value is too long to be one value"
    if line is None:
        return "line number is not in the view"
    needle = _norm(value)
    if needle not in _norm(line.raw) and not any(needle in _norm(cell) for _label, cell in line.cells):
        return "value is not on that line"
    if line.kind == "row" and sum(1 for _label, cell in line.cells if cell and _norm(cell) in needle) >= 2:
        return "value is a whole row, not one cell"
    if line.kind == "row":
        if type(column) is not int or not 1 <= column <= len(line.cells):
            return "table column number is not in the row"
        if needle not in _norm(line.cells[column - 1][1]):
            return "value is not in the selected column"
        target = _target_column(line, description)
        if target is not None and column - 1 != target:
            return "selected column is not the column named in the task"
    if not asks_title(description):
        if needle in {_norm(view.title), _norm(view.h1)}:
            return "value is the page title, not the asked value"
        if line.kind == "heading" and needle == _norm(line.raw):
            return "value is a heading, not the asked value"
    return ""


def suspicious(answer: str, payload: dict, description: str) -> str:
    """Why the script's own answer looks wrong for a value or title, or empty."""
    text = (answer or "").strip()
    if not text:
        return "no answer"
    if "\t" in text or "\n" in text:
        return "several cells or lines"
    words = len(text.split())
    if not asks_title(description) and (words > 8 or len(text) > 60):
        return "long phrase"
    if asks_title(description) and (words > 16 or len(text) > 140):
        return "long phrase"
    title = str(payload.get("title") or "")
    h1 = str(payload.get("h1") or "")
    if not asks_title(description) and _norm(text) in {_norm(title), _norm(h1)} - {""}:
        return "answer is the page title"
    return ""


# --- model-free pick for a table cell or a definition -------------------------------

_WORD = re.compile(r"[a-z0-9][a-z0-9.+#_/-]*[a-z0-9+#]|[a-z0-9]")


def _words(text: str) -> set[str]:
    """Word stems: long words compare on their first five letters."""
    out = set()
    for word in _WORD.findall(_norm(text)):
        if word in _STOP:
            continue
        out.add(word[:5] if len(word) > 5 and word.isalpha() else word)
    return out


def _task_keys(description: str) -> set[str]:
    """Task tokens a row's key cell could equal, including quoted and slash-joined names."""
    keys = {_norm(word) for word, _weight in key_terms(description)}
    for quoted in re.findall(r"[\"“']([^\"”']{2,40})[\"”']", description or ""):
        keys.add(_norm(quoted))
    return {key for key in keys if key}


def _target_column(line: ViewLine, description: str) -> int | None:
    """A uniquely named value column, excluding columns used to identify the row."""
    keys = _task_keys(description)
    key_at = {i for i, (_label, cell) in enumerate(line.cells) if _norm(cell) in keys}
    used = set().union(*(_words(line.cells[i][0]) for i in key_at)) if key_at else set()
    task_words = _words(description)
    scored = sorted(
        ((len((_words(label) - used) & task_words), i)
         for i, (label, cell) in enumerate(line.cells) if i not in key_at and label and cell.strip()),
        reverse=True,
    )
    if not scored or scored[0][0] == 0 or (len(scored) > 1 and scored[0][0] == scored[1][0]):
        return None
    return scored[0][1]


def table_pick(lines: list[ViewLine], description: str) -> str:
    """One cell from the one row whose key cell is named in the task, in the column the task names.

    Empty unless both the row and the column are unique. No model call.
    """
    if asks_title(description):
        return ""
    keys = _task_keys(description)
    found: list[tuple[str, str]] = []
    for line in lines:
        if line.kind not in ("row", "term") or len(line.cells) < 1:
            continue
        cells = list(line.cells)
        if line.kind == "term":
            if len(cells) == 1 and _norm(cells[0][0]) in keys:
                found.append(cells[0])
            continue
        key_at = [i for i, (_label, cell) in enumerate(cells) if _norm(cell) in keys]
        if not key_at:
            continue
        if len(cells) == 2 and not any(label for label, _cell in cells):
            # A two-column key | value table with no header row.
            if key_at == [0]:
                found.append(("", cells[1][1]))
            continue
        column = _target_column(line, description)
        if column is not None:
            found.append(cells[column])
    values = {_norm(value) for _label, value in found}
    if len(values) != 1:
        return ""
    return found[0][1].strip()

# --- the model call ------------------------------------------------------------------

READ_SYSTEM = (
    "You read one value off a web page for a task. You get the task and numbered lines from the page. "
    "Table rows show each cell as 'Column: cell'. Definitions show 'term: value'. "
    'Reply with JSON only: {"line": <number>, "column": <number>, "value": "<the value>"}. '
    "For a table row, column is the cell's 1-based position from the left; otherwise use 0. "
    "Copy the value exactly as it is written on that line: only the asked value, no column label, "
    "no surrounding sentence, no other cells. Pick the cell in the column the task asks about. "
    "If the task asks for a heading or title, copy the whole heading text. "
    'If no line holds the value, reply {"line": 0, "value": "", "missing": "<what is not on this page>"}.'
)


def read_prompt(description: str, view: View, terms) -> str:
    return f"Task: {description}\n\n{view.render(terms)}"


def parse_reply(text: str) -> dict:
    match = re.search(r"\{.*\}", text or "", re.DOTALL)
    if not match:
        return {}
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


# --- the step the harness calls -----------------------------------------------------------


@dataclass
class ReadOutcome:
    verdict: EvidenceVerdict
    payload: dict
    label: str  # strategy row field: nav:<how>
    model_calls: int = 0
    model_ms: float = 0.0
    tool_ms: float = 0.0
    usage: dict = field(default_factory=dict)
    note: str = ""


def _with_answer(payload: dict, answer: str) -> dict:
    updated = dict(payload)
    claimed = dict(updated.get("claimed") or {}) if isinstance(updated.get("claimed"), dict) else {}
    claimed["answer"] = answer
    updated["claimed"] = claimed
    return updated


def _recheck(payload: dict, page_url: str, start_url: str, description: str, earlier=()) -> EvidenceVerdict:
    """The same self-check the script got, on the read answer (the strict one included)."""
    from bench.script_first import claimed_from_payload

    return runtime_verdict(
        trusted_from_payload(payload, url=page_url),
        claimed_from_payload(payload),
        script_ok=payload.get("ok") is not False,
        start_url=start_url,
        asks_value=True,
        task=description,
        earlier=tuple(earlier),
    )


# Self-check FAIL reasons about where the script is, not what it read. Reading cannot fix those.
_NAV_REASONS = (
    "start page",
    "error page",
    "search results page",
    "stopped before it finished",
    "did not end on a web page",
    "claimed url does not match",
    "empty evidence",
    "denied",
    "wrong host",
    "page text was not read",
    "before the form was submitted",
    "returned value is not text",
)


def read_can_fix(verdict: EvidenceVerdict) -> bool:
    """A FAIL about the extraction (wrong cell, heading, label, part of a value, not on the page)."""
    if verdict.verdict != FAIL:
        return False
    reason = (verdict.reason or "").casefold()
    return bool(reason) and not any(part in reason for part in _NAV_REASONS)


async def read_after_pass(
    *,
    page,
    model,
    description: str,
    payload: dict,
    verdict: EvidenceVerdict,
    page_url: str,
    start_url: str,
    earlier=(),
) -> ReadOutcome:
    """Replace the script's extraction with a read by selection.

    After a PASS the read answer replaces the script's (unsure: the script's stays).
    After a FAIL that read_can_fix, a read answer that passes the self-check turns it
    into a PASS without a repair script (unsure: the FAIL and its repair stay).
    Unpriceable API usage propagates so the probe's spend guard can stop the run.
    """
    from bench.script_first import claimed_from_payload

    rescue = verdict.verdict == FAIL
    outcome = await _read(page, model, description, payload, verdict, page_url, start_url, earlier, rescue)
    if rescue:
        if outcome.verdict.verdict == PASS and outcome.payload is not payload:
            outcome.label = outcome.label.replace("nav:", "nav:rescue_", 1)
        else:
            outcome.label = outcome.label.replace("nav:", "nav:rescue_none_", 1)
            outcome.verdict, outcome.payload = verdict, payload
    return outcome


async def _read(page, model, description, payload, verdict, page_url, start_url, earlier, rescue) -> ReadOutcome:
    from bench.script_first import claimed_from_payload

    prior = claimed_from_payload(payload).answer
    keep = ReadOutcome(verdict=verdict, payload=payload, label="nav:kept")
    if rescue and not read_can_fix(verdict):
        keep.label = "nav:not_fixable"
        return keep
    if read_mode() == "suspect" and not rescue:
        why = suspicious(prior, payload, description)
        if not why:
            keep.label = "nav:trusted"
            return keep
        keep.note = why
    started = time.perf_counter()
    data = await _evaluate_value(page, _VIEW_JS) if page is not None else None
    tool_ms = (time.perf_counter() - started) * 1000
    keep.tool_ms = tool_ms
    if not isinstance(data, dict) or not data.get("text"):
        keep.label = "nav:no_view"
        return keep
    view = build_view(data, description, prior_answer=prior)
    terms = key_terms(description)

    value = title_without_model(view, description)
    label = "nav:title_rule"
    if not value and model_free_tables():
        value = table_pick(page_lines(data), description)
        label = "nav:table_rule"
    outcome = ReadOutcome(verdict=verdict, payload=payload, label=label, tool_ms=tool_ms)
    if not value:
        if not view.lines:
            keep.label = "nav:empty_view"
            return keep
        call_started = time.perf_counter()
        try:
            response, model_ms = await model.create_message(
                [{"role": "user", "content": read_prompt(description, view, terms)}],
                [],
                system=READ_SYSTEM,
                max_tokens=1500,
            )
        except Exception as exc:  # noqa: BLE001 - the generic answer stays
            from bench.openai_spend import PriceUnknown

            if isinstance(exc, PriceUnknown):
                raise
            keep.label = "nav:model_error"
            keep.note = str(exc)[:200]
            keep.model_calls = 1
            keep.model_ms = (time.perf_counter() - call_started) * 1000
            return keep
        outcome.model_calls = 1
        outcome.model_ms = model_ms
        outcome.usage = dict(response.get("usage") or {})
        reply = parse_reply("".join(b.get("text", "") for b in response.get("content") or [] if b.get("type") == "text"))
        try:
            number = int(reply.get("line") or 0)
        except (TypeError, ValueError):
            number = 0
        value = str(reply.get("value") or "").strip()
        if number == 0 or not value:
            missing = str(reply.get("missing") or "").strip()
            outcome.note = missing[:200]
            if missing_fails() and missing:
                outcome.label = "nav:missing"
                outcome.verdict = EvidenceVerdict(
                    FAIL,
                    f"the read step found no line with the asked value on this page ({missing[:120]}); "
                    "go to the page that shows it",
                    verdict.scored_url,
                )
                return outcome
            outcome.label = "nav:no_pick"
            return outcome
        line = view.lines[number - 1] if 1 <= number <= len(view.lines) else None
        if line is not None:
            value = _strip_label(value, line)
        problem = check_value(value, line, view, description, column=reply.get("column"))
        if problem:
            outcome.label = "nav:rejected"
            outcome.note = f"{problem}: {value[:80]}"
            return outcome
        outcome.label = "nav:read"
    updated = _with_answer(payload, value)
    again = _recheck(updated, page_url, start_url, description, earlier)
    if again.verdict != PASS:
        outcome.label = "nav:recheck_fail"
        outcome.note = again.reason
        return outcome
    outcome.payload = updated
    outcome.verdict = again
    outcome.note = value[:120]
    return outcome


__all__ = [
    "ClaimedEvidence",
    "ReadOutcome",
    "STRATEGY",
    "build_view",
    "check_value",
    "claims",
    "enabled",
    "read_after_pass",
    "read_can_fix",
    "suspicious",
    "title_without_model",
]
