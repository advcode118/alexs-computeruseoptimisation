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
- All new public-page runs, paid comparisons and the broad pytest invocation use the owner's `CU_PROBE_SLOTS=1` slot wrapper. Luna medium only, script_first only. Strategy-off/on pairs use the same checkout and task order, grounded repair enabled, no cache warming.
- Assigned dev-g ledger opening total: **$5.881834** (inherited project history, not this contribution's spend). This contribution has at most a **$1 increment**. The benchmark key is loaded privately from the owner-provided file.
- No heldout3 or val3 tasks, tests or result contents were inspected or executed. Broad pytest excludes their test files to honor the blindness rule.

## Offline evidence

- Local browser adversarial fixtures cover native text/email/number/date/select/radio/checkbox fields, unrelated required fields, delayed processing, stale results, validation errors, wrong controls and nonexistent field numbers.
- Harness tests cover opt-in isolation, fallback usage accounting and no marker access before completion.
- Model-free public-page replay on six dev3 forms plus two older forms: **6/8 self-pass, 6/8 graded pass, 0 false accepts**. The two failures were the hand-written stand-in's label matching on flight booking and the sum calculator; these are diagnostic-plan failures, not paid-model measurements. No fresh dev4form specialist replay was used for tuning before its agent checkpoint.
- The permitted description catalog contains 132 distinct tasks. Router: **27 true positives, 105 true negatives, 0 false positives, 0 false negatives**. Precision/recall are 100% on this development catalog only. The older `ho_httpbin_customer_form` is semantically a form despite its nonstandard second-word label; treating its ID literally instead gives 26 TP, 1 FP, 0 FN, 105 TN.
- Fixed the inherited `--only-kind` filter to apply to OpenAI probes as well as the other probe entry point; a regression test checks the six dev3 forms.
- Broad permitted suite, through the single-slot wrapper: `python -m pytest -q --ignore-glob=tests/test_heldout3* --ignore-glob=tests/test_val3*` → **853 passed, 1 skipped in 50.01s**. Focused form/cache tests also passed; the OpenAI provider tests passed 13/13. The optional gstack checker could not resolve this repository's GitHub base because it assumes the read-only `origin` remote; its readiness status is not claimed.

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

Alternating comparisons are pending. No performance or accuracy improvement is claimed until the saved rows are summarized.
