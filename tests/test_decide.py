"""decide() is the no-model step. These cases do not call a model or a browser."""

from loop.actions import ActionBatch, Click, Control, Fill, Observation
from loop.decide import TierDecision, decide
from loop.engine import Controller, Engine, Log
from loop.observe.dom import DomSource


def _search_page() -> Observation:
    return Observation(
        "https://en.wikipedia.org/wiki/Main_Page",
        "Wikipedia, the free encyclopedia",
        [
            Control("e4", "textbox", "Search Wikipedia", ""),
            Control("e5", "button", "Search", ""),
        ],
        html="textbox\tSearch Wikipedia\te4\nbutton\tSearch\te5",
    )


def test_decide_fills_a_unique_search_without_a_model():
    task = "Search Wikipedia for Ada Lovelace and confirm the article title."
    outcome = decide(task, _search_page())
    assert isinstance(outcome, ActionBatch)
    assert [type(action).__name__ for action in outcome.actions] == ["Fill", "Click"]
    assert isinstance(outcome.actions[0], Fill)
    assert outcome.actions[0].text == "Ada Lovelace"
    assert outcome.actions[1].ref == "e5"
    assert outcome.done is True


def test_decide_leaves_an_ambiguous_page_for_the_fast_tier():
    task = "Search Wikipedia for Ada Lovelace and confirm the article title."
    page = Observation(
        "https://en.wikipedia.org/",
        "Wikipedia",
        [Control("e5", "button", "Search", ""), Control("e6", "button", "Search", "")],
        html="button\tSearch\te5\nbutton\tSearch\te6",
    )
    outcome = decide(task, page, first=False)
    assert isinstance(outcome, TierDecision)
    assert outcome.tier == "fast"
    assert [control.ref for control in outcome.controls] == ["e5", "e6"]


def test_decide_sends_the_first_cycle_and_a_retry_to_the_planner():
    task = "Add milk to the packing list"
    page = Observation(
        "https://example.test/packing.html",
        "Packing list",
        [
            Control("e1", "textbox", "Item", ""),
            Control("e2", "button", "Add", ""),
        ],
    )
    first = decide(task, page, first=True)
    assert isinstance(first, TierDecision)
    assert first.tier == "planner"
    assert first.controls == ()

    previous = Observation("https://example.test/home", "Home", [Control("e8", "button", "Next", "")])
    batch = ActionBatch("Go on.", [Click("e8")], None, False)
    retry = decide(task, page, batch, previous, True, first=False)
    assert isinstance(retry, TierDecision)
    assert retry.tier == "planner"


def test_decide_clicks_the_only_control_a_previous_batch_named():
    previous = Observation("https://example.test/home", "Home", [Control("e8", "button", "Next", "")])
    batch = ActionBatch("Go on.", [Click("e8")], None, False)
    page = Observation(
        "https://example.test/next",
        "Next",
        [Control("e4", "button", "Next", ""), Control("e5", "textbox", "Item", "")],
    )
    outcome = decide("Go on.", page, batch, previous, False, first=False)
    assert isinstance(outcome, ActionBatch)
    assert outcome.actions == [Click("e4")]
    assert outcome.reason == "Click the only button named Next."
    assert outcome.done is False


def test_decide_does_not_click_the_same_control_on_the_same_page_again():
    previous = Observation("https://example.test/home", "Home", [Control("e8", "button", "Next", "")])
    batch = ActionBatch("Go on.", [Click("e8")], None, False)
    again = Observation(previous.url, "Home", [Control("e8", "button", "Next", "")])
    outcome = decide("Go on.", again, batch, previous, False, first=False)
    assert isinstance(outcome, TierDecision)
    assert outcome.tier == "fast"


def test_engine_uses_decide_and_the_observation_source():
    class Source:
        def __init__(self):
            self.calls = 0

        def observe(self):
            self.calls += 1
            return Observation("https://example.test/fixed", "Fixed", [])

    class Planner:
        def plan(self, task, observation, history):
            del task, history
            assert observation.title == "Fixed"
            return ActionBatch("Done.", [], None, True)

    class Session:
        page = object()

    source = Source()
    controller = Controller()
    controller.task = "Look at the fixed page."
    controller.mode = "running"
    engine = Engine(Session(), controller, Log(), source=source, max_cycles=2)
    engine.planner = Planner()
    engine.run()
    assert source.calls == 1
    assert controller.snapshot()["mode"] == "done"

    default = Engine(Session(), Controller(), Log())
    assert isinstance(default.source, DomSource)
