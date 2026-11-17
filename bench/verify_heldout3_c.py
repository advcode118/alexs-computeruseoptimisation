"""Opt-in public-page verification, not an agent run or an LLM probe.

Run ``python -m bench.verify_heldout3_c`` to refresh docs/HELDOUT3C_VERIFY.md.
Pass task ids as arguments to check only those tasks (the report is not written then).
Only local headless Chromium and the deterministic evidence grader are used.
Every task is driven by clicks, typing and form submits from its start page.
Each task also has negative controls that must grade FAIL.
"""

from __future__ import annotations

import asyncio
import re
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from bench.script_first import ClaimedEvidence, collect_page_evidence, evidence_verdict
from bench.tasks import tasks_for_split

RADIOHEAD = "a74b1b7f-71a5-4011-9441-d0b5e4122711"
OK_COMPUTER = "b1392450-e666-3926-a536-22c65f834433"
APHEX = "f22942a1-6f70-4f48-866e-238cb2308fbd"
BOARDS = "69158f97-4c07-4c4e-baf8-4e4ab1ed666e"

# A value that is on the finished page but is not the requested one.
WRONG_VALUES = {
    "ho3c_value_graphviz_nodesep": "0.02",
    "ho3c_value_bootstrap_xxl_width": "1200",
    "ho3c_value_chemicool_gallium_melting": "302.91",
    "ho3c_value_brew_ripgrep_license": "BurntSushi",
    "ho3c_value_geonames_iceland_area": "392,404",
    "ho3c_value_duckdb_utinyint_max": "2^7 - 1",
    "ho3c_value_eslint_file_line_limit": "skipBlankLines",
    "ho3c_value_mathsisfun_mile_km": "0.3048",
    "ho3c_value_govuk_vat_reduced": "20%",
    "ho3c_value_musicbrainz_boards_founded_in": "1986",
    "ho3c_form_calcnet_percent_of": "17.5",
    "ho3c_form_calcnet_mean": "94",
    "ho3c_form_calcnet_sales_tax": "20.63",
    "ho3c_form_lipsum_eight_words": "8",
    "ho3c_form_alpine_bash_license": "v3.20",
    "ho3c_form_alpine_envsubst_file": "/usr/bin/envsubst",
    "ho3c_spa_datatables_ajax_salary": "$1,200,000",
    "ho3c_spa_crontab_weekday_text": "any value",
    "ho3c_spa_bstack_pro_max": "$999.00",
    "ho3c_spa_demoblaze_nokia": "$360",
    "ho3c_title_jekyll_after_front_matter": "Permalinks",
    "ho3c_title_chemicool_w": "Tungsten",
    "ho3c_title_dart_next_page": "Null safety",
    "ho3c_title_helm_after_variables": "Chart Template Guide",
}

# Real wrong pages beyond the start page: a step short, a neighbour, or a results page.
DECOYS = {
    "ho3c_nav_musicbrainz_ok_computer": [
        f"https://musicbrainz.org/artist/{RADIOHEAD}",
        "https://musicbrainz.org/release-group/e75c0549-ad55-39e3-8025-c72c5d4a3c5d",
    ],
    "ho3c_nav_graphviz_rankdir": [
        "https://www.graphviz.org/documentation/",
        "https://www.graphviz.org/docs/attrs/nodesep/",
        "https://www.graphviz.org/docs/attr-types/rankdir/",
    ],
    "ho3c_nav_bootstrap_collapsible_stack": [
        "https://getbootstrap.com/docs/5.3/components/collapse/",
        "https://getbootstrap.com/docs/5.3/components/alerts/",
    ],
    "ho3c_nav_eslint_unused_rule": [
        "https://eslint.org/docs/latest/rules/",
        "https://eslint.org/docs/latest/rules/no-undef",
    ],
    "ho3c_nav_helm_named_values": [
        "https://helm.sh/docs/chart_template_guide/",
        "https://helm.sh/docs/chart_template_guide/named_templates",
    ],
    "ho3c_nav_jekyll_url_structure": ["https://jekyllrb.com/docs/", "https://jekyllrb.com/docs/pages/"],
    "ho3c_nav_blender_smoothing_modifier": [
        "https://docs.blender.org/manual/en/latest/modeling/modifiers/generate/index.html",
        "https://docs.blender.org/manual/en/latest/modeling/modifiers/generate/multiresolution.html",
    ],
    "ho3c_nav_govuk_lost_licence": [
        "https://www.gov.uk/browse/driving/driving-licences",
        "https://www.gov.uk/renew-driving-licence",
    ],
    "ho3c_nav_docker_compose_benefits": [
        "https://docs.docker.com/compose/",
        "https://docs.docker.com/compose/intro/compose-application-model/",
    ],
    "ho3c_nav_dart_enumerated_types": ["https://dart.dev/language", "https://dart.dev/language/classes"],
    "ho3c_value_graphviz_nodesep": ["https://www.graphviz.org/docs/attrs/ranksep/"],
    "ho3c_value_bootstrap_xxl_width": ["https://getbootstrap.com/docs/5.3/layout/grid/"],
    "ho3c_value_chemicool_gallium_melting": ["https://www.chemicool.com/elements/aluminum.html"],
    "ho3c_value_brew_ripgrep_license": ["https://formulae.brew.sh/formula/", "https://formulae.brew.sh/formula/grep"],
    "ho3c_value_geonames_iceland_area": ["https://www.geonames.org/statistics"],
    "ho3c_value_duckdb_utinyint_max": ["https://duckdb.org/docs/stable/sql/data_types/overview"],
    "ho3c_value_eslint_file_line_limit": ["https://eslint.org/docs/latest/rules/max-lines-per-function"],
    "ho3c_value_mathsisfun_mile_km": ["https://www.mathsisfun.com/"],
    "ho3c_value_govuk_vat_reduced": ["https://www.gov.uk/vat-registration"],
    "ho3c_value_musicbrainz_boards_founded_in": [f"https://musicbrainz.org/artist/{APHEX}"],
    "ho3c_search_musicbrainz_afx": ["https://musicbrainz.org/artist/1f7b4d15-cf9b-403e-bab8-87fc99aa08ef"],
    "ho3c_search_geonames_matterhorn": [
        "https://www.geonames.org/ui-search?q=Matterhorn",
        "https://www.geonames.org/1547307/little-matterhorn.html",
    ],
    "ho3c_search_ctan_bibliography": [
        "https://www.ctan.org/search?phrase=biblatex",
        "https://www.ctan.org/pkg/biber",
    ],
    "ho3c_search_blender_multires": [
        "https://docs.blender.org/manual/en/latest/search.html?q=Multiresolution",
        "https://docs.blender.org/manual/en/latest/modeling/modifiers/generate/subdivision_surface.html",
    ],
    "ho3c_search_govuk_passport_costs": [
        "https://www.gov.uk/search/all?keywords=passport+fees",
        "https://www.gov.uk/renew-adult-passport",
    ],
    "ho3c_search_ansible_galaxy_cli": [
        "https://docs.ansible.com/projects/ansible/latest/search.html?q=ansible-galaxy",
        "https://docs.ansible.com/projects/ansible/latest/cli/ansible-vault.html",
    ],
    "ho3c_form_calcnet_percent_of": ["https://www.calculator.net/percent-calculator.html"],
    "ho3c_form_calcnet_mean": ["https://www.calculator.net/average-calculator.html"],
    "ho3c_form_alpine_bash_license": ["https://pkgs.alpinelinux.org/packages?name=curl&branch=v3.20"],
    "ho3c_form_alpine_envsubst_file": ["https://pkgs.alpinelinux.org/contents?file=ssl_client&branch=v3.20&arch=x86_64"],
    "ho3c_spa_datatables_ajax_salary": ["https://datatables.net/examples/core/data_sources/ajax.html"],
    "ho3c_spa_crontab_weekday_text": ["https://crontab.guru/examples.html"],
    "ho3c_spa_bstack_pro_max": ["https://bstackdemo.com/signin"],
    "ho3c_spa_demoblaze_nokia": ["https://demoblaze.com/cart.html"],
    "ho3c_title_jekyll_after_front_matter": ["https://jekyllrb.com/docs/front-matter/"],
    "ho3c_title_chemicool_w": ["https://www.chemicool.com/elements/gallium.html"],
    "ho3c_title_dart_next_page": ["https://dart.dev/language/comments"],
    "ho3c_title_helm_after_variables": ["https://helm.sh/docs/chart_template_guide/variables"],
}

# Other correct end URLs. The finished page's evidence at these URLs must still PASS.
# Every task is also checked with a #fragment on its finished URL.
VARIANTS = {
    "ho3c_nav_musicbrainz_ok_computer": [f"https://musicbrainz.org/release-group/{OK_COMPUTER}/"],
    "ho3c_nav_graphviz_rankdir": ["https://www.graphviz.org/docs/attrs/rankdir/", "https://graphviz.org/docs/attrs/rankdir"],
    "ho3c_nav_bootstrap_collapsible_stack": [
        "https://getbootstrap.com/docs/5.3/components/accordion/",
        "https://getbootstrap.com/docs/5.3/components/accordion",
    ],
    "ho3c_nav_eslint_unused_rule": [
        "https://eslint.org/docs/latest/rules/no-unused-vars/",
        "https://eslint.org/docs/v9.x/rules/no-unused-vars",
    ],
    "ho3c_nav_helm_named_values": [
        "https://helm.sh/docs/chart_template_guide/variables/",
        "https://helm.sh/docs/chart_template_guide/variables",
    ],
    "ho3c_nav_jekyll_url_structure": ["https://jekyllrb.com/docs/permalinks", "https://jekyllrb.com/docs/permalinks/"],
    "ho3c_nav_blender_smoothing_modifier": [
        "https://docs.blender.org/manual/en/4.5/modeling/modifiers/generate/subdivision_surface.html",
    ],
    "ho3c_nav_govuk_lost_licence": ["https://www.gov.uk/replace-a-driving-licence/", "https://gov.uk/replace-a-driving-licence"],
    "ho3c_nav_docker_compose_benefits": ["https://docs.docker.com/compose/intro/features-uses", "https://docs.docker.com/compose/intro/features-uses/"],
    "ho3c_nav_dart_enumerated_types": ["https://dart.dev/language/enums/", "https://dart.dev/language/enums"],
    "ho3c_value_graphviz_nodesep": ["https://www.graphviz.org/docs/attrs/nodesep", "https://graphviz.org/docs/attrs/nodesep/"],
    "ho3c_value_bootstrap_xxl_width": ["https://getbootstrap.com/docs/5.3/layout/breakpoints/"],
    "ho3c_value_chemicool_gallium_melting": ["https://chemicool.com/elements/gallium.html"],
    "ho3c_value_brew_ripgrep_license": ["https://formulae.brew.sh/formula/ripgrep/", "https://formulae.brew.sh/formula/ripgrep.html"],
    "ho3c_value_geonames_iceland_area": ["https://www.geonames.org/countries/", "https://www.geonames.org/countries"],
    "ho3c_value_duckdb_utinyint_max": [
        "https://duckdb.org/docs/stable/sql/data_types/numeric",
        "https://duckdb.org/docs/2.0/sql/data_types/numeric/",
    ],
    "ho3c_value_eslint_file_line_limit": ["https://eslint.org/docs/v9.x/rules/max-lines"],
    "ho3c_value_mathsisfun_mile_km": ["https://mathsisfun.com/metric-imperial-conversion-charts.html"],
    "ho3c_value_govuk_vat_reduced": ["https://www.gov.uk/vat-rates/", "https://www.gov.uk/vat-rates?ref=x"],
    "ho3c_value_musicbrainz_boards_founded_in": [f"https://musicbrainz.org/artist/{BOARDS}/", f"https://musicbrainz.org/artist/{BOARDS}/details"],
    "ho3c_search_musicbrainz_afx": [f"https://musicbrainz.org/artist/{APHEX}/"],
    "ho3c_search_geonames_matterhorn": ["https://www.geonames.org/2659729/matterhorn", "https://www.geonames.org/2659729/matterhorn.html"],
    "ho3c_search_ctan_bibliography": ["https://ctan.org/pkg/biblatex", "https://www.ctan.org/pkg/biblatex/"],
    "ho3c_search_blender_multires": [
        "https://docs.blender.org/manual/en/latest/modeling/modifiers/generate/multiresolution.html?highlight=Multiresolution",
    ],
    "ho3c_search_govuk_passport_costs": ["https://www.gov.uk/passport-fees", "https://gov.uk/passport-fees"],
    "ho3c_search_ansible_galaxy_cli": [
        "https://docs.ansible.com/projects/ansible/latest/cli/ansible-galaxy.html?highlight=ansible-galaxy",
        "https://docs.ansible.com/ansible/latest/cli/ansible-galaxy.html",
    ],
    "ho3c_form_calcnet_percent_of": [
        "https://www.calculator.net/percent-calculator.html?cpar1=17.5&cpar2=60&cpar3=&ctype=1&x=Calculate",
        "https://calculator.net/percent-calculator.html?cpar1=17.5&cpar2=60&ctype=1",
    ],
    "ho3c_form_calcnet_mean": ["https://www.calculator.net/average-calculator.html?numberinputs=5%2C+9%2C+17%2C+22%2C+41&x=Calculate"],
    "ho3c_form_alpine_bash_license": ["https://pkgs.alpinelinux.org/packages?name=bash&branch=v3.20&repo=&arch=x86_64&origin=&flagged=&maintainer="],
    "ho3c_form_alpine_envsubst_file": ["https://pkgs.alpinelinux.org/contents?file=envsubst&path=&name=&branch=v3.20&repo=&arch=x86_64"],
    "ho3c_spa_datatables_ajax_salary": ["https://datatables.net/examples/ajax/objects.html"],
    "ho3c_spa_crontab_weekday_text": ["https://crontab.guru/#30_8_*_*_1-5", "https://crontab.guru/"],
    "ho3c_spa_bstack_pro_max": ["https://bstackdemo.com/?vendors=Apple", "https://www.bstackdemo.com/"],
    "ho3c_spa_demoblaze_nokia": ["https://www.demoblaze.com/", "https://demoblaze.com/index.html"],
    "ho3c_title_jekyll_after_front_matter": ["https://jekyllrb.com/docs/collections", "https://jekyllrb.com/docs/collections/"],
    "ho3c_title_chemicool_w": ["https://chemicool.com/elements/tungsten.html"],
    "ho3c_title_dart_next_page": ["https://dart.dev/language/variables/"],
    "ho3c_title_helm_after_variables": ["https://helm.sh/docs/chart_template_guide/named_templates/"],
}

# The start page is already the finished page here, so only the decoys are wrong pages.
START_IS_FINISHED = {
    "ho3c_value_mathsisfun_mile_km",
    "ho3c_value_govuk_vat_reduced",
    "ho3c_value_musicbrainz_boards_founded_in",
    "ho3c_spa_datatables_ajax_salary",
    "ho3c_spa_bstack_pro_max",
    "ho3c_spa_demoblaze_nokia",
}

# Text from the answer's row that must be missing when the finished page loads without JavaScript.
SCRIPT_ONLY = {
    "ho3c_spa_datatables_ajax_salary": "Airi Satou\tAccountant",
    "ho3c_spa_crontab_weekday_text": "At 08:30 on every day-of-week",
    "ho3c_spa_bstack_pro_max": "iPhone 12 Pro Max",
    "ho3c_spa_demoblaze_nokia": "Nokia lumia 1520",
}


async def _real_page(page, response) -> int:
    if response is None:
        # Client-side route change: the document was not reloaded, so fetch the new URL's status.
        response = await page.context.request.get(page.url)
    assert response.status == 200, (page.url, response.status)
    await page.wait_for_function("document.body && document.body.innerText.trim().length > 20", timeout=20000)
    body = await page.locator("body").inner_text()
    title = (await page.title()).casefold()
    assert len(body.strip()) > 20, (page.url, "empty/error page")
    assert not any(token in title for token in ("just a moment", "attention required", "access denied", "recaptcha", "oh noes", "client challenge")), page.url
    assert not any(token in body.casefold() for token in (
        "verify you are human", "checking your browser before accessing",
        "performing security verification", "enable javascript and cookies to continue", "too many requests",
    )), page.url
    assert await page.locator("#challenge-running, #challenge-stage, iframe[src*='challenges.cloudflare.com']").count() == 0, page.url
    return response.status


async def _follow(page, locator):
    """Click a link and wait for the page it opens.

    A hidden menu link, or one an overlay keeps from taking the click, is followed by its href.
    """
    link = locator.first
    await link.wait_for(state="attached")
    response = None
    clicked = False
    if await link.is_visible():
        before = page.url
        try:
            async with page.expect_navigation(wait_until="domcontentloaded", timeout=20000) as navigation:
                await link.click(timeout=10000)
            response = await navigation.value
            clicked = page.url != before
        except PlaywrightTimeoutError:
            clicked = False
    if not clicked:
        href = await link.get_attribute("href")
        response = await page.goto(urljoin(page.url, href), wait_until="domcontentloaded")
    await _real_page(page, response)
    return response


async def _submit(page, action):
    async with page.expect_navigation(wait_until="domcontentloaded") as navigation:
        await action()
    response = await navigation.value
    await _real_page(page, response)
    return response


def _link(page, name: str):
    return page.get_by_role("link", name=name, exact=True)


def _href(page, href: str):
    return page.locator(f"a[href='{href}']")


async def _search(page, box, query: str, result) -> None:
    await box.first.fill(query)
    await _submit(page, lambda: box.first.press("Enter"))
    if result is not None:
        await _follow(page, result)


async def _interact(page, task: dict) -> None:
    task_id = task["id"]
    if task_id == "ho3c_nav_musicbrainz_ok_computer":
        await _search(page, page.locator("input[name='query']:visible"), "Radiohead", _href(page, f"/artist/{RADIOHEAD}"))
        await _follow(page, _href(page, f"/release-group/{OK_COMPUTER}"))
    elif task_id == "ho3c_nav_graphviz_rankdir":
        await _follow(page, _link(page, "Documentation"))
        await _follow(page, _href(page, "/docs/attrs/rankdir/"))
    elif task_id == "ho3c_nav_bootstrap_collapsible_stack":
        await _follow(page, _href(page, "/docs/5.3/components/accordion"))
    elif task_id == "ho3c_nav_eslint_unused_rule":
        await _follow(page, _href(page, "/docs/latest/"))
        await _follow(page, _href(page, "/docs/latest/rules/"))
        await _follow(page, _href(page, "/docs/latest/rules/no-unused-vars"))
    elif task_id == "ho3c_nav_helm_named_values":
        await _follow(page, _href(page, "/docs"))
        await _follow(page, _href(page, "/docs/chart_template_guide/"))
        await _follow(page, _href(page, "/docs/chart_template_guide/variables"))
    elif task_id == "ho3c_nav_jekyll_url_structure":
        await _follow(page, _href(page, "/docs/"))
        await _follow(page, _href(page, "/docs/permalinks/"))
    elif task_id == "ho3c_nav_blender_smoothing_modifier":
        await _follow(page, _href(page, "modeling/index.html"))
        await _follow(page, _href(page, "modifiers/index.html"))
        await _follow(page, _href(page, "generate/index.html"))
        await _follow(page, _href(page, "subdivision_surface.html"))
    elif task_id == "ho3c_nav_govuk_lost_licence":
        await _follow(page, _href(page, "/browse/driving"))
        await _follow(page, _href(page, "/browse/driving/driving-licences"))
        await _follow(page, _href(page, "/replace-a-driving-licence"))
    elif task_id == "ho3c_nav_docker_compose_benefits":
        await _follow(page, _href(page, "/manuals/"))
        await _follow(page, page.locator("a[href$='/compose/']"))
        await _follow(page, page.locator("a[href$='/compose/intro/features-uses/']"))
    elif task_id == "ho3c_nav_dart_enumerated_types":
        await _follow(page, _href(page, "/docs"))
        await _follow(page, _href(page, "/language"))
        await _follow(page, _href(page, "/language/enums"))
    elif task_id == "ho3c_value_graphviz_nodesep":
        await _follow(page, _href(page, "/docs/attrs/nodesep/"))
    elif task_id == "ho3c_value_bootstrap_xxl_width":
        await _follow(page, _href(page, "/docs/5.3/layout/breakpoints"))
    elif task_id == "ho3c_value_chemicool_gallium_melting":
        await _follow(page, page.locator("a[href$='/elements/gallium.html']"))
    elif task_id == "ho3c_value_brew_ripgrep_license":
        await _follow(page, page.get_by_role("link", name=re.compile(r"Browse all formulae", re.I)))
        await _follow(page, _href(page, "/formula/ripgrep"))
    elif task_id == "ho3c_value_geonames_iceland_area":
        await _follow(page, _href(page, "/countries"))
    elif task_id == "ho3c_value_duckdb_utinyint_max":
        await _follow(page, page.locator("a[href*='data_types/numeric']"))
    elif task_id == "ho3c_value_eslint_file_line_limit":
        await _follow(page, _href(page, "/docs/latest/rules/max-lines"))
    elif task_id in ("ho3c_value_mathsisfun_mile_km", "ho3c_value_govuk_vat_reduced", "ho3c_value_musicbrainz_boards_founded_in"):
        pass
    elif task_id == "ho3c_search_musicbrainz_afx":
        await _search(page, page.locator("input[name='query']:visible"), "Aphex Twin", page.locator(f"table a[href='/artist/{APHEX}']"))
    elif task_id == "ho3c_search_geonames_matterhorn":
        await _search(page, page.locator("input[name='q']:visible"), "Matterhorn", _href(page, "/2659729/matterhorn.html"))
    elif task_id == "ho3c_search_ctan_bibliography":
        await _search(page, page.locator("input[name='phrase']:visible"), "biblatex", _href(page, "/pkg/biblatex"))
    elif task_id == "ho3c_search_blender_multires":
        await _search(page, page.locator("input[name='q']:visible"), "Multiresolution", page.locator("ul.search a[href*='modeling/modifiers/generate/multiresolution.html']"))
    elif task_id == "ho3c_search_govuk_passport_costs":
        await _search(page, page.locator("input[type='search']:visible"), "passport fees", _href(page, "/passport-fees"))
    elif task_id == "ho3c_search_ansible_galaxy_cli":
        await _search(page, page.locator("input[name='q']:visible"), "ansible-galaxy", page.locator("ul.search a[href*='cli/ansible-galaxy.html']"))
    elif task_id == "ho3c_form_calcnet_percent_of":
        await page.locator("#cpar1").fill("17.5")
        await page.locator("#cpar2").fill("60")
        await _submit(page, lambda: page.locator("#cpar2").press("Enter"))
    elif task_id == "ho3c_form_calcnet_mean":
        await page.locator("textarea[name='numberinputs']").fill("5, 9, 17, 22, 41")
        await _submit(page, lambda: page.locator("input[value='Calculate']").first.click())
    elif task_id == "ho3c_form_calcnet_sales_tax":
        await page.locator("#beforetax").fill("250")
        await page.locator("input[name='taxrate']").fill("8.25")
        await page.locator("#finalprice").fill("")
        await _submit(page, lambda: page.locator("input[value='Calculate']").first.click())
    elif task_id == "ho3c_form_lipsum_eight_words":
        await page.locator("#words").check()
        await page.locator("#amount").fill("8")
        await _submit(page, lambda: page.locator("#generate").click())
    elif task_id == "ho3c_form_alpine_bash_license":
        await page.locator("input[name='name']").fill("bash")
        await page.locator("select[name='branch']").select_option("v3.20")
        await _submit(page, lambda: page.locator("form button").first.click())
    elif task_id == "ho3c_form_alpine_envsubst_file":
        await page.locator("input[name='file']").fill("envsubst")
        await page.locator("select[name='branch']").select_option("v3.20")
        await page.locator("select[name='arch']").select_option("x86_64")
        await _submit(page, lambda: page.locator("form button").first.click())
    elif task_id == "ho3c_spa_datatables_ajax_salary":
        await page.get_by_text("Airi Satou").first.wait_for()
    elif task_id == "ho3c_spa_crontab_weekday_text":
        box = page.locator("input").first
        await box.fill("30 8 * * 1-5")
        await page.get_by_text("At 08:30 on every day-of-week from Monday through Friday.").first.wait_for()
    elif task_id == "ho3c_spa_bstack_pro_max":
        await page.get_by_text("iPhone 12 Pro Max", exact=True).first.wait_for()
    elif task_id == "ho3c_spa_demoblaze_nokia":
        await page.get_by_text("Nokia lumia 1520", exact=True).first.wait_for()
    elif task_id == "ho3c_title_jekyll_after_front_matter":
        await _follow(page, _href(page, "/docs/collections/"))
    elif task_id == "ho3c_title_chemicool_w":
        await _follow(page, page.locator("a[href$='/elements/tungsten.html']"))
    elif task_id == "ho3c_title_dart_next_page":
        await _follow(page, _href(page, "/language/variables"))
    elif task_id == "ho3c_title_helm_after_variables":
        await _follow(page, _href(page, "/docs/chart_template_guide/named_templates"))
    else:
        raise AssertionError(f"no steps for {task_id}")


async def _evidence_at(context, url: str, *, javascript: bool = True):
    page = await context.new_page()
    try:
        response = await page.goto(url, wait_until="domcontentloaded")
        # A static SPA host may answer a deep link with 404 plus the app shell; only decoys must be real pages.
        if javascript:
            assert response is not None and response.status == 200, (url, response.status if response else None)
            await page.wait_for_timeout(1500)
        return await collect_page_evidence(page)
    finally:
        await page.close()


async def verify(only: list[str] | None = None) -> list[tuple]:
    tasks = tasks_for_split("heldout3c")
    if only:
        tasks = [task for task in tasks if task["id"] in only]
        assert len(tasks) == len(only), ("unknown task id", only)
    rows = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        semaphore = asyncio.Semaphore(4)

        async def check(task: dict):
            async with semaphore:
                context = await browser.new_context()
                page = await context.new_page()
                page.set_default_timeout(45000)
                markers = task["end_markers"]
                answer = task["expected_answer"]
                try:
                    start = await page.goto(task["start_url"], wait_until="domcontentloaded")
                    start_status = await _real_page(page, start)
                    start_evidence = await collect_page_evidence(page)
                    await _interact(page, task)
                    evidence = await collect_page_evidence(page)
                    # Literal presence, independent of the grader's case/space folding.
                    assert answer in evidence.text, (task["id"], "answer absent from runner evidence", evidence.text[:300])
                    verdict = evidence_verdict(markers, evidence, ClaimedEvidence(answer=answer))
                    assert verdict.verdict == "PASS", (task["id"], verdict)

                    negatives = []
                    wrong_pages = [] if task["id"] in START_IS_FINISHED else [start_evidence]
                    for decoy in DECOYS.get(task["id"], []):
                        wrong_pages.append(await _evidence_at(context, decoy))
                    assert wrong_pages, (task["id"], "no wrong page to check")
                    for wrong_page in wrong_pages:
                        wrong_page_verdict = evidence_verdict(markers, wrong_page, ClaimedEvidence(answer=answer))
                        assert wrong_page_verdict.verdict == "FAIL", (task["id"], "wrong page accepted", wrong_page.url, wrong_page_verdict)
                    negatives.append(f"{len(wrong_pages)} wrong pages FAIL")
                    variants = [page.url.split("#")[0] + "#ho3c", *VARIANTS.get(task["id"], [])]
                    for variant in variants:
                        moved = replace(evidence, url=variant, canonical="")
                        variant_verdict = evidence_verdict(markers, moved, ClaimedEvidence(answer=answer))
                        assert variant_verdict.verdict == "PASS", (task["id"], "correct URL variant rejected", variant, variant_verdict)
                    negatives.append(f"{len(variants)} URL variants PASS")
                    if task["id"] in WRONG_VALUES:
                        wrong = WRONG_VALUES[task["id"]]
                        assert wrong in evidence.text, (task["id"], "wrong value is not on the page", wrong)
                        wrong_verdict = evidence_verdict(markers, evidence, ClaimedEvidence(answer=wrong))
                        assert wrong_verdict.verdict == "FAIL", (task["id"], "wrong value accepted", wrong_verdict)
                        negatives.append("wrong value FAIL")
                    if task["id"] in SCRIPT_ONLY:
                        no_js_context = await browser.new_context(java_script_enabled=False)
                        try:
                            bare = await _evidence_at(no_js_context, page.url, javascript=False)
                        finally:
                            await no_js_context.close()
                        assert SCRIPT_ONLY[task["id"]] in evidence.text, (task["id"], "row text missing with JavaScript")
                        assert SCRIPT_ONLY[task["id"]] not in bare.text, (task["id"], "row visible without JavaScript")
                        negatives.append("absent without JS")
                    print(f"{task['id']}: {start_status}, {page.url}, {verdict.verdict}, {'; '.join(negatives)}", flush=True)
                    return task["id"], start_status, page.url, verdict.verdict, "; ".join(negatives)
                finally:
                    await context.close()

        try:
            results = await asyncio.gather(*(check(task) for task in tasks), return_exceptions=True)
        finally:
            await browser.close()

    failures = [(task["id"], result) for task, result in zip(tasks, results) if isinstance(result, BaseException)]
    for task_id, error in failures:
        print(f"{task_id}: ERROR {type(error).__name__}: {str(error)[:400]}", flush=True)
    rows = [result for result in results if not isinstance(result, BaseException)]
    print(f"heldout3c verify: {len(rows)}/{len(tasks)} PASS; every negative control FAIL and every URL variant PASS", flush=True)
    if failures:
        sys.exit(1)
    if not only:
        _write_report(rows)
    return rows


def _write_report(rows: list[tuple]) -> None:
    lines = [
        "# Heldout3c public-page verification", "",
        f"Verified {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} with local headless Chromium.", "",
        "This is page/marker validation, not an agent benchmark result. No LLM API calls or bench probes were run.",
        "Mix: 10 multi-step navigation, 10 value reports, 6 site searches, 6 submitted demo forms, 4 JavaScript-rendered pages, 4 page-title reports.",
        "Each task was driven from its start page by clicks, typing and form submits. Every page on the way returned HTTP 200 with no challenge page.",
        "Evidence was collected by the runner's real collect_page_evidence (including its text cap), then graded by evidence_verdict with expected_answer as the claimed answer. Every expected answer was also checked for literal presence in that evidence.",
        "Negative controls: the correct answer claimed on real wrong pages (the start page unless it is the finished page, plus listed decoys such as the page one step short, a neighbouring page, or the site's results page) must FAIL; a wrong value that is on the finished page must FAIL; for script-rendered tasks the answer's row must be absent when the page loads without JavaScript.",
        "URL controls: the finished page's evidence must still PASS at its URL with a #fragment and at listed equivalent URLs (trailing slash, bare host, other docs version, extra query).", "",
        "Reproduce: `python -m bench.verify_heldout3_c` (public network access; no model calls).", "",
        "| Task id | Start status | End URL | Verdict | Controls |",
        "| --- | --- | --- | --- | --- |",
    ]
    lines.extend(f"| {task_id} | {status} | {url} | {verdict} | {negative} |" for task_id, status, url, verdict, negative in rows)
    Path("docs/HELDOUT3C_VERIFY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(verify(sys.argv[1:] or None))
