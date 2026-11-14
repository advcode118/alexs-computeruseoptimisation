"""Literal-only Playwright statements for script_first, not the proxy arm.

No source from this parser is executed as JavaScript. The executor dispatches
only the operations below; page.evaluate remains a separate page-context path.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from proxy.script import ScriptError, _Scan, _skip_until_call_end


_FINDERS = {
    "locator": "css",
    "getByRole": "role",
    "getByLabel": "label",
    "getByText": "text",
    "getByPlaceholder": "placeholder",
    "getByTitle": "title",
    "getByAltText": "alt",
    "getByTestId": "testid",
}
_VALUE_OPS = {"fill", "press", "selectOption", "getAttribute", "type", "pressSequentially"}
# Calls that only wait for or scroll to an element. The runner drops them; its
# own lookups already wait for a control to appear.
_NOOP_OPS = {"waitFor", "scrollIntoViewIfNeeded", "isVisible", "count"}
_LOCATOR_OPS = _VALUE_OPS | _NOOP_OPS | {
    "click", "dblclick", "check", "uncheck", "hover", "focus", "clear", "textContent", "innerText",
}
READ_OPS = {"textContent", "innerText", "getAttribute", "title", "url"}
_DROPPED_PAGE_OPS = {
    "setDefaultTimeout", "setDefaultNavigationTimeout",
}
GRAMMAR_HINT = (
    'use page.locator("css").click() or page.evaluate(() => { ... }); '
    'for an object return, wrap it in page.evaluate(() => ({...}))'
)


def _dropped_page_op(method: str) -> bool:
    return method.casefold().startswith(("waitfor", "wait_for")) or method in _DROPPED_PAGE_OPS


@dataclass(frozen=True)
class JsRegex:
    """A /pattern/flags literal from the script, matched in Python and in the page."""

    pattern: str
    flags: str = ""

    def compiled(self) -> re.Pattern:
        flags = re.IGNORECASE if "i" in self.flags else 0
        if "s" in self.flags:
            flags |= re.DOTALL
        if "m" in self.flags:
            flags |= re.MULTILINE
        return re.compile(self.pattern, flags)


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
    # A /regex/ name or text, and selectOption's {label: ...} or [...] argument as JSON.
    pattern: JsRegex | None = None
    option: str = ""


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

    def regex(self) -> JsRegex:
        """A JS regex literal. Only the pattern text and flags are kept."""
        self.skip()
        self.take("/")
        chars: list[str] = []
        in_class = False
        while self.i < len(self.text):
            ch = self.text[self.i]
            self.i += 1
            if ch == "\\" and self.i < len(self.text):
                chars.append(ch + self.text[self.i])
                self.i += 1
                continue
            if ch == "[":
                in_class = True
            elif ch == "]":
                in_class = False
            elif ch == "/" and not in_class:
                start = self.i
                while self.i < len(self.text) and self.text[self.i] in "dgimsuvy":
                    self.i += 1
                pattern = "".join(chars)
                flags = self.text[start : self.i]
                try:
                    JsRegex(pattern, flags).compiled()
                except re.error as exc:
                    raise ScriptError(f"line {self.line}: bad regex /{pattern}/") from exc
                return JsRegex(pattern, flags)
            elif ch in "\r\n":
                break
            chars.append(ch)
        raise ScriptError(f"line {self.line}: unterminated regex")

    def text_or_regex(self):
        self.skip()
        if self.startswith("/"):
            return self.regex()
        return self.string()

    def array(self) -> list:
        self.take("[")
        items = []
        while not self.startswith("]"):
            items.append(self.literal())
            if not self.startswith(","):
                break
            self.take(",")
        self.take("]")
        return items

    def literal(self):
        self.skip()
        if self.startswith('"') or self.startswith("'"):
            return self.string()
        if self.startswith("/"):
            return self.regex()
        if self.startswith("["):
            return self.array()
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
        target = scan.string() if finder in {"css", "role"} else scan.text_or_regex()
        options = {}
        if finder != "css" and scan.startswith(","):
            scan.take(",")
            options = scan.options()
        scan.take(")")
        exact = options.get("exact")
        if "exact" in options and not isinstance(exact, bool):
            raise ScriptError(f"line {line}: exact must be true or false")
        name = options.get("name") if finder == "role" else target
        pattern = None
        if isinstance(name, JsRegex):
            pattern, name = name, name.pattern
        if name is not None and not isinstance(name, str):
            raise ScriptError(f"line {line}: name must be a string")
        if isinstance(target, JsRegex):
            target = target.pattern
        if not target.strip():
            raise ScriptError(f"line {line}: empty locator")
        positions = []
        if not scan.startswith("."):
            # A bare locator with no action only waits; the runner's lookups already wait.
            scan.skip()
            if scan.i != len(text):
                raise ScriptError(f"line {line}: unexpected trailing text")
            return BrowserAction(finder=finder, op="waitFor", line=line, name=name, role=target if finder == "role" else "")
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
            if not scan.startswith("."):
                scan.skip()
                if scan.i != len(text):
                    raise ScriptError(f"line {line}: unexpected trailing text")
                return BrowserAction(finder=finder, op="waitFor", line=line, name=name, role=target if finder == "role" else "")
            scan.take(".")
            op = scan.identifier()
        if op not in _LOCATOR_OPS:
            raise ScriptError(f"line {line}: unsupported locator action {op}")
        scan.take("(")
        value, option = _op_argument(scan, op)
        if op not in _VALUE_OPS and scan.startswith("{"):
            scan.options()
        scan.end_call(options=op in _VALUE_OPS)
        action = BrowserAction(
            finder=finder, op=op, line=line, name=name,
            role=target if finder == "role" else "", value=value,
            exact=exact, positions=tuple(positions), pattern=pattern, option=option,
        )
    else:
        finder = "page"
        if method == "keyboard":
            finder = "keyboard"
            scan.take(".")
            method = scan.identifier()
            if method not in {"press", "type"}:
                raise ScriptError(f"line {line}: unsupported keyboard action {method}")
        elif method not in _PAGE_OPS and not _dropped_page_op(method):
            raise ScriptError(f"line {line}: unsupported page action {method}")
        scan.take("(")
        name = None
        value = ""
        option = ""
        if finder == "keyboard":
            value = scan.string()
        elif method in _PAGE_TARGET_OPS:
            name = scan.string()
            if method in _PAGE_VALUE_OPS:
                scan.take(",")
                value, option = _op_argument(scan, "selectOption" if method == "selectOption" else "fill")
        elif _dropped_page_op(method):
            # These calls are never dispatched. Ignore their arguments, including
            # predicates, but still reject a chained action after the call.
            _skip_until_call_end(scan)
        elif method in {"goBack", "goForward", "reload"} and scan.startswith("{"):
            scan.options()
        scan.end_call(options=method in _PAGE_TARGET_OPS or method == "type")
        action = BrowserAction(finder, method, line, name=name, value=value, option=option)
    scan.skip()
    if scan.i != len(text):
        raise ScriptError(f"line {line}: unexpected trailing text")
    if action.op == "press" and not action.value:
        raise ScriptError(f"line {line}: press needs a key")
    return action


_PAGE_VALUE_OPS = {"fill", "press", "type", "selectOption"}
_PAGE_TARGET_OPS = _PAGE_VALUE_OPS | {"click", "dblclick", "check", "uncheck", "hover", "focus"}
_PAGE_OPS = _PAGE_TARGET_OPS | {"goBack", "goForward", "reload", "title", "url"}


def _op_argument(scan: _LiteralScan, op: str) -> tuple[str, str]:
    """The value argument of an action: a string, or selectOption's object or list as JSON."""
    if op not in _VALUE_OPS:
        return "", ""
    if op == "selectOption":
        scan.skip()
        if scan.startswith("{"):
            return "", json.dumps(scan.options())
        if scan.startswith("["):
            items = scan.array()
            if not all(isinstance(item, str) for item in items):
                raise ScriptError(f"line {scan.line}: selectOption list must hold strings")
            return "", json.dumps(items)
    return scan.string(), ""


def action_kind(action: BrowserAction) -> str:
    if (action.finder == "page" and _dropped_page_op(action.op)) or action.op in _NOOP_OPS:
        return "wait"
    if action.op in READ_OPS:
        return "read"
    return "locator" if action.finder not in {"page", "keyboard"} else action.finder


def browser_locator(page, action: BrowserAction):
    options = {} if action.exact is None else {"exact": action.exact}
    name = action.pattern.compiled() if action.pattern is not None else action.name
    if action.finder == "css":
        locator = page.locator(action.name)
    elif action.finder == "role":
        if action.name is not None:
            options["name"] = name
        locator = page.get_by_role(action.role, **options)
    elif action.finder == "label":
        locator = page.get_by_label(name, **options)
    elif action.finder == "text":
        locator = page.get_by_text(name, **options)
    elif action.finder == "placeholder":
        locator = page.get_by_placeholder(name, **options)
    elif action.finder == "title":
        locator = page.get_by_title(name, **options)
    elif action.finder == "alt":
        locator = page.get_by_alt_text(name, **options)
    elif action.finder == "testid":
        locator = page.get_by_test_id(action.name)
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
