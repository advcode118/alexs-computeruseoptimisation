"""Code pass/fail checks. A model is not the judge."""

from __future__ import annotations


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
    text = ""
    # One browser round trip. The page waits until the node has text, so a
    # navigation that has only committed does not need a second Python poll.
    for _ in range(3):
        try:
            found = page.evaluate(
                """({selector, limit}) => new Promise((resolve) => {
                  const start = performance.now();
                  const tick = () => {
                    const node = document.querySelector(selector);
                    const value = node ? (node.textContent || node.innerText || "") : "";
                    if (value) { resolve(value); return; }
                    if (performance.now() - start >= limit) { resolve(""); return; }
                    setTimeout(tick, 0);
                  };
                  tick();
                })""",
                {"selector": selector, "limit": 200},
            )
        except Exception:
            found = ""
        if found:
            text = str(found)
            break
    if not text:
        return False, f"dom {selector} unreadable"
    missing = [item for item in _wanted(check, "text", "texts") if item not in text]
    if missing:
        return False, f"dom {selector} missing {missing!r}"
    return True, f"dom {selector} matched"


def _fields(page, check: dict) -> tuple[bool, str]:
    wanted = [
        {"name": str(field["name"]), "value": str(field["value"])}
        for field in check.get("fields") or []
    ]
    try:
        missing = page.evaluate(
            """(wanted) => {
              const norm = (value) => (value || "").toLowerCase().replace(/\\s+/g, " ").trim().replace(/:$/, "");
              const nameOf = (node) => {
                let name = node.getAttribute("aria-label") || "";
                if (!name && node.labels && node.labels.length) name = node.labels[0].innerText || "";
                return norm(name);
              };
              const fields = [...document.querySelectorAll("input, textarea, select")];
              const missing = [];
              for (const item of wanted) {
                const name = norm(item.name);
                const node = fields.find((field) => nameOf(field) === name);
                if (!node || String(node.value || "") !== item.value) missing.push(item.name);
              }
              return missing;
            }""",
            wanted,
        )
    except Exception:
        return False, "fields unreadable"
    if missing:
        return False, f"fields mismatch {missing!r}"
    return True, "fields matched"


def _url(page, check: dict) -> tuple[bool, str]:
    missing = [item for item in _wanted(check, "contains", "contains_all") if item not in page.url]
    if missing:
        return False, f"url missing {missing!r}"
    return True, "url matched"
