"""Twelve fresh search tasks, authored before the search specialist.

Judge-only destinations; runtime strategies receive description/start_url only.
Hosts checked against the owner's used_hosts.txt on 2026-11-14.
"""


def _task(slug, description, start, host, path, title):
    return {
        "id": "dev4search_search_" + slug,
        "description": description + " Use the site's search and open the actual page; do not stop at results.",
        "start_url": start,
        "expected_answer": title,
        "check_url_contains": path,
        "end_markers": {
            "host": host, "path_suffix": path, "url_contains": path,
            "deny": ["/search", "search.html", "Special:Search", "?search="],
        },
    }


DEV4_SEARCH_TASKS = [
    _task("ubuntu_ripgrep", "Find the Ubuntu Noble package details for the ripgrep command-line search utility.",
          "https://packages.ubuntu.com/", "packages.ubuntu.com", "/noble/ripgrep", "Package: ripgrep"),
    _task("ubuntu_jq", "Find the Ubuntu Noble package details for the jq JSON command-line processor.",
          "https://packages.ubuntu.com/", "packages.ubuntu.com", "/noble/jq", "Package: jq"),
    _task("mediawiki_jobs", "On MediaWiki, find the administrator manual page explaining its background job queue.",
          "https://www.mediawiki.org/wiki/MediaWiki", "www.mediawiki.org", "/wiki/Manual:Job_queue", "Manual:Job queue"),
    _task("mediawiki_namespaces", "On MediaWiki, find the help page that explains namespaces to wiki users.",
          "https://www.mediawiki.org/wiki/MediaWiki", "www.mediawiki.org", "/wiki/Help:Namespaces", "Help:Namespaces"),
    _task("scrapy_selectors", "In the stable Scrapy documentation, find the guide to extracting page data with CSS and XPath expressions.",
          "https://docs.scrapy.org/en/latest/", "docs.scrapy.org", "/en/latest/topics/selectors.html", "Selectors"),
    _task("scrapy_requests", "In the stable Scrapy documentation, find the reference page describing Request and Response objects together.",
          "https://docs.scrapy.org/en/latest/", "docs.scrapy.org", "/en/latest/topics/request-response.html", "Requests and Responses"),
    _task("astropy_units", "In the stable Astropy documentation, find the main guide to attaching physical measurement units to numerical values.",
          "https://docs.astropy.org/en/stable/", "docs.astropy.org", "/en/stable/units/index.html", "Units and Quantities"),
    _task("astropy_tables", "In the stable Astropy documentation, find the main guide to working with tabular datasets.",
          "https://docs.astropy.org/en/stable/", "docs.astropy.org", "/en/stable/table/index.html", "Data Tables"),
    _task("pydantic_validators", "In Pydantic's current documentation, find the concepts guide to custom field and model validation functions.",
          "https://pydantic.dev/docs/validation/latest/get-started/", "pydantic.dev", "/docs/validation/latest/concepts/validators/", "Validators"),
    _task("pydantic_serialization", "In Pydantic's current documentation, find the concepts guide to converting models into dictionaries and JSON.",
          "https://pydantic.dev/docs/validation/latest/get-started/", "pydantic.dev", "/docs/validation/latest/concepts/serialization/", "Serialization"),
    _task("fastapi_background", "In the FastAPI tutorial, find the page about running work after returning a response to the client.",
          "https://fastapi.tiangolo.com/", "fastapi.tiangolo.com", "/tutorial/background-tasks/", "Background Tasks"),
    _task("fastapi_cors", "In the FastAPI tutorial, find the page about configuring cross-origin resource sharing for a browser frontend.",
          "https://fastapi.tiangolo.com/", "fastapi.tiangolo.com", "/tutorial/cors/", "CORS (Cross-Origin Resource Sharing)"),
]

DEV4_SEARCH_TASK_IDS = tuple(t["id"] for t in DEV4_SEARCH_TASKS)
