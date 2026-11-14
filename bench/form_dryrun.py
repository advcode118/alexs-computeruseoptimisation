"""Model-free dry run of the form strategy on live public pages. No model calls, no spend.

Run ``python -m bench.form_dryrun [task_id ...]``. A scripted stand-in for the
model reads the same rendered schema the model would see and picks fields
and buttons by label text (hand-written below), so this measures how far the
model-free parts get: schema extraction, the filler, the submit-and-settle,
the new-text diff, and the end check. The final grade is the probe's own.
"""

from __future__ import annotations

import asyncio
import re
import sys
import time

from playwright.async_api import async_playwright

from bench.probe import grade_observation
from bench.script_first import ClaimedEvidence
from bench.strategy_form import run_form_strategy
from bench.tasks import tasks_for_split

# Each step: ("fill", {label regex: value}, button regex) | ("click", None, regex) | ("done", answer, None).
PLANS = {
    "dev4_form_cura_appointment": [
        ("click", None, r"^make appointment$"),
        ("fill", {r"^username": "John Doe", r"^password": "ThisIsNotAPassword"}, r"^login$"),
        ("fill", {r"^facility": "Hongkong CURA Healthcare Center", r"readmission": "on", r"program": "Medicaid",
                  r"visit date": "20/05/2030", r"comment": "Annual check"}, r"book appointment"),
        ("done", "Please be informed that your appointment has been booked as following:", None),
    ],
    "dev4_form_ipcalc_broadcast": [
        ("fill", {r"address \(host": "192.168.10.77", r"^netmask|mask1|^/": "26"}, r"calculate"),
        ("done", "192.168.10.127", None),
    ],
    "dev4_form_epoch_timestamp": [
        ("fill2", {r"^yyyy|year": "2024", r"^mm|month": "3", r"^dd|day": "15", r"^hh|hour": "12", r"^mn|min": "0",
                   r"^ss|sec": "0"}, r"human date to timestamp|date to timestamp"),
        ("done", "1710504000", None),
    ],
    "dev4_form_roman_convert": [
        ("fill", {r"number": "2749"}, r"^convert$"),
        ("done", "MMDCCXLIX", None),
    ],
    "dev4_form_lambdatest_input": [
        ("fill", {r"^name": "Alex Example", r"^email": "alex@example.com", r"^password": "Demo1234",
                  r"^company": "Example Ltd", r"^website": "https://example.com", r"^country": "United Kingdom",
                  r"^city": "Leeds", r"address 1|address line 1": "1 Main Street",
                  r"address 2|address line 2": "Flat 2", r"^state": "Yorkshire", r"zip": "LS1 1AA"}, r"^submit$"),
        ("done", "Thanks for contacting us, we will get back to you shortly.", None),
    ],
    "dev4_form_testmu_radio": [
        ("fill", {r"gender|sex": "Female", r"age": "15 - 50"}, r"get values"),
        ("done", "Age : 15 - 50", None),
    ],
    "dev4_form_playground_checkout": [
        ("fill", {r"quantity|qty": "1"}, r"add to cart"),
        ("click", None, r"checkout"),
        ("fill", {r"account": "Guest Checkout", r"first name": "Alex", r"last name": "Example", r"e-?mail": "alex@example.com",
                  r"address 1": "1 Main Street", r"^city": "Leeds", r"post ?code": "LS1 1AA", r"country": "United Kingdom",
                  r"region|state|zone": "West Yorkshire", r"agree|terms|privacy": "on"}, r"^continue$"),
        ("click", None, r"^choose$"),
        ("fill", {r"flat|shipping": "Flat Shipping Rate"}, r"^continue$"),
        ("done", "Your order has been placed!", None),
    ],
    "dev4_form_playground_enquiry": [
        ("click", None, r"^contact"),
        ("fill", {r"your name|^name": "Alex Example", r"e-?mail": "alex@example.com", r"enquiry": "I would like to ask about delivery times to Leeds."}, r"^submit$"),
        ("done", "Your enquiry has been successfully sent to the store owner!", None),
    ],
    "dev4_form_autoexercise_contact": [
        ("click", None, r"contact us"),
        ("fill", {r"^name": "Alex Example", r"^email": "alex@example.com", r"^subject": "Order question",
                  r"message": "Where is my order? It has not arrived yet."}, r"^submit$"),
        ("done", "Success! Your details have been submitted successfully.", None),
    ],
    "dev4_form_giga_percent": [
        ("fill", {r"calculation|mode|^op|percent change": "what is X percent of Y?"}, None),
        ("fill", {r"^x|first|valx": "17.5", r"^y|second|valy": "368"}, r"calculate"),
        ("done", "64.40", None),
    ],
    "dev4_form_soup_subtract": [
        ("fill", {r"month|dateinputm": "1", r"day|dateinputd": "15", r"year|dateinputy": "2030", r"operator|add|plus": "subtract",
                  r"^days": "100"}, r"calculate"),
        ("done", "October 7, 2029", None),
    ],
    "dev4_form_aos_contact": [
        ("click", None, r"contact us"),
        ("fill", {r"category": "Laptops", r"e-?mail": "alex@example.com", r"subject": "Battery life question"}, r"^send$"),
        ("done", "Thank you for contacting Advantage support.", None),
    ],
    "dev3_form_demoqa_textbox": [
        ("fill", {r"full name": "Alex Example", r"^email": "alex@example.com"}, r"^submit$"),
        ("done", "Name:Alex Example", None),
    ],
    "dev3_form_demoqa_practice": [
        ("fill", {r"^first name": "Alex", r"^last name": "Example", r"gender": "Other", r"mobile": "0123456789"}, r"^submit$"),
        ("done", "Thanks for submitting the form", None),
    ],
    "dev3_form_formy_complete": [
        ("fill", {r"first name": "Alex", r"last name": "Example", r"job title": "Tester"}, r"^submit$"),
        ("done", "The form was successfully submitted!", None),
    ],
    "dev3_form_blazedemo_purchase": [
        ("fill", {r"departure|from": "Boston", r"destination|to": "London"}, r"find flights"),
        ("click", None, r"choose this flight"),
        ("fill", {r"^name": "Alex Example"}, r"purchase flight"),
        ("done", "Thank you for your purchase today!", None),
    ],
    "dev3_form_aito_contact": [
        ("fill", {r"^name": "Alex Example", r"^email": "alex@example.com", r"^phone": "01234567890",
                  r"^subject": "Booking enquiry", r"message|description": "I would like to ask about booking a double room next spring."},
         r"^submit$"),
        ("done", "Thanks for getting in touch Alex Example!", None),
    ],
    "dev3_form_guru99_register": [
        ("fill", {r"first name": "Alex", r"last name": "Example", r"user ?name|email": "alexexample",
                  r"^password": "Demo1234", r"confirm": "Demo1234"}, r"submit"),
        ("done", "Thank you for registering.", None),
    ],
    "ho2_form_expand_ticket": [
        ("fill", {r"contact name": "Alex Example", r"contact number": "012-3456789", r"pick ?up date|date": "2030-01-15",
                  r"payment": "card"}, r"register|submit"),
        ("done", "Thank you for validating your ticket", None),
    ],
    "ho2_form_calculator_sum": [
        ("fill", {r"first|number 1|^one": "17", r"second|number 2|^two": "25", r"function|operation|operator": "plus"}, r"calculate"),
        ("done", "42", None),
    ],
}

_FIELD = re.compile(r'^\s*\[(\d+)\] (\S+) "(.*?)"(?: \((.*)\))?$')
_CONTROL = re.compile(r'^\s*\[(\d+)\] (?:submit button|button|link) "(.*?)"$')


def _parse(schema_text: str) -> tuple[list[tuple[int, str, str]], list[tuple[int, str]]]:
    fields, controls = [], []
    for line in schema_text.splitlines():
        control = _CONTROL.match(line)
        if control:
            controls.append((int(control.group(1)), control.group(2)))
            continue
        found = _FIELD.match(line)
        if found:
            fields.append((int(found.group(1)), found.group(2), found.group(3)))
    return fields, controls


def _last_schema(messages: list[dict]) -> str:
    last = messages[-1]["content"]
    if isinstance(last, list):
        last = last[0]["content"]
    return last.split("PAGE NOW:", 1)[-1]


class ScriptedModel:
    """Stands in for the model: same tool contract, choices by hand-written label regexes."""

    def __init__(self, plan):
        self.plan = list(plan)
        self.log: list[str] = []

    async def create_message(self, messages, tools, system=None, tool_choice=None):
        schema = _last_schema(messages)
        fields, controls = _parse(schema)
        if not self.plan:
            return {"content": [{"type": "tool_use", "id": "x", "name": "form_step", "input": {"action": "fail", "reason": "plan ended"}}]}, 0.0
        kind, data, button = self.plan.pop(0)
        action: dict = {"action": "fill" if kind.startswith("fill") else kind}
        if kind.startswith("fill"):
            chosen = []
            used: set[int] = set()
            for pattern, value in data.items():
                matches = [n for n, _typ, label in fields if re.search(pattern, label, re.IGNORECASE) and n not in used]
                if kind == "fill2" and len(matches) > 1:
                    matches = matches[:1]
                if not matches:
                    self.log.append(f"no field for /{pattern}/")
                    continue
                used.add(matches[0])
                chosen.append({"n": matches[0], "value": value})
            action["fields"] = chosen
        if kind == "done":
            action["answer"] = data
        if button:
            hits = [n for n, text in controls if re.search(button, text, re.IGNORECASE)]
            if hits:
                action["press"] = hits[0]
            else:
                self.log.append(f"no control for /{button}/")
        self.log.append(f"{kind}: {action}")
        return {"content": [{"type": "tool_use", "id": f"s{len(self.log)}", "name": "form_step", "input": action}],
                "usage": {}}, 0.0


async def dry_run(browser, task: dict) -> tuple:
    context = await browser.new_context(viewport={"width": 1366, "height": 900})
    page = await context.new_page()
    model = ScriptedModel(PLANS[task["id"]])
    try:
        started = time.perf_counter()
        outcome = await run_form_strategy(page, model, task["description"], task["start_url"])
        wall = time.perf_counter() - started
        graded = False
        if outcome.passed:
            text = await page.evaluate("() => (document.querySelector('main') || document.body).innerText")
            graded, _reason, _s, _ = grade_observation(
                task, page.url, text, answer=outcome.answer, run_verdict="PASS", claimed=ClaimedEvidence(answer=outcome.answer)
            )
        return task["id"], outcome.passed, graded, round(wall, 1), outcome.reason, model.log
    finally:
        await context.close()


async def main(ids: list[str]) -> int:
    tasks = [task for split in ("dev4form", "dev3", "heldout2") for task in tasks_for_split(split)
             if task["id"] in PLANS and (not ids or task["id"] in ids)]
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        semaphore = asyncio.Semaphore(4)
        rows = []

        async def one(task):
            async with semaphore:
                try:
                    rows.append(await dry_run(browser, task))
                except Exception as exc:  # noqa: BLE001
                    rows.append((task["id"], False, False, 0.0, f"error {exc}", []))

        await asyncio.gather(*(one(task) for task in tasks))
        await browser.close()
    for task_id, passed, graded, wall, reason, log in sorted(rows):
        print(f"{'PASS' if passed else 'FAIL'} grade={'ok' if graded else '--'} {wall:5.1f}s {task_id}: {reason}")
        if not graded:
            for line in log:
                print("      " + line[:300])
    ok = sum(1 for row in rows if row[2])
    print(f"TOTAL self-pass {sum(1 for row in rows if row[1])}/{len(rows)}, graded pass {ok}/{len(rows)}, "
          f"false accepts {sum(1 for row in rows if row[1] and not row[2])}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
