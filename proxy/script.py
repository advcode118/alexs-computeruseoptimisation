"""A short Playwright-style locator script. No JavaScript, no model.

fast_act and do_task_segment accept this instead of only a structured action
list. One action per line. The supported locators are getByRole, getByLabel,
getByText, and getByPlaceholder. The supported actions are click, fill,
press, check, and uncheck. Anything else, including page.evaluate, is rejected
before the page is touched.

    page.getByRole("button", { name: "Search" }).click()
    await page.getByRole("textbox", { name: "Search Wikipedia" }).fill("Ada Lovelace")
    page.getByLabel("Item").fill("milk")
"""

from __future__ import annotations

import re
from dataclasses import dataclass

MAX_SCRIPT_CHARS = 2000
MAX_SCRIPT_LINES = 12

_FINDERS = {
    "getByRole": "role",
    "getByLabel": "label",
    "getByText": "text",
    "getByPlaceholder": "placeholder",
}
_OPS_WITH_VALUE = {"fill", "press"}
_OPS = _OPS_WITH_VALUE | {"click", "check", "uncheck"}


class ScriptError(ValueError):
    """The script is outside the locator grammar."""


@dataclass(frozen=True)
class ScriptAction:
    finder: str
    role: str
    name: str
    op: str
    value: str
    line: int


class _Scan:
    def __init__(self, text: str, line: int):
        self.text = text
        self.line = line
        self.i = 0

    def skip(self) -> None:
        while self.i < len(self.text) and self.text[self.i] in " \t":
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
            raise ScriptError(f"line {self.line}: expected a name")
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

    def remaining(self) -> str:
        return self.text[self.i :]


def parse_script(
    source: str,
    *,
    max_lines: int = MAX_SCRIPT_LINES,
    allow_goto: bool = False,
) -> list[ScriptAction]:
    """Parse a locator script. Raises ScriptError and does not touch a page."""
    if not isinstance(source, str):
        raise ScriptError("script must be a string")
    if len(source) > MAX_SCRIPT_CHARS:
        raise ScriptError(f"script is longer than {MAX_SCRIPT_CHARS} characters")
    if max_lines < 1:
        raise ScriptError("script allows no actions")
    actions: list[ScriptAction] = []
    for lineno, raw in enumerate(source.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("//") or line.startswith("#"):
            continue
        if line.endswith(";"):
            line = line[:-1].strip()
        if line.startswith("await "):
            line = line[len("await ") :].strip()
        if line.startswith("page.goto"):
            if not allow_goto:
                raise ScriptError(f"line {lineno}: page.goto is not part of this script")
            actions.append(_parse_goto(line, lineno))
            continue
        actions.append(_parse_line(line, lineno))
        if len(actions) > max_lines:
            raise ScriptError(f"script has more than {max_lines} actions")
    if not actions:
        raise ScriptError("script has no actions")
    return actions


def _parse_goto(line: str, lineno: int) -> ScriptAction:
    scan = _Scan(line, lineno)
    scan.take("page")
    scan.take(".")
    scan.take("goto")
    scan.take("(")
    url = scan.string()
    _skip_until_call_end(scan)
    scan.take(")")
    scan.skip()
    if scan.i != len(scan.text):
        raise ScriptError(f"line {lineno}: unexpected trailing text")
    if not (url.startswith("https://") or url.startswith("http://") or url.startswith("file:")):
        raise ScriptError(f"line {lineno}: goto url must be http or file")
    return ScriptAction(finder="goto", role="", name="", op="goto", value=url, line=lineno)


def _parse_line(line: str, lineno: int) -> ScriptAction:
    lowered = line.casefold()
    for banned in ("evaluate", "import ", "require(", "process.", "fetch(", "page.goto"):
        if banned in lowered:
            raise ScriptError(f"line {lineno}: {banned.strip()} is not part of this script")
    scan = _Scan(line, lineno)
    scan.take("page")
    scan.take(".")
    finder_name = scan.identifier()
    if finder_name not in _FINDERS:
        raise ScriptError(f"line {lineno}: unsupported locator {finder_name}")
    scan.take("(")
    role = ""
    if finder_name == "getByRole":
        role = scan.string()
        scan.skip()
        if not scan.startswith(","):
            raise ScriptError(f"line {lineno}: getByRole needs {{ name: ... }}")
        scan.take(",")
        name = _object_name(scan)
        _skip_until_call_end(scan)
    else:
        name = scan.string()
        _skip_until_call_end(scan)
    scan.take(")")
    scan.take(".")
    op = scan.identifier()
    if op not in _OPS:
        raise ScriptError(f"line {lineno}: unsupported action {op}")
    scan.take("(")
    value = ""
    if op in _OPS_WITH_VALUE:
        value = scan.string()
    _skip_until_call_end(scan)
    scan.take(")")
    scan.skip()
    if scan.i != len(scan.text):
        raise ScriptError(f"line {lineno}: unexpected trailing text")
    if not name.strip():
        raise ScriptError(f"line {lineno}: empty name")
    if not role.strip() and finder_name == "getByRole":
        raise ScriptError(f"line {lineno}: empty role")
    if op == "press" and not value:
        raise ScriptError(f"line {lineno}: press needs a key")
    return ScriptAction(
        finder=_FINDERS[finder_name],
        role=role,
        name=name,
        op=op,
        value=value,
        line=lineno,
    )


def _object_name(scan: _Scan) -> str:
    """Read `{ name: "..." }` and ignore other keys such as exact."""
    scan.take("{")
    found = ""
    seen = False
    while True:
        scan.skip()
        if scan.startswith("}"):
            scan.take("}")
            break
        key = scan.identifier()
        scan.take(":")
        scan.skip()
        if scan.startswith("'") or scan.startswith('"'):
            value = scan.string()
        elif scan.startswith("true"):
            scan.take("true")
            value = "true"
        elif scan.startswith("false"):
            scan.take("false")
            value = "false"
        else:
            raise ScriptError(f"line {scan.line}: unsupported value for {key}")
        if key == "name":
            found = value
            seen = True
        scan.skip()
        if scan.startswith(","):
            scan.take(",")
            continue
        if scan.startswith("}"):
            continue
        raise ScriptError(f"line {scan.line}: expected a comma in the locator options")
    if not seen:
        raise ScriptError(f"line {scan.line}: locator options need a name")
    return found


def _skip_until_call_end(scan: _Scan) -> None:
    """Leave the scan on the closing paren of the current call. Strings stay intact."""
    depth = 0
    while scan.i < len(scan.text):
        ch = scan.text[scan.i]
        if ch in "\"'":
            scan.string()
            continue
        if ch == "(":
            depth += 1
            scan.i += 1
            continue
        if ch == ")" and depth == 0:
            return
        if ch == ")":
            depth -= 1
        scan.i += 1
    raise ScriptError(f"line {scan.line}: unclosed call")


def norm_label(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip().casefold()


_FIELD_ROLES = {"textbox", "searchbox", "combobox"}


def match_element(elements, action: ScriptAction):
    """The one element this locator names, or ScriptError when it is not unique."""
    want = norm_label(action.name)
    hits = []
    for element in elements:
        if not getattr(element, "name", "").strip() or norm_label(element.name) != want:
            continue
        role = (element.role or "").casefold()
        if action.finder == "role" and role != action.role.casefold():
            continue
        if action.finder == "placeholder" and role not in _FIELD_ROLES:
            continue
        hits.append(element)
    if action.finder == "placeholder" and not hits:
        hits = [
            element
            for element in elements
            if getattr(element, "name", "").strip() and norm_label(element.name) == want
        ]
    if len(hits) == 1:
        return hits[0]
    kind = action.role or action.finder
    if not hits:
        raise ScriptError(f"line {action.line}: no {kind} named {action.name!r}")
    raise ScriptError(f"line {action.line}: {len(hits)} matches for {kind} named {action.name!r}")
