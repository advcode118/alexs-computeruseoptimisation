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
        # No fixed title. The shared check reads the live first title link.
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
            "path_suffix": "/rust-lang/rust",
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
            "url_contains": "/abs/1706.03762",
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
            "url_contains": "/wiki/Eiffel_Tower",
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
    {
        "id": "ho_nav_py_inputoutput",
        "description": (
            "From the Python tutorial index, open the chapter about reading "
            "keyboard input and writing files."
        ),
        "start_url": "https://docs.python.org/3/tutorial/index.html",
        "expected_answer": "On the Python tutorial input and output chapter",
        "check_url_contains": "/tutorial/inputoutput.html",
        "end_markers": {
            "host": "docs.python.org",
            "path_suffix": "/tutorial/inputoutput.html",
            "url_contains": "/tutorial/inputoutput.html",
            "deny": ["/search", "search.html"],
        },
    },
    {
        "id": "ho_nav_py_sqlite3",
        "description": (
            "From the Python library index, open the documentation for the "
            "standard library's SQLite interface."
        ),
        "start_url": "https://docs.python.org/3/library/index.html",
        "expected_answer": "On the Python SQLite module documentation",
        "check_url_contains": "/library/sqlite3.html",
        "end_markers": {
            "host": "docs.python.org",
            "path_suffix": "/library/sqlite3.html",
            "url_contains": "/library/sqlite3.html",
            "deny": ["/search", "search.html"],
        },
    },
    {
        "id": "ho_nav_rust_result",
        "description": (
            "Starting from the Rust book table of contents, open the section "
            "on recoverable errors."
        ),
        "start_url": "https://doc.rust-lang.org/book/",
        "expected_answer": "On the recoverable errors section",
        "check_url_contains": "ch09-02-recoverable-errors-with-result.html",
        "end_markers": {
            "host": "doc.rust-lang.org",
            "path_suffix": "/ch09-02-recoverable-errors-with-result.html",
            "url_contains": "ch09-02-recoverable-errors-with-result.html",
            "deny": ["/search"],
        },
    },
    {
        "id": "ho_nav_k8s_service",
        "description": "From the Kubernetes documentation home, open the concepts page for the Service resource.",
        "start_url": "https://kubernetes.io/docs/home/",
        "expected_answer": "On the Kubernetes Service concepts page",
        "check_url_contains": "/services-networking/service/",
        "end_markers": {
            "host": "kubernetes.io",
            "path_suffix": "/services-networking/service/",
            "url_contains": "/services-networking/service/",
            "deny": ["/search"],
        },
    },
    {
        "id": "ho_nav_go_spec",
        "description": "From the Go documentation home, open the language specification.",
        "start_url": "https://go.dev/doc/",
        "expected_answer": "On the Go language specification",
        "check_url_contains": "/ref/spec",
        "end_markers": {
            "host": "go.dev",
            "path_suffix": "/ref/spec",
            "url_contains": "/ref/spec",
            "deny": ["/search"],
        },
    },
    {
        "id": "ho_nav_pg_select",
        "description": (
            "From the PostgreSQL current documentation, open the reference "
            "page for the statement that returns rows from a table."
        ),
        "start_url": "https://www.postgresql.org/docs/current/",
        "expected_answer": "On the PostgreSQL row-reading statement reference",
        "check_url_contains": "/sql-select.html",
        "end_markers": {
            "host": "postgresql.org",
            "path_suffix": "/sql-select.html",
            "url_contains": "/sql-select.html",
            "deny": ["/search"],
        },
    },
    {
        "id": "ho_nav_sqlite_pragma",
        "description": "From the SQLite documentation index, open the page that documents PRAGMA statements.",
        "start_url": "https://www.sqlite.org/docs.html",
        "expected_answer": "On the SQLite PRAGMA statement page",
        "check_url_contains": "pragma.html",
        "end_markers": {
            "host": "sqlite.org",
            "path_suffix": "/pragma.html",
            "url_contains": "pragma.html",
            "deny": ["/search"],
        },
    },
    {
        "id": "ho_nav_css_flex",
        "description": "From the MDN CSS reference, open the CSS flexible box layout module page (the overview of one-dimensional flexible layout).",
        "start_url": "https://developer.mozilla.org/en-US/docs/Web/CSS",
        "expected_answer": "On the MDN CSS flexible box layout module page",
        "check_url_contains": "CSS_flexible_box_layout",
        "end_markers": {
            "host": "developer.mozilla.org",
            "path_suffix": "/CSS_flexible_box_layout",
            "url_contains": "CSS_flexible_box_layout",
            "deny": ["/search"],
        },
    },
    {
        "id": "ho_form_selenium_received",
        "description": "Open the Selenium demonstration form, submit it, and report the confirmation heading.",
        "start_url": "https://www.selenium.dev/selenium/web/web-form.html",
        "expected_answer": "Received!",
        "check_url_contains": "/submitted-form.html",
        "end_markers": {
            "host": "www.selenium.dev",
            "path_suffix": "/submitted-form.html",
            "url_contains": "/submitted-form.html",
            "query_nonempty": True,
            "deny": ["/web-form.html", "/search"],
            "answer_in_text": "Received!",
        },
    },
    {
        "id": "ho_form_internet_secure",
        "description": (
            "Submit the login form using the credentials printed on the page, "
            "then report the flash message."
        ),
        "start_url": "https://the-internet.herokuapp.com/login",
        "expected_answer": "You logged into a secure area!",
        "check_url_contains": "://the-internet.herokuapp.com/secure",
        "end_markers": {
            "host": "the-internet.herokuapp.com",
            "path_suffix": "/secure",
            "url_contains": "://the-internet.herokuapp.com/secure",
            "deny": ["/login", "insecure", "/search"],
            "answer_in_text": "You logged into a secure area!",
        },
    },
    {
        "id": "ho_form_internet_email",
        "description": "Submit the password-reset form and report the confirmation sentence.",
        "start_url": "https://the-internet.herokuapp.com/forgot_password",
        "expected_answer": "Your e-mail's been sent!",
        "check_url_contains": "/email_sent",
        "end_markers": {
            "host": "the-internet.herokuapp.com",
            "path_suffix": "/email_sent",
            "url_contains": "/email_sent",
            "deny": ["/forgot_password", "/search"],
            "answer_in_text": "Your e-mail's been sent!",
        },
    },
    {
        "id": "ho_form_testpages_comments",
        "description": (
            "Submit the styled HTML form and report the name of the multiline "
            "field as the result page echoes it."
        ),
        "start_url": "https://testpages.herokuapp.com/styled/basic-html-form-test.html",
        "expected_answer": "comments",
        "check_url_contains": "/the_form_processor.php",
        "end_markers": {
            "host": "testpages.herokuapp.com",
            "path_suffix": "/the_form_processor.php",
            "url_contains": "/the_form_processor.php",
            "deny": ["/basic-html-form-test.html", "/search"],
            "answer_in_text": "comments",
        },
    },
    {
        "id": "ho_form_w3schools_action",
        "description": "From the HTML forms lesson, submit the example form. Do not stop on the lesson page.",
        "start_url": "https://www.w3schools.com/html/html_forms.asp",
        "expected_answer": "On the HTML form action result",
        "check_url_contains": "/action_page.php",
        "end_markers": {
            "host": "www.w3schools.com",
            "path_suffix": "/action_page.php",
            "url_contains": "/action_page.php",
            "query_nonempty": True,
            "deny": ["/html_forms.asp", "/search"],
        },
    },
    {
        "id": "ho_form_httpbin_phone",
        "description": (
            "Open the httpbin HTML form, submit it, and report the telephone "
            "field's name exactly as the response body echoes it."
        ),
        "start_url": "https://httpbin.org/",
        "expected_answer": "custtel",
        "check_url_contains": "://httpbin.org/post",
        "end_markers": {
            "host": "httpbin.org",
            "path_suffix": "/post",
            "url_contains": "://httpbin.org/post",
            "deny": ["/forms/", "/redirect", "/anything"],
            "answer_in_text": "custtel",
        },
    },
    {
        "id": "ho_find_wiki_gold",
        "description": (
            "Search Wikipedia for the element gold and report its atomic number. "
            "Do not stop on the search results."
        ),
        "start_url": "https://en.wikipedia.org/wiki/Main_Page",
        "expected_answer": "79",
        "check_url_contains": "/wiki/Gold",
        "end_markers": {
            "host": "en.wikipedia.org",
            "path_suffix": "/wiki/Gold",
            "url_contains": "/wiki/Gold",
            "deny": list(_WIKI_DENY),
            "answer_in_text": "79",
        },
    },
    {
        "id": "ho_find_wiki_wall",
        "description": (
            "Search Wikipedia for the Great Wall and report the country it stands in. "
            "Do not stop on the search results."
        ),
        "start_url": "https://en.wikipedia.org/wiki/Main_Page",
        "expected_answer": "China",
        "check_url_contains": "/wiki/Great_Wall_of_China",
        "end_markers": {
            "host": "en.wikipedia.org",
            "path_suffix": "/wiki/Great_Wall_of_China",
            "url_contains": "/wiki/Great_Wall_of_China",
            "deny": list(_WIKI_DENY),
            "answer_in_text": "China",
        },
    },
    {
        "id": "ho_find_pypi_urllib3",
        "description": (
            "Search PyPI for the HTTP library that the requests package is built on, "
            "and open its project page. Do not stop on the search results."
        ),
        "start_url": "https://pypi.org/",
        "expected_answer": "On the urllib3 project page",
        "check_url_contains": "/project/urllib3/",
        "end_markers": {
            "host": "pypi.org",
            "url_contains": "/project/urllib3/",
            "deny": ["/search"],
        },
    },
    {
        "id": "ho_find_npm_jest",
        "description": (
            "Search npm for the Jest test runner and open its package page. "
            "Do not stop on the search results."
        ),
        "start_url": "https://www.npmjs.com/",
        "expected_answer": "On the Jest package page",
        "check_url_contains": "/package/jest",
        "end_markers": {
            "host": "npmjs.com",
            "path_suffix": "/package/jest",
            "url_contains": "/package/jest",
            "deny": ["/search"],
        },
    },
    {
        "id": "ho_find_mdn_promise_all",
        "description": (
            "Search MDN for the Promise method that resolves once all of the given promises "
            "fulfil, or rejects as soon as one of them rejects, and open its reference page. "
            "Do not stop on the search results."
        ),
        "start_url": "https://developer.mozilla.org/en-US/",
        "expected_answer": "On the Promise.all reference",
        "check_url_contains": "/Promise/all",
        "end_markers": {
            "host": "developer.mozilla.org",
            "path_suffix": "/Promise/all",
            "url_contains": "/Promise/all",
            "deny": ["/search"],
        },
    },
    {
        "id": "ho_find_arxiv_resnet",
        "description": (
            "Search arXiv for the 2015 paper that introduced residual networks, "
            "and report the paper title. Do not stop on the search results."
        ),
        "start_url": "https://arxiv.org/",
        "expected_answer": "Deep Residual Learning for Image Recognition",
        "check_url_contains": "/abs/1512.03385",
        "end_markers": {
            "host": "arxiv.org",
            "path_suffix": "/abs/1512.03385",
            "url_contains": "/abs/1512.03385",
            "deny": ["/search"],
            "answer_in_text": "Deep Residual Learning for Image Recognition",
        },
    },
    {
        "id": "ho_find_crates_serde",
        "description": (
            "Search the Rust crate registry for the de-facto serialization crate "
            "and open its crate page. Do not stop on the search results."
        ),
        "start_url": "https://crates.io/",
        "expected_answer": "On the serde crate page",
        "check_url_contains": "/crates/serde",
        "end_markers": {
            "host": "crates.io",
            "path_suffix": "/crates/serde",
            "url_contains": "/crates/serde",
            "deny": ["/search"],
        },
    },
    {
        "id": "ho_page_wp_news",
        "description": "From the WordPress news index, open the second page of posts.",
        "start_url": "https://wordpress.org/news/",
        "expected_answer": "On the second page of WordPress news",
        "check_url_contains": "/news/page/2/",
        "end_markers": {
            "host": "wordpress.org",
            "path_suffix": "/news/page/2/",
            "url_contains": "/news/page/2/",
            "deny": ["/search"],
        },
    },
    {
        "id": "ho_page_github_blog",
        "description": "From the GitHub blog index, open the second page of posts.",
        "start_url": "https://github.blog/",
        "expected_answer": "On the second page of the GitHub blog",
        "check_url_contains": "/page/2/",
        "end_markers": {
            "host": "github.blog",
            "path_suffix": "/page/2/",
            "url_contains": "/page/2/",
            "deny": ["/search"],
        },
    },
    {
        "id": "ho_page_so_blog",
        "description": "From the Stack Overflow blog index, open the second page of posts.",
        "start_url": "https://stackoverflow.blog/",
        "expected_answer": "On the second page of the Stack Overflow blog",
        "check_url_contains": "/page/2/",
        "end_markers": {
            "host": "stackoverflow.blog",
            "path_suffix": "/page/2/",
            "url_contains": "/page/2/",
            "deny": ["/search"],
        },
    },
    {
        "id": "ho_page_jquery_blog",
        "description": "From the jQuery blog index, open the second page of posts.",
        "start_url": "https://blog.jquery.com/",
        "expected_answer": "On the second page of the jQuery blog",
        "check_url_contains": "/page/2/",
        "end_markers": {
            "host": "blog.jquery.com",
            "path_suffix": "/page/2/",
            "url_contains": "/page/2/",
            "deny": ["/search"],
        },
    },
    {
        "id": "ho_page_wp_core",
        "description": "From the WordPress core development blog, open the second page of posts.",
        "start_url": "https://make.wordpress.org/core/",
        "expected_answer": "On the second page of the core development blog",
        "check_url_contains": "/core/page/2/",
        "end_markers": {
            "host": "make.wordpress.org",
            "path_suffix": "/core/page/2/",
            "url_contains": "/core/page/2/",
            "deny": ["/search"],
        },
    },
    {
        "id": "ho_table_iana_https",
        "description": (
            "Open the IANA service name and port number registry and report "
            "the port number listed for HTTPS."
        ),
        "start_url": "https://www.iana.org/",
        "expected_answer": "443",
        "check_url_contains": "service-names-port-numbers",
        "end_markers": {
            "host": "iana.org",
            "url_contains": "service-names-port-numbers",
            "deny": ["/search"],
            "answer_in_text": "443",
        },
    },
    {
        "id": "ho_table_wiki_http_201",
        "description": (
            "Open the Wikipedia list of HTTP status codes and report the "
            "reason phrase for status 201."
        ),
        "start_url": "https://en.wikipedia.org/wiki/Main_Page",
        "expected_answer": "Created",
        "check_url_contains": "/wiki/List_of_HTTP_status_codes",
        "end_markers": {
            "host": "en.wikipedia.org",
            "path_suffix": "/wiki/List_of_HTTP_status_codes",
            "url_contains": "/wiki/List_of_HTTP_status_codes",
            "deny": list(_WIKI_DENY),
            "answer_in_text": "Created",
        },
    },
    {
        "id": "ho_table_calling_codes",
        "description": (
            "Open the Wikipedia list of country calling codes and report the "
            "calling code for Japan."
        ),
        "start_url": "https://en.wikipedia.org/wiki/Main_Page",
        "expected_answer": "+81",
        "check_url_contains": "/wiki/List_of_country_calling_codes",
        "end_markers": {
            "host": "en.wikipedia.org",
            "path_suffix": "/wiki/List_of_country_calling_codes",
            "url_contains": "/wiki/List_of_country_calling_codes",
            "deny": list(_WIKI_DENY),
            "answer_in_text": "+81",
        },
    },
    {
        "id": "ho_table_html_tr",
        "description": (
            "Open the Wikipedia article that lists HTML elements and report "
            "the element that forms one horizontal line of cells in a grid."
        ),
        "start_url": "https://en.wikipedia.org/wiki/Main_Page",
        "expected_answer": "Table row",
        "check_url_contains": "/wiki/HTML_element",
        "end_markers": {
            "host": "en.wikipedia.org",
            "path_suffix": "/wiki/HTML_element",
            "url_contains": "/wiki/HTML_element",
            "deny": list(_WIKI_DENY),
            "answer_in_text": "Table row",
        },
    },
    {
        "id": "ho_table_unicode_euro",
        "description": (
            "Open the Unicode names list for the currency symbols block and "
            "report the name of the character U+20AC."
        ),
        "start_url": "https://www.unicode.org/charts/",
        "expected_answer": "EURO SIGN",
        "check_url_contains": "/n_20A0.html",
        "end_markers": {
            "host": "www.unicode.org",
            "path_suffix": "/n_20A0.html",
            "url_contains": "/n_20A0.html",
            "deny": ["/search"],
            "answer_in_text": "EURO SIGN",
        },
    },
    {
        "id": "ho_open_go_fmt",
        "description": "Open the Go standard library documentation for the package that formats text.",
        "start_url": "https://pkg.go.dev/",
        "expected_answer": "On the Go formatting package documentation",
        "check_url_contains": "pkg.go.dev/fmt",
        "end_markers": {
            "host": "pkg.go.dev",
            "path_suffix": "/fmt",
            "url_contains": "pkg.go.dev/fmt",
            "deny": ["/search"],
        },
    },
    {
        "id": "ho_open_rust_vec",
        "description": "Open the Rust standard library page for the growable array type.",
        "start_url": "https://doc.rust-lang.org/std/",
        "expected_answer": "On the Rust growable array documentation",
        "check_url_contains": "struct.Vec.html",
        "end_markers": {
            "host": "doc.rust-lang.org",
            "path_suffix": "/vec/struct.Vec.html",
            "url_contains": "struct.Vec.html",
            "deny": ["/search"],
        },
    },
    {
        "id": "ho_open_redis_get",
        "description": (
            "Open the Redis command reference for the command that returns "
            "the string value stored at a key."
        ),
        "start_url": "https://redis.io/",
        "expected_answer": "On the Redis string-read command",
        "check_url_contains": "/commands/get/",
        "end_markers": {
            "host": "redis.io",
            "path_suffix": "/commands/get/",
            "url_contains": "/commands/get/",
            "deny": ["/search"],
        },
    },
    {
        "id": "ho_open_django_queries",
        "description": "Open the Django documentation for making database queries.",
        "start_url": "https://docs.djangoproject.com/en/stable/",
        "expected_answer": "On the Django database queries documentation",
        "check_url_contains": "/topics/db/queries/",
        "end_markers": {
            "host": "docs.djangoproject.com",
            "path_suffix": "/topics/db/queries/",
            "url_contains": "/topics/db/queries/",
            "deny": ["/search"],
        },
    },
]

# The three tasks the arms were tuned on. They stay inside the dev set.
TUNED_PROBE_TASK_IDS = (
    "wv_wikipedia_search",
    "wv_python_docs",
    "wv_hackernews_top",
)

# Public tasks we may tune on. Disjoint from the scored held-out set.
DEV_TASK_IDS = (
    "wv_wikipedia_search",
    "wv_wikipedia_link",
    "wv_arxiv_search",
    "wv_github_repo",
    "wv_python_docs",
    "wv_mdn_search",
    "wv_hackernews_top",
    "wv_bbc_weather",
    "wv_npm_search",
    "wv_stackoverflow_question",
)

# Step 2's five public tasks, plus the wider set. Not the dev set.
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
    "ho_nav_py_inputoutput",
    "ho_nav_py_sqlite3",
    "ho_nav_rust_result",
    "ho_nav_k8s_service",
    "ho_nav_go_spec",
    "ho_nav_pg_select",
    "ho_nav_sqlite_pragma",
    "ho_nav_css_flex",
    "ho_form_selenium_received",
    "ho_form_internet_secure",
    "ho_form_internet_email",
    "ho_form_testpages_comments",
    "ho_form_w3schools_action",
    "ho_form_httpbin_phone",
    "ho_find_wiki_gold",
    "ho_find_wiki_wall",
    "ho_find_pypi_urllib3",
    "ho_find_npm_jest",
    "ho_find_mdn_promise_all",
    "ho_find_arxiv_resnet",
    "ho_find_crates_serde",
    "ho_page_wp_news",
    "ho_page_github_blog",
    "ho_page_so_blog",
    "ho_page_jquery_blog",
    "ho_page_wp_core",
    "ho_table_iana_https",
    "ho_table_wiki_http_201",
    "ho_table_calling_codes",
    "ho_table_html_tr",
    "ho_table_unicode_euro",
    "ho_open_go_fmt",
    "ho_open_rust_vec",
    "ho_open_redis_get",
    "ho_open_django_queries",
)

SPLIT_PROBE = "probe"
SPLIT_DEV = "dev"
SPLIT_HELD_OUT = "held-out"
SPLIT_HONEST = "honest"
# The scored set is held-out only. Dev is what we tune, and it is not scored.
HONEST_TASK_IDS = HELD_OUT_TASK_IDS

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


def task_by_id(task_id: str) -> dict | None:
    """The catalog task, or None. Judge fields stay on this dict."""
    for task in BENCHMARK_TASKS:
        if task.get("id") == task_id:
            return task
    return None


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
    """probe is the tuned trio. dev is the wider tune set.

    held-out is the scored set. honest scores held-out and not dev.
    The default stays probe.
    """
    key = (spec or SPLIT_PROBE).strip().casefold().replace("_", "-")
    if key in ("", "probe", "tuned", "default"):
        return SPLIT_PROBE
    if key in ("dev", "development", "tune"):
        return SPLIT_DEV
    if key in ("held-out", "heldout"):
        return SPLIT_HELD_OUT
    if key == "honest":
        return SPLIT_HONEST
    raise ValueError(f"unknown split {spec!r}")


def tasks_for_split(spec: str | None = None) -> list[dict]:
    """Tasks for one probe split. The default is the tuned trio."""
    name = resolve_task_split(spec)
    if name == SPLIT_DEV:
        return _tasks_in_order(DEV_TASK_IDS)
    if name == SPLIT_HELD_OUT:
        return _tasks_in_order(HELD_OUT_TASK_IDS)
    if name == SPLIT_HONEST:
        return _tasks_in_order(HONEST_TASK_IDS)
    return _tasks_in_order(TUNED_PROBE_TASK_IDS)


def get_dev_tasks() -> list[dict]:
    """Public tasks we tune on. Not the held-out set we score."""
    return tasks_for_split(SPLIT_DEV)


def get_held_out_tasks() -> list[dict]:
    """Held-out public tasks. Not the tasks the arms were tuned on."""
    return tasks_for_split(SPLIT_HELD_OUT)


# Every arm reads the same task message. The answer line is the same for all
# of them, so no arm loses a value-match task on phrasing alone.
ANSWER_FORMAT = (
    "If the task asks for a value, such as a title, a name, or a number, "
    "give that exact value from the page as your answer, with no sentence around it."
)


def task_message(description: str, start_url: str) -> str:
    """The user message every arm gets: task, start URL, and the shared answer line."""
    return f"Task: {description}\n\nStart URL: {start_url}\n\n{ANSWER_FORMAT}"
