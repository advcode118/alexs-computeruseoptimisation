<a href="https://computer-use-optimisation.vercel.app">
  <img src=".github/readme/hero.svg" alt="Alex's browser tool. One Claude call writes the whole browser task. script_first is 3/3 at 3.67s and $0.047 per run in the PR #18 probe." width="100%">
</a>

<p align="center">
  <a href="https://computer-use-optimisation.vercel.app"><b>Open the live site</b></a>
  &nbsp;&nbsp;&nbsp;
  <a href="https://github.com/advcode118/alexs-computeruseoptimisation">GitHub</a>
  &nbsp;&nbsp;&nbsp;
  <a href="https://cursor.com/codebase/tom-wei-de-vrieze/alexs-computeruseoptimisation">Cursor Origin</a>
</p>

# Alex's browser tool

Computer use is slow because the model stops and thinks before every click. **script_first** doesn't. One Claude call writes a Playwright script for the whole task, Chrome runs it start to finish, and Claude only comes back if the final page is wrong.

## How it works

<img src=".github/readme/how-it-runs.svg" alt="script_first: Claude writes the script, Chrome runs it with no model calls, the harness checks the final page, and only if that fails Claude rewrites it once. Plain Playwright MCP: Claude picks a tool, Chrome does one action, the full page snapshot goes back to Claude, and that repeats every page step." width="100%">

1. **Claude writes the script.** One call, for the whole task, not one click at a time.
2. **Chrome runs it.** Search, open, read. No model call between actions.
3. **Check, repair once.** If the end-state check fails, Claude sees the failure and rewrites the script once.

Plain Playwright MCP and Stagehand are the baselines it races.

## Plan

Low-call design, signed off:

1. First: fix the grader — literal/compound answers reject correct ones — and count model calls per stage.
2. One checkpointed planning call, with task classification folded into it.
3. Executor-side safety gate: irreversible steps pause for Alex’s approval.
4. At most one repair call.
5. Later: our own interactive agent. browser-use stays as a benchmark baseline only, not the product fallback.

## Progress

- Merged [PR #95](https://github.com/advcode118/alexs-computeruseoptimisation/pull/95): browser-use priced per request.
- Draft [PR #106](https://github.com/advcode118/alexs-computeruseoptimisation/pull/106): `run_recovery` stage, per-stage model-call counts, `--fallback none`; offline, **1132 passed, 1 skipped**.
- Open [PR #105](https://github.com/advcode118/alexs-computeruseoptimisation/pull/105): Sol model/effort comparison.

## Our best number

**4/22 (18.2%) — cascade (script_first → browser_use fallback).** On the 22 paired extdev tasks (of 40; 18 budget-skipped), **gpt-6.1-sol medium**, **1 replicate**, offline re-grade under grader `7ff695b5…`. **$0.050565/attempt**, mean wall **25.1 s**, p90 **38.1 s**.

3 of the 4 passes came from the browser_use fallback; script_first alone: 1/22, $0.009620/attempt, mean 10.3 s.

**Baseline on the same 22 tasks, same replicate (separate ultrafast invocation): browser_use ultrafast 5/22 (22.7%), $0.053288/attempt, mean 25.3 s — we are one task behind it.**

Source: [extdev control results](docs/results/extdev_control_20261117/README.md).

Recorded execution and offline re-grade commands (not a request to run):

```bash
export CU_OPENAI_SPEND_LEDGER="$HOME/.cu-optimisation/openai-spend-alex15.json"
export CU_OPENAI_PROJECT_BUDGET_USD=9.00
export CU_OPENAI_RUN_BUDGET_USD=3.00
unset CU_BU_MODE
python tools/extdev_control.py --mode default --execute
unset OPENAI_API_KEY ANTHROPIC_API_KEY
.venv/bin/python tools/regrade.py --out docs/results/regrade_20261117
.venv/bin/python docs/results/extdev_control_20261117/regrade_extdev.py
```

Model calls counted for the script stage only (PR #106 adds full per-stage counts); keys are literal, not human-verified; heldout3 retired and not shown.

<details>
<summary><b>Working on this repo</b></summary>

<br>

The progress site is a Next.js App Router app with Tailwind. Homepage data and benchmark copy live in [`data/loop.ts`](data/loop.ts), with layout and inline copy in [`app/sheet.tsx`](app/sheet.tsx). Only add numbers that were measured.

The benchmark harness is separate from the site: see [`bench/README.md`](bench/README.md).

**Run locally** (Node.js 20 or newer):

```bash
npm install
npm run dev        # http://localhost:3000
npm run build && npm start   # production build
```

**Deploy.** There are no environment variables and no custom output directory. Deploy from a checkout with the Vercel CLI, signed in to Tom's Vercel account:

```bash
npx vercel          # preview
npx vercel --prod   # production
```

**Remotes.** The main remote is Cursor Origin. GitHub is a mirror at `advcode118/alexs-computeruseoptimisation`.

</details>
