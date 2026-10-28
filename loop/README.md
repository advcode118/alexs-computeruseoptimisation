# Browser loop

One local process. Playwright attaches to Chrome, observes the page, and runs a batch of actions from one planner call. There is no tier router, skill memory, or model-cost policy.

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
| Step | Run one planner call (observe, a batch of actions, then the assertion) and wait. |
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

## Model planner

The fake planner is the default. The model planner is one OpenAI-compatible chat completion per cycle. It returns the same action batch (`goto`, `click`, `fill`, `press`, `scroll`) plus an assertion. The default model is `gpt-4o-mini`.

```bash
export LOOP_API_KEY=...          # or OPENAI_API_KEY
export LOOP_BASE_URL=https://api.openai.com/v1   # optional
export LOOP_MODEL=gpt-4o-mini                     # optional
python -m loop demo
```

Choose **Model** on the control page, or run `python -m loop run --planner model`.

## Actions

| Action | Fields |
| --- | --- |
| `goto` | `url` (`http`, `https`, or `file`) |
| `click` | `ref` from the latest observation (`e1`, `e2`, …) |
| `fill` | `ref`, `text` |
| `press` | `key`, optional `ref` |
| `scroll` | `direction` `up` or `down`, optional `amount`, optional `ref` |

An assertion between planner calls is `url`, `title`, or `text`. A failed assertion stops the run and is written in the log.

## Tests

```bash
pip install playwright pytest
python -m pytest
```
