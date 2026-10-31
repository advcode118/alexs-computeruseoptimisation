"""Code pass/fail checks. A model is not the judge."""

from __future__ import annotations

from loop.browser import locate


def evaluate(page, check: dict) -> tuple[bool, str]:
    kind = check.get("kind")
    if kind == "dom":
        return _dom(page, check)
    if kind == "url":
        return _url(page, check)
    if kind == "fields":
        return _fields(page, check)
    return False, "unknown check"


def _wanted(check: dict, one: str, many: str) -> list[str]:
    texts = []
    if one in check:
        texts.append(str(check[one]))
    extra = check.get(many) or []
    if isinstance(extra, list):
        texts.extend(str(item) for item in extra)
    return texts


def _dom(page, check: dict) -> tuple[bool, str]:
    selector = str(check.get("selector") or "body")
    try:
        text = page.locator(selector).inner_text(timeout=2000)
    except Exception:
        return False, f"dom {selector} unreadable"
    missing = [item for item in _wanted(check, "text", "texts") if item not in text]
    if missing:
        return False, f"dom {selector} missing {missing!r}"
    return True, f"dom {selector} matched"


def _url(page, check: dict) -> tuple[bool, str]:
    missing = [item for item in _wanted(check, "contains", "contains_all") if item not in page.url]
    if missing:
        return False, f"url missing {missing!r}"
    return True, "url matched"


def _fields(page, check: dict) -> tuple[bool, str]:
    missing = []
    for field in check.get("fields") or []:
        name = str(field["name"])
        role = str(field.get("role") or "textbox")
        expected = str(field["value"])
        ref = locate(page, role, name)
        if ref is None:
            missing.append(name)
            continue
        value = page.locator(f'[data-cu-ref="{ref}"]').input_value()
        if value != expected:
            missing.append(name)
    if missing:
        return False, f"fields mismatch {missing!r}"
    return True, "fields matched"
