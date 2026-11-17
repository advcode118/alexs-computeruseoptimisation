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

- **direct** — no model. The page HTML and the control list are read first. One link or button whose name is already in the task is clicked. A search task with one search box and one Search button is filled and submitted. A previous batch that named one matching role and name is still a direct click. Two controls with the same role and name are not.
- **fast** — one OpenAI-compatible call on that short list. No screenshot. Reads `NEBIUS_API_KEY`, `NEBIUS_BASE_URL`, and `NEBIUS_FAST_MODEL`. If the model name is empty, the loop tries `deepseek-ai/DeepSeek-V4.1-Flash-1017` and `Qwen/Qwen3-30B-A3B-Instruct-2507` and keeps the first valid action batch.
- **planner** — Claude Haiku `claude-haiku-4-5-20251001` when the page HTML has no unique target, and on one retry after a failed assertion. It is not called on every click.

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

## Page checks

Each check has a start and an end.

- **Start** is a blank page, or a url you pass in.
- **End** is the assertion that passes or fails. For `check_page` that is `url`, `title`, and `text`, plus a clean load. For the browser loop it is `Engine.run` finishing done or failed.

`check_page` is for a simple assertion, including `http://localhost:3000`. Navigation times out after 5 seconds. It never calls a model. A `console.error`, a failed request, or a 404 asset fails the check. Those are collected during the load with Playwright `page.on("console")` and `page.on("requestfailed")`.

`run_loop` is the existing `Engine.run` loop, for a task that is not a simple assertion. It is the only tool that may call a model, and only when `planner` is `model`. `planner` `fake` makes zero model calls.

Save a passing check with `check_page(..., save="packing-page.json")`. The file lands in `tests/replay/`. Replay it with no model call:

```bash
python -m loop replay tests/replay/packing-page.json
```

The same replay is the MCP tool `run_saved_test`. A replay finishes in under 3 seconds and makes zero model calls.

Point Cursor at the server from the repository root. `.cursor/mcp.json` is:

```json
{
  "mcpServers": {
    "loop-check": {
      "command": "python",
      "args": ["-m", "loop.mcp_server"]
    }
  }
}
```

Deterministic tools: `open_url`, `check_page`, `reload`, `console_errors`, `failed_requests`, `run_saved_test`. None of them call a model.

### Score a local site over MCP

Start your site (for example `npm run dev` on port 3000). Run the server from the repository root; it speaks MCP over stdio, so an MCP client starts it for you:

```bash
python -m loop.mcp_server
```

Call the `check_page` tool with a start url and at least one end assertion (`url`, `title`, or `text`):

```json
{"name": "check_page", "arguments": {"start_url": "http://localhost:3000", "title": "My app"}}
```

The result is JSON: `ok` is `true` only when every assertion passes and the load had no `console.error`, no failed request, and no 404 asset (`reason` says which). `console_errors` and `failed_requests` list them, and `model_calls` is always `0`. A page that does not load within 5 seconds, or an unreachable url, comes back as a tool error with `ok: false`. Note that a missing `/favicon.ico` is a 404 and fails the check.

From Python, with the official `mcp` SDK (`tests/test_check_page_local.py` does this against a local server):

```python
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

params = StdioServerParameters(command="python", args=["-m", "loop.mcp_server"])
async with stdio_client(params) as (read, write):
    async with ClientSession(read, write) as session:
        await session.initialize()
        result = await session.call_tool("check_page", {"start_url": "http://localhost:3000", "title": "My app"})
```

## Tests

```bash
pip install playwright pytest
python -m pytest
```
