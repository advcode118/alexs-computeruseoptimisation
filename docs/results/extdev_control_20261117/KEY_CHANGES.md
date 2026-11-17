# Extdev key changes — authored-data-only selection

**Key selection was completed before reading any saved arm answers for this step.**
No arm returned answer was consulted to choose parts, full answers or URL flags.
Only descriptions, existing marker/unchecked_fragments, reproducer constants,
and original candidate source_key/provenance were inspected.

The old marker, URL keys, key_scope and unchecked_fragments remain unchanged.
For multipart requests the reference is marker + authored unchecked_fragments,
joined with `; `. Constraints with no authored page-verbatim value are not invented.
Source references are bench/tasks_extdev.py fields and, by source/source_id,
docs/results/ext_sample_20261116/{candidates_extdev,authoring_extdev}.jsonl.
Page-verbatim authorship is not proof that all parts coexist on the final page:
multi-source tasks may still fail grounding. Synthetic 40/40 is logical compatibility only.

URL flags are conservative: five find/browse-page tasks only. No value task
has a URL flag. Contact-support, all-events and daily-player-view tasks do not.

## Frozen key-selection snapshot

`bench/tasks_extdev.py` SHA256: `c0fee784ecc83c9953d64a07447cffcc0899e73e1abccc148aea1020eae6fae6`.

## extdev_filter_greatamerica_thrill

- Description: Find thrill rides in Six Flags Great America, Chicago, IL on sixflags
- Provenance: Mind2Web-Live / `mind2web-live_test_20241024.json:84`.
- Old marker (unchanged): `"Thrill"`.
- New full_answer: `"Thrill"`.
- New answer_parts: `["Thrill"]`.
- url_answer_ok: `false`.
  - Part 1 source: `expected_answer / end_markers.answer_in_text` = `"Thrill"`.
- Not keyed / limitation: Individual ride names: no authored page-verbatim list; only category heading is available.

## extdev_value_nba_2021_leaders

- Description: Who were the NBA season leaders from the 2020-21 regular season? in espn
- Provenance: Mind2Web-Live / `mind2web-live_train_20240528.json:4ph5MPhtgRHlWuYMD6WXT`.
- Old marker (unchanged): `"Russell Westbrook"`.
- New full_answer: `"Russell Westbrook; Stephen Curry; 32.0; 11.7; 5.3; Clint Capela; 14.3; Rudy Gobert; 2.7; Jimmy Butler III; 2.1"`.
- New answer_parts: `["Russell Westbrook", "Stephen Curry", "32.0", "11.7", "5.3", "Clint Capela", "14.3", "Rudy Gobert", "2.7", "Jimmy Butler III", "2.1"]`.
- url_answer_ok: `false`.
  - Part 1 source: `expected_answer / end_markers.answer_in_text` = `"Russell Westbrook"`.
  - Part 2 source: `unchecked_fragments[0]` = `"Stephen Curry"`.
  - Part 3 source: `unchecked_fragments[1]` = `"32.0"`.
  - Part 4 source: `unchecked_fragments[2]` = `"11.7"`.
  - Part 5 source: `unchecked_fragments[3]` = `"5.3"`.
  - Part 6 source: `unchecked_fragments[4]` = `"Clint Capela"`.
  - Part 7 source: `unchecked_fragments[5]` = `"14.3"`.
  - Part 8 source: `unchecked_fragments[6]` = `"Rudy Gobert"`.
  - Part 9 source: `unchecked_fragments[7]` = `"2.7"`.
  - Part 10 source: `unchecked_fragments[8]` = `"Jimmy Butler III"`.
  - Part 11 source: `unchecked_fragments[9]` = `"2.1"`.
- Not keyed / limitation: No additional requested authored fact omitted; literal strings are not paraphrase matching.

## extdev_spa_dota_dlc_cart

- Description: Find Dota 2 game and add all DLC to cart in steam
- Provenance: Mind2Web-Live / `mind2web-live_train_20240528.json:yD3SHg-3yHxUm0FUanCrg`.
- Old marker (unchanged): `"The Dota 2 Official Soundtrack"`.
- New full_answer: `"The Dota 2 Official Soundtrack"`.
- New answer_parts: `["The Dota 2 Official Soundtrack"]`.
- url_answer_ok: `false`.
  - Part 1 source: `expected_answer / end_markers.answer_in_text` = `"The Dota 2 Official Soundtrack"`.
- Not keyed / limitation: Other DLC names and proof that every cartable DLC was added; reproducer supplies UI actions, not more page-verbatim answer values.

## extdev_filter_booking_times_square

- Description: Find a 4 star rated Hotel in New York Timesquare for 2 adults in booking
- Provenance: Mind2Web-Live / `mind2web-live_train_20240528.json:P8htYaov1DieOOhfEcHtb`.
- Old marker (unchanged): `"Millennium Premier Hotel New York Times Square"`.
- New full_answer: `"Millennium Premier Hotel New York Times Square; 2 adults"`.
- New answer_parts: `["Millennium Premier Hotel New York Times Square", "2 adults"]`.
- url_answer_ok: `false`.
  - Part 1 source: `expected_answer / end_markers.answer_in_text` = `"Millennium Premier Hotel New York Times Square"`.
  - Part 2 source: `unchecked_fragments[0]` = `"2 adults"`.
- Not keyed / limitation: Four-star label and location wording have no authored page-verbatim answer part; existing URL key is unchanged.

## extdev_filter_frontiercity_family

- Description: What are the family rides available at frontier city? on sixflags
- Provenance: Mind2Web-Live / `mind2web-live_test_20241024.json:52`.
- Old marker (unchanged): `"Family"`.
- New full_answer: `"Family"`.
- New answer_parts: `["Family"]`.
- url_answer_ok: `false`.
  - Part 1 source: `expected_answer / end_markers.answer_in_text` = `"Family"`.
- Not keyed / limitation: Individual ride names: no authored page-verbatim list; only category heading is available.

## extdev_filter_airbnb_europe_mansions

- Description: I want to see mansions for 3 adults to stay in in europe during any month in airbnb
- Provenance: Mind2Web-Live / `mind2web-live_train_20240528.json:Z4h9VeJnGbgj3mUjIKJ_Y`.
- Old marker (unchanged): `"mansions"`.
- New full_answer: `"mansions; Any month; 3 guests"`.
- New answer_parts: `["mansions", "Any month", "3 guests"]`.
- url_answer_ok: `false`.
  - Part 1 source: `expected_answer / end_markers.answer_in_text` = `"mansions"`.
  - Part 2 source: `unchecked_fragments[0]` = `"Any month"`.
  - Part 3 source: `unchecked_fragments[1]` = `"3 guests"`.
- Not keyed / limitation: Europe wording is not an authored page-verbatim part; existing URL key remains unchanged.

## extdev_value_icse_2004_chair

- Description: What were the exact dates and the General Chair for the ICSE conference in 2004?
- Provenance: WebWalkerQA / `main:451`.
- Old marker (unchanged): `"Anthony Finkelstein"`.
- New full_answer: `"Anthony Finkelstein; May 23-28, 2004"`.
- New answer_parts: `["Anthony Finkelstein", "May 23-28, 2004"]`.
- url_answer_ok: `false`.
  - Part 1 source: `expected_answer / end_markers.answer_in_text` = `"Anthony Finkelstein"`.
  - Part 2 source: `unchecked_fragments[0]` = `"May 23-28, 2004"`.
- Not keyed / limitation: No additional requested authored fact omitted; literal strings are not paraphrase matching.

## extdev_value_icse_duplicate_statement

- Description: When and where was the ICSE duplicate submission statement agreed upon?
- Provenance: WebWalkerQA / `main:1`.
- Old marker (unchanged): `"Charleston, South Carolina at FSE-10 in November 2002"`.
- New full_answer: `"Charleston, South Carolina at FSE-10 in November 2002"`.
- New answer_parts: `["Charleston, South Carolina at FSE-10 in November 2002"]`.
- url_answer_ok: `false`.
  - Part 1 source: `expected_answer / end_markers.answer_in_text` = `"Charleston, South Carolina at FSE-10 in November 2002"`.
- Not keyed / limitation: No additional requested authored fact omitted; literal strings are not paraphrase matching.

## extdev_value_icse_2002_chairs

- Description: Who were the program committee chairs for the ICSE 2002 conference, and when and where was this conference held?
- Provenance: WebWalkerQA / `main:38`.
- Old marker (unchanged): `"Michal Young\nJeff Magee"`.
- New full_answer: `"Michal Young\nJeff Magee; Orlando, Florida, USA; May 19-25, 2002"`.
- New answer_parts: `["Michal Young\nJeff Magee", "Orlando, Florida, USA", "May 19-25, 2002"]`.
- url_answer_ok: `false`.
  - Part 1 source: `expected_answer / end_markers.answer_in_text` = `"Michal Young\nJeff Magee"`.
  - Part 2 source: `unchecked_fragments[0]` = `"Orlando, Florida, USA"`.
  - Part 3 source: `unchecked_fragments[1]` = `"May 19-25, 2002"`.
- Not keyed / limitation: Original multiline chair marker is retained as one part; conjunction/paraphrase matching is not introduced.

## extdev_value_rovio_anniversary

- Description: Who is responsible for overseeing the Angry Birds brand strategy during the 15th anniversary celebrations, and what major project is highlighted as part of these celebrations?
- Provenance: WebWalkerQA / `main:454`.
- Old marker (unchanged): `"Eeva Aaltonen, Head of Brand Operations at Rovio"`.
- New full_answer: `"Eeva Aaltonen, Head of Brand Operations at Rovio; the third installment of The Angry Birds Movie series"`.
- New answer_parts: `["Eeva Aaltonen, Head of Brand Operations at Rovio", "the third installment of The Angry Birds Movie series"]`.
- url_answer_ok: `false`.
  - Part 1 source: `expected_answer / end_markers.answer_in_text` = `"Eeva Aaltonen, Head of Brand Operations at Rovio"`.
  - Part 2 source: `unchecked_fragments[0]` = `"the third installment of The Angry Birds Movie series"`.
- Not keyed / limitation: Authored fragment names the third Angry Birds Movie installment, whereas original source_key.answer names Mystery Island. Preserve the already-authored page fragment, document conflict; do not invent or substitute a title.

## extdev_value_apec_tourism_actions

- Description: What proactive steps did the APEC 12th Tourism Ministerial Meeting conclude to address the challenges in tourism due to sea level rise?
- Provenance: WebWalkerQA / `main:97`.
- Old marker (unchanged): `"Policy Recommendations for Tourism of the Future: Regenerative Tourism"`.
- New full_answer: `"Policy Recommendations for Tourism of the Future: Regenerative Tourism; economic, social, cultural and environmental well-being; creation of resilient tourism ecosystems"`.
- New answer_parts: `["Policy Recommendations for Tourism of the Future: Regenerative Tourism", "economic, social, cultural and environmental well-being", "creation of resilient tourism ecosystems"]`.
- url_answer_ok: `false`.
  - Part 1 source: `expected_answer / end_markers.answer_in_text` = `"Policy Recommendations for Tourism of the Future: Regenerative Tourism"`.
  - Part 2 source: `unchecked_fragments[0]` = `"economic, social, cultural and environmental well-being"`.
  - Part 3 source: `unchecked_fragments[1]` = `"creation of resilient tourism ecosystems"`.
- Not keyed / limitation: No additional requested authored fact omitted; literal strings are not paraphrase matching.

## extdev_search_booking_la_filters

- Description: Search for properties in Los Angeles, browse the results page to see what filters are available, list some of them.
- Provenance: WebVoyager / `Booking--43`.
- Old marker (unchanged): `"Wonderful: 9+\nVery Good: 8+\nGood: 7+\nPleasant: 6+"`.
- New full_answer: `"Wonderful: 9+\nVery Good: 8+\nGood: 7+\nPleasant: 6+"`.
- New answer_parts: `["Wonderful: 9+\nVery Good: 8+\nGood: 7+\nPleasant: 6+"]`.
- url_answer_ok: `false`.
  - Part 1 source: `expected_answer / end_markers.answer_in_text` = `"Wonderful: 9+\nVery Good: 8+\nGood: 7+\nPleasant: 6+"`.
- Not keyed / limitation: Original multiline review-filter marker is retained; no inferred additional filters.

## extdev_value_hf_tei_strengths

- Description: Check out Text Embeddings Inference in Hugging face's Doc to summarise the strengths of the toolkit.
- Provenance: WebVoyager / `Huggingface--40`.
- Old marker (unchanged): `"Optimized Inference: TEI leverages Flash Attention, Candle, and cuBLASLt by using optimized transformers code for inference."`.
- New full_answer: `"Optimized Inference: TEI leverages Flash Attention, Candle, and cuBLASLt by using optimized transformers code for inference.; Streamlined Deployment: TEI eliminates the need for a model graph compilation step for an easier deployment process.; Efficient Resource Utilization: Benefit from small Docker images and rapid boot times, allowing for true serverless capabilities.; Dynamic Batching: TEI incorporates token-based dynamic batching thus optimizing resource utilization during inference.; Safetensors weight loading: TEI loads Safetensors weights for faster boot times.; Production-Ready: TEI supports distributed tracing through Open Telemetry and exports Prometheus metrics."`.
- New answer_parts: `["Optimized Inference: TEI leverages Flash Attention, Candle, and cuBLASLt by using optimized transformers code for inference.", "Streamlined Deployment: TEI eliminates the need for a model graph compilation step for an easier deployment process.", "Efficient Resource Utilization: Benefit from small Docker images and rapid boot times, allowing for true serverless capabilities.", "Dynamic Batching: TEI incorporates token-based dynamic batching thus optimizing resource utilization during inference.", "Safetensors weight loading: TEI loads Safetensors weights for faster boot times.", "Production-Ready: TEI supports distributed tracing through Open Telemetry and exports Prometheus metrics."]`.
- url_answer_ok: `false`.
  - Part 1 source: `expected_answer / end_markers.answer_in_text` = `"Optimized Inference: TEI leverages Flash Attention, Candle, and cuBLASLt by using optimized transformers code for inference."`.
  - Part 2 source: `unchecked_fragments[0]` = `"Streamlined Deployment: TEI eliminates the need for a model graph compilation step for an easier deployment process."`.
  - Part 3 source: `unchecked_fragments[1]` = `"Efficient Resource Utilization: Benefit from small Docker images and rapid boot times, allowing for true serverless capabilities."`.
  - Part 4 source: `unchecked_fragments[2]` = `"Dynamic Batching: TEI incorporates token-based dynamic batching thus optimizing resource utilization during inference."`.
  - Part 5 source: `unchecked_fragments[3]` = `"Safetensors weight loading: TEI loads Safetensors weights for faster boot times."`.
  - Part 6 source: `unchecked_fragments[4]` = `"Production-Ready: TEI supports distributed tracing through Open Telemetry and exports Prometheus metrics."`.
- Not keyed / limitation: No additional requested authored fact omitted; literal strings are not paraphrase matching.

## extdev_nav_ronaldo_world_cup_stats

- Description: Find the statistics of the player Cristiano Ronaldo for the national team of Portugal in all the world cups in espn.com.
- Provenance: Mind2Web-Live / `mind2web-live_test_20241024.json:56`.
- Old marker (unchanged): `"FIFA World Cup"`.
- New full_answer: `"FIFA World Cup"`.
- New answer_parts: `["FIFA World Cup"]`.
- url_answer_ok: `true`.
  - Part 1 source: `expected_answer / end_markers.answer_in_text` = `"FIFA World Cup"`.
- Not keyed / limitation: Individual statistics and years are not authored page-verbatim parts; URL navigation is explicitly allowed for this find-statistics-page task.

## extdev_nav_nets_schedule

- Description: Find the team schedule of the Brooklyn Nets on espn
- Provenance: Mind2Web-Live / `mind2web-live_test_20241024.json:91`.
- Old marker (unchanged): `"Brooklyn Nets Schedule"`.
- New full_answer: `null`.
- New answer_parts: `null`.
- url_answer_ok: `true`.
- Not keyed / limitation: No additional requested authored fact omitted; literal strings are not paraphrase matching.

## extdev_nav_fiestatexas_events

- Description: Show me all the events at any six flags park in Texas in sixflags
- Provenance: Mind2Web-Live / `mind2web-live_train_20240528.json:B1UCuUrgSOAqSeEHS1KBY`.
- Old marker (unchanged): `"Our Events"`.
- New full_answer: `"Our Events"`.
- New answer_parts: `["Our Events"]`.
- url_answer_ok: `false`.
  - Part 1 source: `expected_answer / end_markers.answer_in_text` = `"Our Events"`.
- Not keyed / limitation: Individual event names/dates are unavailable; heading only. No URL-answer flag: asks to show all events, not merely find a page.

## extdev_nav_spothero_marketing

- Description: Find career openings in the marketing department in spothero
- Provenance: Mind2Web-Live / `mind2web-live_train_20240528.json:fpVE0gXWol5kEqO62RlPb`.
- Old marker (unchanged): `"Marketing Analyst"`.
- New full_answer: `"Marketing Analyst"`.
- New answer_parts: `["Marketing Analyst"]`.
- url_answer_ok: `true`.
  - Part 1 source: `expected_answer / end_markers.answer_in_text` = `"Marketing Analyst"`.
- Not keyed / limitation: Other openings, if any, are unavailable; one authored role only. Find-openings page navigation is allowed.

## extdev_filter_amazon_puppy_food

- Description: Browse dog food for puppies that is rated at least 4 stars and sort the results by price from low to high in amazon
- Provenance: Mind2Web-Live / `mind2web-live_train_20240528.json:D4265_JGGnJ4AkBc9VP49`.
- Old marker (unchanged): `"Sort by:Price: Low to High"`.
- New full_answer: `"Sort by:Price: Low to High"`.
- New answer_parts: `["Sort by:Price: Low to High"]`.
- url_answer_ok: `false`.
  - Part 1 source: `expected_answer / end_markers.answer_in_text` = `"Sort by:Price: Low to High"`.
- Not keyed / limitation: Individual products, puppy-food wording and four-star page label are unavailable; only sort heading is authored.

## extdev_nav_eventbrite_planning

- Description: Browse the page with event planning tips on eventbrite
- Provenance: Mind2Web-Live / `mind2web-live_test_20241024.json:51`.
- Old marker (unchanged): `"EVENT PLANNING"`.
- New full_answer: `null`.
- New answer_parts: `null`.
- url_answer_ok: `true`.
- Not keyed / limitation: No additional requested authored fact omitted; literal strings are not paraphrase matching.

## extdev_filter_sam_harris_paperback

- Description: Find a book by Sam Harris that has a rating of at least 4 stars and is available in paperback format in amazon
- Provenance: Mind2Web-Live / `mind2web-live_train_20240528.json:AN-OG7dBV7v_N9g2nmoUG`.
- Old marker (unchanged): `"Free Will [Deckle Edge]"`.
- New full_answer: `"Free Will [Deckle Edge]; Paperback; by Sam Harris; 4.3 out of 5 stars"`.
- New answer_parts: `["Free Will [Deckle Edge]", "Paperback", "by Sam Harris", "4.3 out of 5 stars"]`.
- url_answer_ok: `false`.
  - Part 1 source: `expected_answer / end_markers.answer_in_text` = `"Free Will [Deckle Edge]"`.
  - Part 2 source: `unchecked_fragments[0]` = `"Paperback"`.
  - Part 3 source: `unchecked_fragments[1]` = `"by Sam Harris"`.
  - Part 4 source: `unchecked_fragments[2]` = `"4.3 out of 5 stars"`.
- Not keyed / limitation: No additional requested authored fact omitted; literal strings are not paraphrase matching.

## extdev_nav_steam_daily_players

- Description: Show most played games based on daily players in store.steampowered
- Provenance: Mind2Web-Live / `mind2web-live_train_20240528.json:0ZydjXfdu-f7wjwsL02Yj`.
- Old marker (unchanged): `"By Daily Players"`.
- New full_answer: `"By Daily Players"`.
- New answer_parts: `["By Daily Players"]`.
- url_answer_ok: `false`.
  - Part 1 source: `expected_answer / end_markers.answer_in_text` = `"By Daily Players"`.
- Not keyed / limitation: Game names/player counts are unavailable; tab heading only. No URL-answer flag: asks for the daily-player view, whose tab state is not encoded by the URL.

## extdev_nav_commuter_benefits

- Description: Find guide for paying with commuter benefits in spothero
- Provenance: Mind2Web-Live / `mind2web-live_train_20240528.json:0TlqUv_XigwXM7ao_ogh1`.
- Old marker (unchanged): `"How to Use Your Commuter Benefits Card"`.
- New full_answer: `null`.
- New answer_parts: `null`.
- url_answer_ok: `true`.
- Not keyed / limitation: No additional requested authored fact omitted; literal strings are not paraphrase matching.

## extdev_value_dream_blast_revenue

- Description: Which game contributed significantly to Rovio's revenue in both 2019 and 2022?
- Provenance: WebWalkerQA / `main:537`.
- Old marker (unchanged): `"Angry Birds Dream Blast"`.
- New full_answer: `"Angry Birds Dream Blast"`.
- New answer_parts: `null`.
- url_answer_ok: `false`.
- Not keyed / limitation: Single requested game name is already the complete authored value; year/revenue context is not a requested answer part.

## extdev_value_pirate_treasures

- Description: Which characters are involved in the grand opening of Battle Brewmasters Artisanal Potion Shop in Kingdom Rush 5: Alliance, and what types of hidden treasures can be found in the upcoming Pirate Kings Campaign?
- Provenance: WebWalkerQA / `main:17`.
- Old marker (unchanged): `"Winners can pick any of Ironhide Games, heroes, towers, or DLCs."`.
- New full_answer: `"Winners can pick any of Ironhide Games, heroes, towers, or DLCs.; Linireans, elves, dwarves; King Denas; Obelax; Halfdan"`.
- New answer_parts: `["Winners can pick any of Ironhide Games, heroes, towers, or DLCs.", "Linireans, elves, dwarves", "King Denas", "Obelax", "Halfdan"]`.
- url_answer_ok: `false`.
  - Part 1 source: `expected_answer / end_markers.answer_in_text` = `"Winners can pick any of Ironhide Games, heroes, towers, or DLCs."`.
  - Part 2 source: `unchecked_fragments[0]` = `"Linireans, elves, dwarves"`.
  - Part 3 source: `unchecked_fragments[1]` = `"King Denas"`.
  - Part 4 source: `unchecked_fragments[2]` = `"Obelax"`.
  - Part 5 source: `unchecked_fragments[3]` = `"Halfdan"`.
- Not keyed / limitation: Authored character fragments come from another article and are not guaranteed to coexist on the final page. No additional characters or inferred treasure names added.

## extdev_value_inclusive_strategy_role

- Description: Which position is identified as a key role in promoting inclusion strategy according to Rovio's guide for inclusive game design and 2023 Sustainability Report?
- Provenance: WebWalkerQA / `main:109`.
- Old marker (unchanged): `"Chief Sustainability Officer, Heini Kaihu"`.
- New full_answer: `"Chief Sustainability Officer, Heini Kaihu"`.
- New answer_parts: `null`.
- url_answer_ok: `false`.
- Not keyed / limitation: Single requested named role is already complete in the marker; alternate wording and document title are context, not extra requested answer parts.

## extdev_value_ironhide_historical_games

- Description: What new games were released by Ironhide Game Studio on April 10, 2023, and November 20, 2014?
- Provenance: WebWalkerQA / `main:621`.
- Old marker (unchanged): `"KINGDOM RUSH ORIGINS COMING OUT NOVEMBER 20!"`.
- New full_answer: `"KINGDOM RUSH ORIGINS COMING OUT NOVEMBER 20!; IRON MARINES GOES FREE ON GOOGLE PLAY!"`.
- New answer_parts: `["KINGDOM RUSH ORIGINS COMING OUT NOVEMBER 20!", "IRON MARINES GOES FREE ON GOOGLE PLAY!"]`.
- url_answer_ok: `false`.
  - Part 1 source: `expected_answer / end_markers.answer_in_text` = `"KINGDOM RUSH ORIGINS COMING OUT NOVEMBER 20!"`.
  - Part 2 source: `unchecked_fragments[0]` = `"IRON MARINES GOES FREE ON GOOGLE PLAY!"`.
- Not keyed / limitation: April 2023 authored source says free-game promotion, not a new release. No invented release claim/date part.

## extdev_value_ironhide_arcade_gdc

- Description: Which game developed by Ironhide was awarded a round trip to GDC as a prize, and what is the latest game they announced for Apple Arcade in 2023?
- Provenance: WebWalkerQA / `main:562`.
- Old marker (unchanged): `"JUNKWORLD IS COMING TO APPLE ARCADE ON SEPTEMBER 22ND!"`.
- New full_answer: `"JUNKWORLD IS COMING TO APPLE ARCADE ON SEPTEMBER 22ND!; Kingdom Rush; round trip to GDC"`.
- New answer_parts: `["JUNKWORLD IS COMING TO APPLE ARCADE ON SEPTEMBER 22ND!", "Kingdom Rush", "round trip to GDC"]`.
- url_answer_ok: `false`.
  - Part 1 source: `expected_answer / end_markers.answer_in_text` = `"JUNKWORLD IS COMING TO APPLE ARCADE ON SEPTEMBER 22ND!"`.
  - Part 2 source: `unchecked_fragments[0]` = `"Kingdom Rush"`.
  - Part 3 source: `unchecked_fragments[1]` = `"round trip to GDC"`.
- Not keyed / limitation: GDC fragment comes from another page; coexistence on final page is unverified.

## extdev_value_cambridge_euphoria

- Description: Look up the British pronunciation of the word "euphoria" and find an example sentence using that word on the Cambridge Dictionary.
- Provenance: WebVoyager / `Cambridge Dictionary--9`.
- Old marker (unchanged): `"They were in a state of euphoria for days after they won the prize."`.
- New full_answer: `"They were in a state of euphoria for days after they won the prize.; /juːˈfɔː.ri.ə/"`.
- New answer_parts: `["They were in a state of euphoria for days after they won the prize.", "/juːˈfɔː.ri.ə/"]`.
- url_answer_ok: `false`.
  - Part 1 source: `expected_answer / end_markers.answer_in_text` = `"They were in a state of euphoria for days after they won the prize."`.
  - Part 2 source: `unchecked_fragments[0]` = `"/juːˈfɔː.ri.ə/"`.
- Not keyed / limitation: No additional requested authored fact omitted; literal strings are not paraphrase matching.

## extdev_value_hf_pytorch_tensorflow

- Description: Identify the steps to convert a PyTorch model to TensorFlow using the Hugging Face Transformers library as described in their documentation.
- Provenance: WebVoyager / `Huggingface--22`.
- Old marker (unchanged): `"from_pt=True"`.
- New full_answer: `"from_pt=True; TFAutoModel.from_pretrained(; AutoConfig.from_pretrained(\"./pt_model/config.json\"); save_pretrained"`.
- New answer_parts: `["from_pt=True", "TFAutoModel.from_pretrained(", "AutoConfig.from_pretrained(\"./pt_model/config.json\")", "save_pretrained"]`.
- url_answer_ok: `false`.
  - Part 1 source: `expected_answer / end_markers.answer_in_text` = `"from_pt=True"`.
  - Part 2 source: `unchecked_fragments[0]` = `"TFAutoModel.from_pretrained("`.
  - Part 3 source: `unchecked_fragments[1]` = `"AutoConfig.from_pretrained(\"./pt_model/config.json\")"`.
  - Part 4 source: `unchecked_fragments[2]` = `"save_pretrained"`.
- Not keyed / limitation: No additional requested authored fact omitted; literal strings are not paraphrase matching.

## extdev_value_cambridge_gestalt

- Description: Look up the meaning, pronunciation, and an example sentence of the word "gestalt" using the Cambridge Dictionary.
- Provenance: WebVoyager / `Cambridge Dictionary--7`.
- Old marker (unchanged): `"This new biography is the first to consider fully the writer's gestalt."`.
- New full_answer: `"This new biography is the first to consider fully the writer's gestalt.; /ɡəˈʃtælt/; something such as a structure or experience that, when considered as a whole, has qualities that are more than the total of all its parts:"`.
- New answer_parts: `["This new biography is the first to consider fully the writer's gestalt.", "/ɡəˈʃtælt/", "something such as a structure or experience that, when considered as a whole, has qualities that are more than the total of all its parts:"]`.
- url_answer_ok: `false`.
  - Part 1 source: `expected_answer / end_markers.answer_in_text` = `"This new biography is the first to consider fully the writer's gestalt."`.
  - Part 2 source: `unchecked_fragments[0]` = `"/ɡəˈʃtælt/"`.
  - Part 3 source: `unchecked_fragments[1]` = `"something such as a structure or experience that, when considered as a whole, has qualities that are more than the total of all its parts:"`.
- Not keyed / limitation: No additional requested authored fact omitted; literal strings are not paraphrase matching.

## extdev_value_cambridge_innovate

- Description: Look for the British English pronunciation of the word "innovate" and write down the International Phonetic Alphabet (IPA) notation, then find one example sentence provided in the Cambridge Dictionary that uses this word.
- Provenance: WebVoyager / `Cambridge Dictionary--4`.
- Old marker (unchanged): `"The fashion industry is always desperate to innovate."`.
- New full_answer: `"The fashion industry is always desperate to innovate.; /ˈɪn.ə.veɪt/"`.
- New answer_parts: `["The fashion industry is always desperate to innovate.", "/ˈɪn.ə.veɪt/"]`.
- url_answer_ok: `false`.
  - Part 1 source: `expected_answer / end_markers.answer_in_text` = `"The fashion industry is always desperate to innovate."`.
  - Part 2 source: `unchecked_fragments[0]` = `"/ˈɪn.ə.veɪt/"`.
- Not keyed / limitation: No additional requested authored fact omitted; literal strings are not paraphrase matching.

## extdev_filter_green_xbox_controller

- Description: Search an Xbox Wireless controller with green color and rated above 4 stars.
- Provenance: WebVoyager / `Amazon--0`.
- Old marker (unchanged): `"XBOX Wireless Gaming Controller | Velocity Green"`.
- New full_answer: `"XBOX Wireless Gaming Controller | Velocity Green"`.
- New answer_parts: `["XBOX Wireless Gaming Controller | Velocity Green"]`.
- url_answer_ok: `false`.
  - Part 1 source: `expected_answer / end_markers.answer_in_text` = `"XBOX Wireless Gaming Controller | Velocity Green"`.
- Not keyed / limitation: Four-star page label is unavailable; existing URL marker remains unchanged.

## extdev_filter_tiny_home_dates

- Description: Search for a tiny home anywhere for an adult and 2 pets to stay in from april 10 to april 12
- Provenance: Mind2Web / `1267fbd8-54c8-4f2e-8471-b13c4de332c7`.
- Old marker (unchanged): `"Tiny home in"`.
- New full_answer: `"Tiny home in"`.
- New answer_parts: `["Tiny home in"]`.
- url_answer_ok: `false`.
  - Part 1 source: `expected_answer / end_markers.answer_in_text` = `"Tiny home in"`.
- Not keyed / limitation: Individual property names, adult/pet counts and dates have no authored page-verbatim parts; existing URL key is unchanged.

## extdev_filter_sf_exercise_dates

- Description: Find exercise events taking place in San Francisco between July 10-31.
- Provenance: Mind2Web / `74cb088a-06d9-4a5e-9b00-61fd6b874e89`.
- Old marker (unchanged): `"Exercise Events and Things to do in San Francisco, CA"`.
- New full_answer: `"Exercise Events and Things to do in San Francisco, CA"`.
- New answer_parts: `["Exercise Events and Things to do in San Francisco, CA"]`.
- url_answer_ok: `false`.
  - Part 1 source: `expected_answer / end_markers.answer_in_text` = `"Exercise Events and Things to do in San Francisco, CA"`.
- Not keyed / limitation: Individual event names and date labels are unavailable; existing date-query URL key is unchanged.

## extdev_filter_castles_europe_week

- Description: Search for Castles in Europe for a week next month and price below $1000 per night.
- Provenance: Mind2Web / `181e8206-2d04-47ea-bcaf-f701b8c5525a`.
- Old marker (unchanged): `"Castle in"`.
- New full_answer: `"Castle in"`.
- New answer_parts: `["Castle in"]`.
- url_answer_ok: `false`.
  - Part 1 source: `expected_answer / end_markers.answer_in_text` = `"Castle in"`.
- Not keyed / limitation: Individual property names and price/duration/date labels are unavailable; existing URL key is unchanged.

## Unchanged action-task note

Unchanged: contacting support is an action, not merely opening a URL; no URL-answer flag.

Changed tasks: 35; parts mode: 30; URL flags: 5.
