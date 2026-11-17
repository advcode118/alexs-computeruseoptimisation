"""CLI for the browser loop.

    python -m loop demo
    python -m loop run
"""

from __future__ import annotations

import argparse
import time

from loop.actions import ActionError, PlannerError
from loop.browser import BrowserSession, fixture_file_url
from loop.engine import Controller, Engine, Log, Runner
from loop.planner import DEMO_TASK, make_planner
from loop.server import App, ControlServer


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="loop", description="Thin browser computer-use loop.")
    sub = parser.add_subparsers(dest="command", required=True)

    demo = sub.add_parser("demo", help="Open the control page and a Chrome window.")
    demo.add_argument("--host", default="127.0.0.1")
    demo.add_argument("--port", type=int, default=8765)
    demo.add_argument("--headless", action="store_true", help="Launch Chrome headless.")
    demo.add_argument("--cdp", default=None, help="Attach to Chrome, e.g. http://127.0.0.1:9222")
    demo.add_argument("--max-cycles", type=int, default=12)
    demo.set_defaults(func=cmd_demo)

    run = sub.add_parser("run", help="Run the demo task to completion and print the log.")
    run.add_argument("--task", default=DEMO_TASK)
    run.add_argument("--planner", choices=("fake", "model"), default="fake")
    run.add_argument("--headed", action="store_true")
    run.add_argument("--cdp", default=None, help="Attach to Chrome, e.g. http://127.0.0.1:9222")
    run.add_argument("--max-cycles", type=int, default=12)
    run.set_defaults(func=cmd_run)

    replay = sub.add_parser("replay", help="Replay a saved check_page spec. No model calls.")
    replay.add_argument("file", help="Path to a tests/replay JSON spec.")
    replay.set_defaults(func=cmd_replay)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (ActionError, PlannerError) as exc:
        print(exc)
        return 1


def cmd_demo(args) -> int:
    app = App()
    server = ControlServer(app, args.host, args.port)
    server.start()
    host = "127.0.0.1" if args.host in ("0.0.0.0", "::") else args.host
    fixture_url = f"http://{host}:{server.port}/fixture"
    runner = Runner(
        fixture_url=fixture_url,
        headless=args.headless,
        cdp=args.cdp,
        max_cycles=args.max_cycles,
    )
    app.runner = runner
    try:
        runner.open()
    except (ActionError, TimeoutError) as exc:
        print(exc)
        server.close()
        return 1
    print(f"Control   http://{host}:{server.port}")
    print(f"Task      {DEMO_TASK}")
    print("Planner   fake (no API key). Model routes direct, fast, and Claude.")
    print("Controls  Start runs the task. Pause waits between cycles.")
    print("          Step runs one cycle, then waits. Stop ends the run.")
    print("Ctrl-C ends the process. Stop does not close an attached Chrome.")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        print("\nStopping.")
    finally:
        runner.close()
        server.close()
    return 0


def cmd_run(args) -> int:
    session = BrowserSession(headless=not args.headed, cdp=args.cdp)
    page = session.open()
    del page
    log = Log()
    controller = Controller()
    controller.task = args.task
    controller.planner_name = args.planner
    controller.mode = "running"
    engine = Engine(session, controller, log, max_cycles=args.max_cycles)
    try:
        engine.planner = make_planner(args.planner, fixture_file_url())
        log.status(f"run      {args.task}  planner: {args.planner}")
        engine.run()
    finally:
        session.close()
    mode = controller.snapshot()["mode"]
    print(controller.detail)
    return 0 if mode == "done" else 1


def cmd_replay(args) -> int:
    import json

    from loop.checks import replay_file

    result = replay_file(args.file)
    print(json.dumps(result))
    return 0 if result.get("ok") else 1
