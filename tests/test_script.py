"""Playwright locator parser. No API key or network."""

import pytest

from proxy.script import ScriptError, parse_script

SCRIPT = """
// fill then click
await page.getByRole("textbox", { name: "Search Wikipedia" }).fill("Ada Lovelace");
page.getByRole('button', { name: 'Search', exact: true }).click()
"""


def test_parser_accepts_locator_lines_and_rejects_code():
    actions = parse_script(SCRIPT)
    assert [(item.finder, item.role, item.name, item.op, item.value) for item in actions] == [
        ("role", "textbox", "Search Wikipedia", "fill", "Ada Lovelace"),
        ("role", "button", "Search", "click", ""),
    ]
    label = parse_script('page.getByLabel("Item").fill("milk")')
    assert label[0].finder == "label"
    assert label[0].value == "milk"
    with pytest.raises(ScriptError):
        parse_script('page.evaluate(() => document.title)')
    with pytest.raises(ScriptError):
        parse_script('page.goto("https://example.test")')
    with pytest.raises(ScriptError):
        parse_script("page.getByRole('button', { name: 'Go' }).click()\n" * 5, max_lines=4)
