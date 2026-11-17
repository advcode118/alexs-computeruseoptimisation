"""Deterministic task planning and executor approval checks. No model calls."""

from dataclasses import dataclass
import asyncio
import re
from typing import Literal
from urllib.parse import urlsplit


_COMMIT = re.compile(r"\b(buy|pay|purchase|place order|delete|remove account|send|confirm|subscribe|transfer|order|checkout|book|reserve|donate|post|publish|apply|cancel|unsubscribe|sign up|submit)\b", re.I)
_COMMIT_INTENT = re.compile(r"\b(buy|pay|purchase|place order|delete|remove account|send|confirm\s+(?:(?:the|my|your)\s+)?(?:order|payment|purchase)|subscribe|transfer)\b|^(book|reserve|donate|post|publish|cancel|unsubscribe|sign up|checkout)\b", re.I)
_PAYMENT = re.compile(r"(?:^|[/_.-])(checkout|payment|billing)(?:$|[/_.-])", re.I)
_AUTH = re.compile(r"(?:^|[/_.-])(login|log-in|signin|sign-in|auth|oauth|authenticate)(?:$|[/_.-])", re.I)

_CONTROL_POLICY = r"""function policy(el, cfg, submitting = false, submitter = null) {
    const sensitive = value => {
        try {
            const path = new URL(value, document.baseURI).pathname;
            return new RegExp(cfg.payment, 'i').test(path) ||
                (!cfg.auth && new RegExp(cfg.authPath, 'i').test(path));
        } catch { return false; }
    };
    if (!(el instanceof Element)) return '';
    const control = el.closest('button, input, a[href], [role="button"], [role="link"]') || el;
    if ((control.type === 'password' && !cfg.auth) ||
        (control.getAttribute('href') && sensitive(control.href))) return 'auth/payment control';
    if (cfg.activation === false) return '';
    const plainLink = control.matches('a[href]') && !control.onclick && !control.hasAttribute('onclick');
    const commit = control.matches('button, input[type="submit"], input[type="image"], [role="button"], [role="link"]') ||
        (control.matches('a[href]') && !plainLink);
    const label = control.innerText || control.value || control.getAttribute('aria-label') || '';
    const form = submitting ? el : control.form;
    const isSubmit = submitting || (form && ((control.tagName === 'BUTTON' && control.type === 'submit') ||
        ['submit', 'image'].includes(control.type)));
    const method = (submitter?.getAttribute('formmethod') || (!submitting && control.getAttribute('formmethod')) || form?.method || 'get').toUpperCase();
    const readSubmit = form && method === 'GET' && /^(submit|apply)$/i.test(label.trim());
    const readFilter = /^apply filters?$/i.test(label.trim()) ||
        (/^order by /i.test(label.trim()) && !new RegExp(cfg.commit, 'i').test(label.trim().replace(/^order by /i, '')));
    if (commit && !readSubmit && !readFilter && new RegExp(cfg.commit, 'i').test(label)) return 'commit control';
    if (submitting && submitter) {
        const reason = policy(submitter, cfg);
        if (reason) return reason;
    }
    let login = false;
    if (cfg.auth && form) {
        try {
            const destination = new URL(submitter?.getAttribute('formaction') || control.getAttribute('formaction') || form.action, document.baseURI);
            login = destination.origin === location.origin && !new RegExp(cfg.payment, 'i').test(destination.pathname) &&
                (!!form.querySelector('input[type="password"]') || new RegExp(cfg.authPath, 'i').test(destination.pathname));
        } catch {}
    }
    if (isSubmit && method === 'POST' && !login) return 'POST submission';
    return '';
}"""

_INSTALL_GUARD = """cfg => {
    const policy = POLICY;
    const state = window.__actionGate || (window.__actionGate = {originals: {}});
    state.cfg = cfg;
    const deny = (el, submitting = false, submitter = null) => {
        const reason = policy(el, state.cfg, submitting, submitter);
        if (reason) window[state.cfg.binding](reason);
        return !!reason;
    };
    if (state.listener) for (const type of ['click', 'submit']) window.removeEventListener(type, state.listener, true);
    state.listener = event => {
        if (deny(event.target, event.type === 'submit', event.submitter)) {
            event.preventDefault();
            event.stopImmediatePropagation();
        }
    };
    for (const type of ['click', 'submit']) window.addEventListener(type, state.listener, true);
    for (const method of ['submit', 'requestSubmit']) {
        const original = state.originals[method] || (state.originals[method] = HTMLFormElement.prototype[method]);
        HTMLFormElement.prototype[method] = function(...args) {
            if (!deny(this, true, args[0])) return original.apply(this, args);
        };
    }
}""".replace('POLICY', _CONTROL_POLICY)


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
    if _COMMIT_INTENT.search(description):
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
    return predicates


def evaluate_checkpoints(checkpoints: list[dict], evidence: dict) -> list[dict]:
    results = []
    for predicate in checkpoints:
        kind, value = predicate["kind"], predicate["value"]
        if kind == "no_blocked_action":
            passed = not evidence.get("blocked_actions")
        elif kind == "url_matches":
            try:
                goal, live = urlsplit(value), urlsplit(evidence.get('url', ''))
                passed = bool(goal.hostname) and live.hostname == goal.hostname and (
                    not goal.path.rstrip('/') or live.path.rstrip('/') == goal.path.rstrip('/') or
                    live.path.startswith(goal.path.rstrip('/') + '/'))
            except ValueError:
                passed = False
        elif kind == "text_present":
            claimed = evidence.get('claimed') or {}
            candidates = [claimed.get('answer', '')]
            candidates.extend(evidence.get('filled_values', []))
            candidates.extend(item.get('value', '') for item in evidence.get('controls', []) if isinstance(item, dict))
            passed = any(value.casefold() in str(candidate).casefold() for candidate in candidates)
        elif kind == "element_present":
            passed = any(item.get("role") == value or item.get("name") == value for item in evidence.get("controls", []))
        else:
            raise ValueError(f"unknown checkpoint: {kind}")
        results.append({**predicate, "passed": passed})
    return results


class ApprovalRequired(RuntimeError):
    pass


def configure_gate(client, *, description: str = "", profile: TaskProfile | None = None):
    gate = getattr(client, 'gate', None)
    if not isinstance(gate, ActionGate) or gate.description != description:
        gate = client.gate = ActionGate(description=description, profile=profile)
    elif profile is not None:
        gate.profile = profile
    return gate


class ActionGate:
    def __init__(self, *, description: str = "", profile: TaskProfile | None = None):
        self.description = description
        self.profile = profile or classify_task(description, {})
        self.auth_approved = bool(re.search(r"\b(log(?:ging)?[ -]?in|sign(?:ing)?[ -]?in)\b", description, re.I))
        self.blocked = []
        self._bound_pages = set()
        self._step = None
        self._navigations = {}

    async def wait_for_document(self, page, timeout):
        if page not in self._navigations:
            self._navigations[page] = None

            def requested(request):
                if request.is_navigation_request() and request.frame == page.main_frame:
                    if self._navigations[page] is None or self._navigations[page].done():
                        self._navigations[page] = asyncio.get_running_loop().create_future()

            def committed(frame):
                pending = self._navigations[page]
                if frame == page.main_frame and pending is not None and not pending.done():
                    pending.set_result(None)

            def failed(request):
                if request.is_navigation_request() and request.frame == page.main_frame:
                    committed(page.main_frame)

            page.on('request', requested)
            page.on('framenavigated', committed)
            page.on('requestfailed', failed)
        pending = self._navigations[page]
        if pending is not None and not pending.done():
            await asyncio.wait_for(asyncio.shield(pending), timeout / 1000)
        await page.wait_for_load_state('domcontentloaded', timeout=timeout)

    def record_block(self, reason, step=None):
        step = step or self._step
        record = {"line": step.line if step else 0, "source": step.source if step else "", "reason": reason}
        if record not in self.blocked:
            self.blocked.append(record)

    def _config(self):
        return {"commit": _COMMIT.pattern, "payment": _PAYMENT.pattern, "authPath": _AUTH.pattern,
                "auth": self.auth_approved, "binding": f"__gate_block_{id(self)}"}

    async def install(self, page, step):
        self._step = step
        cfg = self._config()
        if page not in self._bound_pages:
            await page.expose_function(cfg['binding'], lambda reason: self.record_block('needs approval: ' + reason))
            self._bound_pages.add(page)
        await page.evaluate(_INSTALL_GUARD, cfg)

    def _sensitive(self, url):
        try:
            path = urlsplit(url if isinstance(url, str) else "").path
        except ValueError:
            return False
        return bool(_PAYMENT.search(path) or (not self.auth_approved and _AUTH.search(path)))

    async def check(self, step, page) -> tuple[bool, str]:
        from bench.script_grammar import browser_locator
        from bench.script_helpers import _CLICK, _TYPE, _open
        from bench.script_first import _ACTION_TIMEOUT_MS

        action = step.action
        helper = step.helper
        op = action.op if action else helper.op if helper else "evaluate"
        dom = callable(getattr(type(page), "locator", None))
        if dom:
            await self.wait_for_document(page, _ACTION_TIMEOUT_MS)
        if step.kind == "read" or op in {"title", "url", "textContent", "innerText", "getAttribute"}:
            return True, "read"
        if op == "evaluate":
            if dom:
                await self.install(page, step)
                return True, "runtime approval guard"
            function = step.function
            if re.search(r"\bsendBeacon\s*\(|\b(?:fetch|XMLHttpRequest)\b[\s\S]*?['\"]POST['\"]|\.open\s*\(\s*['\"]POST['\"]", function, re.I):
                return False, "needs approval: POST request"
            if re.search(r"\.(submit|requestSubmit)\s*\(", function):
                return False, "needs approval: form submission (POST or unknown method)"
            if re.search(r"\.click\s*\(", function):
                literals = re.findall(r"(['\"])(.*?)\1|/([^/\n]+)/[gimsuy]*", function)
                targets = [quoted or regex for _, quoted, regex in literals]
                checkbox = any(re.search(r"input\[type=['\"]?checkbox", target) for target in targets)
                if not dom and not checkbox and any(_COMMIT.search(target) for target in targets):
                    return False, "needs approval: commit control in evaluate"
            return True, "read"
        name = (action.name or "") if action else helper.target if helper else ""
        if not dom and op == "click" and _COMMIT.search(name):
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
            if op != "press" or action.value.split('+')[-1].lower() not in {'enter', 'space', ' '}:
                return True, "global keyboard action"
            locator = page.locator(":focus")
            if not await locator.count():
                return True, "no focused control"
        elif action.finder == "page":
            locator = page.locator(action.name) if hasattr(page, "locator") else None
        else:
            locator = browser_locator(page, action)
        if locator is not None and hasattr(locator, "evaluate"):
            await locator.wait_for(state='attached', timeout=_ACTION_TIMEOUT_MS)
            key = action.value if action else getattr(helper, 'value', '')
            enter = op == 'press' and key.split('+')[-1].lower() == 'enter'
            activation = op == 'click' or (op == 'press' and key.split('+')[-1].lower() in {'enter', 'space', ' '})
            cfg = {**self._config(), 'activation': activation, 'enter': enter}
            reason = await locator.evaluate("""(el, cfg) => {
                const policy = POLICY;
                const submitter = cfg.enter && el.form ? Array.from(el.form.elements).find(node =>
                    (node.tagName === 'BUTTON' && node.type === 'submit') ||
                    (node.tagName === 'INPUT' && ['submit', 'image'].includes(node.type))) : null;
                return policy(el, cfg) || (cfg.enter && el.form ? policy(el.form, cfg, true, submitter) : '');
            }""".replace('POLICY', _CONTROL_POLICY), cfg, timeout=_ACTION_TIMEOUT_MS)
            if reason:
                return False, 'needs approval: ' + reason
        return True, "read/reversible action"
