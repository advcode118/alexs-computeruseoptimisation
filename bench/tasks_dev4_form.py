"""dev4form: twelve fresh public form tasks for the form specialist. Not a scored set.

Each task fills a real form (text, number, select, radio, checkbox, date,
dialogs, logins, forms a click or two from the start page, several forms on
one page) and reports the result text. Answers are literal page text that
only appears after the submit, and end markers are judge-only, as in dev3.
No host here is in used_hosts.txt. Live checks are in bench/verify_dev4_form.py.
"""

from __future__ import annotations


def _task(task_id, description, start_url, expected, host, url_contains, *, path_suffix="", deny=()):
    markers = {"host": host, "url_contains": url_contains}
    if path_suffix:
        markers["path_suffix"] = path_suffix
    markers["deny"] = ["/search", *deny]
    markers["answer_in_text"] = expected
    return {
        "id": task_id,
        "description": description,
        "start_url": start_url,
        "expected_answer": expected,
        "check_url_contains": url_contains,
        "end_markers": markers,
    }


DEV4_FORM_TASKS = [
    _task(
        "dev4_form_cura_appointment",
        "On the CURA Healthcare demo, log in with the demo account shown on the login page, then book an appointment "
        "at the Hongkong CURA Healthcare Center with hospital readmission ticked, the Medicaid healthcare program, "
        "visit date 20/05/2030 and the comment Annual check. Report the sentence that introduces the booked "
        "appointment details on the confirmation page.",
        "https://katalon-demo-cura.herokuapp.com/",
        "Please be informed that your appointment has been booked as following:",
        "katalon-demo-cura.herokuapp.com", "appointment.php",
    ),
    _task(
        "dev4_form_ipcalc_broadcast",
        "Use the ipcalc web calculator to work out the subnet for host address 192.168.10.77 with netmask 26, "
        "and report the broadcast address it shows.",
        "https://jodies.de/ipcalc",
        "192.168.10.127", "jodies.de", "host=192.168.10.77",
    ),
    _task(
        "dev4_form_epoch_timestamp",
        "On Epoch Converter, use the human date to timestamp form to convert 15 March 2024 at 12:00:00 UTC, "
        "and report the epoch timestamp it gives.",
        "https://www.epochconverter.com/",
        "1710504000", "www.epochconverter.com", "epochconverter.com/",
    ),
    _task(
        "dev4_form_roman_convert",
        "Use miniwebtool's Roman numerals converter to convert the number 2749, and report the Roman numeral "
        "it gives.",
        "https://miniwebtool.com/roman-numerals-converter/",
        "MMDCCXLIX", "miniwebtool.com", "number=2749",
    ),
    _task(
        "dev4_form_lambdatest_input",
        "Fill in the TestMu AI (formerly LambdaTest) Selenium Playground input form demo with name Alex Example, email "
        "alex@example.com, password Demo1234, company Example Ltd, website https://example.com, country "
        "United Kingdom, city Leeds, address line 1 1 Main Street, address line 2 Flat 2, state Yorkshire and "
        "zip code LS1 1AA. Submit it and report the success message.",
        "https://www.testmuai.com/selenium-playground/input-form-demo/",
        "Thanks for contacting us, we will get back to you shortly.",
        "www.testmuai.com", "/input-form-demo",
    ),
    _task(
        "dev4_form_testmu_radio",
        "On the TestMu AI Selenium Playground radio button demo, in the part that asks for both sex and age "
        "group, choose Female and the 15 to 50 age group, get the values, and report the age group line it "
        "prints.",
        "https://www.testmuai.com/selenium-playground/radiobutton-demo/",
        "Age : 15 - 50", "www.testmuai.com", "/radiobutton-demo",
    ),
    _task(
        "dev4_form_playground_checkout",
        "On the LambdaTest e-commerce playground store, open the iPhone product page, add it to the cart, and check "
        "out as a guest with first name Alex, last name Example, email alex@example.com, address 1 Main Street, "
        "city Leeds, post code LS1 1AA, country United Kingdom and region West Yorkshire, using the flat rate "
        "shipping and any available payment method. Confirm the order and report the heading of the page that "
        "says it was placed.",
        "https://ecommerce-playground.lambdatest.io/index.php?route=product/product&product_id=40",
        "Your order has been placed!", "ecommerce-playground.lambdatest.io", "checkout/success",
    ),
    _task(
        "dev4_form_playground_enquiry",
        "On the LambdaTest e-commerce playground store, send an enquiry through the store's contact page with "
        "name Alex Example, email alex@example.com, and an enquiry asking about delivery times to Leeds. "
        "Report the confirmation message.",
        "https://ecommerce-playground.lambdatest.io/",
        "Your enquiry has been successfully sent to the store owner!",
        "ecommerce-playground.lambdatest.io", "information/contact.success",
    ),
    _task(
        "dev4_form_autoexercise_contact",
        "On Automation Exercise, send the Contact Us form with name Alex Example, email alex@example.com, "
        "subject Order question and a short message asking where the order is, confirm the submission, and "
        "report the success message.",
        "https://automationexercise.com/",
        "Success! Your details have been submitted successfully.",
        "automationexercise.com", "/contact_us",
    ),
    _task(
        "dev4_form_giga_percent",
        "On GigaCalculator's percentage calculator, choose the mode that works out what X% of Y is, calculate "
        "17.5% of 368, and report the result shown.",
        "https://www.gigacalculator.com/calculators/percentage-calculator.php",
        "64.40", "www.gigacalculator.com", "percentage-calculator.php",
    ),
    _task(
        "dev4_form_soup_subtract",
        "On Calculator Soup's date calculator, start from 15 January 2030, subtract 100 days, calculate, and "
        "report the resulting date written out with the month name.",
        "https://www.calculatorsoup.com/calculators/time/date-day.php",
        "October 7, 2029", "www.calculatorsoup.com", "/date-day.php",
    ),
    _task(
        "dev4_form_aos_contact",
        "On the Advantage Online Shopping demo, send the Contact Us form about the Laptops category with "
        "email alex@example.com and the subject Battery life question. Report the thank-you message.",
        "https://www.advantageonlineshopping.com/",
        "Thank you for contacting Advantage support.", "www.advantageonlineshopping.com",
        "advantageonlineshopping.com/",
    ),
]

DEV4_FORM_TASK_IDS = tuple(task["id"] for task in DEV4_FORM_TASKS)
