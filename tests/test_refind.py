"""Role and name refind when a snapshot ref has gone stale."""

import pytest

from backends.dom import DomBackend
from backends.playwright_mcp import PlaywrightMcpBackend
from core.backend import Element, Locator, refind_element, resolve_locator
from loop.actions import ActionError, Click, Fill, Goto, Press, Scroll
from loop.browser import BrowserSession, fixture_file_url


def _element(ref: str, role: str, name: str, path: tuple[str, ...] = ()) -> Element:
    return Element(id=ref, role=role, name=name, path=path, source="aria")


def test_refind_keeps_a_live_id_and_replaces_a_stale_one():
    current = _element("e12", "button", "Search")
    assert refind_element(current, [current]) is current

    stale = _element("e12", "button", "Search", ("navigation:Site",))
    live = [
        _element("e30", "button", "Search", ("navigation:Site",)),
        _element("e31", "link", "Home"),
    ]
    found = refind_element(stale, live)
    assert found is not None and found.id == "e30"


def test_refind_rejects_a_reused_id_and_an_ambiguous_name():
    stale = _element("e12", "button", "Search")
    reused = [
        _element("e12", "link", "Home"),
        _element("e40", "button", "Search"),
    ]
    found = refind_element(stale, reused)
    assert found is not None and found.id == "e40"

    ambiguous = [
        _element("e20", "button", "Search", ("navigation:Site",)),
        _element("e21", "button", "Search", ("contentinfo",)),
    ]
    assert refind_element(_element("e12", "button", "Search"), ambiguous) is None
    assert refind_element(stale, ambiguous) is None
    assert refind_element(_element("e9", "list", ""), [_element("e2", "list", "")]) is None


def test_refind_uses_the_ancestor_path_to_break_a_tie():
    stale = _element("e12", "button", "Search", ("navigation:Site",))
    live = [
        _element("e20", "button", "Search", ("contentinfo",)),
        _element("e21", "button", "search", ("navigation:Site",)),
    ]
    found = refind_element(stale, live)
    assert found is not None and found.id == "e21"

    same_path = [
        _element("e20", "button", "Search", ("navigation:Site",)),
        _element("e21", "button", "Search", ("navigation:Site",)),
    ]
    assert refind_element(stale, same_path) is None


def test_resolve_picks_nth_among_the_same_role_and_name():
    elements = [
        _element("e2", "button", "Add", ("form",)),
        _element("e3", "button", "Add", ("form",)),
        _element("e4", "button", "Add", ("menu",)),
    ]
    second = resolve_locator(Locator("button", "Add", nth=1, path=("form",)), elements)
    assert second is not None and second.id == "e3"
    assert resolve_locator(Locator("button", "Add", nth=2, path=("form",)), elements) is None
    other_window = resolve_locator(Locator("button", "Add", window="Other"), elements, window="Packing")
    assert other_window is None


def test_playwright_backend_repairs_a_stale_target():
    backend = PlaywrightMcpBackend()
    backend.load_snapshot(
        '- button "Search" [ref=e12]\n- textbox "Query" [ref=e5]\n',
        url="https://example.com",
        title="Search",
    )
    fresh = backend.load_snapshot(
        '- button "Search" [ref=e30] [box=1,2,3,4]\n- textbox "Query" [ref=e31]\n',
        url="https://example.com/results",
        title="Results",
    )
    assert fresh.elements[0].bounds is not None
    assert backend.refind(_element("e12", "button", "Search")).id == "e30"

    backend.act(Click("e12"))
    backend.act(Fill("e5", "Ada Lovelace"))
    backend.act(Goto("https://example.com"))
    backend.act(Press("Enter"))
    assert backend.calls[0].name == "browser_click"
    assert backend.calls[0].repaired is True
    assert backend.calls[0].arguments["target"] == "e30"
    assert "ref" not in backend.calls[0].arguments
    assert backend.calls[1].name == "browser_type"
    assert backend.calls[1].arguments == {
        "target": "e31",
        "element": 'textbox "Query"',
        "text": "Ada Lovelace",
    }
    assert backend.calls[1].repaired is True
    assert backend.calls[2].name == "browser_navigate"
    assert backend.calls[3].arguments == {"key": "Enter"}

    still = PlaywrightMcpBackend()
    still.load_snapshot('- button "Search" [ref=e12]\n')
    still.act(Click("e12"))
    assert still.calls[0].repaired is False
    assert still.calls[0].arguments["target"] == "e12"

    with pytest.raises(ActionError):
        still.act(Scroll("down"))


def test_playwright_backend_refuses_an_ambiguous_stale_ref():
    backend = PlaywrightMcpBackend()
    backend.load_snapshot('- button "Search" [ref=e12]\n')
    backend.load_snapshot('- button "Search" [ref=e20]\n- button "Search" [ref=e21]\n')
    with pytest.raises(ActionError) as caught:
        backend.act(Click("e12"))
    assert "e12" in str(caught.value)
    assert backend.calls == []


def test_dom_backend_refinds_a_control_after_its_ref_attribute_is_cleared():
    session = BrowserSession(headless=True)
    session.open()
    try:
        session.page.goto(fixture_file_url())
        backend = DomBackend(session)
        snapshot = backend.observe()
        item = next(element for element in snapshot.elements if element.name == "Item")
        add = next(element for element in snapshot.elements if element.name == "Add")
        assert item.source == "dom"
        assert backend.refind(item).id == item.id
        assert backend.capabilities.source == "dom"

        session.page.evaluate(
            "() => document.querySelectorAll('[data-cu-ref]').forEach((node) => node.removeAttribute('data-cu-ref'))"
        )
        backend.act(Fill(item.id, "milk"))
        assert session.page.locator("#item").input_value() == "milk"
        assert session.page.locator(f'[data-cu-ref="{item.id}"]').count() == 1

        session.page.evaluate(
            """() => {
              const extra = document.createElement("button");
              extra.textContent = "Add";
              document.body.appendChild(extra);
              document.querySelectorAll("[data-cu-ref]").forEach((node) => node.removeAttribute("data-cu-ref"));
            }"""
        )
        with pytest.raises(ActionError) as caught:
            backend.act(Click(add.id))
        assert "Matched 2" in str(caught.value)
        assert session.page.locator("#list li").count() == 0

        settled = backend.settle(snapshot, timeout=1)
        assert settled.url.endswith("packing.html")
        assert any(element.name == "Item" for element in settled.elements)
    finally:
        session.close()
