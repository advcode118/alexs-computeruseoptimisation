# Planner gate audit

Reproduce offline: `python tools/gate_audit.py --output docs/results/planner_gate_audit.md`.
Counts retain recorded duplicates. Each step is audited independently (terminal state is reset between audit steps only). Saved HTML uses the real executor, including runtime evaluate interception; missing pages use conservative lexical decisions. Parse rejections are not gate decisions. This is not proof of zero live regressions.

| Source/task set | Scripts | Steps | DOM | Lexical | Parse rejected | Blocked | Reasons |
|---|---:|---:|---:|---:|---:|---:|---|
| docs/results/extdev_control_20261117 | 67 | 95 | 0 | 95 | 23 | 0 |  |
| docs/results/extdev_gpt62_20261117 | 11 | 13 | 0 | 13 | 6 | 0 |  |
| docs/results/form_specialist_20261114 | 77 | 271 | 0 | 271 | 12 | 23 | needs approval: commit control: 18; needs approval: commit control in evaluate: 1; needs approval: form submission (POST or unknown method): 4 |
| docs/results/heldout2_tip2_20261113 | 92 | 227 | 0 | 227 | 9 | 5 | needs approval: commit control: 2; needs approval: commit control in evaluate: 1; needs approval: form submission (POST or unknown method): 2 |
| docs/results/strategy_spa_20261114 | 88 | 168 | 0 | 168 | 7 | 4 | needs approval: commit control: 4 |
| tests/fixtures | 28 | 75 | 11 | 64 | 3 | 2 | needs approval: commit control: 1; needs approval: form submission (POST or unknown method): 1 |
| TOTAL | 363 | 849 | 11 | 838 | 60 | 34 | |

## Blocked steps
docs/results/form_specialist_20261114/dev3_off.jsonl:1.scripts[0] (dev3_form_demoqa_textbox), line 4: needs approval: commit control
  cu.click('Submit')
docs/results/form_specialist_20261114/dev3_off.jsonl:1.scripts[1] (dev3_form_demoqa_textbox), line 3: needs approval: commit control
  cu.click('Submit')
docs/results/form_specialist_20261114/dev3_off.jsonl:2.scripts[0] (dev3_form_demoqa_practice), line 6: needs approval: commit control
  cu.click('Submit')
docs/results/form_specialist_20261114/dev3_off.jsonl:3.scripts[0] (dev3_form_formy_complete), line 5: needs approval: commit control
  cu.click('Submit')
docs/results/form_specialist_20261114/dev3_off.jsonl:4.scripts[2] (dev3_form_blazedemo_purchase), line 2: needs approval: form submission (POST or unknown method)
  page.evaluate(() => { const f = document.querySelector('form'); f.querySelector('[name="fromPort"]').value = 'Boston'; f.querySelector('[name="toPort"]').value = 'London'; f.submit(); })
docs/results/form_specialist_20261114/dev3_off.jsonl:4.scripts[2] (dev3_form_blazedemo_purchase), line 4: needs approval: form submission (POST or unknown method)
  page.evaluate(() => { const f = document.querySelector('form'); const v = {inputName:'Alex Example', address:'1 Main Street', city:'Boston', state:'MA', zipCode:'02101', creditCardNumber:'4111111111111111', creditCardMonth:'12', creditCardYear:'2028', nameOnCard:'Alex Example'}; for (const [n,x] of Object.entries(v)) { const e=f.querySelector(`[name="${n}"]`); if(e) e.value=x; } f.submit(); })
docs/results/form_specialist_20261114/dev3_off.jsonl:5.scripts[0] (dev3_form_aito_contact), line 7: needs approval: commit control
  cu.click('Submit')
docs/results/form_specialist_20261114/dev3_off.jsonl:5.scripts[1] (dev3_form_aito_contact), line 6: needs approval: commit control
  cu.click('Submit')
docs/results/form_specialist_20261114/dev3_off.jsonl:5.scripts[2] (dev3_form_aito_contact), line 6: needs approval: commit control
  cu.click('Submit')
docs/results/form_specialist_20261114/dev3_off.jsonl:6.scripts[0] (dev3_form_guru99_register), line 7: needs approval: commit control
  page.locator('input[name="submit"]').click()
docs/results/form_specialist_20261114/dev4form_off.jsonl:1.scripts[1] (dev4_form_cura_appointment), line 7: needs approval: commit control
  cu.click('Book Appointment')
docs/results/form_specialist_20261114/dev4form_off.jsonl:1.scripts[2] (dev4_form_cura_appointment), line 9: needs approval: commit control
  cu.click('Book Appointment')
docs/results/form_specialist_20261114/dev4form_off.jsonl:4.scripts[1] (dev4_form_roman_convert), line 2: needs approval: form submission (POST or unknown method)
  page.evaluate(() => { const inputs = [...document.querySelectorAll('input')]; const field = inputs.find(x => x.type === 'number' || /number/i.test(x.name + ' ' + x.id + ' ' + x.placeholder)) || inputs.find(x => x.type !== 'hidden' && x.type !== 'submit'); if (field) { field.value = '2749'; field.dispatchEvent(new Event('input', {bubbles:true})); field.dispatchEvent(new Event('change', {bubbles:true})); } const button = [...document.querySelectorAll('button, input[type="submit"]')].find(x => /convert/i.test(x.innerText || x.value || '')); if (button) button.click(); else if (field?.form) field.form.requestSubmit(); })
docs/results/form_specialist_20261114/dev4form_off.jsonl:8.scripts[0] (dev4_form_playground_enquiry), line 5: needs approval: commit control
  cu.click('Submit')
docs/results/form_specialist_20261114/dev4form_off.jsonl:9.scripts[0] (dev4_form_autoexercise_contact), line 6: needs approval: commit control
  cu.click('Submit')
docs/results/form_specialist_20261114/dev4form_off.jsonl:9.scripts[1] (dev4_form_autoexercise_contact), line 2: needs approval: commit control
  cu.click('Submit')
docs/results/form_specialist_20261114/dev4form_off.jsonl:9.scripts[2] (dev4_form_autoexercise_contact), line 1: needs approval: commit control
  cu.click('Submit')
docs/results/form_specialist_20261114/dev4form_off.jsonl:12.scripts[1] (dev4_form_aos_contact), line 3: needs approval: commit control in evaluate
  page.evaluate(() => { const s=[...document.querySelectorAll('select')].find(x=>[...x.options].some(o=>o.textContent.trim()==='Laptops')); if(s){s.value=[...s.options].find(o=>o.textContent.trim()==='Laptops').value;s.dispatchEvent(new Event('change',{bubbles:true}));} const e=[...document.querySelectorAll('input')].find(x=>/email/i.test(x.placeholder||x.name||x.id)); if(e){e.value='alex@example.com';e.dispatchEvent(new Event('input',{bubbles:true}));} const subj=[...document.querySelectorAll('textarea,input')].find(x=>/subject/i.test(x.placeholder||x.name||x.id)); if(subj){subj.value='Battery life question';subj.dispatchEvent(new Event('input',{bubbles:true}));} const b=[...document.querySelectorAll('button,input[type=submit]')].find(x=>/send/i.test(x.innerText||x.value||'')); if(b)b.click(); })
docs/results/form_specialist_20261114/dev4form_on.jsonl:1.scripts[0] (dev4_form_cura_appointment), line 7: needs approval: commit control
  cu.click('Book Appointment')
docs/results/form_specialist_20261114/held-out_off.jsonl:1.scripts[0] (ho_form_selenium_received), line 2: needs approval: commit control
  cu.click('Submit')
docs/results/form_specialist_20261114/held-out_off.jsonl:4.scripts[0] (ho_form_testpages_comments), line 2: needs approval: commit control
  cu.click('Submit')
docs/results/form_specialist_20261114/held-out_off.jsonl:6.scripts[0] (ho_form_httpbin_phone), line 3: needs approval: commit control
  page.getByRole('button', {name:'Submit'}).click()
docs/results/form_specialist_20261114/held-out_on.jsonl:5.scripts[0] (ho_form_w3schools_action), line 2: needs approval: form submission (POST or unknown method)
  page.evaluate(() => { const forms=[...document.forms]; const f=forms.find(x=>x.querySelector('input[type="submit"],button[type="submit"]')); if(f) f.requestSubmit(); })
docs/results/heldout2_tip2_20261113/probe_20261113_013521.jsonl:19.scripts[0] (ho2_form_expand_ticket), line 6: needs approval: commit control
  cu.click('Submit')
docs/results/heldout2_tip2_20261113/probe_20261113_015006.jsonl:18.scripts[1] (ho2_search_flask_blueprints), line 2: needs approval: form submission (POST or unknown method)
  page.evaluate(() => { const f = document.querySelector('form[role="search"]') || document.querySelector('form'); const input = document.querySelector('input[name="q"]'); input.value = 'blueprints'; f.requestSubmit(); })
docs/results/heldout2_tip2_20261113/probe_20261113_015006.jsonl:19.scripts[1] (ho2_form_expand_ticket), line 2: needs approval: commit control in evaluate
  page.evaluate(() => { const controls = [...document.querySelectorAll('input, select')]; for (const el of controls) { const label = (el.labels ? [...el.labels].map(x => x.innerText).join(' ') : '') + ' ' + el.name + ' ' + el.id + ' ' + el.placeholder; if (/contact name/i.test(label)) el.value = 'Alex Example'; else if (/contact number/i.test(label)) el.value = '012-3456789'; else if (/pickup|date/i.test(label)) el.value = el.type === 'date' ? '2030-01-15' : '15 January 2030'; else if (/payment/i.test(label) && el.tagName === 'SELECT') { const option = [...el.options].find(o => /card/i.test(o.text)); if (option) el.value = option.value; } } const submit = [...document.querySelectorAll('button, input[type=submit]')].find(b => /submit/i.test(b.innerText || b.value)); if (submit) submit.click(); })
docs/results/heldout2_tip2_20261113/probe_20261113_015231.jsonl:19.scripts[1] (ho2_form_expand_ticket), line 3: needs approval: commit control
  page.getByRole('button', {name:'Submit'}).click()
docs/results/heldout2_tip2_20261113/probe_20261113_015231.jsonl:20.scripts[1] (ho2_form_calculator_sum), line 2: needs approval: form submission (POST or unknown method)
  page.evaluate(() => { const form = document.querySelector('form'); const inputs = [...form.querySelectorAll('input')].filter(x => x.type === 'text' || x.type === 'number'); inputs[0].value = '17'; inputs[1].value = '25'; const select = form.querySelector('select'); const option = [...select.options].find(o => /add|addition|\+/.test((o.text + ' ' + o.value).toLowerCase())); select.value = option.value; form.requestSubmit(); })
docs/results/strategy_spa_20261114/dev4spa_off_final.jsonl:3.scripts[0] (dev4spa_js_cypress_todo_left), line 2: needs approval: commit control
  cu.click('Pay electric bill')
docs/results/strategy_spa_20261114/dev4spa_off_final.jsonl:3.scripts[2] (dev4spa_js_cypress_todo_left), line 1: needs approval: commit control
  page.getByText('Pay electric bill').click()
docs/results/strategy_spa_20261114/dev4spa_off_first.jsonl:3.scripts[0] (dev4spa_js_cypress_todo_left), line 2: needs approval: commit control
  cu.click('Pay electric bill')
docs/results/strategy_spa_20261114/dev4spa_on_first.jsonl:3.scripts[0] (dev4spa_js_cypress_todo_left), line 2: needs approval: commit control
  cu.click('Pay electric bill')
tests/fixtures/script_grammar.json[17] (form evaluate submission), line 2: needs approval: form submission (POST or unknown method)
  page.evaluate(() => document.querySelector("form").requestSubmit())
tests/fixtures/script_grammar.json[20] (getByPlaceholder fill + button submit), line 3: needs approval: commit control
  page.getByRole("button", {name: "Subscribe"}).click()

## Parse rejections (not gate decisions)
docs/results/extdev_control_20261117/raw/probe_20261117_012232.jsonl:3.scripts[1] (extdev_filter_greatamerica_thrill): line 1: expected a string; use page.locator("css").click() or page.evaluate(() => { ... }); for an object return, wrap it in page.evaluate(() => ({...}))
docs/results/extdev_control_20261117/raw/probe_20261117_012232.jsonl:11.scripts[0] (extdev_spa_dota_dlc_cart): fetch( is not part of this script; use page.locator("css").click() or page.evaluate(() => { ... }); for an object return, wrap it in page.evaluate(() => ({...}))
docs/results/extdev_control_20261117/raw/probe_20261117_012232.jsonl:11.scripts[1] (extdev_spa_dota_dlc_cart): line 2: expected a string literal; use page.locator("css").click() or page.evaluate(() => { ... }); for an object return, wrap it in page.evaluate(() => ({...}))
docs/results/extdev_control_20261117/raw/probe_20261117_012232.jsonl:15.scripts[0] (extdev_filter_booking_times_square): line 2: expected a literal option; use page.locator("css").click() or page.evaluate(() => { ... }); for an object return, wrap it in page.evaluate(() => ({...}))
docs/results/extdev_control_20261117/raw/probe_20261117_012232.jsonl:20.scripts[1] (extdev_filter_frontiercity_family): fetch( is not part of this script; use page.locator("css").click() or page.evaluate(() => { ... }); for an object return, wrap it in page.evaluate(() => ({...}))
docs/results/extdev_control_20261117/raw/probe_20261117_012232.jsonl:31.scripts[0] (extdev_value_icse_2004_chair): line 2: expected a literal option; use page.locator("css").click() or page.evaluate(() => { ... }); for an object return, wrap it in page.evaluate(() => ({...}))
docs/results/extdev_control_20261117/raw/probe_20261117_012232.jsonl:35.scripts[0] (extdev_value_icse_duplicate_statement): line 2: expected a literal option; use page.locator("css").click() or page.evaluate(() => { ... }); for an object return, wrap it in page.evaluate(() => ({...}))
docs/results/extdev_control_20261117/raw/probe_20261117_012232.jsonl:36.scripts[0] (extdev_value_icse_duplicate_statement): line 2: expected a literal option; use page.locator("css").click() or page.evaluate(() => { ... }); for an object return, wrap it in page.evaluate(() => ({...}))
docs/results/extdev_control_20261117/raw/probe_20261117_012232.jsonl:39.scripts[0] (extdev_value_icse_2002_chairs): line 2: expected a literal option; use page.locator("css").click() or page.evaluate(() => { ... }); for an object return, wrap it in page.evaluate(() => ({...}))
docs/results/extdev_control_20261117/raw/probe_20261117_012232.jsonl:43.scripts[0] (extdev_value_rovio_anniversary): fetch( is not part of this script; use page.locator("css").click() or page.evaluate(() => { ... }); for an object return, wrap it in page.evaluate(() => ({...}))
docs/results/extdev_control_20261117/raw/probe_20261117_012232.jsonl:43.scripts[1] (extdev_value_rovio_anniversary): line 2: expected a literal option; use page.locator("css").click() or page.evaluate(() => { ... }); for an object return, wrap it in page.evaluate(() => ({...}))
docs/results/extdev_control_20261117/raw/probe_20261117_012232.jsonl:44.scripts[0] (extdev_value_rovio_anniversary): fetch( is not part of this script; use page.locator("css").click() or page.evaluate(() => { ... }); for an object return, wrap it in page.evaluate(() => ({...}))
docs/results/extdev_control_20261117/raw/probe_20261117_012232.jsonl:44.scripts[1] (extdev_value_rovio_anniversary): line 2: expected a literal option; use page.locator("css").click() or page.evaluate(() => { ... }); for an object return, wrap it in page.evaluate(() => ({...}))
docs/results/extdev_control_20261117/raw/probe_20261117_012232.jsonl:47.scripts[0] (extdev_value_apec_tourism_actions): line 1: expected a string; use page.locator("css").click() or page.evaluate(() => { ... }); for an object return, wrap it in page.evaluate(() => ({...}))
docs/results/extdev_control_20261117/raw/probe_20261117_012232.jsonl:47.scripts[1] (extdev_value_apec_tourism_actions): line 2: unsupported locator action filter; use page.locator("css").click() or page.evaluate(() => { ... }); for an object return, wrap it in page.evaluate(() => ({...}))
docs/results/extdev_control_20261117/raw/probe_20261117_012232.jsonl:48.scripts[0] (extdev_value_apec_tourism_actions): fetch( is not part of this script; use page.locator("css").click() or page.evaluate(() => { ... }); for an object return, wrap it in page.evaluate(() => ({...}))
docs/results/extdev_control_20261117/raw/probe_20261117_012232.jsonl:51.scripts[1] (extdev_value_apec_peru_arrivals): line 3: expected a literal option; use page.locator("css").click() or page.evaluate(() => { ... }); for an object return, wrap it in page.evaluate(() => ({...}))
docs/results/extdev_control_20261117/raw/probe_20261117_012232.jsonl:52.scripts[0] (extdev_value_apec_peru_arrivals): fetch( is not part of this script; use page.locator("css").click() or page.evaluate(() => { ... }); for an object return, wrap it in page.evaluate(() => ({...}))
docs/results/extdev_control_20261117/raw/probe_20261117_012232.jsonl:55.scripts[1] (extdev_value_apec_ministers_chair): fetch( is not part of this script; use page.locator("css").click() or page.evaluate(() => { ... }); for an object return, wrap it in page.evaluate(() => ({...}))
docs/results/extdev_control_20261117/raw/probe_20261117_012232.jsonl:56.scripts[1] (extdev_value_apec_ministers_chair): line 2: expected a literal option; use page.locator("css").click() or page.evaluate(() => { ... }); for an object return, wrap it in page.evaluate(() => ({...}))
docs/results/extdev_control_20261117/raw/probe_20261117_012232.jsonl:60.scripts[0] (extdev_search_booking_la_filters): line 2: unsupported locator action isVisible; use page.locator("css").click() or page.evaluate(() => { ... }); for an object return, wrap it in page.evaluate(() => ({...}))
docs/results/extdev_control_20261117/raw/probe_20261117_012232.jsonl:64.scripts[0] (extdev_value_hf_first_user_message): line 2: unsupported locator action isVisible; use page.locator("css").click() or page.evaluate(() => { ... }); for an object return, wrap it in page.evaluate(() => ({...}))
docs/results/extdev_control_20261117/raw/probe_20261117_012232.jsonl:71.scripts[0] (extdev_nav_ronaldo_world_cup_stats): line 2: expected '.'; use page.locator("css").click() or page.evaluate(() => { ... }); for an object return, wrap it in page.evaluate(() => ({...}))
docs/results/extdev_gpt62_20261117/gpt-6.2-astra/probe_20261117_184010.jsonl:1.scripts[1] (extdev_filter_greatamerica_thrill): line 2: expected a literal option; use page.locator("css").click() or page.evaluate(() => { ... }); for an object return, wrap it in page.evaluate(() => ({...}))
docs/results/extdev_gpt62_20261117/gpt-6.2-astra/probe_20261117_184010.jsonl:2.scripts[0] (extdev_spa_dota_dlc_cart): line 2: expected a string literal; use page.locator("css").click() or page.evaluate(() => { ... }); for an object return, wrap it in page.evaluate(() => ({...}))
docs/results/extdev_gpt62_20261117/gpt-6.2-astra/probe_20261117_184010.jsonl:3.scripts[1] (extdev_filter_frontiercity_family): fetch( is not part of this script; use page.locator("css").click() or page.evaluate(() => { ... }); for an object return, wrap it in page.evaluate(() => ({...}))
docs/results/extdev_gpt62_20261117/gpt-6.2-astra/probe_20261117_184010.jsonl:5.scripts[0] (extdev_value_icse_duplicate_statement): line 2: expected a literal option; use page.locator("css").click() or page.evaluate(() => { ... }); for an object return, wrap it in page.evaluate(() => ({...}))
docs/results/extdev_gpt62_20261117/gpt-6.2-astra/probe_20261117_184010.jsonl:6.scripts[0] (extdev_value_rovio_anniversary): fetch( is not part of this script; use page.locator("css").click() or page.evaluate(() => { ... }); for an object return, wrap it in page.evaluate(() => ({...}))
docs/results/extdev_gpt62_20261117/gpt-6.2-astra/probe_20261117_184010.jsonl:6.scripts[1] (extdev_value_rovio_anniversary): line 2: expected a literal option; use page.locator("css").click() or page.evaluate(() => { ... }); for an object return, wrap it in page.evaluate(() => ({...}))
docs/results/form_specialist_20261114/dev3_off.jsonl:4.scripts[0] (dev3_form_blazedemo_purchase): line 2: expected a string literal; use page.locator("css").click() or page.evaluate(() => { ... }); for an object return, wrap it in page.evaluate(() => ({...}))
docs/results/form_specialist_20261114/dev3_off.jsonl:4.scripts[1] (dev3_form_blazedemo_purchase): script has more than 12 actions
docs/results/form_specialist_20261114/dev4form_off.jsonl:4.scripts[0] (dev4_form_roman_convert): line 3: expected a literal option; use page.locator("css").click() or page.evaluate(() => { ... }); for an object return, wrap it in page.evaluate(() => ({...}))
docs/results/form_specialist_20261114/dev4form_off.jsonl:7.scripts[0] (dev4_form_playground_checkout): line 2: expected a literal option; use page.locator("css").click() or page.evaluate(() => { ... }); for an object return, wrap it in page.evaluate(() => ({...}))
docs/results/form_specialist_20261114/dev4form_off.jsonl:7.scripts[1] (dev4_form_playground_checkout): script is longer than 2000 characters
docs/results/form_specialist_20261114/dev4form_off.jsonl:7.scripts[2] (dev4_form_playground_checkout): line 3: expected a literal option; use page.locator("css").click() or page.evaluate(() => { ... }); for an object return, wrap it in page.evaluate(() => ({...}))
docs/results/form_specialist_20261114/dev4form_off.jsonl:12.scripts[0] (dev4_form_aos_contact): line 3: expected a string literal; use page.locator("css").click() or page.evaluate(() => { ... }); for an object return, wrap it in page.evaluate(() => ({...}))
docs/results/form_specialist_20261114/dev4form_off.jsonl:12.scripts[2] (dev4_form_aos_contact): line 1: expected a string literal; use page.locator("css").click() or page.evaluate(() => { ... }); for an object return, wrap it in page.evaluate(() => ({...}))
docs/results/form_specialist_20261114/dev4form_on.jsonl:7.scripts[0] (dev4_form_playground_checkout): line 13: cu.getbylabel is not a helper
docs/results/form_specialist_20261114/held-out_off.jsonl:2.scripts[0] (ho_form_internet_secure): line 2: expected 'page'; use page.locator("css").click() or page.evaluate(() => { ... }); for an object return, wrap it in page.evaluate(() => ({...}))
docs/results/form_specialist_20261114/held-out_off.jsonl:5.scripts[0] (ho_form_w3schools_action): line 2: expected 'page'; use page.locator("css").click() or page.evaluate(() => { ... }); for an object return, wrap it in page.evaluate(() => ({...}))
docs/results/form_specialist_20261114/heldout2_on.jsonl:2.scripts[0] (ho2_form_calculator_sum): line 4: expected a string literal; use page.locator("css").click() or page.evaluate(() => { ... }); for an object return, wrap it in page.evaluate(() => ({...}))
docs/results/heldout2_tip2_20261113/probe_20261113_013521.jsonl:17.scripts[0] (ho2_search_sphinx_toctree): line 4: expected a literal option; use page.locator("css").click() or page.evaluate(() => { ... }); for an object return, wrap it in page.evaluate(() => ({...}))
docs/results/heldout2_tip2_20261113/probe_20261113_013521.jsonl:19.scripts[1] (ho2_form_expand_ticket): line 5: expected a string literal; use page.locator("css").click() or page.evaluate(() => { ... }); for an object return, wrap it in page.evaluate(() => ({...}))
docs/results/heldout2_tip2_20261113/probe_20261113_015006.jsonl:7.scripts[0] (ho2_nav_curl_manual): line 2: expected a literal option; use page.locator("css").click() or page.evaluate(() => { ... }); for an object return, wrap it in page.evaluate(() => ({...}))
docs/results/heldout2_tip2_20261113/probe_20261113_015006.jsonl:19.scripts[0] (ho2_form_expand_ticket): line 5: expected a string literal; use page.locator("css").click() or page.evaluate(() => { ... }); for an object return, wrap it in page.evaluate(() => ({...}))
docs/results/heldout2_tip2_20261113/probe_20261113_015006.jsonl:20.scripts[0] (ho2_form_calculator_sum): line 4: expected a string literal; use page.locator("css").click() or page.evaluate(() => { ... }); for an object return, wrap it in page.evaluate(() => ({...}))
docs/results/heldout2_tip2_20261113/probe_20261113_015006.jsonl:20.scripts[1] (ho2_form_calculator_sum): line 4: expected a string literal; use page.locator("css").click() or page.evaluate(() => { ... }); for an object return, wrap it in page.evaluate(() => ({...}))
docs/results/heldout2_tip2_20261113/probe_20261113_015231.jsonl:5.scripts[0] (ho2_nav_nginx_beginner): line 2: expected a literal option; use page.locator("css").click() or page.evaluate(() => { ... }); for an object return, wrap it in page.evaluate(() => ({...}))
docs/results/heldout2_tip2_20261113/probe_20261113_015231.jsonl:19.scripts[0] (ho2_form_expand_ticket): line 5: expected a string literal; use page.locator("css").click() or page.evaluate(() => { ... }); for an object return, wrap it in page.evaluate(() => ({...}))
docs/results/heldout2_tip2_20261113/probe_20261113_015231.jsonl:20.scripts[0] (ho2_form_calculator_sum): line 4: expected a string literal; use page.locator("css").click() or page.evaluate(() => { ... }); for an object return, wrap it in page.evaluate(() => ({...}))
docs/results/strategy_spa_20261114/dev4spa_off_final.jsonl:1.scripts[0] (dev4spa_spa_deps_react_dependency): line 2: expected a literal option; use page.locator("css").click() or page.evaluate(() => { ... }); for an object return, wrap it in page.evaluate(() => ({...}))
docs/results/strategy_spa_20261114/dev4spa_off_final.jsonl:3.scripts[1] (dev4spa_js_cypress_todo_left): line 1: empty name
docs/results/strategy_spa_20261114/dev4spa_off_final.jsonl:5.scripts[0] (dev4spa_js_htmx_toyota_models): line 2: expected a string literal; use page.locator("css").click() or page.evaluate(() => { ... }); for an object return, wrap it in page.evaluate(() => ({...}))
docs/results/strategy_spa_20261114/dev4spa_off_first.jsonl:3.scripts[1] (dev4spa_js_cypress_todo_left): line 1: unsupported locator action locator; use page.locator("css").click() or page.evaluate(() => { ... }); for an object return, wrap it in page.evaluate(() => ({...}))
docs/results/strategy_spa_20261114/dev4spa_off_first.jsonl:5.scripts[0] (dev4spa_js_htmx_toyota_models): line 2: expected a string literal; use page.locator("css").click() or page.evaluate(() => { ... }); for an object return, wrap it in page.evaluate(() => ({...}))
docs/results/strategy_spa_20261114/dev4spa_off_first.jsonl:5.scripts[1] (dev4spa_js_htmx_toyota_models): line 2: expected a string literal; use page.locator("css").click() or page.evaluate(() => { ... }); for an object return, wrap it in page.evaluate(() => ({...}))
docs/results/strategy_spa_20261114/dev4spa_off_first.jsonl:12.scripts[1] (dev4spa_js_shoelace_advanced): line 1: cu.click has an extra argument
tests/fixtures/script_grammar.json[11] (const assignment await): line 2: expected 'page'; use page.locator("css").click() or page.evaluate(() => { ... }); for an object return, wrap it in page.evaluate(() => ({...}))
tests/fixtures/script_grammar.json[12] (top-level return object): line 2: top-level return is not supported; use page.locator("css").click() or page.evaluate(() => { ... }); for an object return, wrap it in page.evaluate(() => ({...}))
tests/fixtures/script_grammar.json[23] (locator chained filter): line 2: unsupported locator action filter; use page.locator("css").click() or page.evaluate(() => { ... }); for an object return, wrap it in page.evaluate(() => ({...}))

## Replay failures (remaining steps lexical)
None

## Unreadable inputs
None
