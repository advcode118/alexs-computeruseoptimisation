# Browser loop

One local process. Playwright attaches to Chrome, observes the page, and runs a batch of actions. Each cycle logs a tier: `direct`, `fast`, or `planner`.

## Demo

From the repository root, with Python 3.11 or newer:

```bash
pip install playwright
python -m loop demo
```

Open the printed URL (http://127.0.0.1:8765). The task is already filled in: **Add milk to the packing list**. The fake planner needs no API key.

What you can control:

| Control | What it does |
| --- | --- |
| Start | Run the task. The loop keeps going until it finishes, fails, or you pause or stop it. |
| Pause | Finish the current action, then wait before the next planner call. Start continues. |
| Step | Run one cycle (observe, one tier, a batch of actions, then the assertion) and wait. |
| Stop | End this run. The log stays. Start begins a new one. |

The page and the terminal show each observe (url, title, control refs) and each act.

`python -m loop run` runs that same task straight through, headless, and exits.

## Attach to an existing Chrome profile

The demo launches a new Chrome. To attach to a profile you already use, quit Chrome first (a running Chrome will not open the debugging port), then start it with remote debugging:

```bash
google-chrome --remote-debugging-port=9222
```

That uses the default profile. If the default profile is locked, or you want a separate window, pass a data directory:

```bash
google-chrome --remote-debugging-port=9222 --user-data-dir="$HOME/chrome-computer-use"
```

Then:

```bash
python -m loop demo --cdp http://127.0.0.1:9222
```

Stop and quitting this process disconnect Playwright. They do not quit that Chrome.

## Router

The fake planner is the default and needs no key. **Model** on the control page, or `python -m loop run --planner model`, uses the router.

- **direct** — the previous batch named a ref, and exactly one control has that role and name. The loop clicks it and skips the model. The first cycle of a task always calls a model. `find_ref` is the first match; this tier counts matches, so two controls with the same role and name are not a direct click.
- **fast** — one OpenAI-compatible call on that short list. No screenshot. Reads `NEBIUS_API_KEY`, `NEBIUS_BASE_URL`, and `NEBIUS_FAST_MODEL`. If the model name is empty, the loop tries `deepseek-ai/DeepSeek-V4.1-Flash-1017` and `Qwen/Qwen3-30B-A3B-Instruct-2507` and keeps the first valid action batch.
- **planner** — Claude Haiku `claude-haiku-4-5-20251001` on the first cycle and on one retry after a failed assertion. It is not called on every click.

If `/cursor/stores/self/docs/step5.env.example` is present, those values are used. Otherwise the variables come from the environment. Do not commit a filled key file.

```bash
export ANTHROPIC_API_KEY=...
export NEBIUS_API_KEY=...
export NEBIUS_BASE_URL=https://api.studio.nebius.com/v1   # optional
export NEBIUS_FAST_MODEL=                                  # optional; empty races the small models
python -m loop demo
```

## Actions

| Action | Fields |
| --- | --- |
| `goto` | `url` (`http`, `https`, or `file`) |
| `click` | `ref` from the latest observation (`e1`, `e2`, …) |
| `fill` | `ref`, `text` |
| `press` | `key`, optional `ref` |
| `scroll` | `direction` `up` or `down`, optional `amount`, optional `ref` |

An assertion between cycles is `url`, `title`, or `text`. A failed assertion is written in the log and the loop runs one more cycle. A second failure stops the run.

## Tests

```bash
pip install playwright pytest
python -m pytest
```
