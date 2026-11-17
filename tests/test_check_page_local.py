"""check_page against a local HTTP site, and over a real MCP SDK client. No model call."""

import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import anyio
import pytest

from loop.actions import ActionError
from loop.checks import NAV_TIMEOUT_MS, PageProbe

REPO = Path(__file__).resolve().parents[1]

PAGES = {
    "/clean.html": "<title>Clean</title><body><h1>All good</h1></body>",
    "/console.html": "<title>Console</title><body>Console page<script>console.error('boom from page')</script></body>",
    "/img404.html": "<title>Img</title><body>Image page<img src='/missing.png'></body>",
    "/script404.html": "<title>Script</title><body>Script page<script src='/missing.js'></script></body>",
    "/slow.html": "<title>Slow</title><body>never</body>",
}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/slow.html":
            time.sleep(8)
        if self.path == "/favicon.ico":
            # Chrome requests it on its own; a 404 here shows up as a console error.
            self.send_response(200)
            self.send_header("Content-Type", "image/x-icon")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        body = PAGES.get(self.path)
        if body is None:
            self.send_error(404)
            return
        data = body.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        try:
            self.wfile.write(data)
        except OSError:
            pass

    def log_message(self, fmt, *args):
        return


@pytest.fixture(scope="module")
def site():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}"
    finally:
        httpd.shutdown()
        httpd.server_close()


@pytest.fixture(scope="module")
def probe():
    session = PageProbe(headless=True)
    try:
        session.open()
    except Exception as exc:
        session.close()
        pytest.skip(f"Chrome could not launch: {str(exc).splitlines()[0][:120]}")
    try:
        yield session
    finally:
        session.close()


def test_clean_page_passes(probe, site):
    result = probe.check_page(start_url=f"{site}/clean.html", title="Clean", text="All good")
    assert result["ok"] is True
    assert result["console_errors"] == []
    assert result["failed_requests"] == []
    assert result["model_calls"] == 0


def test_console_error_fails(probe, site):
    result = probe.check_page(start_url=f"{site}/console.html", title="Console")
    assert result["ok"] is False
    assert any("boom from page" in item["text"] for item in result["console_errors"])
    assert "console error" in result["reason"]


@pytest.mark.parametrize("page,asset", [("img404.html", "missing.png"), ("script404.html", "missing.js")])
def test_404_asset_fails(probe, site, page, asset):
    result = probe.check_page(start_url=f"{site}/{page}", text="page")
    assert result["ok"] is False
    assert any(item.get("status") == 404 and item["url"].endswith(asset) for item in result["failed_requests"])
    assert "failed request" in result["reason"]


def test_slow_url_fails_within_the_navigation_timeout(probe, site):
    started = time.monotonic()
    with pytest.raises(ActionError, match="failed"):
        probe.check_page(start_url=f"{site}/slow.html", title="Slow")
    assert time.monotonic() - started < NAV_TIMEOUT_MS / 1000 + 3


def test_unreachable_url_fails_fast(probe):
    started = time.monotonic()
    with pytest.raises(ActionError, match="failed"):
        probe.check_page(start_url="http://127.0.0.1:9/", title="x")
    assert time.monotonic() - started < NAV_TIMEOUT_MS / 1000 + 3


def test_real_mcp_client_calls_check_page(site, probe):
    """The official mcp SDK client lists and calls check_page on `python -m loop.mcp_server`."""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(command=sys.executable, args=["-m", "loop.mcp_server"], cwd=REPO)

    async def run():
        with anyio.fail_after(60):
            return await call_all()

    async def call_all():
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                assert "check_page" in {tool.name for tool in tools.tools}
                clean = await session.call_tool("check_page", {"start_url": f"{site}/clean.html", "title": "Clean"})
                bad = await session.call_tool("check_page", {"start_url": f"{site}/console.html", "title": "Console"})
                slow = await session.call_tool("check_page", {"start_url": f"{site}/slow.html", "title": "Slow"})
                return clean, bad, slow

    # The module's Playwright sync session leaves a loop running in this thread, so use another.
    box: list = []
    worker = threading.Thread(target=lambda: box.append(anyio.run(run)))
    worker.start()
    worker.join(90)
    assert box, "MCP client run did not finish"
    clean, bad, slow = box[0]
    clean_body = json.loads(clean.content[0].text)
    bad_body = json.loads(bad.content[0].text)
    slow_body = json.loads(slow.content[0].text)
    assert clean.is_error is False and clean_body["ok"] is True and clean_body["model_calls"] == 0
    assert bad_body["ok"] is False and bad_body["console_errors"]
    assert slow.is_error is True and slow_body["ok"] is False and slow_body["model_calls"] == 0
