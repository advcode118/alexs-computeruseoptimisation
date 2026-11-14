"""Opt-in public-page verification for dev4form, not an agent run or an LLM probe.

Run ``python -m bench.verify_dev4_form``. It drives local headless Chromium
from each task's start page through the form and its submit with a short
Playwright script, then grades the page with the probe's own grader
(grade_observation and evidence_verdict). Negative checks: the right answer
on the start page, and a wrong value on the end page, must both fail. No
model calls.
"""

from __future__ import annotations

import asyncio
import sys

from playwright.async_api import async_playwright

from bench.script_first import collect_page_evidence
from bench.tasks import tasks_for_split
from bench.verify_dev3 import _grade, _real_page

# A plausible wrong value. Claimed on the end page, it must grade FAIL.
WRONG = {
    "dev4_form_cura_appointment": "Your appointment has been cancelled.",
    "dev4_form_ipcalc_broadcast": "192.168.10.255",
    "dev4_form_epoch_timestamp": "1710500400",
    "dev4_form_roman_convert": "MMDCCXLVIIII",
    "dev4_form_lambdatest_input": "Thanks for signing up, we will get back to you shortly.",
    "dev4_form_testmu_radio": "Age : 5 - 15",
    "dev4_form_playground_checkout": "Your order has been cancelled!",
    "dev4_form_playground_enquiry": "Your enquiry could not be sent to the store owner!",
    "dev4_form_autoexercise_contact": "Error! Your details could not be submitted.",
    "dev4_form_giga_percent": "64.50",
    "dev4_form_soup_subtract": "October 6, 2029",
    "dev4_form_aos_contact": "Thank you for shopping with Advantage.",
}

_CONSENT = ".fc-cta-consent"


async def _consent(page) -> None:
    """Dismiss a Google Funding Choices consent dialog when one is showing."""
    try:
        button = page.locator(_CONSENT).first
        await button.wait_for(state="visible", timeout=4000)
        await button.click(timeout=3000)
    except Exception:  # noqa: BLE001 - no dialog this time
        pass


async def _interact(page, task: dict) -> None:
    task_id = task["id"]
    if task_id == "dev4_form_cura_appointment":
        await page.click("#btn-make-appointment")
        await page.fill("#txt-username", "John Doe")
        await page.fill("#txt-password", "ThisIsNotAPassword")
        await page.click("#btn-login")
        await page.locator("#combo_facility").wait_for()
        await page.select_option("#combo_facility", label="Hongkong CURA Healthcare Center")
        await page.check("#chk_hospotal_readmission")
        await page.check("#radio_program_medicaid")
        # The date picker clears a filled value; typed keys stick.
        await page.click("#txt_visit_date")
        await page.keyboard.type("20/05/2030")
        await page.keyboard.press("Escape")
        await page.fill("#txt_comment", "Annual check")
        await page.click("#btn-book-appointment")
        await page.locator("#summary h2").wait_for()
        return
    if task_id == "dev4_form_ipcalc_broadcast":
        await page.fill("input[name=host]", "192.168.10.77")
        await page.fill("input[name=mask1]", "26")
        async with page.expect_navigation():
            await page.click("input[type=submit]")
        return
    if task_id == "dev4_form_epoch_timestamp":
        await _consent(page)
        form = page.locator("#hf")
        for name, value in (("yyyy", "2024"), ("mm", "3"), ("dd", "15"), ("hh", "12"), ("mn", "0"), ("ss", "0")):
            await form.locator(f"input[name={name}]").fill(value)
        await form.locator("select[name=tz]").select_option(label="UTC")
        await form.locator("button[type=submit]").click()
        await page.get_by_text("1710504000").first.wait_for()
        return
    if task_id == "dev4_form_roman_convert":
        await page.fill("#id_number", "2749")
        async with page.expect_navigation():
            await page.click("input[value=Convert]")
        await _consent(page)
        return
    if task_id == "dev4_form_lambdatest_input":
        form = page.locator("#seleniumform")
        for selector, value in (
            ("#name", "Alex Example"), ("#inputEmail4", "alex@example.com"), ("#inputPassword4", "Demo1234"),
            ("#company", "Example Ltd"), ("#websitename", "https://example.com"), ("#inputCity", "Leeds"),
            ("#inputAddress1", "1 Main Street"), ("#inputAddress2", "Flat 2"), ("#inputState", "Yorkshire"),
            ("#inputZip", "LS1 1AA"),
        ):
            await form.locator(selector).fill(value)
        await form.locator("select[name=country]").select_option(label="United Kingdom")
        await form.locator("button[type=submit]").click()
        await page.get_by_text("Thanks for contacting us").first.wait_for()
        return
    if task_id == "dev4_form_testmu_radio":
        await page.check("input[name=gender][value=Female]")
        await page.check("input[name=ageGroup][value='15 - 50']")
        await page.get_by_role("button", name="Get values").click()
        await page.get_by_text("Age : 15 - 50").first.wait_for()
        return
    if task_id == "dev4_form_playground_checkout":
        await page.click("#button-cart")
        await page.wait_for_timeout(1500)
        await page.goto("https://ecommerce-playground.lambdatest.io/index.php?route=checkout/checkout")
        await page.locator("label[for=input-guest]").click()
        for selector, value in (
            ("#input-firstname", "Alex"), ("#input-lastname", "Example"), ("#input-email", "alex@example.com"),
            ("#input-shipping-address-1", "1 Main Street"), ("#input-shipping-city", "Leeds"),
            ("#input-shipping-postcode", "LS1 1AA"),
        ):
            await page.fill(selector, value)
        await page.select_option("#input-shipping-country", label="United Kingdom")
        await page.wait_for_timeout(1500)
        await page.select_option("#input-shipping-zone", label="West Yorkshire")
        await page.click("#button-register")
        await page.get_by_text("guest account information has been saved").wait_for()
        await page.click("#button-shipping-methods")
        await page.locator("#form-shipping-method input[type=radio]").first.check()
        await page.click("#button-shipping-method")
        await page.wait_for_timeout(1500)
        await page.click("#button-payment-methods")
        await page.locator("#form-payment-method input[type=radio]").first.check()
        await page.click("#button-payment-method")
        await page.wait_for_timeout(1500)
        await page.get_by_role("button", name="Confirm Order").click()
        await page.wait_for_url("**checkout/success**")
        return
    if task_id == "dev4_form_playground_enquiry":
        await page.goto("https://ecommerce-playground.lambdatest.io/index.php?route=information/contact")
        await page.fill("#input-name", "Alex Example")
        await page.fill("#input-email", "alex@example.com")
        await page.fill("#input-enquiry", "I would like to ask about delivery times to Leeds.")
        async with page.expect_navigation():
            await page.click("#content input[type=submit]")
        return
    if task_id == "dev4_form_autoexercise_contact":
        await _consent(page)
        await page.click("a[href='/contact_us']")
        await page.wait_for_url("**/contact_us")
        page.once("dialog", lambda dialog: asyncio.ensure_future(dialog.accept()))
        await page.fill("input[name=name]", "Alex Example")
        await page.fill("input[name=email]", "alex@example.com")
        await page.fill("input[name=subject]", "Order question")
        await page.fill("textarea[name=message]", "Where is my order? It has not arrived yet.")
        await page.click("input[name=submit]")
        await page.get_by_text("Your details have been submitted successfully").first.wait_for()
        return
    if task_id == "dev4_form_giga_percent":
        await _consent(page)
        # The mode radio swaps which number fields are shown.
        await page.check("#op4")
        shown = page.locator("#calculator input[type=number]:visible")
        await shown.nth(0).fill("17.5")
        await shown.nth(1).fill("368")
        await page.locator("#calculator button[type=submit]").first.click()
        await page.get_by_text("64.40").first.wait_for()
        return
    if task_id == "dev4_form_soup_subtract":
        await _consent(page)
        await page.fill("#dateInputM", "1")
        await page.fill("#dateInputD", "15")
        await page.fill("#dateInputY", "2030")
        await page.select_option("select[name=operator]", index=1)
        await page.fill("#days", "100")
        await page.click("#calculateButton")
        await page.get_by_text("October 7, 2029").first.wait_for()
        return
    if task_id == "dev4_form_aos_contact":
        await page.get_by_text("CONTACT US", exact=True).first.click()
        await page.locator("select[name=categoryListboxContactUs]").wait_for()
        await page.select_option("select[name=categoryListboxContactUs]", label="Laptops")
        # The product list loads after the category; sending before that does nothing.
        await page.wait_for_timeout(1500)
        await page.fill("input[name=emailContactUs]", "alex@example.com")
        await page.fill("textarea[name=subjectTextareaContactUs]", "Battery life question")
        await page.click("#send_btn")
        await page.locator(".successMessage:visible").first.wait_for()
        return
    raise AssertionError(f"no reproducer for {task_id}")


async def check(browser, task: dict) -> tuple:
    context = await browser.new_context(viewport={"width": 1366, "height": 900})
    page = await context.new_page()
    page.set_default_timeout(45000)
    try:
        start = await page.goto(task["start_url"], wait_until="domcontentloaded")
        await page.wait_for_timeout(2500)
        start_status = await _real_page(page, start)
        start_evidence = await collect_page_evidence(page)
        answer = task["expected_answer"]
        assert answer not in start_evidence.text, (task["id"], "answer on the start page")
        assert not _grade(task, start_evidence, answer), (task["id"], "start page passed")
        await _interact(page, task)
        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(1000)
        await _real_page(page)
        evidence = await collect_page_evidence(page)
        assert answer in evidence.text, (task["id"], "answer absent from runner evidence", evidence.url, evidence.text[:300])
        assert _grade(task, evidence, answer), (task["id"], "grader rejected the end state", evidence.url)
        wrong = WRONG[task["id"]]
        assert not _grade(task, evidence, wrong), (task["id"], "wrong value accepted", wrong)
        return task["id"], start_status, evidence.url, "PASS", "FAIL", "FAIL"
    finally:
        await context.close()


async def verify(ids: list[str]) -> int:
    tasks = [task for task in tasks_for_split("dev4form") if not ids or task["id"] in ids]
    failures = 0
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        semaphore = asyncio.Semaphore(4)

        async def guarded(task):
            nonlocal failures
            async with semaphore:
                try:
                    row = await check(browser, task)
                    print("OK  " + " | ".join(str(item) for item in row), flush=True)
                except Exception as error:  # noqa: BLE001 - report and continue
                    failures += 1
                    print(f"BAD {task['id']}: {type(error).__name__}: {str(error)[:400]}", flush=True)

        try:
            await asyncio.gather(*(guarded(task) for task in tasks))
        finally:
            await browser.close()
    print(f"TOTAL {len(tasks) - failures}/{len(tasks)} passed", flush=True)
    return failures


if __name__ == "__main__":
    sys.exit(1 if asyncio.run(verify(sys.argv[1:])) else 0)
