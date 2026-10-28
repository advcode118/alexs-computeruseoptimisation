"""Local control page: start, pause, step, stop, and the observe/act log."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from loop.browser import FIXTURE_PATH

CONTROL_HTML = Path(__file__).with_name("control.html").read_text(encoding="utf-8")
FIXTURE_HTML = FIXTURE_PATH.read_text(encoding="utf-8")
PLANNERS = {"fake", "model"}


class App:
    def __init__(self):
        self.runner = None


class ControlServer:
    def __init__(self, app: App, host: str, port: int):
        self.app = app
        handler = _handler(app)
        self.httpd = ThreadingHTTPServer((host, port), handler)
        self.host = host
        self.port = self.httpd.server_address[1]
        self._thread = None

    def start(self) -> None:
        import threading

        self._thread = threading.Thread(target=self.httpd.serve_forever, name="loop-control", daemon=True)
        self._thread.start()

    def close(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


def _handler(app: App):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt: str, *args) -> None:
            return

        def do_GET(self) -> None:
            path = self.path.split("?", 1)[0]
            if path == "/":
                self._bytes(200, CONTROL_HTML.encode(), "text/html; charset=utf-8")
                return
            if path == "/fixture":
                self._bytes(200, FIXTURE_HTML.encode(), "text/html; charset=utf-8")
                return
            if path == "/api/state":
                self._json(200, _state(app))
                return
            if path == "/favicon.ico":
                self._bytes(204, b"", "text/plain")
                return
            self._json(404, {"error": "Not found."})

        def do_POST(self) -> None:
            path = self.path.split("?", 1)[0]
            if app.runner is None:
                self._json(503, {"error": "The browser is not ready."})
                return
            body = self._read_json()
            if body is None:
                self._json(400, {"error": "Send a JSON object."})
                return
            runner = app.runner
            if path == "/api/pause":
                runner.pause()
                self._json(200, _state(app))
                return
            if path == "/api/stop":
                runner.stop()
                self._json(200, _state(app))
                return
            if path not in ("/api/start", "/api/step"):
                self._json(404, {"error": "Not found."})
                return
            task = body.get("task", "")
            planner = body.get("planner", "fake")
            if not isinstance(task, str) or not isinstance(planner, str):
                self._json(400, {"error": "task and planner must be strings."})
                return
            if planner not in PLANNERS:
                self._json(400, {"error": "planner must be fake or model."})
                return
            if path == "/api/start":
                if not task.strip():
                    self._json(400, {"error": "A task is required."})
                    return
                runner.start(task, planner)
            else:
                if not task.strip() and not runner.controller.task:
                    self._json(400, {"error": "A task is required."})
                    return
                runner.step(task, planner)
            self._json(200, _state(app))

        def _read_json(self):
            length = int(self.headers.get("Content-Length", "0") or "0")
            if length > 16000:
                return None
            raw = self.rfile.read(length) if length else b"{}"
            try:
                data = json.loads(raw.decode())
            except json.JSONDecodeError:
                return None
            if not isinstance(data, dict):
                return None
            return data

        def _json(self, status: int, payload: dict) -> None:
            self._bytes(status, json.dumps(payload).encode(), "application/json")

        def _bytes(self, status: int, data: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

    return Handler


def _state(app: App) -> dict:
    if app.runner is None:
        return {"mode": "idle", "task": "", "planner": "fake", "detail": "Browser is starting.", "events": []}
    snapshot = app.runner.controller.snapshot()
    snapshot["events"] = app.runner.log.snapshot()
    if app.runner.open_error:
        snapshot["detail"] = app.runner.open_error
    return snapshot
