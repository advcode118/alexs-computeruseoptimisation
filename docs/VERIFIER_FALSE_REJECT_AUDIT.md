# Runtime verifier false-rejection audit

2026-11-14. Base: `github/t3/tip3` at `bec55ab`, including stricter verifier
`56fbcab`. Compared its runtime changes with `18df996`. Implementation: Astra,
one prepared T3 branch, no delegated agents or live API probes.

## Decision

**Ship the reporting correction and reproducible rule diagnosis. Runtime
behaviour is unchanged.** This uses the task's explicitly permitted fallback.
The rules conflate textual coincidence with task intent or completed actions;
removing them also removes real false-accept catches. The available replay
evidence does not support a safe general replacement. The 13 counterexamples
below establish defects, not their frequency or a net generalisation win.

The owner's aggregate-only gate is the reason to avoid claiming a win:
3 runs of 40 tasks, passes 82/120 before versus 74/120 after; wrong accepts
21 versus 15; mean 10.33 versus 11.25 seconds. Pass difference -6.7pp,
CI [-15.6,+3.1]; false-accept difference -5pp, CI [-11.9,+1.6]. These are
**supplied aggregates, not recomputed results**. No val3/heldout3 task modules,
validators or result files were opened or rerun. `cuo-tip2` was not modified.

## Measurement correction

`grade_observation` requires runtime PASS for script_first's final success.
Consequently `P(runtime PASS | final success)` is structurally 100% and cannot
measure false rejects. Neither `substring_success` nor final success is a
substitute for an independent marker-and-answer grade.

Future model-driven probe rows now record:

- `page_answer_success`: the same marker, shared page and full-claim checks,
  evaluated **after the run**, with no runtime or completion gate.
- `page_answer_reason`: the corresponding post-run diagnostic reason.

`grade_page_answer` calls the existing grader without those gates. The original
`grade_observation` implementation and its final success call remain intact.
There is no extra page read or model call. The new fields are constructed after
the harness returns; they do not enter prompts, repair messages or caching.
All model-driven arms receive this diagnostic. Skipped/no-observation rows and
the separate optional no-model runner have no independent label.

`heldout3_report` now computes recall from independently labelled paired rows
only, with its existing site-cluster bootstrap. Legacy recall and its interval
are N/A (`null` in JSON). Mixed reports include counts of independently graded
rows, rows lacking labels, independent passes, and observed false rejects in
the labelled subset. Missing labels are never inferred from final success.
Precision, pass rates, costs, timing, hybrid scoring and decision bars retain
their existing definitions. In particular, the existing self-check bar is
still **precision-only**; its name must not be interpreted as proof of recall.

This measures **final-state** recall. It does not recover an earlier correct
answer overwritten by a later repair, nor prove a form's side effect from page
text alone. Those require independently recorded evidence at the relevant time.

`selfcheck_replay` uses the same independent grader for saved script states.
A dynamic `answer_equals_selector` task with no saved selector value is now
**ungraded**, not automatically a graded failure. Confusion counts, precision,
recall and per-rule counts exclude it and expose the ungraded count. Static
marker grades remain available from saved page/claim evidence.

## Concrete rule diagnosis

All examples are hand-written fictional pages in
`tests/test_verifier_false_rejects.py`, not benchmark tasks. Every case passes
the unchanged independent page/answer grader, fails runtime, and therefore
still fails final success. Wrong answers continue to fail the independent
grader. These are characterization tests of unresolved bugs; a later supported
runtime fix should update them to require PASS for the repaired case.

| Rule | Valid local state rejected | Why this is a false reject | Catch that must be retained / missing discriminator |
| --- | --- | --- | --- |
| Quantity-digit | Seats remaining `none` | Zero need not be printed as a digit | Rejecting arbitrary non-answer prose requires semantic value evidence, not mandatory digits |
| Quantity-digit | Cable width `two metres` | Written-out quantities are valid | Same issue; extending a small English-number allowlist is not general |
| Quantity-digit | Admission price `Free` | A real price can be nonnumeric | Existing total-question fixture rejects `The total is correct`; deleting the rule would lose that catch |
| Quantity-digit | Ticket price `12 credits`, asked for visitors aged `12` | Correct output digits may coincide with an input number | `_has_new_digit` requires novel numeric tokens, not merely a numeric answer |
| Quantity-digit | Author of *The Long Year*: `Mara Vale` | `year` modifies the book name, not the requested value | `_QUANTITY_WORD` scans the entire asked clause rather than the asked object's meaning |
| Title-word overlap | First exhibition title `Summer Light`, browser title `Collections Portal` | A container page need not name the item in its tab title | Existing breadcrumb-as-paper-title catch is real; lack of overlap alone cannot distinguish it |
| Title-word overlap | Selected article title `夜の旅`, browser title `Reader Workspace` | A selected item can have a different-language title | ASCII `_content_words` also discards non-Latin answer tokens |
| Form history | Same confirmation after revised submission; old/new references BQ-71/BQ-72 | An earlier stopped script may already have submitted; confirmation text may repeat after another successful submission | Existing static `Book Your Stay` answer must still fail; `ok=False` does not mean no submit occurred |
| Start-page heading | Explicitly asked for current heading `Cedar Observatory` | The requested value is precisely the starting page's heading | A heading substituted for an unfinished form result is different intent |
| Start-page navigation | Same-URL reader now shows selected Safety chapter and its text | SPAs can navigate/change state without changing URL | URL equality cannot distinguish an unchanged home page from a completed in-place transition |
| Returned table row | Asked for cheapest service entry; returns `Local<TAB>5 credits` | Relational selection does not require the chosen label to appear in the task | Wrong binary row for a hex request is still wrong; task-word membership is not row identity |
| Item-row matching | French translation of cat is `chat`; table header is `French<TAB>English` | A column heading is treated as a data-row label | Tab-separated page text lacks header/data-cell structure |
| Item-row matching | TCP badge colour `blue` in a legend beside a TCP/port table | The requested attribute is not the unrelated table's port | Keep named-row value catches when the requested attribute actually belongs to the table |

Interactions make lexical patches risky: the task-echo, site-name, heading,
quantity and row rules can all reject the same valid answer. Bypassing one is
not evidence that the remainder correctly classifies it. Conversely, a change
that simply exempts all on-page text recreates the false accepts the stricter
verifier was intended to catch. No task/site-name-specific runtime rule or
accepted-answer change is introduced here.

## Saved evidence inspected and replayed

Only explicitly permitted sources were read. Counts below are script_first
rows, excluding other arms and summary records.

| Source | Files | Rows / replayable scripts | Finding |
| --- | --- | --- | --- |
| `cuo-tip3/bench/runs/control_dev3/*.jsonl` | 5 | 40 rows / 0 scripts | No `self_checks` or independent labels; no recall estimate is possible |
| `docs/results/heldout2_tip2_20261113/*.jsonl` | 8 | 60 rows / 0 scripts | Same missing evidence; no reconstruction from gated success |
| `docs/results/heldout_{luna,sol}_medium_20261111.jsonl` | 2 | 100 rows / 0 scripts | Same missing evidence |
| `t3-bb463a27-6f4ad896de468d1b/docs/results/strategy_spa_20261114/dev3_{on,off}_first.jsonl` | 2 | 12 replayable scripts | Saved and current verdicts agree: 3 true accepts, 0 false accepts, 0 false rejects, 9 true rejects |

The last pair was replayed with `--split dev3`; no live code was executed.
It is a small strategy-specific DEV sample, not evidence of generalisation or
of safe rule removal. PR #70's historical dev3/older-set replay summaries were
also read as background; their larger counts were **not independently
reproduced here**. Generic unlabelled run files were not opened merely to
discover their split, because some could be protected gate runs.

## Verification and reproduction

Targeted result: **119 passed, 7 deselected** on Python 3.14/Windows.

```text
python <audit-guard.py> pytest -q
  tests/test_grade.py tests/test_verifier_false_rejects.py
  tests/test_selfcheck_replay.py tests/test_selfcheck_precision.py
  tests/test_runtime_plain_rules.py tests/test_evidence_judge.py
  tests/test_prompt_audit.py tests/test_script_cache.py
  tests/test_heldout3_report.py
  -k "not catalog and not task_list and not output_omits and not empty_input and not self_test_flag"
```

The temporary launcher installs empty in-memory versions of the five protected
`bench.tasks_*` modules before importing `bench.tasks`, whose eager imports
otherwise read the protected splits. An audit hook refuses opening the
protected task/validator/result files and refuses non-loopback socket connects.
Loopback is needed for Windows asyncio's internal socketpair. This changes
only the test process; no catalog or production import behaviour is edited.
The seven deselected report tests invoke automatic catalog discovery. The
tested report cases pass explicit synthetic `sites` maps instead.

An initial launcher blocked asyncio's loopback socketpair; permitting loopback
fixed that test-environment error. A new test initially expected a null CI as
`[null,null]`; it was aligned to the report's existing `null` representation.
Recall's human-readable missing value is explicitly N/A.

Coverage includes all existing precision-rule catches, unchanged final grading,
independent labels despite runtime FAIL/UNKNOWN or incomplete other arms,
missing/incorrect returned evidence, wrong URL claims, mixed old/new rows,
missing dynamic replay truth, and prompt/answer-key isolation. The real
quantity false-reject fixture yields measured recall 1/2 while final pass rate
remains 1/2. A separate mixed fixture yields recall 1/3, including UNKNOWN.

Full pytest was not run because it would read protected tasks. No full-suite
claim is made. Any future full run must use the owner's shared slot command:
`sh C:/Users/epicd/.cu-optimisation/probe_slot.sh python -m pytest -q`.
The generic gstack checker detected Next.js build/typecheck and an origin/main
pregate; those are not this Python slice's checks. This checkout has no
`node_modules/next/dist/docs`; no Next.js code was changed.

## Unresolved risks / next evidence needed

- All 13 characterized runtime false rejects remain possible. This PR repairs
  the ability to measure them, not runtime accuracy or latency.
- Legacy final rows cannot supply recall. Missing selector truth also limits
  per-script replay; the new final-row field does not retroactively fix it.
- Mixed-era recall describes only the independently labelled cohort; coverage
  may be non-random. Bootstrap intervals are conditional on that cohort.
- Page/answer ground truth is the existing grader's judgement, not independent
  verification of unobserved browser side effects.
- A follow-up should establish trusted DOM/table structure or action/result
  state evidence before changing these broad semantic rules. Any live
  measurement still requires the owner's authorization.
