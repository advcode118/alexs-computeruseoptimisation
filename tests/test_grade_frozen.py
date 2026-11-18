"""Offline contract for the arm-neutral, frozen post-run grader."""

import ast
import hashlib
from pathlib import Path
import sys

import pytest

from bench import grade, probe
from bench.browser_use_arm import _judge as browser_use_grade
from bench.tasks_val3 import VAL3_TASKS


ROOT = Path(__file__).resolve().parents[1]
TASK = next(task for task in VAL3_TASKS if task["id"] == "val3_value_yaml_revision")
URL = "https://yaml.org/spec/1.2.2/"
VALUE = "2021-10-01"
PAGE = "YAML specification revision history\n2021-10-01\n" + "Specification details. " * 30


def verdict(answer, *, text=PAGE, url=URL, claimed=None):
    return grade.evidence_verdict(
        TASK["end_markers"], grade.PageEvidence(url=url, text=text),
        claimed or grade.ClaimedEvidence(answer=answer),
    )


@pytest.mark.parametrize("answer,ok,reason", [
    (PAGE, False, "answer too long"),
    (VALUE, True, "the page evidence matches the markers"),
    (f"The revision date is {VALUE}.", True, "the page evidence matches the markers"),
    (f"**{VALUE}**", True, "the page evidence matches the markers"),
    (f'"{VALUE}"', True, "the page evidence matches the markers"),
    (f"‘{VALUE}’", True, "the page evidence matches the markers"),
    (f"`{VALUE}`", True, "the page evidence matches the markers"),
    (f"{VALUE}.", True, "the page evidence matches the markers"),
    (f"Revision date: {VALUE}", True, "the page evidence matches the markers"),
    (f"  __“{VALUE}”__!  ", True, "the page evidence matches the markers"),
    (f"A revision date was '{VALUE}';", True, "the page evidence matches the markers"),
    ("", False, "empty answer"),
    ("2021-10-02", False, "answer does not satisfy the marker"),
    (f"The revision 2 date is {VALUE}.", False, "answer too long"),
    (f"one two three four five six seven: {VALUE}", False, "answer too long"),
    (VALUE + "x" * (2 * len(VALUE) + 41), False, "answer too long"),
])
def test_public_revision_grade(answer, ok, reason):
    result = probe.grade_observation(TASK, URL, PAGE, answer=answer)
    public_reason = "URL contains '/spec/1.2.2/'" if ok else reason
    assert result[:2] == (ok, public_reason)
    assert probe.grade_page_answer(TASK, URL, PAGE, answer=answer) == (ok, public_reason)
    assert grade.grade_observation(TASK, URL, PAGE, answer=answer) == result
    v = verdict(answer)
    assert v.verdict == (grade.PASS if ok else grade.FAIL)
    if reason == "answer too long":
        assert v.code == "answer_too_long"


def test_core_allowance_and_raw_cap_are_inclusive():
    allowed = VALUE + " abcdefghi"
    over = allowed + "j"
    for answer, ok in [(allowed, True), (over, False)]:
        page = PAGE + "\n" + answer
        assert probe.grade_observation(TASK, URL, page, answer=answer)[0] is ok
    assert verdict(over, text=PAGE + over).code == "answer_too_long"
    at_cap = "`" * 30 + VALUE + "`" * 30
    assert len(at_cap) == 3 * len(VALUE) + 40
    assert probe.grade_observation(TASK, URL, PAGE, answer=at_cap)[0] is True
    assert verdict(at_cap + ".").code == "answer_too_long"


@pytest.mark.parametrize("prefix", [
    "The first second third fourth fifth sixth is ",
    "A first second third fourth fifth sixth: ",
    "Revision dates are ",
    "Revision dates were ",
])
def test_permitted_sentence_frames(prefix):
    assert probe.grade_observation(TASK, URL, PAGE, answer=prefix + VALUE)[0] is True


@pytest.mark.parametrize("answer", [
    f"The revision 2 date is {VALUE}",
    f"The revision date is {VALUE}, and the release is final",
    f"- {VALUE}\n- unrelated release details",
])
def test_unstripped_prefixes_suffixes_and_lists_are_not_removed(answer):
    assert probe.grade_observation(TASK, URL, PAGE + "\n" + answer, answer=answer)[0] is False


def test_core_and_marker_must_be_on_the_page():
    answer = "released " + VALUE
    assert verdict(answer).reason == "answer is not in the page text"
    assert verdict(VALUE, text="Another date").reason == "answer is not in the page text"
    assert verdict(VALUE, text="").verdict == grade.UNKNOWN
    assert verdict("2021-10-010", text="2021-10-010").reason == "answer does not satisfy the marker"


@pytest.mark.parametrize("answer,ok", [
    (VALUE, True), (f"**{VALUE}**", True),
    (f"The revision date is '{VALUE}'.", True),
    ("2021-10-02", False), ("", False),
])
def test_selector_core(answer, ok):
    task = {"end_markers": {"answer_equals_selector": "#revision", "host": "yaml.org"}}
    assert probe.grade_observation(task, URL, PAGE, answer=answer, selector_text=VALUE)[0] is ok
    assert grade.evidence_verdict(
        task["end_markers"], grade.PageEvidence(url=URL, text=PAGE, selector_text=VALUE),
        grade.ClaimedEvidence(answer=answer),
    ).verdict == (grade.PASS if ok else grade.FAIL)
    assert probe.grade_observation(task, URL, "Other page", answer=answer, selector_text=VALUE)[0] is False


@pytest.mark.parametrize("answer", [VALUE, f"**{VALUE}**", "2021-10-02", PAGE, ""])
def test_same_inputs_have_same_page_grade_for_every_arm(answer):
    expected = grade.grade_page_answer(TASK, URL, PAGE, answer=answer)
    assert browser_use_grade(TASK, URL, PAGE, answer=answer) == expected
    for arm in ("script_first", "playwright_mcp", "browser_use", "stagehand", "offline_replay"):
        task = {**TASK, "arm": arm}
        result = probe.grade_observation(
            task, URL, PAGE, answer=answer,
            run_verdict="PASS" if arm == "script_first" else None,
        )
        assert result[:2] == expected


@pytest.mark.parametrize("answer", [
    "Your request was received.", "Your request was received",
    '"Your request was received."', '"Your request was received"',
])
def test_selector_truth_keeps_literal_candidates(answer):
    task = {"end_markers": {"answer_equals_selector": ".answer"}}
    truth = "Your request was received."
    ok, reason, *_ = probe.grade_observation(
        task, URL, truth, answer=answer, selector_text=truth,
    )
    assert ok is True
    assert reason == "the page evidence matches the markers"


@pytest.mark.parametrize("answer", ["X is Y", "X is Y.", '"X is Y"', '**"X is Y."**'])
def test_sentence_shaped_text_marker_keeps_literal_candidates(answer):
    task = {"check_text": "X is Y", "end_markers": {"answer_in_text": "X is Y"}}
    assert probe.grade_observation(task, URL, "X is Y", answer=answer)[0] is True


def test_reduction_chain_records_each_step():
    assert grade._answer_candidates('"Your request was received."') == (
        '"Your request was received."', "Your request was received.",
        "Your request was received", "received",
    )


def test_runtime_gate_is_separate_from_page_grade():
    assert probe.grade_page_answer(TASK, URL, PAGE, answer=VALUE)[0] is True
    assert probe.grade_observation(TASK, URL, PAGE, answer=VALUE, run_verdict="FAIL")[0] is False
    assert probe.grade_observation(TASK, URL, PAGE, answer=VALUE, run_verdict="UNKNOWN")[0] is False
    assert probe.grade_observation(TASK, URL, PAGE, answer=VALUE, completed=False)[0] is False


def test_preexisting_gates_still_precede_answer_or_block_pass():
    assert verdict(PAGE, url="https://yaml.org/search?q=x").code == "page_denied"
    assert verdict(PAGE, url="https://elsewhere.example/").reason == "the page is on the wrong host"
    assert verdict(PAGE, url="https://yaml.org/other").reason == "the URL marker does not match the live page"
    assert verdict(VALUE, claimed=grade.ClaimedEvidence(answer=VALUE, key_text="invented")).reason == "returned evidence is not on the page"
    assert verdict(VALUE, claimed=grade.ClaimedEvidence(answer=VALUE, rejected=True)).reason == "returned value is not text"


def test_runtime_modules_do_not_import_the_frozen_grader():
    paths = [ROOT / "bench/script_first.py",
             ROOT / "bench/script_helpers.py", ROOT / "bench/script_grammar.py",
             ROOT / "bench/stagehand_local.py", ROOT / "bench/script_cache.py"]
    for path in paths:
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import):
                assert all(alias.name != "bench.grade" for alias in node.names), path
            elif isinstance(node, ast.ImportFrom):
                assert node.module != "bench.grade", path
                assert not (node.level and node.module == "grade"), path
                assert not (node.module in {"bench", None} and any(alias.name == "grade" for alias in node.names)), path


def test_frozen_grader_is_stdlib_only():
    for node in ast.walk(ast.parse((ROOT / "bench/grade.py").read_text())):
        if isinstance(node, ast.Import):
            assert all(alias.name.split(".")[0] in sys.stdlib_module_names for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0
            assert node.module.split(".")[0] in sys.stdlib_module_names


def test_frozen_grader_source_hash():
    expected = "5f459309a799a7f3a6b6b309cb8beb3b51f9b0cf7bb37bb5ec542a5c4a914bde"
    actual = hashlib.sha256((ROOT / "bench/grade.py").read_bytes()).hexdigest()
    assert actual == expected, (
        "Changing the frozen grader requires deliberately updating this hash "
        "and noting the rule change and new hash in docs/GRADER.md."
    )
