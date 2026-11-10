"""Responses API client for the computer-use bench.

The harness speaks Anthropic-shaped content blocks. This client translates
those blocks to the Responses API and translates the reply back. It sends
function tools only. It does not send the hosted computer_use tool. Tests
pass a transport and do not open a socket.
"""

from __future__ import annotations

import asyncio
import json
import time

from bench.openai_spend import PriceUnknown, assert_effort, assert_openai_model

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
_USAGE_TOP = frozenset(
    {"input_tokens", "output_tokens", "total_tokens", "input_tokens_details", "output_tokens_details"}
)
_INPUT_DETAILS = frozenset({"cached_tokens"})
_OUTPUT_DETAILS = frozenset({"reasoning_tokens"})
_OUTPUT_ITEMS = frozenset({"message", "function_call", "reasoning"})


class OpenAIResponseError(RuntimeError):
    """The response is not a tool-use reply this harness can run."""


def _post_openai(url: str, headers: dict, payload: dict) -> str:
    import urllib.request

    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read().decode()


def responses_tools(tools: list[dict]) -> list[dict]:
    """Anthropic tool schemas as Responses function tools. No hosted computer tool."""
    converted = []
    for tool in tools:
        name = tool.get("name")
        if not isinstance(name, str) or not name:
            raise OpenAIResponseError("A tool has no name. Refusing to send it.")
        schema = tool.get("input_schema")
        if not isinstance(schema, dict):
            schema = {"type": "object", "properties": {}}
        converted.append(
            {
                "type": "function",
                "name": name,
                "description": tool.get("description") or "",
                "parameters": schema,
            }
        )
    return converted


def responses_input(messages: list[dict]) -> list[dict]:
    """Anthropic messages as Responses input items."""
    items: list[dict] = []
    for message in messages:
        role = message.get("role")
        content = message.get("content")
        if role == "user" and isinstance(content, str):
            items.append({"role": "user", "content": content})
            continue
        if role == "assistant" and isinstance(content, str):
            items.append({"role": "assistant", "content": content})
            continue
        blocks = content if isinstance(content, list) else []
        for block in blocks:
            if not isinstance(block, dict):
                continue
            kind = block.get("type")
            if role == "assistant" and kind == "text":
                items.append({"role": "assistant", "content": block.get("text") or ""})
            elif role == "assistant" and kind == "tool_use":
                items.append(
                    {
                        "type": "function_call",
                        "call_id": block.get("id") or "",
                        "name": block.get("name") or "",
                        "arguments": json.dumps(block.get("input") or {}),
                    }
                )
            elif role == "user" and kind == "tool_result":
                output = block.get("content")
                if not isinstance(output, str):
                    output = json.dumps(output)
                items.append(
                    {
                        "type": "function_call_output",
                        "call_id": block.get("tool_use_id") or "",
                        "output": output,
                    }
                )
            elif role == "user" and kind == "text":
                items.append({"role": "user", "content": block.get("text") or ""})
            else:
                raise OpenAIResponseError(f"Refusing to send message block {kind!r}.")
    return items


def responses_payload(
    model: str,
    messages: list[dict],
    tools: list[dict],
    system: str | None,
    max_tokens: int,
    effort: str,
) -> dict:
    """The JSON body. This does not open a connection."""
    chosen = assert_openai_model(model)
    name = assert_effort(chosen, effort)
    body = {
        "model": chosen,
        "instructions": system or "",
        "input": responses_input(messages),
        "tools": responses_tools(tools),
        "max_output_tokens": int(max_tokens),
        "reasoning": {"effort": name},
        "store": False,
    }
    tool_types = {tool["type"] for tool in body["tools"]}
    if tool_types - {"function"}:
        raise OpenAIResponseError("Refusing to send a non-function tool.")
    return body


def normalize_usage(usage: dict) -> dict:
    """Token counts this ledger knows how to price. Anything else fails closed."""
    if not isinstance(usage, dict):
        raise PriceUnknown("Usage is missing. Refusing to price.")
    extra = set(usage) - _USAGE_TOP
    if extra:
        raise PriceUnknown(
            f"Usage has unrecognized fields {sorted(extra)}. Refusing to price."
        )
    details_in = usage.get("input_tokens_details") or {}
    details_out = usage.get("output_tokens_details") or {}
    if not isinstance(details_in, dict) or not isinstance(details_out, dict):
        raise PriceUnknown("Usage details are not objects. Refusing to price.")
    if set(details_in) - _INPUT_DETAILS:
        raise PriceUnknown(
            f"Input usage has unrecognized fields {sorted(set(details_in) - _INPUT_DETAILS)}. "
            "Refusing to price."
        )
    if set(details_out) - _OUTPUT_DETAILS:
        raise PriceUnknown(
            f"Output usage has unrecognized fields {sorted(set(details_out) - _OUTPUT_DETAILS)}. "
            "Refusing to price."
        )
    try:
        incoming = int(usage.get("input_tokens") or 0)
        outgoing = int(usage.get("output_tokens") or 0)
        cached = int(details_in.get("cached_tokens") or 0)
    except (TypeError, ValueError) as exc:
        raise PriceUnknown("Usage token counts are not integers. Refusing to price.") from exc
    if incoming < 0 or outgoing < 0 or cached < 0 or cached > incoming:
        raise PriceUnknown("Usage token counts are inconsistent. Refusing to price.")
    return {
        "input_tokens": incoming,
        "output_tokens": outgoing,
        "cached_tokens": cached,
    }


def anthropic_shaped(payload: dict) -> dict:
    """A Responses body as the content blocks the harness already reads."""
    if not isinstance(payload, dict):
        raise OpenAIResponseError("Response is not an object.")
    if payload.get("error"):
        raise OpenAIResponseError("Response carried an error. Refusing to continue.")
    content = []
    for item in payload.get("output") or []:
        if not isinstance(item, dict):
            raise OpenAIResponseError("Response item is not an object.")
        kind = item.get("type")
        if kind not in _OUTPUT_ITEMS:
            raise OpenAIResponseError(f"Unsupported response item {kind!r}. Refusing to continue.")
        if kind == "reasoning":
            continue
        if kind == "message":
            for part in item.get("content") or []:
                if not isinstance(part, dict):
                    continue
                if part.get("type") in ("output_text", "text"):
                    content.append({"type": "text", "text": part.get("text") or ""})
        elif kind == "function_call":
            raw = item.get("arguments") or "{}"
            try:
                parsed = json.loads(raw) if isinstance(raw, str) else raw
            except json.JSONDecodeError as exc:
                raise OpenAIResponseError("Function call arguments are not JSON.") from exc
            if not isinstance(parsed, dict):
                parsed = {}
            content.append(
                {
                    "type": "tool_use",
                    "id": item.get("call_id") or item.get("id") or "",
                    "name": item.get("name") or "",
                    "input": parsed,
                }
            )
    usage = normalize_usage(payload.get("usage") or {})
    stop = "tool_use" if any(block["type"] == "tool_use" for block in content) else "end_turn"
    return {"content": content, "stop_reason": stop, "usage": usage}


class OpenAIClient:
    """Tool-use client. gpt-6.1-sol and gpt-6-luna only."""

    def __init__(self, api_key: str, model: str, effort: str, transport=None):
        self.api_key = api_key
        self.model = assert_openai_model(model)
        self.effort = assert_effort(self.model, effort)
        self.transport = transport or _post_openai
        self.base_url = OPENAI_RESPONSES_URL

    async def create_message(
        self,
        messages: list[dict],
        tools: list[dict],
        system: str | None = None,
        max_tokens: int = 4096,
    ) -> tuple[dict, float]:
        """One Responses call. Returns the harness-shaped body and the elapsed milliseconds."""
        assert_openai_model(self.model)
        assert_effort(self.model, self.effort)
        payload = responses_payload(
            self.model,
            messages,
            tools,
            system,
            max_tokens,
            self.effort,
        )
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "content-type": "application/json",
        }
        start = time.perf_counter()

        def send() -> str:
            return self.transport(self.base_url, headers, payload)

        loop = asyncio.get_event_loop()
        body = await loop.run_in_executor(None, send)
        elapsed_ms = (time.perf_counter() - start) * 1000
        parsed = json.loads(body)
        return anthropic_shaped(parsed), elapsed_ms
