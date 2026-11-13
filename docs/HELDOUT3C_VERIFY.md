# Heldout3c public-page verification

Verified 2026-11-13 02:42 UTC with local headless Chromium.

This is page/marker validation, not an agent benchmark result. No LLM API calls or bench probes were run.
Mix: 10 multi-step navigation, 10 value reports, 6 site searches, 6 submitted demo forms, 4 JavaScript-rendered pages, 4 page-title reports.
Each task was driven from its start page by clicks, typing and form submits. Every page on the way returned HTTP 200 with no challenge page.
Evidence was collected by the runner's real collect_page_evidence (including its text cap), then graded by evidence_verdict with expected_answer as the claimed answer. Every expected answer was also checked for literal presence in that evidence.
Negative controls: the correct answer claimed on real wrong pages (the start page unless it is the finished page, plus listed decoys such as the page one step short, a neighbouring page, or the site's results page) must FAIL; a wrong value that is on the finished page must FAIL; for script-rendered tasks the answer's row must be absent when the page loads without JavaScript.
URL controls: the finished page's evidence must still PASS at its URL with a #fragment and at listed equivalent URLs (trailing slash, bare host, other docs version, extra query).

Reproduce: `python -m bench.verify_heldout3_c` (public network access; no model calls).

| Task id | Start status | End URL | Verdict | Controls |
| --- | --- | --- | --- | --- |
| ho3c_nav_musicbrainz_ok_computer | 200 | https://musicbrainz.org/release-group/b1392450-e666-3926-a536-22c65f834433 | PASS | 3 wrong pages FAIL; 2 URL variants PASS |
| ho3c_nav_graphviz_rankdir | 200 | https://www.graphviz.org/docs/attrs/rankdir/ | PASS | 4 wrong pages FAIL; 3 URL variants PASS |
| ho3c_nav_bootstrap_collapsible_stack | 200 | https://getbootstrap.com/docs/5.3/components/accordion/ | PASS | 3 wrong pages FAIL; 3 URL variants PASS |
| ho3c_nav_eslint_unused_rule | 200 | https://eslint.org/docs/latest/rules/no-unused-vars | PASS | 3 wrong pages FAIL; 3 URL variants PASS |
| ho3c_nav_helm_named_values | 200 | https://helm.sh/docs/chart_template_guide/variables | PASS | 3 wrong pages FAIL; 3 URL variants PASS |
| ho3c_nav_jekyll_url_structure | 200 | https://jekyllrb.com/docs/permalinks/ | PASS | 3 wrong pages FAIL; 3 URL variants PASS |
| ho3c_nav_blender_smoothing_modifier | 200 | https://docs.blender.org/manual/en/latest/modeling/modifiers/generate/subdivision_surface.html | PASS | 3 wrong pages FAIL; 2 URL variants PASS |
| ho3c_nav_govuk_lost_licence | 200 | https://www.gov.uk/replace-a-driving-licence | PASS | 3 wrong pages FAIL; 3 URL variants PASS |
| ho3c_nav_docker_compose_benefits | 200 | https://docs.docker.com/compose/intro/features-uses/ | PASS | 3 wrong pages FAIL; 3 URL variants PASS |
| ho3c_nav_dart_enumerated_types | 200 | https://dart.dev/language/enums | PASS | 3 wrong pages FAIL; 3 URL variants PASS |
| ho3c_value_graphviz_nodesep | 200 | https://www.graphviz.org/docs/attrs/nodesep/ | PASS | 2 wrong pages FAIL; 3 URL variants PASS; wrong value FAIL |
| ho3c_value_bootstrap_xxl_width | 200 | https://getbootstrap.com/docs/5.3/layout/breakpoints/ | PASS | 2 wrong pages FAIL; 2 URL variants PASS; wrong value FAIL |
| ho3c_value_chemicool_gallium_melting | 200 | https://www.chemicool.com/elements/gallium.html | PASS | 2 wrong pages FAIL; 2 URL variants PASS; wrong value FAIL |
| ho3c_value_brew_ripgrep_license | 200 | https://formulae.brew.sh/formula/ripgrep | PASS | 3 wrong pages FAIL; 3 URL variants PASS; wrong value FAIL |
| ho3c_value_geonames_iceland_area | 200 | https://www.geonames.org/countries | PASS | 2 wrong pages FAIL; 3 URL variants PASS; wrong value FAIL |
| ho3c_value_duckdb_utinyint_max | 200 | https://duckdb.org/docs/2.0/sql/data_types/numeric | PASS | 2 wrong pages FAIL; 3 URL variants PASS; wrong value FAIL |
| ho3c_value_eslint_file_line_limit | 200 | https://eslint.org/docs/latest/rules/max-lines | PASS | 2 wrong pages FAIL; 2 URL variants PASS; wrong value FAIL |
| ho3c_value_mathsisfun_mile_km | 200 | https://www.mathsisfun.com/metric-imperial-conversion-charts.html | PASS | 1 wrong pages FAIL; 2 URL variants PASS; wrong value FAIL |
| ho3c_value_govuk_vat_reduced | 200 | https://www.gov.uk/vat-rates | PASS | 1 wrong pages FAIL; 3 URL variants PASS; wrong value FAIL |
| ho3c_value_musicbrainz_boards_founded_in | 200 | https://musicbrainz.org/artist/69158f97-4c07-4c4e-baf8-4e4ab1ed666e | PASS | 1 wrong pages FAIL; 3 URL variants PASS; wrong value FAIL |
| ho3c_search_musicbrainz_afx | 200 | https://musicbrainz.org/artist/f22942a1-6f70-4f48-866e-238cb2308fbd | PASS | 2 wrong pages FAIL; 2 URL variants PASS |
| ho3c_search_geonames_matterhorn | 200 | https://www.geonames.org/2659729/matterhorn.html | PASS | 3 wrong pages FAIL; 3 URL variants PASS |
| ho3c_search_ctan_bibliography | 200 | https://www.ctan.org/pkg/biblatex | PASS | 3 wrong pages FAIL; 3 URL variants PASS |
| ho3c_search_blender_multires | 200 | https://docs.blender.org/manual/en/latest/modeling/modifiers/generate/multiresolution.html | PASS | 3 wrong pages FAIL; 2 URL variants PASS |
| ho3c_search_govuk_passport_costs | 200 | https://www.gov.uk/passport-fees | PASS | 3 wrong pages FAIL; 3 URL variants PASS |
| ho3c_search_ansible_galaxy_cli | 200 | https://docs.ansible.com/projects/ansible/latest/cli/ansible-galaxy.html#ansible-galaxy | PASS | 3 wrong pages FAIL; 3 URL variants PASS |
| ho3c_form_calcnet_percent_of | 200 | https://www.calculator.net/percent-calculator.html?cpar1=17.5&cpar2=60&cpar3=&ctype=1&x=Calculate | PASS | 2 wrong pages FAIL; 3 URL variants PASS; wrong value FAIL |
| ho3c_form_calcnet_mean | 200 | https://www.calculator.net/average-calculator.html?numberinputs=5%2C+9%2C+17%2C+22%2C+41&x=Calculate | PASS | 2 wrong pages FAIL; 2 URL variants PASS; wrong value FAIL |
| ho3c_form_calcnet_sales_tax | 200 | https://www.calculator.net/sales-tax-calculator.html?beforetax=250&taxrate=8.25&finalprice=&x=Calculate | PASS | 1 wrong pages FAIL; 1 URL variants PASS; wrong value FAIL |
| ho3c_form_lipsum_eight_words | 200 | https://www.lipsum.com/feed/html | PASS | 1 wrong pages FAIL; 1 URL variants PASS; wrong value FAIL |
| ho3c_form_alpine_bash_license | 200 | https://pkgs.alpinelinux.org/packages?name=bash&branch=v3.20&repo=&arch=x86_64&origin=&flagged=&maintainer= | PASS | 2 wrong pages FAIL; 2 URL variants PASS; wrong value FAIL |
| ho3c_form_alpine_envsubst_file | 200 | https://pkgs.alpinelinux.org/contents?file=envsubst&path=&name=&branch=v3.20&repo=&arch=x86_64 | PASS | 2 wrong pages FAIL; 2 URL variants PASS; wrong value FAIL |
| ho3c_spa_datatables_ajax_salary | 200 | https://datatables.net/examples/core/ajax/objects.html | PASS | 1 wrong pages FAIL; 2 URL variants PASS; wrong value FAIL; absent without JS |
| ho3c_spa_crontab_weekday_text | 200 | https://crontab.guru/#30_8_*_*_1-5 | PASS | 2 wrong pages FAIL; 3 URL variants PASS; wrong value FAIL; absent without JS |
| ho3c_spa_bstack_pro_max | 200 | https://bstackdemo.com/ | PASS | 1 wrong pages FAIL; 3 URL variants PASS; wrong value FAIL; absent without JS |
| ho3c_spa_demoblaze_nokia | 200 | https://demoblaze.com/ | PASS | 1 wrong pages FAIL; 3 URL variants PASS; wrong value FAIL; absent without JS |
| ho3c_title_jekyll_after_front_matter | 200 | https://jekyllrb.com/docs/collections/ | PASS | 2 wrong pages FAIL; 3 URL variants PASS; wrong value FAIL |
| ho3c_title_chemicool_w | 200 | https://www.chemicool.com/elements/tungsten.html | PASS | 2 wrong pages FAIL; 2 URL variants PASS; wrong value FAIL |
| ho3c_title_dart_next_page | 200 | https://dart.dev/language/variables | PASS | 2 wrong pages FAIL; 2 URL variants PASS; wrong value FAIL |
| ho3c_title_helm_after_variables | 200 | https://helm.sh/docs/chart_template_guide/named_templates | PASS | 2 wrong pages FAIL; 2 URL variants PASS; wrong value FAIL |
