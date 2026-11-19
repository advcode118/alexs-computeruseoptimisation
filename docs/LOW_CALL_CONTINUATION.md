# Low-call continuation

## Goal and authority

Build a browser agent faster than browser-use by making fewer model calls and
executing deterministic batches. Measure accuracy, safety and reproducibility
honestly: fewer calls are not a win if success falls. Browser-use remains the
benchmark/comparison, **never the intended product fallback**.

Read `AGENTS.md`, `docs/HISTORY.md`, `docs/TEST_RESULTS.md`, `NOTES.md` and
`docs/CASCADE.md` first. This continuation records the newer product decisions
where those documents still describe browser-use as the product fallback.
Design sources: the original `low_call_stack_review.md` attachment
(Interfaces/Next slices) and `low_call_remaining_plan.md`. Their operative
decisions are captured here; the original files are not prerequisites.

## Dependencies and current implementation

**PR #106**, branch `devin/1794949079-run-recovery` (slice 1)
→ **PR A**, branch `devin/1794950090-planner-gate` (this work)
→ **PR B**, own interactive fallback plus paired-run plan.

Merge #106 before A. Open A and dependent PRs **against `main`**, not a temporary
parent branch: PRs are squash-merged and their branches deleted. Reconcile each
dependent branch with landed `main` before merging; do not depend on the old
parent commit being an ancestor. This document does not authorize a merge.

Implemented in PR A, including the independent-critique corrections:

- `bench/cascade.py`: HTTP grounding → script_first → deterministic precision
  check → optional recovery on the same Chrome. `run_recovery` is currently a
  browser-use handoff function, **not** the generic Stage/CallBudget protocol in
  the design sketch. Those proposed abstractions are not implemented yet.
- #106 adds `stage_model_calls`, total call accounting and
  `--fallback {browser_use,none}`. **Current code still defaults to browser_use**
  in `bench/probe.py` and `run_cascade_task`; this is compatibility behavior,
  not the intended product. PR B must make browser-use explicitly benchmark-only.
- `bench/recovery.py`: `TaskProfile`, `classify_task(description, grounding)`,
  `plan_checkpoints`, `evaluate_checkpoints`, `ActionGate`. Classification uses
  task text plus HTTP grounding (title/h1, links, search forms, error); **zero
  planner model calls**. Model-reported confidence never grants approval.
- `bench/script_first.py`: the real step executor checks the gate before actions.
  `configure_gate` is the single task-gate factory, shared by client, harness and
  cascade; updating the grounded profile preserves the instance and terminal
  `gate.blocked`. Result formatting and cascade read that state directly, even
  across multiple segments/snapshots. A block yields UNKNOWN/“needs approval”,
  prevents repair and fallback; `profile.needs_approval` also prevents fallback.
- Live evaluate steps install capture-phase click/submit interception and native
  form submit/requestSubmit wrappers, inspecting the actual target rather than
  parsing JavaScript selectors. GET search submissions pass even beside POST
  forms; POST blocks except explicit task-approved login. Enter/Space on commit
  controls (including keyboard focus) are checked. Probes wait for attachment up
  to the 5s action timeout and pending main-frame navigation to commit.
- Rules apply to controls, not the current page URL: password fields, sensitive
  hrefs, POST submits and commit buttons/submit inputs/role controls are guarded.
  Plain links use sensitive hrefs, not commit-like link text; todo checkboxes and
  labels pass. Expanded commit vocabulary includes booking/publishing/signup;
  known GET Submit/Apply and explicit filter/sort controls remain readable.
  Without DOM, unknown submissions and commit-like labels stay conservative.
  This is a heuristic gate, not a general JavaScript security sandbox.
- Checkpoints are machine-checkable goal predicates: URL host/path-prefix,
  quoted text against the claimed answer or live filled values (never password
  values), and no blocked action. A textbox merely existing is not a goal.
  Cascade stores their results per recorded script self-check in `checkpoints`,
  plus `profile` and `blocked_actions`; they are currently observational, not an
  additional read-only PASS criterion. PR B must evaluate them after each segment.
- Script stage: **at most one grounded repair**; runtime verdict and
  `precision_check` determine PASS/FAIL/UNKNOWN. UNKNOWN is not PASS.
- `bench/grade.py` is frozen and independently post-run. Live execution never
  reads task markers/answer keys. Do not import grader truth into a stage.

Evidence: `tests/test_recovery.py`, `tests/test_gate_audit.py`,
`tests/test_cascade.py`, local request-logging fixtures under `bench/fixture/`.
`python tools/gate_audit.py` reproduces `docs/results/planner_gate_audit.md`:
363 script occurrences, 849 parsed steps, 34 blocked; only 11 steps have saved-HTML
DOM replay, 60 scripts are parse-rejected. Expanded vocabulary adds lexical
Submit/Apply blocks; missing DOM cannot establish GET methods or plain-link
semantics. Remaining blocks include todo labels and unknown-method read forms:
**not proof of zero live regressions**. The audit checks each step independently;
normal execution keeps blocks terminal. No paid run was made for A.

## Remaining pieces, in order

1. **PR B: owned interactive agent. IMPLEMENTED (offline) on `devin/interactive-stage`**:
   `bench/interactive.py`, `--fallback interactive` now the default; `browser_use` is
   explicit benchmark-only. Checkpoints are evaluated per segment and fed back, not a
   PASS gate. Tests: `tests/test_interactive.py`. Original brief follows.
   **PR B: owned interactive agent.** Implement `InteractiveStage`, selected by
   `--fallback interactive`, with hard cap **K=4 model calls**. Reuse
   `ScriptFirstClient.call_tool("run_script", ...)` and `page_snapshot`; one short
   segment/call, snapshot and checkpoint evaluation after each. Same page,
   grammar, executor gate and verdict; no second framework or extra repair loop.
   Screenshot only inside this stage and only for profile modality `visual`.
   Browser-use remains an explicitly selected benchmark stage; preserve `none`.
2. **Paired-run plan and approval point (plan included in B).** Pre-register a
   fresh external dev/val set, never heldout3. Exact commands: same set/model,
   `gpt-6.1-sol`, medium, **one run per side**, cascade
   `--fallback browser_use` versus `--fallback interactive`. Report pass rate,
   model calls mean/p90, wall time mean/p90 and dollars/task, including failures,
   stage totals, timer definition and raw evidence. Send Ken the commands, set,
   run count and cost estimate versus the **$5/run cap** for alex's explicit go;
   **nothing runs before approval**. Before scorer work lands, an authorized run
   can inform calls/wall/cost only; no paid accuracy claim.
3. **Scorer rewrite: REQUIRED before any paid accuracy claim; ON HOLD until alex
   says go via Ken.** Rewrite extdev answer keys and grading rules offline,
   update the `bench/grade.py` SHA-256 pin in `tests/test_grade_frozen.py`, perform
   a full offline regrade, and validate agreement against independent labels on
   a fresh held-out set. Keep it separate from policy tuning and live execution.
   This prerequisite blocks accuracy claims even if B and its plan are ready.
4. **README/site/scoreboard update.** The agent that lands the paired-run result
   owns this, using its committed evidence **only after alex approves the
   numbers**. Do not promote a performance-only run to an accuracy claim.

Public surfaces checked in this checkout:
- `README.md` still leads with Claude and PR #18's 3/3, 3.67s, $0.047; its table
  is labelled superseded, but its hero, stale spend and PR #20 next step remain.
  Update `.github/readme/hero.svg` and `how-it-runs.svg` with the copy as needed.
- `docs/TEST_RESULTS.md` is the current scoreboard; it still describes the old
  browser-use cascade direction and caveated historical results, not proof for B.
- Actual home route: `app/page.tsx` → `app/sheet.tsx` → `data/loop.ts` (architecture
  proposal and illustrative clocks). `app/runs/page.tsx` hardcodes seven older
  router runs and explicitly calls the 36s/48s/17s clocks sketches. Keep measured
  results distinct from sketches; update these actual surfaces, not just
  `data/progress.ts`, whose old “no agent code” content is not the home data source.
  README's claim that all site copy lives in `data/progress.ts` is stale.

## Copy-ready task prompts

### B — InteractiveStage

```text
Goal: beat browser-use through fewer model calls and deterministic execution,
without sacrificing honestly measured accuracy, safety or reproducibility.
Read docs/LOW_CALL_CONTINUATION.md and its required repo docs. After #106 and A,
implement PR B: InteractiveStage behind --fallback interactive, K=4 calls, one
short segment per call, shared Chrome, run_script + page_snapshot, existing
grammar/executor/ActionGate/verdict, checkpoints after every segment. Preserve
one script-stage repair and --fallback none. Make browser_use explicit benchmark
only, not the product default. Screenshots only for visual profiles in this stage.
Done: mocked-model tests recover a broken script, stop at K, enforce approval
without fallback bypass, preserve task-approved login and read controls, evaluate
checkpoints and account for every stage's calls/tokens/cost/wall time. Run the
full offline suite and gate audit; commit raw outputs/summary and the paired-run
plan described in the next prompt. Bugs require a failing test before the fix;
performance claims require before/after tables with exact command, task set,
model and run count; offline mocks are not a speed/accuracy claim.
Constraints: Fusion mode; stop at 88% reported usage (alex's usage cap), checkpoint
remaining work durably; no sub-sessions unless asked; offline-first; no paid runs
or merges without alex's OK via Ken; browser-use benchmark-only; frozen grader,
no live markers; PR title SWF(<category>): <overview>. Follow main-target/squash
dependency rules. Next: submit the paired-run plan to Ken, not a paid probe.
```

### Paired-run plan and separately authorized execution

```text
Goal: show whether fewer model calls and deterministic execution beat browser-use
on speed while reporting accuracy, safety and reproducibility honestly.
Scope now: write a paired-run plan, no execution. Pre-register a fresh external
dev/val set (never heldout3), exact runnable commands for cascade --fallback
browser_use versus --fallback interactive, gpt-6.1-sol medium, one run per side,
same conditions, explicit timer and stopping policy. Include pass rate, calls
mean/p90, wall mean/p90, dollars/task, all failures and stage accounting. Estimate
both sides against $5/run and the remaining project ledger; send to Ken for alex's
explicit run approval. Resolve the outstanding provider reservation first.
Done now: committed plan, task-set provenance/hash, commands, cost estimate and
approval request. Nothing runs before approval. Only if separately authorized,
execute exactly that plan and commit raw rows plus before/after tables identifying
command, task set, model and run count. Accuracy claims additionally require the
approved scorer rewrite/full regrade/fresh-held-out validation; until then report
calls/wall/cost only. Bugs require a failing test before a fix.
Constraints: Fusion mode; stop at 88% reported usage (alex's usage cap) and leave
a durable checkpoint; no sub-sessions unless asked; offline-first; no paid runs
or merges without alex's OK via Ken; browser-use benchmark-only; no live answer
keys; PR title SWF(<category>): <overview>. Next: scorer remains on hold pending
its own go; after valid results, obtain approval of numbers before publication.
```

### Scorer rewrite — ON HOLD

```text
Goal: measure whether the low-call deterministic agent beats browser-use without
inflating accuracy or sacrificing safety/reproducibility. ON HOLD: do not start
this rewrite until alex explicitly says go via Ken; it is required before any
paid accuracy claim, not permission for paid runs.
Once authorized, rewrite extdev answer keys and grading rules offline in a
separate task/PR. Version the keys/rules, update bench/grade.py and its pin in
tests/test_grade_frozen.py, run the full suite and full offline regrade with
python tools/regrade.py --out docs/results/<new-version>. Preserve old results.
Validate on independent hand labels from a fresh pre-registered held-out set,
not heldout3 or policy-tuning data; never expose keys to live agents.
Done: committed rule rationale, failing regression tests before bug fixes, new
pin, complete regrade/deltas/missing-evidence counts and hand-label agreement
table. Any performance claim needs before/after tables with exact command, task
set, model and run count; offline regrading alone proves no runtime speedup.
Constraints: Fusion mode; stop at 88% reported usage (alex's usage cap), save a
durable checkpoint; no sub-sessions unless asked; offline-first; no paid runs or
merges without alex's OK via Ken; browser-use benchmark-only; PR title
SWF(<category>): <overview>. Next: unlock accuracy reporting only after validation;
paired-run execution still needs its own explicit approval.
```

### Publish approved results — paired-result agent owns this

```text
Goal: communicate whether fewer calls and deterministic execution beat browser-use
with honest accuracy, safety and reproducibility. You, the agent landing the
paired-run result, own the follow-through. Wait for alex's approval of the numbers
via Ken; use only committed results, and no paid accuracy claim before the scorer
rewrite/validation. No new benchmark execution is authorized by this task.
Update README.md, its .github/readme SVGs as needed, docs/TEST_RESULTS.md and the
actual site surfaces app/sheet.tsx/data/loop.ts and app/runs/page.tsx. Check
app/page.tsx routing; data/progress.ts is stale, not the current home data source.
Retire superseded headline claims, distinguish sketches from measured clocks,
explain browser-use is the benchmark rather than intended product fallback.
Done: traceable links to approved raw rows and before/after tables with exact
command, task set, model, run count, pass-rate caveats, calls/wall mean+p90 and
dollars/task. Read the installed Next docs before site edits; build and visually
verify changed surfaces, retain screenshots. Bugs need failing tests before fixes;
do not invent performance tables or treat a build as visual verification.
Constraints: Fusion mode; stop at 88% reported usage (alex's usage cap), save a
durable checkpoint; no sub-sessions unless asked; offline-first; no paid runs,
merges or deployment without alex's OK via Ken; browser-use benchmark-only;
PR title SWF(<category>): <overview>. Next: hand off approved evidence and open
limitations; propose further experiments, never silently spend or merge.
```

## Operating checks and approval boundaries

```bash
source ~/.nvm/nvm.sh && source .venv/bin/activate
pytest -q bench/test_harness.py tests
python tools/gate_audit.py
```

Use Python 3.11+ in the project venv. Persist handoffs/results in the repo or home,
not OS temp. Current OpenAI ledger: `~/.cu-optimisation/openai-spend-20261117.json`,
$15 project cap, $5/run; old ledgers are closed. Re-read current ledger/provider
evidence rather than trusting an old balance. Resolve reservation `32f86e…`
($0.012660) before the first approved paid run. Approval of a plan, scorer work,
numbers, a paid run and a merge are distinct permissions; none implies another.
