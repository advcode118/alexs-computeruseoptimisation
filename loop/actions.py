"""Action, assertion, and observation values the loop passes around."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

REF_RE = re.compile(r"^e[1-9][0-9]{0,2}$")
KEY_RE = re.compile(r"^[A-Za-z0-9+]+$")


class ActionError(Exception):
    """The page rejected an action, or the action itself was not valid."""


class StaleRefError(ActionError):
    """The ref was stamped on a previous page. Observe again."""


class ChooseError(ActionError):
    """The option was not in the list. Observe again and pick a visible name."""


class PlannerError(Exception):
    """The planner could not return a batch."""


@dataclass(frozen=True)
class Control:
    ref: str
    role: str
    name: str
    value: str
    options: tuple[str, ...] = ()
    invalid: str = ""

    def to_dict(self) -> dict:
        data = {"ref": self.ref, "role": self.role, "name": self.name, "value": self.value}
        if self.options:
            data["options"] = list(self.options)
        if self.invalid:
            data["invalid"] = self.invalid
        return data


@dataclass(frozen=True)
class Observation:
    url: str
    title: str
    controls: list[Control]

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "title": self.title,
            "controls": [control.to_dict() for control in self.controls],
        }


@dataclass(frozen=True)
class Goto:
    url: str

    def summary(self) -> str:
        return f"goto {self.url}"


@dataclass(frozen=True)
class Click:
    ref: str

    def summary(self) -> str:
        return f"click {self.ref}"


@dataclass(frozen=True)
class Fill:
    ref: str
    text: str

    def summary(self) -> str:
        return f"fill {self.ref} {self.text!r}"


@dataclass(frozen=True)
class FillNamed:
    """Fill the unique control with this role and accessible name."""

    role: str
    name: str
    text: str

    def summary(self) -> str:
        return f"fill {self.role} {self.name!r} {self.text!r}"


@dataclass(frozen=True)
class ClickNamed:
    """Click the unique control with this role and accessible name."""

    role: str
    name: str

    def summary(self) -> str:
        return f"click {self.role} {self.name!r}"


@dataclass(frozen=True)
class Choose:
    """Set a select to the option with this visible label."""

    ref: str
    option: str

    def summary(self) -> str:
        return f"choose {self.ref} {self.option!r}"


@dataclass(frozen=True)
class ChooseNamed:
    """Set the unique select with this accessible name to a visible option."""

    role: str
    name: str
    option: str

    def summary(self) -> str:
        return f"choose {self.role} {self.name!r} {self.option!r}"


@dataclass(frozen=True)
class Press:
    key: str
    ref: str | None = None

    def summary(self) -> str:
        if self.ref:
            return f"press {self.key} on {self.ref}"
        return f"press {self.key}"


@dataclass(frozen=True)
class Scroll:
    direction: str
    amount: int = 400
    ref: str | None = None

    def summary(self) -> str:
        target = f" on {self.ref}" if self.ref else ""
        return f"scroll {self.direction} {self.amount}{target}"


Action = Goto | Click | Fill | FillNamed | ClickNamed | Choose | ChooseNamed | Press | Scroll


@dataclass(frozen=True)
class AssertUrl:
    text: str

    def summary(self) -> str:
        return f"url contains {self.text!r}"


@dataclass(frozen=True)
class AssertTitle:
    text: str

    def summary(self) -> str:
        return f"title contains {self.text!r}"


@dataclass(frozen=True)
class AssertText:
    text: str

    def summary(self) -> str:
        return f"page contains {self.text!r}"


@dataclass(frozen=True)
class AssertAll:
    texts: tuple[str, ...]

    def summary(self) -> str:
        shown = " and ".join(repr(text) for text in self.texts)
        return f"page contains {shown}"


@dataclass(frozen=True)
class AssertValues:
    """Each check is role, accessible name, expected value."""

    checks: tuple[tuple[str, str, str], ...]

    def summary(self) -> str:
        shown = ", ".join(f"{name}={text!r}" for _, name, text in self.checks)
        return f"values {shown}"


Assertion = AssertUrl | AssertTitle | AssertText | AssertAll | AssertValues


@dataclass(frozen=True)
class ActionBatch:
    reason: str
    actions: list[Action]
    assertion: Assertion | None
    done: bool
    later: tuple[Action, ...] = ()


def check_ref(ref: str) -> str:
    if not isinstance(ref, str) or not REF_RE.fullmatch(ref):
        raise ActionError(f"ref must look like e1, got {ref!r}")
    return ref


def check_url(url: str) -> str:
    if not isinstance(url, str) or not url.strip():
        raise ActionError("goto needs a url")
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https", "file"):
        raise ActionError(f"url scheme must be http, https, or file, got {parsed.scheme or 'none'!r}")
    if parsed.scheme in ("http", "https") and not parsed.netloc:
        raise ActionError(f"url is missing a host: {url}")
    return url.strip()


def parse_action(data: object) -> Action:
    if not isinstance(data, dict):
        raise ActionError("each action must be an object")
    kind = data.get("type")
    if kind == "key":
        kind = "press"
    if kind == "select":
        kind = "choose"
    if kind == "goto":
        return Goto(check_url(data.get("url", "")))
    if kind == "fill":
        text = data.get("text", "")
        if not isinstance(text, str):
            raise ActionError("fill text must be a string")
        if len(text) > 2000:
            raise ActionError("fill text is longer than 2000 characters")
        ref = data.get("ref")
        if ref:
            return Fill(check_ref(ref), text)
        role = data.get("role", "textbox")
        name = data.get("name", "")
        if not isinstance(role, str) or not isinstance(name, str) or not name.strip():
            raise ActionError("fill needs a ref or a role and name")
        return FillNamed(role.strip(), name.strip(), text)
    if kind == "click":
        ref = data.get("ref")
        if ref:
            return Click(check_ref(ref))
        role = data.get("role", "button")
        name = data.get("name", "")
        if not isinstance(role, str) or not isinstance(name, str) or not name.strip():
            raise ActionError("click needs a ref or a role and name")
        return ClickNamed(role.strip(), name.strip())
    if kind == "choose":
        option = data.get("option", data.get("text", ""))
        if not isinstance(option, str) or not option.strip():
            raise ActionError("choose needs the option's visible name")
        if len(option) > 200:
            raise ActionError("choose option is longer than 200 characters")
        ref = data.get("ref")
        if ref:
            return Choose(check_ref(ref), option.strip())
        role = data.get("role", "combobox")
        name = data.get("name", "")
        if not isinstance(role, str) or not isinstance(name, str) or not name.strip():
            raise ActionError("choose needs a ref or a role and name")
        return ChooseNamed(role.strip(), name.strip(), option.strip())
    if kind == "press":
        key = data.get("key", "")
        if not isinstance(key, str) or not key or len(key) > 40 or not KEY_RE.fullmatch(key):
            raise ActionError(f"press key is not usable: {key!r}")
        ref = data.get("ref")
        if ref is not None:
            ref = check_ref(ref)
        return Press(key, ref)
    if kind == "scroll":
        direction = data.get("direction", "down")
        if direction not in ("up", "down"):
            raise ActionError("scroll direction must be up or down")
        amount = data.get("amount", 400)
        if isinstance(amount, bool) or not isinstance(amount, int):
            raise ActionError("scroll amount must be an integer")
        amount = max(50, min(2000, amount))
        ref = data.get("ref")
        if ref is not None:
            ref = check_ref(ref)
        return Scroll(direction, amount, ref)
    raise ActionError(f"unknown action type: {kind!r}")


def _named_action(data: object, kind: str) -> FillNamed | ClickNamed:
    if not isinstance(data, dict):
        raise ActionError(f"{kind} must be an object")
    role = data.get("role", "textbox" if kind == "fill" else "button")
    name = data.get("name", "")
    if not isinstance(role, str) or not isinstance(name, str) or not name.strip():
        raise ActionError(f"{kind} needs a role and name")
    if kind == "click":
        return ClickNamed(role.strip(), name.strip())
    text = data.get("text", "")
    if not isinstance(text, str):
        raise ActionError("fill text must be a string")
    return FillNamed(role.strip(), name.strip(), text)


def parse_assertion(data: object) -> Assertion | None:
    if data is None:
        return None
    if not isinstance(data, dict):
        raise ActionError("assertion must be an object or null")
    kind = data.get("type")
    if kind == "all":
        texts = data.get("texts", [])
        if not isinstance(texts, list) or not texts or not all(isinstance(item, str) and item for item in texts):
            raise ActionError("assertion texts must be a list of strings")
        return AssertAll(tuple(texts))
    if kind == "value":
        raw = data.get("checks")
        if raw is None:
            raw = [{"role": data.get("role", "textbox"), "name": data.get("name", ""), "text": data.get("text", "")}]
        if not isinstance(raw, list) or not raw:
            raise ActionError("value assertion needs checks")
        checks = []
        for item in raw:
            if not isinstance(item, dict):
                raise ActionError("each value check must be an object")
            role = item.get("role", "textbox")
            name = item.get("name", "")
            text = item.get("text", "")
            if not isinstance(role, str) or not isinstance(name, str) or not name or not isinstance(text, str):
                raise ActionError("each value check needs a role, name, and text")
            checks.append((role, name, text))
        return AssertValues(tuple(checks))
    text = data.get("text", "")
    if not isinstance(text, str) or not text:
        raise ActionError("assertion text must be a non-empty string")
    if len(text) > 500:
        raise ActionError("assertion text is longer than 500 characters")
    if kind == "url":
        return AssertUrl(text)
    if kind == "title":
        return AssertTitle(text)
    if kind == "text":
        return AssertText(text)
    raise ActionError(f"unknown assertion type: {kind!r}")


def parse_batch(data: object) -> ActionBatch:
    if not isinstance(data, dict):
        raise ActionError("planner batch must be an object")
    raw_actions = data.get("actions", [])
    if not isinstance(raw_actions, list):
        raise ActionError("actions must be a list")
    fills = data.get("fills", [])
    if not isinstance(fills, list):
        raise ActionError("fills must be a list")
    named = [_named_action(item, "fill") for item in fills]
    submit = data.get("submit")
    if submit is not None:
        named.append(_named_action(submit, "click"))
    raw_later = data.get("later", [])
    if not isinstance(raw_later, list):
        raise ActionError("later must be a list")
    actions = named + [parse_action(item) for item in raw_actions]
    later = tuple(parse_action(item) for item in raw_later)
    if len(actions) + len(later) > 24:
        raise ActionError("a batch can hold at most 24 actions")
    reason = data.get("reason", "")
    if not isinstance(reason, str):
        raise ActionError("reason must be a string")
    done = data.get("done", False)
    if not isinstance(done, bool):
        raise ActionError("done must be true or false")
    return ActionBatch(
        reason=reason.strip(),
        actions=actions,
        assertion=parse_assertion(data.get("assertion")),
        done=done,
        later=later,
    )
