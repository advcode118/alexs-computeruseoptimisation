# Bench

Repeatable browser tasks for the local loop. Every page is a file in this folder: a small HTML fixture, or a saved replay of a page. Nothing here calls a live site.

Pass or fail is a code check on the DOM, the URL, or field values. A model is not the judge.

## Commands

From the repository root:

```bash
python -m bench list
python -m bench run --planner fake
```

`list` prints the agent-facing task list. The planner, the router, and any prompt use that list.

`run` sends each task through the existing loop and writes one log record per task: success, wall time, steps (browser actions), LLM calls, tokens, and estimated dollars. Dollars use the rate table in `bench/rates.py` and are labeled `estimate`. They are not an invoice.

The default planner is `fake`, which needs no API key. `--planner model` uses `LOOP_API_KEY` or `OPENAI_API_KEY` and the model this loop already calls (`gpt-4o-mini`, unless `LOOP_MODEL` is set). A task counts as a real model run only when that planner records a call. The summary lists those task ids.

Logs go to `bench/runs/<timestamp>/`.

## Hidden split

Six of the thirty tasks are withheld from the agent-facing list. `bench/scoring.py` loads them only while scoring. Do not copy them into a prompt, the planner, or the router.
