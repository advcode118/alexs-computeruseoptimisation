
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

1. Per-stage model-call counting is done (PR #106); the grader rewrite is planned but on hold.
2. One checkpointed planning call, with task classification folded into it.
3. Executor-side safety gate: irreversible steps pause for Alex’s approval.
4. At most one repair call.
5. Later: our own interactive agent. browser-use stays as a benchmark baseline only, not the product fallback.

## Progress

- Merged [PR #95](https://github.com/advcode118/alexs-computeruseoptimisation/pull/95): browser-use priced per request.
- Open [PR #106](https://github.com/advcode118/alexs-computeruseoptimisation/pull/106): `run_recovery` stage, per-stage model-call counts, `--fallback none`; offline, **1132 passed, 1 skipped**.
- Open [PR #105](https://github.com/advcode118/alexs-computeruseoptimisation/pull/105): Sol model/effort comparison.

### Current baseline

<sub>Today’s paired speed is effectively tied: cascade mean wall 25.1 s vs browser_use ultrafast 25.3 s. Sample: 22 paired extdev tasks, gpt-6.1-sol medium, 1 replicate. Recorded runs: python tools/extdev_control.py --mode default --execute and python tools/extdev_control.py --mode ultrafast --execute (CU_BU_MODE=ultrafast). The next fresh paired benchmark will provide the speed claim. See the [extdev control evidence](docs/results/extdev_control_20261117/README.md).</sub>

## Evidence

[Saved-evidence hand labels](docs/results/extdev_hand_labels_20261117/) · [Sol comparison, PR #105](https://github.com/advcode118/alexs-computeruseoptimisation/pull/105). These records do not establish an accuracy win.

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
