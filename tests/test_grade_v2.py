"""Contract for scorer v2 (`key_v2` task keys). See docs/GRADER.md, "Scorer v2"."""

import pytest

from bench import grade

PASS, FAIL, UNKNOWN = grade.PASS, grade.FAIL, grade.UNKNOWN


def v2(key, url, text="", answer="", claimed=None):
    return grade.evidence_verdict_v2(
        key, grade.PageEvidence(url=url, text=text),
        claimed or grade.ClaimedEvidence(answer=answer),
    )


PAGE_KEY = {
    "deliverable": "page",
    "host": "sixflags.com",
    "pages": [{"path": "/frontiercity/attractions", "query": {"ride-category": {"any": ["family"]}}}],
    "reference": "Billy's Frog Hopper; Frankie's Mine Train; Grand Carousel",
}
RIDES = "Billy's Frog Hopper\nFrankie's Mine Train\nGrand Carousel\nHootie's Tree House"
FAMILY = "https://www.sixflags.com/frontiercity/attractions?ride-category=family"


def test_page_deliverable_accepts_a_list_answer_on_the_keyed_page():
    # extdev D17: v1 failed this row as "answer too long".
    assert v2(PAGE_KEY, FAMILY, "Rides & Experiences", RIDES).verdict == PASS


@pytest.mark.parametrize("url,reason", [
    ("https://www.sixflags.com/frontiercity/attractions?ride-category=thrill", "the final page is not an accepted page"),
    ("https://www.sixflags.com/frontiercity/attractions", "the final page is not an accepted page"),
    ("https://www.example.com/frontiercity/attractions?ride-category=family", "the final page is on the wrong host"),
    ("https://www.sixflags.com/search?q=family", "the page is denied (search)"),
    ("https://www.sixflags.com/signin?next=/frontiercity/attractions?ride-category=family", "the page is denied (/signin)"),
    ("", "no final page"),
])
def test_page_deliverable_rejects_wrong_pages(url, reason):
    result = v2(PAGE_KEY, url, "text", RIDES)
    assert (result.verdict, result.reason) == (FAIL, reason)


def test_page_deliverable_still_needs_a_report_and_rejects_failure_reports():
    assert v2(PAGE_KEY, FAMILY, "text", "").reason == "empty answer"
    for answer in ("Task failed: the page did not load.", "I couldn't find the family filter.",
                   "I was unable to apply the filter", "Unable to complete the task"):
        result = v2(PAGE_KEY, FAMILY, "text", answer)
        assert (result.verdict, result.reason) == (FAIL, "answer reports failure"), answer


def test_dump_guard_uses_the_written_reference():
    cap = 3 * len(PAGE_KEY["reference"]) + 300
    assert v2(PAGE_KEY, FAMILY, "t", "x" * cap).verdict == PASS
    assert v2(PAGE_KEY, FAMILY, "t", "x" * (cap + 1)).reason == "answer too long"


ANSWER_KEY = {
    "deliverable": "answer",
    "host": ["apec.org"],
    "facts": [["Elizabeth Galdo"]],
    "reference": "Elizabeth Galdo",
}


def test_answer_deliverable_is_judged_on_the_answer_anywhere_on_the_site():
    # extdev D53: right name, different apec.org page than the v1 URL key.
    url = "https://www.apec.org/meeting-papers/sectoral-ministerial-meetings/tourism/12th-apec-tourism-ministerial-meeting"
    assert v2(ANSWER_KEY, url, "page", "H.E. Mrs. Elizabeth Galdo Marín").verdict == PASS
    # A site search page is fine for an answer deliverable: the page is not the evidence.
    assert v2(ANSWER_KEY, "https://www.apec.org/search?q=x", "", "Elizabeth Galdo").verdict == PASS
    assert v2(ANSWER_KEY, "https://www.google.com/search?q=apec", "", "Elizabeth Galdo").reason == "the final page is on the wrong host"
    assert v2(ANSWER_KEY, url, "page", "Elizabeth Galdós").reason == "answer misses a required fact"
    assert v2(ANSWER_KEY, url, "page", "Someone else").reason == "answer misses a required fact"


def test_fact_matching_normalises_formatting_only():
    key = {"deliverable": "answer", "host": "x.org",
           "facts": [["May 23-28, 2004", "23-28 May 2004"], ["Anthony Finkelstein"], ["1000"],
                     ["DC Super-Villains Swing"], ["writer's gestalt"]],
           "reference": "May 23-28, 2004; Anthony Finkelstein; 1000; DC Super-Villains Swing; writer's gestalt"}
    answer = "**23–28 May 2004** — `Anthony  Finkelstein`; 1,000; DC Super‑Villains Swing™; the writer’s gestalt"
    assert v2(key, "https://x.org/a", "", answer).verdict == PASS
    assert v2(key, "https://x.org/a", "", answer.replace("23–28", "23–29")).verdict == FAIL
    # Token boundaries still hold: 10000 is not 1000.
    assert v2(key, "https://x.org/a", "", answer.replace("1,000", "10000")).verdict == FAIL


def test_fact_alternatives_can_be_all_of_groups_and_counted_lists():
    key = {"deliverable": "answer", "host": "x.org", "reference": "r",
           "facts": [{"any": [["King Denas", "Obelax", "Halfdan"], ["Linireans", "elves", "dwarves"]]},
                     {"any": ["5 stars", "4 stars", "Review score", "Wonderful: 9+"], "min": 2}]}
    url = "https://x.org/"
    assert v2(key, url, "", "King Denas, Obelax, Halfdan; 5 stars, Review score").verdict == PASS
    assert v2(key, url, "", "Linireans, elves and dwarves; 4 stars and Wonderful: 9+").verdict == PASS
    assert v2(key, url, "", "King Denas, Obelax; 5 stars, Review score").verdict == FAIL
    assert v2(key, url, "", "King Denas, Obelax, Halfdan; 5 stars").verdict == FAIL


AIRBNB = {
    "deliverable": "page", "host": "airbnb.com", "reference": "r",
    "pages": [
        {"path": "/s/Europe/homes",
         "query": {"category_tag": {"any": ["Tag:8047"]}, "price_max": {"max": 1000},
                   "flexible_trip_lengths[]": {"any": ["one_week"]},
                   "flexible_trip_dates[]": {"any": ["december"]}}},
        {"path": "/s/Europe/homes",
         "query": {"kg_and_tags[]": {"any": ["Tag:8047"]}, "price_max": {"max": 1000},
                   "checkin": {"prefix": "2026-12-"}},
         "stay_nights": 7},
    ],
}


@pytest.mark.parametrize("url,ok", [
    ("https://www.airbnb.com/s/Europe/homes?category_tag=Tag%3A8047&price_max=1000&flexible_trip_lengths%5B%5D=one_week&flexible_trip_dates%5B%5D=december", True),
    ("https://www.airbnb.com/s/Europe/homes?kg_and_tags%5B%5D=Tag%3A8047&price_max=999&checkin=2026-12-01&checkout=2026-12-08", True),
    ("https://www.airbnb.com/s/Europe/homes?kg_and_tags%5B%5D=Tag%3A8047&price_max=1001&checkin=2026-12-01&checkout=2026-12-08", False),
    ("https://www.airbnb.com/s/Europe/homes?kg_and_tags%5B%5D=Tag%3A8047&price_max=999&checkin=2026-12-01&checkout=2026-12-05", False),
    ("https://www.airbnb.com/s/Europe/homes?kg_and_tags%5B%5D=Tag%3A8115&price_max=999&checkin=2026-12-01&checkout=2026-12-08", False),
    ("https://www.airbnb.com/s/Europe/homes?category_tag=Tag%3A8047&price_max=abc&flexible_trip_lengths%5B%5D=one_week&flexible_trip_dates%5B%5D=december", False),
])
def test_query_conditions(url, ok):
    assert (v2(AIRBNB, url, "t", "Castles in Europe set.").verdict == PASS) is ok


def test_has_and_contains_conditions_for_comma_lists_and_search_words():
    key = {"deliverable": "page", "host": "amazon.com", "reference": "r", "allow_search": True,
           "pages": [{"path": "/s", "query": {"s": {"any": ["price-asc-rank"]},
                                              "rh": {"has": "p_72:2661618011"},
                                              "k": {"contains": ["puppy", "puppies"]}}}]}
    good = "https://www.amazon.com/s?k=puppy+dog+food&rh=p_n_g-1%3A2%2Cp_72%3A2661618011&s=price-asc-rank"
    assert v2(key, good, "t", "Sorted.").verdict == PASS
    assert v2(key, good.replace("2661618011", "1248880011"), "t", "Sorted.").verdict == FAIL
    assert v2(key, good.replace("puppy", "cat"), "t", "Sorted.").verdict == FAIL
    assert v2(key, good.replace("price-asc-rank", "review-rank"), "t", "Sorted.").verdict == FAIL


def test_page_text_condition_needs_a_page_read():
    key = {"deliverable": "page", "host": "store.steampowered.com", "reference": "r",
           "pages": [{"path": "/cart/", "text": ["The Dota 2 Official Soundtrack"]},
                     {"path": "/app/570/", "text": ["Added to your cart!", "The Dota 2 Official Soundtrack"]}]}
    cart = "https://store.steampowered.com/cart/?snr=1"
    app = "https://store.steampowered.com/app/570/Dota_2/"
    assert v2(key, cart, "Your Shopping Cart (1 item) The Dota 2 Official Soundtrack $9.99", "Done.").verdict == PASS
    assert v2(key, cart, "Your Shopping Cart (0 items)", "Done.").reason == "the final page is not an accepted page"
    assert v2(key, app, "Added to your cart! The Dota 2 Official Soundtrack $9.99", "Done.").verdict == PASS
    assert v2(key, app, "Play Dota 2", "Done.").verdict == FAIL
    assert v2(key, cart, "", "Done.").verdict == UNKNOWN


def test_both_deliverable_needs_page_and_facts():
    key = {"deliverable": "both", "host": "spothero.com", "reference": "Marketing Analyst (Chicago, IL)",
           "pages": [{"path": "/careers"}], "facts": [["Marketing Analyst"]]}
    assert v2(key, "https://spothero.com/careers", "t", "Marketing Analyst").verdict == PASS
    assert v2(key, "https://spothero.com/careers", "t", "Product Manager").verdict == FAIL
    assert v2(key, "https://spothero.com/about", "t", "Marketing Analyst").verdict == FAIL


def test_script_return_gate_still_applies():
    url = "https://www.apec.org/x"
    bad = grade.ClaimedEvidence(answer="Elizabeth Galdo", key_text="invented text")
    assert v2(ANSWER_KEY, url, "page text", claimed=bad).reason == "returned evidence is not on the page"
    other = grade.ClaimedEvidence(answer="Elizabeth Galdo", url="https://www.apec.org/elsewhere")
    assert v2(ANSWER_KEY, url, "page text", claimed=other).reason == "claimed URL does not match the live page"


@pytest.mark.parametrize("key", [
    {"deliverable": "page", "host": "x.org", "reference": "r"},
    {"deliverable": "answer", "host": "x.org", "reference": "r"},
    {"deliverable": "maybe", "host": "x.org", "reference": "r", "facts": [["a"]]},
    {"deliverable": "answer", "reference": "r", "facts": [["a"]]},
    {"deliverable": "answer", "host": "x.org", "facts": [["a"]]},
    {"deliverable": "answer", "host": "x.org", "reference": "r", "facts": [[]]},
])
def test_malformed_keys_fail_closed(key):
    assert v2(key, "https://x.org/", "a", "a").reason == "invalid v2 key"


def test_grade_observation_dispatches_on_key_v2_and_keeps_the_completion_gate():
    task = {"id": "t", "check_url_contains": "/never", "key_v2": PAGE_KEY,
            "end_markers": {"host": "sixflags.com", "url_contains": "/never", "answer_in_text": "Family"}}
    assert grade.grade_observation(task, FAMILY, "text", answer=RIDES)[:2] == (True, "the final page matches the key")
    assert grade.grade_page_answer(task, FAMILY, "text", answer=RIDES) == (True, "the final page matches the key")
    assert grade.grade_observation(task, FAMILY, "text", answer=RIDES, completed=False)[0] is False
    assert grade.shared_end_state(task, FAMILY, "text", answer=RIDES)[0] is True
    # Tasks without key_v2 keep the v1 rules unchanged.
    legacy = {k: v for k, v in task.items() if k != "key_v2"}
    assert grade.grade_observation(legacy, FAMILY, "text", answer=RIDES)[0] is False
