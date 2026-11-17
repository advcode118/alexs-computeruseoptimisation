# heldout4: pre-registered claim plan

Written 17 Nov 2026, before any agent has run on heldout4. **Status: sealed and ready to run. It will not be run in this project, because the user stopped API spend on 17 Nov 2026.** Whoever runs it later follows this file as written. Nothing in this file may change after the first heldout4 probe row exists, except the "Result" section at the bottom. This is the review's step 5 (REVIEW §1.3): **this run is the claim. Everything before it is development.**

## Why

Every earlier set (dev3, val3, held-out, heldout2, heldout3) was written by Claude-family or Grok models, and every task had to be solvable by a model-free script. So those sets only contain "tasks known to be scriptable", phrased the way script_first's self-check heuristics expect. heldout4 is sampled from external, published benchmarks instead. Its task text is written by people outside this project and outside the Claude family. Tasks are kept whether or not a script can solve them.

## Sets and roles

| Set | Tasks | Role |
|---|---|---|
| dev3, val3, held-out, heldout2, heldout3 | as before | dev: tune freely |
| `extdev` | 40 | dev: baseline control (review step 3) and cascade tuning; read failures freely |
| `heldout4` | 128 (130 authored, 2 dropped at sealing; **pilot if < 120 valid**) | **test**: one run, aggregates only |

The two external sets share no site with each other or with any earlier split (`tests/test_extdev.py`, `tests/test_heldout4.py`).

## How heldout4 was built

- **Sources** (`bench/ext_sources/README.md`, raw files with sha256 and licence):
  - Mind2Web-Live (iMeanAI, CC-BY-4.0);
  - WebWalkerQA main (Alibaba, Apache-2.0; questions drafted by GPT-4o, then filtered and rewritten by human annotators);
  - WebVoyager (Apache-2.0);
  - AssistantBench dev (Apache-2.0);
  - Mind2Web train (OSU, CC-BY-4.0), used only to fill shortfalls.
  - Online-Mind2Web was the first choice, but it is gated on Hugging Face, so it is not used.
- **Random sample, recorded seed.** `bench/ext_sample.py`, `SEED = 20261116`.
  - Rows are ordered by `sha256(f"{SEED}:{source}:{id}")`.
  - Each site goes to extdev if `sha256(f"{SEED}:site:{site}") % 4 == 0`, otherwise to heldout4.
  - Per-source quotas for heldout4: Mind2Web-Live 55, WebWalkerQA 50, WebVoyager 15, AssistantBench 10. A shortfall is filled in a fixed source order.
  - At most 3 accepted tasks per site. Exact duplicate task texts are excluded.
  - Every decision is in an append-only ledger (`docs/results/ext_sample_20261116/`).
- **Exclusions.** Only tasks that cannot be attempted fairly are excluded:
  - the domain is used by an earlier split;
  - the task is not in English;
  - the site is unreachable or bot-blocked from the bench machine;
  - the task needs a login or a payment;
  - the site or content is gone;
  - the answer changes within a day;
  - `no_checkable_key`, for one of two reasons only: the answer is computed and not on any page, or the end state cannot be graded even by the fixed grader. On heldout4 all 12 were computed answers. The 2 sealing drops are recorded separately as `ungradeable_end_state`.

  A task is never excluded for being hard, multi-page or not scriptable. Counts by reason are in `docs/HELDOUT4_VERIFY.md`.
- **Task text** is verbatim. Any edit is recorded per task in `text_edits`.
- **Keys.**
  - Each answer was established on the live site on 17 Nov 2026.
  - Each task has end markers that the fixed grader (`bench/grade.py`, PR #88) checks, and at least one negative check (a wrong value or a decoy page must FAIL).
  - Keys are written to be independent of any one grader:
    - `expected_answer` holds the full answer;
    - `answer_parts` lists every required literal part of a compound or list answer;
    - `answer_type` is `"url"` when the answer is the end URL itself;
    - `end_state` is `"search_results"` when the task ends on a results or query URL;
    - `grader_flags` names the known limits of the pre-#88 grader that the task hits (`length_cap`, `url_only_answer`, `search_results_url`).
  - Tasks are not dropped because the old grader cannot handle them.
  - `key_scope: "partial"` remains only where the full answer cannot be written as literal parts.
- **Reproducers.** `reproducer: "script"` tasks have a model-free Playwright reproducer, driven from the start page by UI actions, that passes the grader. `reproducer: "none"` tasks have only a direct key check and the negative checks. Their presence is what removes heldout3's "scriptable only" bias.

**Known biases, stated up front.**
1. The bot-block screen removes many large commercial sites, so the set leans towards sites that tolerate headless Chromium.
2. Partial keys can pass an answer that is incomplete. This affects every arm equally, and the analysis reports the claim on full-key tasks too.
3. The pre-#88 grader rejects list answers longer than its length cap, URL-only answers and search-results end URLs. Tasks hitting those limits are kept and flagged, and they are graded with the fixed grader (see "Frozen before the run").

## Blindness and sealing

- heldout4 was written and verified in one session (Devin, 16–17 Nov 2026). It runs no agent and did no tuning.
- From the commit that adds this file, **nobody tunes on heldout4**. Do not:
  - read per-task heldout4 rows, scripts, answers or failure reasons;
  - change code because of heldout4;
  - run heldout4 before the freeze.
- All development (baseline control, cascade build, self-check threshold) uses `extdev` and the older dev sets only.
- If anyone who tunes opens per-task heldout4 results before the run, heldout4 becomes a dev set and a new claim set (heldout5) is needed. Write down that it happened.

## Frozen before the run

1. **Code.** One commit. Record its SHA in `docs/results/heldout4_<date>/manifest.txt`. No code change between arms.
2. **The cascade** (the arm under test), as built under review step 4 and tuned on extdev only:
   - script_first with a hard budget: 1 script and at most 1 grounded repair;
   - its self-check, with the PASS threshold set on extdev/dev data for precision ≥ 97%;
   - every verdict that is not a confident PASS hands off to a **warm** `browser_use` on the same browser, at the current URL, with the script's receipt.

   Record at the freeze SHA: the script budget, the repair cap, the self-check threshold, and the handoff prompt.
3. **The best baseline.** This is the arm with the highest extdev pass rate in the review step 3 baseline control, with mean wall time as the tie-break. Candidates:
   - browser-use 1.0.6, default mode;
   - browser-use 1.0.6, `CU_BU_MODE=ultrafast`;
   - playwright_mcp;
   - script_first alone.

   It is named here before the run: **browser_use 1.0.6 `ultrafast`** (`CU_BU_MODE=ultrafast`). This is the selection rule's pick on the extdev control (PR #88, `docs/results/extdev_control_20261117/README.md`): it tied default on pass rate and had the lower mean wall time.
   - That control was one replicate on 22 paired tasks, under the old grader, so the pick is weak.
   - If a fuller extdev control (more replicates, the fixed grader, a working playwright_mcp) is done before the freeze, its pick under the same rule replaces this one, and the change is written here before the first heldout4 row.
   - Its settings are frozen the same way as heldout3's: step cap, budget, timeouts, prompt, browser settings.
   - The cascade under test is `bench/cascade.py` from the cascade line (PR #88's base), at the freeze SHA.
4. **Grader.** The grader fixed in PR #88 (list/compound answers, URL-only answers, search-results end URLs), at its pinned hash. Record the hash in the manifest.
   - **Sealing step:** before the freeze, run the heldout4 key checks and negative checks once against that grader.
   - A task whose key or negative check fails there is fixed only if the failure is a key-format mismatch with the new grader fields. That fix is written down, and it does not use any agent result.
   - After that step the set is sealed, and its sha256 is recorded here.
5. **Pre-run check.**
   - Run every heldout4 key check, reproducer and negative check (`python -m bench.verify_heldout4`) on the day of the run.
   - A task that fails is dropped before any agent runs.
   - If more than 10% of tasks drop, stop and fix the set first.
   - The authoring-day pre-run check is recorded under "Set as written" below.

## Model, arms, run, spend

- **Model:** `gpt-6.1-sol` at effort **medium**, for both arms. (The cascade's browser_use handoff uses the same model.)
- **Arms:** `cascade` and the best baseline.
- **Runs:** exactly **one run of each arm**, on all valid tasks, in one sitting on a quiet machine.
  - Both arms run in **one** `bench.openai_run` invocation (one cell: Sol, medium).
  - The runner loops task by task and runs the arms in the order cascade, then baseline, inside each task. So both arms see each site at about the same time, and a stop from the cap cuts both arms at the same task.
- **Spend cap: $5 total** for this heldout4 run (both arms together), enforced by the repo's OpenAI ledger (`~/.cu-optimisation/openai-spend.json`, `bench/openai_spend.py`, whose per-run cap is `OPENAI_RUN_BUDGET_USD = 5.0`).
  - `bench/openai_run.py` checks the cell's spend before every task-arm. Once it reaches `OPENAI_RUN_BUDGET_USD`, every remaining task-arm is skipped and recorded as skipped. Because both arms share one cell, that is $5 for both arms together. The check runs before each task-arm, so the last task-arm can overshoot the cap by its own cost (a few cents at Sol rates).
  - The ledger total is recorded before and after the run. The $20 project cap also still applies.
  - **Estimate:** about **$0.10 per task paired** (cascade plus browser-use 1.0.6). This comes from the extdev control's recorded mean cost per task: cascade $0.051 and ultrafast $0.053 on Sol medium.
    - For the full set of 128 tasks that is about **$12.80**.
    - **The $5 cap covers only about 48 paired tasks.** Under a $5 cap, the run is therefore a **pilot** by the size rule.
    - A full claim run needs a cap of about $15. It is set with `CU_OPENAI_RUN_BUDGET_USD`, and the project cap must have room for it.
    - Whoever runs it chooses one option before the first row and writes it here:
      - (a) the full set with a raised cap; or
      - (b) the $5 cap, with the task order fixed in advance as `sorted(task ids, key=sha256(f"20261116:order:{id}"))`, so the stop point is not chosen after the fact.
  - If the cap stops the run, the unfinished arm is reported as incomplete. Paired analysis then uses only the tasks both arms finished, and the headline is labelled "incomplete".
- The cascade's live run never reads task markers (`test_the_live_run_never_reads_the_answer_key`). The grade is the same for both arms.
- No re-run is made to get past a bar.

## After the run

- **Post-run check.** Run `verify_heldout4` again. A task that fails it is excluded from **both** arms.
- Report the number of dropped and excluded tasks next to every headline.

## Analysis

- **Unit.** The task, scored 1 or 0 per arm (one run).
- **Primary:** the paired pass-rate difference, cascade minus best baseline, with a 95% CI. The CI comes from a paired bootstrap with 10,000 resamples, **clustered by site** (whole sites are resampled), using a fixed bootstrap seed of 20261116.
- **Success target (the claim):** both of these must hold:
  1. **accuracy within 2 pp:** the lower bound of the primary CI is > −2 pp;
  2. **faster:** the cascade's mean wall time per task is lower than the baseline's, and the paired site-clustered CI on the mean difference (cascade − baseline) is entirely below 0.

  Wall time uses one timer for both arms, started after the shared browser is ready and before the start URL is opened, and stopped when the arm returns control (REVIEW §1.2).
- **Labels** for accuracy: **behind** (upper bound < 0), **ahead** (lower bound > 0), otherwise **inconclusive**. **Within 2 pp** is reported separately. The claim is met only if both success conditions hold.
- **Secondary**, each with a site-clustered CI:
  - the same difference on `key_scope: "full"` tasks only;
  - the same difference excluding tasks with any `grader_flags` (tasks only the fixed grader can grade);
  - the same difference on `reproducer: "none"` tasks only;
  - mean, median and p90 wall time per arm;
  - dollars per task and per passed task;
  - cascade handoff rate;
  - self-check precision (the share of the cascade's confident PASS verdicts that the grade passes).
- **Exploratory, no significance claims:** results by source, by kind, and by `reproducer` value.
- **Size rule.** With fewer than 120 valid tasks after both checks, the result is a **pilot** and its labels are not claims.

## Grader audit

An agent that does no tuning checks a random sample of 40 graded rows against the saved page evidence, with the arm hidden. It reports only the agreement rate and the count of wrong passes and wrong fails. If agreement is below 90%, the headline carries that caveat.

## Re-runs

A re-run is allowed only after an infrastructure failure: more than 10% of an arm's rows ended in a harness error (browser crash, network, provider 5xx, bot block) and not in an agent verdict. A re-run replaces the whole arm, must stay within the run cap chosen above, and its reason is written here.

## Set as written (authoring day, before any agent run)

Full details are in `docs/HELDOUT4_VERIFY.md`. No agent or model has run on any heldout4 task.

- **Seal:** sha256 of `bench/tasks_heldout4.py` = `1f9bfa1f77afaf4080da2cff5bbfc70511e3ec3aafce20c98b95ae63939462a3`. **Grader:** `bench/grade.py` sha256 = `7ff695b598c715cf5cc4426b77827819ec374b23699ca08d5ad881ca21a97e24`.
- **Tasks:** 130 authored, 2 dropped at sealing (`HELDOUT4_DROPPED_TASK_IDS`), **128 valid**.
- **By source:** Mind2Web-Live 67, WebWalkerQA 50, WebVoyager 8, AssistantBench 3.
- **By kind:** value 69, nav 29, filter 20, search 5, form 2, spa 2, multisite 1.
- **Key scope:** 104 full, 24 partial. 18 of the partial tasks are multi-page answers: the full reference is kept, and only the parts on the final page are scored (`unscored_parts`).
- **Reproducers:** 18 are `script` and 110 are `none`.
- **Exclusions at sampling and authoring:**
  - site_cap 325
  - site or content gone 76
  - CAPTCHA or bot block 29
  - volatile (changes within a day) 26
  - login 16
  - no_checkable_key 12 (all computed)
  - payment 3
  - duplicate 3
- **Sealing passes against the fixed grader:**
  - Run 1, on 130 tasks: keys 101/130, reproducers 14/19, negatives 259/259 correctly FAIL.
  - Then 29 recorded key-format or setup fixes; none uses an agent result.
  - Run 2 (final), on 130 tasks: keys 128/130, reproducers 15/19, negatives 260/260 correctly FAIL.
  - The 2 key failures were dropped. On the 128 valid tasks: keys 128/128, negatives 256/256, reproducers 15/18 (3 harness errors).
- **Pre-run check on the run day:** re-run `python -m bench.verify_heldout4`. Report site drift; do not fix keys after it.

## Result

Not run.
