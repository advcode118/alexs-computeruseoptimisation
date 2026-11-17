"""UI backends. Each one turns its tree into core.backend.Snapshot."""

from backends.dom import DomBackend
from backends.playwright_mcp import PLAYWRIGHT_MCP_VERSION, PlaywrightMcpBackend, ToolCall

__all__ = [
    "DomBackend",
    "PLAYWRIGHT_MCP_VERSION",
    "PlaywrightMcpBackend",
    "ToolCall",
]
