# Heldout3b public-page verification

Verified 2026-11-13 10:08 UTC with local headless Chromium.

This is page/marker validation, not an agent benchmark result. No LLM API calls or bench probes were run.
Mix: 8 multi-step navigation, 8 value reports, 4 site searches, 4 submitted demo forms, 3 JavaScript-rendered pages, 3 page-title reports.
Each task was driven from its start page by clicks, typing and form submits. Every page on the way returned HTTP 200 with no challenge page.
Evidence was collected by the runner's real collect_page_evidence (including its text cap), then graded by evidence_verdict with expected_answer as the claimed answer. Every expected answer was also checked for literal presence in that evidence.
Negative controls: the correct answer claimed on real wrong pages (the start page unless it is the finished page, plus listed decoys such as the page one step short, a neighbouring page, or the site's results page) must FAIL; a wrong value that is on the finished page must FAIL; for script-rendered tasks the answer's row must be absent when the page loads without JavaScript.
URL controls: the finished page's evidence must still PASS at its URL with a #fragment and at listed equivalent URLs (trailing slash or index.html, mobile host, unencoded path, other docs version).

Reproduce: `python -m bench.verify_heldout3_b` (public network access; no model calls).

| Task id | Start status | End URL | Verdict | Controls |
| --- | --- | --- | --- | --- |
| ho3b_nav_xkcd_mom | 200 | https://xkcd.com/327/ | PASS | 3 wrong pages FAIL; 2 URL variants PASS |
| ho3b_nav_wikidata_death_country | 200 | https://www.wikidata.org/wiki/Q30 | PASS | 3 wrong pages FAIL; 2 URL variants PASS |
| ho3b_nav_books_cheapest_travel | 200 | https://books.toscrape.com/catalogue/the-road-to-little-dribbling-adventures-of-an-american-in-britain-notes-from-a-small-island-2_277/index.html | PASS | 3 wrong pages FAIL; 2 URL variants PASS |
| ho3b_nav_oracle_lambda | 200 | https://docs.oracle.com/javase/tutorial/java/javaOO/lambdaexpressions.html | PASS | 3 wrong pages FAIL; 1 URL variants PASS |
| ho3b_nav_nssdc_jovian_moons | 200 | https://nssdc.gsfc.nasa.gov/planetary/factsheet/joviansatfact.html | PASS | 3 wrong pages FAIL; 1 URL variants PASS |
| ho3b_nav_typescript_refining | 200 | https://www.typescriptlang.org/docs/handbook/2/narrowing.html | PASS | 3 wrong pages FAIL; 1 URL variants PASS |
| ho3b_nav_tcl_sort_command | 200 | https://www.tcl-lang.org/man/tcl8.6/TclCmd/lsort.htm | PASS | 3 wrong pages FAIL; 2 URL variants PASS |
| ho3b_nav_osm_bench_tag | 200 | https://wiki.openstreetmap.org/wiki/Tag:amenity%3Dbench | PASS | 3 wrong pages FAIL; 2 URL variants PASS |
| ho3b_value_nssdc_mars_mass | 200 | https://nssdc.gsfc.nasa.gov/planetary/factsheet/index.html | PASS | 3 wrong pages FAIL; 2 URL variants PASS; wrong value FAIL |
| ho3b_value_jpl_neptune_radius | 200 | https://ssd.jpl.nasa.gov/planets/phys_par.html | PASS | 2 wrong pages FAIL; 1 URL variants PASS; wrong value FAIL |
| ho3b_value_oracle_char_default | 200 | https://docs.oracle.com/javase/tutorial/java/nutsandbolts/datatypes.html | PASS | 1 wrong pages FAIL; 1 URL variants PASS; wrong value FAIL |
| ho3b_value_numpy_interval_num | 200 | https://numpy.org/doc/stable/reference/generated/numpy.linspace.html | PASS | 2 wrong pages FAIL; 2 URL variants PASS; wrong value FAIL |
| ho3b_value_php_pad_default | 200 | https://www.php.net/manual/en/function.str-pad.php | PASS | 2 wrong pages FAIL; 2 URL variants PASS; wrong value FAIL |
| ho3b_value_rubygems_rails_ruby | 200 | https://rubygems.org/gems/rails/versions/7.0.0 | PASS | 2 wrong pages FAIL; 1 URL variants PASS; wrong value FAIL |
| ho3b_value_oeis_catalan_formerly | 200 | https://oeis.org/A000108 | PASS | 2 wrong pages FAIL; 1 URL variants PASS; wrong value FAIL |
| ho3b_value_spdx_zero_clause | 200 | https://spdx.org/licenses/ | PASS | 1 wrong pages FAIL; 3 URL variants PASS; wrong value FAIL |
| ho3b_search_oeis_triangular | 200 | https://oeis.org/A000217 | PASS | 3 wrong pages FAIL; 1 URL variants PASS |
| ho3b_search_scipy_curve_fit | 200 | https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.curve_fit.html | PASS | 3 wrong pages FAIL; 2 URL variants PASS |
| ho3b_search_wiktionary_rain_scent | 200 | https://en.wiktionary.org/wiki/petrichor | PASS | 3 wrong pages FAIL; 1 URL variants PASS |
| ho3b_search_rubygems_nokogiri | 200 | https://rubygems.org/gems/nokogiri | PASS | 3 wrong pages FAIL; 1 URL variants PASS |
| ho3b_form_practice_login | 200 | https://practicetestautomation.com/logged-in-successfully/ | PASS | 1 wrong pages FAIL; 1 URL variants PASS; wrong value FAIL |
| ho3b_form_wdu_contact | 200 | https://webdriveruniversity.com/Contact-Us/contactus.html | PASS | 1 wrong pages FAIL; 1 URL variants PASS; wrong value FAIL |
| ho3b_form_saucedemo_jacket | 200 | https://www.saucedemo.com/inventory.html | PASS | 1 wrong pages FAIL; 1 URL variants PASS; wrong value FAIL; absent without JS |
| ho3b_form_scrapethissite_hockey | 200 | https://www.scrapethissite.com/pages/forms/?q=Detroit+Red+Wings | PASS | 1 wrong pages FAIL; 1 URL variants PASS; wrong value FAIL |
| ho3b_spa_quotes_simile | 200 | https://quotes.toscrape.com/js/ | PASS | 2 wrong pages FAIL; 2 URL variants PASS; wrong value FAIL; absent without JS |
| ho3b_spa_swagger_upload_path | 200 | https://petstore.swagger.io/ | PASS | 1 wrong pages FAIL; 3 URL variants PASS; wrong value FAIL; absent without JS |
| ho3b_spa_scrapethissite_oscars | 200 | https://www.scrapethissite.com/pages/ajax-javascript/#2015 | PASS | 2 wrong pages FAIL; 2 URL variants PASS; wrong value FAIL; absent without JS |
| ho3b_title_xkcd_after_mom | 200 | https://xkcd.com/328/ | PASS | 2 wrong pages FAIL; 2 URL variants PASS; wrong value FAIL |
| ho3b_title_books_priciest_poetry | 200 | https://books.toscrape.com/catalogue/slow-states-of-collapse-poems_960/index.html | PASS | 1 wrong pages FAIL; 2 URL variants PASS; wrong value FAIL |
| ho3b_title_typescript_after_basics | 200 | https://www.typescriptlang.org/docs/handbook/2/everyday-types.html | PASS | 1 wrong pages FAIL; 1 URL variants PASS; wrong value FAIL |
