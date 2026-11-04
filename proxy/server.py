"""MCP stdio proxy in front of pinned @playwright/mcp@0.0.84.

The child is `npx @playwright/mcp@0.0.84 --snapshot-mode none`. tools/list
runs once at startup. Every tool the child returns is exposed as-is, and
tools/call is forwarded without renaming arguments or rewriting the result.

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

SERVER_NAME = "playwright-mcp-proxy"
SERVER_VERSION = "0.1.0"
INSTRUCTIONS = (
    "Forwards @playwright/mcp@0.0.84 unchanged. "
    "The child is started with --snapshot-mode none. "
    "This server does not call a model."
)


def build_server(child: NdjsonChild) -> Server:
    async def on_list_tools(ctx, params):
        del ctx, params
        return {"tools": child.tools}

    async def on_call_tool(ctx, params):
        del ctx
        try:
            return await child.call_tool(params.name, params.arguments)
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
