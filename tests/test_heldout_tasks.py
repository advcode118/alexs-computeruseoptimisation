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
from bench.tasks import (
    DEV_TASK_IDS,
    HELD_OUT_TASK_IDS,
    TUNED_PROBE_TASK_IDS,
    get_dev_tasks,
    get_held_out_tasks,
    markers_for_task,
    task_by_id,
    tasks_for_split,
)
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
    pages.update(_NEW_FINISHED)
    return pages[task_id]


_NEW_PREFIXES = ("ho_nav_", "ho_form_", "ho_find_", "ho_page_", "ho_table_", "ho_open_")

_NEW_FINISHED = {
    "ho_nav_py_inputoutput": (
        "https://docs.python.org/3/tutorial/inputoutput.html",
        "Input and Output",
        "",
    ),
    "ho_nav_py_sqlite3": ("https://docs.python.org/3/library/sqlite3.html", "sqlite3", ""),
    "ho_nav_rust_result": (
        "https://doc.rust-lang.org/book/ch09-02-recoverable-errors-with-result.html",
        "Recoverable Errors with Result",
        "",
    ),
    "ho_nav_k8s_service": (
        "https://kubernetes.io/docs/concepts/services-networking/service/",
        "Service",
        "",
    ),
    "ho_nav_go_spec": ("https://go.dev/ref/spec", "The Go Programming Language Specification", ""),
    "ho_nav_pg_select": (
        "https://www.postgresql.org/docs/current/sql-select.html",
        "SELECT",
        "",
    ),
    "ho_nav_sqlite_pragma": ("https://www.sqlite.org/pragma.html", "PRAGMA", ""),
    "ho_nav_css_flex": (
        "https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_flexible_box_layout",
        "CSS flexible box layout",
        "",
    ),
    "ho_form_selenium_received": (
        "https://www.selenium.dev/selenium/web/submitted-form.html?my-text=a",
        "Received!",
        "Received!",
    ),
    "ho_form_internet_secure": (
        "https://the-internet.herokuapp.com/secure",
        "You logged into a secure area!",
        "You logged into a secure area!",
    ),
    "ho_form_internet_email": (
        "https://the-internet.herokuapp.com/email_sent",
        "Your e-mail's been sent!",
        "Your e-mail's been sent!",
    ),
    "ho_form_testpages_comments": (
        "https://testpages.herokuapp.com/styled/the_form_processor.php",
        "comments",
        "comments",
    ),
    "ho_form_w3schools_action": ("https://www.w3schools.com/action_page.php?fname=a&lname=b", "Submitted", ""),
    "ho_form_httpbin_phone": ("https://httpbin.org/post", "custtel=555", "custtel"),
    "ho_find_wiki_gold": ("https://en.wikipedia.org/wiki/Gold", "atomic number 79", "79"),
    "ho_find_wiki_wall": (
        "https://en.wikipedia.org/wiki/Great_Wall_of_China",
        "The wall is in China.",
        "China",
    ),
    "ho_find_pypi_urllib3": ("https://pypi.org/project/urllib3/", "urllib3", ""),
    "ho_find_npm_jest": ("https://www.npmjs.com/package/jest", "jest", ""),
    "ho_find_mdn_promise_all": (
        "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Promise/all",
        "Promise.all",
        "",
    ),
    "ho_find_arxiv_resnet": (
        "https://arxiv.org/abs/1512.03385",
        "Deep Residual Learning for Image Recognition",
        "Deep Residual Learning for Image Recognition",
    ),
    "ho_find_crates_serde": ("https://crates.io/crates/serde", "serde", ""),
    "ho_page_wp_news": ("https://wordpress.org/news/page/2/", "News", ""),
    "ho_page_github_blog": ("https://github.blog/page/2/", "Blog", ""),
    "ho_page_so_blog": ("https://stackoverflow.blog/page/2/", "Blog", ""),
    "ho_page_jquery_blog": ("https://blog.jquery.com/page/2/", "Blog", ""),
    "ho_page_wp_core": ("https://make.wordpress.org/core/page/2/", "Core", ""),
    "ho_table_iana_https": (
        "https://www.iana.org/assignments/service-names-port-numbers/service-names-port-numbers.xhtml",
        "https 443",
        "443",
    ),
    "ho_table_wiki_http_201": (
        "https://en.wikipedia.org/wiki/List_of_HTTP_status_codes",
        "201 Created",
        "Created",
    ),
    "ho_table_calling_codes": (
        "https://en.wikipedia.org/wiki/List_of_country_calling_codes",
        "Japan +81",
        "+81",
    ),
    "ho_table_html_tr": ("https://en.wikipedia.org/wiki/HTML_element", "tr Table row", "Table row"),
    "ho_table_unicode_euro": (
        "https://www.unicode.org/charts/nameslist/n_20A0.html",
        "20AC EURO SIGN",
        "EURO SIGN",
    ),
    "ho_open_go_fmt": ("https://pkg.go.dev/fmt", "fmt", ""),
    "ho_open_rust_vec": (
        "https://doc.rust-lang.org/std/vec/struct.Vec.html",
        "Vec",
        "",
    ),
    "ho_open_redis_get": ("https://redis.io/docs/latest/commands/get/", "GET", ""),
    "ho_open_django_queries": (
        "https://docs.djangoproject.com/en/stable/topics/db/queries/",
        "Making queries",
        "",
    ),
}


def test_held_out_set_is_fifty_and_disjoint_from_dev():
    held = get_held_out_tasks()
    dev = get_dev_tasks()
    assert [task["id"] for task in held] == list(HELD_OUT_TASK_IDS)
    assert len(held) >= 50
    assert len({task["id"] for task in held}) == len(held)
    assert [task["id"] for task in dev] == list(DEV_TASK_IDS)
    assert set(DEV_TASK_IDS).isdisjoint(HELD_OUT_TASK_IDS)
    assert set(TUNED_PROBE_TASK_IDS) <= set(DEV_TASK_IDS)
    assert [task["id"] for task in tasks_for_split("honest")] == list(HELD_OUT_TASK_IDS)
    assert [task["id"] for task in tasks_for_split("probe")] == list(TUNED_PROBE_TASK_IDS)
    probe_ids = {task["id"] for task in probe_tasks()}
    assert probe_ids == {"wv_wikipedia_search", "wv_python_docs", "wv_hackernews_top"}
    assert probe_ids.isdisjoint(HELD_OUT_TASK_IDS)
    covered = {prefix for prefix in _NEW_PREFIXES if any(task["id"].startswith(prefix) for task in held)}
    assert covered == set(_NEW_PREFIXES)
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
        ("tutorial index", "ho_nav_py_inputoutput", "https://docs.python.org/3/tutorial/index.html", "", ""),
        ("sqlite sibling", "ho_nav_py_sqlite3", "https://docs.python.org/3/library/dbm.html", "", ""),
        ("rust error index", "ho_nav_rust_result", "https://doc.rust-lang.org/book/ch09-00-error-handling.html", "", ""),
        ("service child", "ho_nav_k8s_service", "https://kubernetes.io/docs/concepts/services-networking/service/virtual-ips/", "", ""),
        ("spec prefix", "ho_nav_go_spec", "https://go.dev/ref/specification", "", ""),
        ("insert not select", "ho_nav_pg_select", "https://www.postgresql.org/docs/current/sql-insert.html", "", ""),
        ("pragma sibling", "ho_nav_sqlite_pragma", "https://www.sqlite.org/lang_explain.html", "", ""),
        ("grid not flex", "ho_nav_css_flex", "https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_grid_layout", "", ""),
        ("form not confirmed", "ho_form_selenium_received", "https://www.selenium.dev/selenium/web/web-form.html", "Received!", "Received!"),
        ("insecure login", "ho_form_internet_secure", "https://the-internet.herokuapp.com/insecure", "You logged into a secure area!", "You logged into a secure area!"),
        ("login page", "ho_form_internet_secure", "https://the-internet.herokuapp.com/login", "You logged into a secure area!", "You logged into a secure area!"),
        ("reset form", "ho_form_internet_email", "https://the-internet.herokuapp.com/forgot_password", "Your e-mail's been sent!", "Your e-mail's been sent!"),
        ("html form", "ho_form_testpages_comments", "https://testpages.herokuapp.com/styled/basic-html-form-test.html", "comments", "comments"),
        ("wrong field", "ho_form_testpages_comments", "https://testpages.herokuapp.com/styled/the_form_processor.php", "username", "username"),
        ("forms lesson", "ho_form_w3schools_action", "https://www.w3schools.com/html/html_forms.asp", "", ""),
        ("phone not submitted", "ho_form_httpbin_phone", "https://httpbin.org/forms/post", "custtel", "custtel"),
        ("phone other endpoint", "ho_form_httpbin_phone", "https://httpbin.org/anything/post", "custtel", "custtel"),
        ("wrong phone field", "ho_form_httpbin_phone", "https://httpbin.org/post", "custname", "custname"),
        ("gold article prefix", "ho_find_wiki_gold", "https://en.wikipedia.org/wiki/Golden_Gate_Bridge", "79", "79"),
        ("wrong atomic number", "ho_find_wiki_gold", "https://en.wikipedia.org/wiki/Gold", "atomic number 47", "47"),
        ("wrong country", "ho_find_wiki_wall", "https://en.wikipedia.org/wiki/Great_Wall_of_China", "The wall is in China.", "Mongolia"),
        ("urllib3 search", "ho_find_pypi_urllib3", "https://pypi.org/search/?q=/project/urllib3/", "", ""),
        ("jest sibling", "ho_find_npm_jest", "https://www.npmjs.com/package/jest-cli", "", ""),
        ("allSettled", "ho_find_mdn_promise_all", "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Promise/allSettled", "", ""),
        ("resnet pdf", "ho_find_arxiv_resnet", "https://arxiv.org/pdf/1512.03385", "Deep Residual Learning for Image Recognition", "Deep Residual Learning for Image Recognition"),
        ("wrong paper title", "ho_find_arxiv_resnet", "https://arxiv.org/abs/1512.03385", "Attention Is All You Need", "Attention Is All You Need"),
        ("serde_json", "ho_find_crates_serde", "https://crates.io/crates/serde_json", "", ""),
        ("news page 1", "ho_page_wp_news", "https://wordpress.org/news/page/1/", "", ""),
        ("news page 20", "ho_page_wp_news", "https://wordpress.org/news/page/20/", "", ""),
        ("blog page 20", "ho_page_github_blog", "https://github.blog/page/20/", "", ""),
        ("core page 1", "ho_page_wp_core", "https://make.wordpress.org/core/page/1/", "", ""),
        ("wrong port", "ho_table_iana_https", "https://www.iana.org/assignments/service-names-port-numbers/service-names-port-numbers.xhtml", "https 80", "80"),
        ("status child", "ho_table_wiki_http_201", "https://en.wikipedia.org/wiki/List_of_HTTP_status_codes/201", "Created", "Created"),
        ("wrong calling code", "ho_table_calling_codes", "https://en.wikipedia.org/wiki/List_of_country_calling_codes", "Japan +86", "+86"),
        ("wrong element", "ho_table_html_tr", "https://en.wikipedia.org/wiki/HTML_element", "Table header", "Table header"),
        ("wrong char name", "ho_table_unicode_euro", "https://www.unicode.org/charts/nameslist/n_20A0.html", "DOLLAR SIGN", "DOLLAR SIGN"),
        ("other block", "ho_table_unicode_euro", "https://www.unicode.org/charts/nameslist/n_20D0.html", "EURO SIGN", "EURO SIGN"),
        ("fmt child", "ho_open_go_fmt", "https://pkg.go.dev/fmt/print", "", ""),
        ("vecdeque", "ho_open_rust_vec", "https://doc.rust-lang.org/std/vec/struct.VecDeque.html", "", ""),
        ("getdel", "ho_open_redis_get", "https://redis.io/docs/latest/commands/getdel/", "", ""),
        ("models not queries", "ho_open_django_queries", "https://docs.djangoproject.com/en/stable/topics/db/models/", "", ""),
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
        if task["id"].startswith(_NEW_PREFIXES) and url_token:
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


def test_original_fifteen_checks_are_unchanged():
    from pathlib import Path

    frozen = json.loads(Path("tests/fixtures/original_heldout.json").read_text(encoding="utf-8"))
    assert [row["id"] for row in frozen] == list(HELD_OUT_TASK_IDS[:15])
    for row in frozen:
        task = task_by_id(row["id"])
        assert task is not None
        for key, value in row.items():
            assert task[key] == value, key


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


def _marker_pass(markers, url, text, answer=""):
    return _verdict(markers, url, title="t", text=text, answer=answer, claim_url=url).verdict


def test_answer_marker_needs_token_boundaries():
    cases = [
        # (marker, page text, answer, must pass)
        ("443", "HTTPS uses port 4430 here and 443.", "4430", False),
        ("443", "HTTPS uses port 443.", "Port 443.", True),
        ("443", "HTTPS uses port 443.", "443", True),
        ("79", "atomic number 179 and 79", "179", False),
        ("79", "atomic number 79", "79", True),
        ("+81", "code +810 and +81", "+810", False),
        ("+81", "code +81", "+81", True),
        ("+81", "Japan is +81.", "Japan is +81.", True),
        ("9.3.1", "version 9.3.10 and 9.3.1", "9.3.10", False),
        ("9.3.1", "version 9.3.1", "9.3.1", True),
        ("9.3.1", "Use version 9.3.1.", "version 9.3.1.", True),
        ("79", "ratio 1.79 and 79", "1.79", False),
        ("Paris", "Parisian and Paris", "Parisian", False),
        ("Paris", "in Paris", "  in   PARIS ", True),
    ]
    for marker, text, answer, ok in cases:
        got = _marker_pass({"answer_in_text": marker, "host": "example.com"}, "https://example.com/p", text, answer)
        assert (got == PASS) is ok, (marker, answer, got)


def test_tightened_markers():
    def result(task_id, url, text="", answer=""):
        return _marker_pass(task_by_id(task_id)["end_markers"], url, text, answer)

    assert result("ho_github_rust", "https://github.com/rust-lang/rust") == PASS
    assert result("ho_github_rust", "https://github.com/rust-lang/rust-analyzer") != PASS
    assert result("ho_github_rust", "https://github.com/rust-lang/rustup") != PASS
    sel = "https://www.selenium.dev/selenium/web/submitted-form.html"
    assert result("ho_form_selenium_received", sel, "Received!", "Received!") != PASS
    assert result("ho_form_selenium_received", sel + "?", "Received!", "Received!") != PASS
    assert result("ho_form_selenium_received", sel + "?my-text=a", "Received!", "Received!") == PASS
    w3 = "https://www.w3schools.com/action_page.php"
    assert result("ho_form_w3schools_action", w3) != PASS
    assert result("ho_form_w3schools_action", w3 + "?fname=a") == PASS
    arx = "Attention Is All You Need"
    assert result("ho_arxiv_attention", "https://arxiv.org/abs/1706.03762", arx, arx) == PASS
    assert result("ho_arxiv_attention", "https://arxiv.org/pdf/1706.03762", arx, arx) != PASS
    assert result("ho_wiki_eiffel_city", "https://en.wikipedia.org/wiki/Eiffel_Tower", "Paris", "Paris") == PASS
    assert result("ho_wiki_eiffel_city", "https://en.wikipedia.org/wiki/Talk:Eiffel_Tower", "Paris", "Paris") != PASS
    assert "settled" not in task_by_id("ho_find_mdn_promise_all")["description"]
    assert "module page" in task_by_id("ho_nav_css_flex")["description"]
