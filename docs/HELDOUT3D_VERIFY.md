# Heldout3d public-page verification

Verified 2026-11-13 02:40 UTC with local headless Chromium.

This is page/marker validation, not an agent benchmark result. No LLM API calls or bench probes were run.
Mix: 10 multi-step navigation, 10 value reports, 6 site searches, 6 submitted demo forms, 4 JavaScript-rendered pages, 4 page-title reports.
Each task was driven from its start page by clicks, typing and form submits. Every page on the way returned HTTP 200 with no challenge page.
Evidence was collected by the runner's real collect_page_evidence (including its text cap), then graded by evidence_verdict with expected_answer as the claimed answer. Every expected answer was also checked for literal presence in that evidence.
Negative controls: the correct answer claimed on real wrong pages (the start page unless it is the finished page, plus listed decoys such as the page one step short, a neighbouring page, or the site's results page) must FAIL; a wrong value that is on the finished page must FAIL; for script-rendered tasks the answer's row must be absent when the page loads without JavaScript.
URL controls: the finished page's evidence must still PASS at its URL with a #fragment and at listed equivalent URLs (trailing slash, no extension, mobile host, other docs version).

Reproduce: `python -m bench.verify_heldout3_d` (public network access; no model calls).

| Task id | Start status | End URL | Verdict | Controls |
| --- | --- | --- | --- | --- |
| ho3d_nav_nobel_physics_1921_facts | 200 | https://www.nobelprize.org/prizes/physics/1921/einstein/facts/ | PASS | 3 wrong pages FAIL; 2 URL variants PASS |
| ho3d_nav_vue_conditional | 200 | https://vuejs.org/guide/essentials/conditional.html | PASS | 3 wrong pages FAIL; 2 URL variants PASS |
| ho3d_nav_euler_pythagorean | 200 | https://projecteuler.net/problem=9 | PASS | 3 wrong pages FAIL; 2 URL variants PASS |
| ho3d_nav_webscraper_cheapest_touch | 200 | https://webscraper.io/test-sites/e-commerce/allinone/product/1 | PASS | 3 wrong pages FAIL; 1 URL variants PASS |
| ho3d_nav_openbsd_pf_shortcuts | 200 | https://www.openbsd.org/faq/pf/shortcuts.html | PASS | 3 wrong pages FAIL; 2 URL variants PASS |
| ho3d_nav_react_first_component | 200 | https://react.dev/learn/your-first-component | PASS | 3 wrong pages FAIL; 2 URL variants PASS |
| ho3d_nav_ocaml_loops | 200 | https://ocaml.org/docs/loops-recursion | PASS | 3 wrong pages FAIL; 2 URL variants PASS |
| ho3d_nav_nextjs_fetching | 200 | https://nextjs.org/docs/app/getting-started/fetching-data | PASS | 3 wrong pages FAIL; 2 URL variants PASS |
| ho3d_nav_pokemondb_mewtwo | 200 | https://pokemondb.net/pokedex/mewtwo | PASS | 3 wrong pages FAIL; 2 URL variants PASS |
| ho3d_nav_nim_strutils | 200 | https://nim-lang.org/docs/strutils.html | PASS | 3 wrong pages FAIL; 2 URL variants PASS |
| ho3d_value_rcsb_1tup_resolution | 200 | https://www.rcsb.org/structure/1TUP | PASS | 1 wrong pages FAIL; 3 URL variants PASS; wrong value FAIL |
| ho3d_value_pokemondb_pikachu_total | 200 | https://pokemondb.net/pokedex/pikachu | PASS | 2 wrong pages FAIL; 2 URL variants PASS; wrong value FAIL |
| ho3d_value_nobel_1922_affiliation | 200 | https://www.nobelprize.org/prizes/physics/1922/bohr/facts/ | PASS | 2 wrong pages FAIL; 2 URL variants PASS; wrong value FAIL |
| ho3d_value_tailwind_text_base_leading | 200 | https://tailwindcss.com/docs/font-size | PASS | 1 wrong pages FAIL; 1 URL variants PASS; wrong value FAIL |
| ho3d_value_playwright_test_timeout | 200 | https://playwright.dev/docs/test-timeouts | PASS | 1 wrong pages FAIL; 2 URL variants PASS; wrong value FAIL |
| ho3d_value_sklearn_logreg_max_iter | 200 | https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.LogisticRegression.html | PASS | 3 wrong pages FAIL; 2 URL variants PASS; wrong value FAIL |
| ho3d_value_pytorch_dropout_p | 200 | https://docs.pytorch.org/docs/2.15/generated/torch.nn.Dropout.html | PASS | 2 wrong pages FAIL; 2 URL variants PASS; wrong value FAIL |
| ho3d_value_webscraper_table_tim | 200 | https://webscraper.io/test-sites/tables/tables-semantically-correct | PASS | 2 wrong pages FAIL; 2 URL variants PASS; wrong value FAIL |
| ho3d_value_rahulshetty_sql_price | 200 | https://rahulshettyacademy.com/AutomationPractice/ | PASS | 1 wrong pages FAIL; 1 URL variants PASS; wrong value FAIL |
| ho3d_value_pandas_sort_kind | 200 | https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.sort_values.html | PASS | 2 wrong pages FAIL; 1 URL variants PASS; wrong value FAIL |
| ho3d_search_videolan_cli | 200 | https://wiki.videolan.org/VLC_command-line_help/ | PASS | 3 wrong pages FAIL; 2 URL variants PASS |
| ho3d_search_pandas_read_csv | 200 | https://pandas.pydata.org/docs/reference/api/pandas.read_csv.html#pandas.read_csv | PASS | 3 wrong pages FAIL; 3 URL variants PASS |
| ho3d_search_sklearn_random_forest | 200 | https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.RandomForestClassifier.html | PASS | 3 wrong pages FAIL; 2 URL variants PASS |
| ho3d_search_openbsd_man_pledge | 200 | https://man.openbsd.org/pledge | PASS | 3 wrong pages FAIL; 3 URL variants PASS |
| ho3d_search_pytorch_conv2d | 200 | https://docs.pytorch.org/docs/2.15/generated/torch.nn.Conv2d.html | PASS | 3 wrong pages FAIL; 2 URL variants PASS |
| ho3d_search_vue_teleport | 200 | https://vuejs.org/guide/built-ins/teleport.html#teleport | PASS | 3 wrong pages FAIL; 3 URL variants PASS |
| ho3d_form_parabank_login | 200 | https://parabank.parasoft.com/parabank/overview.htm | PASS | 2 wrong pages FAIL; 2 URL variants PASS; wrong value FAIL |
| ho3d_form_scrapingcourse_login | 200 | https://www.scrapingcourse.com/dashboard | PASS | 1 wrong pages FAIL; 2 URL variants PASS; wrong value FAIL; absent without JS |
| ho3d_form_pokeapi_pikachu | 200 | https://pokeapi.co/ | PASS | 1 wrong pages FAIL; 1 URL variants PASS; wrong value FAIL |
| ho3d_form_qa_practice_input | 200 | https://www.qa-practice.com/elements/input/simple | PASS | 1 wrong pages FAIL; 2 URL variants PASS; wrong value FAIL |
| ho3d_form_qa_practice_textarea | 200 | https://www.qa-practice.com/elements/textarea/single | PASS | 1 wrong pages FAIL; 2 URL variants PASS; wrong value FAIL |
| ho3d_form_ultimateqa_contact | 200 | https://ultimateqa.com/filling-out-forms/ | PASS | 1 wrong pages FAIL; 1 URL variants PASS; wrong value FAIL |
| ho3d_spa_scrapingcourse_hero | 200 | https://www.scrapingcourse.com/javascript-rendering | PASS | 1 wrong pages FAIL; 2 URL variants PASS; wrong value FAIL; absent without JS |
| ho3d_spa_rahul_shop_cart | 200 | https://rahulshettyacademy.com/angularpractice/shop | PASS | 1 wrong pages FAIL; 2 URL variants PASS; wrong value FAIL |
| ho3d_spa_toolshop_pliers | 200 | https://practicesoftwaretesting.com/ | PASS | 1 wrong pages FAIL; 2 URL variants PASS; wrong value FAIL; absent without JS |
| ho3d_spa_scrapingcourse_load_more | 200 | https://www.scrapingcourse.com/button-click | PASS | 1 wrong pages FAIL; 2 URL variants PASS; wrong value FAIL; absent without JS |
| ho3d_title_pokemondb_after_pikachu | 200 | https://pokemondb.net/pokedex/raichu | PASS | 2 wrong pages FAIL; 2 URL variants PASS; wrong value FAIL |
| ho3d_title_euler_after_palindrome | 200 | https://projecteuler.net/problem=5 | PASS | 2 wrong pages FAIL; 2 URL variants PASS; wrong value FAIL |
| ho3d_title_vue_after_intro | 200 | https://vuejs.org/guide/quick-start.html | PASS | 2 wrong pages FAIL; 2 URL variants PASS; wrong value FAIL |
| ho3d_title_ocaml_datatypes | 200 | https://ocaml.org/docs/basic-data-types | PASS | 2 wrong pages FAIL; 2 URL variants PASS; wrong value FAIL |
