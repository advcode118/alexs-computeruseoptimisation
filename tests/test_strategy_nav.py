"""The nav read step offline: a fake page and a fake model, no browser and no network."""

import asyncio
import json

import pytest

from bench import strategy_nav as sn
from bench.script_first import PASS, FAIL, EvidenceVerdict, claimed_from_payload

TABLE_PAGE = {
    "url": "https://docs.example.org/compat.html",
    "title": "Compatibility Matrix",
    "h1": "Compatibility Matrix",
    "anchor": "",
    "headings": [[1, "Compatibility Matrix"], [2, "Java"]],
    "tables": [
        {
            "header": ["Java version", "Support for toolchains", "Support for running"],
            "rows": [["22", "8.7", "8.8 and after"], ["21", "8.4", "8.5 and after"], ["20", "8.1", "8.3 and after"]],
            "lines": ["Java version\tSupport for toolchains\tSupport for running", "22\t8.7\t8.8 and after", "21\t8.4\t8.5 and after", "20\t8.1\t8.3 and after"],
        }
    ],
    "dls": [],
    "text": "Compatibility Matrix\nJava\nThe table lists versions.\nJava version\tSupport for toolchains\tSupport for running\n22\t8.7\t8.8 and after\n21\t8.4\t8.5 and after\n20\t8.1\t8.3 and after\nFooter",
}
TASK = "In the manual, open the compatibility matrix and report the first version that supports running on Java 21."


@pytest.fixture(autouse=True)
def _model_path(monkeypatch):
    # Most tests exercise the model call; the table rule has its own test.
    monkeypatch.setenv("CU_SF_NAV_MF", "0")
    for name in ("CU_SF_NAV_READ", "CU_SF_NAV_MISSING"):
        monkeypatch.delenv(name, raising=False)


class FakePage:
    def __init__(self, data):
        self.data = data

    async def evaluate(self, source):
        return self.data


class FakeModel:
    def __init__(self, reply):
        self.reply = reply
        self.prompts = []

    async def create_message(self, messages, tools, system=None, max_tokens=0):
        self.prompts.append(messages[0]["content"])
        return {"content": [{"type": "text", "text": json.dumps(self.reply)}], "usage": {"input_tokens": 500, "output_tokens": 20}}, 900.0


def _payload(answer, page=TABLE_PAGE):
    return {"ok": True, "url": page["url"], "title": page["title"], "h1": page["h1"], "text": page["text"], "claimed": {"answer": answer}}


def _run(model, answer="21\t8.4\t8.5 and after", page=TABLE_PAGE, task=TASK):
    verdict = EvidenceVerdict(PASS, "the script finished", page["url"])
    return asyncio.run(
        sn.read_after_pass(
            page=FakePage(page), model=model, description=task, payload=_payload(answer, page),
            verdict=verdict, page_url=page["url"], start_url="https://docs.example.org/",
        )
    )


def test_switch_and_router(monkeypatch):
    monkeypatch.delenv("CU_SF_STRATEGY", raising=False)
    assert not sn.enabled()
    monkeypatch.setenv("CU_SF_STRATEGY", "form, nav")
    assert sn.enabled()
    assert sn.claims(TASK)
    assert sn.claims("Open the registry and report the port number listed for HTTPS.")
    assert sn.claims("What is the boiling point listed on the page?")
    assert not sn.claims("From the docs index, open the page for the command-line tool.")
    assert not sn.claims("Use the package search to find the package named plug and open its package page.")
    assert not sn.claims("Fill in the contact form with the name Alex and report the confirmation message.")


def test_table_rows_carry_their_column_labels():
    lines = sn.page_lines(TABLE_PAGE)
    rows = [line for line in lines if line.kind == "row"]
    assert rows[1].text == "Java version: 21 | Support for toolchains: 8.4 | Support for running: 8.5 and after"
    assert rows[1].raw == "21\t8.4\t8.5 and after"
    # The raw table lines are replaced, not repeated.
    assert not any(line.text.startswith("21\t") for line in lines)


def test_read_replaces_a_whole_row_with_one_cell():
    model = FakeModel({"line": 0, "value": ""})
    view = sn.build_view(TABLE_PAGE, TASK)
    number = next(i for i, line in enumerate(view.lines, 1) if line.raw.startswith("21\t"))
    model.reply = {"line": number, "column": 3, "value": "8.5"}
    out = _run(model)
    assert out.label == "nav:read" and out.verdict.verdict == PASS
    assert claimed_from_payload(out.payload).answer == "8.5"
    assert out.model_calls == 1 and out.usage["input_tokens"] == 500
    assert "Support for running: 8.5 and after" in model.prompts[0]


def test_label_prefix_is_stripped():
    view = sn.build_view(TABLE_PAGE, TASK)
    number = next(i for i, line in enumerate(view.lines, 1) if line.raw.startswith("21\t"))
    out = _run(FakeModel({"line": number, "column": 3, "value": "Support for running: 8.5 and after"}))
    assert claimed_from_payload(out.payload).answer == "8.5 and after"


def test_unverified_values_keep_the_script_answer():
    view = sn.build_view(TABLE_PAGE, TASK)
    number = next(i for i, line in enumerate(view.lines, 1) if line.raw.startswith("21\t"))
    for reply, why in (
        ({"line": number, "value": "9.9"}, "not on that line"),
        ({"line": number, "value": "21\t8.4"}, "several cells"),
        ({"line": number, "value": "8.4 | Support for running: 8.5"}, ""),
        ({"line": 999, "value": "8.5"}, "not in the view"),
        ({"line": 1, "value": "Compatibility Matrix"}, ""),
    ):
        out = _run(FakeModel(reply))
        assert out.label in ("nav:rejected",), (reply, out.label)
        assert claimed_from_payload(out.payload).answer == "21\t8.4\t8.5 and after"
        assert out.verdict.verdict == PASS
        assert why in out.note


def test_missing_value_asks_the_repair_loop(monkeypatch):
    out = _run(FakeModel({"line": 0, "value": "", "missing": "Java 21 is not listed"}))
    assert out.label == "nav:missing" and out.verdict.verdict == FAIL
    assert "go to the page that shows it" in out.verdict.reason
    monkeypatch.setenv("CU_SF_NAV_MISSING", "keep")
    out = _run(FakeModel({"line": 0, "value": "", "missing": "Java 21 is not listed"}))
    assert out.label == "nav:no_pick" and out.verdict.verdict == PASS


def test_suspect_mode_trusts_a_clean_answer(monkeypatch):
    monkeypatch.setenv("CU_SF_NAV_READ", "suspect")
    model = FakeModel({"line": 1, "value": "x"})
    out = _run(model, answer="8.5")
    assert out.label == "nav:trusted" and not model.prompts
    assert sn.suspicious("21\t8.4\t8.5 and after", _payload(""), TASK) == "several cells or lines"
    assert sn.suspicious("Compatibility Matrix", _payload(""), TASK) == "answer is the page title"


def test_title_from_the_fragment_without_a_model():
    page = dict(TABLE_PAGE, url="https://docs.example.org/manual.html#2.4", anchor="2.4 – Metatables and Metamethods",
                text="2.4 – Metatables and Metamethods\nEvery value can have a metatable.")
    page["tables"] = []
    model = FakeModel({"line": 1, "value": "x"})
    task = "In the reference manual, go to the section about metatables and report its full numbered section heading."
    out = _run(model, answer="Lua 5.4 Reference Manual", page=page, task=task)
    assert out.label == "nav:title_rule" and not model.prompts
    assert claimed_from_payload(out.payload).answer == "2.4 – Metatables and Metamethods"


def test_value_not_in_the_checked_text_keeps_the_script_answer():
    page = dict(TABLE_PAGE)
    payload_text_without_value = "Compatibility Matrix\nJava"
    view = sn.build_view(page, TASK, prior_answer="Java")
    number = next(i for i, line in enumerate(view.lines, 1) if line.raw.startswith("21\t"))
    verdict = EvidenceVerdict(PASS, "ok", page["url"])
    payload = dict(_payload("Java"), text=payload_text_without_value)
    out = asyncio.run(sn.read_after_pass(page=FakePage(page), model=FakeModel({"line": number, "column": 3, "value": "8.5"}),
                                         description=TASK, payload=payload, verdict=verdict,
                                         page_url=page["url"], start_url="https://docs.example.org/"))
    assert out.label == "nav:recheck_fail"
    assert claimed_from_payload(out.payload).answer == "Java"


def test_table_pick_needs_a_unique_row_and_column(monkeypatch):
    lines = sn.page_lines(TABLE_PAGE)
    assert sn.table_pick(lines, TASK) == "8.5 and after"
    # Two columns match the task equally: no pick, the model decides.
    assert sn.table_pick(lines, "Report the support version for Java 21.") == ""
    assert sn.table_pick(lines, "Report the page heading for Java 21.") == ""
    monkeypatch.setenv("CU_SF_NAV_MF", "1")
    model = FakeModel({"line": 1, "value": "x"})
    out = _run(model)
    assert out.label == "nav:table_rule" and not model.prompts
    assert claimed_from_payload(out.payload).answer == "8.5 and after"
    monkeypatch.setenv("CU_SF_NAV_MF", "0")
    assert _run(FakeModel({"line": 0, "value": ""})).label == "nav:no_pick"


def test_site_name_words_do_not_steer_the_view():
    page = {
        "url": "https://www.example-codes.com/list", "title": "List", "h1": "Codes", "anchor": "", "headings": [],
        "tables": [], "dls": [],
        "text": "EXAMPLE-CODES.COM footer\nAbout example-codes.com\n" + "\n".join(f"Row {i}" for i in range(50)) + "\nJapan JPY\n",
    }
    view = sn.build_view(page, "Open example-codes.com's table and report the code for Japan.")
    assert any("Japan JPY" == line.text for line in view.lines)
    terms = sn.page_weights(sn.page_lines(page), sn.key_terms("Open example-codes.com's table and report the code for Japan."), "List", page["url"])
    assert "example-codes.com" not in dict(terms)


def test_rescue_turns_an_imprecise_fail_into_a_pass_without_a_repair_script():
    view = sn.build_view(TABLE_PAGE, TASK, prior_answer="Java")
    number = next(i for i, line in enumerate(view.lines, 1) if line.raw.startswith("21\t"))
    failed = EvidenceVerdict(FAIL, "the answer is a heading on the page (Java), not the asked value", TABLE_PAGE["url"])
    assert sn.read_can_fix(failed)
    out = asyncio.run(sn.read_after_pass(page=FakePage(TABLE_PAGE), model=FakeModel({"line": number, "column": 3, "value": "8.5"}),
                                         description=TASK, payload=_payload("Java"), verdict=failed,
                                         page_url=TABLE_PAGE["url"], start_url="https://docs.example.org/"))
    assert out.label == "nav:rescue_read" and out.verdict.verdict == PASS
    assert claimed_from_payload(out.payload).answer == "8.5"
    # No line holds it: the FAIL and its repair stay.
    out = asyncio.run(sn.read_after_pass(page=FakePage(TABLE_PAGE), model=FakeModel({"line": 0, "value": "", "missing": "x"}),
                                         description=TASK, payload=_payload("Java"), verdict=failed,
                                         page_url=TABLE_PAGE["url"], start_url="https://docs.example.org/"))
    assert out.label == "nav:rescue_none_missing" and out.verdict is failed


def test_navigation_failures_are_left_to_the_repair_loop():
    for reason in (
        "the script is still on the start page; follow the link to the page the task asks for",
        "the script ended on a search results page; open the matching result",
        "the live page is an error page (404); open the real page",
        "the script stopped before it finished (timeout)",
    ):
        assert not sn.read_can_fix(EvidenceVerdict(FAIL, reason, ""))
    assert not sn.read_can_fix(EvidenceVerdict(PASS, "ok", ""))


@pytest.mark.parametrize("column,value", [(2, "8.4"), (3, "8.4"), (None, "8.5"), (True, "8.5")])
def test_wrong_or_unidentified_table_column_cannot_replace_a_correct_answer(column, value):
    view = sn.build_view(TABLE_PAGE, TASK, prior_answer="8.5")
    number = next(i for i, line in enumerate(view.lines, 1) if line.raw.startswith("21\t"))
    out = _run(FakeModel({"line": number, "column": column, "value": value}), answer="8.5")
    assert out.label == "nav:rejected"
    assert claimed_from_payload(out.payload).answer == "8.5"
    assert "column" in out.note


def test_main_heading_takes_priority_over_an_unrelated_fragment():
    view = sn.View(url="https://example.org/manual#details", title="Widget Manual", h1="Widget Manual",
                   anchor="Advanced Details", lines=[])
    assert sn.title_without_model(view, "Report the main heading of this page.") == "Widget Manual"
    assert sn.title_without_model(view, "Report the Installation section heading.") == ""
    assert sn.title_without_model(view, "Report the Advanced Details section heading.") == "Advanced Details"


def test_definition_selection_matches_the_term_and_refuses_ambiguity():
    data = {"text": "Timeout\n30 seconds\nRetries\n4", "dls": [[["Timeout", "30 seconds"], ["Retries", "4"]]]}
    assert sn.table_pick(sn.page_lines(data), "Report the Timeout value.") == "30 seconds"
    assert sn.table_pick(sn.page_lines(data), "Report the 30 seconds value.") == ""
    data["dls"].append([["Timeout", "60 seconds"]])
    assert sn.table_pick(sn.page_lines(data), "Report the Timeout value.") == ""


def test_unpriceable_reader_call_propagates_but_transport_error_keeps_the_answer():
    from bench.openai_spend import PriceUnknown

    class BrokenModel:
        def __init__(self, error):
            self.error = error

        async def create_message(self, *args, **kwargs):
            raise self.error

    with pytest.raises(PriceUnknown):
        _run(BrokenModel(PriceUnknown("unknown usage field")))
    out = _run(BrokenModel(ConnectionError("offline")), answer="8.5")
    assert out.label == "nav:model_error" and out.verdict.verdict == PASS
    assert claimed_from_payload(out.payload).answer == "8.5"
    assert out.model_calls == 1 and out.model_ms >= 0


@pytest.mark.parametrize("enabled", [False, True])
def test_probe_accounts_for_reader_usage_and_records_before_after(monkeypatch, tmp_path, enabled):
    from bench.harness import BenchmarkHarness
    from bench.probe import run_claude_arm
    from bench.openai_spend import price_usd
    from bench.script_first import format_run_result
    from tests.test_grounded_repair import _Client, _Model, _reply

    monkeypatch.setenv("CU_SF_STRATEGY", "nav" if enabled else "")
    view = sn.build_view(TABLE_PAGE, TASK, prior_answer="8.5")
    number = next(i for i, line in enumerate(view.lines, 1) if line.raw.startswith("21\t"))
    usage = {"input_tokens": 500, "output_tokens": 20, "cached_tokens": 100,
             "cache_write_30m_tokens": 200, "cache_write_12h_tokens": 50}
    model = _Model([_reply("page.evaluate(() => '8.5')"), {
        "content": [{"type": "text", "text": json.dumps({"line": number, "column": 3, "value": "8.5"})}],
        "usage": usage,
    }])
    client = _Client([format_run_result(ok=True, url=TABLE_PAGE["url"], title=TABLE_PAGE["title"],
                                       h1=TABLE_PAGE["h1"], text=TABLE_PAGE["text"], step_count=1,
                                       claimed={"answer": "8.5"})])
    client._page = FakePage(TABLE_PAGE)

    async def setup(self):
        self.anthropic, self.mcp_client = model, client

    async def noop(*args):
        pass

    monkeypatch.setattr(BenchmarkHarness, "setup", setup)
    monkeypatch.setattr(BenchmarkHarness, "teardown", noop)
    monkeypatch.setattr(BenchmarkHarness, "_read_shared_page", noop)
    row = asyncio.run(run_claude_arm("script_first", {"id": "fixture", "description": TASK,
                                                    "start_url": "https://docs.example.org/"},
                                   api_key="offline", headless=True, runs_dir=tmp_path,
                                   provider="openai", model="gpt-6-luna", effort="medium"))
    assert row["model_calls"] == (2 if enabled else 1)
    assert row["claimed_answer"] == "8.5"
    assert row["input_tokens"] == (501 if enabled else 1)
    assert row["cache_write_30m_tokens"] == (200 if enabled else 0)
    assert row["cache_write_12h_tokens"] == (50 if enabled else 0)
    expected_usd = price_usd("gpt-6-luna", 501, 21, 100, 200, 50) if enabled else price_usd("gpt-6-luna", 1, 1)
    assert row["usd"] == expected_usd
    if enabled:
        event, = row["strategy_reads"]
        assert event["usage"] == usage
        assert event["before_answer"] == event["after_answer"] == "8.5"
        assert event["model_ms"] == 1.0 and event["model_calls"] == 1
    else:
        assert "strategy" not in row and "strategy_reads" not in row
