# Cascade warm-handoff smoke, 17 November 2026

Authorized three-task extdev smoke, Sol medium, browser-use 1.0.6 default mode.
This is a wiring smoke, not an accuracy claim. No protected claim-set file was
opened or run.

## Reproduction

```bash
source .venv/bin/activate
export PATH="$HOME/.nvm/versions/node/v24.22.2/bin:$PATH"
export CU_OPENAI_SPEND_LEDGER="$HOME/.cu-optimisation/openai-spend-alex15.json"
export CU_OPENAI_PROJECT_BUDGET_USD=9.00
export CU_OPENAI_RUN_BUDGET_USD=2.00
env -u CU_BU_MODE python tools/cascade_smoke.py
```

Requires the separately provisioned OpenAI key. Do not run without approval.
The script selects exactly the three task IDs below and uses the existing
budgeted probe executor and token ledger. Caps are checked between tasks.

## Bug found and fixed before paid execution

An offline real-Chromium/CDP reproduction showed that `Browser(cdp_url=...)`
connected to the same Chrome but its daemon created/selected a new blank tab.
The script target was `856AB54751631B21BC618130F587705C`; browser-use's initial
target was `2E4B08CBCA175375B859EE8EC764AAFA`, URL `about:blank`.
`browser._local is None`, so this was not a fresh Chrome process; it was the
wrong tab within the original browser. Merely supplying the CDP endpoint and
current URL in the prompt was insufficient.

The cascade now obtains the script page's CDP target ID, explicitly attaches
the daemon session to that target, and remembers it before constructing the
agent. Rows persist both sides' endpoint/target/URL and the exact handoff
receipt sent as the agent task. The receipt contains the original task,
current URL, visited URLs, and sanitized reason, not script answers or judge
markers. The real-browser regression test additionally checks that an edited
input value survives and that a second browser.start() retains the target.

## Paid results

Raw rows: `probe_20261117_011924.jsonl`; model action log: `run.log`.
All three naturally handed off; no forced paid handoff or retry was needed.

| Task ID suffix (all prefixed extdev_value_) | answered_by | handoff_reason | wall_ms | usd | Frozen-grade pass |
|---|---|---|---:|---:|---|
| hf_tei_strengths | browser_use | multiline_answer | 21711.941442 | 0.027929 | false |
| cambridge_gestalt | browser_use | self-check FAIL | 15660.306131 | 0.034038 | false |
| icse_2002_chairs | browser_use | self-check UNKNOWN | 18698.481326 | 0.043332 | false |

All three fail the independent frozen grader with `answer too long`, despite
browser-use's own internal judge reporting success. Grading and prompts were
not modified to change these outcomes.

### Warm-attach evidence

For every row, `handoff_cdp_url == browser_use_cdp_url`,
`handoff_target_id == browser_use_initial_target_id`, and
`handoff_url == browser_use_initial_url`. Each initial URL also appears in the
actual first model-written `page_info()` output, saved separately below:

| Task | Script handoff URL = browser-use first page_info URL | Shared target ID | First-cell evidence |
|---|---|---|---|
| HF | https://huggingface.co/docs/text-embeddings-inference/index | 312ABC45A3E9488ED000D8867F79E427 | hf_first_cell.txt |
| Cambridge | https://dictionary.cambridge.org/dictionary/english/gestalt | 008D91C796130E940E0717AB604B7B9A | cambridge_first_cell.txt |
| ICSE | http://www.icse-conferences.org/2002/index.html | D5D84456222E3228C4A31E8823370662 | icse_first_cell.txt |

These differ from the tasks' original site-root start URLs. The agent's first
action reads the existing page rather than navigating to the site root.

## Spend and offline checks

Read directly from the ledger after this smoke:

- Task usage sum: **$0.105299**.
- Existing fresh-ledger opening allowance: **$0.050000**.
- Running ledger total: **$0.155299**.
- Project cap: $9; per-run cap: $2; aborted: false.

Full safe suite after all code changes:

```text
pytest -q bench/test_harness.py tests --deselect=tests/test_extdev.py::test_site_cap_and_disjoint_from_every_other_catalog_task_and_heldout4
1124 passed, 1 deselected in 29.03s
```

The deselected test would read the prohibited candidate file. The prior
collection failure is fixed by restoring `get_all_tasks()` as a copied list of
the current `BENCHMARK_TASKS` catalog. No additional catalog is loaded.

Focused cascade/browser-use regression tests:

```text
31 passed in 1.77s
```
