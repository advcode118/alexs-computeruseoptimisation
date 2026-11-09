"""LLM judge for evaluating task success.

Two evaluation methods:
1. Simple checks: URL contains, text present, title matches
2. LLM judge: uses a model to compare the agent's result to expected answer
"""

from __future__ import annotations

import json
import os
import urllib.request
import urllib.error
from dataclasses import dataclass
from urllib.parse import unquote, urlsplit


@dataclass
class JudgeResult:
    """Result of judging a task."""
    success: bool
    reason: str
    confidence: float


def is_search_results_url(url: str) -> bool:
    """True for a results page, including Special:Search?search=Ada_Lovelace.

    A query that merely contains the token is not the finished article.
    """
    if not isinstance(url, str) or not url:
        return False
    raw = url.strip()
    decoded = unquote(raw).casefold()
    if "special:search" in decoded or "special%3asearch" in raw.casefold():
        return True
    parts = urlsplit(raw)
    path = unquote(parts.path).casefold()
    trimmed = path.rstrip("/")
    if trimmed.endswith("/search") or trimmed.endswith("/search.html") or "/search.html" in path:
        return True
    query = unquote(parts.query).casefold()
    if trimmed.endswith("index.php") and (
        query.startswith("search=") or query.startswith("search%3d") or "&search=" in f"&{query}"
    ):
        return True
    return False


def check_url_contains(current_url: str, expected: str) -> JudgeResult:
    """Check if URL contains expected string.

    Search-results URLs fail even when the token is in the query.
    """
    if is_search_results_url(current_url):
        return JudgeResult(
            success=False,
            reason=f"URL is a search page: '{current_url}'",
            confidence=1.0,
        )
    if expected.lower() in current_url.lower():
        return JudgeResult(
            success=True,
            reason=f"URL contains '{expected}'",
            confidence=1.0,
        )
    return JudgeResult(
        success=False,
        reason=f"URL '{current_url}' does not contain '{expected}'",
        confidence=1.0,
    )


def check_text_present(page_text: str, expected: str | list[str]) -> JudgeResult:
    """Check if expected text(s) are present on the page."""
    if isinstance(expected, str):
        expected = [expected]

    missing = []
    for text in expected:
        if text.lower() not in page_text.lower():
            missing.append(text)

    if not missing:
        return JudgeResult(
            success=True,
            reason=f"All expected text found: {expected}",
            confidence=1.0,
        )
    return JudgeResult(
        success=False,
        reason=f"Missing text: {missing}",
        confidence=1.0,
    )


def check_title_contains(page_title: str, expected: str) -> JudgeResult:
    """Check if page title contains expected string."""
    if expected.lower() in page_title.lower():
        return JudgeResult(
            success=True,
            reason=f"Title contains '{expected}'",
            confidence=1.0,
        )
    return JudgeResult(
        success=False,
        reason=f"Title '{page_title}' does not contain '{expected}'",
        confidence=1.0,
    )


JUDGE_SYSTEM = """You are evaluating whether a browser automation agent successfully completed a task.

Given:
- The task description
- The expected answer or success criteria
- The agent's final state (URL, page title, any extracted text)
- The agent's own assessment

Respond with a JSON object:
{
  "success": true/false,
  "reason": "Brief explanation",
  "confidence": 0.0-1.0
}

Be strict but fair. If the agent got to the right place and found the information, that counts as success even if the format differs slightly."""


def llm_judge(
    task_description: str,
    expected_answer: str,
    agent_state: dict,
    agent_assessment: str,
    api_key: str | None = None,
    model: str = "claude-haiku-4-5-20251001",
) -> JudgeResult:
    """Use an LLM to judge task success."""
    if "opus" in (model or "").lower():
        return JudgeResult(
            success=False,
            reason="Refusing Opus. The bench never calls Opus.",
            confidence=0.0,
        )
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return JudgeResult(
            success=False,
            reason="No API key for LLM judge",
            confidence=0.0,
        )

    user_message = f"""Task: {task_description}

Expected answer/criteria: {expected_answer}

Agent's final state:
- URL: {agent_state.get('url', 'unknown')}
- Title: {agent_state.get('title', 'unknown')}
- Extracted text: {agent_state.get('text', 'none')[:500]}

Agent's assessment: {agent_assessment}

Did the agent successfully complete the task? Respond with JSON."""

    payload = {
        "model": model,
        "max_tokens": 200,
        "system": JUDGE_SYSTEM,
        "messages": [{"role": "user", "content": user_message}],
    }

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    try:
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=json.dumps(payload).encode(),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            response = json.loads(resp.read().decode())

        content = response.get("content", [])
        text = ""
        for block in content:
            if block.get("type") == "text":
                text += block.get("text", "")

        text = text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]

        result = json.loads(text)
        return JudgeResult(
            success=result.get("success", False),
            reason=result.get("reason", "Unknown"),
            confidence=result.get("confidence", 0.5),
        )

    except Exception as exc:
        return JudgeResult(
            success=False,
            reason=f"Judge error: {exc}",
            confidence=0.0,
        )


def evaluate_task(
    task: dict,
    final_url: str = "",
    final_title: str = "",
    page_text: str = "",
    agent_assessment: str = "",
    api_key: str | None = None,
) -> JudgeResult:
    """Evaluate a task using the appropriate method."""
    if "check_url_contains" in task:
        return check_url_contains(final_url, task["check_url_contains"])

    if "check_text" in task:
        return check_text_present(page_text, task["check_text"])

    if "check_title" in task:
        return check_title_contains(final_title, task["check_title"])

    if "judge_prompt" in task or "expected_answer" in task:
        return llm_judge(
            task_description=task.get("description", ""),
            expected_answer=task.get("expected_answer", task.get("judge_prompt", "")),
            agent_state={
                "url": final_url,
                "title": final_title,
                "text": page_text,
            },
            agent_assessment=agent_assessment,
            api_key=api_key,
        )

    return JudgeResult(
        success=False,
        reason="No evaluation criteria defined for task",
        confidence=0.0,
    )
