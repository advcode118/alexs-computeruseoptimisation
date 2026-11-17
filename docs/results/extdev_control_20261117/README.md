# Extdev control — replicate 1

> **Main caveat: these absolute pass rates are not valid estimates of task-solving
> accuracy.** Extdev's literal/partial keys plus the frozen grader's length,
> literal-containment and contiguous-page-span bounds reject many plausibly
> correct list/compound answers. Wrong pages and genuine runtime failures also
> occur. This report describes the recorded frozen-grader outcomes; it does not
> silently regrade them. See [ANALYSIS.md](ANALYSIS.md).

**No further paid runs.** Reporting was offline. Model: **gpt-6.1-sol, medium**;
**n = 1 replicate**; browser-use **1.0.6**; **@playwright/mcp 0.0.84**.
The primary analysis is paired on the same **22 attempted tasks across 11
starting sites**. The four-arm invocation budget-skipped the other **18 tasks
per arm**. Ultrafast attempted all 40 tasks across 14 sites in a separate
invocation; its full-catalog results are supplemental, not a paired comparison.

## Results

All latency figures are the recorded version-2 **single-timer `wall_ms`**, over
attempted rows including failures, excluding budget skips. Browser setup and
post-run grading reads are separate measurements; stage timers are not summed
to manufacture the reported wall time. P90 uses linear interpolation (R7).
USD is the recorded ledger estimate, subject to the pricing caveat below.

**Best baseline:** browser_use **ultrafast** on the paired 22, selected by highest
pass rate, then lower mean wall time. It ties default at 2/22 and is faster on
mean wall time. **Best arm overall:** cascade by the same rule. Differences in
the table are paired **arm minus cascade**, in percentage points (pp).

| Arm / sample | Valid n | Passes; rate [site-clustered 95% CI] | Paired delta vs best arm, pp [95% CI] | Median wall_ms | Mean wall_ms | P90 wall_ms | Mean USD | False accepts / claims |
|---|---:|---|---|---:|---:|---:|---:|---|
| browser_use default, paired | 22 | 2/22; 9.09% [0.00, 19.23] | 0.00 [0.00, 0.00] | 26540.26 | 29455.11 | 54878.14 | 0.074627 | 20/22 |
| browser_use ultrafast, paired | 22 | 2/22; 9.09% [0.00, 19.23] | 0.00 [0.00, 0.00] | 27658.92 | 25295.52 | 35355.66 | 0.053288 | 20/22 |
| script_first, paired | 22 | 0/22; 0.00% [0.00, 0.00] | -9.09 [-19.23, 0.00] | 9638.07 | 10267.33 | 15496.32 | 0.009620 | 6/6 self-check PASS |
| cascade, paired | 22 | 2/22; 9.09% [0.00, 19.23] | 0.00 [0.00, 0.00] | 25022.14 | 25126.49 | 38067.98 | 0.050565 | 6/6 stage-1 self-check PASS; 2/2 accepted by gate |
| playwright_mcp | **0** | **infra failure: Chrome missing, 0 valid rows** | N/A | N/A | N/A | N/A | N/A | N/A |
| browser_use ultrafast, all 40 (supplemental) | 40 | 2/40; 5.00% [0.00, 12.20] | N/A: different sample | 27658.92 | 32220.88 | 59687.70 | 0.077470 | 38/40 |

MCP had 22 charged attempts, all blocked by missing Chrome, and 18 budget skips;
none is a valid task-solving measurement. Its $0.057734 infrastructure-failure
spend remains included in the ledger; it is not dropped from accounting.

### Site-clustered uncertainty method

Nonparametric **cluster bootstrap over sites**, **50,000 draws**, Python
`random.Random(20261117)`. A site is the starting URL's hostname with leading
`www.` removed. Sort sites, sample the original number of sites uniformly with
replacement, and retain every task in each sampled site, including multiplicity.
Each draw computes a **task-weighted pooled pass rate**, dividing by the draw's
task count, not a site-unweighted mean. Use the same sampled sites for every arm
in paired differences. Report percentile 2.5%/97.5% bounds with linear
interpolation. The full-40 ultrafast CI uses its own 14-site sample and the same
seed. The selected comparator is fixed after observed-data selection, not
reselected within each bootstrap; there is no selection/multiple-testing
adjustment. Exact task IDs, site counts and unrounded metrics are in
[paired_metrics.json](paired_metrics.json).

**Limitations:** 11 clusters, two passing tasks, one replicate, and no independent
replicate uncertainty. Script's all-zero outcomes necessarily produce a
degenerate [0,0] empirical bootstrap CI; that does not show its population pass
rate is known to be zero. Default, ultrafast and cascade pass the identical two
tasks, giving identically zero paired differences in every resample; those
degenerate CIs do not establish real-world equivalence or validated accuracy.

### False-accept definitions

These are **disagreements with the frozen grader**, not verified semantic errors.

* **Baselines:** nonempty final `claimed_answer` followed by frozen grader FAIL.
  This uses the requested *returned an answer* alternative, not an inferred
  browser-use internal success bit. Refusals/nonempty failure messages are not
  semantically filtered. Both paired BU modes return answers on all 22 rows:
  20/22 false accepts (90.91% of claims and attempts). All-40 ultrafast: 38/40.
* **script_first:** final runtime self-check PASS followed by grader FAIL:
  6/6 PASS claims, or 6/22 attempts (27.27%). Earlier failed checks repaired by
  later checks are not counted as final claims.
* **Cascade stage 1:** final script self-check PASS followed by **stage-1** grader
  FAIL: 6/6 raw PASS claims, or 6/22 attempts. Do not compare the script verdict
  to the fallback's final grade. The stage-1 claims and page snapshots retained
  in `self_checks[-1].payload` replay as failures under the frozen grader for all
  six. For the four subsequently handed off, this is an offline reconstruction
  from the self-check snapshot, not a separately saved post-script grade read.
  The two precision-gate acceptances have actual final grader FAIL rows too:
  **2/2 gate accepts**, or 2/22 attempts (9.09%). Four raw false accepts were
  intercepted by the precision gate; the Peru task was then recovered by BU.
* **MCP:** undefined here; browser startup never provided a valid attempt.

## Cascade outcome and extdev-only diagnosis

| Answering stage | Rows | Share | Frozen passes |
|---|---:|---:|---:|
| Script | 2 | 9.09% | 0 |
| browser_use fallback | 20 | 90.91% | 2 |

Here `answered_by` is the stage that delivered the result, not proof of success.
Handoff reasons: 13 self-check FAIL, 3 UNKNOWN/no usable check, 2 multiline
answers, 1 long answer, 1 search-results URL. The six raw script PASS cases
include the two accepted false accepts and four intercepted false accepts.

**Correction to the question's premise:** cascade *does* meet the requested
**point-estimate** criterion on these 22 rows:

* Versus best baseline (ultrafast): pass difference **0.00 pp [0.00, 0.00]**.
* Cascade mean **25126.49 ms** versus **25295.52 ms**: **169.03 ms lower (0.67%)**.
* Site-clustered 95% CI for the paired mean wall difference is
  **[-8417.80, +7499.17] ms**: no reliable speed advantage is established.

Thus "within 2 pp with lower mean wall time" is **yes descriptively**, not a
demonstrated accuracy/noninferiority or speed win. The main caveat prevents
interpreting the pass-rate criterion as actual accuracy preservation.

What prevents a substantial improvement here is the **90.91% fallback rate**:
mean script stage 7982.41 ms and grounding 186.11 ms are usually paid before BU
(mean BU-stage time across all 22: 16663.67 ms). Stage figures are diagnostics,
not an alternative wall-time calculation. Neither accepted script result passes:
SpotHero contact returns a phone number rather than `Contact Customer Heroes`;
Nets schedule returns a URL rather than `Brooklyn Nets Schedule`. Raw PASS cases
also include wrong pages and an anti-bot page, showing key-blind self-check
weaknesses, not only a length-bound problem. Final cascade failures comprise six
too-long answers, five literal-marker mismatches, and nine wrong URLs. Both
successes (ICSE duplicate statement and APEC Peru arrivals) are BU fallbacks and
are the same successes as both paired standalone BU modes. No finding here is
extrapolated to other splits.

## Audit findings summarized

See [ANALYSIS.md](ANALYSIS.md) and [attempted_row_audit.csv](attempted_row_audit.csv)
for every attempted row, expected key and returned answer.

* Reference-fragment substitution on the **same saved URL/page**, removing other
  original claim/completion gates, gives 13/22 default BU, 13/22 cascade, 6/22
  script and 17/40 ultrafast page-grade passes. These are diagnostic
  counterfactuals, **not corrected benchmark accuracy**. The old model-free
  verifier uses a different runtime evidence grader and directly supplies the
  keyed fragment. Its JSONLs do not retain page evidence for frozen replay.
  All 40 reference fragments are logically compatible with frozen grading on
  synthetic authored-URL/reference-text evidence; that is not live validation.
* Default 1.0.6 averages 78,279 input tokens, 9.86 steps and $0.074627 per attempt,
  versus 14,461, 4.92 and $0.014275 in historical 1.0.0 results on **different
  tasks**. Internal judges ran on every completed current BU stage and their
  usage/time is included. Their exact share is unavailable. Task/version
  confounding prevents attributing the whole 5.41x input-token growth to 1.0.6.
* BU usage aggregates requests, but our pricing applies the per-request 272k
  long-context threshold to that aggregate. Two rows per mode trigger it.
  If every request were short-context, default BU would total $1.340581 rather
  than $1.641794; ultrafast $2.728263 rather than $3.098815. Request-level evidence
  is absent: these are sensitivities, **not revised costs**. No repricing or
  ledger change was made.
* MCP's missing Chrome has since been fixed **in the environment only**, using
  the pinned MCP dependency's Chrome installer. Chrome 157.0.8103.78 launched
  through the unchanged MCP client and performed a local DOM action without a
  model call. This does not retroactively validate the failed rows, and no paid
  rerun was made.

## Ledger and reproducibility

[ledger_summary.json](ledger_summary.json) and [ledger_summary.md](ledger_summary.md)
reconcile all 131 charged ledger entries with the smoke and two invocations:

* Default replicate usage **$3.023613**; ledger afterward **$3.178912**.
* Ultrafast replicate usage **$3.098815**; ledger afterward **$6.277727**.
* Earlier smoke **$0.105299**, plus separate **$0.050000 opening allowance**.
* Baselines + script_first **$5.009993 / $5.00**; cascade including smoke
  **$1.217734**. Opening allowance is shown separately, not arbitrarily assigned.

Only saved rows and the local ledger were read. Run with API keys unset:

```bash
unset OPENAI_API_KEY ANTHROPIC_API_KEY
.venv/bin/python docs/results/extdev_control_20261117/report_rep1.py
```

This regenerates `paired_metrics.json` and the two ledger summaries; README is
the narrative report. [raw/](raw/) contains immutable original JSONLs, invocation
metadata and logs. `analyze_rep1.py` regenerates the earlier detailed audit.
No grader, model prompt, benchmark config, raw row, or ledger was changed.
