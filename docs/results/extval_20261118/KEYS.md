# extval key evidence (18 Nov 2026)

Each key below rests on the quoted page text. Every page was fetched on
**18 Nov 2026**, by plain HTTP GET or a local headless Chrome (Playwright
defaults, region resolved as GB), with no model call. Key format and grading rules:
docs/GRADER.md, "Scorer v2". Keys live in `bench/tasks_extval.py`; `basis`
repeats the reason in one line.

## `extval_nav_real_madrid_ucl_schedule`

* Source: Mind2Web-Live `mind2web-live_train_20240528.json:i6Lbofnb1gaYbej79uhKy`; site `espn.com`; deliverable **page**; host `espn.com`.
* Task: Find the Real Madrid team schedule of the UEFA Champions League championship in espn
* Accepted pages: `[{"path": "/soccer/team/fixtures/_/id/86/", "url_contains": "/league/UEFA.CHAMPIONS"}]`
* Reference: Real Madrid 2026-27 UEFA Champions League fixtures: Tue, Nov 24 Real Madrid v PSV Eindhoven; Wed, Dec 9 Arsenal v Real Madrid; Tue, Jan 19 Real Madrid v LASK Linz; Wed, Jan 27 Shakhtar Donetsk v Real Madrid
* Why: Fixtures page filtered to UEFA Champions League; source key /league/UEFA.CHAMPIONS.
* Page facts:
  * <https://www.espn.com/soccer/team/fixtures/_/id/86/league/UEFA.CHAMPIONS> (18 Nov 2026): "Real Madrid 2026-27 UEFA Champions League Schedule - ESPN (title); Real Madrid Fixtures ... Tue, Nov 24 Real Madrid v PSV Eindhoven 8:00 PM UEFA Champions League"

## `extval_nav_nfl_super_bowl_2015_scoreboard`

* Source: Mind2Web-Live `mind2web-live_train_20240528.json:j4W0lfpmu2n143wb_vHSN`; site `espn.com`; deliverable **page**; host `espn.com`.
* Task: Show me the NFL Scoreboard from the superbowl 2015 in espn
* Accepted pages: `[{"path": "/nfl/scoreboard", "url_contains": "seasontype/3", "text": ["Super Bowl XLIX", "Patriots", "Seahawks"]}, {"path": "/nfl/scoreboard", "url_contains": "seasontype/3", "text": ["Super Bowl 50", "Broncos", "Panthers"]}]`
* Reference: NFL Scoreboard, Super Bowl XLIX (played 1 Feb 2015, 2014 season): Patriots 28, Seahawks 24. (Super Bowl 50 of the 2015 season: Broncos 24, Panthers 10.)
* Why: 'superbowl 2015' reads as the Super Bowl played in 2015 (XLIX) or the 2015 season's (50, the Mind2Web-Live key); both postseason week-5 scoreboards are accepted, told apart by the game note on the page.
* Page facts:
  * <https://www.espn.com/nfl/scoreboard/_/year/2014/seasontype/3/week/5> (18 Nov 2026): "NFL Scores - Postseason Week 5, 2014 - ESPN (title); SUPER BOWL ... FINAL ... Patriots 28 Seahawks 24 Super Bowl XLIX"
  * <https://www.espn.com/nfl/scoreboard/_/week/5/year/2015/seasontype/3> (18 Nov 2026): "NFL Scores - Postseason Week 5, 2015 - ESPN (title); FINAL ... Panthers ... Broncos ... Super Bowl 50; Broncos ride defense's big plays to SB 50 victory"

## `extval_nav_spothero_love_field`

* Source: Mind2Web-Live `mind2web-live_train_20240528.json:OgIu4KqVQkduk2Q-rURvR`; site `spothero.com`; deliverable **page**; host `spothero.com`.
* Task: Find a parking spot near Dallas Love Field Airport in spothero
* Accepted pages: `[{"path": "/search", "path_mode": "suffix", "query": {"kind": {"any": ["airport"]}, "id": {"any": ["DAL"]}}}, {"path": "/search", "path_mode": "suffix", "query": {"search_string": {"contains": ["love field"]}}}, {"path": "/airport/dallas/dal-parking"}]`; `allow_search`
* Reference: SpotHero parking near Dallas Love Field (DAL), e.g. Candlewood Suites DAL - Uncovered Self Park; Marriott Dallas Suites & Medical Center DAL Airport - Uncovered Self Park.
* Why: Source key: search?kind=airport&id=DAL. SpotHero's own DAL landing page and a typed 'Love Field' search reach the same spots.
* Page facts:
  * <https://spothero.com/search?kind=airport&id=DAL&airport=true> (18 Nov 2026): "Dallas Love Field Parking ✈ Rates from $4.99 ✈ SpotHero (title); Candlewood Suites DAL - Uncovered Self Park"
  * <https://spothero.com/airport/dallas/dal-parking> (18 Nov 2026): "Dallas Love Field (DAL) Parking | SpotHero (title); SpotHero Parking Near Dallas Love Field (DAL)"

## `extval_filter_spothero_wheelchair_times_square`

* Source: Mind2Web-Live `mind2web-live_train_20240528.json:X8Pin4Cr6G_NXAEL6qUfO`; site `spothero.com`; deliverable **page**; host `spothero.com`.
* Task: View details for a Times Square parking lot that is wheelchair accessible in spothero
* Accepted pages: `[{"path": "/search", "path_mode": "suffix", "query": {"kind": {"any": ["destination"]}, "id": {"any": ["746"]}, "spot-id": {"min": 1}}, "text": ["Amenities", "Wheelchair Accessible"]}, {"path": "/search", "path_mode": "suffix", "query": {"search_string": {"contains": ["times square", "times sq"]}, "spot-id": {"min": 1}}, "text": ["Amenities", "Wheelchair Accessible"]}]`; `allow_search`
* Reference: 249 W 43rd St. - Valet Garage (Times Square): Amenities - Valet, Garage - Covered, On-Site Staff, Wheelchair Accessible.
* Why: Source key: Times Square destination id=746 with the Wheelchair Accessible filter. The filter does not change the URL; an opened lot's details (spot-id in the URL) list its amenities, and 'Wheelchair Accessible' appears in the page text only when the open lot has it.
* Page facts:
  * <https://spothero.com/search?kind=destination&id=746&view=dl&spot-id=3764> (18 Nov 2026): "249 W 43rd St. - Valet Garage ... Amenities / Valet / Garage - Covered / On-Site Staff / Wheelchair Accessible"
  * <https://spothero.com/search?kind=destination&id=746&view=dl&spot-id=19488> (18 Nov 2026): "Amenities / Valet / Garage - Covered / On-Site Staff (no Wheelchair Accessible: the text check rejects this lot)"

## `extval_nav_darienlake_gift_shops`

* Source: Mind2Web-Live `mind2web-live_train_20240528.json:kMn6BswkshmkS47_Vu7t0`; site `sixflags.com`; deliverable **page**; host `sixflags.com`.
* Task: Show me the gift shops available at a park in New York in sixflags
* Accepted pages: `[{"path": "/darienlake/", "path_mode": "prefix", "url_contains": "/shops"}]`
* Reference: Six Flags Darien Lake (Buffalo, New York) All Shopping: Backwoods Outfitters; Cartoon City Caricatures and Henna Tattoos; Coaster Candy; DL Gear; Emporium; Fun in the Sun; General Store; Sandal Beach Shoes; Steel City Station; Surf Shop Cabana Rentals
* Why: Source key: /darienlake .../shops. Darien Lake is the only New York park on the Select a Park list (Great Escape now redirects off sixflags.com).
* Page facts:
  * <https://www.sixflags.com/select-park?redirect=tickets> (18 Nov 2026): "Six Flags Darien Lake / BUFFALO - NEW YORK (the only NEW YORK park listed)"
  * <https://www.sixflags.com/darienlake/shops> (18 Nov 2026): "All Shopping ... our retail shops have just what you need to remember your day at Six Flags Darien Lake. ... Backwoods Outfitters | ... | Surf Shop Cabana Rentals"

## `extval_value_icse_2002_gil_tutorial`

* Source: WebWalkerQA `main:22`; site `icse-conferences.org`; deliverable **answer**; host `icse-conferences.org`.
* Task: What visual modeling language for complex systems was introduced in the ICSE 2002 tutorial led by Joseph Gil and others on May 21, 2002?
* Facts (one form of each must appear): `[["Beyond UML", ["Spider diagrams", "Constraint diagrams"], ["Spider diagram", "Constraint diagram"]]]`
* Reference: Advanced Visual Modeling: Beyond UML (Tutorial 14: spider diagrams, constraint diagrams and 3D-diagrams)
* Why: WebWalkerQA answer is the tutorial title; the same tutorial text names the notations it presents (spider and constraint diagrams), accepted as the 'language'.
* Page facts:
  * <http://www.icse-conferences.org/2002/info/tutorials.html> (18 Nov 2026): "Tutorial 14 Advanced Visual Modeling: Beyond UML Joseph Gil, Technion -Israel Institute of Technology ... Spider diagrams considerably extend Venn-diagrams ... Constraint diagrams enhance the arrow notation ... This is a half-day tutorial held on the morning of Tuesday May 21st."

## `extval_value_roviocon_theme_series`

* Source: WebWalkerQA `main:456`; site `rovio.com`; deliverable **answer**; host `rovio.com`.
* Task: What is the theme of RovioCon Google 2024 and the name of the Angry Birds animated series released during the 15th anniversary?
* Facts (one form of each must appear): `[["Slingshot to Stardom"], ["Mystery Island"]]`
* Reference: Theme: Slingshot to Stardom; animated series: Angry Birds Mystery Island: A Hatchlings Adventure
* Why: WebWalkerQA answer; both facts quoted from the two rovio.com articles.
* Page facts:
  * <https://www.rovio.com/articles/roviocon-google-a-celebration-of-games-growth-and-the-future-of-mobile/> (18 Nov 2026): "RovioCon Google 2024: Slingshot to Stardom ... With its theme “Slingshot to Stardom,” the event aims to ..."
  * <https://www.rovio.com/articles/angry-birds-celebrates-15th-anniversary-with-special-in-game-events-and-more/> (18 Nov 2026): "During the 15th anniversary year, Rovio has already launched Angry Birds Mystery Island: A Hatchlings Adventure, an animated series that premiered on Prime Video and Amazon Kids+ in May"

## `extval_value_icse_2002_deadlines`

* Source: WebWalkerQA `main:75`; site `icse-conferences.org`; deliverable **answer**; host `icse-conferences.org`.
* Task: What are the submission deadlines for technical papers and the doctoral symposium at the ICSE 2002 conference?
* Facts (one form of each must appear): `[["25 September 2001", "September 25, 2001", "September 25 2001", "Sept. 25, 2001", "Sep 25, 2001", "Sep. 25, 2001", "2001-09-25"], ["January 6, 2002", "6 January 2002", "January 6 2002", "Jan 6, 2002", "Jan. 6, 2002", "2002-01-06"]]`
* Reference: Technical papers: full paper 25 September 2001 (abstract 10 September 2001); Doctoral Symposium: January 6, 2002
* Why: WebWalkerQA answer; full-paper date from the technical papers CFP's Important Dates, doctoral symposium date from its CFP. Date renderings listed; the abstract date alone is not the paper deadline.
* Page facts:
  * <http://www.icse-conferences.org/2002/cfp/techpapers.html> (18 Nov 2026): "Important Dates / Abstract: 10 September 2001 / Full paper: 25 September 2001 / Notification of Acceptance: 07 December 2001"
  * <http://www.icse-conferences.org/2002/cfp/docsymp.html> (18 Nov 2026): "SUBMISSION DEADLINE / January 6, 2002"

## `extval_value_rovio_burger_king_ar_end`

* Source: WebWalkerQA `main:50`; site `rovio.com`; deliverable **answer**; host `rovio.com`.
* Task: When does the unique Angry Birds AR experience created by Zappar and Burger King for fans end in the US and Canada?
* Facts (one form of each must appear): `[["June 20", "20 June", "Jun 20", "Jun. 20", "20 Jun", "2021-06-20", "6/20/2021"]]`
* Reference: June 20, 2021 (it runs from May 10 to June 20 in the US and Canada)
* Why: WebWalkerQA answer June 20, 2021; the article line gives the day and month only, so the year is not required.
* Page facts:
  * <https://www.rovio.com/articles/angry-birds-fly-to-burger-king-with-new-toys-and-augmented-reality-experience/> (18 Nov 2026): "Participating regions include the US, EMEA, APAC and LaTam. The campaign runs through May 31 in most regions and from May 10 to June 20 in the US and Canada."
  * <https://www.rovio.com/articles/angry-birds-fly-to-burger-king-with-new-toys-and-augmented-reality-experience/> (18 Nov 2026): "article date line: 10.05.2021 (so June 20 is 2021)"

## `extval_value_junkworld_launch_update`

* Source: WebWalkerQA `main:553`; site `ironhidegames.com`; deliverable **answer**; host `ironhidegames.com`.
* Task: What is the official launch date of Junkworld on Apple Arcade, and what new feature was introduced in the January 2024 update?
* Facts (one form of each must appear): `[["September 22", "September 22nd", "22 September", "22nd September", "Sept 22", "Sept. 22", "Sep 22", "Sep. 22", "2023-09-22", "9/22/2023"], ["Daily Rewards", "Daily Reward"]]`
* Reference: September 22, 2023; New Daily Rewards
* Why: WebWalkerQA answer; launch date from news 307, feature from the January 24, 2024 post 329.
* Page facts:
  * <https://www.ironhidegames.com/News/Details/307> (18 Nov 2026): "JUNKWORLD IS COMING TO APPLE ARCADE ON SEPTEMBER 22ND! BY PATRICIA MAZZEI ON AUGUST 17, 2023"
  * <https://www.ironhidegames.com/News/Details/329> (18 Nov 2026): "NEW DAILY REWARDS IN JUNKWORLD! BY PATRICIA MAZZEI ON JANUARY 24, 2024"

## `extval_value_kingdom_rush_prize_comic`

* Source: WebWalkerQA `main:630`; site `ironhidegames.com`; deliverable **answer**; host `ironhidegames.com`.
* Task: What was the prize for Kingdom Rush winning Uruguay's national video game contest, and how was the game's world further expanded in 2012?
* Facts (one form of each must appear): `[["GDC", "Game Developers Conference"], ["All Access", "All-Access"], ["comic", "comics", "comic book"]]`
* Reference: A round trip to the 2012 GDC with an All Access Pass; the world was expanded with the Kingdom Rush comic (released October 2012).
* Why: WebWalkerQA answer; prize from news 42, comic from news 64. The prize is the trip and the pass, so both are required.
* Page facts:
  * <https://www.ironhidegames.com/News/Details/42> (18 Nov 2026): "Kingdom Rush got the 1st prize on our national videogame contest here in Uruguay. The prize? A round trip to 2012 GDC with an All Access Pass. :)"
  * <https://www.ironhidegames.com/News/Details/64> (18 Nov 2026): "COMIC RUSH! KINGDOM RUSH COMIC IS OUT! BY ALVARO AZOFRA ON OCTOBER 1, 2012"

## `extval_value_apec_photo_2021_country`

* Source: WebWalkerQA `main:201`; site `apec.org`; deliverable **answer**; host `apec.org`.
* Task: Which country's photographer won the first prize in the 2021 APEC Photo Contest for highlighting digitalization as a tool for economic recovery?
* Facts (one form of each must appear): `[["Philippines", "Philippine", "Filipino"]]`
* Reference: The Philippines (First Prize: Online Learning by Froiland Rivera)
* Why: WebWalkerQA answer; the APEC news release names the first-prize winner and country.
* Page facts:
  * <https://www.apec.org/press/news-releases/2021/winning-photo-of-apec-photo-contest-2021-highlight-digitalization-as-a-tool-for-recovery> (18 Nov 2026): "First Prize: Online Learning by Froiland Rivera, The Philippines."

## `extval_value_cambridge_present_perfect`

* Source: WebVoyager `Cambridge Dictionary--30`; site `cambridge.org`; deliverable **both**; host `dictionary.cambridge.org`.
* Task: Find the grammar for present perfect simple uses in English, including examples of affirmative, negative, and interrogative sentences, on the Cambridge Dictionary website.
* Accepted pages: `[{"path": "/grammar/british-grammar/present-perfect-simple-i-have-worked"}]`
* Facts (one form of each must appear): `[["I've been there a couple of times before", "I've seen 'Buddy'", "They've sold 110 so far", "It was the worst performance we have ever seen", "the most beautiful building I have ever seen", "It was the best decision I have ever made", "That's the first time I've seen you get angry", "has recently opened an office in the UK", "Niki and John have just come back", "She's broken her arm", "A fire has broken out", "has been empty for three years", "has been empty since 2006", "I've already booked my flight home", "I've already cleaned them", "I have worked", "I've worked", "You have worked", "You've worked", "We have worked", "We've worked", "They have worked", "They've worked", "She has worked", "She's worked", "He has worked", "He's worked", "It has worked", "It's worked"], ["We haven't met before", "She's never said sorry", "Your flowers haven't arrived", "I haven't finished my coffee", "have not worked", "haven't worked", "has not worked", "hasn't worked"], ["Have you ever tried to write your name and address with your left hand", "How long have you worked there", "Haven't you done your homework yet", "have we?", "What's just happened", "Why haven't you dressed in something warmer", "Have I worked", "Have you worked", "Have we worked", "Have they worked", "Has she worked", "Has he worked", "Has it worked", "Haven't I worked", "Haven't you worked", "Haven't we worked", "Haven't they worked", "Hasn't she worked", "Hasn't he worked", "Hasn't it worked", "Have I not worked", "Have you not worked", "Have we not worked", "Have they not worked", "Has she not worked", "Has he not worked", "Has it not worked"]]`
* Reference: Present perfect simple: uses (Cambridge Grammar, 'Present perfect simple (I have worked)'). Affirmative: I've been there a couple of times before. Negative: We haven't met before, have we? / Your flowers haven't arrived. Interrogative: Have you ever tried to write your name and address with your left hand?
* Why: WebVoyager reference examples; the accepted forms are every affirmative, negative and interrogative example sentence on the page plus the sentences its form table builds (have/has + worked, full and short, + - ? and ? -).
* Page facts:
  * <https://dictionary.cambridge.org/grammar/british-grammar/present-perfect-simple-i-have-worked> (18 Nov 2026): "Present perfect simple: uses ... I’ve been there a couple of times before. ... We haven’t met before, have we? ... Have you ever tried to write your name and address with your left hand? ... Your flowers haven’t arrived. ... How long have you worked there?; form table: + have/has worked, ’ve/’s; − have not/has not worked, haven’t/hasn’t; ? + Have/Has ... worked?; ? − Have/Has ... not worked?, Haven’t/Hasn’t"

## `extval_value_cambridge_feel_giddy_synonyms`

* Source: WebVoyager `Cambridge Dictionary--28`; site `cambridge.org`; deliverable **answer**; host `dictionary.cambridge.org`.
* Task: Search for "feel giddy" in Cambridge Dictionary's Thesaurus and list the synonyms the dictionary provides.
* Facts (one form of each must appear): `[["feel dizzy"], ["whirl"], ["spin"], ["reel"]]`
* Reference: feel dizzy; whirl; spin; reel
* Why: WebVoyager golden answer; the thesaurus page lists exactly these four synonyms, and the task asks for the list, so all four are required.
* Page facts:
  * <https://dictionary.cambridge.org/thesaurus/feel-giddy> (18 Nov 2026): "FEEL GIDDY - 4 Synonyms and Antonyms - Cambridge English (title); Synonyms and antonyms of feel giddy in English ... WHIRL / Synonyms / feel dizzy / whirl / spin / reel"

## `extval_value_hf_cc_by_sa_most_liked`

* Source: WebVoyager `Huggingface--3`; site `huggingface.co`; deliverable **answer**; host `huggingface.co`.
* Task: Look up a model with a license of cc-by-sa-4.0 with the most likes on Hugging face.
* Facts (one form of each must appear): `[["replit-code-v1-3b"]]`
* Reference: replit/replit-code-v1-3b
* Why: WebVoyager answer, unchanged since 2024: top cc-by-sa-4.0 model by likes, 748 likes vs 453 for the second (sort=likes page and models API, 18 Nov 2026).
* Page facts:
  * <https://huggingface.co/models?license=license:cc-by-sa-4.0&sort=likes> (18 Nov 2026): "Models with LICENSE:CC-BY-SA-4.0 license – Hugging Face (title); first result: replit/replit-code-v1-3b"
  * <https://huggingface.co/api/models?filter=license:cc-by-sa-4.0&sort=likes&direction=-1&limit=5> (18 Nov 2026): "replit/replit-code-v1-3b 748; defog/sqlcoder-7b-2 453; nlpaueb/legal-bert-base-uncased 336"

## `extval_filter_amazon_womens_hiking_boots`

* Source: WebVoyager `Amazon--7`; site `amazon.com`; deliverable **page**; host `amazon.com`.
* Task: Browse the women's hiking boots on Amazon and filter the results to show only those that are waterproof and have a rating of at least 4 stars and size 6.
* Accepted pages: `[{"path": "/s", "path_mode": "prefix", "url_contains": "p_72:2661618011", "query": {"k": {"contains": ["hiking boot"]}, "rh": {"has": "p_n_g-1004158520091:1285132011", "contains": ["p_n_g-1003509617111:32912228011", "p_n_g-101017968886111:221385166011"]}}}]`
* Reference: Women's hiking boots results filtered by Customer Review: 4 Stars & Up, Waterproof, and Women's Shoe Size: 6 (1-48 of 550 results).
* Why: Facet ids read from the live results sidebar: Customer Review '4 Stars & Up' p_72:2661618011; 'Waterproof' under Special Features (p_n_g-1003509617111:32912228011) or Water Resistance Level (p_n_g-101017968886111:221385166011), either accepted; Women's Shoe Size '6' p_n_g-1004158520091:1285132011. Search words must include 'hiking boot'.
* Page facts:
  * <https://www.amazon.com/s?k=women%27s+hiking+boots> (18 Nov 2026): "sidebar links: '4 Stars & Up' -> rh=p_72:2661618011 (Customer Review); 'Waterproof' -> rh=p_n_g-1003509617111:32912228011 (Special Features); 'Waterproof' -> rh=p_n_g-101017968886111:221385166011 (Water Resistance Level); '6' -> rh=p_n_g-1004158520091:1285132011 (Women's Shoe Size)"
  * <https://www.amazon.com/s?k=women%27s+hiking+boots&rh=p_72%3A2661618011%2Cp_n_g-1003509617111%3A32912228011%2Cp_n_g-1004158520091%3A1285132011> (18 Nov 2026): "1-48 of 550 results for "women's hiking boots""

## `extval_value_hf_trainer_parameters`

* Source: WebVoyager `Huggingface--39`; site `huggingface.co`; deliverable **answer**; host `huggingface.co`.
* Task: Investigate in the Hugging Face documentation how to utilize the 'Trainer' API for training a model on a custom dataset, and note the configurable parameters of the Trainer class.
* Facts (one form of each must appear): `[{"any": ["data_collator", "train_dataset", "eval_dataset", "processing_class", "model_init", "compute_loss_func", "compute_metrics", "callbacks", "optimizers", "optimizer_cls_and_kwargs", "preprocess_logits_for_metrics", "output_dir", "learning_rate", "per_device_train_batch_size", "per_device_eval_batch_size", "weight_decay", "eval_strategy", "save_strategy", "logging_steps", "warmup_steps", "gradient_accumulation_steps", "lr_scheduler_type", "max_steps", "report_to", "push_to_hub"], "min": 4}]`
* Reference: Create a TrainingArguments object (e.g. output_dir, learning_rate, per_device_train_batch_size, num_train_epochs, weight_decay, eval_strategy) and pass it with the model and your tokenized custom train_dataset/eval_dataset to Trainer, then call trainer.train(). Trainer class parameters: model, args (TrainingArguments), data_collator, train_dataset, eval_dataset, processing_class, model_init, compute_loss_func, compute_metrics, callbacks, optimizers, optimizer_cls_and_kwargs, preprocess_logits_for_metrics.
* Why: The Trainer signature on the transformers Trainer docs page lists 13 parameters; 'configurable parameters' can also be read as the TrainingArguments passed as args, documented on the same page. At least four distinct exact parameter identifiers from either list are required; the generic names model and args do not count.
* Page facts:
  * <https://huggingface.co/docs/transformers/main_classes/trainer> (18 Nov 2026): "class transformers.Trainer ( model ... = None args: transformers.training_args.TrainingArguments | None = None data_collator ... train_dataset ... eval_dataset ... processing_class ... model_init ... compute_loss_func ... compute_metrics ... callbacks ... optimizers ... = (None, None) optimizer_cls_and_kwargs ... preprocess_logits_for_metrics ... = None )"
  * <https://huggingface.co/docs/transformers/main_classes/trainer> (18 Nov 2026): "TrainingArguments parameters documented on the same page include output_dir (, learning_rate (, per_device_train_batch_size (, weight_decay (, eval_strategy (, save_strategy (, warmup_steps (, gradient_accumulation_steps (, lr_scheduler_type (, max_steps (, report_to (, push_to_hub ("

## `extval_filter_amazon_gaming_desktop`

* Source: WebVoyager `Amazon--2`; site `amazon.com`; deliverable **page**; host `amazon.com`.
* Task: Find a gaming desktop with Windows 11 Home, and the disk size should be 1TB.
* Accepted pages: `[{"path": "/s", "path_mode": "prefix", "query": {"k": {"contains": ["gaming"]}, "rh": {"has": "p_n_g-1004209391091:5446812011", "contains": ["p_n_g-1004198069091:23724790011"]}}}, {"path": "/dp/", "text": ["Gaming", "Windows 11 Home", "1TB"]}, {"path": "/dp/", "text": ["Gaming", "Windows 11 Home", "1 TB"]}]`
* Reference: Gaming desktop results filtered to Operating System: Windows 11 Home and Hard Drive Size: 1 TB (431 results), e.g. msi Codex Z2 Gaming Desktop, AMD R7-8700F, RTX 5060Ti, 16GB DDR5, 1TB SSD, Windows 11 Home.
* Why: Facet ids read from the live sidebar: Hard Drive Size '1 TB' p_n_g-1004209391091:5446812011, Operating System 'Windows 11 Home' p_n_g-1004198069091:23724790011. A product page that names Gaming, Windows 11 Home and a 1TB/1 TB disk is the other accepted end state.
* Page facts:
  * <https://www.amazon.com/s?k=gaming+desktop> (18 Nov 2026): "sidebar links: '1 TB' -> rh=p_n_g-1004209391091:5446812011 (Hard Drive Size); 'Windows 11 Home' -> rh=p_n_g-1004198069091:23724790011 (Operating System)"
  * <https://www.amazon.com/s?k=gaming+desktop&rh=p_n_g-1004209391091%3A5446812011%2Cp_n_g-1004198069091%3A23724790011> (18 Nov 2026): "1-16 of 431 results for "gaming desktop" ... msi Codex Z2 Gaming Desktop, AMD R7-8700F, RTX 5060Ti, 16GB DDR5, 1TB SSD ... Windows 11 Home"
