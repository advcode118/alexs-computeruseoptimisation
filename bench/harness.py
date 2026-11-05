"""Harness that runs browser tasks via @playwright/mcp with claude-sonnet-4-6.

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
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from bench.budget import (
    ALLOWED_MODEL,
    BudgetExceeded,
    SpendLedger,
    assert_allowed_model,
)
from proxy.ignores import IgnoreCounter

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

SYSTEM_PROMPT = """You are a browser automation agent. You have access to tools for controlling a web browser.
Your goal is to complete the given task by using the browser tools.

Guidelines:
- Use browser_snapshot to see the current page state
- Use browser_click with target (ref like "S1E2") to click elements
- Use browser_type with target and text to type into fields
- Use browser_navigate with url to navigate to pages
- When the task is complete, respond with TASK_COMPLETE
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
    return [_cap_message(message) for message in (head, *kept)]


def _cap_message(message: dict) -> dict:
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


def playwright_mcp_args(*, headless: bool, snapshot_mode: str, user_data_dir: str) -> list[str]:
    """Plain Playwright MCP, one private browser per process.

    --isolated keeps the profile in memory. The unique user-data-dir is the
    other way the CLI avoids the shared workspace profile lock. Sequential
    arms each get their own directory.
    """
    args = [
        "npx",
        f"@playwright/mcp@{PLAYWRIGHT_MCP_VERSION}",
        "--isolated",
        "--user-data-dir",
        user_data_dir,
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
            self._profile_dir = tempfile.mkdtemp(prefix="pw-mcp-arm-")
            args = playwright_mcp_args(
                headless=self.headless,
                snapshot_mode=self.snapshot_mode,
                user_data_dir=self._profile_dir,
            )

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
            claude_tools.append(
                {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
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


class AnthropicClient:
    """Simple Anthropic API client for tool use. claude-sonnet-4-6 only."""

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL):
        self.api_key = api_key
        self.model = assert_allowed_model(model)
        self.base_url = "https://api.anthropic.com/v1/messages"

    async def create_message(
        self,
        messages: list[dict],
        tools: list[dict],
        system: str | None = None,
        max_tokens: int = 4096,
    ) -> tuple[dict, float]:
        """Create a message and return (response, time_ms)."""
        assert_allowed_model(self.model)
        import urllib.request

        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": system or SYSTEM_PROMPT,
            "messages": messages,
            "tools": tools,
        }

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
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
    ):
        from bench.arms import prompt_for

        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.arm = arm
        self.system_prompt = prompt_for(arm)
        self.model = assert_allowed_model(model)
        self.headless = headless
        self.max_steps = max_steps
        self.runs_dir = runs_dir or Path(__file__).parent / "runs"
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self.snapshot_dir = snapshot_dir

        self.mcp_client: PlaywrightMCPClient | None = None
        self.anthropic: AnthropicClient | None = None
        self._capture_index = 0
        self._pending_snapshot_path: Path | None = None

    def has_api_key(self) -> bool:
        """Check if we have an API key configured."""
        return bool(self.api_key)

    async def setup(self) -> None:
        """Set up clients."""
        if self.api_key:
            self.anthropic = AnthropicClient(self.api_key, self.model)

        from bench.arms import build_client

        self.mcp_client = build_client(self.arm, headless=self.headless)
        await self.mcp_client.start()

    async def teardown(self) -> None:
        """Clean up clients."""
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

    async def run_task(
        self,
        task_id: str,
        task_description: str,
        start_url: str,
        expected_answer: str | None = None,
        judge_prompt: str | None = None,
    ) -> TaskResult:
        """Run a single task and collect metrics."""
        del expected_answer, judge_prompt
        if not self.anthropic:
            return self._empty_result(
                task_id,
                task_description,
                "No API key configured",
                "ANTHROPIC_API_KEY not set",
            )

        if not self.mcp_client:
            return self._empty_result(
                task_id,
                task_description,
                "MCP client not initialized",
                "MCP client not started",
            )

        wall_start = time.perf_counter()
        steps: list[StepMetrics] = []
        total_model_ms = 0.0
        total_tool_ms = 0.0
        total_input_tokens = 0
        total_output_tokens = 0
        total_snapshot_tokens = 0
        ignores = IgnoreCounter()
        replay_hits = 0
        self._pending_snapshot_path = None

        messages: list[dict] = [
            {"role": "user", "content": f"Task: {task_description}\n\nStart URL: {start_url}"}
        ]

        tools = self.mcp_client.tools_for_claude()
        step_num = 0
        success = False
        success_reason = "Max steps reached"
        error: str | None = None

        try:
            while step_num < self.max_steps:
                step_num += 1

                response, model_ms = await self.anthropic.create_message(
                    cap_messages_for_model(messages),
                    tools,
                    system=self.system_prompt,
                )
                total_model_ms += model_ms

                usage = response.get("usage", {})
                input_tokens = usage.get("input_tokens", 0)
                output_tokens = usage.get("output_tokens", 0)
                total_input_tokens += input_tokens
                total_output_tokens += output_tokens

                content = response.get("content", [])
                stop_reason = response.get("stop_reason", "")

                assistant_content = []
                tool_uses = []
                for block in content:
                    if block.get("type") == "text":
                        text = block.get("text", "")
                        assistant_content.append(block)
                        if "TASK_COMPLETE" in text:
                            success = True
                            success_reason = "Task completed successfully"
                            break
                        if "TASK_FAILED" in text:
                            success = False
                            success_reason = f"Task failed: {text}"
                            break
                    elif block.get("type") == "tool_use":
                        tool_uses.append(block)
                        assistant_content.append(block)

                if success or "TASK_FAILED" in str(content):
                    messages.append({"role": "assistant", "content": assistant_content})
                    break

                if not tool_uses:
                    if stop_reason == "end_turn":
                        success_reason = "Model ended without completing task"
                    break

                if self._pending_snapshot_path is not None:
                    _annotate_snapshot_file(self._pending_snapshot_path, tool_uses[0], step_num)
                    self._pending_snapshot_path = None

                messages.append({"role": "assistant", "content": assistant_content})

                tool_results = []
                for index, tool_use in enumerate(tool_uses):
                    tool_name = tool_use.get("name", "")
                    tool_args = tool_use.get("input", {})
                    tool_id = tool_use.get("id", "")

                    result_text, tool_ms = await self.mcp_client.call_tool(tool_name, tool_args)
                    total_tool_ms += tool_ms
                    ignores.note_call(tool_name, tool_args if isinstance(tool_args, dict) else {})
                    ignores.note_result(tool_name, result_text)
                    if result_is_replay(result_text):
                        replay_hits += 1

                    this_snapshot_tokens = snapshot_tokens_for(tool_name, result_text)
                    total_snapshot_tokens += this_snapshot_tokens
                    snapshot_text = extract_page_snapshot(result_text)
                    page_url = page_field(result_text, "URL")
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
                            step_number=step_num,
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
                        )
                    )

                messages.append({"role": "user", "content": tool_results})

        except Exception as exc:
            error = str(exc)
            success = False
            success_reason = f"Error: {error}"

        total_wall_ms = (time.perf_counter() - wall_start) * 1000
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
                "error": result.error,
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
                    }
                    for step in result.steps
                ],
            }
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
    current sonnet-4-6 price, then written to the ledger. The next task is
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
) -> list[TaskResult]:
    """Run a benchmark suite and return results."""
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
