"""Harness that runs browser tasks via @playwright/mcp with a Claude model.

Logs per-task metrics: wall time split (model vs tool vs other), steps,
input/output tokens, snapshot tokens per step, and success.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PLAYWRIGHT_MCP_VERSION = "0.0.84"
DEFAULT_MODEL = "claude-sonnet-4-20250514"

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


def estimate_tokens(text: str) -> int:
    """Rough token estimate (chars / 4)."""
    return max(1, len(text) // 4)


class PlaywrightMCPClient:
    """Client that communicates with @playwright/mcp over stdio."""

    def __init__(self, headless: bool = True, snapshot_mode: str = "full"):
        self.headless = headless
        self.snapshot_mode = snapshot_mode
        self.process: subprocess.Popen | None = None
        self._request_id = 0
        self._tools: list[dict] = []

    async def start(self) -> None:
        """Start the @playwright/mcp process."""
        args = ["npx", f"@playwright/mcp@{PLAYWRIGHT_MCP_VERSION}"]
        if self.headless:
            args.append("--headless")
        args.extend(["--snapshot-mode", self.snapshot_mode])

        self.process = await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        await self._initialize()

    async def _send_request(self, method: str, params: dict | None = None) -> dict:
        """Send a JSON-RPC request and wait for response."""
        if self.process is None or self.process.stdin is None:
            raise RuntimeError("MCP process not started")

        self._request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
        }
        if params:
            request["params"] = params

        message = json.dumps(request)
        content = f"Content-Length: {len(message)}\r\n\r\n{message}"
        self.process.stdin.write(content.encode())
        await self.process.stdin.drain()

        return await self._read_response()

    async def _read_response(self) -> dict:
        """Read a JSON-RPC response from stdout."""
        if self.process is None or self.process.stdout is None:
            raise RuntimeError("MCP process not started")

        header = b""
        while True:
            char = await self.process.stdout.read(1)
            if not char:
                raise RuntimeError("MCP process ended unexpectedly")
            header += char
            if header.endswith(b"\r\n\r\n"):
                break

        content_length = 0
        for line in header.decode().split("\r\n"):
            if line.lower().startswith("content-length:"):
                content_length = int(line.split(":", 1)[1].strip())

        body = await self.process.stdout.read(content_length)
        return json.loads(body.decode())

    async def _initialize(self) -> None:
        """Initialize the MCP connection and get tools list."""
        await self._send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "bench-harness", "version": "0.1.0"}
        })
        await self._send_request("notifications/initialized")

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
            claude_tools.append({
                "name": tool["name"],
                "description": tool.get("description", ""),
                "input_schema": tool.get("inputSchema", {"type": "object", "properties": {}})
            })
        return claude_tools

    async def call_tool(self, name: str, arguments: dict) -> tuple[str, float]:
        """Call a tool and return (result_text, time_ms)."""
        start = time.perf_counter()
        response = await self._send_request("tools/call", {
            "name": name,
            "arguments": arguments
        })
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
        if self.process:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self.process.kill()
            self.process = None


class AnthropicClient:
    """Simple Anthropic API client for tool use."""

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://api.anthropic.com/v1/messages"

    async def create_message(
        self,
        messages: list[dict],
        tools: list[dict],
        system: str = SYSTEM_PROMPT,
        max_tokens: int = 4096,
    ) -> tuple[dict, float]:
        """Create a message and return (response, time_ms)."""
        import urllib.request
        import urllib.error

        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": system,
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
    ):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.model = model
        self.headless = headless
        self.max_steps = max_steps
        self.runs_dir = runs_dir or Path(__file__).parent / "runs"
        self.runs_dir.mkdir(exist_ok=True)

        self.mcp_client: PlaywrightMCPClient | None = None
        self.anthropic: AnthropicClient | None = None

    def has_api_key(self) -> bool:
        """Check if we have an API key configured."""
        return bool(self.api_key)

    async def setup(self) -> None:
        """Set up clients."""
        if self.api_key:
            self.anthropic = AnthropicClient(self.api_key, self.model)

        self.mcp_client = PlaywrightMCPClient(headless=self.headless)
        await self.mcp_client.start()

    async def teardown(self) -> None:
        """Clean up clients."""
        if self.mcp_client:
            await self.mcp_client.stop()
            self.mcp_client = None

    async def run_task(
        self,
        task_id: str,
        task_description: str,
        start_url: str,
        expected_answer: str | None = None,
        judge_prompt: str | None = None,
    ) -> TaskResult:
        """Run a single task and collect metrics."""
        if not self.anthropic:
            return TaskResult(
                task_id=task_id,
                task_description=task_description,
                success=False,
                success_reason="No API key configured",
                total_steps=0,
                total_wall_ms=0,
                total_model_ms=0,
                total_tool_ms=0,
                total_other_ms=0,
                total_input_tokens=0,
                total_output_tokens=0,
                total_snapshot_tokens=0,
                error="ANTHROPIC_API_KEY not set",
            )

        if not self.mcp_client:
            return TaskResult(
                task_id=task_id,
                task_description=task_description,
                success=False,
                success_reason="MCP client not initialized",
                total_steps=0,
                total_wall_ms=0,
                total_model_ms=0,
                total_tool_ms=0,
                total_other_ms=0,
                total_input_tokens=0,
                total_output_tokens=0,
                total_snapshot_tokens=0,
                error="MCP client not started",
            )

        wall_start = time.perf_counter()
        steps: list[StepMetrics] = []
        total_model_ms = 0.0
        total_tool_ms = 0.0
        total_input_tokens = 0
        total_output_tokens = 0
        total_snapshot_tokens = 0

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

                response, model_ms = await self.anthropic.create_message(messages, tools)
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

                messages.append({"role": "assistant", "content": assistant_content})

                tool_results = []
                step_tool_ms = 0.0
                step_snapshot_tokens = 0
                for tool_use in tool_uses:
                    tool_name = tool_use.get("name", "")
                    tool_args = tool_use.get("input", {})
                    tool_id = tool_use.get("id", "")

                    result_text, tool_ms = await self.mcp_client.call_tool(tool_name, tool_args)
                    step_tool_ms += tool_ms
                    total_tool_ms += tool_ms

                    if tool_name == "browser_snapshot" or "snapshot" in result_text.lower()[:100]:
                        snapshot_tokens = estimate_tokens(result_text)
                        step_snapshot_tokens += snapshot_tokens
                        total_snapshot_tokens += snapshot_tokens

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "content": result_text,
                    })

                    steps.append(StepMetrics(
                        step_number=step_num,
                        tool_name=tool_name,
                        tool_args=tool_args,
                        tool_result_size=len(result_text),
                        snapshot_tokens=step_snapshot_tokens,
                        model_time_ms=model_ms if tool_use == tool_uses[0] else 0,
                        tool_time_ms=tool_ms,
                        input_tokens=input_tokens if tool_use == tool_uses[0] else 0,
                        output_tokens=output_tokens if tool_use == tool_uses[0] else 0,
                    ))

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
        )

    def save_result(self, result: TaskResult, run_id: str) -> Path:
        """Save a task result to a JSONL file."""
        run_file = self.runs_dir / f"{run_id}.jsonl"
        with open(run_file, "a", encoding="utf-8") as f:
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
                "error": result.error,
                "steps": [
                    {
                        "step_number": s.step_number,
                        "tool_name": s.tool_name,
                        "tool_args": s.tool_args,
                        "tool_result_size": s.tool_result_size,
                        "snapshot_tokens": s.snapshot_tokens,
                        "model_time_ms": s.model_time_ms,
                        "tool_time_ms": s.tool_time_ms,
                        "input_tokens": s.input_tokens,
                        "output_tokens": s.output_tokens,
                    }
                    for s in result.steps
                ],
            }
            f.write(json.dumps(data) + "\n")
        return run_file


async def run_benchmark(
    tasks: list[dict],
    api_key: str | None = None,
    model: str = DEFAULT_MODEL,
    headless: bool = True,
    run_id: str | None = None,
) -> list[TaskResult]:
    """Run a benchmark suite and return results."""
    import datetime

    if run_id is None:
        run_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    harness = BenchmarkHarness(api_key=api_key, model=model, headless=headless)

    results = []
    try:
        await harness.setup()

        for task in tasks:
            print(f"Running task: {task['id']} - {task['description'][:50]}...")
            result = await harness.run_task(
                task_id=task["id"],
                task_description=task["description"],
                start_url=task["start_url"],
                expected_answer=task.get("expected_answer"),
                judge_prompt=task.get("judge_prompt"),
            )
            results.append(result)
            harness.save_result(result, run_id)
            print(f"  -> {'SUCCESS' if result.success else 'FAILED'}: {result.success_reason[:60]}")

    finally:
        await harness.teardown()

    return results


if __name__ == "__main__":
    from bench.tasks import BENCHMARK_TASKS

    asyncio.run(run_benchmark(BENCHMARK_TASKS))
