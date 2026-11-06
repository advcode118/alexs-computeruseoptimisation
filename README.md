# Alex's browser tool

**One Claude call writes the whole browser task.** Chrome runs the script. No model between clicks. If the end-state check fails, Claude gets one repair.

That's script_first, and it's Alex's product. **Live site: [computer-use-optimisation.vercel.app](https://computer-use-optimisation.vercel.app)** (pink is his).

## How it works

1. **Claude writes the script.** One call. A short Playwright script for the whole task, not one click at a time.
2. **Chrome runs it.** Search, open, read. Zero model calls between actions.
3. **Check, repair once.** The harness checks the final page. Only if that fails does Claude see the failure and rewrite the script, once.

Plain Playwright MCP and Stagehand are the baselines it races. They call a model per step; script_first doesn't.

## Latest numbers

PR #18 probe, Claude Sonnet 5.5, three tasks (Wikipedia search, Python docs, Hacker News top), scored on wall time per successful task:

| | Success | Per success | Per run |
| --- | --- | --- | --- |
| **script_first (Alex's)** | **3/3** | **3.67s** | **$0.047** |
| Playwright MCP | 3/3 | 2.98s | $0.165 |
| Stagehand | 3/3 | 4.62s | $0.074 |

Same success as Playwright MCP at about 3.5x less cost, and about 0.7s behind it on time. Every script_first task is still 2 steps. Claude spend so far: about $16.64 of $50.

## What's done

- A browser loop that owns each step (observe, decide, act, assert) and an M0 measurement showing the outer model's thinking is the clock: 87% of the time in the model.
- The speed-layer stack, PRs #7 to #17: an MCP proxy over Playwright MCP, settle, compact diffs, macros, replay. Outer Claude got every proxy arm to 3/3, but plain Playwright MCP stayed faster, so that stack is **parked**.
- script_first (PR #16), one repair call to reach 3/3 (PR #17), and the PR #18 probe above.

## What's next

**PR #20: stop when the first page is already done.** In progress, not yet measured.

## Links

- Live site: https://computer-use-optimisation.vercel.app
- GitHub: https://github.com/advcode118/alexs-computeruseoptimisation
- Cursor Origin: https://cursor.com/codebase/tom-wei-de-vrieze/alexs-computeruseoptimisation

The site's copy and every number live in [`data/progress.ts`](https://github.com/advcode118/alexs-computeruseoptimisation/blob/cursor/progress-site-redesign-8676/data/progress.ts) on the `cursor/progress-site-redesign-8676` branch. Run it with `npm install && npm run dev`.
