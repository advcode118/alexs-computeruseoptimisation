"""Helpers a generated Playwright script can call.

script_first does not run the script as JavaScript. It parses each line and
drives the Playwright page: page.goto, a getBy* action, or page.evaluate.
These helpers are three more lines that the parser accepts, plus cu.claim inside
page.evaluate.

cu.click, cu.fill, and cu.press take an accessible name. They use the one
control with that name. They do not choose a role for the model, and they do
not read the judge's selector. cu.claim only shapes the object the script
returns. The evidence judge still scores the live page.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from proxy.script import ScriptError

_CLICK = (
    ("role", "link"),
    ("role", "button"),
    ("role", "tab"),
    ("role", "menuitem"),
    ("role", "checkbox"),
    ("role", "radio"),
    ("text", ""),
)
_TYPE = (
    ("role", "textbox"),
    ("role", "searchbox"),
    ("role", "combobox"),
    ("label", ""),
    ("placeholder", ""),
)
_ARITY = {"click": 1, "fill": 2, "press": 2}
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


@dataclass(frozen=True)
class HelperCall:
    op: str
    target: str
    value: str
    line: int


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
    return HelperCall(op=op, target=target, value=value, line=line)


def references_claim(source: str) -> bool:
    """True when a page.evaluate function calls the claim helper."""
    text = source or ""
    return "cu.claim" in text or "cu['claim']" in text or 'cu["claim"]' in text


def wrap_evaluate(function: str) -> str:
    """Define cu.claim for this function. Other evaluate sources stay unchanged."""
    if not references_claim(function):
        return function
    return "() => {\n" + CLAIM_JS + "\nconst __cuUser = " + function.strip() + ";\nreturn __cuUser();\n}"


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


def _call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except TypeError:
        kwargs.pop("exact", None)
        return fn(*args, **kwargs)


def _open(page, kind: str, role: str, name: str):
    if kind == "role":
        return _call(page.get_by_role, role, name=name, exact=True)
    if kind == "text":
        return _call(page.get_by_text, name, exact=True)
    if kind == "label":
        return _call(page.get_by_label, name, exact=True)
    if kind == "placeholder":
        return _call(page.get_by_placeholder, name, exact=True)
    raise RuntimeError(f"unsupported finder {kind}")


async def _count(locator) -> int:
    count = getattr(locator, "count", None)
    if not callable(count):
        raise RuntimeError("the page cannot count controls")
    value = count()
    if asyncio.iscoroutine(value):
        value = await value
    return int(value)


async def _act(locator, op: str, value: str, timeout_ms: int) -> None:
    if op == "click":
        result = locator.click(timeout=timeout_ms)
    elif op == "fill":
        result = locator.fill(value, timeout=timeout_ms)
    elif op == "press":
        result = locator.press(value, timeout=timeout_ms)
    else:
        raise ScriptError(f"unsupported helper {op}")
    if asyncio.iscoroutine(result):
        await result


async def run_helper(page, call: HelperCall, *, timeout_ms: int) -> None:
    """Act on the one control named by the call. A miss raises and does not click another."""
    order = _CLICK if call.op == "click" else _TYPE
    for kind, role in order:
        locator = _open(page, kind, role, call.target)
        count = await _count(locator)
        if count == 0:
            continue
        if count != 1:
            label = role or kind
            raise RuntimeError(f"line {call.line}: {count} matches for {label} named {call.target!r}")
        await _act(locator, call.op, call.value, timeout_ms)
        return
    raise RuntimeError(f"line {call.line}: no control named {call.target!r}")
