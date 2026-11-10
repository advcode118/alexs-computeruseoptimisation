"""Held-out tasks. Offline. No browser, no network, no model call.

Expected answers stay on the judge side. A system prompt, a repair, and a
patch turn must not gain them. UNKNOWN is not a pass and does not repair.
The scored URL is the live URL or the canonical href, byte for byte.
"""

from __future__ import annotations

import asyncio
import json

from bench.arms import SELECTABLE_ARMS, prompt_for
from bench.judge import JUDGE_SYSTEM, check_url_contains
from bench.probe import main, plan_probe, probe_tasks
from bench.script_cache import PATCH_PROMPT, PATCH_TOOL, patch_request
from bench.script_first import (
    FAIL,
    PASS,
    UNKNOWN,
    ClaimedEvidence,
    PageEvidence,
    evidence_verdict,
    format_run_result,
    repair_request,
    script_verdict,
)
from bench.tasks import HELD_OUT_TASK_IDS, get_held_out_tasks, markers_for_task
from loop import planner

# The ten tasks added on top of the original five. Their destination tokens
# are not part of the task text.
WIDER_IDS = (
    "ho_httpbin_customer_form",
    "ho_pypi_requests",
    "ho_rust_book_borrowing",
    "ho_w3c_selectors_4",
    "ho_iana_status_451",
    "ho_rfc9110_get_section",
    "ho_schema_person",
    "ho_cppreference_vector",
    "ho_sqlite_vacuum",
    "ho_k8s_pod",
)

PYPI = "https://pypi.org/project/requests/"
SCHEMA = "https://schema.org/Person"
RUST = "https://doc.rust-lang.org/book/ch04-02-references-and-borrowing.html"
RUST_ENCODED = "https://doc.rust-lang.org/book/ch04-02-references-and-borrowing%2Ehtml"
NODE = "https://nodejs.org/api/fs.html"
IANA = "https://www.iana.org/assignments/http-status-codes/http-status-codes.xhtml"


def _verdict(markers, url="", *, canonical="", title="", text="", answer="", claim_url=""):
    verdict = evidence_verdict(
        markers,
        PageEvidence(url=url, title=title, canonical=canonical, text=text),
        ClaimedEvidence(url=claim_url, answer=answer),
    )
    if verdict.scored_url:
        assert verdict.scored_url == url or (bool(canonical) and verdict.scored_url == canonical)
    return verdict


def _finished(task_id):
    """A page that should PASS, and the answer the model would return."""
    pages = {
        "ho_mdn_array_map": (
            "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Array/map",
            "Array.prototype.map",
            "Array.prototype.map",
        ),
        "ho_github_rust": (
            "https://github.com/rust-lang/rust",
            "rust-lang/rust",
            "",
        ),
        "ho_arxiv_attention": (
            "https://arxiv.org/abs/1706.03762",
            "Attention Is All You Need",
            "Attention Is All You Need",
        ),
        "ho_wiki_eiffel_city": (
            "https://en.wikipedia.org/wiki/Eiffel_Tower",
            "The tower stands in Paris.",
            "Paris",
        ),
        "ho_nodejs_fs_docs": (NODE, "fs", ""),
        "ho_httpbin_customer_form": (
            "https://httpbin.org/post",
            "custname=Alice",
            "custname",
        ),
        "ho_pypi_requests": (PYPI, "requests", ""),
        "ho_rust_book_borrowing": (RUST, "References and Borrowing", ""),
        "ho_w3c_selectors_4": ("https://www.w3.org/TR/selectors-4/", "Selectors Level 4", ""),
        "ho_iana_status_451": (
            IANA,
            "451 Unavailable For Legal Reasons",
            "Unavailable For Legal Reasons",
        ),
        "ho_rfc9110_get_section": (
            "https://www.rfc-editor.org/rfc/rfc9110.html",
            "9.3.1 GET",
            "9.3.1",
        ),
        "ho_schema_person": (SCHEMA, "Person", ""),
        "ho_cppreference_vector": (
            "https://en.cppreference.com/w/cpp/container/vector",
            "std::vector",
            "",
        ),
        "ho_sqlite_vacuum": ("https://www.sqlite.org/lang_vacuum.html", "VACUUM", ""),
        "ho_k8s_pod": (
            "https://kubernetes.io/docs/concepts/workloads/pods/",
            "Pods",
            "",
        ),
    }
    return pages[task_id]


def test_held_out_set_is_fifteen_and_disjoint_from_the_tuned_probe():
    held = get_held_out_tasks()
    assert [task["id"] for task in held] == list(HELD_OUT_TASK_IDS)
    assert len(held) == 15
    assert 10 <= len(held) <= 15
    assert len({task["id"] for task in held}) == len(held)
    probe_ids = {task["id"] for task in probe_tasks()}
    assert probe_ids == {"wv_wikipedia_search", "wv_python_docs", "wv_hackernews_top"}
    assert probe_ids.isdisjoint(HELD_OUT_TASK_IDS)
    for task in held:
        markers = task["end_markers"]
        assert markers.get("host")
        assert markers.get("url_contains") or markers.get("path_suffix")
        assert "answer_equals_selector" not in markers
        assert task["id"] in WIDER_IDS or task["id"] in HELD_OUT_TASK_IDS


def test_finished_pages_pass_and_the_scored_url_is_not_rewritten():
    encoded = _verdict(markers_for_task("ho_rust_book_borrowing"), RUST_ENCODED, title="References and Borrowing")
    assert encoded.verdict == PASS
    assert encoded.scored_url == RUST_ENCODED
    assert encoded.scored_url != RUST

    canonical = _verdict(
        markers_for_task("ho_pypi_requests"),
        "https://pypi.org/project/requests",
        canonical=PYPI,
        claim_url=PYPI,
    )
    assert canonical.verdict == PASS
    assert canonical.scored_url == PYPI

    live_wins = _verdict(
        markers_for_task("ho_schema_person"),
        SCHEMA,
        canonical="https://schema.org/Person/",
    )
    assert live_wins.verdict == PASS
    assert live_wins.scored_url == SCHEMA

    slash = _verdict(
        markers_for_task("ho_schema_person"),
        "https://schema.org/Person/",
        canonical=SCHEMA,
    )
    assert slash.verdict == PASS
    assert slash.scored_url == SCHEMA

    node = _verdict(
        markers_for_task("ho_nodejs_fs_docs"),
        "https://nodejs.org/api/fs",
        canonical=NODE,
    )
    assert node.verdict == PASS
    assert node.scored_url == NODE

    for task in get_held_out_tasks():
        url, text, answer = _finished(task["id"])
        verdict = _verdict(task["end_markers"], url, title=task["id"], text=text, answer=answer, claim_url=url)
        assert verdict.verdict == PASS, task["id"]
        assert verdict.scored_url == url


def test_near_misses_fail_and_a_search_url_is_not_rewritten_into_a_pass():
    search = check_url_contains(
        "https://en.wikipedia.org/wiki/Special:Search?search=Ada_Lovelace",
        "Ada_Lovelace",
    )
    assert search.success is False

    cases = [
        ("form not submitted", "ho_httpbin_customer_form", "https://httpbin.org/forms/post", "custname", "custname"),
        ("pypi search", "ho_pypi_requests", "https://pypi.org/search/?q=/project/requests/", "", ""),
        ("pypi package", "ho_pypi_requests", "https://pypi.org/project/requests-html/", "", ""),
        ("wrong host", "ho_pypi_requests", "https://example.com/project/requests/", "", ""),
        ("title only", "ho_pypi_requests", "https://pypi.org/", "", ""),
        ("rust chapter index", "ho_rust_book_borrowing", "https://doc.rust-lang.org/book/ch04-00-understanding-ownership.html", "", ""),
        ("selectors 3", "ho_w3c_selectors_4", "https://www.w3.org/TR/selectors-3/", "", ""),
        ("selectors without slash", "ho_w3c_selectors_4", "https://www.w3.org/TR/selectors-4", "", ""),
        ("iana wrong answer", "ho_iana_status_451", IANA, "451 Unavailable For Legal Reasons", "Not Found"),
        ("iana answer absent", "ho_iana_status_451", IANA, "Status codes", "Unavailable For Legal Reasons"),
        ("rfc other section", "ho_rfc9110_get_section", "https://www.rfc-editor.org/rfc/rfc9110.html", "9.3.2 POST", "9.3.2"),
        ("schema other type", "ho_schema_person", "https://schema.org/Organization", "", ""),
        ("vector bool", "ho_cppreference_vector", "https://en.cppreference.com/w/cpp/container/vector_bool", "", ""),
        ("vector member", "ho_cppreference_vector", "https://en.cppreference.com/w/cpp/container/vector/empty", "", ""),
        ("sqlite other statement", "ho_sqlite_vacuum", "https://www.sqlite.org/lang_delete.html", "", ""),
        ("pod child", "ho_k8s_pod", "https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/", "", ""),
        ("mdn search", "ho_mdn_array_map", "https://developer.mozilla.org/en-US/search?q=Array/map", "", ""),
        ("github search", "ho_github_rust", "https://github.com/search?q=rust-lang/rust", "", ""),
        ("arxiv search", "ho_arxiv_attention", "https://arxiv.org/search/?query=1706.03762", "Attention Is All You Need", "Attention Is All You Need"),
        ("wiki search", "ho_wiki_eiffel_city", "https://en.wikipedia.org/wiki/Special:Search?search=Eiffel_Tower", "Paris", "Paris"),
        ("wiki wrong city", "ho_wiki_eiffel_city", "https://en.wikipedia.org/wiki/Eiffel_Tower", "The tower stands in Paris.", "Lyon"),
        ("fs extra", "ho_nodejs_fs_docs", "https://nodejs.org/api/fs.html/extra", "", ""),
        ("claimed other page", "ho_pypi_requests", PYPI, "requests", ""),
    ]
    for name, task_id, url, text, answer in cases:
        markers = markers_for_task(task_id)
        claim_url = "https://pypi.org/project/numpy/" if name == "claimed other page" else ""
        verdict = _verdict(markers, url, text=text, answer=answer, claim_url=claim_url, title=name)
        assert verdict.verdict == FAIL, name
        assert verdict.verdict != PASS
        assert verdict.scored_url == url

    for task in get_held_out_tasks():
        host = task["end_markers"]["host"]
        token = task.get("check_url_contains") or task["end_markers"].get("url_contains") or task["end_markers"].get("path_suffix")
        search_url = f"https://{host}/search?q={token}"
        if task.get("check_url_contains"):
            assert check_url_contains(search_url, task["check_url_contains"]).success is False, task["id"]
        verdict = _verdict(task["end_markers"], search_url, text="results", answer=token)
        assert verdict.verdict == FAIL, task["id"]
        assert verdict.scored_url == search_url
        start = _verdict(task["end_markers"], task["start_url"], text="The start page is open.")
        assert start.verdict == FAIL, task["id"]
        assert start.scored_url == task["start_url"]


def test_empty_evidence_fails_and_unread_text_is_unknown_not_success():
    for task in get_held_out_tasks():
        empty = _verdict(task["end_markers"])
        assert empty.verdict == FAIL, task["id"]
        assert empty.reason == "empty evidence"
        assert empty.scored_url == ""

    unread = _verdict(
        markers_for_task("ho_iana_status_451"),
        IANA,
        answer="Unavailable For Legal Reasons",
    )
    assert unread.verdict == UNKNOWN
    assert unread.verdict != PASS
    assert unread.reason == "page text was not read"
    assert unread.scored_url == IANA

    missing_answer = _verdict(
        markers_for_task("ho_rfc9110_get_section"),
        "https://www.rfc-editor.org/rfc/rfc9110.html",
        text="9.3.1 GET",
        answer="",
    )
    assert missing_answer.verdict == FAIL
    assert missing_answer.scored_url == "https://www.rfc-editor.org/rfc/rfc9110.html"


def test_unknown_does_not_repair_or_count_as_success(tmp_path):
    from tests.test_script_first import _done_reply, _script_harness, _tool_reply

    secret = "SHOULD-NOT-LEAK"
    raw = format_run_result(
        ok=True,
        url=IANA,
        step_count=1,
        title="HTTP Status Code Registry",
        selector_text=secret,
        claimed={"answer": "Unavailable For Legal Reasons"},
    )

    async def call_tool(name, arguments, nth):
        del name, arguments, nth
        return raw, 1.0

    harness, model, client = _script_harness(
        tmp_path,
        [_tool_reply("read"), _tool_reply("again"), _done_reply()],
        call_tool,
        max_steps=4,
    )
    task = next(item for item in get_held_out_tasks() if item["id"] == "ho_iana_status_451")
    result = asyncio.run(
        harness.run_task(
            task_id=task["id"],
            task_description=task["description"],
            start_url=task["start_url"],
            expected_answer=task["expected_answer"],
        )
    )
    seen = json.dumps(model.seen)
    assert client.calls == 1
    assert len(model.seen) == 1
    assert result.model_calls == 1
    assert result.success is False
    assert result.end_state == UNKNOWN
    assert result.success_reason.startswith("UNKNOWN")
    assert "END_STATE_FAILED" not in seen
    assert "selector_text" not in seen
    assert secret not in seen
    assert task["expected_answer"] not in harness.system_prompt
    assert result.steps[-1].page_url == IANA


def _judge_only(task) -> list[str]:
    secrets = [task["expected_answer"]]
    check = task.get("check_text")
    if isinstance(check, str):
        secrets.append(check)
    elif isinstance(check, list):
        secrets.extend(str(item) for item in check)
    markers = task["end_markers"]
    for key in ("answer_in_text", "path_suffix", "answer_equals_selector"):
        value = markers.get(key)
        if isinstance(value, str) and value:
            secrets.append(value)
    return secrets


def test_answers_stay_off_the_prompt_repair_and_patch_turn():
    standing = [(f"prompt:{arm}", prompt_for(arm)) for arm in SELECTABLE_ARMS]
    standing.append(("patch-prompt", PATCH_PROMPT))
    standing.append(("patch-tool", json.dumps(PATCH_TOOL)))
    standing.append(("planner", planner._SYSTEM))
    standing.append(("judge-system", JUDGE_SYSTEM))
    for task in get_held_out_tasks():
        markers = task["end_markers"]
        url_token = str(markers.get("url_contains") or "")
        task_text = task["description"] + "\n" + task["start_url"]
        for secret in _judge_only(task):
            assert secret not in task_text, task["id"]
        if task["id"] in WIDER_IDS and url_token:
            assert url_token not in task_text, task["id"]
        raw = format_run_result(
            ok=True,
            url=task["start_url"],
            step_count=1,
            title="Start",
            text="The start page is open.",
            selector_text=".titleline a",
            claimed={"answer": "not the finished page"},
        )
        verdict, payload = script_verdict(markers, raw, task["start_url"])
        assert verdict.verdict == FAIL, task["id"]
        payload["selector_text"] = ".titleline a"
        payload["answer_equals_selector"] = ".titleline a"
        payload["expected_answer"] = task["expected_answer"]
        repair = repair_request(task["start_url"], verdict.reason)
        patch = patch_request(
            description=task["description"],
            start_url=task["start_url"],
            script='page.goto("https://example.com/")',
            payload=payload,
            verdict=verdict,
        )
        visible = [repair, patch, *standing]
        for secret in _judge_only(task):
            for text in visible:
                body = text if isinstance(text, str) else text[1]
                assert secret not in body, task["id"]
        if url_token and url_token not in task_text:
            assert url_token not in repair
            assert url_token not in patch
        assert "selector_text" not in repair
        assert "selector_text" not in patch
        assert ".titleline" not in repair
        assert ".titleline" not in patch
        assert "answer_equals_selector" not in repair
        assert "answer_equals_selector" not in patch
        for _name, text in standing:
            assert "selector_text" not in text
            if url_token:
                assert url_token not in text


def test_held_out_split_is_a_plan_and_the_default_stays_the_tuned_trio(capsys):
    default = plan_probe()
    assert default["execute"] is False
    assert default["split"] == "probe"
    assert default["tasks"] == ["wv_wikipedia_search", "wv_python_docs", "wv_hackernews_top"]
    held = plan_probe(split="held-out")
    assert held["execute"] is False
    assert held["split"] == "held-out"
    assert held["tasks"] == list(HELD_OUT_TASK_IDS)
    assert held["outer_model"] == "claude-sonnet-5-5"
    assert main(["--split", "held-out"]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["execute"] is False
    assert printed["split"] == "held-out"
    assert printed["tasks"] == list(HELD_OUT_TASK_IDS)
    assert main(["--split", "nope"]) == 2
    assert "unknown split" in capsys.readouterr().err
