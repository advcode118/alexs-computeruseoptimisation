"""Offline coverage for the helpers a generated script can call.

No browser, no network, and no API key. The page is a fake. The claim
function is executed by Node as page JavaScript, not in Chrome.
"""

from __future__ import annotations

import asyncio
import json

from bench.arms import prompt_for
from bench.script_cache import PATCH_PROMPT
from bench.script_first import (
    ScriptFirstClient,
    parse_task_script,
    repair_request,
    run_on_page,
)
from bench.script_helpers import (
    parse_helper_call,
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


def test_click_fill_and_press_use_the_one_matching_control():
    page = _Page(
        {
            ("role:link", "Go"): 0,
            ("role:button", "Go"): 1,
            ("role:textbox", "Query"): 1,
            ("label", "Query"): 1,
        }
    )
    script = """
    page.goto("https://example.com/start");
    cu.fill("Query", "maps");
    cu.press("Query", "Enter");
    cu.click("Go");
    """
    text = asyncio.run(run_on_page(page, script))
    assert page.log[0] == ("goto", "https://example.com/start", "domcontentloaded")
    assert page.log[1] == ("fill", "role:textbox", "Query", "maps", _ACTION_TIMEOUT_MS)
    assert page.log[2] == ("press", "role:textbox", "Query", "Enter", _ACTION_TIMEOUT_MS)
    assert page.log[3] == ("click", "role:button", "Go", _ACTION_TIMEOUT_MS)
    assert "label" not in [item[1] for item in page.log if item[0] == "fill"]
    payload = json.loads(text.splitlines()[0])
    assert payload["ok"] is True
    assert payload["url"] == "https://example.com/start"
    assert payload["steps"] == 4


def test_an_ambiguous_name_does_not_fall_through_to_another_role():
    page = _Page({("role:link", "Go"): 2, ("role:button", "Go"): 1, ("text", "Go"): 1})
    text = asyncio.run(run_on_page(page, 'cu.click("Go")'))
    payload = json.loads(text.splitlines()[0])
    assert payload["ok"] is False
    assert payload["steps"] == 0
    assert "2 matches for link named 'Go'" in payload["error"]
    assert [item[0] for item in page.log] == ["evaluate"]
    assert "canonical" in page.log[-1][1]
    assert not any(item[0] == "click" for item in page.log)


def test_click_uses_exact_text_and_fill_uses_a_placeholder():
    page = _Page(
        {
            ("role:link", "Open"): 0,
            ("role:button", "Open"): 0,
            ("role:tab", "Open"): 0,
            ("role:menuitem", "Open"): 0,
            ("role:checkbox", "Open"): 0,
            ("role:radio", "Open"): 0,
            ("text", "Open"): 1,
            ("role:textbox", "Notes"): 0,
            ("role:searchbox", "Notes"): 0,
            ("role:combobox", "Notes"): 0,
            ("label", "Notes"): 0,
            ("placeholder", "Notes"): 1,
        }
    )
    text = asyncio.run(run_on_page(page, 'cu.click("Open"); cu.fill("Notes", "kept")'))
    assert ("click", "text", "Open", _ACTION_TIMEOUT_MS) in page.log
    assert ("fill", "placeholder", "Notes", "kept", _ACTION_TIMEOUT_MS) in page.log
    assert json.loads(text.splitlines()[0])["ok"] is True


def test_fill_uses_the_label_when_no_field_role_matches():
    page = _Page(
        {
            ("role:textbox", "Query"): 0,
            ("role:searchbox", "Query"): 0,
            ("role:combobox", "Query"): 0,
            ("label", "Query"): 1,
        }
    )
    text = asyncio.run(run_on_page(page, 'page.goto("https://example.com/form"); cu.fill("Query", "maps")'))
    assert ("fill", "label", "Query", "maps", _ACTION_TIMEOUT_MS) in page.log
    assert json.loads(text.splitlines()[0])["ok"] is True


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
    assert "does not settle or snapshot" in prompt
    assert "one control" in tool or "accessible name" in tool
