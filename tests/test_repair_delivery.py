"""Offline repair delivery and probe tracing; no browser or API calls."""

import asyncio
import json
import shutil
import subprocess

import pytest

from bench.harness import BenchmarkHarness, MAX_SNAPSHOT_CHARS, cap_messages_for_model, message_payload
from bench.probe import run_claude_arm
from bench.script_first import format_run_result, model_visible_script_result, ScriptFirstClient


def tool(name="run_script", **arguments):
    return {"type": "tool_use", "id": "call", "name": name, "input": arguments}


class Model:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.requests = []

    async def create_message(self, messages, tools, **kwargs):
        self.requests.append((messages, tools, kwargs))
        return {"content": next(self.replies), "stop_reason": "end_turn"}, 0.0


class Client:
    def tools_for_claude(self):
        return []

    async def call_tool(self, name, arguments):
        assert name == "run_script"
        return format_run_result(
            ok=False, url="https://example.org/page", title="Example", step_count=1,
            error="fixture failure",
        ), 0.0


@pytest.mark.parametrize("reply,kind", [
    ([tool(code="second")], "script"),
    ([{"type": "text", "text": "I am done"}], "prose"),
    ([{"type": "text", "text": "TASK_FAILED: unavailable"}], "task_failed"),
    ([], "none"),
])
def test_probe_traces_actual_repair_reply(monkeypatch, tmp_path, reply, kind):
    model = Model([[tool(code="first")], reply])

    async def setup(self):
        self.anthropic = model
        self.mcp_client = Client()

    async def noop(*args):
        pass

    monkeypatch.setattr(BenchmarkHarness, "setup", setup)
    monkeypatch.setattr(BenchmarkHarness, "teardown", noop)
    monkeypatch.setattr(BenchmarkHarness, "_read_shared_page", noop)
    row = asyncio.run(run_claude_arm(
        "script_first", {"id": "fixture", "description": "Read page", "start_url": "https://example.org"},
        api_key="offline", headless=True, runs_dir=tmp_path,
    ))
    assert row["final_url"] == "https://example.org/page"
    assert row["final_title"] == "Example"
    assert row["scripts"] == (["first", "second"] if kind == "script" else ["first"])
    assert row["repair_sent"] is True
    assert row["repair_reply"] == kind
    assert "tool_choice" not in model.requests[0][2]
    assert model.requests[1][2]["tool_choice"] == {"type": "any"}


def test_long_result_preserves_repair_and_json():
    original = format_run_result(
        ok=False, url="https://example.org", step_count=1,
        text=('quoted " slash \\ newline\n    ' * 1000), title="Example",
    ) + "\nEND_STATE_FAILED: repair now\nEND_STATE_FAILED: another instruction"
    visible = model_visible_script_result(original)
    assert len(visible) <= MAX_SNAPSHOT_CHARS - 300
    lines = visible.splitlines()
    assert lines[:2] == ["END_STATE_FAILED: repair now", "END_STATE_FAILED: another instruction"]
    payload = json.loads(lines[2])
    assert payload["text"].endswith("[text truncated]")
    assert payload["title"] == "Example"
    assert lines[3].startswith("Ran goto")
    messages = [{"role": "user", "content": [{"type": "tool_result", "content": original}]}]
    guarded = cap_messages_for_model(messages, script_first=True)[0]["content"][0]["content"]
    assert len(guarded) <= MAX_SNAPSHOT_CHARS
    assert json.loads(guarded.splitlines()[2])["text"].endswith("[text truncated]")
    assert "[snapshot truncated]" in cap_messages_for_model(messages)[0]["content"][0]["content"]


@pytest.mark.parametrize("provider,choice", [("anthropic", {"type": "any"}), ("openai", "required")])
def test_task_failed_and_repair_only_choice(monkeypatch, tmp_path, provider, choice):
    model = Model([[tool(code="first")], [tool("task_failed", reason="Unavailable")]])
    harness = BenchmarkHarness(api_key="offline", arm="script_first", runs_dir=tmp_path)
    harness.provider = provider
    harness.anthropic = model
    harness.mcp_client = Client()

    async def noop(*args):
        pass

    monkeypatch.setattr(harness, "_read_shared_page", noop)
    result = asyncio.run(harness.run_task("fixture", "Read page", "https://example.org"))
    assert result.success is False
    assert result.success_reason == "Task failed: Unavailable"
    assert result.repair_reply == "task_failed"
    assert len(result.steps) == 1
    assert "tool_choice" not in model.requests[0][2]
    assert model.requests[1][2]["tool_choice"] == choice


def test_provider_payload_tool_choice():
    from bench.openai_client import responses_payload

    args = ("gpt-6.1-sol", [], ScriptFirstClient().tools_for_claude(), "system", 100, "medium")
    assert "tool_choice" not in responses_payload(*args)
    assert responses_payload(*args, tool_choice="required")["tool_choice"] == "required"
    args = ("claude-sonnet-5-5", [], ScriptFirstClient().tools_for_claude(), "system", 100)
    assert "tool_choice" not in message_payload(*args, cache_prefix=True)
    assert message_payload(*args, cache_prefix=True, tool_choice={"type": "any"})["tool_choice"] == {"type": "any"}


def test_tool_choice_is_cleared_after_repair(monkeypatch, tmp_path):
    model = Model([[tool(code="first")], [tool(code="repair")], [tool("task_failed", reason="Stop")]])
    harness = BenchmarkHarness(api_key="offline", arm="script_first", runs_dir=tmp_path)
    harness.anthropic = model

    class MovingClient(Client):
        calls = 0

        async def call_tool(self, name, arguments):
            self.calls += 1
            return format_run_result(ok=False, url=f"https://example.org/{self.calls}", step_count=1), 0

    harness.mcp_client = MovingClient()

    async def noop(*args):
        pass

    monkeypatch.setattr(harness, "_read_shared_page", noop)
    asyncio.run(harness.run_task("fixture", "Read page", "https://example.org"))
    # A second FAIL on a new page earns another grounded repair, so tool_choice stays required.
    assert [request[2].get("tool_choice") for request in model.requests] == [None, {"type": "any"}, {"type": "any"}]


def test_oversized_metadata_fails_closed():
    raw = format_run_result(ok=False, url="https://example.org", step_count=1, title="x" * 9000)
    with pytest.raises(ValueError, match="refusing to cut JSON"):
        model_visible_script_result(raw)


def test_failed_hints_take_priority_over_text():
    links = [[f"Link {i}", f"https://example.org/item/{i}"] for i in range(50)]
    controls = [{"role": "button", "name": f"Action {i}"} for i in range(40)]
    raw = format_run_result(
        ok=True, url="https://example.org", step_count=1, text="page text " * 1000,
        links=links, controls=controls, selector_text="JUDGE-ONLY",
    )
    visible = model_visible_script_result(raw + "\nEND_STATE_FAILED: no returned answer", failed=True)
    assert visible.startswith("END_STATE_FAILED:")
    assert len(visible) <= MAX_SNAPSHOT_CHARS - 300
    payload = json.loads(visible.splitlines()[1])
    assert payload["links"] == links[:40]
    assert payload["controls"] == controls[:30]
    assert payload["text"].endswith("[text truncated]")
    assert "JUDGE-ONLY" not in visible
    # No hints on PASS/UNKNOWN, even when the script itself executed successfully.
    payload = json.loads(model_visible_script_result(raw).splitlines()[0])
    assert "links" not in payload
    assert "controls" not in payload


@pytest.mark.parametrize("answer,requests", [("", 2), ("Visible value", 1)])
def test_harness_exposes_hints_only_for_failed_verdict(monkeypatch, tmp_path, answer, requests):
    model = Model([[tool(code="first")], [tool("task_failed", reason="Stop")]])
    harness = BenchmarkHarness(api_key="offline", arm="script_first", runs_dir=tmp_path)
    harness.anthropic = model

    class HintClient(Client):
        def tools_for_claude(self):
            return ScriptFirstClient().tools_for_claude()

        async def call_tool(self, name, arguments):
            return format_run_result(
                ok=True, url="https://example.org/page", step_count=1,
                text="Visible value", claimed={"answer": answer},
                links=[["Next", "https://example.org/next"]],
                controls=[{"role": "button", "name": "Submit"}],
                selector_text="JUDGE-ONLY",
            ), 0

    harness.mcp_client = HintClient()

    async def noop(*args):
        pass

    monkeypatch.setattr(harness, "_read_shared_page", noop)
    result = asyncio.run(harness.run_task("fixture", "Read value", "https://example.org"))
    assert len(model.requests) == requests
    assert result.success == bool(answer)
    if not answer:
        assert model.requests[0][1] == model.requests[1][1]
        assert [item["name"] for item in model.requests[1][1]] == ["run_script", "task_failed"]
        visible = model.requests[1][0][-1]["content"][0]["content"]
        payload = json.loads(visible.splitlines()[1])
        assert payload["links"] == [["Next", "https://example.org/next"]]
        assert payload["controls"] == [{"role": "button", "name": "Submit"}]
        assert "JUDGE-ONLY" not in visible


def test_oversized_hints_keep_whole_entries_and_valid_json():
    links = [[f"Link {i}", f"https://example.org/{i}/" + "x" * 1000] for i in range(40)]
    controls = [{"role": "button", "name": f"Action {i}"} for i in range(30)]
    raw = format_run_result(ok=False, url="https://example.org", step_count=1,
                            links=links, controls=controls, text="body " * 2000)
    visible = model_visible_script_result(raw, failed=True)
    payload = json.loads(visible.splitlines()[0])
    assert len(visible) <= MAX_SNAPSHOT_CHARS - 300
    assert 0 < len(payload["links"]) < 40
    assert payload["links"] == links[:len(payload["links"])]
    assert payload["controls"] == controls


def test_trusted_link_collector_and_single_evaluate():
    from bench.script_first import _PAGE_EVIDENCE_JS, run_on_page

    node = shutil.which("node")
    assert node
    program = r"""
const source = process.argv[1];
const nodes = [];
function anchor(text, href, options = {}) {
  nodes.push({innerText: text,
    getAttribute: () => href,
    closest: (selector) => selector.startsWith('[hidden]') ? options.hidden : options.main,
    getClientRects: () => options.noRects ? [] : [{}],
    style: options.style || {visibility: 'visible', display: 'inline'}
  });
}
anchor('Navigation copy', '/duplicate');
anchor('Navigation', '/nav');
anchor('Article copy', '/duplicate', {main: true});
anchor('  Article \n value  ', '../value', {main: true});
anchor('Protocol relative', '//other.example.org/item', {main: true});
anchor('Empty label', '/hidden', {main: true, hidden: true});
anchor('No rect', '/no-rect', {main: true, noRects: true});
anchor('Hidden style', '/style', {main: true, style: {visibility: 'hidden'}});
anchor('   ', '/empty', {main: true});
anchor('Script', 'javascript:alert(1)', {main: true});
anchor('Email', 'mailto:me@example.org', {main: true});
for (let i = 0; i < 45; i++) anchor('Extra ' + i, '/extra/' + i);
const document = {
  baseURI: 'https://example.org/catalog/page', title: 'Catalog',
  body: {innerText: 'Catalog body'},
  querySelector: () => null,
  querySelectorAll: (selector) => selector === 'a[href]' ? nodes : []
};
const location = {href: document.baseURI};
const getComputedStyle = (node) => node.style;
const collect = new Function('document', 'location', 'getComputedStyle', 'return (' + source + ')()');
process.stdout.write(JSON.stringify(collect(document, location, getComputedStyle)));
"""
    completed = subprocess.run([node, "-e", program, _PAGE_EVIDENCE_JS],
                               check=True, capture_output=True, text=True)
    raw = json.loads(completed.stdout)
    assert len(raw["links"]) == 40
    assert raw["links"][:4] == [
        ["Article copy", "https://example.org/duplicate"],
        ["Article value", "https://example.org/value"],
        ["Protocol relative", "https://other.example.org/item"],
        ["Navigation", "https://example.org/nav"],
    ]
    assert len({href for _, href in raw["links"]}) == 40
    assert not any(text in {"Script", "Email", "Empty label", "No rect", "Hidden style"}
                   for text, _ in raw["links"])

    class Page:
        url = "https://example.org/catalog/page"
        title = "Catalog"
        reads = 0

        async def goto(self, url, **kwargs):
            self.url = url

        async def evaluate(self, source):
            assert source == _PAGE_EVIDENCE_JS
            self.reads += 1
            return raw

    page = Page()
    result = asyncio.run(run_on_page(page, 'page.goto("https://example.org/catalog/page")'))
    assert page.reads == 1
    assert json.loads(result.splitlines()[0])["links"] == raw["links"]


def test_no_repair_defaults():
    from bench.harness import TaskResult

    result = TaskResult("fixture", "read", False, "empty", 0, 0, 0, 0, 0, 0, 0, 0)
    assert result.repair_sent is False
    assert result.repair_reply == "none"
