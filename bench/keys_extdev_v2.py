"""Scorer v2 answer keys for the 40 extdev tasks. Judge-only metadata.

Rules: docs/GRADER.md, "Scorer v2". Every change from the v1 key, with the page
fact it rests on, is in docs/results/scorer_v2_20261118/KEY_CHANGES.md. The v1
keys stay untouched in bench/tasks_extdev.py (end_markers, full_answer,
answer_parts, url_answer_ok). `basis` is documentation only; the grader ignores it.
Agents never see this module: the prompt builder only reads description/start_url.
"""

_DEC = {"flexible_trip_lengths[]": {"any": ["one_week"]}, "flexible_trip_dates[]": {"any": ["december"]}}

KEYS_V2 = {
    "extdev_filter_greatamerica_thrill": {
        "deliverable": "page", "host": "sixflags.com",
        "pages": [{"path": "/greatamerica/attractions", "query": {"ride-category": {"any": ["thrill"]}}}],
        "reference": "DC Super-Villains Swing; Giant Drop; Sky Striker",
        "basis": "v1 URL key; reference from the saved filter page (D1)."},
    "extdev_value_nba_2021_leaders": {
        "deliverable": "answer", "host": "espn.com",
        "facts": [["Russell Westbrook"], ["Stephen Curry"], ["32.0"], ["11.7"], ["5.3"], ["Clint Capela"],
                  ["14.3"], ["Rudy Gobert"], ["2.7"], ["Jimmy Butler"], ["2.1"]],
        "reference": "Russell Westbrook; Stephen Curry; 32.0; 11.7; 5.3; Clint Capela; 14.3; Rudy Gobert; 2.7; Jimmy Butler III; 2.1",
        "basis": "v1 parts; 'Jimmy Butler III' -> 'Jimmy Butler' (same player)."},
    "extdev_spa_dota_dlc_cart": {
        "deliverable": "page", "host": "store.steampowered.com",
        "pages": [{"path": "/cart/", "text": ["The Dota 2 Official Soundtrack"]},
                  {"path": "/app/570/", "text": ["Added to your cart!", "The Dota 2 Official Soundtrack"]}],
        "reference": "The Dota 2 Official Soundtrack is in the cart ($9.99).",
        "basis": "cart page text (U3/D12) and Steam's add-to-cart confirmation on the app page (D9)."},
    "extdev_filter_booking_times_square": {
        "deliverable": "answer", "host": "booking.com",
        "facts": [["Millennium Premier Hotel New York Times Square", "LUMA Hotel - Times Square",
                   "Riu Plaza Manhattan Times Square"]],
        "reference": "Millennium Premier Hotel New York Times Square",
        "basis": "v1 hotel; LUMA on Booking's 4-star New York list (D13); Riu 'This 4-star hotel' (U4)."},
    "extdev_filter_frontiercity_family": {
        "deliverable": "page", "host": "sixflags.com",
        "pages": [{"path": "/frontiercity/attractions", "query": {"ride-category": {"any": ["family"]}}}],
        "reference": "Billy's Frog Hopper; Frankie's Mine Train; Grand Carousel; Hootie's Tree House; "
                     "Ol' 89er Express; Quick Draw; Rocky's Ranger Planes",
        "basis": "v1 URL key; reference from the saved filter page (D17)."},
    "extdev_nav_spothero_contact": {
        "deliverable": "page", "host": "spothero.com",
        "pages": [{"path": "/contact"}],
        "reference": "SpotHero support: call +1 (844) 324-7768 (every day, 6am-11pm CST) or send a message "
                     "with the Contact Customer Heroes form at https://spothero.com/contact",
        "basis": "v1 URL key; reference from the saved contact page (D21)."},
    "extdev_filter_airbnb_europe_mansions": {
        "deliverable": "page", "host": "airbnb.com",
        "pages": [{"path": "/s/Europe/homes", "query": {"category_tag": {"any": ["Tag:8115"]}, "adults": {"any": ["3"]},
                                                        "date_picker_type": {"any": ["flexible_dates"]}}},
                  {"path": "/s/Europe/homes", "query": {"kg_and_tags[]": {"any": ["Tag:8115"]}, "adults": {"any": ["3"]},
                                                        "date_picker_type": {"any": ["flexible_dates"]}}}],
        "reference": "Mansions in Europe for 3 adults, flexible dates in any month.",
        "basis": "v1 tag Tag:8115 plus the task's own '3 adults', 'Europe' and 'any month'."},
    "extdev_value_icse_2004_chair": {
        "deliverable": "answer", "host": "icse-conferences.org",
        "facts": [["Anthony Finkelstein"], ["May 23-28, 2004", "23-28 May 2004"]],
        "reference": "May 23-28, 2004; Anthony Finkelstein",
        "basis": "v1 parts; day-month order is a format variant (2004/org_ctte.htm, D32)."},
    "extdev_value_icse_duplicate_statement": {
        "deliverable": "answer", "host": "icse-conferences.org",
        "facts": [["Charleston, South Carolina"], ["FSE-10"], ["November 2002"]],
        "reference": "Charleston, South Carolina at FSE-10 in November 2002",
        "basis": "v1 phrase split into its three facts."},
    "extdev_value_rovio_anniversary": {
        "deliverable": "answer", "host": "rovio.com",
        "facts": [["Eeva Aaltonen"], ["third installment of The Angry Birds Movie", "Angry Birds Movie 3"]],
        "reference": "Eeva Aaltonen, Head of Brand Operations at Rovio; the third installment of The Angry Birds Movie series",
        "basis": "v1 parts; 'The Angry Birds Movie 3' is that third installment (Wikipedia GET)."},
    "extdev_value_apec_tourism_actions": {
        "deliverable": "answer", "host": "apec.org",
        "facts": [["Regenerative Tourism"], ["economic, social, cultural and environmental well-being"],
                  ["resilient tourism ecosystems"]],
        "reference": "Continue implementing the Policy Recommendations for Tourism of the Future: Regenerative Tourism, "
                     "which prioritizes economic, social, cultural and environmental well-being and the creation of "
                     "resilient tourism ecosystems.",
        "basis": "v1 parts, shortened to the facts."},
    "extdev_value_apec_peru_arrivals": {
        "deliverable": "answer", "host": "apec.org", "facts": [["4.4 million"]], "reference": "4.4 million",
        "basis": "v1 marker."},
    "extdev_value_apec_ministers_chair": {
        "deliverable": "answer", "host": "apec.org", "facts": [["Elizabeth Galdo"]], "reference": "Elizabeth Galdo",
        "basis": "v1 marker."},
    "extdev_search_booking_la_filters": {
        "deliverable": "both", "host": "booking.com",
        "pages": [{"path": "/city/us/los-angeles"},
                  {"path": "/searchresults", "query": {"ss": {"contains": ["los angeles"]}}}],
        "facts": [{"any": ["Property rating", "5 stars", "4 stars", "3 stars", "2 stars", "1 star", "Review score",
                           "Wonderful: 9+", "Very Good: 8+", "Good: 7+", "Pleasant: 6+"], "min": 2}],
        "reference": "Property rating: 5 stars, 4 stars, 3 stars, 2 stars, 1 star; Review score: Wonderful: 9+, "
                     "Very Good: 8+, Good: 7+, Pleasant: 6+",
        "basis": "filter block 'Filter by: Property rating ... Pleasant: 6+' on the saved LA page (D57)."},
    "extdev_value_hf_first_user_message": {
        "deliverable": "answer", "host": "huggingface.co",
        "facts": [["Please provide a reasonable subgoal-based plan to solve the given task."],
                  ["What was the opening date of the museum dedicated to the war that, after it occurred, Boston "
                   "became one of the wealthiest international ports?"],
                  ["Initial Environment Description: None."]],
        "reference": "Please provide a reasonable subgoal-based plan to solve the given task.\nTask: What was the "
                     "opening date of the museum dedicated to the war that, after it occurred, Boston became one of "
                     "the wealthiest international ports?; Initial Environment Description: None.",
        "basis": "v1 marker held a literal backslash-n; split at it (viewer text, D64)."},
    "extdev_value_hf_tei_strengths": {
        "deliverable": "answer", "host": "huggingface.co",
        "facts": [["Flash Attention"], ["Candle"], ["cuBLASLt"], ["graph compilation"], ["Docker"],
                  ["boot time", "boot times", "startup", "start-up", "boot"], ["dynamic batching"], ["Safetensors"],
                  ["OpenTelemetry", "Open Telemetry"], ["Prometheus"]],
        "reference": "Optimized Inference: TEI leverages Flash Attention, Candle, and cuBLASLt by using optimized "
                     "transformers code for inference. Streamlined Deployment: TEI eliminates the need for a model "
                     "graph compilation step for an easier deployment process. Efficient Resource Utilization: "
                     "Benefit from small Docker images and rapid boot times, allowing for true serverless "
                     "capabilities. Dynamic Batching: TEI incorporates token-based dynamic batching thus optimizing "
                     "resource utilization during inference. Safetensors weight loading: TEI loads Safetensors "
                     "weights for faster boot times. Production-Ready: TEI supports distributed tracing through Open "
                     "Telemetry and exports Prometheus metrics.",
        "basis": "v1 sentences reduced to the distinctive term of each listed strength."},
    "extdev_value_icse_2002_chairs": {
        "deliverable": "answer", "host": "icse-conferences.org",
        "facts": [["Michal Young"], ["Jeff Magee"], ["Orlando"],
                  ["May 19-25, 2002", "19-25 May 2002", "May 19-24, 2002", "19-24 May 2002"]],
        "reference": "Michal Young and Jeff Magee; May 19-25, 2002; Orlando, Florida, USA",
        "basis": "v1 parts; the same site's history.html says 'May 19-24, 2002' (D40)."},
    "extdev_value_cambridge_gestalt": {
        "deliverable": "answer", "host": "dictionary.cambridge.org",
        "facts": [["more than the total of all its parts"], ["/ɡəˈʃtælt/", "/ɡəˈʃtɑːlt/"],
                  ["This new biography is the first to consider fully the writer's gestalt."]],
        "reference": "something such as a structure or experience that, when considered as a whole, has qualities "
                     "that are more than the total of all its parts; /ɡəˈʃtælt/; This new biography is the first to "
                     "consider fully the writer's gestalt.",
        "basis": "v1 parts without the trailing colon; US IPA from the same entry (S2)."},
}

KEYS_V2.update({
    "extdev_nav_ronaldo_world_cup_stats": {
        "deliverable": "page", "host": "espn.com",
        "pages": [{"path": "/soccer/player/stats/_/id/22774/team/482/type/fifa.world"}],
        "reference": "Season | Team | STRT | FC | FA | YC | RC | G | A | SHOT | SOG | OFF\n"
                     "2026 FIFA World Cup | POR | 5 | 2 | 5 | 0 | 0 | 3 | 0 | 18 | 9 | 6\n"
                     "2022 FIFA World Cup | POR | 3 | 2 | 5 | 0 | 0 | 1 | 0 | 11 | 3 | 0\n"
                     "2018 FIFA World Cup | POR | 4 | 2 | 14 | 2 | 0 | 4 | 0 | 21 | 8 | 1\n"
                     "2014 FIFA World Cup | POR | 3 | 2 | 10 | 0 | 0 | 1 | 1 | 23 | 14 | 3\n"
                     "2010 FIFA World Cup | POR | 4 | 1 | 8 | 1 | 0 | 1 | 1 | 22 | 7 | 3\n"
                     "2006 FIFA World Cup | POR | 6 | 7 | 23 | 1 | 0 | 1 | 0 | 29 | 13 | 0",
        "basis": "v1 URL key; reference is the World Cup table the task asks for."},
    "extdev_nav_nets_schedule": {
        "deliverable": "page", "host": "espn.com",
        "pages": [{"path": "/nba/team/schedule/_/name/bkn"}],
        "reference": "https://www.espn.com/nba/team/schedule/_/name/bkn/brooklyn-nets",
        "basis": "v1 URL key."},
    "extdev_nav_fiestatexas_events": {
        "deliverable": "page", "host": "sixflags.com",
        "pages": [{"path": "/fiestatexas/events"}, {"path": "/overtexas/events"}],
        "reference": "Holiday in the Park; Countdown To New Year's; New Year's 360 Fireworks Celebration; Mardi Gras "
                     "Festival; Viva La Fiesta; Star-Spangled Nights Fireworks presented by M&M'S; Oktoberfest; Fright "
                     "Fest; Tricks and Treats - each with its dates (Select Dates, November 21 - January 4, 2027; "
                     "December 26-30, 2026; December 31, 2026; February 6 - March 15, 2027; April 3 - 25, 2027; "
                     "July 3 - 4, 2027; Sept. 4 - Oct. 31, 2027; Sept. 10 - Oct. 31, 2027; Sept 11 - Oct. 31, 2027)",
        "basis": "task says 'any six flags park in Texas'; Six Flags Over Texas is one (overtexas slug)."},
    "extdev_nav_spothero_marketing": {
        "deliverable": "both", "host": "spothero.com",
        "pages": [{"path": "/careers"}], "facts": [["Marketing Analyst"]],
        "reference": "Marketing Analyst (Chicago, IL)",
        "basis": "careers page lists 'Marketing Marketing Analyst' (D81); the role page is one click deeper."},
    "extdev_filter_amazon_puppy_food": {
        "deliverable": "page", "host": "amazon.com",
        "pages": [{"path": "/s", "path_mode": "prefix",
                   "query": {"s": {"any": ["price-asc-rank"]}, "rh": {"has": "p_72:2661618011"},
                             "k": {"contains": ["puppy", "puppies"]}}}],
        "reference": "Puppy dog food, 4 Stars & Up, sorted by Price: Low to High.",
        "basis": "v1 query parameters; search words 'puppy dog food' are the task's words."},
    "extdev_nav_eventbrite_planning": {
        "deliverable": "page", "host": "eventbrite.com",
        "pages": [{"path": "/blog/category/event-planning"}],
        "reference": "https://www.eventbrite.com/blog/category/event-planning/",
        "basis": "v1 URL key."},
    "extdev_filter_sam_harris_paperback": {
        "deliverable": "answer", "host": "amazon.com",
        "facts": [["Free Will", "The End of Faith"]],
        "reference": "Free Will [Deckle Edge] by Sam Harris, Paperback, 4.3 out of 5 stars",
        "basis": "v1 book; The End of Faith '4.5 out of 5 stars ... Paperback' on the saved results page (U24)."},
    "extdev_nav_steam_daily_players": {
        "deliverable": "page", "host": "store.steampowered.com",
        "pages": [{"path": "/charts/mostplayed", "text": ["By Daily Players"]}],
        "reference": "Most Played: Top 100 played games By Daily Players - 1 Counter-Strike 2, 2 Dota 2, 3 PUBG",
        "basis": "v1 URL and v1 marker, moved from the answer to the page text."},
    "extdev_nav_commuter_benefits": {
        "deliverable": "page", "host": "spothero.com",
        "pages": [{"path": "/solutions/commuter-benefits"}],
        "reference": "https://spothero.com/solutions/commuter-benefits",
        "basis": "v1 URL key."},
    "extdev_value_dream_blast_revenue": {
        "deliverable": "answer", "host": "rovio.com", "facts": [["Dream Blast"]],
        "reference": "Angry Birds Dream Blast", "basis": "v1 marker."},
    "extdev_value_pirate_treasures": {
        "deliverable": "answer", "host": "ironhidegames.com",
        "facts": [{"any": [["King Denas", "Obelax", "Halfdan"], ["Linireans", "elves", "dwarves"]]},
                  ["Ironhide Games", "games"], ["heroes"], ["towers"], ["DLCs", "DLC"]],
        "reference": "Linireans, elves, dwarves (with King Denas, Obelax and Halfdan the Blunt); Winners can pick "
                     "any of Ironhide Games, heroes, towers, or DLCs.",
        "basis": "article 372 names King Denas, Obelax, Halfdan at the opening and Linireans/elves/dwarves as "
                 "customers (HTTP GET); treasures from article 370 (U28)."},
    "extdev_value_inclusive_strategy_role": {
        "deliverable": "answer", "host": "rovio.com",
        "facts": [["Chief Sustainability Officer"]],
        "reference": "Chief Sustainability Officer, Heini Kaihu", "basis": "v1 marker, role only."},
    "extdev_value_ironhide_historical_games": {
        "deliverable": "answer", "host": "ironhidegames.com",
        "facts": [["Kingdom Rush Origins"], ["Iron Marines"]],
        "reference": "Iron Marines (April 10, 2023); Kingdom Rush Origins (November 20, 2014)",
        "basis": "v1 headlines reduced to the game names."},
    "extdev_value_ironhide_arcade_gdc": {
        "deliverable": "answer", "host": "ironhidegames.com",
        "facts": [["Junkworld"], ["Kingdom Rush"]],
        "reference": "Kingdom Rush and Junkworld",
        "basis": "WebWalkerQA source answer 'Kingdom Rush and Junkworld'; v1 headline reduced to the game name."},
    "extdev_value_cambridge_euphoria": {
        "deliverable": "answer", "host": "dictionary.cambridge.org",
        "facts": [["/juːˈfɔː.ri.ə/"], ["They were in a state of euphoria for days after they won the prize."]],
        "reference": "/juːˈfɔː.ri.ə/; They were in a state of euphoria for days after they won the prize.",
        "basis": "v1 parts."},
    "extdev_value_hf_pytorch_tensorflow": {
        "deliverable": "answer", "host": "huggingface.co",
        "facts": [["from_pt=True"], ["save_pretrained"]],
        "reference": "Load the PyTorch checkpoint into a TF class with TFAutoModel.from_pretrained(..., from_pt=True) "
                     "and save it with save_pretrained.",
        "basis": "v1 parts; the blog-specific config path is not a required step."},
    "extdev_value_cambridge_innovate": {
        "deliverable": "answer", "host": "dictionary.cambridge.org",
        "facts": [["/ˈɪn.ə.veɪt/"], ["The fashion industry is always desperate to innovate."]],
        "reference": "/ˈɪn.ə.veɪt/; The fashion industry is always desperate to innovate.",
        "basis": "v1 parts."},
    "extdev_filter_green_xbox_controller": {
        "deliverable": "both", "host": "amazon.com",
        "pages": [{"path": "/s", "path_mode": "prefix", "query": {"rh": {"has": "p_72:1248885011"}}}],
        "facts": [["green"], ["Xbox"]],
        "reference": "XBOX Wireless Gaming Controller | Velocity Green",
        "basis": "v1 rating filter; answer must name a green Xbox controller."},
    "extdev_value_booking_parent": {
        "deliverable": "answer", "host": "booking.com", "facts": [["Booking Holdings"]],
        "reference": "Booking Holdings Inc.", "basis": "v1 marker."},
    "extdev_filter_tiny_home_dates": {
        "deliverable": "page", "host": "airbnb.com",
        "pages": [{"path": "/homes", "query": {"property_type_id[]": {"any": ["67"]}, "adults": {"any": ["1"]},
                                               "pets": {"any": ["2"]}, "checkin": {"any": ["2027-04-10"]},
                                               "checkout": {"any": ["2027-04-12"]}}},
                  {"path": "/rooms/", "path_mode": "prefix", "text": ["Tiny home in"],
                   "query": {"adults": {"any": ["1"]}, "pets": {"any": ["2"]},
                             "check_in": {"any": ["2027-04-10"]}, "check_out": {"any": ["2027-04-12"]}}}],
        "reference": "Forest Tiny House | Fire Pit | Olympic Peninsula",
        "basis": "v1 search parameters; a tiny-home listing page with the same guests and dates (U38)."},
    "extdev_filter_sf_exercise_dates": {
        "deliverable": "page", "host": "eventbrite.com",
        "pages": [{"path": "/d/ca--san-francisco/exercise/",
                   "query": {"start_date": {"any": ["2027-07-10"]}, "end_date": {"any": ["2027-07-31"]}}}],
        "reference": "Somatic Breathwork and Deep relaxation: Creating Health and Healing!; Monday Yoga; Bachata Lab; "
                     "Salsa Dance Classes and Salsa and Bachata Dancing - SalsaCrazy Mondays; Bachata Kizomba Sunday; "
                     "Queer Bowling MBC; Breathing Ecstasy; Team Building - Archery Class in San Francisco",
        "basis": "v1 URL key; reference from the saved results page (U39)."},
    "extdev_filter_castles_europe_week": {
        "deliverable": "page", "host": "airbnb.com",
        "pages": [{"path": "/s/Europe/homes", "query": {"category_tag": {"any": ["Tag:8047"]},
                                                        "price_max": {"max": 1000}, **_DEC}},
                  {"path": "/s/Europe/homes", "query": {"kg_and_tags[]": {"any": ["Tag:8047"]},
                                                        "price_max": {"max": 1000}, **_DEC}},
                  {"path": "/s/Europe/homes", "query": {"kg_and_tags[]": {"any": ["Tag:8047"]},
                                                        "price_max": {"max": 1000},
                                                        "checkin": {"prefix": "2026-12-"}}, "stay_nights": 7},
                  {"path": "/s/Europe/homes", "query": {"category_tag": {"any": ["Tag:8047"]},
                                                        "price_max": {"max": 1000},
                                                        "checkin": {"prefix": "2026-12-"}}, "stay_nights": 7}],
        "reference": "Castles in Europe, one week in December 2026, max $1000 per night.",
        "basis": "v1 tag/price/week/December; a fixed 7-night December stay is the same request."},
})
