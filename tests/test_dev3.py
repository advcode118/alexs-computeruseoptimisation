"""Offline catalog invariants for dev3; never open a browser or call a model."""

import re
from collections import Counter
from urllib.parse import urlsplit

from bench.script_first import ClaimedEvidence, PageEvidence, evidence_verdict
from bench.tasks import DEV3_TASK_IDS, get_all_tasks, resolve_task_split, tasks_for_split

# Hosts already used by other task sets when dev3 was written (13 Nov 2026).
USED_HOSTS = (
    "apache.org arxiv.org bipm.org blog.jquery.com bonigarcia.dev books.toscrape.com bstackdemo.com "
    "calculator.net chemicool.com clickhouse.com clojure.org cmake.org crates.io creativecommons.org "
    "crontab.guru ctan.org curl.se dart.dev datatables.net debian.org demoblaze.com desmos.com "
    "developer.mozilla.org doc.rust-lang.org docs.ansible.com docs.blender.org docs.djangoproject.com "
    "docs.docker.com docs.julialang.org docs.oracle.com docs.pytest.org docs.python.org docs.pytorch.org "
    "docs.scipy.org duckdb.org ecma-international.org en.cppreference.com en.wikipedia.org en.wiktionary.org "
    "eslint.org flask.palletsprojects.com formulae.brew.sh freebsd.org geonames.org getbootstrap.com "
    "git-scm.com github.blog github.com globalsqa.com go.dev gov.uk graphviz.org gutenberg.org haskell.org "
    "helm.sh httpbin.org httpbingo.org iana.org iban.com ietf.org imagemagick.org jekyllrb.com julialang.org "
    "kernel.org kotlinlang.org kubernetes.io lipsum.com llvm.org loc.gov make.wordpress.org man.openbsd.org "
    "man7.org manpages.debian.org material.angular.dev mathsisfun.com musicbrainz.org nextjs.org nginx.org "
    "nim-lang.org nist.gov nobelprize.org nodejs.org npmjs.com nssdc.gsfc.nasa.gov numpy.org ocaml.org "
    "oeis.org openbsd.org pandas.pydata.org petstore.swagger.io php.net pkg.go.dev pkgs.alpinelinux.org "
    "playwright.dev pokeapi.co pokemondb.net postgresql.org practice.expandtesting.com "
    "practicetestautomation.com projecteuler.net pypi.org qa-practice.com quotes.toscrape.com "
    "rahulshettyacademy.com rcsb.org react.dev redis.io rfc-editor.org rubygems.org saucedemo.com schema.org "
    "scikit-learn.org scrapethissite.com scrapingcourse.com selenium.dev spdx.org sphinx-doc.org sqlite.org "
    "ssd.jpl.nasa.gov stackoverflow.blog standardebooks.org tailwindcss.com tcl-lang.org "
    "testpages.eviltester.com testpages.herokuapp.com the-internet.herokuapp.com typescriptlang.org "
    "ultimateqa.com unicode.org vuejs.org w3.org w3schools.com webdriveruniversity.com webscraper.io "
    "wiki.openstreetmap.org wiki.videolan.org wikidata.org wordpress.org xkcd.com"
).split()

# Public suffixes with a dot that these hosts can sit under. Enough for this catalog.
_MULTI_SUFFIXES = {"herokuapp.com", "github.io", "co.uk", "ac.uk", "gov.uk", "gov.au", "blogspot.com", "netlify.app", "vercel.app"}

# Same-page tasks: the result appears on the start URL itself.
_SAME_PAGE = {"dev3_form_demoqa_textbox", "dev3_form_demoqa_practice", "dev3_form_aito_contact", "dev3_form_guru99_register", "dev3_spa_demoqa_origin"}


def registrable(host: str) -> str:
    labels = host.casefold().strip(".").split(".")
    if ".".join(labels[-2:]) in _MULTI_SUFFIXES:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def _hosts(task: dict) -> set[str]:
    hosts = {urlsplit(task["start_url"]).hostname}
    marker = (task.get("end_markers") or {}).get("host")
    hosts.update(marker if isinstance(marker, (list, tuple)) else [marker])
    return {host for host in hosts if host}


def test_dev3_split_has_forty_unique_complete_tasks():
    tasks = tasks_for_split("dev3")
    assert resolve_task_split("dev3") == "dev3"
    assert len(tasks) == len(DEV3_TASK_IDS) == 40
    ids = [task["id"] for task in tasks]
    assert len(set(ids)) == 40
    assert tuple(ids) == DEV3_TASK_IDS
    catalog_ids = [task["id"] for task in get_all_tasks()]
    assert all(catalog_ids.count(task_id) == 1 for task_id in ids)
    kinds = Counter(task_id.split("_")[1] for task_id in ids)
    assert all(task_id.startswith("dev3_") for task_id in ids)
    assert kinds == {"nav": 10, "value": 10, "search": 6, "form": 6, "title": 4, "spa": 4}
    required = {"id", "description", "start_url", "expected_answer", "check_url_contains", "end_markers"}
    for task in tasks:
        assert required <= task.keys() and all(task[key] for key in required), task["id"]
        assert task["start_url"].startswith("https://")
        markers = task["end_markers"]
        assert {"host", "url_contains", "deny"} <= markers.keys()
        assert task["check_url_contains"] in markers["url_contains"]
        assert "https://" not in task["description"]
        assert not re.search(r"(?<!\w)" + re.escape(task["expected_answer"]) + r"(?!\w)", task["description"], re.I), task["id"]
        assert task["expected_answer"] not in task["start_url"]
        if task["id"] not in _SAME_PAGE:
            assert markers["url_contains"] not in task["start_url"], task["id"]
        if not task["id"].startswith(("dev3_nav_", "dev3_search_")):
            assert markers["answer_in_text"] == task["expected_answer"], task["id"]


def test_dev3_sites_are_a_to_m_capped_and_new():
    tasks = tasks_for_split("dev3")
    per_site = Counter()
    for task in tasks:
        sites = {registrable(host) for host in _hosts(task)}
        assert len(sites) == 1, (task["id"], sites)
        site = sites.pop()
        assert "a" <= site[0] <= "m", (task["id"], site)
        per_site[site] += 1
    assert max(per_site.values()) <= 3, per_site.most_common(3)
    assert len(per_site) >= 25, len(per_site)
    used = {registrable(host) for host in USED_HOSTS}
    for name in ("probe", "dev", "held-out", "heldout2", "heldout3"):
        for task in tasks_for_split(name):
            used.update(registrable(host) for host in _hosts(task))
    assert not used & set(per_site), sorted(used & set(per_site))


def test_dev3_is_disjoint_from_other_splits():
    new_ids = set(DEV3_TASK_IDS)
    for name in ("probe", "dev", "held-out", "honest", "heldout2", "heldout3"):
        assert new_ids.isdisjoint(task["id"] for task in tasks_for_split(name))


def test_dev3_value_markers_require_the_value_not_a_heading():
    # Synthetic evidence checks marker wiring. Live pages are in bench.verify_dev3.
    for task in tasks_for_split("dev3"):
        markers = task["end_markers"]
        if not markers.get("answer_in_text"):
            continue
        token = markers["url_contains"]
        end = "https://" + markers["host"] + (token if token.startswith("/") else "/")
        suffix = markers.get("path_suffix") or ""
        if suffix and not end.endswith(suffix):
            end += suffix.rsplit("/", 1)[-1]
        evidence = PageEvidence(url=end, h1="Unrelated page heading", text="Unrelated page heading\n" + task["expected_answer"])
        assert evidence_verdict(markers, evidence, ClaimedEvidence(answer=task["expected_answer"])).verdict == "PASS", task["id"]
        assert evidence_verdict(markers, evidence, ClaimedEvidence(answer=evidence.h1)).verdict == "FAIL", task["id"]


def test_dev3_dry_plan_lists_tasks_without_a_spend_ledger(monkeypatch):
    from bench.probe import LedgerMissing, SpendLedger, plan_probe

    def missing_ledger(*args, **kwargs):
        raise LedgerMissing("No shared ledger on this offline machine")

    monkeypatch.setattr(SpendLedger, "load", missing_ledger)
    plan = plan_probe(split="dev3")
    assert plan["execute"] is False
    assert plan["split"] == "dev3"
    assert plan["tasks"] == list(DEV3_TASK_IDS)
    assert plan["project_spent_usd"] is None
