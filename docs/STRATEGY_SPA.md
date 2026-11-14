# Dynamic-page specialist (opt-in)

Draft contribution against `t3/tip3`. Runtime baseline: `56fbcab`; the merged
`bec55ab` update is documentation only. First measured specialist: `14d0533`.
Final candidate: `f023565` (adds adjacent-label transparent checkbox observation).

## Recommendation: park integration

Retain this draft as an opt-in experimental candidate, but **park integration
and default enablement**. The final pair improves the shared grade from 10/12
to 11/12 and median wall time from 11.08s to 4.99s. Strict task compliance is
still 10/12, with one manually identified false accept (8.3%). The requested
90% accuracy / under-5% false-accept bar is not met, and this authored,
previously exercised development set cannot establish generalization.

The queued final benchmark and suite were recovered from their completed saved
outputs; neither was relaunched during compact continuation. No further API
spend was incurred. Useful mechanisms and remaining failure causes are below.

## Mechanism

1. `CU_SF_STRATEGY=spa` enables a cheap router: interaction language plus a
   bounded HTTP read detecting nearly empty JavaScript app shells. Framework
   markers on a substantial server-rendered page alone do not trigger it.
2. Load the real browser page and wait for a fresh DOM/network quiet window
   (300 ms), bounded at 5 seconds on load and 2.5 seconds after actions.
3. Show rendered control numbers, names, roles, states, options, and visible
   text to the model. Rank task-matching controls before the 140-control cap.
4. Execute structured actions, settling after each. Re-observe after navigation;
   compare current visible lines with the initial page. At most three model
   calls and two action rounds; the action budget is 25 seconds. An in-flight
   model call retains the model client's timeout rather than being cancelled
   with unaccounted usage.
5. Accept only a visible answer grounded in changed text after interaction (or
   non-chrome rendered text for a read-only task), then require the inherited
   runtime self-check. Failure returns to the generic path with its full repair
   time allowance. All specialist calls/tokens/time remain in the row totals.

The runtime module receives only the task description, start URL, browser, and
model client. It does not receive a task id, expected answer, or grade markers.
The final grade is the existing shared grade. Successful rows say `strategy=spa`;
attempted handbacks say `spa_fallback`. `strategy_detail` records routing,
actions, model choices, and the specialist's own outcome separately from fallback.

## Protocol and limitations

- Twelve `dev4spa` tasks were written and verified before the implementation,
  spanning nine hosts and Angular/React/Vue/Knockout/htmx/jQuery/web components
  and hash-routed documentation. The task-author verifier passed 12/12 twice
  in the preceding session (including negative checks).
- The preceding implementation session also manually exercised these pages.
  Its hand-picked mechanics result was 13/16 across dev3 + dev4spa. Thus the
  first model checkpoint below is **not a pristine unseen-page evaluation**.
  It is the first Luna measurement of this candidate on the authored tasks.
- Paired measurements alternate off/on in the same checkout, Luna medium,
  script_first only, grounded repair enabled. Managed jobs use the single-slot
  wrapper. Timings include all attempts and fallback, not successful rows only.
- The permitted older splits (`dev`, `held-out`, `heldout2`) contain **zero**
  tasks whose kind is `spa` or `js`. Their 80 descriptions/URLs are included in
  the router negative set; there is no older dynamic-task pass-rate denominator.
- Protected gate task files, tests, and results are excluded from investigation
  and test collection. No grader changes or site/task rules are introduced.
- Specialist calls have no answer-key access; local browser tests tripwire
  `markers_for_task` throughout both specialist success and generic fallback.

## Router audit

On all **132** permitted development/older task descriptions and live start
URLs: **16 true positives, 116 true negatives, 0 false positives, 0 misses**.
Precision and recall were both **100%** on this development pool. HTTP fetch
median was **194 ms**, with one fetch error; the text-cue/fallback path kept
classification correct. This is a development audit, not an unseen gate result.
The router sees description and HTML signals only; task ids supply audit labels
outside the implementation.

## Evidence

The dev3 checkpoint passed **3/4 off and 3/4 on**, with no false accepts in
either arm. The specialist itself completed three tasks; DevDocs handed back
after selecting navigation entries and returning `Array.flat`, a navigation
label. Its subsequent generic fallback also failed. This is not evidence of an
accuracy improvement on dev3.

All times below cover **every task**, including failures and generic fallback.
P90 is the nearest-rank percentile. False accepts mean runtime PASS but shared
grade FAIL; this does not detect every wording/formatting mistake (see below).

| Split / checkpoint | Mode | Pass | False accepts | Wall median / mean / p90 (s) | Model calls median / mean | USD/task |
|---|---|---:|---:|---:|---:|---:|
| dev3 | Off | 3/4 | 0/4 | 6.75 / 7.38 / 10.01 | 2 / 2.50 | 0.000681 |
| dev3 | On | 3/4 | 0/4 | 7.57 / 10.13 / 18.53 | 2.5 / 3.50 | 0.001411 |
| dev4spa, first model contact | Off | 10/12 | 0/12 | 10.55 / 11.87 / 20.97 | 3 / 2.75 | 0.001004 |
| dev4spa, first model contact | On | 10/12 | 0/12 | 5.58 / 8.32 / 19.04 | 2 / 2.50 | 0.000737 |
| dev4spa, final post-fix | Off | 10/12 | 0/12 | 11.08 / 12.40 / 21.11 | 2.5 / 2.67 | 0.000915 |
| dev4spa, final post-fix | On | 11/12 | 0/12 | 4.99 / 8.17 / 15.57 | 2 / 2.42 | 0.000364 |

At first contact, the specialist accepted 13/16 tasks directly; all 13 passed
the shared grader. Its three handbacks also failed in generic fallback. In
dev4spa, it rescued the web-component tabs task but lost the to-do counter task.
First checkpoint spend: **$0.029256**. No accuracy gain is established by these
first-contact pairs. On dev4spa the median fell 47%, but this is one small pair
on a shared machine, not a reliable deployment-speed estimate.

Final dev4spa: **10 specialist acceptances + 1 successful generic fallback =
11/12 graded passes**. The to-do action now works, but its correct changed
counter sits in an application footer and is rejected as chrome; generic
fallback rescues it. Component-title rejection remains the other handback and
does not recover. The four-versus-three-word formatting miss persists: **10/12
strict compliance**, not 11/12. That is one manually identified false accept
(8.3% of tasks) despite zero grader-defined false accepts. The 90% accuracy and
under-5% false-accept targets are therefore **not demonstrated under strict task
compliance**. This stays opt-in. Dev3 was not remeasured after the checkbox-only
fix; its first pair is the available evidence, not a final-code rerun.

Total probe spend: **$0.044604**; dev-h ledger **$5.881834 → $5.926438**. No other
model/API probes were run. No protected gate was opened or executed.

### First-contact per-task record

`P`/`F` is the shared grade. Each cell is **grade; seconds; model calls**.
The committed JSONL also records generic script steps and the structured
specialist action list (including repeated click counts).

| Task suffix | Off | On |
|---|---|---|
| dev3: devdocs_flat | F; 10.01; 4 | F; 18.53; 7 |
| dev3: elm_repeat | P; 6.03; 2 | P; 7.47; 3 |
| dev3: letcode_total | P; 7.39; 2 | P; 7.68; 2 |
| dev3: demoqa_origin | P; 6.11; 2 | P; 6.83; 2 |
| deps_react_dependency | P; 11.50; 3 | P; 7.03; 2 |
| deps_requests_urllib3 | P; 9.60; 3 | P; 9.43; 2 |
| cypress_todo_left | P; 7.37; 3 | F; 19.04; 5 |
| knockout_clicks | P; 17.50; 4 | P; 5.15; 2 |
| htmx_toyota_models | P; 20.66; 4 | P; 6.01; 2 |
| htmx_tab_two | P; 6.91; 2 | P; 4.59; 2 |
| docsify_serve | P; 5.46; 2 | P; 4.81; 2 |
| naiveui_beatles | F; 21.56; 4 | F; 23.32; 6 |
| jqueryui_section_three | P; 11.64; 2 | P; 4.17; 2 |
| artifacthub_nginx_app | P; 5.93; 2 | P; 4.00; 1 |
| jqueryui_tab_three | P; 3.32; 1 | P; 4.54; 2 |
| shoelace_advanced | F; 20.97; 3 | P; 7.74; 2 |

### Final dev4spa per-task record

Cells are **grade; seconds; model calls; logged tool groups**. A successful
specialist is one aggregate tool group containing its actual action list;
tool groups are not interchangeable with individual browser interactions.

| Task suffix | Off | On | Specialist browser interactions |
|---|---|---|---|
| deps_react_dependency | P; 13.09; 3; 3 | P; 7.78; 2; 1 | 1 click |
| deps_requests_urllib3 | P; 12.07; 3; 3 | P; 4.42; 2; 1 | 1 click |
| cypress_todo_left | P; 7.86; 3; 3 | P; 15.57; 4; 2 | 1 check, then generic fallback |
| knockout_clicks | F; 32.84; 4; 4 | P; 5.01; 2; 1 | 3 repeated clicks |
| htmx_toyota_models | P; 18.83; 4; 4 | P; 4.96; 2; 1 | 1 select |
| htmx_tab_two | P; 5.89; 2; 2 | P; 6.50; 2; 1 | 1 click; formatting miss |
| docsify_serve | P; 5.92; 2; 2 | P; 4.95; 2; 1 | 1 click |
| naiveui_beatles | F; 11.65; 4; 3 | F; 28.03; 6; 4 | 1 click, then generic fallback |
| jqueryui_section_three | P; 10.52; 2; 2 | P; 4.70; 2; 1 | 1 click |
| artifacthub_nginx_app | P; 5.62; 2; 2 | P; 4.31; 1; 1 | Rendered read only |
| jqueryui_tab_three | P; 3.40; 1; 1 | P; 3.75; 2; 1 | 1 click |
| shoelace_advanced | P; 21.11; 2; 2 | P; 8.01; 2; 1 | 1 click, overlay dismissal on interception |

### What worked, and what did not

- **Keep bounded settling:** the local delayed-render test found a real bug
  where a quiet DOM *before* an action could cause an immediate return. A fresh
  quiet window fixes that. The render-only chart-version task used one model
  call at 4.00s. Waiting's isolated contribution is **not measured**.
- **Keep rendered choices and batched actions:** ten dev4spa tasks completed
  directly on the first candidate; the repeated counter used one action choice
  for three clicks, and the cascading select used its actual option label.
- **Keep iterative observations and click-based routes:** dependencies,
  requirements, hash-routed docs, and package/module navigation passed. No
  complete one-call-plan versus iterative ablation was run; no superiority
  claim is made for the three-call cap.
- **Keep changed-text and chrome rejection:** DevDocs returned `Array.flat`
  from navigation rather than the requested entry title. It was rejected, but
  two action rounds did not reach the correct content. This remains unresolved.
- **Transparent checkboxes:** associated-label support was insufficient. The
  first candidate could not see the to-do checkbox and gave up. The final
  candidate also recognizes a directly adjacent visible label, while using the
  input's real checked state and Playwright hit testing. Covered by a local
  browser regression test, then remeasured on the whole dev4spa checkpoint.
- **Component title false rejection remains:** the specialist returned the
  correct changed song title, but the inherited runtime check requires overlap
  with the document title. It stays a FAIL; that check is not bypassed.
- **Formatting is not fully verified:** the first htmx tab answer contained
  four words when the user requested three. The existing substring grader
  accepted it. Manual strict task compliance for that first on run is at most
  **9/12**, despite its 10/12 graded count. The grader is unchanged.
- **Fallback costs:** it preserves the generic algorithm and its repair-time
  allowance, but spends additional calls and time and cannot guarantee an
  identical stochastic outcome to a separate off run. No default enablement
  is justified by these measurements.

Paired rows and the router audit are committed under
`docs/results/strategy_spa_20261114/`. The planned measurements are complete.
Further work needs better content-region attribution, exact output-format
validation, navigation depth/re-observation, and an independent gate before
considering default enablement.

## Reproduction

In Git Bash, with the approved local key kept out of output:

```sh
export OPENAI_API_KEY="$(cat C:/Users/epicd/.cu-optimisation/openai.key)"
export CU_OPENAI_SPEND_LEDGER=C:/Users/epicd/.cu-optimisation/openai-spend-dev-h.json
export CU_PROBE_SLOTS=1
# Run off then on, first for dev3, then for dev4spa:
CU_SF_STRATEGY= sh C:/Users/epicd/.cu-optimisation/probe_slot.sh python -m bench.probe --execute --split dev3 --only-kind spa,js --arms script_first --provider openai --model gpt-6-luna --effort medium
CU_SF_STRATEGY=spa sh C:/Users/epicd/.cu-optimisation/probe_slot.sh python -m bench.probe --execute --split dev3 --only-kind spa,js --arms script_first --provider openai --model gpt-6-luna --effort medium
```

The checkpoint driver calls the same `execute_probe` entry point with these
arguments, serially under one slot, retaining the off/on rows separately.
Opening dev-h ledger: **$5.881834** (inherited project spend, not this specialist's
bill). This contribution has a maximum **$1 increment**. Parent's recovered
project total across ledgers was approximately $7.19 before these runs.

## Checks

Final candidate: **840 passed, 1 skipped in 46.42s**. This is the full permitted
collection through the managed wrapper (this job requested one slot), excluding
the protected gate tests. The shared wrapper remains configured for two slots.
The final checkbox regression also passed its focused run: **8 passed in 9.12s**.
The broader focused set before that last fix gave **22 passed in 7.35s**.

Focused command: `python -m pytest -q tests/test_strategy_spa.py tests/test_dev4_spa.py tests/test_script_cache.py`.

Full permitted test collection:

```sh
CU_PROBE_SLOTS=1 sh C:/Users/epicd/.cu-optimisation/probe_slot.sh python -m pytest -q --ignore-glob='tests/test_heldout3*' --ignore-glob='tests/test_val3*'
```

### Test-count reconciliation and ancestry

- Fresh `git fetch github t3/tip3 t3/strategy-spa` resolves tip3 to
  `bec55abe93c7b26f206142e21827e50ad362b8cd`. That exact commit is an ancestor
  of measured/report head `7e2df498f2977ce92e0a3dd26f92858069ab122a`; there are
  zero tip3 commits missing from this branch. No integration merge was made.
- Against that tip3 tree, the only test changes are two added SPA test files:
  eight strategy cases and two catalog cases. No baseline test or pytest
  collection configuration was removed or changed.
- Collection-only, with the same protected-file exclusions and the two SPA
  files additionally excluded, gives **831 baseline test items** in 0.41s.
  Adding the ten SPA cases gives **841 items = 840 passed + 1 skipped** in the
  completed suite.
- The reported tip3 baseline is 876 passes. The apparent 36-pass deficit is
  reconciled by **876 - 46 excluded protected cases + 10 new SPA cases = 840**
  (one skip in both totals). The 46 is inferred from the baseline count and
  the permitted collection, not by opening or collecting the protected tests.
  This is a narrower collection, not lost baseline coverage or an ancestry gap.

The recovery manifest in `docs/results/strategy_spa_20261114/manifest.json`
records row counts, hashes, spend, ancestry, and the saved completion sources.
