# heldout3: pre-registered test plan

Written 13 Nov 2026, before any agent has run on heldout3, and revised the same day after a design review (Fable 5.2). Nothing in this file may change after the first heldout3 probe row exists, except the "Result" section at the bottom.

## Why

The 50 held-out tasks and the 20 heldout2 tasks have both been studied task by task, and fixes were made because of what we saw. They are now **dev sets**. Gains measured on them are partly fitted. heldout3 is the clean test.

## Sets and roles

| Set | Tasks | Role |
|---|---|---|
| held-out (`held-out`) | 50 (8 known broken) | dev: tune, read failures freely |
| heldout2 | 20 | dev: tune, read failures freely |
| heldout3 | target 120–150 | **test**: aggregates only |

## How heldout3 is written

- Each author writes blind: no results, history, failure notes or PR discussion.
- Each task has:
  - a model-free reproducer that passes the real grader;
  - a negative check (a wrong page or wrong value must fail).
- **Wave 1** (split `heldout3a`, 30 tasks): written by Grok 4.7, sites a–m. Grok was stopped before verifying. It had also edited the grader against its brief, and that edit was reverted. Claude Opus 5.5 verified the set and fixed or replaced tasks, without reading results.
- **Wave 1** (split `heldout3b`, 30 tasks): Claude Opus 5.5 via Cursor, sites n–z, verified by Claude Sonnet 5.5. GPT-6.1 Sol was asked first and declined twice over repo-instruction conflicts, so no model under test wrote any heldout3 tasks.
- **Wave 2** (splits `heldout3c` and `heldout3d`, 40 tasks each): two Claude Sonnet 5.5 authors working separately, on sites a–m and n–z, using no domain from wave 1. The authors are now mostly from the Claude family, so results by author family are reported as exploratory.
- No site may hold more than 3 tasks.
- **Size rule.** The headline claim needs at least 120 valid tasks. With fewer, the run is reported as a **pilot**, and its labels are not claims.

**Known bias, stated up front.** Every task needs a model-free script that solves it, so the set holds only tasks a script can solve. This favours script_first. Every claim from this test carries that caveat: "on tasks known to be scriptable".

## Blindness rule

Nobody who tunes the agents reads per-task heldout3 rows, scripts, answers or failure reasons. The only outputs are the aggregate script and the grader audit below.

If anyone who tunes opens per-task heldout3 results, heldout3 becomes a dev set and the next test needs a new set (heldout4). Write down that it happened.

## Frozen before the run

1. **Code.** One commit on the consolidated tip. Record its SHA. No code change between arms or runs.
2. **browser_use configuration.** Record these at that SHA:
   - step cap (`BROWSER_USE_MAX_STEPS`);
   - per-task budget and timeouts;
   - its system prompt;
   - the browser settings.

   They are the same values used on the dev sets. They are not tuned for this test.
   Before freezing, browser-use was upgraded from 1.0.0 to 1.0.3, so the baseline does not lose tasks to bugs already fixed upstream (1.0.2 fixed hangs on slow pages and on pages behind a dialog). It was then run once on the heldout2 dev set as a smoke check. The playwright_mcp arm is frozen the same way.
3. **Pre-run check.** Run every heldout3 reproducer the same day. A task that fails is **dropped before any agent runs**. If more than 10% drop, stop and fix the set first.

## Arms, models, runs

- Arms:
  - `script_first` (being tested);
  - `browser_use` (primary baseline);
  - `playwright_mcp` (second baseline, added before freezing). It is the plain MCP tool most people use, and on Sol it was script_first's closest rival on the 50-task set.
- Models, both at effort medium:
  - `gpt-6-luna` (primary): **3 runs of each of the three arms**.
  - `gpt-6.1-sol` (secondary): 3 runs each of script_first and browser_use, plus **1 run of playwright_mcp** (exploratory). The single MCP run keeps the spend under the stop.
- Run order:
  - Luna is a Latin square: (sf, bu, mcp), (bu, mcp, sf), (mcp, sf, bu). Each arm takes each position once.
  - Sol is sf, bu, mcp, bu, sf, sf, bu.
- Estimated cost at 138 tasks, from held-out per-task costs:
  - Luna: about $1.4.
  - Sol: about $9.3. An earlier estimate of $4 for Sol's two arms was wrong; this was corrected before the run.
  - Hard stop: the OpenAI ledger may not pass $16. It stood at $3.55 before the run, and the project budget is $20.
  - The runner checks the ledger after each run. If it passes the stop, the remaining runs are skipped and the report notes it.

## After the run

- **Post-run check.** Run every reproducer again. A task that fails it is excluded from **both** arms, so a task must pass both the pre-run and the post-run check.
- Report the number of dropped and excluded tasks beside every headline.

## Analysis

- **Unit and CI.** The unit is the task. Each task's pass rate is averaged over its runs. CIs use a bootstrap with 10,000 resamples, **clustered by site**: whole sites are resampled, because tasks on one site pass and fail together.
- **Primary:** paired pass-rate difference on Luna, script_first minus browser_use, with its 95% site-clustered CI.

Secondary, all with site-clustered CIs:
- the same difference on Sol;
- **script_first minus playwright_mcp** on Luna, paired the same way, with the same labels as the primary (reported as secondary). On Sol it is one MCP run, so that comparison is exploratory;
- **self-check precision**: the share of script_first's runtime PASS verdicts that the grade passes;
- **self-check recall**: the share of graded passes that the runtime also passed;
- **dollars per passed task**, per arm;
- median wall time per task, per arm;
- **the hybrid**: script_first, then browser_use when script_first's own check says FAIL. It is computed from the paired rows of the same run index:
  - it passes if sf self-PASS and sf graded pass, or if sf self-FAIL and bu graded pass;
  - its cost is sf cost, plus bu cost when sf self-FAIL;
  - its time is worked out the same way.

**Exploratory only**, with no significance claims:
- results by author (wave and model);
- results by task kind;
- results split by author family.

## Decision labels (set now)

Accuracy uses the Luna primary CI and takes exactly one of these labels:
- **behind**: upper bound < 0;
- **ahead**: lower bound > 0;
- **inconclusive**: otherwise.

Separately, **within the −10 pp margin** is yes when the lower bound > −10 pp. A result can be "behind, within margin".

Other bars:

| Claim | Needs |
|---|---|
| The self-check is fit to use | precision CI lower bound ≥ 75% on Luna |
| Cheaper | sf dollars per passed task ≤ 0.5× bu, on both models |
| Faster | sf median wall time ≤ 0.5× bu, on both models |
| Hybrid worth building | hybrid pass rate CI lower bound > bu's point estimate − 2 pp, at ≤ 0.6× bu's dollars per task |

We do not re-run to get past a bar.

## Grader audit

An agent that does no tuning checks a random sample of 40 graded rows against the saved page evidence, with the arm hidden. It reports only the agreement rate and the count of disagreements in each direction (wrong pass, wrong fail). If agreement is below 90%, the headline carries that caveat.

## Re-runs

Only for an infrastructure failure: more than 10% of an arm's rows ended in a harness error (browser crash, network, provider 5xx, bot block) and not in an agent verdict. A re-run replaces the whole run for that arm, keeps its place in the order, and the reason is written here.

## Result

Not final: 3 of 16 runs are done. The rest come later, using the manifest and the same commit.

**Deviations so far (13 Nov):**
- The first launch of Luna's first script_first run was cut off after 1 row by a session time limit. That file was set aside unread as an infrastructure abort, and the run was redone in full.
- The user had limited time, so Luna's second script_first run was moved from position 6 to position 3. The other 13 runs keep their pre-registered order.

**Interim look (Luna; script_first × 2, browser_use × 1; not a claim):**
- The pass-rate gap (script_first − browser_use, run 1) is −42 pp, CI [−51, −33], which is labelled behind.
- script_first passes 54%. browser_use passes 96%.
- The self-check precision is 84%, CI [76, 91]. The recall is 100%.
- script_first costs 0.74× browser_use's dollars per passed task, and its median wall time is 0.36× (7.3 s against 20.2 s).
- The hybrid passes 89%, CI [83, 94], at 0.91× browser_use's dollars.

Aggregates are in `docs/results/heldout3_20261113/interim_luna_sf2_bu1.json`. No post-run check or grader audit has been done yet.

## Run record (written before the first heldout3 row)

- **Code.** The commit that adds this section. The runner writes its SHA to `docs/results/heldout3_20261113/manifest.txt`.
- **Tasks.** 138:
  - the 140 authored, minus `ho3d_spa_toolshop_pliers` and `ho3d_form_parabank_login`;
  - each of those two failed one of two same-day reproducer runs (`HELDOUT3_DROPPED_TASK_IDS`);
  - the pre-run checks were a 30/30, b 30/30, c 40/40, and d 38/40 then 39/40.
- **browser_use.**
  - browser-use 1.0.3, local Chromium over CDP, `BROWSER_USE_MAX_STEPS = 30`;
  - the same prompt, task message and answer-format line as on the dev sets;
  - smoke check on heldout2, Luna: 20/20.
- **playwright_mcp.** `@playwright/mcp` 0.0.84 with `--isolated`.
- **Harness fixes made before the freeze**, after the heldout2 smoke check:
  - On the OpenAI path, MCP's final reply is plain text, not TASK_COMPLETE. The harness had dropped that text, so every MCP row had an empty answer, and the 11 Nov MCP scores are too low.
  - The fix records the final reply as the claimed answer and asks for the value in the MCP prompt.
  - It also counts a final answer with no TASK_FAILED as a completion claim, as browser_use's `done()` does.
  - Smoke check on heldout2, Luna: MCP 20/20 (it was 10/20 before the fix).
- **script_first.** The tip as of this commit: the answer-required check is in, and heldout2 dev was 71.7% over 3 runs.
- **OpenAI ledger before the run:** $3.70.
