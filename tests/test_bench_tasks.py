"""Public task wording still matches the direct router. No model call."""

from loop.actions import Control, Observation
from loop.planner import direct_batch

from bench.catalog import agent_tasks


def _task(task_id: str):
    return next(task for task in agent_tasks() if task.id == task_id)


def _batch(task_id: str, controls, title: str, url: str = "file:///local.html"):
    task = _task(task_id)
    return direct_batch(task.instruction, Observation(url, title, controls), [])


def test_invoice_is_one_direct_batch():
    controls = [
        Control("e1", "textbox", "Customer name", ""),
        Control("e2", "textbox", "City", ""),
        Control("e3", "button", "Submit order", ""),
    ]
    batch = _batch("invoice-ada", controls, "Invoice")
    assert batch is not None
    assert [type(action).__name__ for action in batch.actions] == [
        "FillNamed",
        "FillNamed",
        "ClickNamed",
    ]
    assert batch.done is True


def test_login_fills_and_does_not_submit():
    controls = [
        Control("e1", "textbox", "Username", ""),
        Control("e2", "textbox", "Password", ""),
    ]
    batch = _batch("login-hold", controls, "Sign in")
    assert batch is not None
    assert [type(action).__name__ for action in batch.actions] == ["FillNamed", "FillNamed"]
    assert batch.done is True


def test_newsletter_clicks_the_named_box():
    controls = [
        Control("e1", "textbox", "Email", ""),
        Control("e2", "checkbox", "Weekly notes", ""),
        Control("e3", "button", "Submit order", ""),
    ]
    batch = _batch("newsletter-optin", controls, "Notes")
    assert batch is not None
    assert [type(action).__name__ for action in batch.actions] == [
        "FillNamed",
        "ClickNamed",
        "ClickNamed",
    ]
    assert batch.actions[1].name == "Weekly notes"


def test_delivery_clicks_only_the_named_radio():
    controls = [
        Control("e1", "textbox", "Reference", ""),
        Control("e2", "radio", "Express post", ""),
        Control("e3", "radio", "Standard post", ""),
        Control("e4", "button", "Submit order", ""),
    ]
    batch = _batch("delivery-radio", controls, "Delivery")
    assert batch is not None
    names = [action.name for action in batch.actions]
    assert "Express post" in names
    assert "Standard post" not in names
    assert names[-1] == "Submit order"


def test_catalog_search_does_not_call_a_model():
    controls = [Control("e1", "textbox", "Search catalog", "")]
    batch = _batch("catalog-wool", controls, "Catalog")
    assert batch is not None
    assert [type(action).__name__ for action in batch.actions] == ["Fill", "Press"]
    assert batch.actions[0].text == "wool"


def test_open_section_is_a_direct_click():
    controls = [Control("e1", "link", "Childhood", "")]
    batch = _batch("open-childhood", controls, "Saved biography")
    assert batch is not None
    assert batch.actions[0].name == "Childhood"
    assert batch.done is True


def test_filter_button_is_a_direct_click():
    controls = [Control("e1", "button", "Apply the cedar filter", "")]
    batch = _batch("filter-cedar", controls, "Cedar rack")
    assert batch is not None
    assert batch.actions[0].name == "Apply the cedar filter"
    assert batch.done is True


def test_packing_list_is_left_to_the_fake_planner():
    controls = [
        Control("e1", "textbox", "Item", ""),
        Control("e2", "button", "Add", ""),
    ]
    assert _batch("pack-milk", controls, "Packing list") is None
