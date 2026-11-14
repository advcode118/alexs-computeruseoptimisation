# FORM specialist (opt-in experiment)

Branch: `t3/strategy-form`; draft PR [#72](https://github.com/advcode118/alexs-computeruseoptimisation/pull/72), base `t3/tip3`.

## Mechanism

1. Route from the task description, then observe numbered live fields, labels, options and controls.
2. Ask the model for field numbers and values rather than executable code.
3. Fill with native Playwright actions, read values back, validate the selected form and click its observed submit control.
4. Settle after submission, present the new visible lines and ask for the requested result.
5. Accept only a live answer absent from all pre-submit pages, without new validation/server errors; otherwise run the existing generic path.

Enable with `CU_SF_STRATEGY=form` (a comma-separated list). The switch is off by default. Successful rows carry `strategy=form`; attempts that give up carry `strategy=form:fallback`, with their reason and model usage retained. Other arms never invoke it. The grading functions and existing task definitions are unchanged.

The implementation uses DOM structure and general field/widget conventions, with no task IDs, site names, destination URLs or expected answers. The live entry point receives only task description and start URL. Judge markers are read only by the shared post-run grade.

## Protocol and provenance

- Runtime base: `56fbcab`; current `t3/tip3` documentation was merged. Preserved the earlier task commit and both inherited in-progress modules before completing the hook.
- Twelve `dev4form` tasks were authored before the specialist implementation. Their model-free verifier returned **12/12 twice** on 14 November, with the start page and a wrong end-page value rejected for every task in both runs.
- Development sets: `dev3` and older `held-out` / `heldout2`. New `dev4form` agent runs are checkpoints; the first completed pair is reported separately and retained verbatim.
- The completed public-page runs, paid comparisons and broad pytest invocation used the owner's slot wrapper with `CU_PROBE_SLOTS=1`. The shared wrapper's current default is two slots; no wrapper or live slot was changed during recovery. Luna medium only, script_first only. Strategy-off/on pairs use the same checkout and task order, grounded repair enabled, no cache warming.
- Assigned dev-g ledger opening total: **$5.881834** (inherited project history, not this contribution's spend). This contribution has at most a **$1 increment**. The benchmark key is loaded privately from the owner-provided file.
- No heldout3 or val3 tasks, tests or result contents were inspected or executed. Broad pytest excludes their test files to honor the blindness rule.

## Offline evidence

- Local browser adversarial fixtures cover native text/email/number/date/select/radio/checkbox fields, unrelated required fields, delayed processing, stale results, validation errors, wrong controls and nonexistent field numbers.
- Harness tests cover opt-in isolation, fallback usage accounting and no marker access before completion.
- Model-free public-page replay on six dev3 forms plus two older forms: **6/8 self-pass, 6/8 graded pass, 0 false accepts**. The two failures were the hand-written stand-in's label matching on flight booking and the sum calculator; these are diagnostic-plan failures, not paid-model measurements. No fresh dev4form specialist replay was used for tuning before its agent checkpoint.
- The permitted description catalog contains 132 distinct tasks. Router: **27 true positives, 105 true negatives, 0 false positives, 0 false negatives**. Precision/recall are 100% on this development catalog only. The older `ho_httpbin_customer_form` is semantically a form despite its nonstandard second-word label; treating its ID literally instead gives 26 TP, 1 FP, 0 FN, 105 TN.
- Fixed the inherited `--only-kind` filter to apply to OpenAI probes as well as the other probe entry point; a regression test checks the six dev3 forms.
- Broad permitted suite, through the single-slot wrapper: `python -m pytest -q --ignore-glob=tests/test_heldout3* --ignore-glob=tests/test_val3*` → **853 passed, 1 skipped in 50.01s**. Focused form/cache tests also passed; the OpenAI provider tests passed 13/13. The optional gstack checker could not resolve this repository's GitHub base because it assumes the read-only `origin` remote; its readiness status is not claimed.

### Why 853 differs from tip3's reported 876

This was the **permitted subset**, not the same selection as tip3's full suite. Both protected filename families above were explicitly excluded. The ancestry check on recovery confirmed `github/t3/tip3` at `bec55ab`, including runtime `56fbcab`, is an ancestor of `9bd9402`. Relative to that baseline, test changes consist only of the two added FORM test files (24 cases); no existing test file was changed or deleted. `bench/script_first.py`, `bench/judge.py` and the marker-blindness tests are byte-identical to tip3. There is no evidence of lost baseline changes. The existing successful permitted run is retained; no broad suite or protected tests were rerun to reconcile the counts.

## Limits to evaluate

| Brief idea | Decision and evidence |
|---|---|
| Observe fields first, several forms and label sources | Kept: local real-browser schema/readback test exercises labels, native types and unrelated forms. |
| Model chooses data, deterministic filler executes it | Kept: schema numbers only; malformed/unknown fields and ambiguous options reject; model-free public replay passes 6/8. |
| Submit, wait, read new text | Kept: delayed-processing fixture passes; stale confirmations and unrelated navigation reject. |
| Honest errors and correction | Kept: native and server validation errors reject; bounded correction uses the next observed schema. |
| Multi-step forms and forms behind controls | Bounded support: navigation clicks are allowed, but cannot independently certify completion; five model calls and three fill attempts cap the specialist. Long checkout support is not established. |
| Generic fallback | Kept: disabled/unclaimed tasks avoid browser access; failed specialist usage is retained and generic script execution is tested. |

The 40-second budget is checked between model calls so a billable in-flight response is not discarded; an individual call/action can exceed it. Up to five calls and three fill attempts include navigation and multi-step work. Generic fallback adds its own cost. The standalone model-free replay script contains explicit plans and answers and is diagnostic only, never imported by the live specialist.

Freshness is evidence of an observed post-click change, not a transaction receipt or proof that every requested value was interpreted correctly by the site. Native validation, wrong form selection and explicit fill failures are rejected. Arbitrary custom widgets, iframes, file uploads, long checkouts, delayed dependent fields and results exposed only in input values remain limited. Dialogs are recorded and accepted, but a dialog-only answer is not accepted without live page text.

## Measurement

All eight existing runs completed: one off/on pair for each of the four splits, **52 task rows**, on unchanged runtime `b42e486` (also the runtime at recorded head `9bd9402`). Recovery verified every archived row against the original source and all eight completion summaries. No job was restarted. The two earlier empty probe files have no task rows or billed spend.

| Split | Off pass | On pass | False accepts off → on | Calls median off → on | Median seconds off → on | Mean seconds off → on | USD/task off → on |
|---|---:|---:|---:|---:|---:|---:|---:|
| dev3 | 4/6 | 6/6 | 0 → 0 | 2 → 2 | 11.34 → 10.52 | 12.16 → 10.58 | .000843 → .000346 |
| held-out (older development) | 2/6 | 3/6 | 3 → 2 | 2 → 2.5 | 7.15 → 13.02 | 11.78 → 19.06 | .000759 → .000551 |
| heldout2 (older development) | 1/2 | 2/2 | 0 → 0 | 3.5 → 3.5 | 16.02 → 16.96 | 16.02 → 16.96 | .001304 → .001200 |
| dev4form, first contact = final | 2/12 | 9/12 | 2 → 1 | 3 → 3.5 | 13.57 → 17.20 | 13.33 → 23.21 | .001074 → .000836 |

The first dev4form pair is the final checkpoint: no later tuning or rerun occurred. Its nine on-arm passes comprise eight direct specialist passes and one generic fallback recovery. Four tasks fell back; the on-arm false accept occurred in generic fallback. All fallback time and usage remain charged to the on arm. Across the older held-out set, the specialist itself still made two false accepts.

The dev4form result is **75% pass, 8.3% false accepts per attempt, 17.20s median / 23.21s mean, and 3.5 median model calls**. It misses the requested 90% pass, <5% false accepts, <10s median / <12s mean and ≤2-call targets. Completion improves in this small sample, while latency and calls worsen on the fresh set. Keep the switch opt-in. One repetition per task, sequential split-level off/on blocks and a shared machine support only exploratory conclusions.

The saved comparisons cost **$0.042914**, exactly the dev-g ledger increment from **$5.881834** to **$5.924748**, within the assigned $1 cap. The opening ledger total is inherited history, not this contribution's spend.

Remaining failures:

- Multi-step appointment and checkout flows exhaust fill/time limits; generic fallback also fails. Some actions or responses overrun the between-call 40-second check.
- Radio-result wording is rejected by the specialist; fallback returns concatenated option labels and is falsely accepted by its runtime check.
- Immediate recalculation can put the correct answer on the page before the explicit submit, causing a conservative specialist rejection; fallback recovered the Roman converter.
- The older Selenium confirmation and TestPages form fail the unchanged answer/URL markers. The live TestPages destination differs from its old marker, but its model also returned a field label. Both stay counted as false accepts; no task or grade was amended.
- Embedded-example forms and missing/unsupported field structures still require slow fallback.

Full p90, mean-call and per-task wall/step/cost tables, raw rows, source hashes and an offline reproducer are in [the evidence directory](results/form_specialist_20261114/README.md).
