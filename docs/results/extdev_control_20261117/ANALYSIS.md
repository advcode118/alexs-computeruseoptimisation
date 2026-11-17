# Replicate 1: offline audit

No paid runs or model calls were made during this audit. Ledger remains
**$6.277727**. `bench/grade.py` and all benchmark/runtime configuration are
unchanged. The only environment change was installing MCP's default Chrome.

## Failure census

Every attempted row is in `attempted_row_audit.csv` (128 rows). Full answers,
expected keys, final URLs, raw length limits, exact saved reasons, frozen replay
reasons, and self-checks are retained. `analysis_rep1.json` contains exact reason
counts, verifier history and cost/timing statistics. Budget-skipped rows excluded.

| Final result/category | BU default (22) | MCP (22) | Script (22) | Cascade (22) | BU ultrafast (40) |
|---|---:|---:|---:|---:|---:|
| PASS | 2 | 0 | 0 | 2 | 2 |
| Wrong/empty page URL | 9 | 0 | 15 | 9 | 19 |
| Browser unavailable, empty URL | 0 | 22 | 0 | 0 | 0 |
| Answer too long | 6 | 0 | 1 | 6 | 8 |
| Answer does not satisfy literal marker | 4 | 0 | 2 | 5 | 7 |
| Answer not in page text | 1 | 0 | 0 | 0 | 3 |
| Search page denied | 0 | 0 | 1 | 0 | 1 |
| Returned value not text | 0 | 0 | 1 | 0 | 0 |
| Returned evidence not on page | 0 | 0 | 1 | 0 | 0 |
| Harness result-metadata budget error | 0 | 0 | 1 | 0 | 0 |

The last category is a harness/runtime failure, not a frozen page-grade rule.
Replaying saved evidence through the frozen grader reproduces all 128 success
booleans. One reason differs: script Fiesta Texas saved its runtime metadata
budget error; the frozen page-only replay returns `answer too long`. The original
runtime-gated reason is deliberately preserved in the census.

## Reachable systematic issue: literal-span keys versus requested full answers

The split is wired to the correct key catalog, not an unrelated grader/key set:
`bench.openai_run._tasks` calls `bench.probe.probe_tasks`, which uses
`bench.tasks.tasks_for_split('extdev')`; the catalog is `bench/tasks_extdev.py`.
`bench.browser_use_arm._judge` delegates to `bench.probe.grade_observation`,
which calls `bench.grade.grade_observation` (probe lines 505 onward).
Script and MCP go through the same probe delegate. Cascade's fallback uses the
same browser-use arm. No alternate extdev grading-kind dispatch exists: its
value/filter/nav/search/spa kinds are metadata, while grading uses URL checks
and `end_markers`.

All 40 extdev tasks have literal answer markers: 18 partial keys and 22 full
keys. `bench/grade.py:388-420` requires the answer to contain the keyed literal,
be a short local span, and occur contiguously in the saved page text. In particular:

* Stripped raw answer length must be <= `3 * len(marker) + 40`.
* After limited wrapper/frame reductions, normalized excess over the marker
  must be <= `max(8, len(normalized marker))`.
* A semantically correct paraphrase or a multi-field answer assembled from
  separate page spans can fail even if all individual facts appear on-page.

These paths demonstrably executed in these runs: the saved reasons match frozen
replay; replacing ONLY the returned answer with the expected reference fragment
(discarding other original claims/completion flags) on the SAME saved URL/page
produces **13/22 BU-default, 13/22 cascade, 6/22 script, and 17/40 ultrafast**
page-grade passes. This is a counterfactual diagnostic, not revised benchmark
accuracy. It disproves an explanation based solely on wrong-page navigation or
unusable keys. Wrong pages, unavailable Chrome and actual script failures also
contribute, so there is not one cause for every failed row.

### Concrete examples

Task IDs below carry the `extdev_` prefix. Answers are truncated where indicated.

| Task / arm | Expected literal | Returned answer | Saved verdict / counterfactual |
|---|---|---|---|
| `value_nba_2021_leaders`, BU default | `Russell Westbrook` | `Points: Stephen Curry — 32.0; Assists: Russell Westbrook — 11.7; 3-Pointers Made: Stephen Curry — 5.3; ...` | FAIL `answer too long`: 186 chars > 91 raw limit. Literal-only reference passes on the same page. |
| `filter_frontiercity_family`, script | `Family` | `Billy's Frog Hopper; Frankie's Mine Train; Grand Carousel; Hootie's Tree House; ...` | Runtime PASS, frozen FAIL `answer too long`: 125 > 58. User asked for family rides; the category word rather than ride list is keyed. Reference passes on same page. |
| `value_icse_2004_chair`, BU default | `Anthony Finkelstein` | `May 23-28, 2004; Anthony Finkelstein` | FAIL `answer is not in the page text`. Combined date/name answer is not one contiguous page span; literal-only reference passes. |
| `nav_nets_schedule`, script | `Brooklyn Nets Schedule` | `https://www.espn.com/nba/team/schedule/_/name/bkn/brooklyn-nets` | Runtime PASS, frozen FAIL `answer does not satisfy the marker`. Navigation succeeded but returned URL is not the keyed heading; reference passes. |

### What the earlier model-free verification does and does not prove

`bench/verify_extdev.py:19,140-151` imports the runtime evidence grader from
`bench.script_first`, **not the frozen `bench.grade`**. Both direct-key and UI
reproducer checks explicitly supply `task['expected_answer']`, not a natural
answer to the original question. The runtime marker grader has no frozen
short-span length limits (`bench/script_first.py:734-758`). Thus historical
verification is not a frozen-grader/full-answer end-to-end validation.

`verification_extdev.jsonl` records 39/40 keys and 13/13 reproducers passing;
`verification_extdev_step3_keyfix.jsonl` records 40/40 keys and 11/13 reproducers.
Other historical files and their individual totals are included in the JSON.
All these JSONLs contain booleans/errors, **no original page text/returned
answers**, so the original live verification evidence cannot be replayed through
the frozen grader offline from these artifacts. No live verifier was run.

As a limited compatibility check, all **40/40** expected reference fragments
pass the frozen grader with the authored final URL and synthetic text equal to
that fragment. This tests logical key/URL/length compatibility, not live-page
validity. The original reference itself is not too long; fuller correct answers
can be. Saved run evidence provides the stronger, nonsynthetic counterfactual
checks above.

## Why script_first is 0/22

Final runtime self-check/end state: **6 PASS, 16 FAIL**, frozen/page diagnostic
**0/22**. Across all checks including repairs: **6 PASS, 29 FAIL**, with two
tasks recording no checks (HF first-user-message and TEI).

The 29 failed check records comprise 14 script execution/parser failures,
7 missing answers, 7 answers absent from page text, and 1 returned-evidence
failure. These are check counts, not distinct tasks; repairs can recover.

The six final runtime PASS rows subsequently fail grading as follows:

* Frontier City: answer too long.
* Airbnb Europe mansions: literal marker absent from answer.
* Ronaldo stats: final URL differs from the exact keyed URL.
* Nets schedule: returned URL does not contain the keyed answer heading.
* SpotHero marketing: careers landing page rather than keyed job-detail URL.
* Amazon puppy food: search/query/rating parameters differ from the exact key.

Runtime self-checks intentionally have no judge-only answer keys; probe applies
their PASS gate in addition to the frozen grade (`bench/probe.py:610-638`).
Here no row passed the page diagnostic either, so the own-verdict gate alone
does not explain zero accuracy.

## Browser-use cost and timing

| Attempted rows | N | Mean USD | Mean steps | Mean input tokens | Mean output tokens | Cached input share | Median wall_ms | Mean wall_ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Historical BU 1.0.0, different tasks | 50 | .014275 | 4.92 | 14461 | 373 | 73.78% | 13812.83 | 14719.06 |
| Default 1.0.6 | 22 | .074627 | 9.86 | 78279 | 881 | 76.38% | 26540.26 | 29455.11 |
| Ultrafast, paired first 22 | 22 | .053288 | 6.59 | 51268 | 416 | 64.18% | 27658.92 | 25295.52 |
| Ultrafast, all 40 | 40 | .077470 | 8.68 | 87121 | 558 | 74.18% | 27658.92 | 32220.88 |

Historical source: `docs/results/heldout_sol_medium_20261111.jsonl`. These are
different task sets and different browser-use versions; the data do not isolate
an upgrade effect. Current default has **5.41x input tokens**, **2.01x steps**,
and **2.36x output tokens**, with no aggregate cache-hit collapse.

The 1.0.6 internal LLM judge is enabled by default. Every completed current
browser-use run has a judge log: default invocation 42 judges (22 standalone +
20 cascade fallbacks), ultrafast 40. Installed `browser_use/agent/service.py:591-616`
actually invokes the judge before returning and adds its usage to result totals;
`agent/judge.py:144-159` uses the run model at low effort with trace/screenshots.
Our `await agent.run()` wall timer and `_priced_usage(result.usage)` therefore
include this overhead. Per-judge tokens/time and request counts are not retained
in these JSONL rows, so the judge's share of the increase is **not identifiable**.
Historical judge behavior was not established; do not attribute the whole
increase to a newly added judge.

**Additional reachable accounting issue:** installed
`browser_use/agent/loop.py:1210-1227` sums input across all responses; our
`bench/browser_use_arm.py:309-343` sends that aggregate into `price_usd`, whose
`bench/openai_spend.py:211` long-context threshold is intended for one request.
Two default tasks (Booking Times Square, Airbnb mansions) and two ultrafast tasks
(Ironhide arcade GDC, Airbnb castles) exceed 272k aggregate input and trigger
the multiplier. If every request were short-context, default BU total would be
$1.340581 instead of $1.641794 (mean ~$0.06094 rather than $0.07463), ultrafast
$2.728263 rather than $3.098815. Individual request sizes are not saved, so
these are sensitivity estimates, **not corrected bills**. No ledger/pricing
code was changed. This deserves a separate accounting fix before more runs.

The earlier default median of 11.7 s included 18 zero-time budget skips and
must not be compared to ultrafast's 40 real attempts. On the same 22 tasks,
ultrafast mean is ~14.1% faster, costs ~28.6% less, and uses fewer steps; its
median is slightly higher (27.66 vs 26.54 s). It is faster on 11/22 individual
tasks, with median paired delta -447 ms. The extra 18 ultrafast tasks average
40.69 s and $0.1070, raising its all-task mean. One sequential replicate cannot
establish a statistically reliable speed difference or isolate the AX mode's
causal effect from site/model variation.

## Environment-only MCP fix

Resolved installed pinned MCP 0.0.84 to its own Playwright dependency
`1.65.0-alpha-2026-10-30`, then ran:

```text
node ~/.npm/_npx/314abffa6aaf2cd1/node_modules/playwright/cli.js install chrome
Google Chrome 157.0.8103.78
```

Installer installed `google-chrome-stable`, including `/opt/google/chrome/chrome`.
No repo dependency, browser selection flag, symlink workaround, or shared
configuration was changed.

With API-key variables unset, instantiated the existing
`bench.harness.PlaywrightMCPClient(headless=True)` using its unchanged default
arguments. Navigated to `about:blank`, used `browser_evaluate` to create/read a
local h1, and verified its text and HeadlessChrome user agent:

```text
"text": "Offline MCP launch verified"
"userAgent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) HeadlessChrome/157.0.0.0 Safari/537.36"
PASS: pinned MCP default Chrome launched and DOM interaction succeeded; no model call
```

First smoke attempt used the unavailable name `browser_run_code`; switching to
the advertised `browser_evaluate` tool verified launch/interaction. The harness
emitted an ignored subprocess-transport `RuntimeError: Event loop is closed`
during teardown after the successful smoke. No runtime code was edited.

## Checks and recommendation

```text
Attempted rows audited: 128
Synthetic reference/marker compatibility: 40 /40 (not live evidence)
Stored-page frozen replay disagreements: 1
Ledger running_total_usd: 6.277727
49 passed in 0.18s
```

The one disagreement is reason-only, explained above; success booleans agree.
Test command: `.venv/bin/python -m pytest -q tests/test_grade_frozen.py`.
Frozen SHA256 remains
`0e65aecefd0d99f2313b6124495014f7ac2bd7acfb1e9c190a625eec12241752`.

Keep paid runs stopped. Decide how to align externally sourced, often
multi-field task outputs with literal-span grading, validate that offline, and
address per-request cost accounting before spending the remaining budget.
