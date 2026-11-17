"""Page checks and replay. No API key and no model call."""

import inspect
import io
import json
import subprocess
import sys
import threading
import time
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from loop.actions import ActionError
from loop.checks import REPLAY_DIR, PageProbe, replay_file, resolve_url
from loop.mcp_server import TOOLS, ToolServer, read_message, serve

REPO = Path(__file__).resolve().parents[1]
FIXTURE = REPO / "loop" / "fixture"
PACKING = "loop/fixture/packing.html"
BROKEN = "loop/fixture/broken.html"


@pytest.fixture(scope="module")
def probe():
    session = PageProbe(headless=True)
    session.open()
    try:
        yield session
    finally:
        session.close()


def block_model(monkeypatch):
    def boom(*_args, **_kwargs):
        raise AssertionError("deterministic check called the model")

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    import loop.planner as planner

    monkeypatch.setattr(planner, "_post_json", boom)
    monkeypatch.setattr(planner, "make_planner", boom)


def test_check_module_does_not_reference_the_planner():
    import loop.checks as checks

    source = inspect.getsource(checks)
    assert "loop.planner" not in source
    assert "loop.engine" not in source
    assert "make_planner" not in source


def test_resolve_localhost_adds_http():
    assert resolve_url("localhost:3000") == "http://localhost:3000"
    assert resolve_url(PACKING).endswith("loop/fixture/packing.html")


def test_tool_descriptions_state_start_and_end():
    names = {tool["name"] for tool in TOOLS}
    assert names == {
        "open_url",
        "check_page",
        "reload",
        "console_errors",
        "failed_requests",
        "run_loop",
        "run_saved_test",
    }
    for tool in TOOLS:
        text = tool["description"].lower()
        assert "start" in text
        assert "end" in text
        assert "model" in text


def test_check_page_pass_fail_console_and_failed_requests(probe, monkeypatch):
    block_model(monkeypatch)
    failed = probe.check_page(start_url=BROKEN, title="Broken fixture", text="Broken page")
    assert failed["ok"] is False
    assert failed["model_calls"] == 0
    assert failed["start"]["url"].endswith("broken.html")
    assert any("fixture console error" in item["text"] for item in failed["console_errors"])
    assert any("missing-asset.png" in item["url"] for item in failed["failed_requests"])

    opened = probe.open_url(BROKEN)
    assert opened["model_calls"] == 0
    assert opened["console_errors"]
    assert opened["failed_requests"]
    kept = probe.check_page(title="Broken fixture")
    assert kept["ok"] is False
    assert kept["console_errors"] == opened["console_errors"]
    assert kept["failed_requests"] == opened["failed_requests"]
    assert probe.console_errors()["model_calls"] == 0
    assert probe.failed_requests()["failed_requests"]

    passed = probe.check_page(start_url=PACKING, url="packing.html", title="Packing list", text="Packing list")
    assert passed["ok"] is True
    assert passed["model_calls"] == 0
    assert passed["console_errors"] == []
    assert passed["failed_requests"] == []
    assert passed["end"]["title"]["ok"] is True
    assert passed["reason"] == "passed"

    missed = probe.check_page(start_url=PACKING, text="not on the page")
    assert missed["ok"] is False
    assert missed["console_errors"] == []
    assert missed["failed_requests"] == []
    assert missed["end"]["text"]["ok"] is False

    reloaded = probe.reload()
    assert reloaded["loaded"] is True
    assert reloaded["model_calls"] == 0
    assert reloaded["console_errors"] == []
    assert reloaded["failed_requests"] == []


def test_http_404_asset_fails_without_a_model(probe, monkeypatch):
    block_model(monkeypatch)

    class Quiet(SimpleHTTPRequestHandler):
        def log_message(self, fmt, *args):
            return

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), lambda *args: Quiet(*args, directory=str(FIXTURE)))
    thread = threading.Thread(target=httpd.serve_forever, name="fixture-http", daemon=True)
    thread.start()
    port = httpd.server_address[1]
    try:
        result = probe.check_page(
            start_url=f"http://127.0.0.1:{port}/broken.html",
            title="Broken fixture",
            text="Broken page",
        )
    finally:
        httpd.shutdown()
        httpd.server_close()
    assert result["ok"] is False
    assert result["model_calls"] == 0
    assert any("fixture console error" in item["text"] for item in result["console_errors"])
    assert any(item.get("status") == 404 and item["url"].endswith("missing-asset.png") for item in result["failed_requests"])


def test_save_then_replay_makes_no_model_call(probe, monkeypatch, tmp_path):
    block_model(monkeypatch)
    saved = probe.check_page(
        start_url=PACKING,
        url="packing.html",
        title="Packing list",
        text="Packing list",
        save_path=tmp_path / "packing-roundtrip.json",
    )
    assert saved["ok"] is True
    assert saved["saved"] is True
    spec = json.loads((tmp_path / "packing-roundtrip.json").read_text(encoding="utf-8"))
    assert spec["start"] == {"url": PACKING}
    assert spec["end"]["title"] == "Packing list"
    started = time.perf_counter()
    replayed = replay_file(tmp_path / "packing-roundtrip.json", probe=probe)
    elapsed = time.perf_counter() - started
    assert replayed["ok"] is True
    assert replayed["model_calls"] == 0
    assert replayed["console_errors"] == []
    assert replayed["failed_requests"] == []
    assert elapsed < 3

    server = ToolServer(session=probe)
    started = time.perf_counter()
    tool = server.call("run_saved_test", {"file": "tests/replay/packing-page.json"})
    elapsed = time.perf_counter() - started
    assert tool["ok"] is True
    assert tool["model_calls"] == 0
    assert elapsed < 3

    refused = probe.check_page(start_url=BROKEN, title="Broken fixture", save="should-not-write.json")
    assert refused["ok"] is False
    assert refused["saved"] is False
    assert not (REPLAY_DIR / "should-not-write.json").exists()


def test_mcp_tool_check_page_reports_the_fixture(probe, monkeypatch):
    block_model(monkeypatch)
    server = ToolServer(session=probe)
    passed = server.call("check_page", {"start_url": PACKING, "title": "Packing list", "text": "Packing list"})
    assert passed["ok"] is True
    assert passed["model_calls"] == 0
    failed = server.call("check_page", {"start_url": BROKEN, "title": "Broken fixture"})
    assert failed["ok"] is False
    assert failed["model_calls"] == 0
    assert failed["console_errors"]
    assert failed["failed_requests"]


def test_run_loop_fake_planner_reaches_done_without_a_model(probe, monkeypatch):
    def boom(*_args, **_kwargs):
        raise AssertionError("run_loop fake planner called the model")

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    import loop.planner as planner

    monkeypatch.setattr(planner, "_post_json", boom)
    from loop.run_tool import run_loop

    result = run_loop(probe, task="Add milk to the packing list", start_url=PACKING, planner="fake")
    assert result["ok"] is True, result
    assert result["mode"] == "done"
    assert result["model_calls"] == 0
    assert result["model_allowed"] is False
    assert result["start"]["url"] == PACKING
    assert any(event["kind"] == "assert" for event in result["events"])


def test_stdio_check_page_does_not_open_a_browser():
    class Stub:
        def __init__(self):
            self.kwargs = None

        def check_page(self, **kwargs):
            self.kwargs = kwargs
            return {
                "ok": True,
                "model_calls": 0,
                "console_errors": [],
                "failed_requests": [],
                "start": {"url": PACKING},
                "end": {},
            }

        def open_url(self, url):
            raise AssertionError(url)

        def reload(self):
            raise AssertionError("reload")

        def console_errors(self):
            return {"console_errors": [], "model_calls": 0}

        def failed_requests(self):
            return {"failed_requests": [], "model_calls": 0}

    stub = Stub()
    messages = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test", "version": "0"}},
        },
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "check_page", "arguments": {"start_url": PACKING, "title": "Packing list"}},
        },
    ]
    stdin = io.BytesIO(b"".join(json.dumps(message).encode() + b"\n" for message in messages))
    stdout = io.BytesIO()
    serve(stdin, stdout, server=ToolServer(session=stub))
    lines = [json.loads(line) for line in stdout.getvalue().splitlines() if line.strip()]
    assert [line["id"] for line in lines] == [1, 2, 3]
    assert "start" in lines[0]["result"]["instructions"].lower()
    assert any(tool["name"] == "check_page" for tool in lines[1]["result"]["tools"])
    body = json.loads(lines[2]["result"]["content"][0]["text"])
    assert lines[2]["result"]["isError"] is False
    assert body["ok"] is True
    assert body["model_calls"] == 0
    assert stub.kwargs["title"] == "Packing list"


def test_content_length_ping():
    body = json.dumps({"jsonrpc": "2.0", "id": 7, "method": "ping"}).encode()
    frame = f"Content-Length: {len(body)}\r\n\r\n".encode() + body
    message = read_message(io.BytesIO(frame))
    assert message["id"] == 7


def test_run_saved_test_rejects_paths_outside_the_repo():
    server = ToolServer(session=object())
    with pytest.raises(ActionError):
        server.call("run_saved_test", {"file": "/etc/passwd"})


def test_cli_replay_committed_spec():
    started = time.perf_counter()
    proc = subprocess.run(
        [sys.executable, "-m", "loop", "replay", "tests/replay/packing-page.json"],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    elapsed = time.perf_counter() - started
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert payload["model_calls"] == 0
    assert payload["console_errors"] == []
    assert payload["failed_requests"] == []
    assert elapsed < 3
    assert payload["spec"]["name"] == "packing-page"
