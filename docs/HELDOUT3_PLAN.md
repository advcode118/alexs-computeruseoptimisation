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
3. **Pre-run check.** Run every heldout3 reproducer the same day. A task that fails is **dropped before any agent runs**. If more than 10% drop, stop and fix the set first.

## Arms, models, runs

- Arms: `script_first` (being tested) and `browser_use` (baseline).
- Models: `gpt-6-luna` (primary) and `gpt-6.1-sol` (secondary). Both at effort medium, **3 runs per arm** each.
- Order within each model is ABBA-style: sf, bu, bu, sf, sf, bu. That way neither arm always gets the fresher site.
- Estimated cost at 140 tasks, from held-out per-task costs:
  - Luna: about $0.5.
  - Sol: about $4.
  - Hard stop: the OpenAI ledger may not pass $14.

## After the run

- **Post-run check.** Run every reproducer again. A task that fails it is excluded from **both** arms, so a task must pass both the pre-run and the post-run check.
- Report the number of dropped and excluded tasks beside every headline.

## Analysis

- **Unit and CI.** The unit is the task. Each task's pass rate is averaged over its runs. CIs use a bootstrap with 10,000 resamples, **clustered by site**: whole sites are resampled, because tasks on one site pass and fail together.
- **Primary:** paired pass-rate difference on Luna, script_first minus browser_use, with its 95% site-clustered CI.

Secondary, all with site-clustered CIs:
- the same difference on Sol;
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

(empty until the run)
