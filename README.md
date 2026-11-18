
<p align="center">
  <a href="https://computer-use-optimisation.vercel.app"><b>Open the live site</b></a>
  &nbsp;&nbsp;&nbsp;
  <a href="https://github.com/advcode118/alexs-computeruseoptimisation">GitHub</a>
  &nbsp;&nbsp;&nbsp;
  <a href="https://cursor.com/codebase/tom-wei-de-vrieze/alexs-computeruseoptimisation">Cursor Origin</a>
</p>

# Alex's browser tool

Speed from fewer model calls and deterministic execution. Easier maintenance through scripts you can read and rerun, instead of a model deciding each click. That is the product promise, not a measured speed or accuracy win today.

## Plan

Low-call design, signed off:

1. Per-stage model-call counting (built in PR #106, not merged yet). A grader rewrite, scorer v2, is in draft (PR #109).
2. One checkpointed planning call, with task classification folded into it.
3. Executor-side safety gate: irreversible steps pause for Alex’s approval.
4. At most one repair call.
5. Later: our own interactive agent (first draft in PR #110). browser-use stays as a benchmark baseline only, not the product fallback.

## Progress

- Merged [PR #95](https://github.com/advcode118/alexs-computeruseoptimisation/pull/95): browser-use priced per request.
- Merged [PR #101](https://github.com/advcode118/alexs-computeruseoptimisation/pull/101): removed the dead `loop/`, `backends/` and `core/` packages; fixtures moved to `bench/fixture`.
- Merged [PR #104](https://github.com/advcode118/alexs-computeruseoptimisation/pull/104): ruff and offline pytest run on every PR.
- Open [PR #106](https://github.com/advcode118/alexs-computeruseoptimisation/pull/106): `run_recovery` stage, per-stage model-call counts, `--fallback none`; offline, **1132 passed, 1 skipped**.
- Open [PR #105](https://github.com/advcode118/alexs-computeruseoptimisation/pull/105): Sol model/effort comparison.
- In progress [PR #108](https://github.com/advcode118/alexs-computeruseoptimisation/pull/108): offline only — task profile, checkpoints, executor safety gate, side-effect fixtures.
- Draft [PR #109](https://github.com/advcode118/alexs-computeruseoptimisation/pull/109): scorer v2 for extdev, with deliverable-based keys and written rules. The PR reports agreement with hand labels of 99.1% on extdev (frozen grader 40.4%) and 92.7% on a blind held-out set (frozen grader 90.9%).
- Draft [PR #110](https://github.com/advcode118/alexs-computeruseoptimisation/pull/110): our own `InteractiveStage`, behind `--fallback interactive`.
- Draft [PR #111](https://github.com/advcode118/alexs-computeruseoptimisation/pull/111): paired live run, InteractiveStage vs browser-use. Not yet competitive.
- [Continuation plan](https://github.com/advcode118/alexs-computeruseoptimisation/blob/devin/1794950090-planner-gate/docs/LOW_CALL_CONTINUATION.md).


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

**Remotes.** Since 9 Nov 2026 GitHub (`advcode118/alexs-computeruseoptimisation`) is the home for the code. Cursor Origin is kept as read-only history; see [`docs/HISTORY.md`](docs/HISTORY.md).

</details>
