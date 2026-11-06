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

WEBVOYAGER_TASKS = [
    {
        "id": "wv_wikipedia_search",
        "description": "Search Wikipedia for 'Ada Lovelace' and confirm you are on her article page",
        "start_url": "https://en.wikipedia.org/wiki/Main_Page",
        "expected_answer": "On the Ada Lovelace Wikipedia article",
        "check_url_contains": "Ada_Lovelace",
    },
    {
        "id": "wv_wikipedia_link",
        "description": "Go to the Wikipedia article for Python (programming language) and find the year it was first released",
        "start_url": "https://en.wikipedia.org/wiki/Main_Page",
        "expected_answer": "1991",
        "check_text": "1991",
    },
    {
        "id": "wv_arxiv_search",
        "description": "Search arXiv for 'attention is all you need' and identify the first author of the top result",
        "start_url": "https://arxiv.org/",
        "expected_answer": "Ashish Vaswani",
        "check_text": "Vaswani",
    },
    {
        "id": "wv_github_repo",
        "description": "Navigate to the microsoft/playwright GitHub repository and find the primary programming language",
        "start_url": "https://github.com/",
        "expected_answer": "TypeScript",
        "check_text": "TypeScript",
    },
    {
        "id": "wv_python_docs",
        "description": "Go to the Python documentation and find the page about the 'heapq' module",
        "start_url": "https://docs.python.org/3/",
        "expected_answer": "On the heapq module documentation page",
        "check_url_contains": "heapq",
    },
    {
        "id": "wv_mdn_search",
        "description": "Search MDN Web Docs for 'fetch API' and navigate to the main article",
        "start_url": "https://developer.mozilla.org/en-US/",
        "expected_answer": "On the Fetch API documentation",
        "check_url_contains": "Fetch_API",
    },
    {
        "id": "wv_hackernews_top",
        "description": "Go to Hacker News and identify the title of the top story",
        "start_url": "https://news.ycombinator.com/",
        "expected_answer": "The title of the first story on the page",
        "judge_prompt": "The agent should report the title of the top story. Check that they identified a story title from the page.",
    },
    {
        "id": "wv_bbc_weather",
        "description": "Go to BBC Weather and search for the weather in London",
        "start_url": "https://www.bbc.com/weather",
        "expected_answer": "Viewing London weather forecast",
        "check_url_contains": "london",
    },
    {
        "id": "wv_npm_search",
        "description": "Search npm for the 'lodash' package and find its weekly download count",
        "start_url": "https://www.npmjs.com/",
        "expected_answer": "Found lodash download statistics",
        "check_url_contains": "lodash",
    },
    {
        "id": "wv_stackoverflow_question",
        "description": "Go to Stack Overflow and search for 'how to center a div' - find the most voted answer",
        "start_url": "https://stackoverflow.com/",
        "expected_answer": "Found a highly voted answer about centering divs",
        "judge_prompt": "The agent should have searched for centering divs and found an answer. Check that they navigated to a relevant question or search results.",
    },
]

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
