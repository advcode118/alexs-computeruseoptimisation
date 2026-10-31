# Bench log

Dollars are an estimate from `bench/rates.py` and the token counts the API returned. They are not an invoice. The counted planner is the live model (Nebius `deepseek-ai/DeepSeek-V4-Pro-0813`). A run with no model calls is not a result.

The goal is fixed: median time per task at most half the baseline, median estimated dollars at most half the baseline, and success on the main split and on the holdout each within 1 percentage point of the baseline.

## Baseline

Pinned in `bench/baseline.json`. Code `bench/baseline_agent.py`, sha256 `b27384e7240a2f8b94ecb3d7481bb0c7ad834d28ed51a0d09e61f26eb1462e3d`.

One action per model call. Direct role-and-name batching is off. The browser stays open. No API key is printed.

Full run: 30 tasks, 6 holdout, 30 passed, 72 model calls.

| | median |
| --- | --- |
| wall time | 8.435 s |
| estimated dollars | 0.00268524 |

Main success 1.0. Holdout success 1.0. Wall clock for the run 315.266 s. Kept. This file is frozen.

## Candidate

`python -m bench run`. The existing direct role-and-name path runs first. The model plans only when that path has no batch. Several actions still go out in one batch. The browser stays open. The observation is the accessibility tree. There is no screenshot path.

Full run: 30 passed, 4 model calls on the tasks the direct path does not cover, wall clock 59.222 s.

| | median |
| --- | --- |
| wall time | 0.332 s |
| estimated dollars | 0.0 |

Time ratio against the baseline 25.407. Cost target met (median estimate is half or less of 0.00268524). Main success 1.0. Holdout success 1.0. Both are inside the 1 percentage point band. Both targets are met. Kept: `direct_match`, `batch_actions`, `warm_browser`, `a11y_before_image`.

`python -m bench run --quick` is the first 10 public tasks. It does not load the holdout. That run passed 10, 3 model calls, median 2.252 s, median estimate 0.0, wall clock 26.118 s.

## Flags

Each idea below was measured on its own. A flag stays off when it does not beat the candidate.

### Replay cached actions

Quick record median 2.274 s with 3 model calls. Replay of the named steps median 1.684 s, 10 passed, 0 model calls. Search steps use refs, so they were not replayed. The full-run median is already set by direct tasks near 0.332 s, so replay does not move that median or the median cost. A counted run that makes no model call is not a result. Flag left off. Traces were deleted.

### Accessibility tree before any image

The loop never sends an image. Nothing was added. The candidate already observes the accessibility tree, and that run is the one that hit both targets. No screenshot path.

### Small model, then a bigger one when stuck

Quick handoff median 2.292 s against the quick candidate 2.252 s. Same model on every call. No task was stuck, so the bigger model did not run. Time did not improve. Flag left off.

### Several actions per call

Turning the batch cap to one action on the quick set passed 3 of 10. Success 0.3. Median 2.475 s. That is worse success than the candidate. Reverted. `batch_actions` stays on. The full baseline (one action per model call) is the other side of this comparison.

### Browser already open

Cold browser, one process per task, quick median 2.558 s, wall clock 44.203 s. Warm quick median 2.252 s, wall clock 26.118 s. Cold is slower. `warm_browser` stays on.

### Prompt caching

The provider already returns `prompt_cache_hit_tokens`. Those tokens are billed at the cached input rate in the estimate. The baseline run recorded 18432 cached input tokens. Repeat packing calls on the candidate recorded cache hits and a lower estimate than the first call. No extra request flag was added. `prompt_cache` stays off because the discount is already in the counted dollars.
