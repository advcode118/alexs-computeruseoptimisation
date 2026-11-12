"""Literal-only Playwright statements for script_first, not the proxy arm.

No source from this parser is executed as JavaScript. The executor dispatches
only the operations below; page.evaluate remains a separate page-context path.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from proxy.script import ScriptError, _Scan


_FINDERS = {
    "locator": "css",
    "getByRole": "role",
    "getByLabel": "label",
    "getByText": "text",
    "getByPlaceholder": "placeholder",
}
_VALUE_OPS = {"fill", "press", "selectOption", "getAttribute"}
_LOCATOR_OPS = _VALUE_OPS | {"click", "check", "uncheck", "textContent", "innerText", "waitFor"}
READ_OPS = {"textContent", "innerText", "getAttribute", "title", "url"}
_DROPPED_PAGE_OPS = {
    "waitForTimeout", "waitForLoadState", "waitForSelector",
    "wait_for_timeout", "wait_for_load_state", "wait_for_selector",
    "setDefaultTimeout", "setDefaultNavigationTimeout",
}
GRAMMAR_HINT = (
    'use page.locator("css").click() or page.evaluate(() => { ... }); '
    'for an object return, wrap it in page.evaluate(() => ({...}))'
)


@dataclass(frozen=True)
class BrowserAction:
    finder: str
    op: str
    line: int
    name: str | None = None
    role: str = ""
    value: str = ""
    exact: bool | None = None
    positions: tuple[tuple[str, int], ...] = ()


class _LiteralScan(_Scan):
    def skip(self) -> None:
        while self.i < len(self.text) and self.text[self.i].isspace():
            self.i += 1

    def string(self) -> str:
        """Decode JS quoted literals, never expressions or template strings."""
        self.skip()
        if self.i >= len(self.text) or self.text[self.i] not in "\"'":
            raise ScriptError(f"line {self.line}: expected a string literal")
        quote = self.text[self.i]
        self.i += 1
        chars: list[str] = []
        escapes = {"n": "\n", "r": "\r", "t": "\t", "b": "\b", "f": "\f", "v": "\v", "0": "\0"}
        while self.i < len(self.text):
            ch = self.text[self.i]
            self.i += 1
            if ch == quote:
                return "".join(chars)
            if ch in "\r\n":
                raise ScriptError(f"line {self.line}: unescaped newline in string")
            if ch == "\\":
                if self.i >= len(self.text):
                    break
                ch = self.text[self.i]
                self.i += 1
                if ch in {"u", "x"}:
                    size = 4 if ch == "u" else 2
                    digits = self.text[self.i : self.i + size]
                    if len(digits) != size or not re.fullmatch(r"[0-9a-fA-F]+", digits):
                        raise ScriptError(f"line {self.line}: bad string escape")
                    chars.append(chr(int(digits, 16)))
                    self.i += size
                    continue
                if ch == "\n":
                    continue
                if ch == "\r":
                    if self.i < len(self.text) and self.text[self.i] == "\n":
                        self.i += 1
                    continue
                ch = escapes.get(ch, ch)
            chars.append(ch)
        raise ScriptError(f"line {self.line}: unterminated string")

    def literal(self):
        self.skip()
        if self.startswith('"') or self.startswith("'"):
            return self.string()
        if self.startswith("{"):
            return self.options()
        match = re.match(r"(?:true|false|null|-?\d+(?:\.\d+)?)\b", self.remaining())
        if not match:
            raise ScriptError(f"line {self.line}: expected a literal option")
        token = match.group()
        self.i += len(token)
        return {"true": True, "false": False, "null": None}.get(token, token)

    def options(self) -> dict:
        self.take("{")
        options = {}
        while not self.startswith("}"):
            key = self.string() if self.startswith('"') or self.startswith("'") else self.identifier()
            self.take(":")
            if key in options:
                raise ScriptError(f"line {self.line}: duplicate option {key}")
            options[key] = self.literal()
            if not self.startswith(","):
                break
            self.take(",")
        self.take("}")
        return options

    def end_call(self, *, options: bool = False) -> None:
        # Existing action options do not override the runner's fixed timeouts.
        if options and self.startswith(","):
            self.take(",")
            self.options()
        self.take(")")


def parse_browser_action(text: str, line: int) -> BrowserAction:
    scan = _LiteralScan(text, line)
    scan.take("page")
    scan.take(".")
    method = scan.identifier()
    if method in _FINDERS:
        finder = _FINDERS[method]
        scan.take("(")
        target = scan.string()
        options = {}
        if finder != "css" and scan.startswith(","):
            scan.take(",")
            options = scan.options()
        scan.take(")")
        exact = options.get("exact")
        if "exact" in options and not isinstance(exact, bool):
            raise ScriptError(f"line {line}: exact must be true or false")
        name = options.get("name") if finder == "role" else target
        if name is not None and not isinstance(name, str):
            raise ScriptError(f"line {line}: name must be a string")
        if not target.strip():
            raise ScriptError(f"line {line}: empty locator")
        positions = []
        scan.take(".")
        op = scan.identifier()
        while op in {"first", "last", "nth"}:
            scan.take("(")
            index = 0
            if op == "nth":
                scan.skip()
                match = re.match(r"-?\d+", scan.remaining())
                if not match:
                    raise ScriptError(f"line {line}: nth needs an integer literal")
                index = int(match.group())
                scan.i += len(match.group())
            scan.take(")")
            positions.append((op, index))
            scan.take(".")
            op = scan.identifier()
        if op not in _LOCATOR_OPS:
            raise ScriptError(f"line {line}: unsupported locator action {op}")
        scan.take("(")
        value = scan.string() if op in _VALUE_OPS else ""
        if op not in _VALUE_OPS and scan.startswith("{"):
            scan.options()
        scan.end_call(options=True)
        action = BrowserAction(
            finder=finder, op=op, line=line, name=name,
            role=target if finder == "role" else "", value=value,
            exact=exact, positions=tuple(positions),
        )
    else:
        finder = "page"
        if method == "keyboard":
            finder = "keyboard"
            scan.take(".")
            method = scan.identifier()
            if method not in {"press", "type"}:
                raise ScriptError(f"line {line}: unsupported keyboard action {method}")
        elif method not in {"click", "fill", "press", "goBack", "title", "url"} | _DROPPED_PAGE_OPS:
            raise ScriptError(f"line {line}: unsupported page action {method}")
        scan.take("(")
        name = None
        value = ""
        if finder == "keyboard":
            value = scan.string()
        elif method in {"click", "fill", "press"}:
            name = scan.string()
            if method != "click":
                scan.take(",")
                value = scan.string()
        elif method in _DROPPED_PAGE_OPS and not scan.startswith(")"):
            scan.literal()
        scan.end_call(options=method not in {"title", "url"})
        action = BrowserAction(finder, method, line, name=name, value=value)
    scan.skip()
    if scan.i != len(text):
        raise ScriptError(f"line {line}: unexpected trailing text")
    if action.op == "press" and not action.value:
        raise ScriptError(f"line {line}: press needs a key")
    return action


def action_kind(action: BrowserAction) -> str:
    if action.op in _DROPPED_PAGE_OPS or action.op == "waitFor":
        return "wait"
    if action.op in READ_OPS:
        return "read"
    return "locator" if action.finder not in {"page", "keyboard"} else action.finder


def browser_locator(page, action: BrowserAction):
    options = {} if action.exact is None else {"exact": action.exact}
    if action.finder == "css":
        locator = page.locator(action.name)
    elif action.finder == "role":
        if action.name is not None:
            options["name"] = action.name
        locator = page.get_by_role(action.role, **options)
    elif action.finder == "label":
        locator = page.get_by_label(action.name, **options)
    elif action.finder == "text":
        locator = page.get_by_text(action.name, **options)
    elif action.finder == "placeholder":
        locator = page.get_by_placeholder(action.name, **options)
    else:
        raise ScriptError(f"line {action.line}: unsupported locator")
    for op, index in action.positions:
        if op == "first":
            locator = locator.first
        elif op == "last":
            locator = locator.last
        else:
            locator = locator.nth(index)
    return locator
