# Fairness of four arms

This note reads how `playwright_mcp`, `script_first`, `stagehand`, and `browser_use` are launched and graded at `98fcfeaf576788d8163de4624c6088f3997af312`. It changes no harness code. It records no live probe.

## What they share

The model string is the same: `claude-sonnet-5-5`.

The page-text function is the same: `_PAGE_EVIDENCE_JS`, assembled by `page_text_from_evidence`. The call that runs that function differs.

The timeouts differ. The browsers differ. The grade function is `grade_observation` for all four, and the completion bit passed into it differs.

## Timeouts

The timeouts differ. Each arm's numbers below are the ones this checkout sets.

`playwright_mcp`, `script_first`, and `stagehand` send the outer model through `AnthropicClient`, which waits 120 seconds on the HTTP call:

From `bench/harness.py`:

```python
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.loads(resp.read().decode())
```

`browser_use` does not use that client. This checkout sets no HTTP timeout on `ChatAnthropic`.

The probe step cap is 30 for `playwright_mcp` and `stagehand`, 4 calls for `script_first` with a hard cap of 6, and 30 steps for `browser_use`:

```python
max_steps = SCRIPT_FIRST_MAX_CALLS if arm == ARM_SCRIPT_FIRST else 30
```

```python
SCRIPT_FIRST_MAX_CALLS = 4
SCRIPT_FIRST_MAX_SCRIPTS = 2
SCRIPT_FIRST_HARD_CAP = 6
```

```python
BROWSER_USE_MAX_STEPS = 30
```

```python
result = await agent.run(max_steps=BROWSER_USE_MAX_STEPS)
```

Action and navigation waits differ too.

`script_first` sets its own waits and does not run the settle loop:

```python
_NAV_TIMEOUT_MS = 10000
_ACTION_TIMEOUT_MS = 5000
_EVALUATE_TIMEOUT_S = 5
_LAND_TIMEOUT_S = 0.8
```

```python
await page.goto(action.value, wait_until="domcontentloaded", timeout=_NAV_TIMEOUT_MS)
```

```python
await locator.click(timeout=_ACTION_TIMEOUT_MS)
```

`stagehand` calls `page.goto` and `locator.click` with no timeout argument in `apply_script`, then settles with the proxy quiet window and cap (500 ms and 3000 ms unless the environment overrides them):

```python
await page.goto(action.value)
```

```python
async def settle_playwright_page(page) -> dict:
    """Same 500ms quiet wait the proxy uses. A failure still returns."""
    try:
        raw = await page.evaluate(settle_source(configured_quiet_ms(), configured_timeout_ms()))
```

```python
QUIET_MS = 500
SETTLE_TIMEOUT_MS = 3000
```

`playwright_mcp` passes no timeout and no settle flag. `playwright_mcp_args` is `--isolated`, optional `--headless`, and `--snapshot-mode`. A tool call waits until the MCP process writes a response. On stop, the process is given 5 seconds and then killed:

```python
await asyncio.wait_for(self.process.wait(), timeout=5.0)
```

`browser_use` sets no action timeout in this checkout. The page read's daemon request for the current tab uses 5 seconds:

```python
own = _daemon_request_fn()(name, {"meta": "current_tab"}, 5)
```

## Browser

The browsers differ. Each arm opens its own.

`playwright_mcp` starts a separate `@playwright/mcp@0.0.84` process. The argv names no browser channel:

From `bench/harness.py`:

```python
    args = [
        "npx",
        f"@playwright/mcp@{PLAYWRIGHT_MCP_VERSION}",
        "--isolated",
    ]
    if headless:
        args.append("--headless")
    args.extend(["--snapshot-mode", snapshot_mode])
```

`build_client` asks that process for a full snapshot:

```python
return PlaywrightMCPClient(headless=headless, snapshot_mode="full")
```

`script_first` and `stagehand` each call Playwright's `chromium.launch_persistent_context` on a fresh temp directory. Both try `channel: "chrome"` and then a launch with no channel. The profile prefixes differ (`script-first-arm-` and `stagehand-arm-`). `script_first` starts that launch while the model is writing and does not open the task URL in the launch. `stagehand` finishes `start()` before the model loop.

From `bench/script_first.py`:

```python
        attempts = (
            {"channel": "chrome", "headless": self.headless},
            {"headless": self.headless},
        )
        for kwargs in attempts:
            profile = tempfile.mkdtemp(prefix="script-first-arm-")
            try:
                self._context = await self._playwright.chromium.launch_persistent_context(
                    profile,
                    **kwargs,
                )
```

From `bench/stagehand_local.py`:

```python
        attempts = (
            {"channel": "chrome", "headless": self.headless},
            {"headless": self.headless},
        )
        for kwargs in attempts:
            profile = tempfile.mkdtemp(prefix="stagehand-arm-")
            try:
                self._context = await self._playwright.chromium.launch_persistent_context(
                    profile,
                    **kwargs,
                )
```

`browser_use` is not that Playwright client. The probe calls `run_browser_use_task`, which constructs browser-use's browser with the string `chromium`:

```python
LOCAL_BROWSER = "chromium"
```

```python
browser = browser_cls(LOCAL_BROWSER, headless=headless, keep_alive=True)
```

The arm docstring states the library default this call replaces:

```python
"""browser-use 1.0 baseline. Local Chrome over CDP, same bench model.

The library's defaults are a cloud browser and the bu-fast gateway model.
This arm passes Browser('chromium') and ChatAnthropic('claude-sonnet-5-5').
```

Before a model call, `playwright_mcp` navigates and can skip when that snapshot body is longer than 40,000 characters. `stagehand` does the same after `page.goto` plus `snapshot`. `script_first` returns an empty peek, so that length check does not skip it. `browser_use` has no peek.

From `bench/probe.py`:

```python
    if arm == ARM_SCRIPT_FIRST:
        return "", 0.0
    if arm == "stagehand":
        await client.call_tool("run", {"code": f"page.goto({json.dumps(url)})"})
        return await client.call_tool("snapshot", {})
    text, elapsed = await client.call_tool("browser_navigate", {"url": url})
    return text, elapsed
```

```python
HUGE_SNAPSHOT_CHARS = 40_000
```

## Model string

The model string is `claude-sonnet-5-5` for all four. `assert_allowed_model` returns that string and refuses anything else.

```python
ALLOWED_MODEL = "claude-sonnet-5-5"
```

```python
DEFAULT_MODEL = ALLOWED_MODEL
```

`playwright_mcp`, `script_first`, and `stagehand` go through `BenchmarkHarness`, which stores `assert_allowed_model(model)` and sends it as the Messages `model` field:

```python
self.model = assert_allowed_model(model)
```

From `bench/harness.py`:

```python
    return {
        "model": model,
```

`browser_use` passes the same checked string into browser-use's `ChatAnthropic`:

```python
chosen = assert_allowed_model(model)
```

```python
llm = llm_cls(chosen, api_key=api_key)
```

`run_browser_use_task` defaults `model` to `ALLOWED_MODEL`. The probe calls it without a different model. The Messages `anthropic-version` header is set only on `AnthropicClient`. This checkout does not set that header on the `ChatAnthropic` call.

## Page-text source

The page-text function is `_PAGE_EVIDENCE_JS`. It reads `main` or `body` (`innerText`, then `textContent`), plus title, canonical, h1, headings, and controls. `page_text_from_evidence` puts headings in front of the body and caps the result at 8000 characters.

```python
_PAGE_TEXT_CAP = 8000
```

From `bench/script_first.py`:

```python
  const root = document.querySelector("main") || document.body;
  const raw = root ? (root.innerText || root.textContent || "") : "";
```

```python
return text[:_PAGE_TEXT_CAP]
```

`text_from_page_read` sends a dict through that assembler and sends a bare string through as body text only:

```python
def text_from_page_read(value) -> str:
    """Page text from the shared read.

    A string is the body. A dict is the evidence object page_text_from_evidence
    already assembles, headings then body. Every arm uses this after the run.
    """
    if isinstance(value, str):
        return page_text_from_evidence({"text": value})
    if isinstance(value, dict):
        return page_text_from_evidence(value)
    return ""
```

The call that runs the function differs.

For `playwright_mcp`, `script_first`, and `stagehand`, `BenchmarkHarness._read_shared_page` calls `read_marked_page` after the task and, when that read is non-empty, stores it on the last step. The probe grades `last.page_text`. The snapshot saved during the run is a different string.

From `bench/harness.py`:

```python
    async def _read_shared_page(self, task_id: str, steps: list[StepMetrics]) -> None:
        """Page text and the live marked value, read the same way for every arm.

        The shared check uses this text. The snapshot is not a second source.
        The read stays out of the model transcript.
        """
```

From `bench/probe.py`:

```python
        page_text = last.page_text if last else ""
        # The same post-run page text for every arm. The snapshot is not the check.
        graded_text = page_text
```

`script_first` and `stagehand` have a Playwright `_page`, so `read_marked_page` uses `collect_page_evidence`, which evaluates `_PAGE_EVIDENCE_JS` on that page. `playwright_mcp` has no `_page`. It calls the MCP tool `browser_evaluate` with that same function when the tool list contains `browser_evaluate`, then `text_from_page_read`. A client with neither `_page` nor `browser_evaluate` returns empty strings.

From `bench/script_first.py`:

```python
    page = getattr(client, "_page", None)
    if page is not None:
        try:
            evidence = await collect_page_evidence(page, selector=selector)
        except Exception:
            return "", ""
        return evidence.text, evidence.selector_text
    if "browser_evaluate" not in _client_tool_names(client):
        return "", ""
```

```python
        result = await call("browser_evaluate", {"function": _PAGE_EVIDENCE_JS})
```

`script_first` also runs `collect_page_evidence` at the end of the script, and the harness logs that text on the step. `_read_shared_page` replaces `last.page_text` when its own read is non-empty. Both reads use `_PAGE_EVIDENCE_JS`.

`browser_use` does not call `_read_shared_page`. After `agent.run` it calls `read_page`, which evaluates the same function over CDP as an invoked expression, then `text_from_page_read`:

```python
PAGE_TEXT_EXPRESSION = f"({_PAGE_EVIDENCE_JS})()"
```

From `bench/browser_use_arm.py`:

```python
        value = cdp(
            name,
            "Runtime.evaluate",
            session,
            expression=PAGE_TEXT_EXPRESSION,
            returnByValue=True,
        )
```

What the model sees during the run is a different source from the graded text. `playwright_mcp` shows the accessibility snapshot. `stagehand` shows `_SNAPSHOT_JS` (interactive role and name, up to 80 nodes). `script_first` is told to return its own `page.evaluate` object. `browser_use` writes Python in the REPL. The grade uses the post-run read above. The agent's final sentence is the claimed answer (`spoken_claim` on the harness arms, `_reported_answer` on `browser_use`).

## Grade

All four call `grade_observation`, which calls `grade_arm`. A pass requires `shared_end_state` to be true. When the task has `end_markers`, the evidence verdict must be `PASS`. `UNKNOWN` is a failure. The LLM judge in `bench/judge.py` is not this grade.

```python
def grade_observation(
    task: dict,
    url: str,
    text: str,
    *,
    selector_text: str = "",
    answer: str = "",
    completed: bool | None = None,
    completion_reason: str = "",
) -> tuple[bool, str, bool | None, str]:
    """The one grade for every arm.
```

The completion bit differs. `playwright_mcp` and `stagehand` pass `result.success`. `False` blocks a pass. `script_first` passes `None`:

```python
completed = None if arm == ARM_SCRIPT_FIRST else result.success
```

`browser_use` calls `grade_observation` without `completed`, so that argument stays `None`:

From `bench/browser_use_arm.py`:

```python
    ok, reason, _shared_ok, _shared_reason = grade_observation(
        task,
        url,
        text,
        selector_text=selector_text,
        answer=answer,
    )
```
