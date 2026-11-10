"""Benchmark task definitions.

Contains:
1. Local fixture tasks from loop/fixture
2. WebVoyager-style tasks on stable public sites

WebVoyager tasks are adapted from the WebVoyager dataset
(https://github.com/MinorJerry/WebVoyager). We select tasks on stable
sites that don't require login and have predictable answers.

Success is judged by:
- Fixture tasks: checking the final page state (title, text presence)
- WebVoyager tasks: LLM judge comparing the answer to expected, or
  checking for specific text/URL patterns
"""

from __future__ import annotations

from pathlib import Path

FIXTURE_DIR = Path(__file__).parent.parent / "loop" / "fixture"


def fixture_url(name: str) -> str:
    """Get file:// URL for a fixture."""
    path = FIXTURE_DIR / name
    return f"file://{path.resolve()}"


FIXTURE_TASKS = [
    {
        "id": "fixture_packing_add",
        "description": "Add 'milk' to the packing list",
        "start_url": fixture_url("packing.html"),
        "expected_answer": "milk appears in the list",
        "check_text": "milk",
    },
    {
        "id": "fixture_packing_multi",
        "description": "Add 'socks' and 'toothbrush' to the packing list",
        "start_url": fixture_url("packing.html"),
        "expected_answer": "both items appear in the list",
        "check_text": ["socks", "toothbrush"],
    },
]

# Judge-only. script_first must not copy these into the model prompt.
_WIKI_DENY = ["Special:Search", "Main_Page"]

WEBVOYAGER_TASKS = [
    {
        "id": "wv_wikipedia_search",
        "description": "Search Wikipedia for 'Ada Lovelace' and confirm you are on her article page",
        "start_url": "https://en.wikipedia.org/wiki/Main_Page",
        "expected_answer": "On the Ada Lovelace Wikipedia article",
        "check_url_contains": "Ada_Lovelace",
        "end_markers": {
            "url_contains": "Ada_Lovelace",
            "host": "en.wikipedia.org",
            "deny": list(_WIKI_DENY),
        },
    },
    {
        "id": "wv_wikipedia_link",
        "description": "Go to the Wikipedia article for Python (programming language) and find the year it was first released",
        "start_url": "https://en.wikipedia.org/wiki/Main_Page",
        "expected_answer": "1991",
        "check_text": "1991",
        "end_markers": {
            "url_contains": "Python_(programming_language)",
            "host": "en.wikipedia.org",
            "deny": list(_WIKI_DENY),
            "answer_in_text": "1991",
        },
    },
    {
        "id": "wv_arxiv_search",
        "description": "Search arXiv for 'attention is all you need' and identify the first author of the top result",
        "start_url": "https://arxiv.org/",
        "expected_answer": "Ashish Vaswani",
        "check_text": "Vaswani",
        "end_markers": {
            "url_contains": "1706.03762",
            "host": "arxiv.org",
            "deny": ["/search"],
            "answer_in_text": "Vaswani",
        },
    },
    {
        "id": "wv_github_repo",
        "description": "Navigate to the microsoft/playwright GitHub repository and find the primary programming language",
        "start_url": "https://github.com/",
        "expected_answer": "TypeScript",
        "check_text": "TypeScript",
        "end_markers": {
            "url_contains": "microsoft/playwright",
            "host": "github.com",
            "deny": ["/search"],
            "answer_in_text": "TypeScript",
        },
    },
    {
        "id": "wv_python_docs",
        "description": "Go to the Python documentation and find the page about the 'heapq' module",
        "start_url": "https://docs.python.org/3/",
        "expected_answer": "On the heapq module documentation page",
        "check_url_contains": "heapq",
        "end_markers": {
            "url_contains": "heapq",
            "host": "docs.python.org",
            "path_suffix": "/library/heapq.html",
            "deny": ["/search", "search.html"],
        },
    },
    {
        "id": "wv_mdn_search",
        "description": "Search MDN Web Docs for 'fetch API' and navigate to the main article",
        "start_url": "https://developer.mozilla.org/en-US/",
        "expected_answer": "On the Fetch API documentation",
        "check_url_contains": "Fetch_API",
        "end_markers": {
            "url_contains": "Fetch_API",
            "host": "developer.mozilla.org",
            "deny": ["/search"],
        },
    },
    {
        "id": "wv_hackernews_top",
        "description": "Go to Hacker News and identify the title of the top story",
        "start_url": "https://news.ycombinator.com/",
        "expected_answer": "The title of the first story on the page",
        "judge_prompt": "The agent should report the title of the top story. Check that they identified a story title from the page.",
        "end_markers": {
            "host": "news.ycombinator.com",
            "answer_equals_selector": ".titleline a",
        },
    },
    {
        "id": "wv_bbc_weather",
        "description": "Go to BBC Weather and search for the weather in London",
        "start_url": "https://www.bbc.com/weather",
        "expected_answer": "Viewing London weather forecast",
        "check_url_contains": "london",
        "end_markers": {
            "url_contains": "london",
            "host": ["bbc.com", "bbc.co.uk"],
            "deny": ["/search"],
        },
    },
    {
        "id": "wv_npm_search",
        "description": "Search npm for the 'lodash' package and find its weekly download count",
        "start_url": "https://www.npmjs.com/",
        "expected_answer": "Found lodash download statistics",
        "check_url_contains": "lodash",
        "end_markers": {
            "url_contains": "lodash",
            "host": "npmjs.com",
            "deny": ["/search"],
        },
    },
    {
        "id": "wv_stackoverflow_question",
        "description": "Go to Stack Overflow and search for 'how to center a div' - find the most voted answer",
        "start_url": "https://stackoverflow.com/",
        "expected_answer": "Found a highly voted answer about centering divs",
        "judge_prompt": "The agent should have searched for centering divs and found an answer. Check that they navigated to a relevant question or search results.",
        "end_markers": {
            "host": "stackoverflow.com",
            "url_contains": "/questions/",
            "deny": ["/search"],
        },
    },
    {
        "id": "ho_mdn_array_map",
        "description": "Open the MDN documentation page for Array.prototype.map",
        "start_url": "https://developer.mozilla.org/en-US/",
        "expected_answer": "On the Array.prototype.map documentation",
        "check_url_contains": "Array/map",
        "end_markers": {
            "url_contains": "Array/map",
            "host": "developer.mozilla.org",
            "deny": ["/search"],
        },
    },
    {
        "id": "ho_github_rust",
        "description": "Open the rust-lang/rust repository page on GitHub",
        "start_url": "https://github.com/",
        "expected_answer": "On the rust-lang/rust repository",
        "check_url_contains": "rust-lang/rust",
        "end_markers": {
            "url_contains": "rust-lang/rust",
            "host": "github.com",
            "deny": ["/search"],
        },
    },
    {
        "id": "ho_arxiv_attention",
        "description": (
            "Open the arXiv abstract for the 2017 paper that introduced the Transformer, "
            "and report the paper title."
        ),
        "start_url": "https://arxiv.org/",
        "expected_answer": "Attention Is All You Need",
        "check_url_contains": "1706.03762",
        "end_markers": {
            "url_contains": "1706.03762",
            "host": "arxiv.org",
            "deny": ["/search"],
            "answer_in_text": "Attention Is All You Need",
        },
    },
    {
        "id": "ho_wiki_eiffel_city",
        "description": "Open the Wikipedia article for the Eiffel Tower and report the city it stands in",
        "start_url": "https://en.wikipedia.org/wiki/Main_Page",
        "expected_answer": "Paris",
        "check_text": "Paris",
        "end_markers": {
            "url_contains": "Eiffel_Tower",
            "host": "en.wikipedia.org",
            "deny": list(_WIKI_DENY),
            "answer_in_text": "Paris",
        },
    },
    {
        "id": "ho_nodejs_fs_docs",
        "description": "Open the Node.js documentation for the fs module",
        "start_url": "https://nodejs.org/api/",
        "expected_answer": "On the Node.js fs module documentation",
        "check_url_contains": "/fs.html",
        "end_markers": {
            "url_contains": "fs.html",
            "host": "nodejs.org",
            "path_suffix": "/fs.html",
            "deny": ["/search"],
        },
    },
    {
        "id": "ho_httpbin_customer_form",
        "description": (
            "Open the httpbin HTML form, submit it, and report the customer-name "
            "field's name exactly as the response body echoes it."
        ),
        "start_url": "https://httpbin.org/",
        "expected_answer": "custname",
        "check_url_contains": "httpbin.org/post",
        "end_markers": {
            "host": "httpbin.org",
            "path_suffix": "/post",
            "deny": ["/forms/"],
            "answer_in_text": "custname",
        },
    },
    {
        "id": "ho_pypi_requests",
        "description": (
            "Search PyPI for the requests library and open its project page. "
            "Do not stop on the search results."
        ),
        "start_url": "https://pypi.org/",
        "expected_answer": "On the requests project page",
        "check_url_contains": "/project/requests/",
        "end_markers": {
            "host": "pypi.org",
            "url_contains": "/project/requests/",
            "deny": ["/search"],
        },
    },
    {
        "id": "ho_rust_book_borrowing",
        "description": (
            "Starting from the Rust book table of contents, open the section "
            "on references and borrowing."
        ),
        "start_url": "https://doc.rust-lang.org/book/",
        "expected_answer": "On the references and borrowing section",
        "check_url_contains": "ch04-02-references-and-borrowing.html",
        "end_markers": {
            "host": "doc.rust-lang.org",
            "path_suffix": "/ch04-02-references-and-borrowing.html",
            "deny": ["/search"],
        },
    },
    {
        "id": "ho_w3c_selectors_4",
        "description": (
            "Starting from the W3C technical reports index, open the "
            "CSS Selectors Level 4 specification."
        ),
        "start_url": "https://www.w3.org/TR/",
        "expected_answer": "On the CSS Selectors Level 4 specification",
        "check_url_contains": "/TR/selectors-4/",
        "end_markers": {
            "host": "www.w3.org",
            "url_contains": "/TR/selectors-4/",
            "deny": ["/search", "search="],
        },
    },
    {
        "id": "ho_iana_status_451",
        "description": (
            "Open the IANA HTTP status code registry and report the description "
            "listed for status code 451."
        ),
        "start_url": "https://www.iana.org/",
        "expected_answer": "Unavailable For Legal Reasons",
        "check_url_contains": "http-status-codes",
        "end_markers": {
            "host": "iana.org",
            "url_contains": "http-status-codes",
            "deny": ["/search"],
            "answer_in_text": "Unavailable For Legal Reasons",
        },
    },
    {
        "id": "ho_rfc9110_get_section",
        "description": (
            "Open RFC 9110 and report the section number of the section "
            "that defines the GET method."
        ),
        "start_url": "https://www.rfc-editor.org/",
        "expected_answer": "9.3.1",
        "check_url_contains": "rfc9110",
        "end_markers": {
            "host": "rfc-editor.org",
            "url_contains": "rfc9110",
            "deny": ["/search"],
            "answer_in_text": "9.3.1",
        },
    },
    {
        "id": "ho_schema_person",
        "description": "Open the Schema.org type page for Person.",
        "start_url": "https://schema.org/",
        "expected_answer": "On the Schema.org Person type",
        "check_url_contains": "/Person",
        "end_markers": {
            "host": "schema.org",
            "path_suffix": "/Person",
            "deny": ["/search", "search_docs", "search="],
        },
    },
    {
        "id": "ho_cppreference_vector",
        "description": (
            "Search cppreference for std::vector and open its reference page. "
            "Do not stop on the search results."
        ),
        "start_url": "https://en.cppreference.com/w/cpp",
        "expected_answer": "On the std::vector reference page",
        "check_url_contains": "/cpp/container/vector",
        "end_markers": {
            "host": "en.cppreference.com",
            "path_suffix": "/cpp/container/vector",
            "deny": ["Special:Search", "action=search", "search="],
        },
    },
    {
        "id": "ho_sqlite_vacuum",
        "description": "From the SQLite documentation index, open the page for the VACUUM statement.",
        "start_url": "https://www.sqlite.org/docs.html",
        "expected_answer": "On the SQLite VACUUM statement page",
        "check_url_contains": "lang_vacuum.html",
        "end_markers": {
            "host": "sqlite.org",
            "path_suffix": "/lang_vacuum.html",
            "deny": ["/search"],
        },
    },
    {
        "id": "ho_k8s_pod",
        "description": "From the Kubernetes documentation home, open the concepts page for Pods.",
        "start_url": "https://kubernetes.io/docs/home/",
        "expected_answer": "On the Kubernetes Pods concepts page",
        "check_url_contains": "/docs/concepts/workloads/pods/",
        "end_markers": {
            "host": "kubernetes.io",
            "path_suffix": "/workloads/pods/",
            "deny": ["/search"],
        },
    },
]

# The three tasks the arms were tuned on. The held-out split stays disjoint.
TUNED_PROBE_TASK_IDS = (
    "wv_wikipedia_search",
    "wv_python_docs",
    "wv_hackernews_top",
)

# Step 2's five public tasks, plus the wider set. Not the tuned probe.
HELD_OUT_TASK_IDS = (
    "ho_mdn_array_map",
    "ho_github_rust",
    "ho_arxiv_attention",
    "ho_wiki_eiffel_city",
    "ho_nodejs_fs_docs",
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

SPLIT_PROBE = "probe"
SPLIT_HELD_OUT = "held-out"

BENCHMARK_TASKS = FIXTURE_TASKS + WEBVOYAGER_TASKS


def get_fixture_tasks() -> list[dict]:
    """Get only fixture tasks (for offline testing)."""
    return FIXTURE_TASKS


def get_webvoyager_tasks() -> list[dict]:
    """Get only WebVoyager tasks (require network)."""
    return WEBVOYAGER_TASKS


def get_all_tasks() -> list[dict]:
    """Get all benchmark tasks."""
    return BENCHMARK_TASKS


def markers_for_task(task_id: str) -> dict:
    """Judge-only markers for one task. Empty when the task has none.

    The model prompt must not include this dict.
    """
    for task in BENCHMARK_TASKS:
        if task["id"] == task_id:
            markers = task.get("end_markers") or {}
            return dict(markers)
    return {}


def _tasks_in_order(task_ids: tuple[str, ...]) -> list[dict]:
    wanted = set(task_ids)
    found = [task for task in WEBVOYAGER_TASKS if task["id"] in wanted]
    missing = wanted.difference(task["id"] for task in found)
    if missing:
        raise RuntimeError(f"tasks missing from the suite: {sorted(missing)}")
    order = {task_id: index for index, task_id in enumerate(task_ids)}
    return sorted(found, key=lambda task: order[task["id"]])


def resolve_task_split(spec: str | None) -> str:
    """probe is the tuned trio. held-out is the overfitting split."""
    key = (spec or SPLIT_PROBE).strip().casefold().replace("_", "-")
    if key in ("", "probe", "tuned", "default"):
        return SPLIT_PROBE
    if key in ("held-out", "heldout"):
        return SPLIT_HELD_OUT
    raise ValueError(f"unknown split {spec!r}")


def tasks_for_split(spec: str | None = None) -> list[dict]:
    """Tasks for one probe split. The default is the tuned trio."""
    name = resolve_task_split(spec)
    if name == SPLIT_HELD_OUT:
        return _tasks_in_order(HELD_OUT_TASK_IDS)
    return _tasks_in_order(TUNED_PROBE_TASK_IDS)


def get_held_out_tasks() -> list[dict]:
    """Held-out public tasks. Not the three tasks the arms were tuned on."""
    return tasks_for_split(SPLIT_HELD_OUT)
