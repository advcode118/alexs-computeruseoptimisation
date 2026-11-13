"""Helpers a generated Playwright script can call.

script_first does not run the script as JavaScript. It parses each line and
drives the Playwright page: page.goto, a getBy* action, or page.evaluate.
These helpers are four more lines that the parser accepts, plus cu.claim and
cu.text inside page.evaluate.

cu.click, cu.fill, and cu.press take a visible name, label, or placeholder;
bench/script_resolve.py picks the best-matching control on the live page.
cu.search types into the site's own search box and submits it. None of them
reads the judge's selector. cu.claim only shapes the object the script
returns, and cu.text reads the value shown next to a label. The evidence
judge still scores the live page.
"""

from __future__ import annotations

from dataclasses import dataclass

from proxy.script import ScriptError

_ARITY = {"click": 1, "fill": 2, "press": 2, "search": 1}
_TEXT_KEYS = ("url", "title", "h1", "key_text", "answer")

# Page-context function. wrap_evaluate puts this in scope only for a script
# that calls cu.claim. It does not navigate and it does not read a selector
# the judge uses.
CLAIM_JS = """const cu = {
  claim(partial) {
    const node = document.querySelector("h1");
    const out = {
      url: String(location.href || ""),
      title: String(document.title || ""),
      h1: node ? String(node.innerText || node.textContent || "").trim() : "",
      key_text: "",
      values: [],
      answer: ""
    };
    if (partial == null || partial === "") return out;
    if (typeof partial !== "object" || Array.isArray(partial)) {
      out.rejected = true;
      return out;
    }
    let rejected = false;
    for (const key of ["url", "title", "h1", "key_text", "answer"]) {
      if (!Object.prototype.hasOwnProperty.call(partial, key)) continue;
      const value = partial[key];
      if (value == null || value === "") continue;
      if (typeof value === "string") {
        const text = value.trim();
        if (text) out[key] = text;
        continue;
      }
      if (typeof value === "number" && Number.isFinite(value)) {
        out[key] = String(value);
        continue;
      }
      rejected = true;
    }
    if (Object.prototype.hasOwnProperty.call(partial, "values")) {
      const raw = partial.values;
      if (!(raw == null || raw === "" || (Array.isArray(raw) && raw.length === 0))) {
        if (!Array.isArray(raw)) rejected = true;
        else {
          const values = [];
          let bad = false;
          for (const item of raw) {
            if (item == null || item === "") continue;
            if (typeof item === "string") {
              const parts = [];
              let buf = "";
              for (const ch of item) {
                const code = ch.charCodeAt(0);
                const space = code === 9 || code === 10 || code === 11 || code === 12 || code === 13 || code === 32 || code === 160;
                if (space) {
                  if (buf) parts.push(buf);
                  buf = "";
                } else buf += ch;
              }
              if (buf) parts.push(buf);
              const text = parts.join(" ");
              if (!text) continue;
              values.push(text.length > 400 ? text.slice(0, 400) : text);
            } else if (typeof item === "number" && Number.isFinite(item)) {
              values.push(String(item));
            } else {
              bad = true;
              break;
            }
            if (values.length > 20) {
              bad = true;
              break;
            }
          }
          if (bad) rejected = true;
          else out.values = values;
        }
      }
    }
    if (rejected) out.rejected = true;
    return out;
  }
};"""


# cu.text(label): the value shown next to a label, a table header, a term,
# or a heading. Defined beside cu.claim in the same page function.
TEXT_JS = r"""cu.text = function (label) {
  const norm = (s) => String(s == null ? "" : s).replace(/[\s ]+/g, " ").trim();
  const low = (s) => norm(s).toLowerCase().replace(/[\s:*]+$/, "");
  const want = low(label);
  if (!want) return "";
  const shown = (el) => !!el.getClientRects().length;
  const tx = (el) => el ? norm(el.innerText != null ? el.innerText : el.textContent) : "";
  const rest = (whole, head) => {
    const i = whole.toLowerCase().indexOf(head);
    if (i < 0) return "";
    return norm(whole.slice(i + head.length).replace(/^[\s:=\-–—]+/, ""));
  };
  const cands = [];
  for (const el of document.querySelectorAll("dt, th, td, label, strong, b, em, span, div, p, li, h1, h2, h3, h4, h5, h6, caption, legend, summary, figcaption")) {
    const t = tx(el);
    if (!t || t.length > 200 || !shown(el)) continue;
    const l = low(t);
    let rank = -1;
    if (l === want) rank = 0;
    else if (l.startsWith(want + ":") || l.startsWith(want + " :")) rank = 1;
    else if (l.startsWith(want + " ") && el.children.length === 0) rank = 2;
    if (rank >= 0) cands.push([rank, t.length, el]);
  }
  cands.sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  for (const [rank, , el] of cands) {
    const t = tx(el);
    if (rank > 0) {
      const v = rest(t, want);
      if (v) return v;
    }
    const name = el.tagName;
    if (name === "DT") {
      let n = el.nextElementSibling;
      while (n && n.tagName !== "DD") n = n.nextElementSibling;
      if (n && tx(n)) return tx(n);
    }
    if (name === "TH" || name === "TD") {
      const row = el.parentElement;
      const cells = row ? Array.from(row.children) : [];
      const i = cells.indexOf(el);
      if (i >= 0 && i + 1 < cells.length && tx(cells[i + 1])) return tx(cells[i + 1]);
      const table = el.closest("table");
      if (table && name === "TH" && i >= 0) {
        for (const r of table.querySelectorAll("tr")) {
          if (r === row) continue;
          const c = r.children[i];
          if (c && c.tagName === "TD" && tx(c)) return tx(c);
        }
      }
    }
    if (name === "LABEL" && el.control && el.control.value) return norm(el.control.value);
    const next = el.nextElementSibling;
    if (next && tx(next)) return tx(next).slice(0, 300);
    const parent = el.parentElement;
    if (parent) {
      const after = rest(tx(parent), low(t));
      if (after && after.length <= 300) return after;
      const pn = parent.nextElementSibling;
      if (pn && tx(pn)) return tx(pn).slice(0, 300);
    }
  }
  return "";
};"""


@dataclass(frozen=True)
class HelperCall:
    op: str
    target: str
    value: str
    line: int
    # Set when the name was a /regex/flags literal; target then holds the pattern.
    regex_flags: str | None = None


class _Scan:
    def __init__(self, text: str, line: int):
        self.text = text
        self.line = line
        self.i = 0

    def skip(self) -> None:
        while self.i < len(self.text) and self.text[self.i] in " \t\r\n":
            self.i += 1

    def startswith(self, literal: str) -> bool:
        self.skip()
        return self.text.startswith(literal, self.i)

    def take(self, literal: str) -> None:
        self.skip()
        if not self.text.startswith(literal, self.i):
            raise ScriptError(f"line {self.line}: expected {literal!r}")
        self.i += len(literal)

    def identifier(self) -> str:
        self.skip()
        start = self.i
        while self.i < len(self.text) and (self.text[self.i].isalnum() or self.text[self.i] == "_"):
            self.i += 1
        if start == self.i:
            raise ScriptError(f"line {self.line}: expected a helper name")
        return self.text[start : self.i]

    def string(self) -> str:
        self.skip()
        if self.i >= len(self.text) or self.text[self.i] not in "\"'":
            raise ScriptError(f"line {self.line}: expected a string")
        quote = self.text[self.i]
        self.i += 1
        chars: list[str] = []
        while self.i < len(self.text):
            ch = self.text[self.i]
            if ch == "\\":
                self.i += 1
                if self.i >= len(self.text):
                    raise ScriptError(f"line {self.line}: bad escape")
                chars.append(self.text[self.i])
                self.i += 1
                continue
            if ch == quote:
                self.i += 1
                return "".join(chars)
            chars.append(ch)
            self.i += 1
        raise ScriptError(f"line {self.line}: unterminated string")


def is_helper_call(text: str) -> bool:
    return text.lstrip().casefold().startswith("cu.")


def parse_helper_call(text: str, line: int) -> HelperCall:
    """Parse one cu.click, cu.fill, or cu.press line. Raises before the page is used."""
    raw = (text or "").strip()
    if raw.startswith("await "):
        raw = raw[len("await ") :].strip()
    if not raw.casefold().startswith("cu."):
        raise ScriptError(f"line {line}: not a helper call")
    scan = _Scan("cu." + raw[3:], line)
    scan.take("cu")
    scan.take(".")
    op = scan.identifier().casefold()
    if op == "claim":
        raise ScriptError(f"line {line}: cu.claim belongs inside page.evaluate")
    if op not in _ARITY:
        raise ScriptError(f"line {line}: cu.{op} is not a helper")
    scan.take("(")
    regex_flags = None
    scan.skip()
    if scan.text.startswith("/", scan.i) and op != "search":
        from bench.script_grammar import _LiteralScan

        literal = _LiteralScan(scan.text, line)
        literal.i = scan.i
        found = literal.regex()
        scan.i = literal.i
        target, regex_flags = found.pattern, found.flags
    else:
        target = scan.string().strip()
    value = ""
    if _ARITY[op] == 2:
        scan.take(",")
        value = scan.string()
    scan.skip()
    if scan.startswith(","):
        raise ScriptError(f"line {line}: cu.{op} has an extra argument")
    scan.take(")")
    scan.skip()
    if scan.i != len(scan.text):
        raise ScriptError(f"line {line}: unexpected trailing text")
    if not target:
        raise ScriptError(f"line {line}: empty name")
    if op == "press" and not value:
        raise ScriptError(f"line {line}: press needs a key")
    return HelperCall(op=op, target=target, value=value, line=line, regex_flags=regex_flags)


def references_claim(source: str) -> bool:
    """True when a page.evaluate function calls cu.claim or cu.text."""
    text = source or ""
    return any(
        token in text
        for token in ("cu.claim", "cu['claim']", 'cu["claim"]', "cu.text", "cu['text']", 'cu["text"]')
    )


def wrap_evaluate(function: str) -> str:
    """Define cu.claim and cu.text for this function. Other evaluate sources stay unchanged."""
    if not references_claim(function):
        return function
    return "() => {\n" + CLAIM_JS + "\n" + TEXT_JS + "\nconst __cuUser = " + function.strip() + ";\nreturn __cuUser();\n}"


def _js_number(value: int | float) -> str:
    if isinstance(value, float) and value.is_integer() and value not in {float("inf"), float("-inf")}:
        return str(int(value))
    return str(value)


def _collapse(value: str) -> str:
    return " ".join(value.split())


def shape_claim(partial, *, url: str, title: str, h1: str) -> dict:
    """The object cu.claim returns. Strings only. A bad value is marked rejected.

    This does not decide PASS or FAIL. The live page is still the judge.
    """
    out = {
        "url": url or "",
        "title": title or "",
        "h1": (h1 or "").strip(),
        "key_text": "",
        "values": [],
        "answer": "",
    }
    if partial is None or partial == "":
        return out
    if not isinstance(partial, dict):
        out["rejected"] = True
        return out
    rejected = False
    for key in _TEXT_KEYS:
        if key not in partial:
            continue
        value = partial[key]
        if value is None or value == "":
            continue
        if isinstance(value, str):
            text = value.strip()
            if text:
                out[key] = text
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            rejected = True
            continue
        out[key] = _js_number(value)
    if "values" in partial:
        raw = partial["values"]
        if raw is None or raw == "" or raw == [] or raw == ():
            pass
        elif isinstance(raw, bool) or not isinstance(raw, (list, tuple)):
            rejected = True
        else:
            values: list[str] = []
            bad = False
            for item in raw:
                if item is None or item == "":
                    continue
                if isinstance(item, str):
                    text = _collapse(item)
                    if not text:
                        continue
                    if len(text) > 400:
                        text = text[:400]
                    values.append(text)
                elif isinstance(item, bool) or not isinstance(item, (int, float)):
                    bad = True
                    break
                else:
                    values.append(_js_number(item))
                if len(values) > 20:
                    bad = True
                    break
            if bad:
                rejected = True
            else:
                out["values"] = values
    if rejected:
        out["rejected"] = True
    return out


