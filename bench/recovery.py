"""Deterministic task planning and executor approval checks. No model calls."""

from dataclasses import dataclass
import re
from typing import Literal
from urllib.parse import urlsplit


_COMMIT = re.compile(r"\b(buy|pay|purchase|place order|delete|remove account|send|confirm|subscribe|transfer)\b", re.I)
_SENSITIVE = re.compile(r"(?:^|[/_.-])(login|log-in|signin|sign-in|auth|oauth|checkout|payment|billing)(?:$|[/_.-])", re.I)


@dataclass(frozen=True)
class TaskProfile:
    modality: Literal["text", "dom", "visual"]
    risk: Literal["read", "reversible", "irreversible"]
    needs_approval: bool
    signals: tuple[str, ...]


def classify_task(description: str, grounding: dict) -> TaskProfile:
    signals = []
    modality = "text"
    if re.search(r"\b(image|color|colour|screenshot|visually|diagram)\b", description, re.I):
        modality = "visual"
        signals.append("visual task")
    elif grounding.get("forms") or re.search(r"\b(click|fill|select|filter|search)\b", description, re.I):
        modality = "dom"
        signals.append("interactive controls")
    risk = "read"
    if _COMMIT.search(description):
        risk = "irreversible"
        signals.append("commit intent")
    elif re.search(r"\b(add|edit|update|check|uncheck)\b", description, re.I):
        risk = "reversible"
        signals.append("editable state")
    if any(str(form.get("method", "GET")).upper() == "POST" for form in grounding.get("forms", [])):
        signals.append("POST form")
    if grounding.get("error"):
        signals.append("grounding unavailable")
    return TaskProfile(modality, risk, risk == "irreversible", tuple(signals or ["read intent"]))


def plan_checkpoints(task, profile: TaskProfile) -> list[dict]:
    description = task if isinstance(task, str) else task.get("description", "")
    predicates = [{"kind": "no_blocked_action", "value": ""}]
    for url in re.findall(r"https?://[^\s<>\"']+", description):
        predicates.append({"kind": "url_matches", "value": url.rstrip(".,)")})
    for text in re.findall(r'"([^"\n]+)"', description):
        predicates.append({"kind": "text_present", "value": text})
    if profile.modality == "dom" and re.search(r"\b(search|fill)\b", description, re.I):
        predicates.append({"kind": "element_present", "value": "textbox"})
    return predicates


def evaluate_checkpoints(checkpoints: list[dict], evidence: dict) -> list[dict]:
    results = []
    for predicate in checkpoints:
        kind, value = predicate["kind"], predicate["value"]
        if kind == "no_blocked_action":
            passed = not evidence.get("blocked_actions")
        elif kind == "url_matches":
            passed = evidence.get("url") == value
        elif kind == "text_present":
            passed = value.casefold() in str(evidence.get("text", "")).casefold()
        elif kind == "element_present":
            passed = any(item.get("role") == value or item.get("name") == value for item in evidence.get("controls", []))
        else:
            raise ValueError(f"unknown checkpoint: {kind}")
        results.append({**predicate, "passed": passed})
    return results


class ApprovalRequired(RuntimeError):
    pass


class ActionGate:
    async def check(self, step, page) -> tuple[bool, str]:
        from bench.script_grammar import browser_locator
        from bench.script_helpers import _CLICK, _TYPE, _open

        action = step.action
        helper = step.helper
        op = action.op if action else helper.op if helper else "evaluate"
        if step.kind == "read" or op in {"title", "url", "textContent", "innerText", "getAttribute"}:
            return True, "read"
        if op == "evaluate":
            function = step.function
            if re.search(r"\bsendBeacon\s*\(|\b(?:fetch|XMLHttpRequest)\b[\s\S]*?['\"]POST['\"]|\.open\s*\(\s*['\"]POST['\"]", function, re.I):
                return False, "needs approval: POST request"
            if re.search(r"\.(submit|requestSubmit)\s*\(", function):
                selector = re.search(r"document\.querySelector\(\s*(['\"])(.*?)\1\s*\)\.(?:submit|requestSubmit)\(", function)
                if selector and callable(getattr(type(page), "locator", None)):
                    method = await page.locator(selector[2]).evaluate("el => (el.method || 'get').toUpperCase()", timeout=1000)
                    if method == "GET":
                        return True, "GET navigation"
                return False, "needs approval: form submission (POST or unknown method)"
            if re.search(r"\.click\s*\(", function):
                literals = re.findall(r"(['\"])(.*?)\1|/([^/\n]+)/[gimsuy]*", function)
                targets = [quoted or regex for _, quoted, regex in literals]
                checkbox = any(re.search(r"input\[type=['\"]?checkbox", target) for target in targets)
                if not checkbox and any(_COMMIT.search(target) for target in targets):
                    return False, "needs approval: commit control in evaluate"
                if callable(getattr(type(page), "locator", None)):
                    selectors = re.findall(r"querySelector(?:All)?\(\s*(['\"])(.*?)\1\s*\)", function)
                    for _, selector in selectors:
                        controls = await page.locator(selector).evaluate_all("""elements => elements.map(el => {
                            const form = el.form || el.closest('form');
                            const post = !!form && form.method.toUpperCase() === 'POST' &&
                                ((el.tagName === 'BUTTON' && el.type === 'submit') || ['submit','image'].includes(el.type));
                            return {post, checkbox: el.type === 'checkbox', label: el.innerText || el.value || el.getAttribute('aria-label') || ''};
                        })""")
                        if any(control["post"] for control in controls):
                            return False, "needs approval: POST submission in evaluate"
                        if any(not control["checkbox"] and _COMMIT.search(control["label"]) for control in controls):
                            return False, "needs approval: commit control in evaluate"
            return True, "read"
        url = action.value if op == "goto" else getattr(page, "url", "")
        if isinstance(url, str) and _SENSITIVE.search(urlsplit(url).path):
            return False, "needs approval: auth/payment page"
        name = (action.name or "") if action else helper.target if helper else ""
        if op == "click" and _COMMIT.search(name):
            return False, "needs approval: commit control"
        if op == "goto" or op == "goBack":
            return True, "navigation"
        if not callable(getattr(type(page), "locator", None)):
            return True, "no DOM inspection interface"
        locator = None
        if helper:
            for kind, role in _CLICK if op == "click" else _TYPE:
                candidate = _open(page, kind, role, helper.target)
                if hasattr(candidate, "evaluate") and await candidate.count() == 1:
                    locator = candidate
                    break
        elif action.finder == "keyboard":
            locator = page.locator(":focus") if hasattr(page, "locator") else None
        elif action.finder == "page":
            locator = page.locator(action.name) if hasattr(page, "locator") else None
        else:
            locator = browser_locator(page, action)
        if locator is not None and hasattr(locator, "evaluate"):
            info = await locator.evaluate("""el => {
                const form = el.form || el.closest('form');
                return {label: el.innerText || el.value || el.getAttribute('aria-label') || '',
                    href: el.href || '', password: el.type === 'password',
                    method: form ? (el.getAttribute('formmethod') || form.method || 'get').toUpperCase() : '',
                    submit: !!form && ((el.tagName === 'BUTTON' && el.type === 'submit') || ['submit', 'image'].includes(el.type))};
            }""", timeout=1000)
            if info["password"] or _SENSITIVE.search(urlsplit(info["href"]).path):
                return False, "needs approval: auth/payment control"
            if op == "click" and _COMMIT.search(info["label"]):
                return False, "needs approval: commit control"
            enter = op == "press" and "enter" in (action.value if action else helper.value).lower()
            if info["method"] == "POST" and ((op == "click" and info["submit"]) or enter):
                return False, "needs approval: POST submission"
        return True, "read/reversible action"
