"""Count full-page observes that ignore a compact diff.

The outer model sometimes calls browser_snapshot, or another full-page
observe, after an action already returned a compact diff. LangChain saw the
same thing: trimming a snapshot after the fact failed because the agent
fetched the full page again. This counter is that event. A scoped snapshot
(a target, a depth, or a ref) is not a full-page observe and does not count.
"""

from __future__ import annotations

FULL_PAGE_OBSERVE_TOOLS = frozenset(
    {
        "browser_snapshot",
        "browser_observe",
        "observe",
        "snapshot",
    }
)
_SCOPE_KEYS = ("target", "ref", "depth", "selector")


_AFTER_DIFF = (
    " Do not take a full snapshot after a diff was returned."
    " That call is counted as model_ignores_tools."
)


def annotate_tool_description(name: str, description: str) -> str:
    """Tell the outer model not to snapshot again after a compact diff.

    The child's own description is left unchanged on tools/list. This note is
    added when the description is handed to the model, and only on a full-page
    observe tool that does not already mention the counter.
    """
    text = description or ""
    if (name or "").strip() not in FULL_PAGE_OBSERVE_TOOLS:
        return text
    if "model_ignores_tools" in text:
        return text
    return text.rstrip() + _AFTER_DIFF


def is_full_page_observe(tool_name: str, tool_args: dict | None) -> bool:
    """True for a snapshot or observe that asks for the whole page."""
    if (tool_name or "").strip() not in FULL_PAGE_OBSERVE_TOOLS:
        return False
    args = tool_args or {}
    for key in _SCOPE_KEYS:
        value = args.get(key)
        if value not in (None, "", 0, False):
            return False
    return True


def action_returned_compact_diff(tool_name: str, result_text: str) -> bool:
    """True when this tool result is a compact diff from an action.

    A full-page observe is not itself a diff, even if the proxy stamps the
    same size lines on the pruned tree.
    """
    if is_full_page_observe(tool_name, {}):
        return False
    text = result_text or ""
    has_diff = "diff_chars:" in text or '"diff_chars"' in text
    has_full = "full_snapshot_chars:" in text or '"full_snapshot_chars"' in text
    return has_diff and has_full


class IgnoreCounter:
    """Running 'model ignores tools' count for one outer-agent session."""

    def __init__(self) -> None:
        self.count = 0
        self._last_was_diff = False
        self._call_name = ""
        self._call_args: dict | None = None

    def note_call(self, tool_name: str, tool_args: dict | None = None) -> bool:
        """Count this call when the previous result was already a compact diff."""
        self._call_name = tool_name or ""
        self._call_args = tool_args
        ignored = self._last_was_diff and is_full_page_observe(tool_name, tool_args)
        if ignored:
            self.count += 1
        return ignored

    def note_result(self, tool_name: str, result_text: str) -> None:
        """A compact action diff arms the counter. A full-page observe disarms it.

        A scoped snapshot does neither: the model still has the diff, so a
        later full-page observe still counts.
        """
        if action_returned_compact_diff(tool_name, result_text):
            self._last_was_diff = True
        elif is_full_page_observe(self._call_name, self._call_args):
            self._last_was_diff = False


def ignore_counter(child) -> IgnoreCounter:
    """The counter stored on a proxy child. Created on first use."""
    counter = getattr(child, "_ignore_counter", None)
    if isinstance(counter, IgnoreCounter):
        return counter
    counter = IgnoreCounter()
    setattr(child, "_ignore_counter", counter)
    return counter
