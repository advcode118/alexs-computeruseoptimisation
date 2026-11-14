# Opt-in reader after navigation

`CU_SF_STRATEGY=nav` adds a grounded read step to `script_first`. The default is
`CU_SF_NAV_READ=always`; `suspect` reads only rejected or suspicious extractions.
This is an experimental contribution against `t3/tip3`, not a default rollout.

## Mechanism and scope

1. The existing script and grounded repair loop navigate. The reader claims tasks
   that ask to report a value/title, excluding form work, using only task text.
2. It builds a numbered rendered-page view: relevant lines with neighbours,
   labelled table cells, definitions, h1/document title and fragment heading.
3. Explicit main-heading and uniquely identified table/definition requests can be
   answered without another model call. Otherwise Luna selects a line, column
   and copied value; it writes no code in this read step.
4. Selection checks reject missing values, multiple cells, wrong column evidence,
   headings returned as values, and a column conflicting with the uniquely named
   task column. Every replacement passes the unchanged runtime self-check again.
5. Uncertain selections retain the original result and generic repair path. A
   missing-value response after a PASS can request a grounded repair. Unpriceable
   model usage propagates to the existing spend guard.

The parent superseded the original navigate-by-selection brief with read-after-
arrival. HTTP link ranking, sitemap navigation, two-hop selection and search
fallback were therefore not implemented or measured here. Other arms and the
shared grader are unchanged. The flag is off by default.

## Frozen pre-fix batch

Revision `ab33918f5054506b2a153cc68d80474485ff8e1f`, 14 November 2026,
`script_first`, `gpt-6-luna`, medium effort. All 15 manifest entries completed;
228 task rows, no skips, no duplicate task IDs within a run. Sets match within
each split. Dev3 order was off/always/suspect, off/always/suspect, off/always;
there are **three off and always runs, two suspect runs**. Dev4 order was
always first contact, off, suspect. Older splits have one off/always pair each.

The [preserved rows](results/nav_reader_20261114_pre.jsonl) carry source filenames,
source SHA-256, revision, batch label, individual times, calls, steps, verdicts
and final claims. Large script/self-check payloads remain in the local source
JSONL files; the committed file is a metric/claim extract, not a raw-file copy.

### Definitions

- Pass = the existing final grade, including its requirement for agent self-PASS.
- False accept (FA) = self-PASS and failed final grade, divided by all tasks.
  It includes final-page/claim mismatches and infrastructure-induced missing
  final evidence; rows are not discarded for those causes.
- Final success is **not an independent recall/correctness label** for rejected
  answers. No false-reject estimate is inferred from these rows.
- Calls are median/mean model calls per task; steps are mean tool steps. Wall
  time includes the reader and repair, excludes the common post-run grade read.
- p90 is nearest-rank (`sorted[ceil(.9*n)-1]`). Repeats of the same tasks are not
  independent new tasks; no significance or broad generalisation claim is made.
- Pre-fix USD/task is the **recorded estimate**. Reader cache-write lifetime
  charges were omitted by the harness. The missing premiums cannot be recovered
  exactly from these rows; post-fix accounting records both lifetime counters.
  Pre-fix reader-only latency and the original pre-reader extraction were not
  logged separately. Do not infer either from cumulative script-turn times.

### Dev3: pre-fix repeated comparison

| Kind | Variant | Pass | FA | Calls med/mean | Steps mean | Wall median/mean/p90 s | Recorded USD/task |
|---|---|---:|---:|---:|---:|---:|---:|
| value | off | 18/30 (60%) | 2/30 | 2/2.17 | 2.00 | 7.20/11.94/31.19 | .000674 |
| value | always | 21/30 (70%) | 1/30 | 2/2.87 | 1.90 | 8.04/12.71/26.37 | .000640 |
| value | suspect | 14/20 (70%) | 3/20 | 2/2.40 | 1.85 | 6.08/10.60/26.48 | .000567 |
| title | off | 11/12 (91.7%) | 0/12 | 2/1.92 | 1.92 | 7.89/8.17/14.29 | .000508 |
| title | always | 12/12 (100%) | 0/12 | 2/1.83 | 1.08 | 4.52/4.84/7.01 | .000247 |
| title | suspect | 7/8 (87.5%) | 1/8 | 2/2.12 | 1.50 | 4.18/5.63/14.93 | .000416 |
| SPA read | off | 12/12 | 0/12 | 2/2.25 | 2.25 | 5.98/7.70/14.69 | .000638 |
| SPA read | always | 12/12 | 0/12 | 2.5/3.42 | 1.92 | 6.13/9.27/21.37 | .000609 |
| SPA read | suspect | 6/8 | 0/8 | 3/3.75 | 2.12 | 7.54/9.42/18.51 | .000781 |

Always-read improved title completion with fewer repair/tool steps. Value
completion improved, but stayed below the 90% target, and its mean exceeded 12 s.
Suspect-only missed plausible-looking wrong values: for example a neighbouring
quantity and a precision rather than a storage-size cell. Keep always-read as
the opt-in default; these data do not justify enabling it generally.

### Dev4nav first contact, preserved separately

The authored split has eight value and four title tasks on nine sites, with at
most two tasks per site. The first live strategy run was **10/12**, zero false
accepts: **6/8 value, 4/4 title**. No result after the fixes replaces this number.
This is a new-task development checkpoint, not an independently authored blind
test. Two value tasks failed the existing strict check despite a plausible read;
the check and tasks have not been softened.

| Kind | Variant | Pass | FA | Calls med/mean | Steps mean | Wall median/mean/p90 s | Recorded USD/task |
|---|---|---:|---:|---:|---:|---:|---:|
| value | always, first contact | 6/8 | 0/8 | 2/3.12 | 1.88 | 7.53/8.82/19.36 | .000698 |
| value | off, subsequent | 4/8 | 1/8 | 3/2.88 | 2.50 | 9.61/10.20/18.82 | .000994 |
| value | suspect, subsequent | 4/8 | 1/8 | 3/3.00 | 2.00 | 8.24/9.07/19.52 | .000740 |
| title | always, first contact | 4/4 | 0/4 | 2.5/2.25 | 2.00 | 9.37/9.61/16.57 | .000615 |
| title | off, subsequent | 4/4 | 0/4 | 2/2.00 | 2.00 | 8.84/8.85/14.89 | .000626 |
| title | suspect, subsequent | 3/4 | 0/4 | 1.5/2.00 | 2.00 | 4.81/8.75/22.39 | .000644 |

### Older development sets

| Split/kind | Variant | Pass | FA | Calls med/mean | Steps mean | Wall median/mean/p90 s | Recorded USD/task |
|---|---|---:|---:|---:|---:|---:|---:|
| heldout2 value | off | 3/6 | 2/6 | 2/2.17 | 2.00 | 6.64/7.54/14.30 | .000736 |
| heldout2 value | always | 5/6 | 0/6 | 2.5/2.83 | 1.67 | 6.40/8.00/13.72 | .000694 |
| heldout2 title | off | 2/2 | 0/2 | 1/1.00 | 1.00 | 4.54/4.54/4.62 | .000175 |
| heldout2 title | always | 2/2 | 0/2 | 1.5/1.50 | 1.00 | 3.66/3.66/4.46 | .000173 |
| older held-out table | off | 2/5 | 0/5 | 4/3.20 | 2.80 | 9.79/12.69/24.51 | .001249 |
| older held-out table | always | 2/5 | 0/5 | 4/4.60 | 2.60 | 12.29/13.28/21.31 | .001294 |

Across the selected 16 older held-out tasks, off passed 9/16 with 3 FAs; always
passed 11/16 with 1 FA. These old task IDs use `table/find/wiki/iana/rfc9110/arxiv`
rather than value/title. The full per-task figures are in the preserved extract.

## Recovery fixes, after the frozen batch

Synthetic regressions demonstrated three defects rather than tuning to a task ID:

- Same row, wrong column: the reader could replace a correct runtime-support
  version with the neighbouring toolchain-support version and still self-PASS.
  Replies now identify a column; copied-value membership and a uniquely named
  target column are checked before the unchanged strict self-check.
- A fragment heading could override a request for the main heading. Explicit
  main-heading intent now wins. Section/chapter shortcuts additionally need a
  content-word match to the fragment heading; otherwise the model reads the view.
- Definition-list model-free lookup compared the task with the value rather
  than its term. It now matches the term and refuses conflicting definitions.

Accounting now includes both cache-write lifetimes, propagates `PriceUnknown`,
and counts recoverable failed reader attempts. New `strategy_reads` events
record before/after claims and verdicts, selection notes, calls, time and usage.
An integration test checks opt-out behaviour, exact priced usage and telemetry;
all of these changes stay behind the existing opt-in hook.

## Router and remaining limitations

- Dev3: claims 18/40 descriptions, all 14 value/title tasks and the four SPA read
  tasks; no navigation-only, search-only or form tasks. Relative to *only* the
  value/title labels, precision is 14/18 (77.8%), recall 14/14 (100%). The four
  extra claims are intentionally read tasks, not navigation ownership.
- Dev4nav: 12/12 claims, precision/recall 100% for value/title. Heldout2: 8/20
  claims, precision/recall 100% for its eight value/title tasks.
- Older held-out: 12/50 descriptions claimed; its different labels do not support
  the same numeric value/title router precision calculation.
- Wrong pages, navigation timeouts, blocks and final-page claim mismatches remain
  the navigator's problem. The reader cannot fix an absent page.
- Some correct-looking values are rejected by the shared precision/evidence
  check. Keeping that stricter check is intentional; this PR does not change it.
- Column matching is lexical, not a proof of semantic intent. When labels are
  ambiguous or synonymous, selection still depends on the model. Complex merged
  table headers and truncation are further limitations.
- A failure of the always-reader's model-free recheck keeps the generic result;
  it does not automatically try another reader model call. The model-free
  heuristic itself can therefore leave recoverable reads to generic repair.
- All timing comparisons share a busy Windows machine. Small samples and
  non-contemporaneous post-fix checkpoints are not a speed/accuracy guarantee.

## Validation and post-fix checkpoint

Focused offline regression checks: **63 passed**. Post-fix permitted-suite and
live checkpoint results will be recorded here when complete. Forbidden val3 and
heldout3 tasks/results were not consulted for these changes. The local Next.js
guide/dependencies are absent; this contribution changes only the Python bench.
