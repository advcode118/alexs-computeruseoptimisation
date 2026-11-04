"""Settle, then a compact diff. No API key and no network.

The child is a fake. Token counts are len(text)//4, the same estimate the
bench harness uses. Nothing calls Anthropic.
"""

from __future__ import annotations

import asyncio

from proxy.diff import (
    UNCHANGED,
    PageMemory,
    depth_snapshot_text,
    find_result_text,
    full_snapshot_text,
    limit_depth,
    memory_of,
    render_find,
    rewrite_arguments,
    show_snapshot,
    view_result_text,
)
from proxy.segment import dispatch
from proxy.settle import decide_settle, mutation_is_meaningful, parse_settle_result, settle_page

URL = "https://en.wikipedia.org/wiki/Main_Page"
TITLE = "Wikipedia, the free encyclopedia"

_LIST = """- list [ref=e2]:
  - listitem [ref=e3]: text
  - listitem [ref=e4]:
    - button "Button" [ref=e5]"""


def _tokens(text: str) -> int:
    """chars/4. Matches bench.harness.estimate_tokens without importing a model."""
    return max(1, len(text) // 4)


def _article(value: str) -> tuple[str, str, str]:
    """A long page. One textbox's value is the only thing that changes."""
    lines = ['- main "Article" [ref=e1]:']
    ref = 2
    query_ref = ""
    form_ref = ""
    for section in range(16):
        region = ref
        ref += 1
        lines.append(f'  - region "Section {section}" [ref=e{region}]:')
        lines.append(f'    - heading "Heading {section} of the article" [level=1] [ref=e{ref}]')
        ref += 1
        if section == 5:
            form_ref = f"e{ref}"
            lines.append(f'    - form "Search the site" [ref={form_ref}]:')
            ref += 1
            lines.append(f'      - navigation "Filters" [ref=e{ref}]:')
            ref += 1
            for name in ("Images", "News", "Videos", "Maps"):
                lines.append(f'        - link "{name}" [ref=e{ref}]')
                ref += 1
            query_ref = f"e{ref}"
            typed = f": {value}" if value else ""
            lines.append(f'      - textbox "Search Wikipedia" [ref={query_ref}]{typed}')
            ref += 1
            lines.append(f'      - button "Search" [ref=e{ref}]')
            ref += 1
            for name in ("Advanced search", "Search help", "Languages"):
                lines.append(f'      - link "{name}" [ref=e{ref}]')
                ref += 1
        for item in range(8):
            lines.append(f'    - link "Result {section}.{item} about a longer topic name" [ref=e{ref}]')
            ref += 1
            lines.append(f"      - /url: https://en.wikipedia.org/wiki/Result_{section}_{item}")
            lines.append(
                f'    - paragraph "Paragraph {section}.{item} fills out the article body with extra words." [ref=e{ref}]'
            )
            ref += 1
    return "\n".join(lines), query_ref, form_ref


class _Pages:
    def __init__(self, pages: list[str], evaluate: str = '{"settled": true, "reason": "quiet"}'):
        self.pages = list(pages)
        self.evaluate = evaluate
        self.calls: list[tuple[str, dict]] = []
        self._shot = 0

    async def call_tool(self, name, arguments):
        args = arguments or {}
        self.calls.append((name, args))
        if name == "browser_evaluate":
            return {"content": [{"type": "text", "text": self.evaluate}], "isError": False}
        if name == "browser_snapshot":
            text = self.pages[min(self._shot, len(self.pages) - 1)] if self.pages else ""
            if self._shot < len(self.pages) - 1:
                self._shot += 1
            return {"content": [{"type": "text", "text": text}], "isError": False}
        return {"content": [{"type": "text", "text": "ok"}], "isError": False}


def test_depth_limit_matches_the_playwright_snapshot():
    assert limit_depth(_LIST, target=None, depth=1) == (
        "- list [ref=e2]:\n"
        "  - listitem [ref=e3]: text\n"
        "  - listitem [ref=e4]"
    )
    assert limit_depth(_LIST, target=None, depth=2) == _LIST
    assert limit_depth(_LIST, target="e4", depth=2) == (
        "- listitem [ref=e4]:\n"
        "  - button \"Button\" [ref=e5]"
    )
    wrapped = depth_snapshot_text(_LIST, url=URL, title=TITLE, target="e2", depth=1)
    assert wrapped.startswith("### Page\n")
    assert "```yaml\n" in wrapped
    assert '[ref=e5]' not in wrapped


def test_find_keeps_the_path_and_nearby_lines():
    page = "\n".join(
        [
            '- main "Article" [ref=e1]:',
            '  - region "Sidebar" [ref=e2]:',
            '    - navigation "Primary" [ref=e3]:',
            '      - list "Links" [ref=e4]:',
            '        - listitem [ref=e5]:',
            '          - link "Home" [ref=e6]',
            '        - listitem [ref=e7]:',
            '          - link "Deep Target Link" [ref=e8]',
            '        - listitem [ref=e9]:',
            '          - link "Other" [ref=e10]',
            '        - listitem [ref=e11]:',
            '          - link "Far Away Topic" [ref=e12]',
        ]
    )
    found = render_find(page, "Deep Target Link")
    assert found.startswith('Found 1 match for "Deep Target Link":')
    assert 'main "Article"' in found
    assert 'link "Home"' in found
    assert 'link "Deep Target Link" [ref=e8]' in found
    assert "Far Away Topic" not in found
    tool = find_result_text(page, "Deep Target Link")
    assert tool.startswith("### Result\n")


def test_settle_times_out_while_the_page_keeps_mutating():
    events = [(time_ms, True) for time_ms in range(0, 2000, 50)]
    assert decide_settle(events, quiet_ms=100, timeout_ms=1500) == "timeout"
    assert decide_settle([], quiet_ms=100, timeout_ms=1500) == "quiet"
    parsed = parse_settle_result('### Result\n{"settled": false, "reason": "timeout"}')
    assert parsed == {"settled": False, "reason": "timeout"}


def test_settle_ignores_mutations_that_do_not_change_the_tree():
    assert mutation_is_meaningful({"type": "attributes", "attribute": "style", "tag": "div"}) is False
    assert mutation_is_meaningful({"type": "attributes", "attribute": "class", "tag": "div"}) is False
    assert mutation_is_meaningful({"type": "attributes", "attribute": "data-id", "tag": "div"}) is False
    assert mutation_is_meaningful({"type": "childList", "tag": "script"}) is False
    assert mutation_is_meaningful({"type": "childList", "tag": "div"}) is True
    assert mutation_is_meaningful({"type": "attributes", "attribute": "aria-expanded", "tag": "button"}) is True
    # style/class/script noise does not push a quiet page out to the timeout
    noisy = [(0, True), (40, False), (80, False), (500, False), (1200, False)]
    assert decide_settle(noisy, quiet_ms=100, timeout_ms=1500) == "quiet"


def test_settle_times_out_when_evaluate_hangs():
    class Hang:
        async def call_tool(self, name, arguments):
            await asyncio.sleep(5)

    result = asyncio.run(settle_page(Hang(), timeout_s=0.05))
    assert result == {"settled": False, "reason": "timeout"}


def test_first_snapshot_is_a_pruned_tree():
    raw = "\n".join(
        [
            "- generic:",
            '  - link "Home" [ref=e3] [box=8,8,40,16] [cursor=pointer]:',
            "    - /url: https://example.com/home",
            '  - button "OK" [ref=e4] [box=1,2,3,4]',
        ]
    )
    view = show_snapshot(PageMemory(), raw)
    assert "[box=" not in view.text
    assert "/url" not in view.text
    assert "cursor=" not in view.text
    assert '[ref=e3]' in view.text
    assert '[ref=e4]' in view.text
    assert "Home" in view.text
    assert len(view.text) < len(raw)
    assert view.diff_chars == len(view.text)
    assert view.full_chars == len(raw)


def test_unchanged_page_is_a_tiny_diff():
    page, _query, _form = _article("")
    memory = PageMemory()
    show_snapshot(memory, page)
    again = show_snapshot(memory, page)
    assert again.text == UNCHANGED
    assert again.diff_chars == len(UNCHANGED)
    assert again.diff_chars < 20
    assert again.diff_chars * 10 < again.full_chars
    tool = view_result_text(again)
    assert "full_snapshot_chars:" in tool
    assert "diff_chars:" in tool
    assert len(tool) * 4 < len(page)


def test_one_changed_control_keeps_untouched_refs():
    before = "\n".join(
        [
            '- main "Packing" [ref=e1]:',
            '  - button "OK" [ref=e2]',
            '  - button "Cancel" [ref=e3]',
            '  - textbox "Item" [ref=e4]',
        ]
    )
    after = "\n".join(
        [
            '- main "Packing" [ref=e10]:',
            '  - button "OK" [ref=e11]',
            '  - button "Cancel" [ref=e12]',
            '  - textbox "Item" [ref=e13]: milk',
        ]
    )
    memory = PageMemory()
    show_snapshot(memory, before)
    changed = show_snapshot(memory, after)
    assert changed.text == '~ textbox "Item" [ref=e4]: milk'
    assert "[ref=e11]" not in changed.text
    assert "[ref=e12]" not in changed.text
    assert "[ref=e13]" not in changed.text
    assert "OK" not in changed.text
    assert "Cancel" not in changed.text
    assert memory.live_for_stable["e2"] == "e11"
    assert memory.live_for_stable["e3"] == "e12"
    assert memory.live_for_stable["e4"] == "e13"
    assert memory.live_for_stable["e1"] == "e10"
    rewritten = rewrite_arguments(memory, {"target": "e3", "element": "Cancel"})
    assert rewritten == {"target": "e12", "element": "Cancel"}


def test_diff_is_smaller_than_a_full_depth_and_find_snapshot():
    before, query_ref, form_ref = _article("")
    after, after_query, after_form = _article("Ada Lovelace")
    assert query_ref == after_query
    assert form_ref == after_form
    memory = PageMemory()
    show_snapshot(memory, before)
    view = show_snapshot(memory, after)
    ours = view_result_text(view)
    full = full_snapshot_text(after, url=URL, title=TITLE)
    depth = depth_snapshot_text(after, url=URL, title=TITLE, target=query_ref, depth=2)
    region = depth_snapshot_text(after, url=URL, title=TITLE, target=form_ref, depth=2)
    found = find_result_text(after, "Ada Lovelace")
    assert view.text.startswith("~ ")
    assert query_ref in view.text
    assert "Result 0.0" not in view.text
    assert "main" in found and "Search Wikipedia" in found
    sizes = {
        "full_chars": len(full),
        "depth_chars": len(depth),
        "region_depth_chars": len(region),
        "find_chars": len(found),
        "diff_chars": len(ours),
        "diff_body_chars": len(view.text),
        "full_tokens": _tokens(full),
        "depth_tokens": _tokens(depth),
        "region_depth_tokens": _tokens(region),
        "find_tokens": _tokens(found),
        "diff_tokens": _tokens(ours),
    }
    assert sizes["diff_chars"] < sizes["full_chars"], sizes
    assert sizes["diff_chars"] < sizes["depth_chars"], sizes
    assert sizes["diff_chars"] < sizes["region_depth_chars"], sizes
    assert sizes["diff_chars"] < sizes["find_chars"], sizes
    assert sizes["diff_body_chars"] < len(after), sizes
    assert sizes["diff_tokens"] < sizes["full_tokens"], sizes
    assert sizes["diff_tokens"] < sizes["depth_tokens"], sizes
    assert sizes["diff_tokens"] < sizes["region_depth_tokens"], sizes
    assert sizes["diff_tokens"] < sizes["find_tokens"], sizes
    assert f"full_snapshot_chars: {view.full_chars}" in ours
    assert f"diff_chars: {view.diff_chars}" in ours


def test_forwarded_action_settles_then_returns_the_diff():
    before = "\n".join(
        [
            '- main "Packing" [ref=e1]:',
            '  - button "OK" [ref=e2]',
            '  - button "Cancel" [ref=e3]',
            '  - textbox "Item" [ref=e4]',
        ]
    )
    after = "\n".join(
        [
            '- main "Packing" [ref=e10]:',
            '  - button "OK" [ref=e11]',
            '  - button "Cancel" [ref=e12]',
            '  - textbox "Item" [ref=e13]: milk',
        ]
    )
    child = _Pages([before, after], evaluate='{"settled": false, "reason": "timeout"}')
    opened = asyncio.run(dispatch(child, "browser_snapshot", {}))
    assert "full_snapshot_chars:" in opened["content"][0]["text"]
    result = asyncio.run(dispatch(child, "browser_click", {"target": "e3"}))
    text = result["content"][0]["text"]
    assert result["isError"] is False
    assert '~ textbox "Item" [ref=e4]: milk' in text
    assert "full_snapshot_chars:" in text
    assert "diff_chars:" in text
    assert "[ref=e13]" not in text
    names = [name for name, _args in child.calls]
    assert names == ["browser_snapshot", "browser_click", "browser_evaluate", "browser_snapshot"]
    assert child.calls[1][1]["target"] == "e3"
    assert "MutationObserver" in child.calls[2][1]["function"]
    assert "timeout" in child.calls[2][1]["function"]
    assert rewrite_arguments(memory_of(child), {"target": "e2"}) == {"target": "e11"}
    assert rewrite_arguments(memory_of(child), {"target": "e3"}) == {"target": "e12"}
