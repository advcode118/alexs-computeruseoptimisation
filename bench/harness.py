"""Harness that runs browser tasks via @playwright/mcp with claude-sonnet-5-5.

@playwright/mcp 0.0.84 speaks newline-delimited JSON-RPC on stdio. Notifications
have no id and get no reply. The model context keeps the task plus the last
few turns, and each tool result is capped before it is sent.

Logs per-task metrics: wall time split (model vs tool vs other), steps,
input/output tokens, snapshot tokens per step, and success. Page snapshots
from the run are written under the run directory for a later offline replay.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from bench.budget import (
    ALLOWED_MODEL,
    ANTHROPIC_VERSION,
    BudgetExceeded,
    SpendLedger,
    assert_allowed_model,
)
from proxy.ignores import IgnoreCounter, annotate_tool_description

PLAYWRIGHT_MCP_VERSION = "0.0.84"
DEFAULT_MODEL = ALLOWED_MODEL
MCP_LINE_LIMIT = 16 * 1024 * 1024
MAX_HISTORY_PAIRS = 6
MAX_SNAPSHOT_CHARS = 8000
_TRUNCATION_NOTE = "\n[snapshot truncated]"

_NAVIGATE_TOOLS = frozenset(
    {
        "browser_navigate",
        "browser_navigate_back",
        "browser_navigate_forward",
        "browser_reload",
    }
)
_FIND_TOOLS = frozenset({"browser_find"})
_ACTION_TOOLS = frozenset(
    {
        "browser_click",
        "browser_type",
        "browser_hover",
        "browser_drag",
        "browser_drop",
        "browser_select_option",
        "browser_press_key",
        "browser_fill_form",
        "browser_file_upload",
        "browser_handle_dialog",
        "browser_wait_for",
        "browser_mouse_click_xy",
        "browser_mouse_move_xy",
        "browser_mouse_drag_xy",
        "browser_mouse_wheel",
    }
)

_SNAPSHOT_FENCE = re.compile(
    r"### Snapshot\s*```(?:ya?ml)?\s*\n(.*?)```",
    re.IGNORECASE | re.DOTALL,
)
_PAGE_FIELD = re.compile(r"(?m)^- Page ([A-Za-z]+):\s*(.+?)\s*$")
_JSON_URL = re.compile(r'"url"\s*:\s*"(https?://[^"\\]+)"')
_GOTO_URL = re.compile(r"\bgoto\s+(https?://[^\s'\"<>]+)", re.IGNORECASE)
_QUOTED_GOTO = re.compile(
    r"""\bpage\.goto\(\s*(['"])(https?://.+?)\1""",
    re.IGNORECASE,
)
_URL_TRAILING = ".,;)]}>\"'"

SYSTEM_PROMPT = """You are a browser automation agent. You have access to tools for controlling a web browser.
Your goal is to complete the given task by using the browser tools.

Guidelines:
- Use browser_snapshot to see the current page state
- Use browser_click with target (ref like "S1E2") to click elements
- Use browser_type with target and text to type into fields
- Use browser_navigate with url to navigate to pages
- When the task is complete, respond with TASK_COMPLETE. If the task asks for a value, such as a title, a name, or a number, put that exact value in the same reply
- If you cannot complete the task, respond with TASK_FAILED and explain why

Be efficient - try to complete the task in as few steps as possible."""


@dataclass
class StepMetrics:
    """Metrics for a single step in a task run."""

    step_number: int
    tool_name: str
    tool_args: dict
    tool_result_size: int
    snapshot_tokens: int
    model_time_ms: float
    tool_time_ms: float
    input_tokens: int
    output_tokens: int
    snapshot_text: str = ""
    snapshot_file: str = ""
    page_url: str = ""
    page_title: str = ""
    # Judge read of answer_equals_selector. Logged, never sent to the model.
    selector_text: str = ""
    # What the script claimed, and the page text the evidence judge read.
    # The shared URL/text check does not use these. They stay out of the model prompt.
    claimed_answer: str = ""
    page_text: str = ""
    # The script's own return. The shared grade checks these against the live page.
    claimed_url: str = ""
    claimed_title: str = ""
    claimed_h1: str = ""
    claimed_key_text: str = ""
    claimed_values: tuple[str, ...] = ()
    claimed_rejected: bool = False
    # script_first only: what the runtime self-check saw and decided, for offline replay.
    self_check: dict = field(default_factory=dict)


@dataclass
class TaskResult:
    """Result of running a single task."""

    task_id: str
    task_description: str
    success: bool
    success_reason: str
    total_steps: int
    total_wall_ms: float
    total_model_ms: float
    total_tool_ms: float
    total_other_ms: float
    total_input_tokens: int
    total_output_tokens: int
    total_snapshot_tokens: int
    steps: list[StepMetrics] = field(default_factory=list)
    error: str | None = None
    # Full-page observes the outer model issued after an action already returned a compact diff.
    model_ignores_tools: int = 0
    # do_task_segment results whose tier was replay. The outer model still ran.
    replay_hits: int = 0
    # script_first end-state: PASS, FAIL, UNKNOWN, or empty for other arms.
    end_state: str = ""
    # script_first tier that answered: cache_hit, patched, or fresh.
    tier: str = ""
    model_calls: int = 0
    # Actions the last script ran.
    script_steps: int = 0
    # OpenAI cached input tokens. Claude stays at 0; those reads use the recorded rate.
    total_cached_tokens: int = 0
    # Cache writes are a slice of input tokens. Claude stays at 0.
    total_cache_write_30m_tokens: int = 0
    total_cache_write_12h_tokens: int = 0
    repair_sent: bool = False
    repair_reply: str = "none"
    # script_first: one entry per script that ran: [self-check verdict, wall ms since the task started].
    script_turns: list = field(default_factory=list)
    strategy: str = ""
    strategy_detail: dict = field(default_factory=dict)


def estimate_tokens(text: str) -> int:
    """Rough token estimate (chars / 4)."""
    return max(1, len(text) // 4)


def encode_ndjson(payload: dict) -> bytes:
    """One JSON-RPC object per line. No Content-Length header."""
    return json.dumps(payload, separators=(",", ":")).encode() + b"\n"


def cap_snapshot_text(text: str, limit: int = MAX_SNAPSHOT_CHARS) -> str:
    """Shorten a tool result before it is placed in the model context."""
    if len(text) <= limit:
        return text
    if limit <= len(_TRUNCATION_NOTE):
        return _TRUNCATION_NOTE[:limit]
    return text[: limit - len(_TRUNCATION_NOTE)] + _TRUNCATION_NOTE


def cap_messages_for_model(
    messages: list[dict],
    max_pairs: int = MAX_HISTORY_PAIRS,
    *,
    script_first: bool = False,
) -> list[dict]:
    """Keep the opening task and the last few assistant/tool pairs.

    Tool results are shortened. The stored history is left intact.
    """
    if not messages:
        return []
    head = messages[0]
    rest = messages[1:]
    pairs: list[list[dict]] = []
    bucket: list[dict] = []
    for message in rest:
        bucket.append(message)
        if len(bucket) == 2:
            pairs.append(bucket)
            bucket = []
    if bucket:
        pairs.append(bucket)
    kept = [message for pair in pairs[-max_pairs:] for message in pair]
    return [_cap_message(message, script_first=script_first) for message in (head, *kept)]


def _cap_message(message: dict, *, script_first: bool = False) -> dict:
    content = message.get("content")
    if not isinstance(content, list):
        return message
    blocks = []
    changed = False
    for block in content:
        if (
            isinstance(block, dict)
            and block.get("type") == "tool_result"
            and isinstance(block.get("content"), str)
        ):
            if script_first:
                from bench.script_first import budget_script_result

                capped = budget_script_result(block["content"], MAX_SNAPSHOT_CHARS)
            else:
                capped = cap_snapshot_text(block["content"])
            if capped != block["content"]:
                changed = True
                block = {**block, "content": capped}
        blocks.append(block)
    if not changed:
        return message
    return {**message, "content": blocks}


def snapshot_tokens_for(tool_name: str, result_text: str) -> int:
    """Token estimate for a response that carries a page snapshot.

    Navigate and find responses are included along with action responses
    and browser_snapshot. The whole tool result is counted, matching the
    text the model would read.
    """
    if not result_text or not _carries_snapshot(tool_name, result_text):
        return 0
    return estimate_tokens(result_text)


def _carries_snapshot(tool_name: str, result_text: str) -> bool:
    name = tool_name or ""
    lowered = result_text.lower()
    if name == "browser_snapshot" or name in _NAVIGATE_TOOLS or name in _FIND_TOOLS:
        return True
    if "snapshot" in lowered[:100]:
        return True
    if name in _ACTION_TOOLS and ("snapshot" in lowered or "[ref=" in result_text):
        return True
    return False


def page_field(result_text: str, label: str) -> str:
    """Read `- Page URL:` or `- Page Title:` from a tool response."""
    for match in _PAGE_FIELD.finditer(result_text or ""):
        if match.group(1).lower() == label.lower():
            return match.group(2).strip()
    return ""


def _clean_url(value: str) -> str:
    return (value or "").strip().rstrip(_URL_TRAILING)


def _remember_url(found: list[tuple[int, str]], pos: int, url: str) -> None:
    cleaned = _clean_url(url)
    if cleaned.startswith(("http://", "https://")):
        found.append((pos, cleaned))


def _last_url(found: list[tuple[int, str]]) -> str:
    if not found:
        return ""
    found.sort(key=lambda item: item[0])
    return found[-1][1]


def page_url_from_result(result_text: str) -> str:
    """URL for the judge. A `- Page URL:` line wins; otherwise the last reported URL.

    Stagehand emits a JSON url, `Ran goto https://...`, `- Page URL:`, and
    sometimes `page.goto("https://...")` in a failure. The live page URL is
    appended last, so an earlier goto in the script does not hide the page a
    click opened. A compact diff that only names full_snapshot_chars does not
    invent a URL.
    """
    text = result_text or ""
    page_lines: list[tuple[int, str]] = []
    found: list[tuple[int, str]] = []
    for match in _PAGE_FIELD.finditer(text):
        if match.group(1).lower() == "url":
            _remember_url(page_lines, match.start(), match.group(2))
    if page_lines:
        return _last_url(page_lines)
    stripped = text.strip()
    if stripped.startswith("{"):
        try:
            data = json.loads(stripped)
        except json.JSONDecodeError:
            data = None
        if isinstance(data, dict):
            url = data.get("url")
            if isinstance(url, str):
                _remember_url(found, 0, url)
    for line_start, line in _line_spans(text):
        body = line.strip()
        if not body.startswith("{"):
            continue
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and isinstance(data.get("url"), str):
            _remember_url(found, line_start, data["url"])
    for match in _JSON_URL.finditer(text):
        _remember_url(found, match.start(), match.group(1))
    for match in _GOTO_URL.finditer(text):
        _remember_url(found, match.start(), match.group(1))
    for match in _QUOTED_GOTO.finditer(text):
        _remember_url(found, match.start(), match.group(2))
    return _last_url(found)


def _line_spans(text: str) -> list[tuple[int, str]]:
    spans: list[tuple[int, str]] = []
    offset = 0
    for line in text.splitlines(keepends=True):
        spans.append((offset, line))
        offset += len(line)
    return spans


def logged_evidence(payload: dict | None) -> tuple[str, str, str, dict]:
    """Selector, claimed answer, page text, and the script's full return.

    selector_text stays out of the model message. The caller logs it on the step.
    The return keeps the URL, title, key text, and values the shared grade checks.
    """
    from bench.script_first import claimed_from_payload

    data = payload if isinstance(payload, dict) else {}
    selector = data.get("selector_text") if isinstance(data.get("selector_text"), str) else ""
    text = data.get("text") if isinstance(data.get("text"), str) else ""
    claim = claimed_from_payload(data)
    returned = {
        "url": claim.url,
        "title": claim.title,
        "h1": claim.h1,
        "key_text": claim.key_text,
        "values": claim.values,
        "rejected": claim.rejected,
    }
    return selector, claim.answer, text, returned


def claim_from_step(step) -> "ClaimedEvidence":
    """The script return stored on a step. The shared grade checks this object."""
    from bench.script_first import ClaimedEvidence

    return ClaimedEvidence(
        url=step.claimed_url or "",
        title=step.claimed_title or "",
        h1=step.claimed_h1 or "",
        answer=step.claimed_answer or "",
        key_text=step.claimed_key_text or "",
        values=tuple(step.claimed_values or ()),
        rejected=bool(step.claimed_rejected),
    )


def self_check_record(payload: dict | None, page_url: str, start_url: str, verdict) -> dict:
    """The runtime self-check's inputs and verdict for one script, for offline replay.

    Logged on the probe row only. Controls are dropped to keep rows small.
    """
    data = {k: v for k, v in (payload or {}).items() if k != "controls"} if isinstance(payload, dict) else {}
    return {
        "payload": data,
        "page_url": page_url or "",
        "start_url": start_url or "",
        "verdict": getattr(verdict, "verdict", ""),
        "reason": getattr(verdict, "reason", ""),
    }


def claim_step_fields(returned: dict | None) -> dict:
    """Step fields for the script return. Empty when the tool logged none."""
    data = returned if isinstance(returned, dict) else {}
    values = data.get("values") or ()
    return {
        "claimed_url": data.get("url") or "",
        "claimed_title": data.get("title") or "",
        "claimed_h1": data.get("h1") or "",
        "claimed_key_text": data.get("key_text") or "",
        "claimed_values": tuple(item for item in values if isinstance(item, str)),
        "claimed_rejected": bool(data.get("rejected")),
    }


def spoken_claim(text: str) -> str:
    """What an arm claimed when it said the task was done.

    TASK_COMPLETE is the stop token, not the answer. The remaining text is
    the same kind of claim browser_use reads from the agent's final result.
    """
    pieces = []
    for line in (text or "").replace("TASK_COMPLETE", "\n").splitlines():
        cleaned = " ".join(line.split())
        if cleaned:
            pieces.append(cleaned)
    return "\n".join(pieces)


def extract_page_snapshot(result_text: str) -> str:
    """Pull the accessibility tree out of a playwright-mcp tool response."""
    if not result_text:
        return ""
    fenced = _SNAPSHOT_FENCE.search(result_text)
    if fenced:
        return fenced.group(1).strip()
    lines = []
    for line in result_text.splitlines():
        if line.strip().startswith("- Page "):
            continue
        if "[ref=" in line:
            lines.append(line)
    return "\n".join(lines).strip()


def playwright_mcp_args(*, headless: bool, snapshot_mode: str) -> list[str]:
    """Plain Playwright MCP, one private browser per process.

    --isolated keeps the profile in memory. @playwright/mcp@0.0.84 rejects
    --isolated together with --user-data-dir, so this argv is --isolated only.
    Sequential arms each get their own process.
    """
    args = [
        "npx",
        f"@playwright/mcp@{PLAYWRIGHT_MCP_VERSION}",
        "--isolated",
    ]
    if headless:
        args.append("--headless")
    args.extend(["--snapshot-mode", snapshot_mode])
    return args


def result_is_replay(text: str) -> bool:
    """True when a proxy tool result says the stored sequence ran."""
    compact = (text or "").replace(" ", "")
    return '"tier":"replay"' in compact


def _annotate_snapshot_file(path: Path, tool_use: dict, action_step: int) -> None:
    """Attach the model action that was taken on this saved page."""
    data = json.loads(path.read_text(encoding="utf-8"))
    data["captured_on_step"] = data.get("step_number")
    data["step_number"] = action_step
    data["model_tool_name"] = tool_use.get("name")
    data["model_tool_args"] = tool_use.get("input") or {}
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


class PlaywrightMCPClient:
    """Client that communicates with @playwright/mcp over stdio.

    The server speaks newline-delimited JSON. A notification has a method and
    no id; it is not a response and this client does not wait for one.
    """

    def __init__(self, headless: bool = True, snapshot_mode: str = "full", argv: list[str] | None = None):
        self.headless = headless
        self.snapshot_mode = snapshot_mode
        self.argv = list(argv) if argv is not None else None
        self.process: asyncio.subprocess.Process | None = None
        self._request_id = 0
        self._tools: list[dict] = []
        self._stderr_task: asyncio.Task | None = None
        self._profile_dir: str | None = None

    async def start(self) -> None:
        """Start the @playwright/mcp process, or the proxy, with its own browser."""
        env = os.environ.copy()
        if self.argv is not None:
            args = list(self.argv)
            # The proxy child inherits this. It does not share the caller's shell.
            if self.headless:
                env["PLAYWRIGHT_MCP_HEADLESS"] = "1"
            else:
                env.pop("PLAYWRIGHT_MCP_HEADLESS", None)
        else:
            args = playwright_mcp_args(
                headless=self.headless,
                snapshot_mode=self.snapshot_mode,
            )

        # On Windows npx is npx.cmd, which CreateProcess only finds by full path.
        args = [shutil.which(args[0]) or args[0], *args[1:]]
        try:
            self.process = await asyncio.create_subprocess_exec(
                *args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                limit=MCP_LINE_LIMIT,
            )
        except BaseException:
            self._discard_profile()
            raise
        self._stderr_task = asyncio.create_task(self._drain_stderr())
        try:
            await self._initialize()
        except BaseException:
            await self.stop()
            raise

    async def _drain_stderr(self) -> None:
        if self.process is None or self.process.stderr is None:
            return
        while True:
            line = await self.process.stderr.readline()
            if not line:
                return

    async def _write(self, payload: dict) -> None:
        if self.process is None or self.process.stdin is None:
            raise RuntimeError("MCP process not started")
        raw = encode_ndjson(payload)
        self.process.stdin.write(raw)
        await self.process.stdin.drain()

    async def _send_request(self, method: str, params: dict | None = None) -> dict:
        """Send a JSON-RPC request and wait for the matching response id."""
        self._request_id += 1
        request_id = self._request_id
        request: dict = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
        }
        if params:
            request["params"] = params
        await self._write(request)
        return await self._read_response(request_id)

    async def _send_notification(self, method: str, params: dict | None = None) -> None:
        """Send a notification. There is no id and no response to wait for."""
        payload: dict = {"jsonrpc": "2.0", "method": method}
        if params:
            payload["params"] = params
        await self._write(payload)

    async def _read_message(self) -> dict:
        """Read one JSON object. Skip blank lines and non-JSON log lines."""
        if self.process is None or self.process.stdout is None:
            raise RuntimeError("MCP process not started")
        while True:
            line = await self.process.stdout.readline()
            if not line:
                raise RuntimeError("MCP process ended unexpectedly")
            stripped = line.strip()
            if not stripped or stripped[:1] not in (b"{", b"["):
                continue
            try:
                data = json.loads(stripped.decode())
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict):
                return data

    async def _read_response(self, request_id: int) -> dict:
        """Return the message with this id. Notifications are not that message."""
        while True:
            message = await self._read_message()
            if message.get("id") == request_id:
                return message

    async def _initialize(self) -> None:
        """Initialize the MCP connection and get tools list."""
        await self._send_request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "bench-harness", "version": "0.1.0"},
            },
        )
        await self._send_notification("notifications/initialized")
        response = await self._send_request("tools/list")
        self._tools = response.get("result", {}).get("tools", [])

    @property
    def tools(self) -> list[dict]:
        """Get available tools."""
        return self._tools

    def tools_for_claude(self) -> list[dict]:
        """Convert MCP tools to Claude tool format."""
        claude_tools = []
        for tool in self._tools:
            name = tool["name"]
            claude_tools.append(
                {
                    "name": name,
                    "description": annotate_tool_description(name, tool.get("description", "")),
                    "input_schema": tool.get("inputSchema", {"type": "object", "properties": {}}),
                }
            )
        return claude_tools

    async def call_tool(self, name: str, arguments: dict) -> tuple[str, float]:
        """Call a tool and return (result_text, time_ms)."""
        start = time.perf_counter()
        response = await self._send_request(
            "tools/call",
            {"name": name, "arguments": arguments},
        )
        elapsed_ms = (time.perf_counter() - start) * 1000

        result = response.get("result", {})
        content = result.get("content", [])
        text_parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text_parts.append(item.get("text", ""))
        return "\n".join(text_parts), elapsed_ms

    async def stop(self) -> None:
        """Stop the MCP process."""
        if self._stderr_task is not None:
            self._stderr_task.cancel()
            try:
                await self._stderr_task
            except asyncio.CancelledError:
                pass
            self._stderr_task = None
        if self.process:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self.process.kill()
            self.process = None
        self._discard_profile()

    def _discard_profile(self) -> None:
        profile = self._profile_dir
        self._profile_dir = None
        if profile:
            shutil.rmtree(profile, ignore_errors=True)


def cached_prompt_prefix(system: str, tools: list[dict]) -> tuple[list[dict], list[dict]]:
    """Anthropic cache breakpoint on a stable system prompt and its tool schema.

    The last tool and the system block are marked. Messages are not. The task,
    the page, and judge markers stay outside this prefix. Cache reads are still
    input tokens at the recorded ledger rate.
    """
    marked = []
    for index, tool in enumerate(tools):
        item = dict(tool)
        if index == len(tools) - 1:
            item["cache_control"] = {"type": "ephemeral"}
        marked.append(item)
    return [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}], marked


def message_payload(
    model: str,
    messages: list[dict],
    tools: list[dict],
    system: str | None,
    max_tokens: int,
    *,
    cache_prefix: bool,
    tool_choice: dict | None = None,
) -> dict:
    """The JSON body of one Messages request. This does not open a connection."""
    system_text = system or SYSTEM_PROMPT
    sent_system: str | list = system_text
    sent_tools: list = list(tools)
    if cache_prefix:
        sent_system, sent_tools = cached_prompt_prefix(system_text, sent_tools)
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "system": sent_system,
        "messages": messages,
        "tools": sent_tools,
    }
    if tool_choice is not None:
        payload["tool_choice"] = tool_choice
    return payload


class AnthropicClient:
    """Simple Anthropic API client for tool use. claude-sonnet-5-5 only."""

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL):
        self.api_key = api_key
        self.model = assert_allowed_model(model)
        self.base_url = "https://api.anthropic.com/v1/messages"
        # script_first sets this. Other arms send the system prompt as a string.
        self.cache_prefix = False

    async def create_message(
        self,
        messages: list[dict],
        tools: list[dict],
        system: str | None = None,
        max_tokens: int = 4096,
        tool_choice: dict | None = None,
    ) -> tuple[dict, float]:
        """Create a message and return (response, time_ms)."""
        assert_allowed_model(self.model)
        import urllib.request

        payload = message_payload(
            self.model,
            messages,
            tools,
            system,
            max_tokens,
            cache_prefix=self.cache_prefix,
            tool_choice=tool_choice,
        )

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        }

        start = time.perf_counter()

        def do_request():
            req = urllib.request.Request(
                self.base_url,
                data=json.dumps(payload).encode(),
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.loads(resp.read().decode())

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, do_request)
        elapsed_ms = (time.perf_counter() - start) * 1000

        return response, elapsed_ms


class BenchmarkHarness:
    """Main harness for running benchmark tasks."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
        headless: bool = True,
        max_steps: int = 30,
        runs_dir: Path | None = None,
        snapshot_dir: Path | None = None,
        arm: str = "playwright_mcp",
        script_cache=None,
        provider: str = "anthropic",
        effort: str | None = None,
    ):
        from bench.arms import prompt_for

        self.provider = provider
        self.arm = arm
        self.system_prompt = prompt_for(arm)
        if provider == "openai":
            from bench.openai_spend import EffortNotAllowed, assert_effort, assert_openai_model

            self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
            self.model = assert_openai_model(model)
            self.effort = assert_effort(self.model, effort or "")
        elif provider == "anthropic":
            if effort not in (None, ""):
                from bench.openai_spend import EffortNotAllowed

                raise EffortNotAllowed("Claude does not take --effort.")
            self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
            self.model = assert_allowed_model(model)
            self.effort = None
        else:
            raise ValueError(f"unknown provider {provider!r}")
        self.headless = headless
        self.max_steps = max_steps
        self.runs_dir = runs_dir or Path(__file__).parent / "runs"
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self.snapshot_dir = snapshot_dir
        # script_first only. None keeps every run on the fresh path.
        self.script_cache = script_cache

        self.mcp_client: PlaywrightMCPClient | None = None
        self.anthropic: AnthropicClient | None = None
        self._capture_index = 0
        self._pending_snapshot_path: Path | None = None
        # In flight while the model writes. None for arms that start first.
        self._browser_launch: asyncio.Future | None = None

    def has_api_key(self) -> bool:
        """Check if we have an API key configured."""
        return bool(self.api_key)

    def _begin_browser_launch(self) -> None:
        """Start script_first's Chrome if it is not already launching.

        The launch does not open the task URL. Other arms have no begin_launch,
        so this leaves them on the browser setup already started.
        """
        if self.arm != "script_first" or self._browser_launch is not None:
            return
        client = self.mcp_client
        begin = getattr(client, "begin_launch", None)
        if not callable(begin):
            return
        self._browser_launch = begin()

    async def _wait_for_browser(self) -> None:
        """Block until script_first's Chrome launch has finished."""
        launch = self._browser_launch
        if launch is not None:
            await launch

    async def setup(self) -> None:
        """Set up clients.

        script_first returns while Chrome is still launching, so the model
        can write during that launch. The launch does not open the task URL.
        """
        if self.api_key:
            if self.provider == "openai":
                from bench.openai_client import OpenAIClient

                self.anthropic = OpenAIClient(self.api_key, self.model, self.effort or "")
            else:
                self.anthropic = AnthropicClient(self.api_key, self.model)
                # The stable script_first prompt and the patch prompt. Other arms stay uncached.
                self.anthropic.cache_prefix = self.arm == "script_first"

        from bench.arms import build_client

        self.mcp_client = build_client(self.arm, headless=self.headless)
        if self.arm == "script_first":
            self._begin_browser_launch()
            return
        await self.mcp_client.start()

    async def teardown(self) -> None:
        """Close the browser after an in-flight launch has finished."""
        launch = self._browser_launch
        self._browser_launch = None
        if launch is not None:
            try:
                await launch
            except (asyncio.CancelledError, Exception):
                pass
        if self.mcp_client:
            await self.mcp_client.stop()
            self.mcp_client = None

    def _write_page_snapshot(
        self,
        *,
        task_id: str,
        step_number: int,
        tool_name: str,
        snapshot_text: str,
        page_url: str,
        page_title: str,
    ) -> Path | None:
        """Save the page tree from a tool response. The next model action is added later."""
        if self.snapshot_dir is None or not snapshot_text:
            return None
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        self._capture_index += 1
        path = self.snapshot_dir / f"{self._capture_index:03d}_{task_id}_step{step_number}.json"
        payload = {
            "task_id": task_id,
            "step_number": step_number,
            "url": page_url,
            "title": page_title,
            "snapshot_text": snapshot_text,
            "model_tool_name": None,
            "model_tool_args": {},
            "captured_by": tool_name,
            "source": "run",
        }
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return path

    def _page_passes_shared(self, task_id: str, step: StepMetrics | None) -> bool:
        """The shared check on the page the script left. An evidence PASS is not enough."""
        from bench.probe import shared_check_passes

        if step is None:
            return False
        return shared_check_passes(
            task_id,
            step.page_url,
            step.page_text,
            selector=step.selector_text,
            answer=step.claimed_answer,
            claimed=claim_from_step(step),
        )

    async def _cached_script_tier(
        self,
        *,
        task_id: str,
        task_description: str,
        start_url: str,
        markers: dict,
        steps: list[StepMetrics],
    ) -> dict:
        """Replay a cached script, then one patch turn. Every run is judged again.

        tier stays empty when neither passed. The entry is then dropped and
        the caller runs the fresh path.
        """
        from bench.script_cache import (
            PATCH_PROMPT,
            PATCH_TOOL,
            TIER_CACHE_HIT,
            TIER_PATCHED,
            apply_patch,
            fingerprint_from_payload,
            patch_request,
        )
        from bench.script_first import (
            PASS,
            EvidenceVerdict,
            script_runtime_verdict,
            task_asks_value,
        )
        from proxy.script import ScriptError

        outcome = {
            "tier": "",
            "verdict": None,
            "page_url": "",
            "model_ms": 0.0,
            "tool_ms": 0.0,
            "input_tokens": 0,
            "output_tokens": 0,
            "cached_tokens": 0,
            "cache_write_30m_tokens": 0,
            "cache_write_12h_tokens": 0,
            "model_calls": 0,
            "script_steps": 0,
        }
        cache = self.script_cache
        entry = cache.lookup(task_description, start_url)
        if entry is None:
            return outcome

        async def run(code: str, model_ms: float = 0.0, input_tokens: int = 0, output_tokens: int = 0):
            result_text, tool_ms = await self.mcp_client.call_tool("run_script", {"code": code})
            outcome["tool_ms"] += tool_ms
            page_url = page_url_from_result(result_text)
            # The live check has no answer key. The final grade still does.
            verdict, payload = script_runtime_verdict(
                result_text,
                page_url,
                start_url,
                asks_value=task_asks_value(task_description),
                task=task_description,
            )
            selector_text, claimed_answer, page_text, returned = logged_evidence(payload)
            steps.append(
                StepMetrics(
                    step_number=len(steps) + 1,
                    tool_name="run_script",
                    tool_args={"code": code},
                    tool_result_size=len(result_text),
                    snapshot_tokens=0,
                    model_time_ms=model_ms,
                    tool_time_ms=tool_ms,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    page_url=page_url,
                    page_title=page_field(result_text, "Title"),
                    selector_text=selector_text,
                    claimed_answer=claimed_answer,
                    page_text=page_text,
                    **claim_step_fields(returned),
                    self_check=self_check_record(payload, page_url, start_url, verdict),
                )
            )
            outcome["verdict"] = verdict
            outcome["page_url"] = page_url
            outcome["script_steps"] = int(payload.get("steps") or 0)
            passed = verdict.verdict == PASS and page_url.startswith(("http://", "https://"))
            return passed, verdict, payload

        passed, verdict, payload = await run(entry.script)
        live_fp = fingerprint_from_payload(payload, start_url)
        if passed and live_fp == entry.fingerprint:
            outcome["tier"] = TIER_CACHE_HIT
            return outcome
        if passed and live_fp != entry.fingerprint:
            verdict = EvidenceVerdict(
                "FAIL",
                "live page fingerprint does not match the cached page",
                verdict.scored_url,
            )

        response, model_ms = await self.anthropic.create_message(
            [
                {
                    "role": "user",
                    "content": patch_request(
                        description=task_description,
                        start_url=start_url,
                        script=entry.script,
                        payload=payload,
                        verdict=verdict,
                    ),
                }
            ],
            [PATCH_TOOL],
            system=PATCH_PROMPT,
        )
        usage = response.get("usage", {})
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        outcome["model_calls"] += 1
        outcome["model_ms"] += model_ms
        outcome["input_tokens"] += input_tokens
        outcome["output_tokens"] += output_tokens
        outcome["cached_tokens"] += int(usage.get("cached_tokens") or 0)
        outcome["cache_write_30m_tokens"] += int(usage.get("cache_write_30m_tokens") or 0)
        outcome["cache_write_12h_tokens"] += int(usage.get("cache_write_12h_tokens") or 0)
        patch = next(
            (
                block.get("input")
                for block in response.get("content", [])
                if block.get("type") == "tool_use" and block.get("name") == PATCH_TOOL["name"]
            ),
            None,
        )
        patched = ""
        if isinstance(patch, dict):
            try:
                patched = apply_patch(entry.script, int(patch.get("step")), str(patch.get("code") or ""))
            except (ScriptError, TypeError, ValueError):
                patched = ""
        if patched:
            passed, verdict, patched_payload = await run(patched, model_ms, input_tokens, output_tokens)
            if passed:
                cache.save(
                    task_description,
                    start_url,
                    patched,
                    verdict,
                    controls=patched_payload.get("controls"),
                    landed_url=patched_payload.get("url") if isinstance(patched_payload.get("url"), str) else "",
                )
                outcome["tier"] = TIER_PATCHED
                return outcome
        cache.drop(task_description, start_url)
        return outcome

    def _apply_spoken_claim(self, steps: list[StepMetrics], claim: str) -> None:
        """Record the completion text as the claimed answer.

        script_first already logged its claim from the script. TASK_COMPLETE
        is not the answer. The page read is separate and runs for every arm.
        """
        if not steps:
            steps.append(
                StepMetrics(
                    step_number=1,
                    tool_name="",
                    tool_args={},
                    tool_result_size=0,
                    snapshot_tokens=0,
                    model_time_ms=0.0,
                    tool_time_ms=0.0,
                    input_tokens=0,
                    output_tokens=0,
                    claimed_answer=claim,
                )
            )
            return
        steps[-1].claimed_answer = claim

    async def _read_shared_page(self, task_id: str, steps: list[StepMetrics]) -> None:
        """Page text and the live marked value, read the same way for every arm.

        The shared check uses this text. The snapshot is not a second source.
        The read stays out of the model transcript.
        """
        from bench.script_first import read_marked_page
        from bench.tasks import markers_for_task

        if not steps or self.mcp_client is None:
            return
        markers = markers_for_task(task_id)
        wanted = markers.get("answer_equals_selector")
        selector = wanted if isinstance(wanted, str) else ""
        last = steps[-1]
        page_text, marked = await read_marked_page(self.mcp_client, selector)
        if page_text:
            last.page_text = page_text
        if marked:
            last.selector_text = marked

    async def run_task(
        self,
        task_id: str,
        task_description: str,
        start_url: str,
        expected_answer: str | None = None,
        judge_prompt: str | None = None,
        check_url_contains: str | None = None,
    ) -> TaskResult:
        """Run a single task and collect metrics."""
        del expected_answer, judge_prompt
        if not self.anthropic:
            missing = "OPENAI_API_KEY not set" if self.provider == "openai" else "ANTHROPIC_API_KEY not set"
            return self._empty_result(
                task_id,
                task_description,
                "No API key configured",
                missing,
            )

        if not self.mcp_client:
            return self._empty_result(
                task_id,
                task_description,
                "MCP client not initialized",
                "MCP client not started",
            )

        wall_start = time.perf_counter()
        generic_start = wall_start
        steps: list[StepMetrics] = []
        total_model_ms = 0.0
        total_tool_ms = 0.0
        total_input_tokens = 0
        total_output_tokens = 0
        total_cached_tokens = 0
        total_cache_write_30m_tokens = 0
        total_cache_write_12h_tokens = 0
        total_snapshot_tokens = 0
        ignores = IgnoreCounter()
        replay_hits = 0
        last_url = ""
        self._pending_snapshot_path = None

        from bench.tasks import task_message

        messages: list[dict] = [
            {"role": "user", "content": task_message(task_description, start_url)}
        ]

        tools = self.mcp_client.tools_for_claude()
        step_num = 0
        success = False
        success_reason = "Max steps reached"
        spoken_answer = ""
        error: str | None = None
        expect_url = check_url_contains or ""
        turn_limit = self.max_steps
        script_calls = 0
        repairs_sent = 0
        awaiting_repair_reply = False
        repair_reply = "none"
        refusal_extended = False
        previous_payload: dict | None = None
        # Every earlier script payload in this run, for the self-check.
        earlier_payloads: list[dict] = []
        # script_first's grounded repair loop: scripts already run, and the last FAIL's outcome.
        seen_scripts: set[str] = set()
        last_fail_key: tuple | None = None
        same_fail_count = 0
        script_turns: list = []
        looks = 0
        end_state = ""
        last_verdict = None
        markers: dict = {}
        tier = ""
        model_calls = 0
        script_steps = 0
        passing_code = ""
        passing_verdict = None
        strategy = ""
        strategy_detail = {}
        cache = self.script_cache if self.arm == "script_first" else None
        if self.arm == "script_first":
            from bench.arms import SCRIPT_FIRST_HARD_CAP, script_first_repair_mode
            from bench.script_first import (
                FAIL,
                PASS,
                UNKNOWN,
                drop_old_snapshots,
                grounded_repair_request,
                model_visible_script_result,
                next_script_first_limit,
                normalized_script,
                repair_outcome_key,
                repair_request,
                script_made_progress,
                script_runtime_verdict,
                task_asks_value,
            )
            # No answer key while the run is live. The task's markers are read
            # only by the post-run grade, the same as for every other arm.
            turn_limit = min(self.max_steps, SCRIPT_FIRST_HARD_CAP)
            repair_mode = script_first_repair_mode()
            legacy_repair = repair_mode["legacy"]
            max_repairs = repair_mode["max_repairs"]
            max_scripts = 1 + max_repairs
            repair_budget_s = repair_mode["budget_s"]
            if hasattr(self.mcp_client, "end_markers"):
                self.mcp_client.end_markers = {}
            if hasattr(self.mcp_client, "look_task"):
                self.mcp_client.look_task = task_description

        try:
            if self.arm == "script_first":
                from bench.strategy_spa import maybe_run_spa

                spa = await maybe_run_spa(self, task_description=task_description, start_url=start_url)
                total_model_ms += spa.model_ms
                total_tool_ms += spa.tool_ms
                total_input_tokens += spa.input_tokens
                total_output_tokens += spa.output_tokens
                total_cached_tokens += spa.cached_tokens
                total_cache_write_30m_tokens += spa.cache_write_30m_tokens
                total_cache_write_12h_tokens += spa.cache_write_12h_tokens
                model_calls += spa.model_calls
                if spa.route:
                    strategy_detail = {"claimed": spa.claimed, "passed": spa.passed, "route": spa.route,
                                       "reason": spa.reason, "rounds": spa.rounds, "actions": spa.actions,
                                       "fetch_ms": spa.fetch_ms, "model_calls": spa.model_calls}
                if spa.claimed:
                    strategy = "spa" if spa.passed else "spa_fallback"
                if spa.passed:
                    tier = "specialist"
                    success, end_state, last_verdict = True, PASS, spa.verdict
                    success_reason = spa.reason
                    last_url = spa.evidence.url
                    steps.append(StepMetrics(
                        step_number=1, tool_name="spa", tool_args={"actions": spa.actions},
                        tool_result_size=0, snapshot_tokens=0, model_time_ms=spa.model_ms,
                        tool_time_ms=spa.tool_ms, input_tokens=spa.input_tokens, output_tokens=spa.output_tokens,
                        page_url=last_url, page_title=spa.evidence.title, page_text=spa.evidence.text,
                        claimed_answer=spa.answer,
                    ))
                if spa.claimed or spa.route:
                    # Specialist latency remains timed, but cannot consume the generic repair allowance.
                    generic_start = time.perf_counter()
            if cache is not None and not tier:
                # A cached script runs before any model write, so Chrome has to
                # be up first. A miss leaves the launch for the fresh model call.
                if cache.lookup(task_description, start_url) is not None:
                    self._begin_browser_launch()
                    await self._wait_for_browser()
                cached = await self._cached_script_tier(
                    task_id=task_id,
                    task_description=task_description,
                    start_url=start_url,
                    markers=markers,
                    steps=steps,
                )
                total_model_ms += cached["model_ms"]
                total_tool_ms += cached["tool_ms"]
                total_input_tokens += cached["input_tokens"]
                total_output_tokens += cached["output_tokens"]
                total_cached_tokens += int(cached.get("cached_tokens") or 0)
                total_cache_write_30m_tokens += int(cached.get("cache_write_30m_tokens") or 0)
                total_cache_write_12h_tokens += int(cached.get("cache_write_12h_tokens") or 0)
                model_calls += cached["model_calls"]
                if cached["tier"]:
                    tier = cached["tier"]
                    last_verdict = cached["verdict"]
                    end_state = PASS
                    success = True
                    success_reason = "Task completed successfully"
                    script_steps = cached["script_steps"]
                    last_url = cached["page_url"]
            step_base = len(steps)

            while not tier and step_num < turn_limit:
                step_num += 1

                self._begin_browser_launch()
                request_options = {}
                if self.arm == "script_first" and awaiting_repair_reply:
                    request_options["tool_choice"] = "required" if self.provider == "openai" else {"type": "any"}
                response, model_ms = await self.anthropic.create_message(
                    cap_messages_for_model(messages, script_first=self.arm == "script_first"),
                    tools,
                    system=self.system_prompt,
                    **request_options,
                )
                model_calls += 1
                total_model_ms += model_ms

                usage = response.get("usage", {})
                input_tokens = usage.get("input_tokens", 0)
                output_tokens = usage.get("output_tokens", 0)
                total_input_tokens += input_tokens
                total_output_tokens += output_tokens
                total_cached_tokens += int(usage.get("cached_tokens") or 0)
                total_cache_write_30m_tokens += int(usage.get("cache_write_30m_tokens") or 0)
                total_cache_write_12h_tokens += int(usage.get("cache_write_12h_tokens") or 0)

                content = response.get("content", [])
                stop_reason = response.get("stop_reason", "")

                assistant_content = []
                tool_uses = []
                saw_complete = False
                saw_failed_text = ""
                for block in content:
                    if block.get("type") == "text":
                        text = block.get("text", "")
                        assistant_content.append(block)
                        if self.arm == "script_first":
                            if "TASK_COMPLETE" in text:
                                saw_complete = True
                            if "TASK_FAILED" in text and not saw_failed_text:
                                saw_failed_text = text
                            continue
                        if "TASK_COMPLETE" in text:
                            success = True
                            success_reason = "Task completed successfully"
                            # The answer may sit in another text block of the same reply.
                            spoken_answer = spoken_claim(
                                "\n".join(b.get("text", "") for b in content if b.get("type") == "text")
                            )
                            break
                        if "TASK_FAILED" in text:
                            success = False
                            success_reason = f"Task failed: {text}"
                            break
                    elif block.get("type") == "tool_use":
                        tool_uses.append(block)
                        assistant_content.append(block)

                if self.arm != "script_first" and (success or "TASK_FAILED" in str(content)):
                    messages.append({"role": "assistant", "content": assistant_content})
                    break

                if self.arm == "script_first" and awaiting_repair_reply:
                    names = {tool.get("name") for tool in tool_uses}
                    if "run_script" in names:
                        repair_reply = "script"
                    elif "task_failed" in names or saw_failed_text:
                        repair_reply = "task_failed"
                    elif any(block.get("text", "").strip() for block in assistant_content):
                        repair_reply = "prose"
                    awaiting_repair_reply = False

                if not tool_uses:
                    if self.arm == "script_first" and saw_complete:
                        failure = ""
                        if (
                            last_verdict is not None
                            and last_verdict.verdict == FAIL
                            and repairs_sent < max_repairs
                            and time.perf_counter() - generic_start < repair_budget_s
                        ):
                            failure = last_verdict.reason
                        if failure:
                            messages.append({"role": "assistant", "content": assistant_content})
                            messages.append({"role": "user", "content": repair_request(last_url, failure)})
                            repairs_sent += 1
                            awaiting_repair_reply = True
                            turn_limit = next_script_first_limit(
                                step_num=step_num,
                                limit=turn_limit,
                                hard_cap=SCRIPT_FIRST_HARD_CAP,
                                made_progress=False,
                                repair_pending=True,
                                refused_extra_script=False,
                            )
                            continue
                        if last_verdict is not None and last_verdict.verdict == PASS:
                            success = True
                            success_reason = "Task completed successfully"
                            end_state = PASS
                        elif last_verdict is not None and last_verdict.verdict == FAIL:
                            success = False
                            success_reason = last_verdict.reason
                            end_state = FAIL
                        else:
                            reason = last_verdict.reason if last_verdict is not None else "no page evidence"
                            success = False
                            success_reason = f"UNKNOWN: {reason}"
                            end_state = UNKNOWN
                        messages.append({"role": "assistant", "content": assistant_content})
                        break
                    if self.arm == "script_first" and saw_failed_text:
                        success = False
                        success_reason = f"Task failed: {saw_failed_text}"
                        messages.append({"role": "assistant", "content": assistant_content})
                        break
                    if stop_reason == "end_turn":
                        success_reason = "Model ended without completing task"
                    if self.arm != "script_first":
                        # A model that ends in plain prose without the stop token
                        # still made a claim. The grade judges it like any other.
                        spoken_answer = spoken_claim(
                            "\n".join(b.get("text", "") for b in content if b.get("type") == "text")
                        )
                        if spoken_answer and stop_reason == "end_turn":
                            # A final answer with no TASK_FAILED is a completion
                            # claim, like browser_use's done(). The grade checks it.
                            success = True
                            success_reason = "Task completed with a final answer"
                    break

                if self._pending_snapshot_path is not None:
                    _annotate_snapshot_file(self._pending_snapshot_path, tool_uses[0], step_num)
                    self._pending_snapshot_path = None

                messages.append({"role": "assistant", "content": assistant_content})

                tool_results = []
                stop_after_tools = False
                for index, tool_use in enumerate(tool_uses):
                    if stop_after_tools:
                        break
                    tool_name = tool_use.get("name", "")
                    tool_args = tool_use.get("input", {})
                    tool_id = tool_use.get("id", "")

                    if self.arm == "script_first" and tool_name == "look":
                        # Opt-in (CU_SF_LOOK=1). One look; it gets its own turn so it does not use up a repair.
                        looks += 1
                        if looks == 1:
                            turn_limit = min(SCRIPT_FIRST_HARD_CAP + 1, turn_limit + 1)
                        else:
                            tool_results.append(
                                {
                                    "type": "tool_result",
                                    "tool_use_id": tool_id,
                                    "content": "look was already used. Send run_script.",
                                }
                            )
                            continue

                    if self.arm == "script_first" and tool_name == "task_failed":
                        success = False
                        success_reason = f"Task failed: {tool_args.get('reason', '')}"
                        stop_after_tools = True
                        break

                    # Each script after the first needs a repair the harness sent.
                    finished_first = script_calls >= 1 and script_calls > repairs_sent
                    code_now = ""
                    if isinstance(tool_args, dict):
                        code_now = tool_args.get("code") or tool_args.get("script") or ""
                    repeated = (
                        self.arm == "script_first"
                        and tool_name == "run_script"
                        and isinstance(code_now, str)
                        and normalized_script(code_now) in seen_scripts
                        and not legacy_repair
                    )
                    refused = (
                        self.arm == "script_first"
                        and tool_name == "run_script"
                        and (script_calls >= max_scripts or finished_first or repeated)
                    )
                    if refused:
                        if repeated and not (script_calls >= max_scripts or finished_first):
                            result_text = "No further scripts. This exact script already ran."
                        elif script_calls >= max_scripts:
                            result_text = (
                                (
                                    "No further scripts. One script and one repair already ran. "
                                    if legacy_repair
                                    else "No further scripts. The repair limit is reached. "
                                )
                                + "Reply with TASK_COMPLETE or TASK_FAILED. Do not call run_script again."
                            )
                        elif last_verdict is not None and last_verdict.verdict == UNKNOWN:
                            result_text = (
                                "No further scripts. The end state is UNKNOWN, so there is no repair call. "
                                "Do not call run_script again."
                            )
                        else:
                            result_text = (
                                "No further scripts. The first script already finished. "
                                "Reply with TASK_COMPLETE or TASK_FAILED. Do not call run_script again."
                            )
                        tool_ms = 0.0
                    else:
                        await self._wait_for_browser()
                        result_text, tool_ms = await self.mcp_client.call_tool(tool_name, tool_args)
                    logged_selector = ""
                    logged_answer = ""
                    logged_page_text = ""
                    logged_return: dict = {}
                    logged_check: dict = {}
                    total_tool_ms += tool_ms
                    ignores.note_call(tool_name, tool_args if isinstance(tool_args, dict) else {})
                    ignores.note_result(tool_name, result_text)
                    if result_is_replay(result_text):
                        replay_hits += 1

                    this_snapshot_tokens = snapshot_tokens_for(tool_name, result_text)
                    total_snapshot_tokens += this_snapshot_tokens
                    snapshot_text = extract_page_snapshot(result_text)
                    found_url = page_url_from_result(result_text)
                    page_url = found_url or last_url
                    if found_url:
                        last_url = found_url
                    if self.arm == "script_first" and tool_name == "run_script":
                        if refused and repeated:
                            # The same script again cannot change a FAIL. End on the last verdict.
                            stop_after_tools = True
                            success = False
                            if last_verdict is not None:
                                success_reason = last_verdict.reason
                        elif refused:
                            if refusal_extended:
                                stop_after_tools = True
                            else:
                                turn_limit = next_script_first_limit(
                                    step_num=step_num,
                                    limit=turn_limit,
                                    hard_cap=SCRIPT_FIRST_HARD_CAP,
                                    made_progress=False,
                                    repair_pending=False,
                                    refused_extra_script=True,
                                )
                                refusal_extended = True
                        else:
                            script_calls += 1
                            if isinstance(code_now, str):
                                seen_scripts.add(normalized_script(code_now))
                            # page_url stays the live URL. Markers never rewrite it.
                            # No answer key while the run is live. The final grade uses the markers.
                            verdict, payload = script_runtime_verdict(
                                result_text,
                                page_url,
                                start_url,
                                asks_value=task_asks_value(task_description),
                                task=task_description,
                                earlier=earlier_payloads,
                            )
                            progress = script_made_progress(previous_payload, payload)
                            previous_payload = payload
                            earlier_payloads.append(payload)
                            script_steps = int(payload.get("steps") or 0)
                            if verdict.verdict == PASS:
                                args = tool_args if isinstance(tool_args, dict) else {}
                                passing_code = args.get("code") or args.get("script") or ""
                                passing_verdict = verdict
                            last_verdict = verdict
                            end_state = verdict.verdict
                            script_turns.append([verdict.verdict, round((time.perf_counter() - wall_start) * 1000)])
                            failure = verdict.reason if verdict.verdict == FAIL else ""
                            logged_selector, logged_answer, logged_page_text, logged_return = logged_evidence(payload)
                            logged_check = self_check_record(payload, page_url, start_url, verdict)
                            # The judge already read selector_text. The model must not.
                            repair_pending = False
                            grounded = ""
                            if verdict.verdict == FAIL:
                                outcome = repair_outcome_key(verdict, payload)
                                # The same failure on the same page three times in a row ends the repairs.
                                same_fail_count = same_fail_count + 1 if outcome == last_fail_key else 1
                                stalled = same_fail_count >= 3 and not legacy_repair
                                last_fail_key = outcome
                                in_budget = time.perf_counter() - generic_start < repair_budget_s
                                if repairs_sent < max_repairs and in_budget and not stalled:
                                    snapshot, snap_ms = "", 0.0
                                    reader = getattr(self.mcp_client, "page_snapshot", None)
                                    if callable(reader) and not legacy_repair:
                                        try:
                                            snapshot, snap_ms = await reader(task_description)
                                        except Exception:
                                            snapshot, snap_ms = "", 0.0
                                    tool_ms += snap_ms
                                    total_tool_ms += snap_ms
                                    if snapshot:
                                        grounded = grounded_repair_request(
                                            failure,
                                            code=code_now if isinstance(code_now, str) else "",
                                            payload=payload,
                                            snapshot=snapshot,
                                            repair_number=repairs_sent + 1,
                                            max_repairs=max_repairs,
                                        )
                                        drop_old_snapshots(messages)
                                    else:
                                        result_text += "\n" + repair_request(page_url, failure)
                                    repairs_sent += 1
                                    awaiting_repair_reply = True
                                    repair_pending = True
                            # With a snapshot, it replaces the raw links, controls, and page text.
                            result_text = model_visible_script_result(
                                result_text,
                                failed=verdict.verdict == FAIL and not grounded,
                                hide_page=bool(grounded),
                            )
                            if grounded:
                                result_text += "\n" + grounded
                            turn_limit = next_script_first_limit(
                                step_num=step_num,
                                limit=turn_limit,
                                hard_cap=SCRIPT_FIRST_HARD_CAP,
                                made_progress=progress,
                                repair_pending=repair_pending,
                                refused_extra_script=False,
                            )
                            # A PASS ends the task. UNKNOWN is not a pass and does not repair.
                            # A second script is refused, so another model call cannot change it.
                            if verdict.verdict == PASS and isinstance(page_url, str) and page_url.startswith(
                                ("http://", "https://")
                            ):
                                success = True
                                success_reason = "Task completed successfully"
                                stop_after_tools = True
                            elif verdict.verdict == UNKNOWN:
                                success = False
                                success_reason = f"UNKNOWN: {verdict.reason}"
                                stop_after_tools = True
                            elif legacy_repair and (
                                verdict.verdict == FAIL
                                and not progress
                                and not repair_pending
                                and script_calls >= max_scripts
                            ):
                                # tip2's rule: stop only when the repair made no progress either.
                                stop_after_tools = True
                                success = False
                                success_reason = failure
                            elif not legacy_repair and verdict.verdict == FAIL and not repair_pending:
                                # No repair is left (limit, wall budget, or the same failure twice).
                                # A further script would be refused, so another model call cannot change it.
                                stop_after_tools = True
                                success = False
                                success_reason = failure
                    page_title = page_field(result_text, "Title")
                    snapshot_path = self._write_page_snapshot(
                        task_id=task_id,
                        step_number=step_num,
                        tool_name=tool_name,
                        snapshot_text=snapshot_text,
                        page_url=page_url,
                        page_title=page_title,
                    )
                    if snapshot_path is not None:
                        self._pending_snapshot_path = snapshot_path

                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_id,
                            "content": result_text,
                        }
                    )

                    steps.append(
                        StepMetrics(
                            step_number=step_base + step_num,
                            tool_name=tool_name,
                            tool_args=tool_args,
                            tool_result_size=len(result_text),
                            snapshot_tokens=this_snapshot_tokens,
                            model_time_ms=model_ms if index == 0 else 0,
                            tool_time_ms=tool_ms,
                            input_tokens=input_tokens if index == 0 else 0,
                            output_tokens=output_tokens if index == 0 else 0,
                            snapshot_text=snapshot_text,
                            snapshot_file=str(snapshot_path) if snapshot_path else "",
                            page_url=page_url,
                            page_title=page_title,
                            selector_text=logged_selector,
                            claimed_answer=logged_answer,
                            page_text=logged_page_text,
                            **claim_step_fields(logged_return),
                            self_check=logged_check,
                        )
                    )

                messages.append({"role": "user", "content": tool_results})
                if self.arm == "script_first" and saw_complete and not stop_after_tools:
                    repaired = any(
                        "END_STATE_FAILED" in str(block.get("content") or "")
                        for block in tool_results
                        if isinstance(block, dict)
                    )
                    if not repaired:
                        if last_verdict is not None and last_verdict.verdict == PASS:
                            success = True
                            success_reason = "Task completed successfully"
                            end_state = PASS
                        elif last_verdict is not None and last_verdict.verdict == FAIL:
                            success = False
                            success_reason = last_verdict.reason
                            end_state = FAIL
                        else:
                            reason = last_verdict.reason if last_verdict is not None else "no page evidence"
                            success = False
                            success_reason = f"UNKNOWN: {reason}"
                            end_state = UNKNOWN
                        break
                if stop_after_tools:
                    break

        except Exception as exc:
            from bench.openai_spend import PriceUnknown

            if isinstance(exc, PriceUnknown):
                raise
            error = str(exc)
            success = False
            success_reason = f"Error: {error}"

        if spoken_answer and self.arm != "script_first":
            self._apply_spoken_claim(steps, spoken_answer)
        # The grade read is the judge's work, not the arm's. Every arm does the
        # same read, and none of them is timed for it.
        grade_start = time.perf_counter()
        await self._read_shared_page(task_id, steps)
        grade_read_ms = (time.perf_counter() - grade_start) * 1000

        if self.arm == "script_first" and end_state == UNKNOWN and success_reason == "Max steps reached":
            reason = last_verdict.reason if last_verdict is not None else "no page evidence"
            success = False
            success_reason = f"UNKNOWN: {reason}"
        if self.arm == "script_first" and end_state == FAIL and success:
            success = False
            if last_verdict is not None:
                success_reason = last_verdict.reason
        if self.arm == "script_first" and not tier:
            from bench.script_cache import TIER_FRESH

            tier = TIER_FRESH
            if (
                cache is not None
                and success
                and end_state == PASS
                and passing_code
            ):
                landed = ""
                controls = None
                if isinstance(previous_payload, dict):
                    raw_url = previous_payload.get("url")
                    landed = raw_url if isinstance(raw_url, str) else ""
                    controls = previous_payload.get("controls")
                cache.save(
                    task_description,
                    start_url,
                    passing_code,
                    passing_verdict,
                    controls=controls,
                    landed_url=landed,
                )

        total_wall_ms = (time.perf_counter() - wall_start) * 1000 - grade_read_ms
        total_other_ms = total_wall_ms - total_model_ms - total_tool_ms

        return TaskResult(
            task_id=task_id,
            task_description=task_description,
            success=success,
            success_reason=success_reason,
            total_steps=len(steps),
            total_wall_ms=total_wall_ms,
            total_model_ms=total_model_ms,
            total_tool_ms=total_tool_ms,
            total_other_ms=total_other_ms,
            total_input_tokens=total_input_tokens,
            total_output_tokens=total_output_tokens,
            total_snapshot_tokens=total_snapshot_tokens,
            steps=steps,
            error=error,
            model_ignores_tools=ignores.count,
            replay_hits=replay_hits,
            end_state=end_state,
            tier=tier,
            model_calls=model_calls,
            script_steps=script_steps,
            total_cached_tokens=total_cached_tokens,
            total_cache_write_30m_tokens=total_cache_write_30m_tokens,
            total_cache_write_12h_tokens=total_cache_write_12h_tokens,
            repair_sent=repairs_sent > 0,
            repair_reply=repair_reply,
            script_turns=script_turns,
            strategy=strategy,
            strategy_detail=strategy_detail,
        )

    def _empty_result(
        self,
        task_id: str,
        task_description: str,
        reason: str,
        error: str,
    ) -> TaskResult:
        return TaskResult(
            task_id=task_id,
            task_description=task_description,
            success=False,
            success_reason=reason,
            total_steps=0,
            total_wall_ms=0,
            total_model_ms=0,
            total_tool_ms=0,
            total_other_ms=0,
            total_input_tokens=0,
            total_output_tokens=0,
            total_snapshot_tokens=0,
            error=error,
        )

    def save_result(self, result: TaskResult, run_id: str) -> Path:
        """Save a task result to a JSONL file."""
        run_file = self.runs_dir / f"{run_id}.jsonl"
        with open(run_file, "a", encoding="utf-8") as handle:
            data = {
                "task_id": result.task_id,
                "task_description": result.task_description,
                "success": result.success,
                "success_reason": result.success_reason,
                "total_steps": result.total_steps,
                "total_wall_ms": result.total_wall_ms,
                "total_model_ms": result.total_model_ms,
                "total_tool_ms": result.total_tool_ms,
                "total_other_ms": result.total_other_ms,
                "total_input_tokens": result.total_input_tokens,
                "total_output_tokens": result.total_output_tokens,
                "total_snapshot_tokens": result.total_snapshot_tokens,
                "model_ignores_tools": result.model_ignores_tools,
                "replay_hits": result.replay_hits,
                "end_state": result.end_state,
                "tier": result.tier,
                "model_calls": result.model_calls,
                "script_steps": result.script_steps,
                "strategy": result.strategy,
                "strategy_detail": result.strategy_detail,
                "error": result.error,
                "claimed_answer": result.steps[-1].claimed_answer if result.steps else "",
                "expected_value": result.steps[-1].selector_text if result.steps else "",
                "steps": [
                    {
                        "step_number": step.step_number,
                        "tool_name": step.tool_name,
                        "tool_args": step.tool_args,
                        "tool_result_size": step.tool_result_size,
                        "snapshot_tokens": step.snapshot_tokens,
                        "model_time_ms": step.model_time_ms,
                        "tool_time_ms": step.tool_time_ms,
                        "input_tokens": step.input_tokens,
                        "output_tokens": step.output_tokens,
                        "snapshot_text": step.snapshot_text,
                        "snapshot_file": step.snapshot_file,
                        "page_url": step.page_url,
                        "page_title": step.page_title,
                        "selector_text": step.selector_text,
                        "claimed_answer": step.claimed_answer,
                        "page_text": step.page_text,
                        "claimed_url": step.claimed_url,
                        "claimed_title": step.claimed_title,
                        "claimed_h1": step.claimed_h1,
                        "claimed_key_text": step.claimed_key_text,
                        "claimed_values": list(step.claimed_values),
                        "claimed_rejected": step.claimed_rejected,
                    }
                    for step in result.steps
                ],
            }
            if self.provider == "openai":
                data["provider"] = "openai"
                data["model"] = self.model
                data["effort"] = self.effort
                data["cached_tokens"] = result.total_cached_tokens
            handle.write(json.dumps(data) + "\n")
        return run_file


async def execute_benchmark_tasks(
    harness: BenchmarkHarness,
    tasks: list[dict],
    ledger: SpendLedger,
    run_id: str,
) -> list[TaskResult]:
    """Run tasks until the project total would pass the budget.

    Spend is estimated after every task from that task's tokens times the
    recorded ledger rate, then written to the ledger. The next task is
    not started once the running total has reached $40.
    """
    results: list[TaskResult] = []
    for task in tasks:
        if not ledger.allows_another_task():
            ledger.mark_aborted()
            ledger.save()
            raise BudgetExceeded(ledger.running_total_usd, results, ledger.budget_usd)

        print(f"Running task: {task['id']} - {task['description'][:50]}...")
        result = await harness.run_task(
            task_id=task["id"],
            task_description=task["description"],
            start_url=task["start_url"],
            expected_answer=task.get("expected_answer"),
            judge_prompt=task.get("judge_prompt"),
        )
        results.append(result)
        from bench.openai_spend import OpenAISpendLedger

        cached = int(getattr(result, "total_cached_tokens", 0) or 0)
        if isinstance(ledger, OpenAISpendLedger):
            ledger.record_task(
                run_id=run_id,
                task_id=result.task_id,
                input_tokens=result.total_input_tokens,
                output_tokens=result.total_output_tokens,
                cached_tokens=cached,
                cache_write_30m_tokens=int(getattr(result, "total_cache_write_30m_tokens", 0) or 0),
                cache_write_12h_tokens=int(getattr(result, "total_cache_write_12h_tokens", 0) or 0),
            )
        else:
            ledger.record_task(
                run_id=run_id,
                task_id=result.task_id,
                input_tokens=result.total_input_tokens,
                output_tokens=result.total_output_tokens,
            )
        over_budget = not ledger.allows_another_task()
        if over_budget:
            ledger.mark_aborted()
        ledger.save()
        harness.save_result(result, run_id)
        print(f"  -> {'SUCCESS' if result.success else 'FAILED'}: {result.success_reason[:60]}")
        print(f"  -> project total ${ledger.running_total_usd:.2f}")
        if over_budget:
            raise BudgetExceeded(ledger.running_total_usd, results, ledger.budget_usd)
    return results


async def run_benchmark(
    tasks: list[dict],
    api_key: str | None = None,
    model: str = DEFAULT_MODEL,
    headless: bool = True,
    run_id: str | None = None,
    spend_path: Path | None = None,
    runs_dir: Path | None = None,
    arm: str = "playwright_mcp",
    provider: str = "anthropic",
    effort: str | None = None,
) -> list[TaskResult]:
    """Run a benchmark suite and return results."""
    if provider == "openai":
        from bench.openai_spend import (
            OPENAI_RUN_BUDGET_USD,
            OpenAISpendLedger,
            assert_effort,
            assert_openai_model,
            default_openai_spend_path,
        )

        chosen = assert_openai_model(model)
        name = assert_effort(chosen, effort or "")
        ledger = OpenAISpendLedger.read(spend_path or default_openai_spend_path())
        ledger.model = chosen
        ledger.effort = name
        # The allowance sits inside this run's $5, not on top of it.
        baseline = ledger.running_total_usd
        ledger.cover_unrecorded_call()
        ledger.run_ceiling_usd = round(baseline + OPENAI_RUN_BUDGET_USD, 6)
        if run_id is None:
            run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        if not ledger.allows_another_task():
            ledger.mark_aborted()
            ledger.save()
            raise BudgetExceeded(ledger.running_total_usd, [], ledger.run_ceiling_usd or OPENAI_RUN_BUDGET_USD)
        harness = BenchmarkHarness(
            api_key=api_key,
            model=chosen,
            headless=headless,
            runs_dir=runs_dir,
            arm=arm,
            provider="openai",
            effort=name,
        )
        harness.snapshot_dir = harness.runs_dir / run_id / "snapshots"
        try:
            await harness.setup()
            return await execute_benchmark_tasks(harness, tasks, ledger, run_id)
        finally:
            await harness.teardown()
    if effort not in (None, ""):
        from bench.openai_spend import EffortNotAllowed

        raise EffortNotAllowed("Claude does not take --effort.")
    assert_allowed_model(model)
    ledger = SpendLedger.load(spend_path)
    if run_id is None:
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    if not ledger.allows_another_task():
        ledger.mark_aborted()
        ledger.save()
        raise BudgetExceeded(ledger.running_total_usd, [], ledger.budget_usd)

    harness = BenchmarkHarness(
        api_key=api_key,
        model=model,
        headless=headless,
        runs_dir=runs_dir,
        arm=arm,
    )
    harness.snapshot_dir = harness.runs_dir / run_id / "snapshots"

    try:
        await harness.setup()
        return await execute_benchmark_tasks(harness, tasks, ledger, run_id)
    finally:
        await harness.teardown()


if __name__ == "__main__":
    from bench.tasks import BENCHMARK_TASKS

    asyncio.run(run_benchmark(BENCHMARK_TASKS))
