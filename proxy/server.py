"""MCP stdio proxy in front of pinned @playwright/mcp@0.0.84.

The child is `npx @playwright/mcp@0.0.84 --snapshot-mode none`. tools/list
runs once at startup. Every tool the child returns is exposed as-is, then
fast_act and do_task_segment. A Playwright tools/call is forwarded without
renaming arguments. After a page action the proxy waits for the DOM to settle,
calls browser_snapshot itself, and returns a compact diff instead of the full
tree. fast_act runs one no-model batch. do_task_segment replays a stored
sequence when the page matches, and otherwise runs the sub-task in one call.

Cursor and Claude Code use the same stdio config. From a checkout:

    {
      "mcpServers": {
        "playwright-proxy": {
          "command": "uvx",
          "args": ["--from", "/absolute/path/to/this/repo", "playwright-mcp-proxy"]
        }
      }
    }

Cursor reads that from `.cursor/mcp.json`. Claude Code reads it from
`.mcp.json` in the project, or from `claude mcp add`.
"""

from __future__ import annotations

import sys

import anyio
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.shared.exceptions import MCPError
from mcp_types import INTERNAL_ERROR

from proxy.child import ChildProtocolError, NdjsonChild, child_argv
from proxy.segment import dispatch, listed_tools

SERVER_NAME = "playwright-mcp-proxy"
SERVER_VERSION = "0.2.0"
INSTRUCTIONS = (
    "Forwards @playwright/mcp@0.0.84 unchanged. "
    "The child is started with --snapshot-mode none. "
    "Prefer do_task_segment for a multi-step sub-task and fast_act for one obvious action, "
    "instead of calling browser_snapshot, browser_click, and browser_type one step at a time. "
    "After a browser action this proxy waits for the page to settle and returns a compact diff. "
    "Refs for controls that are still there stay valid, so a separate browser_snapshot call is not required. "
    "fast_act does not call a model. "
    "do_task_segment replays a stored sequence for the same domain, task, and page shape "
    "before decide(), and does not call a model while that replay matches. "
    "do_task_segment uses the cheap Nebius tier only when NEBIUS_API_KEY is set. "
    "This server does not call a model for a forwarded Playwright tool."
)


def build_server(child: NdjsonChild) -> Server:
    async def on_list_tools(ctx, params):
        del ctx, params
        return {"tools": listed_tools(child.tools)}

    async def on_call_tool(ctx, params):
        del ctx
        try:
            return await dispatch(child, params.name, params.arguments)
        except ChildProtocolError as exc:
            raise MCPError(INTERNAL_ERROR, str(exc)) from exc

    return Server(
        SERVER_NAME,
        version=SERVER_VERSION,
        instructions=INSTRUCTIONS,
        on_list_tools=on_list_tools,
        on_call_tool=on_call_tool,
    )


async def serve() -> None:
    child = NdjsonChild(child_argv())
    await child.start()
    server = build_server(child)
    try:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )
    finally:
        await child.stop()


def main() -> int:
    try:
        anyio.run(serve)
    except ChildProtocolError as exc:
        sys.stderr.write(f"{exc}\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
