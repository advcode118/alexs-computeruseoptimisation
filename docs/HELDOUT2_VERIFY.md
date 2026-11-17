# Heldout2 public-page verification

Verified 2026-11-13 01:23 UTC with local headless Chromium.

This is page/marker validation, not an agent benchmark result. No LLM API calls or bench probes were run.
Authored using only AGENTS.md, bench/tasks.py, bench/probe.py, and the evidence grading/collection helpers in bench/script_first.py; no results, failure taxonomy, notes, temporary-directory files, or other branches were read.

Mix: 8 navigation, 8 value reports (including 2 title headings), 2 site searches, 2 submitted public demo forms.
All start pages returned HTTP 200 with real content and no challenge indicators. All navigated end pages returned HTTP 200. The calculator stays on its start URL and its calculation POST returned 200.
Evidence was collected by the runner's real collect_page_evidence (including its text cap), then graded by evidence_verdict with expected_answer as the claimed answer. Every expected answer was also checked for literal presence in that evidence.
For value/form answers different from the first h1, that h1 was separately claimed and had to grade FAIL. The two title tasks explicitly request the heading itself, so that negative control does not apply.
Searches used each site's search form and followed a result. Both forms were filled and submitted; the calculator answer also failed its marker before submission.

Reproduce: `python -m bench.verify_heldout2` (public network access; no model calls).

| Task id | Start status | End URL | Verdict | First-h1 claim |
| --- | --- | --- | --- | --- |
| ho2_nav_gutenberg_shelley | 200 | https://www.gutenberg.org/ebooks/84 | PASS | not a value task |
| ho2_nav_standardebooks_austen | 200 | https://standardebooks.org/ebooks/jane-austen/sense-and-sensibility | PASS | not a value task |
| ho2_nav_cc_attribution | 200 | https://creativecommons.org/licenses/by/4.0/ | PASS | not a value task |
| ho2_nav_apache_license | 200 | https://www.apache.org/licenses/LICENSE-2.0 | PASS | not a value task |
| ho2_nav_nginx_beginner | 200 | https://nginx.org/en/docs/beginners_guide.html | PASS | not a value task |
| ho2_nav_git_branching | 200 | https://git-scm.com/book/en/v2/Git-Branching-Basic-Branching-and-Merging | PASS | not a value task |
| ho2_nav_curl_manual | 200 | https://curl.se/docs/manpage.html | PASS | not a value task |
| ho2_nav_pytest_setup | 200 | https://docs.pytest.org/en/stable/how-to/fixtures.html | PASS | not a value task |
| ho2_value_iban_japan | 200 | https://www.iban.com/currency-codes | PASS | FAIL |
| ho2_value_color_rebecca | 200 | https://www.w3schools.com/colors/colors_names.asp | PASS | FAIL |
| ho2_value_dns_type | 200 | https://www.iana.org/assignments/dns-parameters | PASS | FAIL |
| ho2_value_sqlite_busy | 200 | https://www.sqlite.org/rescode.html | PASS | FAIL |
| ho2_value_si_deka | 200 | https://www.nist.gov/pml/owm/metric-si-prefixes | PASS | FAIL |
| ho2_value_rfc_status | 200 | https://www.rfc-editor.org/info/rfc8259/ | PASS | FAIL |
| ho2_title_gutenberg_carroll | 200 | https://www.gutenberg.org/ebooks/11 | PASS | same as requested heading |
| ho2_title_standardebooks_wells | 200 | https://standardebooks.org/ebooks/h-g-wells/the-time-machine | PASS | same as requested heading |
| ho2_search_sphinx_toctree | 200 | https://www.sphinx-doc.org/en/master/usage/restructuredtext/directives.html#directive-toctree | PASS | not a value task |
| ho2_search_flask_blueprints | 200 | https://flask.palletsprojects.com/en/stable/blueprints/ | PASS | not a value task |
| ho2_form_expand_ticket | 200 | https://practice.expandtesting.com/form-confirmation | PASS | FAIL |
| ho2_form_calculator_sum | 200 | https://testpages.eviltester.com/apps/server-side-calculator/ | PASS | FAIL |

## Candidates dropped before finalization

- GNU GPL/coreutils pages: repeated connection resets/timeouts and an HTTP 429 in headless Chromium.
- Python Packaging User Guide site search: no visible matching result appeared within the verification timeout; replaced with Flask's working site search.
- nginx keepalive timeout value: the value was outside the runner's capped trusted text, so it could not be verified by the required grading path.
- RFC directory URL (`/rfc/`): HTTP 404; the task starts at the working RFC Editor home instead.
