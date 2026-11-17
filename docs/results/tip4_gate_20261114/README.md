# tip4 specialist integration gate — complete

**Decision: retain all specialists as opt-in. None qualifies for default-on.**
Measured candidate `80f7433` merges PR75 (independent page/answer labels), PR78
(reader), PR72 (form) and PR73 (SPA) on tip3. Observe-first PR74, executor PR77
and narrowed-verifier PR79 are not in this measured candidate.

## Gate

Nine sequential completed runs, all `script_first`, `gpt-6-luna`, medium effort.
Order: off/on three times, then nav alone, form alone, SPA alone. Each has the
same 40 val3 task IDs. Parent recovery checked 360 rows, unique membership,
model/effort/arm, no skips, one completion report per file and source SHA-256.
`aggregate.json` contains aggregates and hashes only; task-level validation
data stays local and was not displayed or reviewed.

Val3 has already informed development priorities. This is reused development
validation, not a fresh final test. Repeats are not independent new tasks.
Shared-machine timing and the fixed condition order limit speed/causal claims.
No page-drift audit or confirmatory uncertainty estimate is provided.

| Condition | Pass | False accepts | Not accepted | Median / mean / p90 s | Mean calls / steps | USD |
|---|---:|---:|---:|---:|---:|---:|
| Off, three runs | 79/120 | 18/120 | 23/120 | 9.50 / 11.53 / 20.34 | 2.50 / 2.43 | .102382 |
| All on, three runs | 79/120 | 15/120 | 26/120 | 11.67 / 14.90 / 30.72 | 3.23 / 2.46 | .113047 |
| Nav alone, one run | 25/40 | 6/40 | 9/40 | 13.77 / 13.17 / 21.18 | 3.13 / 2.25 | .035008 |
| Form alone, one run | 24/40 | 5/40 | 11/40 | 9.63 / 12.93 / 25.32 | 2.40 / 2.30 | .031435 |
| SPA alone, one run | 25/40 | 5/40 | 10/40 | 7.96 / 11.33 / 17.82 | 2.30 / 2.15 | .031777 |

P90 is nearest rank. Off per-run passes: **25, 29, 25**. On: **26, 26, 27**.
Combined mean latency rises **3.38 seconds**, exceeding the predefined
**+2-second** default-on limit. Pass rate is unchanged; fewer false accepts
alone do not make the bundle a net win. The single-specialist cells are
exploratory ablations, not three replicated treatment comparisons.

### By kind: passes (false accepts)

| Kind | Off | All on | Nav alone | Form alone | SPA alone |
|---|---:|---:|---:|---:|---:|
| Navigation | 26/30 (1) | 23/30 (1) | 8/10 (1) | 8/10 (0) | 8/10 (0) |
| Value | 25/30 (1) | 23/30 (5) | 9/10 (1) | 7/10 (2) | 9/10 (1) |
| Search | 16/18 (0) | 13/18 (0) | 5/6 (0) | 5/6 (0) | 6/6 (0) |
| Form | 8/18 (0) | 11/18 (0) | 2/6 (0) | 2/6 (0) | 0/6 (0) |
| Title | 2/12 (10) | 6/12 (5) | 1/4 (2) | 2/4 (2) | 1/4 (3) |
| Dynamic page | 2/12 (6) | 3/12 (4) | 0/4 (2) | 0/4 (1) | 1/4 (1) |

### Honest final-state recall

Every row carries the independent page/answer label introduced by PR75.
This is final-state recall, not a measure of correct earlier states overwritten
by repair or proof of an unobserved form side effect.

| Condition | Accepted independent passes / independent passes | False rejects |
|---|---:|---:|
| Off | 79/84 (94.0%) | 5 |
| All on | 79/84 (94.0%) | 5 |
| Nav alone | 25/25 (100%) | 0 |
| Form alone | 24/26 (92.3%) | 2 |
| SPA alone | 25/27 (92.6%) | 2 |

## Smoke, review and tests

The earlier dev3 smoke completed at 33/40 off and 34/40 on, with false accepts
4 and 2. It does not replace the gate.

The integration author reports **924 passed, 1 skipped**, with protected
heldout3 tests excluded. Parent independently ran **66 focused integration
tests**, all passing: combined routing, strategies-off golden scenarios, nav,
form and SPA. This is focused confirmation, not independent reproduction of
the broad suite or a complete specialist security review.

Precedence: form owns form work; nav reads values/titles after arrival; when
nav also claims a task, SPA takes it first only for app-shell page signals.
Form fallback disables nav/SPA for that task; SPA fallback can reach nav.
The off golden tests cover first-pass and repair scenarios and forbid specialist
calls. They prove those scenarios, not every possible execution.

Integration removed the experimental `form_dryrun.py` diagnostic. Runtime
`bench/script_first.py` is unchanged from tip3. Parent reviewed the integration
harness diff; upstream specialist limits remain documented in their PRs.
Full independent review is pending. PR79 is excluded: parent reproduced an
additional wrong-row false accept in its header detection.

## Spend and provenance

Smoke plus gate: **$0.363754**, below the assigned **$0.40** allocation.
The 440 observations contain one zero-usage attempt. The other 439 match the
ledger's owned suffix exactly on input/output-token and cost signatures.
Opening dev-j balance: $5.881834; closing: $6.245588. The allocation was not
mechanically guarded by the launch script; this is an after-run reconciliation.
No further batch is authorized by the remaining $0.036246.

`spend.json` also records a non-atomic cross-ledger snapshot of approximately
**$8.333360** using a max-multiplicity union of complete task entries and the
maximum recorded prior once. This estimate is below the $20 project cap; it
does not replace a fresh budget check before a future live run. Ledgers were
not reset or changed.

Recovery scripts on this machine:
`C:/Users/epicd/AppData/Local/Temp/opencode/recover-tip4-aggregates.py` and
`C:/Users/epicd/AppData/Local/Temp/opencode/reconcile-completed-spend.py`.
All nine subprocesses exited zero in the saved completion artifact. Recovery
ran offline, produced only aggregate output and made no API calls.

## Post-gate independent review and repairs

The fresh Astra review of `0f8d0d9` reproduced five defects on local fixtures.
All five regression cases failed before repair; the adjacent native-submit and
zero-delay fallback controls passed. These repairs are **after the gate**.
The measurements above remain attributed to `80f7433` and have not been rerun
or regraded. The repaired candidate has no new live accuracy/latency claim.

1. **Nav history and accounting:** normalize earlier payload dictionaries to
   the existing `EarlierPage` type before rechecking a reader answer. The
   failed-script/reader sequence now succeeds and accounts for all three model
   calls and all 21 input / 9 output tokens in the synthetic reproduction.
   A second case proves earlier-page rejection is preserved, not bypassed.
2. **SPA control identity:** discard page-supplied `data-cu-id` attributes
   (including open shadow roots) and allocate observation-local numbers.
   Action lookup requires exactly one match and retains Playwright strictness
   instead of choosing `.first`. The fixture verifies the intended click and
   refusal of a collision introduced after observation.
3. **Form submit provenance:** a fill action must choose an observed native
   submit control associated with the filled form. Preview/custom buttons and
   links cannot establish submission merely by showing new text. Custom
   JavaScript-only submits now use the generic fallback; this conservative
   restriction may change performance and coverage relative to the gate.
   This checks native control semantics and visible result freshness; it does
   not independently prove server-side completion.
4. **Form fallback allowance:** reset the generic repair clock after form
   fallback, as already done for SPA. Total wall time and specialist usage
   remain included. An injected 31-second failed form attempt no longer removes
   the generic script's repair opportunity.
5. **Missing replay evidence:** metadata-only form checks explicitly mark
   replay unavailable. Missing payload/text/URL yields ungraded ground truth
   and UNKNOWN replay, not a fabricated negative label. A recorded empty page
   still receives a failed grade. Existing frozen scores and final grading
   are unchanged.

Parent verification: **163 distinct focused tests passed** (161 in the combined
run, then two additional negative-path checks). Tests cover the nine new cases,
combined routing/off parity, all three specialist modules, replay, final grade,
cache, grounded repair, precision catches and prompt isolation. All commands
used `verifier_audit_guard.py`; no protected datasets or live API calls.
A fresh independent review of the repaired candidate is required before
considering this review complete. Defaults remain off.
