# Bench

Repeatable browser tasks for the local loop. Every page is a file in this folder: a small HTML fixture, or a saved replay of a page. Nothing here calls a live site.

Pass or fail is a code check on the DOM, the URL, or field values. A model is not the judge.

## Commands

From the repository root:

```bash
python -m bench list
python -m bench run
python -m bench run --quick
python -m bench baseline
```

`list` prints the agent-facing task list. The planner, the router, and any prompt use that list.

`run` is the counted bench. It loads the live loop env (Nebius, then Claude) and fails if neither key is present. It does not print the keys. Each task goes through the existing loop. The log records success, wall time, steps (browser actions), LLM calls, tokens, and estimated dollars. Dollars use the rate table in `bench/rates.py` and are labeled `estimate`. They are not an invoice.

A task that the direct role-and-name path finishes can show zero model calls. A counted run with zero model calls in total is a failure: the keys did not reach the planner. `--planner fake` still runs the checker with no key, and it is not a baseline or a result.

`run --quick` scores the first 10 public tasks and does not load the hidden split.

`baseline` pins the one-action model agent to `bench/baseline.json` and freezes `bench/baseline_agent.py` by hash.

Logs go to `bench/runs/<timestamp>/`.

## Hidden split

Six of the thirty tasks are withheld from the agent-facing list. `bench/scoring.py` loads them only while scoring. Do not copy them into a prompt, the planner, or the router.
