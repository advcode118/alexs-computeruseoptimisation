import subprocess
import time
import urllib.request

import pytest

from loop.actions import ActionBatch, AssertText, AssertTitle, Click, Fill, Goto, Press, Scroll
from loop.browser import BrowserSession, act, check, fixture_file_url, observe
from loop.engine import Runner
from loop.planner import DEMO_TASK, FakePlanner, FastClient, ScriptPlanner
from loop.server import App, ControlServer

FIXTURE = fixture_file_url()


def wait_mode(runner, mode, timeout=15):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        last = runner.controller.snapshot()
        if last["mode"] == mode:
            return last
        time.sleep(0.02)
    raise AssertionError(f"mode is {last}, log={runner.log.snapshot()}")


@pytest.fixture()
def page():
    session = BrowserSession(headless=True)
    session.open()
    try:
        yield session.page
    finally:
        session.close()


def test_observe_lists_url_title_and_refs(page):
    page.goto(FIXTURE)
    observation = observe(page)
    assert observation.title == "Packing list"
    assert observation.url.endswith("packing.html")
    roles = {(control.role, control.name): control.ref for control in observation.controls}
    assert roles[("textbox", "Item")] == "e1"
    assert roles[("button", "Add")] == "e2"
    assert "textbox\tItem\te1" in observation.html
    assert "button\tAdd\te2" in observation.html
    assert page.locator('[data-cu-ref="e1"]').count() == 1


def test_fill_click_press_and_scroll(page):
    page.goto(FIXTURE)
    observation = observe(page)
    item = next(control.ref for control in observation.controls if control.name == "Item")
    add = next(control.ref for control in observation.controls if control.name == "Add")
    act(page, Fill(item, "tent"))
    act(page, Press("Enter", item))
    assert "tent" in page.locator("body").inner_text()

    page.goto(FIXTURE)
    observation = observe(page)
    item = next(control.ref for control in observation.controls if control.name == "Item")
    add = next(control.ref for control in observation.controls if control.name == "Add")
    act(page, Fill(item, "map"))
    act(page, Click(add))
    assert "map" in page.locator("body").inner_text()

    before = page.evaluate("() => window.scrollY")
    act(page, Scroll("down", 900))
    assert page.evaluate("() => window.scrollY") > before


def test_assertion_between_actions(page):
    page.goto(FIXTURE)
    ok, detail = check(page, AssertTitle("Packing list"))
    assert ok and "Packing list" in detail
    ok, detail = check(page, AssertText("not on the page"))
    assert ok is False


def test_fake_planner_run_reaches_done():
    runner = Runner(fixture_url=FIXTURE, headless=True)
    runner.open()
    try:
        runner.start(DEMO_TASK, "fake")
        snapshot = wait_mode(runner, "done")
        assert "milk" in snapshot["detail"]
        kinds = runner.log.kinds()
        assert "observe" in kinds
        assert "act" in kinds
        assert "assert" in kinds
        text = "\n".join(event["line"] for event in runner.log.snapshot())
        assert "goto" in text
        assert "fill" in text
        assert "click" in text
        assert "assert   ok" in text
    finally:
        runner.close()


def _acts(runner):
    return [event for event in runner.log.snapshot() if event["kind"] == "act"]


def test_step_runs_one_planner_call_then_waits():
    runner = Runner(fixture_url=FIXTURE, headless=True)
    runner.open()
    try:
        runner.step(DEMO_TASK, "fake")
        wait_mode(runner, "paused")
        acts = _acts(runner)
        assert len(acts) == 1
        assert acts[0]["action"].startswith("goto")

        runner.step(DEMO_TASK, "fake")
        deadline = time.time() + 15
        while time.time() < deadline:
            if len(_acts(runner)) >= 3 and runner.controller.snapshot()["mode"] == "paused":
                break
            time.sleep(0.02)
        else:
            raise AssertionError(runner.log.snapshot())
        text = "\n".join(event["line"] for event in runner.log.snapshot())
        assert "fill" in text
        assert "click" in text
        assert len(_acts(runner)) == 3

        runner.step(DEMO_TASK, "fake")
        snapshot = wait_mode(runner, "done")
        assert "milk" in snapshot["detail"]
        assert len(_acts(runner)) == 3
    finally:
        runner.close()


def test_pause_holds_the_next_planner_call():
    import threading

    class Gate:
        def __init__(self):
            self.calls = 0
            self.first_entered = threading.Event()
            self.first_release = threading.Event()
            self.second_entered = threading.Event()

        def reset(self):
            return None

        def plan(self, task, observation, history):
            del task, observation, history
            self.calls += 1
            if self.calls == 1:
                self.first_entered.set()
                assert self.first_release.wait(5)
                return ActionBatch("first", [], None, False)
            self.second_entered.set()
            return ActionBatch("second", [], None, True)

    gate = Gate()
    runner = Runner(fixture_url=FIXTURE, headless=True, planner_factory=lambda name, url: gate)
    runner.open()
    try:
        runner.start(DEMO_TASK, "fake")
        assert gate.first_entered.wait(5)
        runner.pause()
        gate.first_release.set()
        wait_mode(runner, "paused")
        assert gate.calls == 1
        assert gate.second_entered.is_set() is False
        runner.start(DEMO_TASK, "fake")
        assert gate.second_entered.wait(5)
        wait_mode(runner, "done")
    finally:
        runner.close()


def test_stop_skips_actions_after_the_planner_returns():
    class Gate:
        def __init__(self):
            self.inside = __import__("threading").Event()
            self.release = __import__("threading").Event()

        def reset(self):
            return None

        def plan(self, task, observation, history):
            del task, observation, history
            self.inside.set()
            self.release.wait(timeout=5)
            return ActionBatch("held", [Goto(FIXTURE)], None, False)

    gate = Gate()
    runner = Runner(fixture_url=FIXTURE, headless=True, planner_factory=lambda name, url: gate)
    runner.open()
    try:
        runner.start("wait", "fake")
        assert gate.inside.wait(5)
        runner.stop()
        gate.release.set()
        wait_mode(runner, "stopped")
        assert not any(event["kind"] == "act" for event in runner.log.snapshot())
    finally:
        runner.close()


def test_failed_assertion_retries_once_then_stops():
    batches = [
        ActionBatch("Open the list.", [Goto(FIXTURE)], AssertTitle("Missing title"), False),
        ActionBatch("Retry still wrong.", [Goto(FIXTURE)], AssertTitle("Still missing"), False),
        ActionBatch("Should not run.", [Fill("e1", "milk")], None, True),
    ]
    planner = ScriptPlanner(batches)
    runner = Runner(fixture_url=FIXTURE, headless=True, planner_factory=lambda name, url: planner)
    runner.open()
    try:
        runner.start(DEMO_TASK, "fake")
        snapshot = wait_mode(runner, "failed")
        assert "Assertion failed" in snapshot["detail"]
        assert planner.index == 2
        failed = [event for event in runner.log.snapshot() if event["kind"] == "assert" and not event["ok"]]
        assert len(failed) == 2
        assert not any("fill" in event.get("action", "") for event in runner.log.snapshot())
        tiers = [event.get("tier") for event in runner.log.snapshot() if event["kind"] == "plan"]
        assert tiers == ["planner", "planner"]
    finally:
        runner.close()


def test_failed_assertion_can_succeed_on_the_retry():
    batches = [
        ActionBatch("Wrong title.", [Goto(FIXTURE)], AssertTitle("Missing title"), False),
        ActionBatch("Open the list.", [Goto(FIXTURE)], AssertTitle("Packing list"), True),
        ActionBatch("Should not run.", [Fill("e1", "milk")], None, True),
    ]
    planner = ScriptPlanner(batches)
    runner = Runner(fixture_url=FIXTURE, headless=True, planner_factory=lambda name, url: planner)
    runner.open()
    try:
        runner.start(DEMO_TASK, "fake")
        snapshot = wait_mode(runner, "done")
        assert "Open the list." in snapshot["detail"]
        assert planner.index == 2
        assert not any("fill" in event.get("action", "") for event in runner.log.snapshot())
    finally:
        runner.close()


def test_router_clicks_a_unique_named_ref_and_retries_with_the_planner():
    class Claude:
        def __init__(self):
            self.calls = 0

        def reset(self):
            return None

        def plan(self, task, observation, history):
            del task, observation, history
            self.calls += 1
            if self.calls == 1:
                return ActionBatch("Open the packing list.", [Goto(FIXTURE)], AssertTitle("Packing list"), False)
            if self.calls == 2:
                return ActionBatch("The title is the packing list.", [Goto(FIXTURE)], AssertTitle("Packing list"), True)
            raise AssertionError("Claude ran more than the first cycle and one retry")

    class Fast:
        def __init__(self):
            self.calls = 0
            self.lists = []

        def reset(self):
            return None

        def plan(self, task, controls, history):
            del task, history
            self.calls += 1
            self.lists.append([control.name for control in controls])
            item = next(control.ref for control in controls if control.name == "Item")
            add = next(control.ref for control in controls if control.name == "Add")
            if self.calls == 1:
                return ActionBatch("Type milk.", [Fill(item, "milk")], None, False)
            return ActionBatch("Add milk.", [Click(add)], AssertText("milk"), True)

    class Routed:
        use_router = True

        def __init__(self):
            self.claude = Claude()
            self.fast = Fast()

        def reset(self):
            self.claude.reset()
            self.fast.reset()

    routed = Routed()
    runner = Runner(fixture_url=FIXTURE, headless=True, planner_factory=lambda name, url: routed)
    runner.open()
    try:
        runner.start(DEMO_TASK, "model")
        snapshot = wait_mode(runner, "done")
        assert "Add milk." in snapshot["detail"]
        tiers = [event["tier"] for event in runner.log.snapshot() if event["kind"] == "plan"]
        assert tiers[0] == "planner"
        assert "direct" in tiers
        assert "fast" in tiers
        assert routed.claude.calls == 1
        assert routed.fast.calls == 2
        assert "Item" in routed.fast.lists[0] and "Add" in routed.fast.lists[0]
        text = "\n".join(event["line"] for event in runner.log.snapshot())
        assert "direct" in text
        assert "click" in text
        assert "assert   ok" in text
    finally:
        runner.close()


def test_router_retry_calls_the_planner_once_then_stops():
    class Claude:
        def __init__(self):
            self.calls = 0

        def reset(self):
            return None

        def plan(self, task, observation, history):
            del task, observation, history
            self.calls += 1
            if self.calls > 2:
                raise AssertionError("Claude ran after the single retry")
            title = "Missing title" if self.calls == 1 else "Still missing"
            return ActionBatch("Wrong page.", [Goto(FIXTURE)], AssertTitle(title), False)

    class Fast:
        def __init__(self):
            self.calls = 0

        def reset(self):
            return None

        def plan(self, task, controls, history):
            del task, controls, history
            self.calls += 1
            raise AssertionError("The retry must call the planner, not the fast tier")

    class Routed:
        use_router = True

        def __init__(self):
            self.claude = Claude()
            self.fast = Fast()

        def reset(self):
            return None

    routed = Routed()
    runner = Runner(fixture_url=FIXTURE, headless=True, planner_factory=lambda name, url: routed)
    runner.open()
    try:
        runner.start(DEMO_TASK, "model")
        snapshot = wait_mode(runner, "failed")
        assert "Assertion failed" in snapshot["detail"]
        assert routed.claude.calls == 2
        assert routed.fast.calls == 0
        tiers = [event["tier"] for event in runner.log.snapshot() if event["kind"] == "plan"]
        assert tiers == ["planner", "planner"]
    finally:
        runner.close()


def test_finished_task_stops_when_the_next_reply_is_null():
    import json

    class Claude:
        def reset(self):
            return None

        def plan(self, task, observation, history):
            del task, observation, history
            return ActionBatch("Open the packing list.", [Goto(FIXTURE)], AssertTitle("Packing list"), False)

    replies = {"n": 0}

    def transport(url, headers, payload):
        del url, headers, payload
        replies["n"] += 1
        if replies["n"] == 1:
            return json.dumps(
                {
                    "reason": "Add milk.",
                    "done": False,
                    "actions": [
                        {"type": "fill", "ref": "e1", "text": "milk"},
                        {"type": "click", "ref": "e2"},
                    ],
                    "assertion": {"type": "text", "text": "milk"},
                }
            )
        return None

    class Routed:
        use_router = True

        def __init__(self):
            self.claude = Claude()
            self.fast = FastClient(
                api_key="test-key",
                base_url="https://example.test/v1",
                model="deepseek-ai/DeepSeek-V4.1-Flash-1017",
                transport=transport,
            )

        def reset(self):
            return None

    routed = Routed()
    runner = Runner(fixture_url=FIXTURE, headless=True, planner_factory=lambda name, url: routed)
    runner.open()
    try:
        runner.start(DEMO_TASK, "model")
        snapshot = wait_mode(runner, "done")
        assert snapshot["detail"] == "Done."
        assert replies["n"] == 2
        text = "\n".join(event["line"] for event in runner.log.snapshot())
        assert "assert   ok" in text
        assert "strip" not in text
        assert not any(event["kind"] == "error" for event in runner.log.snapshot())
    finally:
        runner.close()


def test_control_page_can_start_and_stop():
    app = App()
    server = ControlServer(app, "127.0.0.1", 0)
    server.start()
    runner = Runner(fixture_url=f"http://127.0.0.1:{server.port}/fixture", headless=True)
    app.runner = runner
    runner.open()
    try:
        base = f"http://127.0.0.1:{server.port}"
        page = urllib.request.urlopen(base + "/", timeout=5).read().decode()
        assert "Start" in page and "Step" in page and "Stop" in page
        body = __import__("json").dumps({"task": DEMO_TASK, "planner": "fake"}).encode()
        request = urllib.request.Request(base + "/api/step", data=body, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(request, timeout=5).read()
        wait_mode(runner, "paused")
        stop = urllib.request.Request(base + "/api/stop", data=b"{}", headers={"Content-Type": "application/json"})
        urllib.request.urlopen(stop, timeout=5).read()
        wait_mode(runner, "stopped")
        state = __import__("json").loads(urllib.request.urlopen(base + "/api/state", timeout=5).read())
        assert any(event["kind"] == "observe" for event in state["events"])
        assert any(event["kind"] == "act" for event in state["events"])
    finally:
        runner.close()
        server.close()


def test_attached_chrome_keeps_running_after_close():
    import socket
    import tempfile

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    profile = tempfile.mkdtemp(prefix="cu-chrome-")
    proc = subprocess.Popen(
        [
            "google-chrome",
            "--headless=new",
            f"--remote-debugging-port={port}",
            f"--user-data-dir={profile}",
            "--no-first-run",
            "--no-default-browser-check",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.time() + 10
        while time.time() < deadline:
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=0.2)
                break
            except Exception:
                time.sleep(0.1)
        else:
            raise AssertionError("Chrome did not open the debugging port")
        session = BrowserSession(cdp=f"http://127.0.0.1:{port}")
        session.open()
        assert session.attached
        assert session.page is not None
        session.close()
        time.sleep(0.4)
        assert proc.poll() is None
    finally:
        if proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=5)


def test_fake_planner_object_matches_the_runner_script():
    planner = FakePlanner(FIXTURE)
    from loop.actions import Control, Observation

    blank = Observation("about:blank", "", [])
    first = planner.plan(DEMO_TASK, blank, [])
    assert isinstance(first.actions[0], Goto)
    on_page = Observation(
        FIXTURE,
        "Packing list",
        [Control("e1", "textbox", "Item", ""), Control("e2", "button", "Add", "")],
    )
    second = planner.plan(DEMO_TASK, on_page, [])
    assert [type(action).__name__ for action in second.actions] == ["Fill", "Click"]
    assert isinstance(second.assertion, AssertText)


def test_html_shortcut_searches_without_calling_a_model(tmp_path):
    page = tmp_path / "search.html"
    page.write_text(
        """<!DOCTYPE html>
        <html><head><title>Search</title></head>
        <body>
          <label for="q">Search Wikipedia</label>
          <input id="q" type="text" />
          <button type="button" id="go">Search</button>
          <script>
            document.getElementById("go").addEventListener("click", () => {
              document.title = document.getElementById("q").value + " - Wikipedia";
            });
          </script>
        </body></html>
        """,
        encoding="utf-8",
    )
    url = page.resolve().as_uri()

    class Claude:
        def __init__(self):
            self.calls = 0

        def reset(self):
            return None

        def plan(self, task, observation, history):
            del task, observation, history
            self.calls += 1
            if self.calls == 1:
                return ActionBatch("Open the search page.", [Goto(url)], None, False)
            raise AssertionError("Claude ran after the HTML shortcut")

    class Fast:
        def reset(self):
            return None

        def plan(self, task, controls, history):
            del task, controls, history
            raise AssertionError("The fast tier ran")

    class Routed:
        use_router = True

        def __init__(self):
            self.claude = Claude()
            self.fast = Fast()

        def reset(self):
            self.claude.reset()
            self.fast.reset()

    routed = Routed()
    runner = Runner(fixture_url=url, headless=True, planner_factory=lambda name, start: routed)
    runner.open()
    try:
        runner.start("Search Wikipedia for Ada Lovelace and confirm the article title.", "model")
        snapshot = wait_mode(runner, "done")
        tiers = [event["tier"] for event in runner.log.snapshot() if event["kind"] == "plan"]
        assert tiers == ["planner", "direct"]
        assert routed.claude.calls == 1
        assert "Ada Lovelace" in snapshot["detail"]
    finally:
        runner.close()
