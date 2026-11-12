<a href="https://computer-use-optimisation.vercel.app">
  <img src=".github/readme/hero.svg" alt="Our approach. One model call writes the whole browser task. On 50 held-out tasks, gpt-6-luna script_first passes 27/50 with a 5.98s median, and gpt-6.1-sol passes 37/50 with a 4.15s median. Medians cover all 50 tasks." width="100%">
</a>

<p align="center">
  <a href="https://computer-use-optimisation.vercel.app"><b>Open the live site</b></a>
  &nbsp;&nbsp;&nbsp;
  <a href="https://github.com/advcode118/alexs-computeruseoptimisation">GitHub</a>
  &nbsp;&nbsp;&nbsp;
  <a href="https://computer-use-optimisation.vercel.app/stats">Stats</a>
</p>

# Our approach: script_first

Computer use is slow when the model stops before every click. **script_first** asks once. One model call writes a Playwright script for the whole task, Chrome runs it, and the model comes back only if the final page fails the check.

## How it works

<img src=".github/readme/how-it-runs.svg" alt="script_first: the model writes the script, Chrome runs it with no model calls, the harness checks the final page, and only if that fails the model rewrites it once. Plain Playwright MCP: the model picks a tool, Chrome does one action, the page snapshot goes back, and that repeats." width="100%">

1. **The model writes the script.** One call, for the whole task.
2. **Chrome runs it.** Search, open, read. No model call between actions.
3. **Check, repair once.** If the check fails, the model sees the failure and rewrites the script once.

The measured comparison is script_first, plain Playwright MCP, and browser-use.

## Latest numbers

50 held-out tasks, OpenAI medium, one cold run, no answer key in the script_first runtime. Median and p90 are over all 50 tasks (nearest-rank p90). Passes-only latency is on the stats page.

| | gpt-6-luna | gpt-6.1-sol |
| :-- | --: | --: |
| **script_first** | **27/50 · 5.98s · p90 15.76s · $0.0181** | **37/50 · 4.15s · p90 7.57s · $0.2408** |
| Playwright MCP | 28/50 · 12.98s · p90 26.99s · $0.0883 | 38/50 · 13.79s · p90 22.14s · $0.5006 |
| browser-use | 40/50 · 20.33s · p90 34.64s · $0.0593 | 41/50 · 13.81s · p90 20.90s · $0.7137 |

script_first is the fastest arm on both models. browser-use passes more tasks on both. A later Luna-only code variant, with plain URL / title / h1 rules, passed 31, 36 and 31 of 50 with Decisions off (mean 32.7). Decisions on passed 29, 35 and 37 (mean 33.7) and stays off: 3 of 9 overturns passed the grade. Those six runs are a different build from the table above.

Recorded ledgers in the 11 Nov write-up, not re-read live: OpenAI $3.2185 of $20, Claude $26.022488 of $50 (code abort $40). The full tables, per-task rows and source commits are on the [stats page](https://computer-use-optimisation.vercel.app/stats).

## Run the site

The site is a Next.js App Router app. Numbers live in [`data/measured.json`](data/measured.json) and [`data/measured-tasks.json`](data/measured-tasks.json). `python scripts/check_measured.py` recomputes them from the saved JSONL and fails if the files drift.

```bash
npm ci
npx tsc --noEmit
npm run build
python scripts/check_measured.py
python scripts/check_site_copy.py
```

Deploy is a separate step on the existing Vercel project. This branch does not deploy.
