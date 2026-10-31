import subprocess
import time
import urllib.request

import pytest

from loop.actions import ActionBatch, AssertText, AssertTitle, Click, Fill, Goto, Press, Scroll
from loop.browser import BrowserSession, act, check, fixture_file_url, observe
from loop.engine import Runner
from loop.planner import DEMO_TASK, FakePlanner, ScriptPlanner
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


def test_failed_assertion_replans_once():
    batches = [
        ActionBatch("Open the list.", [Goto(FIXTURE)], AssertTitle("Missing title"), False),
        ActionBatch("The list is open.", [], AssertTitle("Packing list"), True),
    ]
    planner = ScriptPlanner(batches)
    runner = Runner(fixture_url=FIXTURE, headless=True, planner_factory=lambda name, url: planner)
    runner.open()
    try:
        runner.start(DEMO_TASK, "fake")
        snapshot = wait_mode(runner, "done")
        assert "list is open" in snapshot["detail"]
        assert planner.index == 2
    finally:
        runner.close()


def test_recovery_stops_after_two_retries():
    batches = [
        ActionBatch("Open the list.", [Goto(FIXTURE)], AssertTitle("Missing title"), False),
        ActionBatch("Still missing.", [], AssertTitle("Missing title"), False),
        ActionBatch("Still missing again.", [], AssertTitle("Missing title"), False),
        ActionBatch("Should not run.", [Fill("e1", "milk")], None, True),
    ]
    planner = ScriptPlanner(batches)
    runner = Runner(fixture_url=FIXTURE, headless=True, planner_factory=lambda name, url: planner)
    runner.open()
    try:
        runner.start(DEMO_TASK, "fake")
        snapshot = wait_mode(runner, "failed")
        assert "Assertion failed" in snapshot["detail"]
        assert planner.index == 3
        assert not any("fill" in event.get("action", "") for event in runner.log.snapshot())
    finally:
        runner.close()


def test_named_fills_use_one_plan(page):
    from loop.actions import ClickNamed, FillNamed
    from loop.engine import Controller, Engine, Log

    fields = "".join(
        f'<label>Field {index}<input name="f{index}"></label>' for index in range(1, 13)
    )
    links = "".join(f'<a href="#l{index}">Link {index}</a>' for index in range(1, 50))
    page.set_content(
        "<!doctype html><title>Form</title><body>"
        f"{links}<form>{fields}<button>Send</button></form>"
        "<p id='out'></p>"
        "<script>document.querySelector('form').addEventListener('submit', (event) => {"
        "event.preventDefault();"
        "document.querySelector('#out').textContent = document.querySelector('[name=f1]').value;"
        "});</script></body>"
    )
    observation_names = {control.name for control in __import__("loop.browser", fromlist=["observe"]).observe(page).controls}
    for index in range(1, 13):
        assert f"Field {index}" in observation_names

    class Once:
        calls = 0

        def reset(self):
            return None

        def plan(self, task, observation, history):
            del task, observation, history
            self.calls += 1
            actions = [FillNamed("textbox", f"Field {index}", f"v{index}") for index in range(1, 13)]
            actions.append(ClickNamed("button", "Send"))
            from loop.actions import AssertText

            return ActionBatch("Fill every field.", actions, AssertText("v1"), True)

    once = Once()
    log = Log()
    controller = Controller()
    controller.task = "Fill the form"
    controller.mode = "running"
    engine = Engine(page.session if False else type("S", (), {"page": page})(), controller, log)
    # The page fixture owns the browser. Drive the engine with that page.
    engine.session.page = page
    engine.planner = once
    engine.run()
    assert controller.snapshot()["mode"] == "done"
    assert once.calls == 1
    for index in range(1, 13):
        assert page.locator(f"[name=f{index}]").input_value() == f"v{index}"


def test_choose_sets_the_visible_option(page):
    from loop.actions import ChooseNamed
    from loop.engine import Controller, Engine, Log

    page.set_content(
        "<!doctype html><title>Menu</title><body>"
        "<label for='size'>Size</label>"
        "<select id='size' name='size'>"
        "<option value='s'>Small</option>"
        "<option value='m'>Medium</option>"
        "<option value='l'>Large</option>"
        "</select>"
        "<label for='when'>When</label>"
        "<input id='when' name='when' type='time' min='11:00' max='21:00' value='09:00'>"
        "</body>"
    )
    page.locator("[name=when]").evaluate("node => node.reportValidity()")
    observation = observe(page)
    size = next(control for control in observation.controls if control.name.startswith("Size"))
    assert size.role == "combobox"
    assert "Medium" in size.options
    when = next(control for control in observation.controls if control.name.startswith("When"))
    assert when.invalid

    class Once:
        calls = 0

        def reset(self):
            return None

        def plan(self, task, observation, history):
            del task, observation, history
            self.calls += 1
            from loop.actions import AssertValues

            return ActionBatch(
                "Choose medium.",
                [ChooseNamed("combobox", "Size", "Medium")],
                AssertValues((("combobox", "Size", "m"),)),
                True,
            )

    once = Once()
    controller = Controller()
    controller.task = "Choose a size"
    controller.mode = "running"
    engine = Engine(type("S", (), {"page": page})(), controller, Log())
    engine.session.page = page
    engine.planner = once
    engine.run()
    assert controller.snapshot()["mode"] == "done"
    assert once.calls == 1
    assert page.locator("[name=size]").input_value() == "m"


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
