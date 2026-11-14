"""dev4spa: twelve public dynamic-page tasks for the spa specialist. Not a scored set.

Each task needs JavaScript to render the answer, or a click (tab, accordion,
toggle, select, repeated button) to reveal it. At most two tasks per site, no
host from the shared used-hosts list. Answers are literal page text, and end
markers are judge-only. Live checks are in bench/verify_dev4_spa.py.
"""

from __future__ import annotations


def _task(task_id, description, start_url, expected, host, url_contains, *, deny=()):
    return {
        "id": task_id,
        "description": description,
        "start_url": start_url,
        "expected_answer": expected,
        "check_url_contains": url_contains,
        "end_markers": {
            "host": host,
            "url_contains": url_contains,
            "deny": ["/search", *deny],
            "answer_in_text": expected,
        },
    }


DEV4_SPA_TASKS = [
    # Client-routed tab views of an Angular app.
    _task(
        "dev4spa_spa_deps_react_dependency",
        "On Open Source Insights, open the dependencies view for the npm package react at version 18.2.0 and report the name of its only direct dependency.",
        "https://deps.dev/npm/react/18.2.0",
        "loose-envify", "deps.dev", "/npm/react/18.2.0/dependencies",
    ),
    _task(
        "dev4spa_spa_deps_requests_urllib3",
        "On Open Source Insights, open the requirements of the PyPI package requests version 2.31.0 and report the version constraint it places on urllib3.",
        "https://deps.dev/pypi/requests/2.31.0",
        "<3,>=1.21.1", "deps.dev", "/pypi/requests/2.31.0/requirements",
    ),
    # A to-do app: toggle one item and read the live counter.
    _task(
        "dev4spa_js_cypress_todo_left",
        "In the Cypress kitchen-sink to-do app, mark the 'Pay electric bill' to-do as done and report the item counter shown under the list.",
        "https://example.cypress.io/todo",
        "1 item left", "example.cypress.io", "/todo",
    ),
    # A repeated click until the view model disables the button.
    _task(
        "dev4spa_js_knockout_clicks",
        "On Knockout's click counter example, keep clicking its button until the example stops you, then report the line that says how many times you clicked.",
        "https://knockoutjs.com/examples/clickCounter.html",
        "You've clicked 3 times", "knockoutjs.com", "/examples/clickCounter.html",
    ),
    # htmx: a select that fetches options, and tabs that swap in content.
    _task(
        "dev4spa_js_htmx_toyota_models",
        "On the htmx cascading selects example, change the live demo's make to Toyota and report the last model it then offers.",
        "https://htmx.org/examples/value-select/",
        "Yaris", "htmx.org", "/examples/value-select/",
    ),
    _task(
        "dev4spa_js_htmx_tab_two",
        "On the htmx tabs (HATEOAS) example, open Tab 2 in the live demo and report the first three words of its text.",
        "https://htmx.org/examples/tabs-hateoas/",
        "Kitsch fanny pack", "htmx.org", "/examples/tabs-hateoas/",
    ),
    # Hash-routed documentation rendered in the browser.
    _task(
        "dev4spa_spa_docsify_serve",
        "In the docsify documentation, open the Quick start guide and report the local address where docsify serve lets you preview your site.",
        "https://docsify.js.org/",
        "http://localhost:3000", "docsify.js.org", "#/quickstart",
    ),
    # Tabs without tab roles in a client-rendered Vue app.
    _task(
        "dev4spa_spa_naiveui_beatles",
        "On Naive UI's Tabs component page, switch the first demo to the Beatles tab and report the song title it shows.",
        "https://www.naiveui.com/en-US/os-theme/components/tabs",
        "Hey Jude", "naiveui.com", "/components/tabs",
    ),
    # A jQuery accordion.
    _task(
        "dev4spa_js_jqueryui_section_three",
        "On the jQuery UI default accordion demo, open Section 3 and report the first item of the bulleted list inside it.",
        "https://jqueryui.com/resources/demos/accordion/default.html",
        "List item one", "jqueryui.com", "/accordion/default.html",
    ),
    # A value that exists only once the app has rendered.
    _task(
        "dev4spa_spa_artifacthub_nginx_app",
        "On Artifact Hub, open the Bitnami nginx Helm chart at chart version 15.0.0 and report the application version that chart release packages.",
        "https://artifacthub.io/packages/helm/bitnami/nginx/15.0.0",
        "1.25.0", "artifacthub.io", "/nginx/15.0.0",
    ),
    # jQuery tabs: the panel text is hidden until its tab is chosen.
    _task(
        "dev4spa_js_jqueryui_tab_three",
        "On the jQuery UI default tabs demo, open the Aenean lacinia tab and report the first sentence of its text.",
        "https://jqueryui.com/resources/demos/tabs/default.html",
        "Mauris eleifend est et turpis", "jqueryui.com", "/tabs/default.html",
    ),
    # Web-component tabs behind a page-load dialog.
    _task(
        "dev4spa_js_shoelace_advanced",
        "On Shoelace's tab group component page, switch the first example to its Advanced tab and report the sentence shown in that tab's panel.",
        "https://shoelace.style/components/tab-group",
        "This is the advanced tab panel", "shoelace.style", "/components/tab-group",
    ),
]

DEV4_SPA_TASK_IDS = tuple(task["id"] for task in DEV4_SPA_TASKS)
