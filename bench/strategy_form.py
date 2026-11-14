"""Form specialist for script_first: fill real fields from a schema, submit, read what is new.

The generic path asks the model to write a whole script blind. For forms
that guesses field selectors it has never seen, and it often reads a result
that was on the page before the submit. This strategy works the other way:

1. Observe. Load the start page and extract every visible field (label,
   type, options, required flag, current value) and every button and link,
   with no model.
2. Ask the model for data, not code. It sees the task and the numbered
   schema and calls one tool, form_step, with a small JSON action: fill these
   numbered fields with these values and press this numbered control, or
   click a numbered link to reach the form.
3. Fill in code: typed input, real option selection, clicks for radios and
   checkboxes, a read-back of every value, and a keyboard retry for widgets
   that clear a filled value. Dialogs are accepted and recorded.
4. Submit and wait for the page to change, then diff the visible text. The
   model sees only what is new since the submit and copies the answer from
   those lines (action done), fixes a validation error once, or fills the
   next step of a multi-step form.
5. End check, no model: the submit changed something, the answer is on the
   live page, and it was on none of the pages seen before the submit.
   Anything else is FAIL, and the harness then runs the generic path.

No host names, site names, or task ids here. Markers and expected answers
are never read.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime

STRATEGY_ENV = "CU_SF_STRATEGY"
STRATEGY_NAME = "form"

# Model calls per task: observe+fill, result, one correction or next step, and two spare.
MAX_MODEL_CALLS = 5
# Fill-and-submit actions per task, including one corrected attempt.
MAX_FILLS = 3
# Wall-time budget for the strategy before it hands back to the generic path.
BUDGET_S = 40.0
_NAV_TIMEOUT_MS = 15000
_ACTION_TIMEOUT_MS = 4000
_SETTLE_MAX_S = 8.0
_NEW_LINES_CAP = 40
_FIELDS_CAP = 60
_LINKS_CAP = 30


def strategy_enabled(name: str = STRATEGY_NAME) -> bool:
    """CU_SF_STRATEGY is a comma list of specialist type names."""
    raw = os.environ.get(STRATEGY_ENV, "")
    return name in {part.strip().casefold() for part in raw.split(",") if part.strip()}


# ---------------------------------------------------------------- router

# A task that gives values to enter and asks for what happens after a submit.
_FORM_VERB = re.compile(
    r"\b(?:fill(?:ing)?\s+(?:in|out)|submit(?:s|ting)?|send(?:ing)?\s+(?:the|a|an)\b[^.]{0,40}?\b(?:form|message|enquiry|inquiry)"
    r"|register|sign\s+up|log\s*in\s+with|book\s+an?\b|check\s*out|complete\s+the\b[^.]{0,30}?\bform"
    r"|enter\s+(?:the\s+)?(?:[\w-]+\s+){0,4}?(?:value|code|number|name|e-?mail|date|address)"
    r"|(?:choose|select|tick|pick)\b[^.]{0,80}?(?:,|\bthen\b|\band\b)\s*(?:get|press|click|submit|calculate|send)\b"
    r"|(?:calculate|convert|work\s+out)\b)",
    re.IGNORECASE,
)
_FORM_WORD = re.compile(r"\b(?:form|calculator|converter|checkout|contact\s+us|confirm(?:ation)?|submission)\b", re.IGNORECASE)
# The search specialist owns site search; a value read is not a form.
_SEARCH = re.compile(r"\b(?:search(?:es|ing)?|look\s+up|find\s+the\s+page)\b", re.IGNORECASE)
_REPORT = re.compile(r"\b(?:report|say|tell|return|give)\b", re.IGNORECASE)


def claims(description: str) -> bool:
    """Cheap text router: values to enter, a submit, and a result to report.

    The live page is the second gate: no fillable field and no link to one
    on the start page means the strategy hands back at once.
    """
    text = description or ""
    if _SEARCH.search(text) and not re.search(r"\bform\b", text, re.IGNORECASE):
        return False
    verb = _FORM_VERB.search(text)
    if not verb:
        return False
    return bool(_FORM_WORD.search(text) or _REPORT.search(text))


# ---------------------------------------------------------------- page schema

CONSENT_SELECTORS = (
    # Google Funding Choices, OneTrust, Cookiebot, Quantcast, Didomi, Usercentrics-style buttons.
    ".fc-cta-consent",
    "#onetrust-accept-btn-handler",
    "#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll",
    "#CybotCookiebotDialogBodyButtonAccept",
    ".qc-cmp2-summary-buttons button[mode=primary]",
    "#didomi-notice-agree-button",
    "button[data-testid=uc-accept-all-button]",
)

_CONSENT_JS = r"""(selectors) => {
  const shown = (el) => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  for (const sel of selectors) {
    for (const el of document.querySelectorAll(sel)) { if (shown(el)) { el.click(); return sel; } }
  }
  const words = /^(accept all|accept all cookies|allow all|allow all cookies|i agree|agree|consent|got it|accept cookies|accept)$/i;
  for (const box of document.querySelectorAll('[id*=cookie i],[class*=cookie i],[id*=consent i],[class*=consent i],[aria-label*=cookie i],[role=dialog]')) {
    if (!shown(box)) continue;
    for (const el of box.querySelectorAll('button,a[role=button],[role=button],input[type=button],input[type=submit]')) {
      const t = (el.innerText || el.value || '').trim();
      if (words.test(t) && shown(el)) { el.click(); return 'text:' + t; }
    }
  }
  return '';
}"""

SCHEMA_JS = r"""(args) => {
  const terms = (args && args.terms) || [];
  const fieldsCap = (args && args.fieldsCap) || 60;
  const linksCap = (args && args.linksCap) || 30;
  const clean = (s) => (s || '').replace(/\s+/g, ' ').trim();
  const shown = (el) => {
    if (!el || !el.isConnected) return false;
    const r = el.getBoundingClientRect();
    if (r.width < 1 && r.height < 1) return false;
    const s = getComputedStyle(el);
    return s.visibility !== 'hidden' && s.display !== 'none';
  };
  const inConsent = (el) => !!el.closest('[id*=cookie i],[class*=cookie i],[id*=consent i],[class*=consent i],[class*=fc-],[id^=onetrust],[id^=CybotCookiebot]');
  const ownText = (node, skip) => {
    let out = '';
    const walk = (n) => {
      if (n === skip) return;
      if (n.nodeType === 3) { out += ' ' + n.nodeValue; return; }
      if (n.nodeType !== 1) return;
      const tag = n.tagName.toLowerCase();
      if (['input', 'select', 'textarea', 'script', 'style', 'option', 'button'].includes(tag)) return;
      for (const c of n.childNodes) walk(c);
    };
    walk(node);
    return clean(out);
  };
  const byIds = (ids) => clean((ids || '').split(/\s+/).map((id) => {
    const e = id && document.getElementById(id); return e ? (e.innerText || e.textContent || '') : '';
  }).join(' '));
  const nearText = (el) => {
    let node = el;
    for (let depth = 0; depth < 4 && node && node !== document.body; depth++) {
      let sib = node.previousElementSibling;
      for (let hops = 0; sib && hops < 3; hops++, sib = sib.previousElementSibling) {
        if (sib.querySelector && sib.querySelector('input,select,textarea') && !['LABEL'].includes(sib.tagName)) break;
        const t = clean(sib.innerText || sib.textContent || '');
        if (t && t.length <= 120) return t;
      }
      const cell = node.closest && node.closest('td');
      if (cell && cell.previousElementSibling) {
        const t = clean(cell.previousElementSibling.innerText || '');
        if (t && t.length <= 120) return t;
      }
      node = node.parentElement;
      if (node) {
        const t = ownText(node, el);
        if (t && t.length <= 80) return t;
      }
    }
    return '';
  };
  const labelOf = (el) => {
    const parts = [];
    const lab = byIds(el.getAttribute('aria-labelledby'));
    if (lab) parts.push(lab);
    if (el.getAttribute('aria-label')) parts.push(clean(el.getAttribute('aria-label')));
    if (el.labels && el.labels.length) {
      for (const l of el.labels) { const t = ownText(l, el); if (t) parts.push(t); }
    }
    if (!parts.length && el.getAttribute('placeholder')) parts.push(clean(el.getAttribute('placeholder')));
    if (!parts.length && el.getAttribute('title')) parts.push(clean(el.getAttribute('title')));
    if (!parts.length) { const t = nearText(el); if (t) parts.push(t); }
    if (!parts.length) {
      const n = el.getAttribute('name') || el.id || '';
      if (n) parts.push(n.replace(/[_\-\[\]]+/g, ' ').replace(/([a-z])([A-Z])/g, '$1 $2').trim());
    }
    const seen = new Set();
    return parts.filter((p) => { const k = p.toLowerCase(); if (seen.has(k)) return false; seen.add(k); return true; }).join(' / ').slice(0, 120);
  };
  const forms = Array.from(document.forms);
  const formKey = (el) => {
    const f = el.form || el.closest('form');
    return f ? forms.indexOf(f) : -1;
  };
  const formName = (f) => {
    if (!f) return '';
    const h = f.querySelector('h1,h2,h3,h4,legend');
    return clean(f.getAttribute('aria-label') || (h && h.innerText) || f.getAttribute('name') || f.id || '').slice(0, 80);
  };
  document.querySelectorAll('[data-cu-n]').forEach((e) => { e.removeAttribute('data-cu-n'); e.removeAttribute('data-cu-opt'); });
  let n = 0;
  const fields = [];
  const groups = new Map();
  const nodes = document.querySelectorAll('input, select, textarea, [contenteditable=true], [role=textbox], [role=combobox]:not(input):not(select), [role=checkbox]:not(input), [role=radio]:not(input)');
  for (const el of nodes) {
    if (fields.length >= fieldsCap) break;
    const tag = el.tagName.toLowerCase();
    let type = tag === 'input' ? (el.getAttribute('type') || 'text').toLowerCase() : tag;
    if (tag !== 'input' && tag !== 'select' && tag !== 'textarea') {
      const role = el.getAttribute('role') || '';
      type = role === 'checkbox' ? 'checkbox' : role === 'radio' ? 'radio' : role === 'combobox' ? 'combobox' : 'textbox';
      if (el.closest('input,select,textarea')) continue;
    }
    if (['hidden', 'submit', 'button', 'reset', 'image'].includes(type)) continue;
    if (inConsent(el)) continue;
    const labelShown = el.labels && Array.from(el.labels).some(shown);
    const visible = shown(el) || ((type === 'radio' || type === 'checkbox') && labelShown);
    if (!visible) continue;
    if (el.disabled) continue;
    const required = !!(el.required || el.getAttribute('aria-required') === 'true');
    const form = formKey(el);
    if (type === 'radio') {
      const gname = el.getAttribute('name') || ('__radio' + n);
      const key = form + '|' + gname;
      let g = groups.get(key);
      if (!g) {
        n += 1;
        const fs = el.closest('fieldset');
        const legend = fs && fs.querySelector('legend');
        const box = el.closest('[role=radiogroup]');
        let glabel = clean((legend && legend.innerText) || (box && (box.getAttribute('aria-label') || byIds(box.getAttribute('aria-labelledby')))) || '');
        g = { n, kind: 'radio', type: 'radio', name: gname, label: glabel, options: [], value: '', required, form };
        groups.set(key, g);
        fields.push(g);
      }
      const optLabel = labelOf(el) || clean(el.value);
      el.setAttribute('data-cu-n', String(g.n));
      el.setAttribute('data-cu-opt', String(g.options.length));
      g.options.push(optLabel.slice(0, 80));
      if (el.checked || el.getAttribute('aria-checked') === 'true') g.value = optLabel.slice(0, 80);
      g.required = g.required || required;
      continue;
    }
    n += 1;
    el.setAttribute('data-cu-n', String(n));
    const item = { n, kind: 'field', type, name: el.getAttribute('name') || el.id || '', label: labelOf(el), required, form, value: '' };
    if (tag === 'select') {
      const opts = Array.from(el.options).map((o) => clean(o.text || o.value).slice(0, 80));
      item.options = opts;
      item.multiple = !!el.multiple;
      item.value = el.selectedIndex >= 0 ? clean(el.options[el.selectedIndex].text) : '';
    } else if (type === 'checkbox') {
      item.value = (el.checked || el.getAttribute('aria-checked') === 'true') ? 'on' : 'off';
    } else if (tag === 'input' || tag === 'textarea') {
      item.value = type === 'password' ? '' : clean(el.value).slice(0, 80);
      const list = el.list;
      if (list) item.options = Array.from(list.options).map((o) => clean(o.value || o.text).slice(0, 80)).slice(0, 40);
      if (el.getAttribute('min')) item.min = el.getAttribute('min');
      if (el.getAttribute('max')) item.max = el.getAttribute('max');
      if (el.getAttribute('maxlength') && Number(el.getAttribute('maxlength')) > 0) item.maxlength = Number(el.getAttribute('maxlength'));
      if (el.getAttribute('pattern')) item.pattern = el.getAttribute('pattern').slice(0, 60);
      if (el.readOnly) item.readonly = true;
      if (type === 'search' || el.closest('[role=search]') || /^(q|query|search|s)$/i.test(el.getAttribute('name') || '')) item.search = true;
    } else {
      item.value = clean(el.innerText || '').slice(0, 80);
    }
    fields.push(item);
  }
  for (const g of fields) {
    if (g.kind === 'radio' && !g.label) {
      const first = document.querySelector(`[data-cu-n="${g.n}"]`);
      let box = first ? first.parentElement : null;
      for (let d = 0; d < 4 && box; d++, box = box.parentElement) {
        if (box.querySelectorAll(`[data-cu-n="${g.n}"]`).length >= g.options.length) {
          const t = nearText(box);
          if (t) { g.label = t.slice(0, 100); break; }
        }
      }
      if (!g.label) g.label = g.name.replace(/[_\-]+/g, ' ');
    }
  }
  const controls = [];
  const seen = new Set();
  const lower = terms.map((t) => t.toLowerCase());
  const score = (t) => lower.reduce((s, w) => s + (t.toLowerCase().includes(w) ? 1 : 0), 0);
  for (const el of document.querySelectorAll('button, input[type=submit], input[type=button], input[type=image], [role=button], a[href], [role=link], [role=tab], [role=menuitem]')) {
    if (inConsent(el) || !shown(el) || el.disabled) continue;
    if (el.closest('[data-cu-n]') && el.tagName.toLowerCase() !== 'button') continue;
    const tag = el.tagName.toLowerCase();
    const type = (el.getAttribute('type') || '').toLowerCase();
    if (type === 'reset') continue;
    let text = clean(el.innerText || el.value || el.getAttribute('aria-label') || el.getAttribute('title') || '');
    if (!text) { const img = el.querySelector('img[alt]'); if (img) text = clean(img.getAttribute('alt')); }
    if (!text) text = clean(el.getAttribute('name') || el.id || '');
    if (!text) continue;
    text = text.slice(0, 80);
    const form = formKey(el);
    const isLink = tag === 'a' && !el.getAttribute('role') && !/\bbtn\b|button/i.test(el.className || '');
    const submits = (tag === 'button' && (type === 'submit' || (!type && form >= 0))) || (tag === 'input' && (type === 'submit' || type === 'image'));
    const key = (isLink ? 'link' : 'button') + '|' + text.toLowerCase() + '|' + form;
    if (seen.has(key)) continue;
    seen.add(key);
    controls.push({ el, kind: isLink ? 'link' : 'button', text, form, submits, score: score(text), order: controls.length,
      href: isLink ? (el.href || '') : '' });
  }
  const buttons = controls.filter((c) => c.kind === 'button');
  const links = controls.filter((c) => c.kind === 'link');
  links.sort((a, b) => (b.score - a.score) || (a.order - b.order));
  const keptButtons = buttons.slice(0, 40);
  const keptLinks = links.slice(0, linksCap);
  const kept = [...keptButtons, ...keptLinks].sort((a, b) => a.order - b.order);
  const out = [];
  for (const c of kept) {
    n += 1;
    c.el.setAttribute('data-cu-n', String(n));
    out.push({ n, kind: c.kind, text: c.text, form: c.form, submits: c.submits, href: c.href });
  }
  const formInfo = forms.map((f, i) => ({ index: i, name: formName(f), action: clean(f.getAttribute('action') || ''), method: (f.method || 'get').toLowerCase() }));
  return {
    url: location.href,
    title: document.title || '',
    h1: clean((document.querySelector('h1') || {}).innerText || ''),
    fields,
    controls: out,
    forms: formInfo,
  };
}"""

_TEXT_JS = r"""() => {
  const b = document.body;
  return b ? (b.innerText || '') : '';
}"""


@dataclass
class FormStep:
    """One strategy step, logged on the harness step list."""

    action: dict
    result: str
    page_url: str
    model_ms: float = 0.0
    tool_ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class FormOutcome:
    passed: bool = False
    answer: str = ""
    reason: str = ""
    final_url: str = ""
    page_text: str = ""
    claimed: bool = False
    model_calls: int = 0
    model_ms: float = 0.0
    tool_ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    cache_write_30m_tokens: int = 0
    cache_write_12h_tokens: int = 0
    steps: list[FormStep] = field(default_factory=list)


_STOP = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "at", "for", "with", "by", "from", "as", "is", "it",
    "its", "this", "that", "then", "into", "page", "site", "demo", "form", "report", "shown", "shows", "use",
    "using", "fill", "submit", "enter", "send", "open", "click", "your", "you", "any", "all", "what", "which",
}


def task_terms(description: str) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9'-]{2,}", description or "")
    out: list[str] = []
    for word in words:
        low = word.casefold()
        if low not in _STOP and low not in out:
            out.append(low)
    return out[:30]


def _opts_text(options: list[str], terms: list[str], value: str = "") -> str:
    """A select's options, trimmed: the first ones, any that match the task, and the count."""
    if len(options) <= 25:
        return " | ".join(options)
    picked: list[str] = []
    for index, option in enumerate(options):
        low = option.casefold()
        if index < 8 or option == value or any(term in low for term in terms if len(term) > 3):
            picked.append(option)
        if len(picked) >= 25:
            break
    return " | ".join(picked) + f" | ... ({len(options)} options in all; any exact option text works)"


def render_schema(schema: dict, terms: list[str]) -> str:
    """The numbered page schema the model chooses from."""
    lines = [f"URL: {schema.get('url', '')}", f"Title: {schema.get('title', '')}"]
    if schema.get("h1"):
        lines.append(f"Heading: {schema['h1']}")
    forms = {item["index"]: item for item in schema.get("forms") or []}
    fields = schema.get("fields") or []
    controls = schema.get("controls") or []
    groups: dict[int, list[str]] = {}
    for item in fields:
        typ = item.get("type", "text")
        label = item.get("label") or item.get("name") or "(no label)"
        bits = [f"[{item['n']}] {typ} \"{label}\""]
        if item.get("required"):
            bits.append("required")
        if item.get("search"):
            bits.append("site search box")
        if item.get("readonly"):
            bits.append("read-only")
        if typ == "date":
            bits.append("format YYYY-MM-DD")
        for key in ("min", "max", "maxlength", "pattern"):
            if item.get(key) not in (None, ""):
                bits.append(f"{key}={item[key]}")
        if item.get("options"):
            bits.append("options: " + _opts_text(item["options"], terms, item.get("value", "")))
        if item.get("value") not in (None, ""):
            bits.append(f"now: {item['value']}")
        groups.setdefault(int(item.get("form", -1)), []).append(" ".join(bits) if len(bits) == 1 else bits[0] + " (" + "; ".join(bits[1:]) + ")")
    button_lines: dict[int, list[str]] = {}
    link_lines: list[str] = []
    for item in controls:
        if item["kind"] == "link":
            link_lines.append(f"[{item['n']}] link \"{item['text']}\"")
            continue
        tag = "submit button" if item.get("submits") else "button"
        button_lines.setdefault(int(item.get("form", -1)), []).append(f"[{item['n']}] {tag} \"{item['text']}\"")
    keys = sorted(set(groups) | set(button_lines), key=lambda k: (k < 0, k))
    for key in keys:
        if key >= 0:
            info = forms.get(key, {})
            name = info.get("name") or ""
            lines.append(f"FORM {key + 1}" + (f" \"{name}\"" if name else "") + ":")
        else:
            lines.append("FIELDS AND BUTTONS OUTSIDE ANY <form>:" if groups.get(key) else "BUTTONS OUTSIDE ANY <form>:")
        lines.extend("  " + line for line in groups.get(key, []))
        lines.extend("  " + line for line in button_lines.get(key, []))
    if not fields:
        lines.append("NO FORM FIELDS ON THIS PAGE.")
    if link_lines:
        lines.append("LINKS:")
        lines.extend("  " + line for line in link_lines)
    return "\n".join(lines)


# ---------------------------------------------------------------- model contract

FORM_TOOL = {
    "name": "form_step",
    "description": "Choose the next step on the live page. Only numbers from the page list are valid.",
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["fill", "click", "done", "fail"]},
            "fields": {
                "type": "array",
                "description": "For fill: every field to set, by its number.",
                "items": {
                    "type": "object",
                    "properties": {"n": {"type": "integer"}, "value": {"type": "string"}},
                    "required": ["n", "value"],
                },
            },
            "press": {
                "type": "integer",
                "description": "For fill: the button that submits that form. For click: the link or button to click.",
            },
            "answer": {
                "type": "string",
                "description": "For done: the part the task asks for, copied exactly from one NEW TEXT line.",
            },
            "reason": {"type": "string", "description": "For fail: why the task cannot be done here."},
        },
        "required": ["action"],
    },
}

FORM_PROMPT = """You complete web forms for a user. You never write code.
You see the task and a numbered list of the real fields, buttons and links on the live page.
Answer by calling form_step exactly once.

action "fill": set fields and press one button.
- fields: every field the task gives a value for, by number. Use the exact option text for a select or radio,
  "on" or "off" for a checkbox, YYYY-MM-DD for a date field, plain digits for a number field.
- A required field the task does not mention: give a sensible value that fits the task
  (for a message box, write a sentence of the length the task asks for).
- Leave out fields the task does not need. Never fill a site search box unless the task says to search.
- press: the number of the button that submits that form (pick the one in the same FORM block).
action "click": the form is not on this page, or a button must open it first. press: the link or button that leads to it.
action "done": only after a submit, when the NEW TEXT shows the result the task asks for.
  answer: copy only the asked-for part, exactly as written in one NEW TEXT line.
action "fail": reason, when the task cannot be done here.

After a fill or click you see what changed: the new URL, any dialog text, and NEW TEXT (lines that were not on the
page before). If the NEW TEXT is a validation error, fill again to fix it. If the next page is another step
(a login, the next part of a multi-step form, a checkout step), handle it the same way.
Never answer with text that was already on the page before the submit."""


def first_message(description: str, start_url: str, schema_text: str) -> str:
    return f"TASK: {description}\nSTART URL: {start_url}\n\nPAGE NOW:\n{schema_text}"


# ---------------------------------------------------------------- page helpers


def _norm(text: str) -> str:
    folded = (text or "").replace(" ", " ")
    folded = re.sub(r"[‐-―−]", "-", folded)
    return " ".join(folded.split()).casefold()


def _lines(text: str) -> list[str]:
    out = []
    for raw in (text or "").splitlines():
        line = " ".join(raw.replace(" ", " ").split())
        if line:
            out.append(line)
    return out


def new_lines(before_texts: list[str], after: str) -> list[str]:
    """Visible lines of after that were on none of the earlier pages."""
    seen = set()
    for text in before_texts:
        seen.update(_norm(line) for line in _lines(text))
    out: list[str] = []
    kept = set()
    for line in _lines(after):
        key = _norm(line)
        if key in seen or key in kept:
            continue
        kept.add(key)
        out.append(line[:300])
    return out


_ERROR = re.compile(
    r"\b(?:error|invalid|is required|are required|required field|must be|must contain|please (?:enter|fill|provide|select|choose|correct)|"
    r"not valid|incorrect|failed|try again|cannot be (?:empty|blank)|too short|too long)\b",
    re.IGNORECASE,
)


def error_lines(lines: list[str]) -> list[str]:
    return [line for line in lines if _ERROR.search(line)]


async def _evaluate(page, source: str, arg=None, timeout: float = 5.0):
    try:
        if arg is None:
            return await asyncio.wait_for(page.evaluate(source), timeout)
        return await asyncio.wait_for(page.evaluate(source, arg), timeout)
    except Exception:  # noqa: BLE001 - a navigation can destroy the context mid-read
        return None


async def page_text(page) -> str:
    value = await _evaluate(page, _TEXT_JS)
    return value if isinstance(value, str) else ""


async def dismiss_consent(page) -> str:
    """Click a visible cookie or consent 'accept' button, if any. Widely used CMPs only."""
    value = await _evaluate(page, _CONSENT_JS, list(CONSENT_SELECTORS))
    if value:
        await asyncio.sleep(0.4)
    return value if isinstance(value, str) else ""


async def read_schema(page, terms: list[str]) -> dict:
    value = await _evaluate(page, SCHEMA_JS, {"terms": terms, "fieldsCap": _FIELDS_CAP, "linksCap": _LINKS_CAP})
    return value if isinstance(value, dict) else {"url": getattr(page, "url", ""), "title": "", "fields": [], "controls": [], "forms": []}


async def settle(page, before_url: str, before_text: str, dialogs: list[str], *, max_s: float = _SETTLE_MAX_S) -> str:
    """Wait until the page changed and then held still, or until max_s. Returns the last text read."""
    deadline = time.perf_counter() + max_s
    last = None
    stable = 0
    changed = False
    busy = re.compile(r"\b(?:loading|sending|submitting|processing|please wait)\b", re.IGNORECASE)
    while time.perf_counter() < deadline:
        await asyncio.sleep(0.15)
        url = getattr(page, "url", "")
        if url != before_url:
            try:
                await page.wait_for_load_state("domcontentloaded", timeout=_NAV_TIMEOUT_MS)
            except Exception:  # noqa: BLE001
                pass
        text = await page_text(page)
        if not changed and (url != before_url or (text and text != before_text) or dialogs):
            changed = True
        if not changed:
            continue
        if text == last and text:
            stable += 1
            fresh = new_lines([before_text], text)
            if stable >= 4 and not any(busy.search(line) for line in fresh[:5]):
                return text
        else:
            stable = 0
        last = text
    return last if last is not None else await page_text(page)


# ---------------------------------------------------------------- deterministic fill

_DATE_FORMATS = (
    "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d %B %Y", "%d %b %Y", "%B %d, %Y", "%b %d, %Y", "%B %d %Y", "%d.%m.%Y",
)


def iso_date(value: str) -> str:
    text = " ".join((value or "").replace(",", ", ").split()).replace(" ,", ",")
    text = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", text)
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return value


def match_option(options: list[str], wanted: str) -> int:
    """Index of the option the value names: exact, then folded, then contained either way. -1 if none."""
    if not options:
        return -1
    want = _norm(wanted)
    if not want:
        return -1
    for index, option in enumerate(options):
        if option == wanted:
            return index
    for index, option in enumerate(options):
        if _norm(option) == want:
            return index
    simple = re.sub(r"[^a-z0-9]+", "", want)
    for index, option in enumerate(options):
        if simple and re.sub(r"[^a-z0-9]+", "", _norm(option)) == simple:
            return index
    contains = [i for i, option in enumerate(options) if want in _norm(option)]
    if len(contains) == 1:
        return contains[0]
    inside = [i for i, option in enumerate(options) if _norm(option) and _norm(option) in want and len(_norm(option)) > 2]
    if inside:
        return max(inside, key=lambda i: len(options[i]))
    if contains:
        return min(contains, key=lambda i: len(options[i]))
    return -1


def _truthy(value: str) -> bool:
    return _norm(value) in {"on", "true", "yes", "checked", "1", "tick", "ticked", "check", "x", "agree", "selected"}


async def _set_text(locator, value: str, typ: str) -> str:
    """fill(), then read back; widgets that clear a filled value get typed keys instead."""
    if typ == "date":
        value = iso_date(value)
    try:
        await locator.fill(value, timeout=_ACTION_TIMEOUT_MS)
    except Exception:  # noqa: BLE001 - a masked or custom input can refuse fill
        pass
    current = await _read_value(locator)
    if _norm(current) == _norm(value):
        return ""
    try:
        await locator.click(timeout=_ACTION_TIMEOUT_MS)
        await locator.press("Control+A", timeout=_ACTION_TIMEOUT_MS)
        await locator.press("Delete", timeout=_ACTION_TIMEOUT_MS)
        await locator.press_sequentially(value, delay=15, timeout=_ACTION_TIMEOUT_MS * 3)
        await locator.press("Escape", timeout=_ACTION_TIMEOUT_MS)
    except Exception:  # noqa: BLE001
        pass
    current = await _read_value(locator)
    if _norm(current) == _norm(value) or (current and _norm(value) in _norm(current)):
        return ""
    return f"value reads back as {current!r}"


async def _read_value(locator) -> str:
    try:
        value = await locator.evaluate(
            "e => (e.value !== undefined && e.tagName !== 'DIV' && e.tagName !== 'SPAN') ? String(e.value) : (e.innerText || '')"
        )
        return value if isinstance(value, str) else ""
    except Exception:  # noqa: BLE001
        return ""


async def _wait_options(locator, wanted: str, max_s: float = 3.0) -> tuple[list[str], int]:
    """A dependent select fills its options late (a region after a country). Poll for the wanted one."""
    deadline = time.perf_counter() + max_s
    options: list[str] = []
    while True:
        try:
            options = await locator.evaluate("e => Array.from(e.options).map(o => (o.text || o.value).replace(/\\s+/g, ' ').trim())")
        except Exception:  # noqa: BLE001
            options = []
        index = match_option(options, wanted)
        if index >= 0 or time.perf_counter() >= deadline:
            return options, index
        await asyncio.sleep(0.25)


async def _set_select(locator, value: str) -> str:
    options, index = await _wait_options(locator, value)
    if index < 0:
        return f"no option matches {value!r}"
    try:
        await locator.select_option(index=index, timeout=_ACTION_TIMEOUT_MS)
    except Exception as exc:  # noqa: BLE001
        return f"select failed: {str(exc).splitlines()[0][:120]}"
    return ""


async def _click_choice(page, locator, want_on: bool) -> str:
    """Check or uncheck a checkbox or radio; a hidden styled input is set through its label."""
    async def state() -> bool | None:
        try:
            return bool(await locator.evaluate("e => e.checked !== undefined ? e.checked : e.getAttribute('aria-checked') === 'true'"))
        except Exception:  # noqa: BLE001
            return None

    if await state() == want_on:
        return ""
    attempts = (
        lambda: locator.check(timeout=_ACTION_TIMEOUT_MS) if want_on else locator.uncheck(timeout=_ACTION_TIMEOUT_MS),
        lambda: locator.evaluate("e => { const l = e.labels && e.labels[0]; (l || e).click(); }"),
        lambda: locator.click(timeout=_ACTION_TIMEOUT_MS, force=True),
    )
    for attempt in attempts:
        try:
            await attempt()
        except Exception:  # noqa: BLE001
            pass
        if await state() == want_on:
            return ""
    return "could not set the choice"


async def _set_combobox(page, locator, value: str) -> str:
    """A custom combobox: type, then click the matching option in the list it opens."""
    try:
        await locator.click(timeout=_ACTION_TIMEOUT_MS)
        try:
            await locator.fill(value, timeout=_ACTION_TIMEOUT_MS)
        except Exception:  # noqa: BLE001
            await page.keyboard.type(value, delay=15)
        await asyncio.sleep(0.5)
        options = page.locator("[role=option]:visible")
        count = await options.count()
        texts = [((await options.nth(i).inner_text()) or "").strip() for i in range(min(count, 50))]
        index = match_option(texts, value)
        if index >= 0:
            await options.nth(index).click(timeout=_ACTION_TIMEOUT_MS)
            return ""
        await page.keyboard.press("Enter")
        return ""
    except Exception as exc:  # noqa: BLE001
        return f"combobox failed: {str(exc).splitlines()[0][:120]}"


async def fill_fields(page, schema: dict, values: list[dict]) -> list[str]:
    """Set each numbered field. Returns one problem line per field that did not take its value."""
    by_n = {int(item["n"]): item for item in schema.get("fields") or []}
    problems: list[str] = []
    for entry in values or []:
        try:
            number = int(entry.get("n"))
        except (TypeError, ValueError, AttributeError):
            continue
        value = str(entry.get("value") if entry.get("value") is not None else "")
        item = by_n.get(number)
        if item is None:
            problems.append(f"[{number}] is not a field")
            continue
        typ = item.get("type", "text")
        problem = ""
        try:
            if item.get("kind") == "radio":
                index = match_option(item.get("options") or [], value)
                if index < 0:
                    problem = f"no option matches {value!r}"
                else:
                    target = page.locator(f'[data-cu-n="{number}"][data-cu-opt="{index}"]').first
                    problem = await _click_choice(page, target, True)
            else:
                target = page.locator(f'[data-cu-n="{number}"]').first
                if typ == "select":
                    problem = await _set_select(target, value)
                elif typ == "checkbox":
                    problem = await _click_choice(page, target, _truthy(value))
                elif typ == "combobox":
                    problem = await _set_combobox(page, target, value)
                elif typ == "file":
                    problem = "file fields are not filled"
                else:
                    problem = await _set_text(target, value, typ)
                    try:
                        await target.evaluate("e => { e.dispatchEvent(new Event('change', {bubbles: true})); e.blur && e.blur(); }")
                    except Exception:  # noqa: BLE001
                        pass
        except Exception as exc:  # noqa: BLE001 - one field must not stop the others
            problem = str(exc).splitlines()[0][:160]
        if problem:
            problems.append(f"[{number}] {item.get('label') or item.get('name')}: {problem}")
        if typ == "select" or item.get("kind") == "radio":
            # A select or radio can change which fields the form shows next.
            await asyncio.sleep(0.2)
    return problems


async def invalid_fields(page) -> list[str]:
    """Native constraint-validation messages: the browser blocks the submit and shows no page text."""
    value = await _evaluate(
        page,
        r"""() => Array.from(document.querySelectorAll('[data-cu-n]')).filter((e) => e.willValidate && !e.checkValidity())
          .slice(0, 8).map((e) => '[' + e.getAttribute('data-cu-n') + '] ' + (e.validationMessage || 'invalid'))""",
    )
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


async def press_control(page, number: int) -> str:
    target = page.locator(f'[data-cu-n="{number}"]').first
    try:
        if await target.count() == 0:
            return f"[{number}] is not on the page"
    except Exception:  # noqa: BLE001
        return f"[{number}] is not on the page"
    try:
        await target.click(timeout=_ACTION_TIMEOUT_MS)
        return ""
    except Exception:  # noqa: BLE001 - an overlay over the button; a DOM click still submits
        pass
    try:
        await target.evaluate("e => e.click()")
        return ""
    except Exception as exc:  # noqa: BLE001
        return f"click failed: {str(exc).splitlines()[0][:160]}"


def default_submit(schema: dict, values: list[dict]) -> int | None:
    """The submit button of the form that holds most of the filled fields."""
    by_n = {int(item["n"]): item for item in schema.get("fields") or []}
    counts: dict[int, int] = {}
    for entry in values or []:
        try:
            item = by_n.get(int(entry.get("n")))
        except (TypeError, ValueError, AttributeError):
            item = None
        if item is not None:
            counts[int(item.get("form", -1))] = counts.get(int(item.get("form", -1)), 0) + 1
    if not counts:
        return None
    form = max(counts, key=counts.get)
    for control in schema.get("controls") or []:
        if control.get("kind") == "button" and int(control.get("form", -2)) == form and control.get("submits"):
            return int(control["n"])
    for control in schema.get("controls") or []:
        if control.get("kind") == "button" and int(control.get("form", -2)) == form:
            return int(control["n"])
    return None


# ---------------------------------------------------------------- end check


def check_answer(answer: str, live_text: str, earlier_texts: list[str], fresh: list[str]) -> tuple[bool, str]:
    """The honest end check. No markers: only the pages this run saw.

    PASS needs a non-empty answer that is on the live page, sits in a line that
    is new since the submit, and was on none of the pages seen before it.
    """
    want = _norm(answer)
    if not want:
        return False, "empty answer"
    if want not in _norm(live_text):
        return False, "the answer is not on the live page"
    for text in earlier_texts:
        if want in _norm(text):
            return False, "the answer was already on the page before the submit"
    if not any(want in _norm(line) or _norm(line) in want for line in fresh):
        return False, "the answer is not in the text that appeared after the submit"
    return True, "the answer appeared after the submit"


# ---------------------------------------------------------------- the strategy


def _tool_input(response: dict) -> dict | None:
    for block in response.get("content") or []:
        if block.get("type") == "tool_use" and block.get("name") == FORM_TOOL["name"]:
            data = block.get("input")
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except ValueError:
                    data = None
            return data if isinstance(data, dict) else None
    return None


def _tool_id(response: dict) -> str:
    for block in response.get("content") or []:
        if block.get("type") == "tool_use":
            return str(block.get("id") or "")
    return ""


def _outcome_text(*, url_before: str, url_after: str, dialogs: list[str], fresh: list[str], problems: list[str],
                  invalid: list[str], schema_text: str, pressed: bool) -> str:
    parts = []
    if problems:
        parts.append("FILL PROBLEMS:\n" + "\n".join(f"- {line}" for line in problems))
    if invalid:
        parts.append("THE BROWSER BLOCKED THE SUBMIT. INVALID FIELDS:\n" + "\n".join(f"- {line}" for line in invalid))
    if pressed:
        parts.append("URL: " + (f"changed to {url_after}" if url_after != url_before else f"unchanged ({url_after})"))
    if dialogs:
        parts.append("DIALOG TEXT (accepted):\n" + "\n".join(f"- {line}" for line in dialogs))
    if fresh:
        shown = fresh[:_NEW_LINES_CAP]
        more = f"\n(... {len(fresh) - len(shown)} more new lines)" if len(fresh) > len(shown) else ""
        parts.append("NEW TEXT (not on the page before):\n" + "\n".join(f"{i + 1}. {line}" for i, line in enumerate(shown)) + more)
    elif pressed:
        parts.append("NEW TEXT: none. Nothing visible changed.")
    parts.append("PAGE NOW:\n" + schema_text)
    return "\n\n".join(parts)


async def run_form_strategy(page, model, description: str, start_url: str) -> FormOutcome:
    """Observe, ask for data, fill, submit, read what is new, check. FAIL hands back to the generic path."""
    outcome = FormOutcome(claimed=True)
    started = time.perf_counter()
    terms = task_terms(description)
    dialogs: list[str] = []

    def on_dialog(dialog) -> None:
        dialogs.append(" ".join((dialog.message or "").split())[:300])
        asyncio.ensure_future(_accept(dialog))

    page.on("dialog", on_dialog)
    try:
        tool_started = time.perf_counter()
        try:
            await page.goto(start_url, wait_until="domcontentloaded", timeout=_NAV_TIMEOUT_MS)
        except Exception as exc:  # noqa: BLE001
            outcome.reason = f"start page did not load: {str(exc).splitlines()[0][:120]}"
            return outcome
        await _wait_for_fields(page)
        await dismiss_consent(page)
        schema = await read_schema(page, terms)
        outcome.tool_ms += (time.perf_counter() - tool_started) * 1000
        if not schema.get("fields") and not schema.get("controls"):
            outcome.reason = "no fields or controls on the start page"
            return outcome
        # Every page text seen before the latest press. The answer may be on none of them.
        seen: list[str] = [await page_text(page)]
        schema_text = render_schema(schema, terms)
        messages: list[dict] = [{"role": "user", "content": first_message(description, start_url, schema_text)}]
        fills = 0
        submitted = False
        fresh: list[str] = []
        while outcome.model_calls < MAX_MODEL_CALLS and time.perf_counter() - started < BUDGET_S:
            response, model_ms = await model.create_message(
                messages, [FORM_TOOL], system=FORM_PROMPT, tool_choice=_tool_choice(model)
            )
            outcome.model_calls += 1
            outcome.model_ms += model_ms
            usage = response.get("usage") or {}
            in_tokens = int(usage.get("input_tokens") or 0)
            out_tokens = int(usage.get("output_tokens") or 0)
            outcome.input_tokens += in_tokens
            outcome.output_tokens += out_tokens
            outcome.cached_tokens += int(usage.get("cached_tokens") or 0)
            outcome.cache_write_30m_tokens += int(usage.get("cache_write_30m_tokens") or 0)
            outcome.cache_write_12h_tokens += int(usage.get("cache_write_12h_tokens") or 0)
            action = _tool_input(response)
            step = FormStep(action=action or {}, result="", page_url=getattr(page, "url", ""), model_ms=model_ms,
                            input_tokens=in_tokens, output_tokens=out_tokens)
            outcome.steps.append(step)
            if action is None:
                outcome.reason = "the model sent no form_step"
                return outcome
            kind = str(action.get("action") or "")
            if kind == "fail":
                outcome.reason = f"model gave up: {str(action.get('reason') or '')[:200]}"
                return outcome
            if kind == "done":
                answer = " ".join(str(action.get("answer") or "").split())
                live = await page_text(page)
                if not submitted:
                    outcome.reason = "done before any submit"
                    return outcome
                ok, why = check_answer(answer, live, seen, fresh)
                outcome.answer = answer
                outcome.final_url = getattr(page, "url", "")
                outcome.page_text = live
                outcome.passed = ok
                outcome.reason = why
                step.result = why
                return outcome
            if kind not in ("fill", "click"):
                outcome.reason = f"unknown action {kind!r}"
                return outcome
            tool_started = time.perf_counter()
            problems: list[str] = []
            invalid: list[str] = []
            values = action.get("fields") if isinstance(action.get("fields"), list) else []
            press = action.get("press")
            try:
                press = int(press) if press is not None else None
            except (TypeError, ValueError):
                press = None
            if kind == "fill":
                fills += 1
                if fills > MAX_FILLS:
                    outcome.reason = "too many fill attempts"
                    return outcome
                problems = await fill_fields(page, schema, values)
                if press is None:
                    press = default_submit(schema, values)
            before_url = getattr(page, "url", "")
            before_text = await page_text(page)
            dialogs.clear()
            pressed = False
            if press is not None:
                if kind == "fill":
                    invalid = await invalid_fields(page)
                problem = await press_control(page, press)
                if problem:
                    problems.append(problem)
                else:
                    pressed = True
            if pressed:
                after = await settle(page, before_url, before_text, dialogs)
                await dismiss_consent(page)
                after = await page_text(page) or after
            else:
                after = before_text
            if pressed:
                seen.append(before_text)
                # Lines new since this press, and not on any page seen before it.
                fresh = new_lines(seen, after)
                submitted = submitted or kind == "fill"
            else:
                fresh = []
            await _wait_for_fields(page, max_s=1.0)
            schema = await read_schema(page, terms)
            schema_text = render_schema(schema, terms)
            text = _outcome_text(
                url_before=before_url,
                url_after=getattr(page, "url", ""),
                dialogs=list(dialogs),
                fresh=fresh,
                problems=problems,
                invalid=invalid,
                schema_text=schema_text,
                pressed=pressed,
            )
            step.result = text
            step.page_url = getattr(page, "url", "")
            step.tool_ms = (time.perf_counter() - tool_started) * 1000
            outcome.tool_ms += step.tool_ms
            tool_id = _tool_id(response) or f"form_step_{outcome.model_calls}"
            messages.append({"role": "assistant", "content": [
                {"type": "tool_use", "id": tool_id, "name": FORM_TOOL["name"], "input": action}
            ]})
            messages.append({"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": tool_id, "content": text}
            ]})
        outcome.reason = outcome.reason or "model-call or time budget used up"
        return outcome
    finally:
        try:
            page.remove_listener("dialog", on_dialog)
        except Exception:  # noqa: BLE001
            pass


async def _accept(dialog) -> None:
    try:
        await dialog.accept()
    except Exception:  # noqa: BLE001
        pass


async def _wait_for_fields(page, max_s: float = 2.5) -> None:
    """A client-rendered page draws its form after DOMContentLoaded. Wait briefly for a field or a settle."""
    deadline = time.perf_counter() + max_s
    last = -1
    while time.perf_counter() < deadline:
        count = await _evaluate(page, "() => document.querySelectorAll('input:not([type=hidden]),select,textarea,button').length")
        count = int(count) if isinstance(count, (int, float)) else 0
        if count > 0 and count == last:
            return
        last = count
        await asyncio.sleep(0.25)


def _tool_choice(model):
    """Force the one tool. OpenAI takes 'required'; the Claude client takes no tool_choice here."""
    return "required" if model.__class__.__name__ == "OpenAIClient" else None


# ---------------------------------------------------------------- harness glue


async def run_for_harness(harness, task_description: str, start_url: str) -> FormOutcome | None:
    """None when the strategy is off or does not claim the task. The harness logs the steps."""
    if not strategy_enabled() or not claims(task_description):
        return None
    client = harness.mcp_client
    page = getattr(client, "_page", None)
    if page is None:
        return None
    try:
        outcome = await run_form_strategy(page, harness.anthropic, task_description, start_url)
    except Exception as exc:  # noqa: BLE001 - the generic path still runs
        from bench.openai_spend import PriceUnknown

        if isinstance(exc, PriceUnknown):
            raise
        outcome = FormOutcome(claimed=True, reason=f"strategy error: {str(exc).splitlines()[0][:200]}")
    if not outcome.passed:
        # Hand back a blank page, as the generic path would have had.
        try:
            await page.goto("about:blank", timeout=_NAV_TIMEOUT_MS)
        except Exception:  # noqa: BLE001
            pass
    return outcome
