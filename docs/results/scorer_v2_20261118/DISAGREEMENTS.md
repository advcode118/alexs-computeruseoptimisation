# Extdev disagreements: v1 grader vs hand labels

Every extdev row where the v1 grader or scorer v2 disagrees with the original hand label
(`docs/results/extdev_hand_labels_20261117/hand_labels.csv`). Each was read from the task, the saved
final URL, the answer and the saved page text. Machine-readable: `DISAGREEMENTS.csv`.

| Class | Rows |
|---|---:|
| key wrong/too narrow | 40 |
| grader rule too strict | 23 |
| genuinely ambiguous | 2 |
| label too strict | 1 |

Classes: *grader rule too strict*: a v1 rule rejects a correct outcome whatever the key.
*key wrong/too narrow*: the key's URL or literal text excludes correct outcomes, or is malformed.
*genuinely ambiguous*: the task or the site supports two readings. *label too strict*: the label
is stricter than the written v2 rules (corrected in `extdev_label_corrections.csv`).
No row is classed *label too lenient*; AGREEMENT.md lists the rule choices that a stricter rubric
would flip, row by row.

| Row | Arm | Task | v1 | v1 reason | Label | Class | Why | v2 |
|---|---|---|---|---|---|---|---|---|
| S1 | cascade | value_hf_tei_strengths | FAIL | answer does not satisfy the required parts | correct | key wrong/too narrow | Summary task keyed by six verbatim sentences; answers paraphrase every listed strength. | PASS |
| S2 | cascade | value_cambridge_gestalt | FAIL | answer does not satisfy the required parts | correct | key wrong/too narrow | Key meaning part ends with ':' copied from the page; the answer gives the meaning without it. | PASS |
| S3 | cascade | value_icse_2002_chairs | FAIL | answer does not satisfy the required parts | correct | key wrong/too narrow | Key joined the chairs with a newline ('Michal Young<newline>Jeff Magee'); answers write 'Michal Young and Jeff Magee'. | PASS |
| D1 | browser_use | filter_greatamerica_thrill | FAIL | answer does not satisfy the required parts | correct | grader rule too strict | Page task judged by answer text: on the keyed thrill filter page, the answer lists the rides but not the word 'Thrill'. | PASS |
| D4 | cascade | filter_greatamerica_thrill | FAIL | answer does not satisfy the required parts | correct | grader rule too strict | Page task judged by answer text: on the keyed thrill filter page, the answer lists the rides but not the word 'Thrill'. | PASS |
| D9 | browser_use | spa_dota_dlc_cart | FAIL | URL | correct | key wrong/too narrow | Steam's add-to-cart confirmation on the app page ('Added to your cart! The Dota 2 Official Soundtrack'); key required the /cart/ URL. | PASS |
| D12 | cascade | spa_dota_dlc_cart | FAIL | answer too long | correct | grader rule too strict | Cart page shows 'Your Shopping Cart (1 item) The Dota 2 Official Soundtrack'; a one-sentence answer exceeded the length bound. | PASS |
| D13 | browser_use | filter_booking_times_square | FAIL | URL | correct | key wrong/too narrow | Key accepted one hotel on one search URL; the answer is another 4-star Times Square hotel shown on the saved Booking page. | PASS |
| D17 | browser_use | filter_frontiercity_family | FAIL | answer too long | correct | grader rule too strict | Page task judged by answer length: the family filter page was reached; a 7-ride list exceeded the 3x+40 bound of the marker 'Family'. | PASS |
| D19 | script_first | filter_frontiercity_family | FAIL | answer too long | correct | grader rule too strict | Page task judged by answer length: the family filter page was reached; a 7-ride list exceeded the 3x+40 bound of the marker 'Family'. | PASS |
| D20 | cascade | filter_frontiercity_family | FAIL | answer too long | correct | grader rule too strict | Page task judged by answer length: the family filter page was reached; a 7-ride list exceeded the 3x+40 bound of the marker 'Family'. | PASS |
| D21 | browser_use | nav_spothero_contact | FAIL | answer too long | correct | grader rule too strict | On /contact (the keyed page); the answer explains the form and failed the marker length bound. | PASS |
| D24 | cascade | nav_spothero_contact | FAIL | answer does not satisfy the marker | correct | grader rule too strict | On /contact; the answer is the support phone number shown there, rejected for lacking the marker 'Contact Customer Heroes'. | PASS |
| D27 | script_first | filter_airbnb_europe_mansions | FAIL | answer does not satisfy the required parts | correct | grader rule too strict | URL carries category_tag=Tag:8115, adults=3, flexible dates; the answer text lacked the literal parts 'mansions', 'Any month', '3 guests'. | PASS |
| D28 | cascade | filter_airbnb_europe_mansions | FAIL | answer does not satisfy the required parts | correct | grader rule too strict | URL carries category_tag=Tag:8115, adults=3, flexible dates; the answer text lacked the literal parts 'mansions', 'Any month', '3 guests'. | PASS |
| D32 | cascade | value_icse_2004_chair | FAIL | URL | correct | key wrong/too narrow | Dates and chair right, from the 2004 organising committee page; key tied to /history.html and the 'May 23-28, 2004' rendering. | PASS |
| D37 | browser_use | value_icse_2002_chairs | FAIL | answer does not satisfy the required parts | correct | key wrong/too narrow | Key joined the chairs with a newline ('Michal Young<newline>Jeff Magee'); answers write 'Michal Young and Jeff Magee'. | PASS |
| D40 | cascade | value_icse_2002_chairs | FAIL | URL | correct | genuinely ambiguous | Chairs and place right; 'May 19-24, 2002' is what the same site's history.html says (committee page says 19-25). Also ended on history.html, not the keyed URL. | PASS |
| D41 | browser_use | value_rovio_anniversary | FAIL | URL | correct | key wrong/too narrow | Both facts right; ended on the Eeva Aaltonen article not the keyed URL; 'The Angry Birds Movie 3' is the third installment. | PASS |
| D44 | cascade | value_rovio_anniversary | FAIL | URL | correct | key wrong/too narrow | Both facts right; ended on the Eeva Aaltonen article not the keyed URL; 'The Angry Birds Movie 3' is the third installment. | PASS |
| D45 | browser_use | value_apec_tourism_actions | FAIL | URL | correct | key wrong/too narrow | Quotes the keyed statement text; ended on the tourism overview page (it links the statement under /tourism/, not the keyed /general/ path). | PASS |
| D48 | cascade | value_apec_tourism_actions | FAIL | URL | correct | key wrong/too narrow | Quotes the keyed statement text; ended on the tourism overview page (it links the statement under /tourism/, not the keyed /general/ path). | PASS |
| D53 | browser_use | value_apec_ministers_chair | FAIL | URL | correct | key wrong/too narrow | 'Elizabeth Galdo Marin' is right; ended on the ministerial statement page, not the keyed press release. | PASS |
| D56 | cascade | value_apec_ministers_chair | FAIL | URL | correct | key wrong/too narrow | 'Elizabeth Galdo Marin' is right; ended on the ministerial statement page, not the keyed press release. | PASS |
| D57 | browser_use | search_booking_la_filters | FAIL | answer does not satisfy the required parts | correct | key wrong/too narrow | Key required the review-score block verbatim with newlines; answers list real filters from the saved 'Filter by:' block. | PASS |
| D60 | cascade | search_booking_la_filters | FAIL | answer does not satisfy the required parts | correct | key wrong/too narrow | Key required the review-score block verbatim with newlines; answers list real filters from the saved 'Filter by:' block. | PASS |
| D61 | browser_use | value_hf_first_user_message | FAIL | URL | correct | key wrong/too narrow | Exact message returned; key tied to the viewer URL (the dataset card shows the same message). | PASS |
| D64 | cascade | value_hf_first_user_message | FAIL | answer does not satisfy the marker | correct | key wrong/too narrow | On the keyed viewer URL with the exact message; the v1 marker held a literal backslash-n, so it could not match an answer with a real newline. | PASS |
| D65 | browser_use | value_hf_tei_strengths | FAIL | answer does not satisfy the required parts | correct | key wrong/too narrow | Summary task keyed by six verbatim sentences; answers paraphrase every listed strength. | PASS |
| D68 | cascade | value_hf_tei_strengths | FAIL | answer does not satisfy the required parts | correct | key wrong/too narrow | Summary task keyed by six verbatim sentences; answers paraphrase every listed strength. | PASS |
| D69 | browser_use | nav_ronaldo_world_cup_stats | FAIL | answer too long | correct | grader rule too strict | On the keyed World Cup stats URL; the requested table exceeded the length bound of the marker 'FIFA World Cup'. | PASS |
| D72 | cascade | nav_ronaldo_world_cup_stats | FAIL | answer too long | correct | grader rule too strict | On the keyed World Cup stats URL; the requested table exceeded the length bound of the marker 'FIFA World Cup'. | PASS |
| D77 | browser_use | nav_fiestatexas_events | FAIL | answer too long | correct | key wrong/too narrow | Task allows any Six Flags park in Texas; key accepted only Fiesta Texas. | PASS |
| D80 | cascade | nav_fiestatexas_events | FAIL | URL | correct | key wrong/too narrow | Task allows any Six Flags park in Texas; key accepted only Fiesta Texas. | PASS |
| D81 | browser_use | nav_spothero_marketing | FAIL | URL | correct | key wrong/too narrow | Careers page lists 'Marketing Marketing Analyst'; key required the single role page /careers/8069541. | PASS |
| D84 | cascade | nav_spothero_marketing | FAIL | URL | correct | key wrong/too narrow | Careers page lists 'Marketing Marketing Analyst'; key required the single role page /careers/8069541. | PASS |
| D85 | browser_use | filter_amazon_puppy_food | FAIL | URL | correct | key wrong/too narrow | URL has rh p_72:2661618011 and s=price-asc-rank; key required the literal search words 'dog food for puppies' and an exact rh string. | PASS |
| U1 | browser_use | filter_greatamerica_thrill | FAIL | answer does not satisfy the required parts | correct | grader rule too strict | Page task judged by answer text: on the keyed thrill filter page, the answer lists the rides but not the word 'Thrill'. | PASS |
| U3 | browser_use | spa_dota_dlc_cart | FAIL | answer too long | correct | grader rule too strict | Cart page shows 'Your Shopping Cart (1 item) The Dota 2 Official Soundtrack'; a one-sentence answer exceeded the length bound. | PASS |
| U4 | browser_use | filter_booking_times_square | FAIL | URL | correct | key wrong/too narrow | Key accepted one hotel on one search URL; the answer is another 4-star Times Square hotel shown on the saved Booking page. | PASS |
| U5 | browser_use | filter_frontiercity_family | FAIL | answer too long | correct | grader rule too strict | Page task judged by answer length: the family filter page was reached; a 7-ride list exceeded the 3x+40 bound of the marker 'Family'. | PASS |
| U6 | browser_use | nav_spothero_contact | FAIL | answer too long | correct | grader rule too strict | On /contact (the keyed page); the answer explains the form and failed the marker length bound. | PASS |
| U10 | browser_use | value_icse_2002_chairs | FAIL | answer does not satisfy the required parts | correct | key wrong/too narrow | Key joined the chairs with a newline ('Michal Young<newline>Jeff Magee'); answers write 'Michal Young and Jeff Magee'. | PASS |
| U11 | browser_use | value_rovio_anniversary | FAIL | URL | correct | key wrong/too narrow | Both facts right; ended on the Eeva Aaltonen article not the keyed URL; 'The Angry Birds Movie 3' is the third installment. | PASS |
| U12 | browser_use | value_apec_tourism_actions | FAIL | URL is a search page: | correct | grader rule too strict | Quotes the keyed statement text; ended on an apec.org search page, which v1 denies even for an answer task. | PASS |
| U14 | browser_use | value_apec_ministers_chair | FAIL | URL | correct | key wrong/too narrow | 'Elizabeth Galdo Marin' is right; ended on the ministerial statement page, not the keyed press release. | PASS |
| U15 | browser_use | search_booking_la_filters | FAIL | answer does not satisfy the required parts | correct | key wrong/too narrow | Key required the review-score block verbatim with newlines; answers list real filters from the saved 'Filter by:' block. | PASS |
| U16 | browser_use | value_hf_first_user_message | FAIL | URL | correct | key wrong/too narrow | Exact message returned; key tied to the viewer URL (the dataset card shows the same message). | PASS |
| U17 | browser_use | value_hf_tei_strengths | FAIL | answer does not satisfy the required parts | correct | key wrong/too narrow | Summary task keyed by six verbatim sentences; answers paraphrase every listed strength. | PASS |
| U18 | browser_use | nav_ronaldo_world_cup_stats | FAIL | answer too long | correct | grader rule too strict | On the keyed World Cup stats URL; the requested table exceeded the length bound of the marker 'FIFA World Cup'. | PASS |
| U20 | browser_use | nav_fiestatexas_events | FAIL | URL | correct | key wrong/too narrow | Task allows any Six Flags park in Texas; key accepted only Fiesta Texas. | PASS |
| U21 | browser_use | nav_spothero_marketing | FAIL | URL | correct | key wrong/too narrow | Careers page lists 'Marketing Marketing Analyst'; key required the single role page /careers/8069541. | PASS |
| U22 | browser_use | filter_amazon_puppy_food | FAIL | URL | correct | key wrong/too narrow | URL has rh p_72:2661618011 and s=price-asc-rank; key required the literal search words 'dog food for puppies' and an exact rh string. | PASS |
| U23 | browser_use | nav_eventbrite_planning | FAIL | answer too long | correct | grader rule too strict | On the keyed blog category page; a URL answer wrapped in one sentence was rejected. | PASS |
| U24 | browser_use | filter_sam_harris_paperback | FAIL | URL | correct | key wrong/too narrow | The End of Faith shows '4.5 out of 5 stars ... Paperback' on the saved page; key accepted only Free Will via a filter URL. | PASS |
| U25 | browser_use | nav_steam_daily_players | FAIL | answer too long | correct | grader rule too strict | On /charts/mostplayed, page shows 'By Daily Players'; a one-line answer exceeded the length bound. | PASS |
| U27 | browser_use | value_dream_blast_revenue | FAIL | URL | correct | key wrong/too narrow | Right game; ended on the 2019 results article, key tied to the 2022 report URL. | PASS |
| U28 | browser_use | value_pirate_treasures | FAIL | answer does not satisfy the required parts | correct | genuinely ambiguous | Source answer names the customers (Linireans, elves, dwarves); the agent named the characters at the opening (King Denas, Obelax, Halfdan), also in article 372. Key required both. | PASS |
| U30 | browser_use | value_ironhide_historical_games | FAIL | URL | correct | key wrong/too narrow | Iron Marines and Kingdom Rush Origins are right; key required full headlines on one URL. | PASS |
| U31 | browser_use | value_ironhide_arcade_gdc | FAIL | URL | partial | label too strict | Answer is the source answer 'Kingdom Rush and Junkworld'; labelled partial only because the final page does not show the GDC prize. | PASS |
| U32 | browser_use | value_cambridge_euphoria | FAIL | answer part is not in the page text | correct | grader rule too strict | Answer equals the key; the saved page is a security-verification screen, so v1 grounding in page text failed. | PASS |
| U35 | browser_use | value_cambridge_innovate | FAIL | answer part is not in the page text | correct | grader rule too strict | Answer equals the key; the saved page is a security-verification screen, so v1 grounding in page text failed. | PASS |
| U37 | browser_use | value_booking_parent | FAIL | URL | correct | key wrong/too narrow | 'Booking Holdings Inc.' is right; ended on the home page, key tied to /content/about.html. | PASS |
| U38 | browser_use | filter_tiny_home_dates | FAIL | URL | correct | key wrong/too narrow | A tiny-home listing ('Tiny home in Port Ludlow') with adults=1, pets=2, Apr 10-12; key required the search-results URL. | PASS |
| U39 | browser_use | filter_sf_exercise_dates | FAIL | answer too long | correct | grader rule too strict | On the keyed URL with the date range; the event list exceeded the length bound. | PASS |
| U40 | browser_use | filter_castles_europe_week | FAIL | URL | correct | key wrong/too narrow | kg_and_tags[]=Tag:8047, price_max=999, Dec 1-8 (7 nights); key required category_tag, price_max=1000 and flexible-week parameters. | PASS |
