<a href="https://computer-use-optimisation.vercel.app">
  <img src=".github/readme/hero.svg" alt="Our approach. One Claude call writes the whole browser task. script_first passes 18/18 at 3.18s per success in the PR #27 probe." width="100%">
</a>

<p align="center">
  <a href="https://computer-use-optimisation.vercel.app"><b>Open the live site</b></a>
  &nbsp;&nbsp;&nbsp;
  <a href="https://github.com/advcode118/alexs-computeruseoptimisation">GitHub</a>
  &nbsp;&nbsp;&nbsp;
  <a href="https://cursor.com/codebase/tom-wei-de-vrieze/alexs-computeruseoptimisation">Cursor Origin</a>
</p>

# Our approach: script_first

Computer use is slow because the model stops and thinks before every click. **script_first** doesn't. One Claude call writes a Playwright script for the whole task, Chrome runs it start to finish, and Claude only comes back if the final page is wrong.

## How it works

<img src=".github/readme/how-it-runs.svg" alt="script_first: Claude writes the script, Chrome runs it with no model calls, the harness checks the final page, and only if that fails Claude rewrites it once. Plain Playwright MCP: Claude picks a tool, Chrome does one action, the full page snapshot goes back to Claude, and that repeats every page step." width="100%">

1. **Claude writes the script.** One call, for the whole task, not one click at a time.
2. **Chrome runs it.** Search, open, read. No model call between actions.
3. **Check, repair once.** If the end-state check fails, Claude sees the failure and rewrites the script once.

Plain Playwright MCP and Stagehand are the baselines it races.

## Latest numbers

PR #27 probe on Claude Sonnet 5.5. 18 tasks (3 tuned, 15 held out), one shared fail-closed grader. Scored on wall time per successful task.

| | Passed | Per success (mean) | Median |
| :-- | :-: | --: | --: |
| **script_first** (our approach) | **18/18** | **3.18s** | **2.98s** |
| Plain Playwright MCP | 17/18 | 5.25s | 4.03s |
| browser-use | 17/18 | 6.03s | 4.95s |
| Stagehand | 16/18 | 12.54s | 6.69s |

A warm replay of script_first's cached script also passes 18/18, with a 1.46s median. Cost per arm was not logged for this probe. Claude spend so far is about $26.02 of the $50 budget. The full results, including the OpenAI runs and what is not tested yet, are on the Stats page.

## Done, and next

- [x] A browser loop that owns each step, and an M0 measurement that showed the outer model's thinking is the clock (87% of the time).
- [x] The speed-layer stack, PRs #7 to #17: an MCP proxy, settle, compact diffs, macros, and replay. Plain Playwright MCP stayed faster, so that stack is **parked**.
- [x] script_first (PR #16), one repair call that reaches 3/3 (PR #17), and the PR #27 probe above.
- [ ] **PR #20: stop when the first page is already done.** In progress, not yet measured.

<details>
<summary><b>Working on this repo</b></summary>

<br>

The progress site is a Next.js App Router app with Tailwind. All of the copy and every probe number lives in [`data/progress.ts`](https://github.com/advcode118/alexs-computeruseoptimisation/blob/cursor/progress-site-redesign-8676/data/progress.ts) on the `cursor/progress-site-redesign-8676` branch. Edit that file to update the site, and only add numbers that were measured.

The browser loop is separate from the site: `python -m loop demo` (see [`loop/README.md`](https://github.com/advcode118/alexs-computeruseoptimisation/blob/cursor/progress-site-redesign-8676/loop/README.md)).

**Run locally** (Node.js 20 or newer):

```bash
npm install
npm run dev        # http://localhost:3000
npm run build && npm start   # production build
```

**Deploy.** There are no environment variables and no custom output directory. Deploy from a checkout with the Vercel CLI, signed in to the project's Vercel account:

```bash
npx vercel          # preview
npx vercel --prod   # production
```

**Remotes.** The main remote is Cursor Origin. GitHub is a mirror at `advcode118/alexs-computeruseoptimisation`.

</details>
