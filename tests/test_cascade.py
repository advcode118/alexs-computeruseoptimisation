"""Cascade tests use saved evidence and mock models only."""

import asyncio
import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from bench.cascade import ground_start_page, grounding_note, handoff_note, precision_check, run_cascade_task
from bench.cascade_precision import build_report
from bench.harness import BenchmarkHarness
from bench.script_first import ScriptFirstClient
from tests.test_script_cache import _WikiPage, _Model, _script_reply, CLICK_SCRIPT, LINK, DESCRIPTION, START, TASK_ID


def test_grounding():
    class Response(io.BytesIO):
        headers = {"Content-Type": "text/html"}
    html = b'<title>Example</title><h1>Hello <b>world</b></h1><a href="/x">X</a><a href="/x">X</a><a href="#foo">skip</a><form action="/search"><input name="query"><input type="hidden" name="lang" value="en"></form>'
    data = ground_start_page("https://example.org/start", fetch=lambda *a, **k: Response(html))
    assert data["h1"] == "Hello world"
    assert data["links"] == [{"href": "https://example.org/x", "text": "X"}]
    assert data["forms"][0] == {"action": "https://example.org/search", "method": "GET", "input": "query", "hidden": {"lang": "en"}}
    assert "query=<query>" in grounding_note(data)
    assert grounding_note({}) == ""
    def fail(*a, **k):
        raise TimeoutError()
    assert ground_start_page("https://example.org", fetch=fail) == {"error": "TimeoutError"}


@pytest.mark.parametrize("answer,url,claim,description,rule", [
    ("a\nb", "https://x/item", "", "Find page", "multiline_answer"),
    ("a\tb", "https://x/item", "", "Find page", "multiline_answer"),
    ("a"*81, "https://x/item", "", "Find page", "long_answer"),
    ("a", "https://x/search", "", "Find page", "search_results_url"),
    ("a", "https://x/item?q=", "", "Find page", "search_results_url"),
    ("", "https://x/", "", "Open the documentation page", "landing_page"),
    ("a", "https://x/item", "https://y/item", "Find page", "claimed_url_mismatch"),
    ("a", "https://X/item/", "https://x/item", "Find page", "PASS"),
])
def test_precision_rules(answer, url, claim, description, rule):
    assert precision_check(description, {"verdict": "PASS", "page_url": url, "payload": {"claimed": {"url": claim, "answer": answer}}}) == (rule == "PASS", rule)


def test_fail_and_handoff():
    assert precision_check("", {"verdict": "FAIL"}) == (False, "self-check FAIL")
    note = handoff_note({"description": "Find page", "start_url": "https://x"}, "https://x/current", ["https://x"]*8, 'FAIL "secret answer"')
    assert "https://x/current" in note
    assert "secret answer" not in note


def test_first_message_and_marker_tripwire(tmp_path, monkeypatch):
    async def run():
        harness = BenchmarkHarness(api_key="mock", arm="script_first", runs_dir=tmp_path)
        harness.mcp_client = ScriptFirstClient(page=_WikiPage({LINK: "article"}))
        harness.anthropic = _Model([_script_reply(CLICK_SCRIPT)])
        async def no_grade(*args):
            pass
        monkeypatch.setattr(harness, "_read_shared_page", no_grade)
        def refuse(*args):
            raise AssertionError("markers read live")
        monkeypatch.setattr("bench.tasks.markers_for_task", refuse)
        result = await harness.run_task(TASK_ID, DESCRIPTION, START, first_message_extra="grounding example")
        assert result.end_state == "PASS"
        assert harness.mcp_client.gate.description == DESCRIPTION
        assert len(harness.anthropic.calls) == 1
        assert "grounding example" in harness.anthropic.calls[0]["messages"][0]["content"]
    asyncio.run(run())


@pytest.mark.parametrize("fallback", ["browser_use", "none"])
@pytest.mark.parametrize("reject", [False, "FAIL", "precision", "error", "empty", "attach_error", "approval", "blocked_state"])
@pytest.mark.parametrize("provider", ["anthropic", "openai"])
def test_cascade_wiring(tmp_path, monkeypatch, reject, provider, fallback):
    from tests.test_script_cache import _run
    monkeypatch.setattr("bench.cascade.time.perf_counter", lambda: 100.0)
    result, _, _ = _run(tmp_path, _WikiPage({LINK: "article"}), [_script_reply(CLICK_SCRIPT)])
    if reject:
        result.steps[-1].self_check["verdict"] = "PASS" if reject == "precision" else "FAIL"
        result.steps[-1].self_check["payload"]["claimed"]["answer"] = "DO NOT LEAK"
        if reject == "precision":
            result.steps[-1].self_check["page_url"] = "https://x/search?q=example"
    if reject == "empty":
        result.steps[-1].self_check = None
    monkeypatch.delenv("CU_BU_MODE", raising=False)
    def refuse(*args):
        raise AssertionError("cascade live path read task markers")
    monkeypatch.setattr("bench.tasks.markers_for_task", refuse)
    class Harness:
        model = "claude-sonnet-5-5"
        effort = None
        browser_launch_ms = 0
        mcp_client = SimpleNamespace(cdp_url="http://127.0.0.1:12345", _page=SimpleNamespace(url="https://x/current"))
        def __init__(self, **kwargs):
            assert kwargs["remote_debugging"]
            if kwargs["provider"] == "openai":
                self.model = "gpt-6.1-sol"
                self.effort = "medium"
        async def setup(self):
            pass
        async def teardown(self):
            pass
        async def run_task(self, *args, **kwargs):
            assert self.mcp_client.gate.description == DESCRIPTION
            assert self.mcp_client.gate.profile.signals
            if reject == 'blocked_state':
                self.mcp_client.gate.record_block('needs approval: test')
            return result
    built = []
    class Browser:
        page_url = "https://x/final"
        page_text = "final"
        def __init__(self, **kwargs):
            assert kwargs["cdp_url"] == Harness.mcp_client.cdp_url
            self.cdp_url = kwargs["cdp_url"]
            built.append(self)
        async def start(self):
            pass
        async def stop(self):
            raise AssertionError("externally owned browser stopped")
    class Agent:
        def __init__(self, text, **kwargs):
            assert "https://x/current" in text
            assert "DO NOT LEAK" not in text
        async def run(self, **kwargs):
            if reject == "error":
                raise RuntimeError("mock browser failure")
            return SimpleNamespace(usage={"input": 1, "output": 1, "requests": 3}, steps=1, text="done")
    monkeypatch.setattr("bench.harness.BenchmarkHarness", Harness)
    async def target_id(page):
        if reject == "attach_error":
            raise RuntimeError("cannot attach")
        return "script-target"
    monkeypatch.setattr("bench.cascade._page_target_id", target_id)
    def attach(browser, target):
        assert target == "script-target"
        return {"targetId": target, "url": "https://x/current"}
    monkeypatch.setattr("bench.browser_use_arm._attach_target", attach)
    monkeypatch.setattr("bench.cascade.ground_start_page", lambda *a, **k: {})
    if reject == 'approval':
        from bench.recovery import TaskProfile
        monkeypatch.setattr('bench.cascade.classify_task', lambda *a: TaskProfile('dom', 'irreversible', True, ('commit intent',)))
    options = {"fallback": fallback}
    row = asyncio.run(run_cascade_task({"id": TASK_ID, "description": DESCRIPTION, "start_url": START}, api_key="mock", runs_dir=tmp_path, provider=provider, browser_use_loader=lambda: (Agent, Browser, lambda *a, **k: object()), **options))
    handed_off = bool(reject) and reject not in {'approval', 'blocked_state'} and fallback == "browser_use"
    failed = reject in {"error", "attach_error"}
    assert row["answered_by"] == ("script" if not reject else "none" if not handed_off or failed else "browser_use")
    assert bool(built) == handed_off
    if reject in {"approval", "blocked_state"}:
        # A task stopped for approval is not a pass, whatever the script stage graded.
        assert row["success"] is False and row["end_state"] == "UNKNOWN"
        assert row["success_reason"].startswith("UNKNOWN: needs approval")
    assert row["stage_model_calls"] == {"script": 1, "browser_use": 3 if handed_off and not failed else 0}
    assert row["model_calls"] == sum(row["stage_model_calls"].values())
    if reject and fallback == "none":
        assert row["handoff_reason"]
        assert row["stage_wall_ms"]["browser_use"] == 0
        assert row["stage_usd"]["browser_use"] == 0
        assert not any(row["stage_tokens"]["browser_use"].values())
        assert row["final_url"] == result.steps[-1].page_url
        assert row["usd"] == row["stage_usd"]["script"]
    if handed_off and reject != "attach_error":
        assert row["handoff_target_id"] == row["browser_use_initial_target_id"]
        assert row["handoff_url"] == row["browser_use_initial_url"]
        assert "DO NOT LEAK" not in row["handoff_receipt"]
    assert set(row["stage_wall_ms"]) == {"grounding", "script", "browser_use"}
    assert row["wall_ms"] >= sum(row["stage_wall_ms"].values()) - 2
    if reject == "FAIL" and provider == "anthropic" and fallback == "browser_use":
        golden = json.loads((Path(__file__).parent / "fixtures/cascade_before_recovery.json").read_text())
        comparable = dict(row)
        comparable.pop("stage_model_calls")
        for key in ("profile", "checkpoints", "blocked_actions"):
            comparable.pop(key)
        comparable["model_calls"] = golden["model_calls"]
        assert json.loads(json.dumps(comparable)) == golden
    from bench.probe import arm_report
    assert arm_report([row], ("cascade",))


def test_invalid_fallback(tmp_path):
    with pytest.raises(ValueError, match="unknown fallback"):
        asyncio.run(run_cascade_task({}, api_key="mock", runs_dir=tmp_path, fallback="other"))


@pytest.mark.parametrize("provider", ["anthropic", "openai"])
def test_fallback_cli(monkeypatch, capsys, provider):
    from bench.probe import main

    async def execute(**kwargs):
        assert kwargs["fallback"] == "none"
        assert kwargs["arms"] == ("cascade",)
        return []

    monkeypatch.setattr("bench.probe.execute_probe", execute)
    assert main(["--execute", "--arms", "cascade", "--provider", provider, "--fallback", "none"]) == 0
    assert "probe rows: 0" in capsys.readouterr().out


def test_source_and_saved_precision():
    root = Path(__file__).resolve().parents[1]
    assert "bench.grade" not in (root / "bench/cascade.py").read_text()
    assert build_report(root) == json.loads((root / "docs/results/cascade_selfcheck_20261117/precision.json").read_text())


def test_remote_debugging():
    from urllib.request import urlopen

    async def run():
        client = ScriptFirstClient(headless=True, remote_debugging=True)
        try:
            await client.start()
            assert client.cdp_url.startswith("http://127.0.0.1:")
            with urlopen(client.cdp_url + "/json/version", timeout=4) as response:
                assert "webSocketDebuggerUrl" in json.load(response)
        finally:
            await client.stop()
    asyncio.run(run())
