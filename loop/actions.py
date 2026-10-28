"""Action, assertion, and observation values the loop passes around."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

REF_RE = re.compile(r"^e[1-9][0-9]{0,2}$")
KEY_RE = re.compile(r"^[A-Za-z0-9+]+$")


class ActionError(Exception):
    """The page rejected an action, or the action itself was not valid."""


class PlannerError(Exception):
    """The planner could not return a batch."""


@dataclass(frozen=True)
class Control:
    ref: str
    role: str
    name: str
    value: str

    def to_dict(self) -> dict:
        return {"ref": self.ref, "role": self.role, "name": self.name, "value": self.value}


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


Action = Goto | Click | Fill | Press | Scroll


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


Assertion = AssertUrl | AssertTitle | AssertText


@dataclass(frozen=True)
class ActionBatch:
    reason: str
    actions: list[Action]
    assertion: Assertion | None
    done: bool


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
    if kind == "goto":
        return Goto(check_url(data.get("url", "")))
    if kind == "click":
        return Click(check_ref(data.get("ref", "")))
    if kind == "fill":
        text = data.get("text", "")
        if not isinstance(text, str):
            raise ActionError("fill text must be a string")
        if len(text) > 2000:
            raise ActionError("fill text is longer than 2000 characters")
        return Fill(check_ref(data.get("ref", "")), text)
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


def parse_assertion(data: object) -> Assertion | None:
    if data is None:
        return None
    if not isinstance(data, dict):
        raise ActionError("assertion must be an object or null")
    text = data.get("text", "")
    if not isinstance(text, str) or not text:
        raise ActionError("assertion text must be a non-empty string")
    if len(text) > 500:
        raise ActionError("assertion text is longer than 500 characters")
    kind = data.get("type")
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
    if len(raw_actions) > 8:
        raise ActionError("a batch can hold at most 8 actions")
    reason = data.get("reason", "")
    if not isinstance(reason, str):
        raise ActionError("reason must be a string")
    done = data.get("done", False)
    if not isinstance(done, bool):
        raise ActionError("done must be true or false")
    return ActionBatch(
        reason=reason.strip(),
        actions=[parse_action(item) for item in raw_actions],
        assertion=parse_assertion(data.get("assertion")),
        done=done,
    )
