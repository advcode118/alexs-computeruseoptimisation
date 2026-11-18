"""Write KEY_CHANGES.md: every extdev key, v1 -> v2, with the page fact behind each change.

Run from the repository root:
    python docs/results/scorer_v2_20261118/build_key_changes.py
"""

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
HERE = Path(__file__).resolve().parent
RAW = "docs/results/extdev_control_20261117"
D, U, S = (f"{RAW}/raw/probe_20261117_012232.jsonl", f"{RAW}/raw/probe_20261117_015118.jsonl",
           f"{RAW}/smoke/probe_20261117_011924.jsonl")

SAME = "same content"
# (change summary or SAME, [evidence lines]). Row ids: D/U/S + line in regraded_rows.csv
# (see extdev_rows.csv for the file); quotes are from the row's saved grade_page_text unless
# a URL is given, in which case the quote is from a plain HTTP GET on 18 Nov 2026.
CHANGES = {
    "extdev_filter_greatamerica_thrill": (SAME, ["Page deliverable: the answer no longer has to contain 'Thrill' (rule change, not key change)."]),
    "extdev_value_nba_2021_leaders": ("Accepts 'Jimmy Butler' for 'Jimmy Butler III'.", [
        "Same player; the v1 numbers stay required."]),
    "extdev_spa_dota_dlc_cart": ("Cart page must show the soundtrack; also accepts Steam's add-to-cart confirmation on the Dota 2 app page.", [
        "U3 (cart): \"Your Shopping Cart (1 item) The Dota 2 Official Soundtrack $9.99\".",
        "D9 (app/570): \"Cart 1 Added to your cart! The Dota 2 Official Soundtrack $9.99 For my account Remove Continue Shopping View My Cart (1)\"."]),
    "extdev_filter_booking_times_square": ("Answer task: any of three cited 4-star Times Square hotels; the search URL and '2 adults' part are no longer required.", [
        "D13 (booking.com/fourstars/city/us/new-york.html): \"The best 4-star hotels in New York ... LUMA Hotel - Times Square Hotel in Manhattan, New York Located 984 feet from Times Square\".",
        "U4 (district/us/new-york/timessquare.html): \"Riu Plaza Manhattan Times Square Hotel in Times Square, New York ... This 4-star hotel offers room service\".",
        "'2 adults' is Booking's default occupancy: D13 and U4 both show \"Select occupancy 2 adults · 0 children · 1 room\"."]),
    "extdev_filter_frontiercity_family": (SAME, ["Page deliverable; reference list from D17: \"See Our Rides Billy's Frog Hopper Frankie's Mine Train Grand Carousel Hootie's Tree House Ol' 89er Express Quick Draw Rocky's Ranger Planes\"."]),
    "extdev_nav_spothero_contact": (SAME, ["Page deliverable on /contact; D21 page: \"Contact Customer Heroes Give us a call ... +1 (844) 324-7768 Every day, 6am-11pm CST\"."]),
    "extdev_filter_airbnb_europe_mansions": ("Narrowed to the task's own constraints (Europe path, adults=3, flexible dates); accepts Airbnb's kg_and_tags[] alias for the category tag.", [
        "Task text: \"mansions for 3 adults ... in europe during any month\".",
        "D27 URL: \"/s/Europe/homes?adults=3&category_tag=Tag%3A8115&...&date_picker_type=flexible_dates\".",
        "Alias: U40 URL carries the castle tag as \"kg_and_tags%5B%5D=Tag%3A8047 ... selected_filter_order%5B%5D=kg_and_tags%3ATag%3A8047\"."]),
    "extdev_value_icse_2004_chair": ("Answer task (any icse-conferences.org page); accepts the day-month rendering '23-28 May 2004'.", [
        "D31 (2004/index.html): \"hosted the ICSE conference from 23rd to 28th May\" (the site's own day-month order); same dates."]),
    "extdev_value_icse_duplicate_statement": ("v1 phrase split into its three facts (place, venue, month).", [
        "v1 marker \"Charleston, South Carolina at FSE-10 in November 2002\"."]),
    "extdev_value_rovio_anniversary": ("Person by name (title optional); project also as 'Angry Birds Movie 3'.", [
        "https://www.rovio.com/articles/angry-birds-celebrates-15th-anniversary-with-special-in-game-events-and-more/: \"said Eeva Aaltonen , Head of Brand Operations at Rovio\"; \"announced the third installment of The Angry Birds Movie series\".",
        "https://en.wikipedia.org/wiki/The_Angry_Birds_Movie_3: \"The Angry Birds Movie 3 is an upcoming animated comedy film ... the third installment in the Angry Birds film series\"."]),
    "extdev_value_apec_tourism_actions": ("v1 parts shortened to their facts: 'Regenerative Tourism', the well-being list, 'resilient tourism ecosystems'.", [
        "v1 parts (authored from the 12th APEC Tourism Ministerial statement)."]),
    "extdev_value_apec_peru_arrivals": (SAME, ["v1 marker \"4.4 million\"."]),
    "extdev_value_apec_ministers_chair": (SAME, ["v1 marker \"Elizabeth Galdo\"; the URL is no longer required (answer task)."]),
    "extdev_search_booking_la_filters": ("Any two filter names from the page's filter block, instead of the review-score block verbatim.", [
        "D57 (booking.com/city/us/los-angeles.html): \"Filter by: Property ratingIncludes stars and other ratings. 5 stars 4 stars 3 stars 2 stars 1 star Review score Wonderful: 9+ Very Good: 8+ Good: 7+ Pleasant: 6+\".",
        "Task text: \"list some of them\"."]),
    "extdev_value_hf_first_user_message": ("Fixed a malformed key: v1 held a literal backslash-n; split into the three sentences.", [
        "D64 (viewer page): \"\\\"content\\\": \\\"Please provide a reasonable subgoal-based plan to solve the given task.\\nTask: What was the opening date ...\\\"\" (the viewer shows the JSON escape)."]),
    "extdev_value_hf_tei_strengths": ("Summary task: one distinctive term per listed strength instead of six verbatim sentences.", [
        "v1 parts, each authored verbatim from huggingface.co/docs/text-embeddings-inference/index; terms: Flash Attention, Candle, cuBLASLt, graph compilation, Docker, boot time, dynamic batching, Safetensors, Open Telemetry, Prometheus."]),
    "extdev_value_icse_2002_chairs": ("Chairs as two facts (v1 joined them with a newline); also accepts 'May 19-24, 2002'.", [
        "D37 (2002/info/ccommittee.html): \"Orlando, Florida, USA May 19-25, 2002\".",
        "D40 (history.html, same site): \"24th ICSE 2002 Orlando, Florida, USA May 19-24, 2002 ... Michal Young, University of Oregon, USA and Jeff Magee\"."]),
    "extdev_value_cambridge_gestalt": ("Meaning part without the trailing ':'; accepts the US IPA too.", [
        "S2: \"UK /ɡəˈʃtælt/ US /ɡəˈʃtɑːlt/ ... has qualities that are more than the total of all its parts: This new biography is the first to consider fully the writer's gestalt.\""]),
    "extdev_nav_ronaldo_world_cup_stats": (SAME, ["Page deliverable on the v1 URL; reference is the World Cup table on that page (D72)."]),
    "extdev_nav_nets_schedule": (SAME, ["v1 URL."]),
    "extdev_nav_fiestatexas_events": ("Also accepts Six Flags Over Texas events.", [
        "Task text: \"all the events at any six flags park in Texas\".",
        "https://www.sixflags.com/overtexas: page heading \"Six Flags Over Texas\" and \"Hurricane Harbor Arlington\"."]),
    "extdev_nav_spothero_marketing": ("Careers page plus 'Marketing Analyst' in the answer, instead of the single role page.", [
        "D81 (spothero.com/careers): \"Engineering ... Marketing Marketing Analyst Product Product Manager, Acquisitions\"."]),
    "extdev_filter_amazon_puppy_food": ("Search words may be any phrase with 'puppy'/'puppies'; rh must include p_72:2661618011 among other filters.", [
        "D85 (amazon.com/s?k=puppy+dog+food&rh=p_72%3A2661618011&s=price-asc-rank...): \"1-48 of over 1,000 results for \\\"puppy dog food\\\" Sort by: ... Price: Low to High\".",
        "U22 URL: \"rh=p_n_g-101015646925111%3A204428486011%2Cp_72%3A2661618011\" (Amazon joins filters with commas)."]),
    "extdev_nav_eventbrite_planning": (SAME, ["v1 URL."]),
    "extdev_filter_sam_harris_paperback": ("Answer task: Free Will or The End of Faith; the filter URL is no longer required.", [
        "U24 (amazon.com/s?k=Sam+Harris+paperback): \"The End of Faith: Religion, Terror, and the Future of Reason by Sam Harris | Sep 17, 2005 4.5 4.5 out of 5 stars (3.3K) Paperback\"."]),
    "extdev_nav_steam_daily_players": ("v1 marker moved from the answer to the page text.", [
        "U25 (store.steampowered.com/charts/mostplayed): \"MOST PLAYED Top 100 played games By Daily Players RANK PRICE CHANGE PEAK TODAY\"."]),
    "extdev_nav_commuter_benefits": (SAME, ["v1 URL."]),
    "extdev_value_dream_blast_revenue": ("Accepts 'Dream Blast' (v1 'Angry Birds Dream Blast').", ["Same game; v1 marker."]),
    "extdev_value_pirate_treasures": ("Characters: either the named characters at the opening or the peoples; treasures split into their items.", [
        "https://www.ironhidegames.com/News/Details/372: \"Obelax: Thanks, Sheepy! With King Denas here, we've got a full house! ... customers are flocking in from all corners of the Kingdom: Linireans, elves, dwarves\"; \"Halfdan the Blunt: It's going quite well!\".",
        "WebWalkerQA source answer: \"Characters like Linireans, elves, and dwarves participate in the grand opening\".",
        "U28 (News/Details/370): \"Winners can pick any of Ironhide Games, heroes, towers, or DLCs.\""]),
    "extdev_value_inclusive_strategy_role": ("Role only (the name is optional).", ["v1 marker \"Chief Sustainability Officer, Heini Kaihu\"; the question asks for the position."]),
    "extdev_value_ironhide_historical_games": ("Game names instead of full headlines.", [
        "U30 (News/Details/295): \"IRON MARINES GOES FREE ON GOOGLE PLAY!\"; v1 headline \"KINGDOM RUSH ORIGINS COMING OUT NOVEMBER 20!\"."]),
    "extdev_value_ironhide_arcade_gdc": ("Game names instead of the headline; the question's own words 'round trip to GDC' are no longer required in the answer.", [
        "WebWalkerQA source answer (candidates_extdev.jsonl, main:562): \"Kingdom Rush and Junkworld\".",
        "https://www.ironhidegames.com/News/Details/307: \"Junkworld is Coming to Apple Arcade on September 22nd!\"."]),
    "extdev_value_cambridge_euphoria": (SAME, ["v1 parts."]),
    "extdev_value_hf_pytorch_tensorflow": (SAME, ["v1 parts."]),
    "extdev_value_cambridge_innovate": (SAME, ["v1 parts."]),
    "extdev_filter_green_xbox_controller": (SAME, ["v1 rating filter and v1 marker."]),
    "extdev_value_booking_parent": ("Accepts 'Booking Holdings' without 'Inc.'.", ["v1 marker \"Booking Holdings Inc.\"."]),
    "extdev_filter_tiny_home_dates": ("Any location (task: 'anywhere'); also accepts a tiny-home listing page with the same guests and dates.", [
        "U38 (airbnb.com/rooms/52007336?adults=1&check_in=2027-04-10&check_out=2027-04-12&pets=2...): \"Forest Tiny House | Fire Pit | Olympic Peninsula Tiny home in Port Ludlow, Washington\"."]),
    "extdev_filter_sf_exercise_dates": (SAME, ["v1 URL parameters."]),
    "extdev_filter_castles_europe_week": ("Accepts the kg_and_tags[] alias, any price_max <= 1000, and a fixed 7-night December 2026 stay.", [
        "U40 URL: \"kg_and_tags%5B%5D=Tag%3A8047 ... checkin=2026-12-01&checkout=2026-12-08 ... selected_filter_order%5B%5D=price_max%3A999 ... price_max=999\".",
        "Task text: \"price below $1000 per night\", \"for a week next month\" (runs were on 17 Nov 2026; v1 key already fixed December)."]),
}


def v1_key(task):
    fields = ("check_url_contains", "end_markers", "full_answer", "answer_parts", "url_answer_ok")
    return {k: task[k] for k in fields if k in task}


def main():
    from bench.tasks_extdev import EXTDEV_TASKS

    assert set(CHANGES) == {t["id"] for t in EXTDEV_TASKS}
    changed = [t["id"] for t in EXTDEV_TASKS if CHANGES[t["id"]][0] != SAME]
    keys_sha = hashlib.sha256((ROOT / "bench/keys_extdev_v2.py").read_bytes()).hexdigest()
    lines = ["# Extdev key changes: v1 -> scorer v2", "",
             "The v1 keys are unchanged in `bench/tasks_extdev.py` (and in git history); the v2 keys are in",
             "`bench/keys_extdev_v2.py` " + f"(SHA-256 `{keys_sha}`). Rules: [GRADER.md](../../GRADER.md), 'Scorer v2'.", "",
             f"All 40 tasks have a v2 key. {len(changed)} change what is accepted beyond the rule changes; the other",
             f"{40 - len(changed)} restate the v1 content in v2 form. Every change cites the page fact it rests on:",
             "a saved page-text excerpt with its row (D = default run, U = ultrafast run, S = smoke; numbering as in",
             "`extdev_rows.csv`), a URL fetched with a plain HTTP GET on 18 Nov 2026 with the quoted text, or the",
             "task's own words. No key was changed to make an arm pass: changes widen to outcomes the page or",
             "task supports, and several narrow (mansions now needs the task's own adults=3 and Europe).", "",
             "Rule-level changes that apply to every key (deliverable, normalisation, dump guard, page-only",
             "evidence for answer tasks) are in GRADER.md and are not repeated per task.", ""]
    for task in EXTDEV_TASKS:
        summary, evidence = CHANGES[task["id"]]
        key = {k: v for k, v in task["key_v2"].items()}
        lines += [f"## {task['id']}", "", f"- Task: {task['description']}",
                  f"- Change: **{summary}**", f"- Deliverable: `{key['deliverable']}`"]
        lines += [f"- Evidence: {e}" for e in evidence]
        lines += ["", "<details><summary>v1 key -> v2 key</summary>", "", "v1:", "", "```json",
                  json.dumps(v1_key(task), ensure_ascii=False, indent=1), "```", "", "v2:", "", "```json",
                  json.dumps(key, ensure_ascii=False, indent=1), "```", "", "</details>", ""]
    (HERE / "KEY_CHANGES.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"{len(changed)} changed, {40 - len(changed)} same content")


if __name__ == "__main__":
    main()
