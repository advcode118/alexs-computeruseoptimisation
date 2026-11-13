"""Offline coverage for the helpers a generated script can call.

No browser, no network, and no API key. The page is a fake. The claim
function is executed by Node as page JavaScript, not in Chrome.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import subprocess

from bench.arms import prompt_for
from bench.script_cache import PATCH_PROMPT
from bench.script_first import (
    PageEvidence,
    ScriptFirstClient,
    check_returned_evidence,
    parse_task_script,
    repair_request,
    run_on_mcp,
    run_on_page,
)
from bench.script_helpers import (
    CLAIM_JS,
    parse_helper_call,
    shape_claim,
    wrap_evaluate,
)
from proxy.script import ScriptError
from tests.test_prompt_audit import FORBIDDEN

_ACTION_TIMEOUT_MS = 5000


class _Box:
    def __init__(self, page, kind: str, name: str, count: int):
        self.page = page
        self.kind = kind
        self.name = name
        self._count = count

    async def count(self):
        self.page.counts.append((self.kind, self.name))
        return self._count

    async def click(self, **kwargs):
        self.page.log.append(("click", self.kind, self.name, kwargs.get("timeout")))

    async def fill(self, value, **kwargs):
        self.page.log.append(("fill", self.kind, self.name, value, kwargs.get("timeout")))

    async def press(self, value, **kwargs):
        self.page.log.append(("press", self.kind, self.name, value, kwargs.get("timeout")))


class _Page:
    def __init__(self, counts: dict):
        self.counts = []
        self.available = counts
        self.log = []
        self.url = "about:blank"
        self.title = "Example"

    def _box(self, kind: str, name: str, exact):
        assert exact is True
        return _Box(self, kind, name, self.available.get((kind, name), 0))

    def get_by_role(self, role, name=None, exact=None):
        return self._box(f"role:{role}", name or "", exact)

    def get_by_text(self, name, exact=None):
        return self._box("text", name, exact)

    def get_by_label(self, name, exact=None):
        return self._box("label", name, exact)

    def get_by_placeholder(self, name, exact=None):
        return self._box("placeholder", name, exact)

    async def goto(self, url, **kwargs):
        self.url = url
        self.log.append(("goto", url, kwargs.get("wait_until")))

    async def title(self):
        return self.title

    async def evaluate(self, source):
        self.log.append(("evaluate", source))
        if "const cu" in source and "cu.claim" in source:
            return {
                "url": self.url,
                "title": self.title,
                "h1": "Visible heading",
                "key_text": "Visible heading",
                "values": ["Visible heading"],
                "answer": "Visible heading",
            }
        return {"url": self.url, "title": self.title, "h1": "", "text": "Visible heading", "canonical": "", "controls": []}


def test_parser_accepts_name_helpers_and_rejects_a_claim_statement():
    script = """
    await page.goto("https://example.com/start");
    CU.Click("Go");
    cu.fill("Query", "maps");
    cu.press("Query", "Enter");
    page.evaluate(() => cu.claim({answer: "", key_text: "", values: []}));
    """
    steps = parse_task_script(script)
    assert [step.kind for step in steps] == ["goto", "helper", "helper", "helper", "evaluate"]
    assert steps[1].helper.op == "click"
    assert steps[1].helper.target == "Go"
    quoted = parse_helper_call('cu.fill("a \\"b\\"", "c, d")', 3)
    assert quoted.target == 'a "b"'
    assert quoted.value == "c, d"
    page = _Page({})
    for source in (
        'cu.click("")',
        'cu.click("Go", "extra")',
        'cu.fill("Query")',
        'cu.press("Query", "")',
        "cu.wait(1)",
        'cu.claim({answer: ""})',
        'cu.click("Go").click()',
    ):
        try:
            asyncio.run(run_on_page(page, source))
        except ScriptError as exc:
            assert "line 1" in str(exc)
        else:
            raise AssertionError(source)
        assert page.log == []


# Name matching, ties, and fallbacks run on a real page in tests/test_script_resolve.py.


def test_a_missing_control_is_recorded_and_the_page_is_still_read():
    page = _Page({})
    text = asyncio.run(run_on_page(page, 'page.goto("https://example.com/stay"); cu.click("Missing")'))
    payload = json.loads(text.splitlines()[0])
    assert payload["ok"] is False
    assert payload["steps"] == 1
    assert payload["url"] == "https://example.com/stay"
    assert "no control named 'Missing'" in payload["error"]
    assert page.log[-1][0] == "evaluate"
    assert "canonical" in page.log[-1][1]


def test_claim_inside_evaluate_is_wrapped_and_still_judged():
    plain = "() => document.title"
    assert wrap_evaluate(plain) == plain
    page = _Page({})
    script = """
    page.goto("https://example.com/item");
    page.evaluate(() => cu.claim({answer: "Visible heading", key_text: "Visible heading", values: ["Visible heading"]}));
    """
    text = asyncio.run(run_on_page(page, script))
    wrapped = next(item[1] for item in page.log if item[0] == "evaluate" and "const cu" in item[1])
    assert "cu.claim" in wrapped
    assert wrapped.strip().startswith("() => {")
    payload = json.loads(text.splitlines()[0])
    assert payload["claimed"]["answer"] == "Visible heading"
    assert payload["claimed"]["key_text"] == "Visible heading"
    verdict = check_returned_evidence(
        {"host": "example.com", "url_contains": "/item"},
        PageEvidence(
            url="https://example.com/item",
            title="Example",
            h1="Visible heading",
            text="Visible heading is on the page",
        ),
        payload["claimed"],
    )
    assert verdict.verdict == "PASS"
    missing = shape_claim(
        {"answer": True, "key_text": "not on this page"},
        url="https://example.com/item",
        title="Example",
        h1="Visible heading",
    )
    assert missing["rejected"] is True
    assert missing["answer"] == ""
    failed = check_returned_evidence(
        {"host": "example.com", "url_contains": "/item"},
        PageEvidence(url="https://example.com/item", title="Example", text="Visible heading"),
        missing,
    )
    assert failed.verdict == "FAIL"
    assert failed.reason == "returned value is not text"


def test_claim_javascript_matches_the_python_shape():
    node = shutil.which("node")
    assert node
    cases = [
        {"url": "https://example.com/item", "title": "Example", "h1": "Visible heading", "partial": None},
        {
            "url": "https://example.com/item",
            "title": "Example",
            "h1": "From the page",
            "partial": {"h1": " From the script ", "answer": "  kept  ", "key_text": "", "values": ["  a \n b  ", 2]},
        },
        {
            "url": "https://example.com/item",
            "title": "Example",
            "h1": "H",
            "partial": {"answer": True, "values": ["ok", False]},
        },
        {
            "url": "https://example.com/item",
            "title": "Example",
            "h1": "H",
            "partial": ["not", "an", "object"],
        },
        {
            "url": "https://example.com/item",
            "title": "Example",
            "h1": "H",
            "partial": {"values": ["x"] * 21},
        },
        {
            "url": "https://example.com/item",
            "title": "Example",
            "h1": "H",
            "partial": {"values": ["y" * 401]},
        },
    ]
    program = (
        "const cases = JSON.parse(process.argv[1]);\n"
        "const source = process.argv[2];\n"
        "const out = cases.map((item) => {\n"
        "  const location = { href: item.url };\n"
        "  const document = { title: item.title, querySelector(sel) {\n"
        "    if (sel === 'h1' && item.h1) return { innerText: item.h1, textContent: item.h1 };\n"
        "    return null;\n"
        "  } };\n"
        "  const fn = new Function('location', 'document', 'partial', source + '\\nreturn cu.claim(partial);');\n"
        "  return fn(location, document, item.partial);\n"
        "});\n"
        "process.stdout.write(JSON.stringify(out));\n"
    )
    completed = subprocess.run(
        [node, "-e", program, json.dumps(cases), CLAIM_JS],
        check=True,
        capture_output=True,
        text=True,
    )
    found = json.loads(completed.stdout)
    expect = [shape_claim(item["partial"], url=item["url"], title=item["title"], h1=item["h1"]) for item in cases]
    assert found == expect
    assert found[2]["rejected"] is True
    assert found[5]["values"] == ["y" * 400]


def test_mcp_evaluate_receives_the_claim_helper_and_refuses_a_click():
    calls = []

    async def call_tool(name, arguments):
        calls.append((name, arguments))
        if name == "browser_navigate":
            return f"- Page URL: {arguments['url']}\n"
        if arguments.get("function") == "() => location.href":
            return "https://example.com/item"
        return "null"

    script = """
    page.goto("https://example.com/item");
    page.evaluate(() => cu.claim({answer: "Visible heading"}));
    """
    asyncio.run(run_on_mcp(call_tool, script))
    assert calls[0][0] == "browser_navigate"
    assert calls[1][0] == "browser_evaluate"
    assert "const cu" in calls[1][1]["function"]
    assert calls[1][1]["function"].strip().startswith("() => {")
    calls.clear()
    try:
        asyncio.run(run_on_mcp(call_tool, 'cu.click("Go")'))
    except ScriptError as exc:
        assert "page.evaluate" in str(exc)
    else:
        raise AssertionError("a helper click is not an MCP evaluate")
    assert calls == []


def test_prompts_name_the_helpers_and_omit_judge_fields():
    prompt = prompt_for("script_first")
    tool = ScriptFirstClient().tools_for_claude()[0]["description"]
    repair = repair_request("https://example.com/start", "the page is denied (search)")
    for text in (prompt, tool, PATCH_PROMPT, repair):
        assert "cu.click" in text
        assert "cu.claim" in text
        for secret in FORBIDDEN:
            assert secret not in text
    assert "visible name" in prompt
    assert "waits for each control" in prompt
    assert "one control" in tool or "accessible name" in tool
