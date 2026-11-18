"""Write DISAGREEMENTS.md/.csv: why the v1 grader and the extdev hand labels disagree.

Run after agreement.py, from the repository root:
    python docs/results/scorer_v2_20261118/build_disagreements.py
"""

import csv
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
STRICT = "grader rule too strict"
NARROW = "key wrong/too narrow"
AMBIG = "genuinely ambiguous"
LSTRICT = "label too strict"

# One cause per task unless a row overrides it. Written from each row's task, final URL,
# answer and saved page text (docs/results/extdev_control_20261117).
BY_TASK = {
    "extdev_filter_greatamerica_thrill": (STRICT, "Page task judged by answer text: on the keyed thrill filter page, the answer lists the rides but not the word 'Thrill'."),
    "extdev_filter_frontiercity_family": (STRICT, "Page task judged by answer length: the family filter page was reached; a 7-ride list exceeded the 3x+40 bound of the marker 'Family'."),
    "extdev_spa_dota_dlc_cart": (STRICT, "Cart page shows 'Your Shopping Cart (1 item) The Dota 2 Official Soundtrack'; a one-sentence answer exceeded the length bound."),
    "extdev_filter_booking_times_square": (NARROW, "Key accepted one hotel on one search URL; the answer is another 4-star Times Square hotel shown on the saved Booking page."),
    "extdev_nav_spothero_contact": (STRICT, "On /contact (the keyed page); the answer explains the form and failed the marker length bound."),
    "extdev_filter_airbnb_europe_mansions": (STRICT, "URL carries category_tag=Tag:8115, adults=3, flexible dates; the answer text lacked the literal parts 'mansions', 'Any month', '3 guests'."),
    "extdev_value_icse_2004_chair": (NARROW, "Value task tied to /history.html."),
    "extdev_value_rovio_anniversary": (NARROW, "Both facts right; ended on the Eeva Aaltonen article not the keyed URL; 'The Angry Birds Movie 3' is the third installment."),
    "extdev_value_apec_tourism_actions": (NARROW, "Quotes the keyed statement text; ended on the tourism overview page (it links the statement under /tourism/, not the keyed /general/ path)."),
    "extdev_value_apec_ministers_chair": (NARROW, "'Elizabeth Galdo Marin' is right; ended on the ministerial statement page, not the keyed press release."),
    "extdev_search_booking_la_filters": (NARROW, "Key required the review-score block verbatim with newlines; answers list real filters from the saved 'Filter by:' block."),
    "extdev_value_hf_first_user_message": (NARROW, "Exact message returned; key tied to the viewer URL (the dataset card shows the same message)."),
    "extdev_nav_ronaldo_world_cup_stats": (STRICT, "On the keyed World Cup stats URL; the requested table exceeded the length bound of the marker 'FIFA World Cup'."),
    "extdev_nav_fiestatexas_events": (NARROW, "Task allows any Six Flags park in Texas; key accepted only Fiesta Texas."),
    "extdev_nav_spothero_marketing": (NARROW, "Careers page lists 'Marketing Marketing Analyst'; key required the single role page /careers/8069541."),
    "extdev_filter_amazon_puppy_food": (NARROW, "URL has rh p_72:2661618011 and s=price-asc-rank; key required the literal search words 'dog food for puppies' and an exact rh string."),
    "extdev_nav_eventbrite_planning": (STRICT, "On the keyed blog category page; a URL answer wrapped in one sentence was rejected."),
    "extdev_filter_sam_harris_paperback": (NARROW, "The End of Faith shows '4.5 out of 5 stars ... Paperback' on the saved page; key accepted only Free Will via a filter URL."),
    "extdev_nav_steam_daily_players": (STRICT, "On /charts/mostplayed, page shows 'By Daily Players'; a one-line answer exceeded the length bound."),
    "extdev_value_dream_blast_revenue": (NARROW, "Right game; ended on the 2019 results article, key tied to the 2022 report URL."),
    "extdev_value_pirate_treasures": (AMBIG, "Source answer names the customers (Linireans, elves, dwarves); the agent named the characters at the opening (King Denas, Obelax, Halfdan), also in article 372. Key required both."),
    "extdev_value_ironhide_historical_games": (NARROW, "Iron Marines and Kingdom Rush Origins are right; key required full headlines on one URL."),
    "extdev_value_cambridge_euphoria": (STRICT, "Answer equals the key; the saved page is a security-verification screen, so v1 grounding in page text failed."),
    "extdev_value_cambridge_innovate": (STRICT, "Answer equals the key; the saved page is a security-verification screen, so v1 grounding in page text failed."),
    "extdev_value_booking_parent": (NARROW, "'Booking Holdings Inc.' is right; ended on the home page, key tied to /content/about.html."),
    "extdev_filter_tiny_home_dates": (NARROW, "A tiny-home listing ('Tiny home in Port Ludlow') with adults=1, pets=2, Apr 10-12; key required the search-results URL."),
    "extdev_filter_sf_exercise_dates": (STRICT, "On the keyed URL with the date range; the event list exceeded the length bound."),
    "extdev_filter_castles_europe_week": (NARROW, "kg_and_tags[]=Tag:8047, price_max=999, Dec 1-8 (7 nights); key required category_tag, price_max=1000 and flexible-week parameters."),
    "extdev_value_hf_tei_strengths": (NARROW, "Summary task keyed by six verbatim sentences; answers paraphrase every listed strength."),
    "extdev_value_icse_2002_chairs": (NARROW, "Key joined the chairs with a newline ('Michal Young<newline>Jeff Magee'); answers write 'Michal Young and Jeff Magee'."),
    "extdev_value_cambridge_gestalt": (NARROW, "Key meaning part ends with ':' copied from the page; the answer gives the meaning without it."),
    "extdev_value_ironhide_arcade_gdc": (LSTRICT, "Answer is the source answer 'Kingdom Rush and Junkworld'; labelled partial only because the final page does not show the GDC prize."),
}
ROW = {
    "D9": (NARROW, "Steam's add-to-cart confirmation on the app page ('Added to your cart! The Dota 2 Official Soundtrack'); key required the /cart/ URL."),
    "D24": (STRICT, "On /contact; the answer is the support phone number shown there, rejected for lacking the marker 'Contact Customer Heroes'."),
    "D64": (NARROW, "On the keyed viewer URL with the exact message; the v1 marker held a literal backslash-n, so it could not match an answer with a real newline."),
    "U12": (STRICT, "Quotes the keyed statement text; ended on an apec.org search page, which v1 denies even for an answer task."),
    "D40": (AMBIG, "Chairs and place right; 'May 19-24, 2002' is what the same site's history.html says (committee page says 19-25). Also ended on history.html, not the keyed URL."),
    "D32": (NARROW, "Dates and chair right, from the 2004 organising committee page; key tied to /history.html and the 'May 23-28, 2004' rendering."),
}


def main():
    rows = list(csv.DictReader((HERE / "extdev_rows.csv").open(encoding="utf-8")))
    out = []
    for r in rows:
        truth = r["label_original"] == "correct"
        if (r["v1_final"] == "PASS") == truth and (r["v2_final"] == "PASS") == truth:
            continue
        cls, why = ROW.get(r["row"]) or BY_TASK[r["task_id"]]
        out.append({"row": r["row"], "arm": r["arm"], "task_id": r["task_id"], "v1": r["v1_final"],
                    "v1_reason": r["v1_reason"].split(" '")[0], "label": r["label_original"], "class": cls,
                    "why": why, "v2": r["v2_final"], "v2_reason": r["v2_reason"]})
    with (HERE / "DISAGREEMENTS.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(out[0]))
        writer.writeheader()
        writer.writerows(out)
    counts = Counter(o["class"] for o in out)
    lines = ["# Extdev disagreements: v1 grader vs hand labels", "",
             "Every extdev row where the v1 grader or scorer v2 disagrees with the original hand label",
             "(`docs/results/extdev_hand_labels_20261117/hand_labels.csv`). Each was read from the task, the saved",
             "final URL, the answer and the saved page text. Machine-readable: `DISAGREEMENTS.csv`.", "",
             "| Class | Rows |", "|---|---:|"]
    lines += [f"| {k} | {v} |" for k, v in counts.most_common()]
    lines += ["", "Classes: *grader rule too strict*: a v1 rule rejects a correct outcome whatever the key.",
              "*key wrong/too narrow*: the key's URL or literal text excludes correct outcomes, or is malformed.",
              "*genuinely ambiguous*: the task or the site supports two readings. *label too strict*: the label",
              "is stricter than the written v2 rules (corrected in `extdev_label_corrections.csv`).",
              "No row is classed *label too lenient*; AGREEMENT.md lists the rule choices that a stricter rubric",
              "would flip, row by row.", "",
              "| Row | Arm | Task | v1 | v1 reason | Label | Class | Why | v2 |", "|---|---|---|---|---|---|---|---|---|"]
    for o in out:
        cells = [o["row"], o["arm"], o["task_id"].removeprefix("extdev_"), o["v1"], o["v1_reason"],
                 o["label"], o["class"], o["why"].replace("|", "/"), o["v2"]]
        lines.append("| " + " | ".join(cells) + " |")
    (HERE / "DISAGREEMENTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(len(out), dict(counts))


if __name__ == "__main__":
    main()
