# Extdev key changes: v1 -> scorer v2

The v1 keys are unchanged in `bench/tasks_extdev.py` (and in git history); the v2 keys are in
`bench/keys_extdev_v2.py` (SHA-256 `9b7b57a7d2fcaa3e006ed0c985e7c9dce8a6dd2a46f1049d893ec706e80528d7`). Rules: [GRADER.md](../../GRADER.md), 'Scorer v2'.

All 40 tasks have a v2 key. 26 change what is accepted beyond the rule changes; the other
14 restate the v1 content in v2 form. Every change cites the page fact it rests on:
a saved page-text excerpt with its row (D = default run, U = ultrafast run, S = smoke; numbering as in
`extdev_rows.csv`), a URL fetched with a plain HTTP GET on 18 Nov 2026 with the quoted text, or the
task's own words. No key was changed to make an arm pass: changes widen to outcomes the page or
task supports, and several narrow (mansions now needs the task's own adults=3 and Europe).

Rule-level changes that apply to every key (deliverable, normalisation, dump guard, page-only
evidence for answer tasks) are in GRADER.md and are not repeated per task.

## extdev_filter_greatamerica_thrill

- Task: Find thrill rides in Six Flags Great America, Chicago, IL on sixflags
- Change: **same content**
- Deliverable: `page`
- Evidence: Page deliverable: the answer no longer has to contain 'Thrill' (rule change, not key change).

<details><summary>v1 key -> v2 key</summary>

v1:

```json
{
 "check_url_contains": "/greatamerica/attractions?ride-category=thrill",
 "end_markers": {
  "host": "sixflags.com",
  "url_contains": "/greatamerica/attractions?ride-category=thrill",
  "deny": [
   "/signin",
   "/login",
   "/sorry/"
  ],
  "answer_in_text": "Thrill"
 },
 "full_answer": "Thrill",
 "answer_parts": [
  "Thrill"
 ]
}
```

v2:

```json
{
 "deliverable": "page",
 "host": "sixflags.com",
 "pages": [
  {
   "path": "/greatamerica/attractions",
   "query": {
    "ride-category": {
     "any": [
      "thrill"
     ]
    }
   }
  }
 ],
 "reference": "DC Super-Villains Swing; Giant Drop; Sky Striker",
 "basis": "v1 URL key; reference from the saved filter page (D1)."
}
```

</details>

## extdev_value_nba_2021_leaders

- Task: Who were the NBA season leaders from the 2020-21 regular season? in espn
- Change: **Accepts 'Jimmy Butler' for 'Jimmy Butler III'.**
- Deliverable: `answer`
- Evidence: Same player; the v1 numbers stay required.

<details><summary>v1 key -> v2 key</summary>

v1:

```json
{
 "check_url_contains": "/nba/stats/_/season/2021/seasontype/2",
 "end_markers": {
  "host": "espn.com",
  "url_contains": "/nba/stats/_/season/2021/seasontype/2",
  "deny": [
   "/signin",
   "/login",
   "/sorry/"
  ],
  "answer_in_text": "Russell Westbrook"
 },
 "full_answer": "Russell Westbrook; Stephen Curry; 32.0; 11.7; 5.3; Clint Capela; 14.3; Rudy Gobert; 2.7; Jimmy Butler III; 2.1",
 "answer_parts": [
  "Russell Westbrook",
  "Stephen Curry",
  "32.0",
  "11.7",
  "5.3",
  "Clint Capela",
  "14.3",
  "Rudy Gobert",
  "2.7",
  "Jimmy Butler III",
  "2.1"
 ]
}
```

v2:

```json
{
 "deliverable": "answer",
 "host": "espn.com",
 "facts": [
  [
   "Russell Westbrook"
  ],
  [
   "Stephen Curry"
  ],
  [
   "32.0"
  ],
  [
   "11.7"
  ],
  [
   "5.3"
  ],
  [
   "Clint Capela"
  ],
  [
   "14.3"
  ],
  [
   "Rudy Gobert"
  ],
  [
   "2.7"
  ],
  [
   "Jimmy Butler"
  ],
  [
   "2.1"
  ]
 ],
 "reference": "Russell Westbrook; Stephen Curry; 32.0; 11.7; 5.3; Clint Capela; 14.3; Rudy Gobert; 2.7; Jimmy Butler III; 2.1",
 "basis": "v1 parts; 'Jimmy Butler III' -> 'Jimmy Butler' (same player)."
}
```

</details>

## extdev_spa_dota_dlc_cart

- Task: Find Dota 2 game and add all DLC to cart in steam
- Change: **Cart page must show the soundtrack; also accepts Steam's add-to-cart confirmation on the Dota 2 app page.**
- Deliverable: `page`
- Evidence: U3 (cart): "Your Shopping Cart (1 item) The Dota 2 Official Soundtrack $9.99".
- Evidence: D9 (app/570): "Cart 1 Added to your cart! The Dota 2 Official Soundtrack $9.99 For my account Remove Continue Shopping View My Cart (1)".

<details><summary>v1 key -> v2 key</summary>

v1:

```json
{
 "check_url_contains": "/cart/",
 "end_markers": {
  "host": "store.steampowered.com",
  "url_contains": "/cart/",
  "deny": [
   "/signin",
   "/login",
   "/sorry/"
  ],
  "answer_in_text": "The Dota 2 Official Soundtrack"
 },
 "full_answer": "The Dota 2 Official Soundtrack",
 "answer_parts": [
  "The Dota 2 Official Soundtrack"
 ]
}
```

v2:

```json
{
 "deliverable": "page",
 "host": "store.steampowered.com",
 "pages": [
  {
   "path": "/cart/",
   "text": [
    "The Dota 2 Official Soundtrack"
   ]
  },
  {
   "path": "/app/570/",
   "text": [
    "Added to your cart!",
    "The Dota 2 Official Soundtrack"
   ]
  }
 ],
 "reference": "The Dota 2 Official Soundtrack is in the cart ($9.99).",
 "basis": "cart page text (U3/D12) and Steam's add-to-cart confirmation on the app page (D9)."
}
```

</details>

## extdev_filter_booking_times_square

- Task: Find a 4 star rated Hotel in New York Timesquare for 2 adults in booking
- Change: **Answer task: any of three cited 4-star Times Square hotels; the search URL and '2 adults' part are no longer required.**
- Deliverable: `answer`
- Evidence: D13 (booking.com/fourstars/city/us/new-york.html): "The best 4-star hotels in New York ... LUMA Hotel - Times Square Hotel in Manhattan, New York Located 984 feet from Times Square".
- Evidence: U4 (district/us/new-york/timessquare.html): "Riu Plaza Manhattan Times Square Hotel in Times Square, New York ... This 4-star hotel offers room service".
- Evidence: '2 adults' is Booking's default occupancy: D13 and U4 both show "Select occupancy 2 adults · 0 children · 1 room".

<details><summary>v1 key -> v2 key</summary>

v1:

```json
{
 "check_url_contains": "/searchresults.html?dest_id=ChIJnaBtqVVYwokRaAqg4aX1C4Y;dest_type=landmark;latitude=40.7579747;longitude=-73.9855426;nflt=ht_id%3D204%3Bclass%3D4",
 "end_markers": {
  "host": "booking.com",
  "url_contains": "/searchresults.html?dest_id=ChIJnaBtqVVYwokRaAqg4aX1C4Y;dest_type=landmark;latitude=40.7579747;longitude=-73.9855426;nflt=ht_id%3D204%3Bclass%3D4",
  "deny": [
   "/signin",
   "/login",
   "/sorry/"
  ],
  "answer_in_text": "Millennium Premier Hotel New York Times Square"
 },
 "full_answer": "Millennium Premier Hotel New York Times Square; 2 adults",
 "answer_parts": [
  "Millennium Premier Hotel New York Times Square",
  "2 adults"
 ]
}
```

v2:

```json
{
 "deliverable": "answer",
 "host": "booking.com",
 "facts": [
  [
   "Millennium Premier Hotel New York Times Square",
   "LUMA Hotel - Times Square",
   "Riu Plaza Manhattan Times Square"
  ]
 ],
 "reference": "Millennium Premier Hotel New York Times Square",
 "basis": "v1 hotel; LUMA on Booking's 4-star New York list (D13); Riu 'This 4-star hotel' (U4)."
}
```

</details>

## extdev_filter_frontiercity_family

- Task: What are the family rides available at frontier city? on sixflags
- Change: **same content**
- Deliverable: `page`
- Evidence: Page deliverable; reference list from D17: "See Our Rides Billy's Frog Hopper Frankie's Mine Train Grand Carousel Hootie's Tree House Ol' 89er Express Quick Draw Rocky's Ranger Planes".

<details><summary>v1 key -> v2 key</summary>

v1:

```json
{
 "check_url_contains": "/frontiercity/attractions?ride-category=family",
 "end_markers": {
  "host": "sixflags.com",
  "url_contains": "/frontiercity/attractions?ride-category=family",
  "deny": [
   "/signin",
   "/login",
   "/sorry/"
  ],
  "answer_in_text": "Family"
 },
 "full_answer": "Family",
 "answer_parts": [
  "Family"
 ]
}
```

v2:

```json
{
 "deliverable": "page",
 "host": "sixflags.com",
 "pages": [
  {
   "path": "/frontiercity/attractions",
   "query": {
    "ride-category": {
     "any": [
      "family"
     ]
    }
   }
  }
 ],
 "reference": "Billy's Frog Hopper; Frankie's Mine Train; Grand Carousel; Hootie's Tree House; Ol' 89er Express; Quick Draw; Rocky's Ranger Planes",
 "basis": "v1 URL key; reference from the saved filter page (D17)."
}
```

</details>

## extdev_nav_spothero_contact

- Task: Contact the support service on spothero
- Change: **same content**
- Deliverable: `page`
- Evidence: Page deliverable on /contact; D21 page: "Contact Customer Heroes Give us a call ... +1 (844) 324-7768 Every day, 6am-11pm CST".

<details><summary>v1 key -> v2 key</summary>

v1:

```json
{
 "check_url_contains": "/contact",
 "end_markers": {
  "host": "spothero.com",
  "url_contains": "/contact",
  "deny": [
   "/signin",
   "/login",
   "/sorry/"
  ],
  "answer_in_text": "Contact Customer Heroes"
 }
}
```

v2:

```json
{
 "deliverable": "page",
 "host": "spothero.com",
 "pages": [
  {
   "path": "/contact"
  }
 ],
 "reference": "SpotHero support: call +1 (844) 324-7768 (every day, 6am-11pm CST) or send a message with the Contact Customer Heroes form at https://spothero.com/contact",
 "basis": "v1 URL key; reference from the saved contact page (D21)."
}
```

</details>

## extdev_filter_airbnb_europe_mansions

- Task: I want to see mansions for 3 adults to stay in in europe during any month in airbnb
- Change: **Narrowed to the task's own constraints (Europe path, adults=3, flexible dates); accepts Airbnb's kg_and_tags[] alias for the category tag.**
- Deliverable: `page`
- Evidence: Task text: "mansions for 3 adults ... in europe during any month".
- Evidence: D27 URL: "/s/Europe/homes?adults=3&category_tag=Tag%3A8115&...&date_picker_type=flexible_dates".
- Evidence: Alias: U40 URL carries the castle tag as "kg_and_tags%5B%5D=Tag%3A8047 ... selected_filter_order%5B%5D=kg_and_tags%3ATag%3A8047".

<details><summary>v1 key -> v2 key</summary>

v1:

```json
{
 "check_url_contains": "category_tag=Tag%3A8115",
 "end_markers": {
  "host": "airbnb.com",
  "url_contains": "category_tag=Tag%3A8115",
  "deny": [
   "/signin",
   "/login",
   "/sorry/"
  ],
  "answer_in_text": "mansions",
  "path_suffix": "/s/Europe/homes"
 },
 "full_answer": "mansions; Any month; 3 guests",
 "answer_parts": [
  "mansions",
  "Any month",
  "3 guests"
 ]
}
```

v2:

```json
{
 "deliverable": "page",
 "host": "airbnb.com",
 "pages": [
  {
   "path": "/s/Europe/homes",
   "query": {
    "category_tag": {
     "any": [
      "Tag:8115"
     ]
    },
    "adults": {
     "any": [
      "3"
     ]
    },
    "date_picker_type": {
     "any": [
      "flexible_dates"
     ]
    }
   }
  },
  {
   "path": "/s/Europe/homes",
   "query": {
    "kg_and_tags[]": {
     "any": [
      "Tag:8115"
     ]
    },
    "adults": {
     "any": [
      "3"
     ]
    },
    "date_picker_type": {
     "any": [
      "flexible_dates"
     ]
    }
   }
  }
 ],
 "reference": "Mansions in Europe for 3 adults, flexible dates in any month.",
 "basis": "v1 tag Tag:8115 plus the task's own '3 adults', 'Europe' and 'any month'."
}
```

</details>

## extdev_value_icse_2004_chair

- Task: What were the exact dates and the General Chair for the ICSE conference in 2004?
- Change: **Answer task (any icse-conferences.org page); accepts the day-month rendering '23-28 May 2004'.**
- Deliverable: `answer`
- Evidence: D31 (2004/index.html): "hosted the ICSE conference from 23rd to 28th May" (the site's own day-month order); same dates.

<details><summary>v1 key -> v2 key</summary>

v1:

```json
{
 "check_url_contains": "/history.html",
 "end_markers": {
  "host": "icse-conferences.org",
  "url_contains": "/history.html",
  "deny": [
   "/signin",
   "/login",
   "/sorry/"
  ],
  "answer_in_text": "Anthony Finkelstein"
 },
 "full_answer": "Anthony Finkelstein; May 23-28, 2004",
 "answer_parts": [
  "Anthony Finkelstein",
  "May 23-28, 2004"
 ]
}
```

v2:

```json
{
 "deliverable": "answer",
 "host": "icse-conferences.org",
 "facts": [
  [
   "Anthony Finkelstein"
  ],
  [
   "May 23-28, 2004",
   "23-28 May 2004"
  ]
 ],
 "reference": "May 23-28, 2004; Anthony Finkelstein",
 "basis": "v1 parts; day-month order is a format variant (2004/org_ctte.htm, D32)."
}
```

</details>

## extdev_value_icse_duplicate_statement

- Task: When and where was the ICSE duplicate submission statement agreed upon?
- Change: **v1 phrase split into its three facts (place, venue, month).**
- Deliverable: `answer`
- Evidence: v1 marker "Charleston, South Carolina at FSE-10 in November 2002".

<details><summary>v1 key -> v2 key</summary>

v1:

```json
{
 "check_url_contains": "/duplicate.html",
 "end_markers": {
  "host": "icse-conferences.org",
  "url_contains": "/duplicate.html",
  "deny": [
   "/signin",
   "/login",
   "/sorry/"
  ],
  "answer_in_text": "Charleston, South Carolina at FSE-10 in November 2002"
 },
 "full_answer": "Charleston, South Carolina at FSE-10 in November 2002",
 "answer_parts": [
  "Charleston, South Carolina at FSE-10 in November 2002"
 ]
}
```

v2:

```json
{
 "deliverable": "answer",
 "host": "icse-conferences.org",
 "facts": [
  [
   "Charleston, South Carolina"
  ],
  [
   "FSE-10"
  ],
  [
   "November 2002"
  ]
 ],
 "reference": "Charleston, South Carolina at FSE-10 in November 2002",
 "basis": "v1 phrase split into its three facts."
}
```

</details>

## extdev_value_icse_2002_chairs

- Task: Who were the program committee chairs for the ICSE 2002 conference, and when and where was this conference held?
- Change: **Chairs as two facts (v1 joined them with a newline); also accepts 'May 19-24, 2002'.**
- Deliverable: `answer`
- Evidence: D37 (2002/info/ccommittee.html): "Orlando, Florida, USA May 19-25, 2002".
- Evidence: D40 (history.html, same site): "24th ICSE 2002 Orlando, Florida, USA May 19-24, 2002 ... Michal Young, University of Oregon, USA and Jeff Magee".

<details><summary>v1 key -> v2 key</summary>

v1:

```json
{
 "check_url_contains": "/2002/info/ccommittee.html",
 "end_markers": {
  "host": "icse-conferences.org",
  "url_contains": "/2002/info/ccommittee.html",
  "deny": [
   "/signin",
   "/login",
   "/sorry/"
  ],
  "answer_in_text": "Michal Young\nJeff Magee"
 },
 "full_answer": "Michal Young\nJeff Magee; Orlando, Florida, USA; May 19-25, 2002",
 "answer_parts": [
  "Michal Young\nJeff Magee",
  "Orlando, Florida, USA",
  "May 19-25, 2002"
 ]
}
```

v2:

```json
{
 "deliverable": "answer",
 "host": "icse-conferences.org",
 "facts": [
  [
   "Michal Young"
  ],
  [
   "Jeff Magee"
  ],
  [
   "Orlando"
  ],
  [
   "May 19-25, 2002",
   "19-25 May 2002",
   "May 19-24, 2002",
   "19-24 May 2002"
  ]
 ],
 "reference": "Michal Young and Jeff Magee; May 19-25, 2002; Orlando, Florida, USA",
 "basis": "v1 parts; the same site's history.html says 'May 19-24, 2002' (D40)."
}
```

</details>

## extdev_value_rovio_anniversary

- Task: Who is responsible for overseeing the Angry Birds brand strategy during the 15th anniversary celebrations, and what major project is highlighted as part of these celebrations?
- Change: **Person by name (title optional); project also as 'Angry Birds Movie 3'.**
- Deliverable: `answer`
- Evidence: https://www.rovio.com/articles/angry-birds-celebrates-15th-anniversary-with-special-in-game-events-and-more/: "said Eeva Aaltonen , Head of Brand Operations at Rovio"; "announced the third installment of The Angry Birds Movie series".
- Evidence: https://en.wikipedia.org/wiki/The_Angry_Birds_Movie_3: "The Angry Birds Movie 3 is an upcoming animated comedy film ... the third installment in the Angry Birds film series".

<details><summary>v1 key -> v2 key</summary>

v1:

```json
{
 "check_url_contains": "/articles/angry-birds-celebrates-15th-anniversary-with-special-in-game-events-and-more/",
 "end_markers": {
  "host": "rovio.com",
  "url_contains": "/articles/angry-birds-celebrates-15th-anniversary-with-special-in-game-events-and-more/",
  "deny": [
   "/signin",
   "/login",
   "/sorry/"
  ],
  "answer_in_text": "Eeva Aaltonen, Head of Brand Operations at Rovio"
 },
 "full_answer": "Eeva Aaltonen, Head of Brand Operations at Rovio; the third installment of The Angry Birds Movie series",
 "answer_parts": [
  "Eeva Aaltonen, Head of Brand Operations at Rovio",
  "the third installment of The Angry Birds Movie series"
 ]
}
```

v2:

```json
{
 "deliverable": "answer",
 "host": "rovio.com",
 "facts": [
  [
   "Eeva Aaltonen"
  ],
  [
   "third installment of The Angry Birds Movie",
   "Angry Birds Movie 3"
  ]
 ],
 "reference": "Eeva Aaltonen, Head of Brand Operations at Rovio; the third installment of The Angry Birds Movie series",
 "basis": "v1 parts; 'The Angry Birds Movie 3' is that third installment (Wikipedia GET)."
}
```

</details>

## extdev_value_apec_tourism_actions

- Task: What proactive steps did the APEC 12th Tourism Ministerial Meeting conclude to address the challenges in tourism due to sea level rise?
- Change: **v1 parts shortened to their facts: 'Regenerative Tourism', the well-being list, 'resilient tourism ecosystems'.**
- Deliverable: `answer`
- Evidence: v1 parts (authored from the 12th APEC Tourism Ministerial statement).

<details><summary>v1 key -> v2 key</summary>

v1:

```json
{
 "check_url_contains": "/meeting-papers/sectoral-ministerial-meetings/general/12th-apec-tourism-ministerial-meeting",
 "end_markers": {
  "host": "apec.org",
  "url_contains": "/meeting-papers/sectoral-ministerial-meetings/general/12th-apec-tourism-ministerial-meeting",
  "deny": [
   "/signin",
   "/login",
   "/sorry/"
  ],
  "answer_in_text": "Policy Recommendations for Tourism of the Future: Regenerative Tourism"
 },
 "full_answer": "Policy Recommendations for Tourism of the Future: Regenerative Tourism; economic, social, cultural and environmental well-being; creation of resilient tourism ecosystems",
 "answer_parts": [
  "Policy Recommendations for Tourism of the Future: Regenerative Tourism",
  "economic, social, cultural and environmental well-being",
  "creation of resilient tourism ecosystems"
 ]
}
```

v2:

```json
{
 "deliverable": "answer",
 "host": "apec.org",
 "facts": [
  [
   "Regenerative Tourism"
  ],
  [
   "economic, social, cultural and environmental well-being"
  ],
  [
   "resilient tourism ecosystems"
  ]
 ],
 "reference": "Continue implementing the Policy Recommendations for Tourism of the Future: Regenerative Tourism, which prioritizes economic, social, cultural and environmental well-being and the creation of resilient tourism ecosystems.",
 "basis": "v1 parts, shortened to the facts."
}
```

</details>

## extdev_value_apec_peru_arrivals

- Task: What is the target for international tourist arrivals in Peru for 2024?
- Change: **same content**
- Deliverable: `answer`
- Evidence: v1 marker "4.4 million".

<details><summary>v1 key -> v2 key</summary>

v1:

```json
{
 "check_url_contains": "/press/news-releases/2024/ministers-safeguard-tourism-sector-s-role-as-driver-of-economic-growth",
 "end_markers": {
  "host": "apec.org",
  "url_contains": "/press/news-releases/2024/ministers-safeguard-tourism-sector-s-role-as-driver-of-economic-growth",
  "deny": [
   "/signin",
   "/login",
   "/sorry/"
  ],
  "answer_in_text": "4.4 million"
 }
}
```

v2:

```json
{
 "deliverable": "answer",
 "host": "apec.org",
 "facts": [
  [
   "4.4 million"
  ]
 ],
 "reference": "4.4 million",
 "basis": "v1 marker."
}
```

</details>

## extdev_value_apec_ministers_chair

- Task: Who chaired the APEC Tourism Ministers Meeting on June 9, 2024?
- Change: **same content**
- Deliverable: `answer`
- Evidence: v1 marker "Elizabeth Galdo"; the URL is no longer required (answer task).

<details><summary>v1 key -> v2 key</summary>

v1:

```json
{
 "check_url_contains": "/press/news-releases/2024/apec-tourism-ministers-issue-joint-statement",
 "end_markers": {
  "host": "apec.org",
  "url_contains": "/press/news-releases/2024/apec-tourism-ministers-issue-joint-statement",
  "deny": [
   "/signin",
   "/login",
   "/sorry/"
  ],
  "answer_in_text": "Elizabeth Galdo"
 }
}
```

v2:

```json
{
 "deliverable": "answer",
 "host": "apec.org",
 "facts": [
  [
   "Elizabeth Galdo"
  ]
 ],
 "reference": "Elizabeth Galdo",
 "basis": "v1 marker."
}
```

</details>

## extdev_search_booking_la_filters

- Task: Search for properties in Los Angeles, browse the results page to see what filters are available, list some of them.
- Change: **Any two filter names from the page's filter block, instead of the review-score block verbatim.**
- Deliverable: `both`
- Evidence: D57 (booking.com/city/us/los-angeles.html): "Filter by: Property ratingIncludes stars and other ratings. 5 stars 4 stars 3 stars 2 stars 1 star Review score Wonderful: 9+ Very Good: 8+ Good: 7+ Pleasant: 6+".
- Evidence: Task text: "list some of them".

<details><summary>v1 key -> v2 key</summary>

v1:

```json
{
 "check_url_contains": "/city/us/los-angeles.html",
 "end_markers": {
  "host": "booking.com",
  "url_contains": "/city/us/los-angeles.html",
  "deny": [
   "/signin",
   "/login",
   "/sorry/"
  ],
  "answer_in_text": "Wonderful: 9+\nVery Good: 8+\nGood: 7+\nPleasant: 6+"
 },
 "full_answer": "Wonderful: 9+\nVery Good: 8+\nGood: 7+\nPleasant: 6+",
 "answer_parts": [
  "Wonderful: 9+\nVery Good: 8+\nGood: 7+\nPleasant: 6+"
 ]
}
```

v2:

```json
{
 "deliverable": "both",
 "host": "booking.com",
 "pages": [
  {
   "path": "/city/us/los-angeles.html"
  }
 ],
 "facts": [
  {
   "any": [
    "Property rating",
    "5 stars",
    "4 stars",
    "3 stars",
    "2 stars",
    "1 star",
    "Review score",
    "Wonderful: 9+",
    "Very Good: 8+",
    "Good: 7+",
    "Pleasant: 6+"
   ],
   "min": 2
  }
 ],
 "reference": "Property rating: 5 stars, 4 stars, 3 stars, 2 stars, 1 star; Review score: Wonderful: 9+, Very Good: 8+, Good: 7+, Pleasant: 6+",
 "basis": "filter block 'Filter by: Property rating ... Pleasant: 6+' on the saved LA page (D57)."
}
```

</details>

## extdev_value_hf_first_user_message

- Task: Check the Dataset Viewer for ai2lumos/lumos_complex_qa_plan_onetime on Hugging face. what is the content corresponding to user in the first message?
- Change: **Fixed a malformed key: v1 held a literal backslash-n; split into the three sentences.**
- Deliverable: `answer`
- Evidence: D64 (viewer page): "\"content\": \"Please provide a reasonable subgoal-based plan to solve the given task.\nTask: What was the opening date ...\"" (the viewer shows the JSON escape).

<details><summary>v1 key -> v2 key</summary>

v1:

```json
{
 "check_url_contains": "/datasets/ai2lumos/lumos_complex_qa_plan_onetime/viewer/default/train",
 "end_markers": {
  "host": "huggingface.co",
  "url_contains": "/datasets/ai2lumos/lumos_complex_qa_plan_onetime/viewer/default/train",
  "deny": [
   "/signin",
   "/login",
   "/sorry/"
  ],
  "answer_in_text": "Please provide a reasonable subgoal-based plan to solve the given task.\\nTask: What was the opening date of the museum dedicated to the war that, after it occurred, Boston became one of the wealthiest international ports?; Initial Environment Description: None."
 }
}
```

v2:

```json
{
 "deliverable": "answer",
 "host": "huggingface.co",
 "facts": [
  [
   "Please provide a reasonable subgoal-based plan to solve the given task."
  ],
  [
   "What was the opening date of the museum dedicated to the war that, after it occurred, Boston became one of the wealthiest international ports?"
  ],
  [
   "Initial Environment Description: None."
  ]
 ],
 "reference": "Please provide a reasonable subgoal-based plan to solve the given task.\nTask: What was the opening date of the museum dedicated to the war that, after it occurred, Boston became one of the wealthiest international ports?; Initial Environment Description: None.",
 "basis": "v1 marker held a literal backslash-n; split at it (viewer text, D64)."
}
```

</details>

## extdev_value_hf_tei_strengths

- Task: Check out Text Embeddings Inference in Hugging face's Doc to summarise the strengths of the toolkit.
- Change: **Summary task: one distinctive term per listed strength instead of six verbatim sentences.**
- Deliverable: `answer`
- Evidence: v1 parts, each authored verbatim from huggingface.co/docs/text-embeddings-inference/index; terms: Flash Attention, Candle, cuBLASLt, graph compilation, Docker, boot time, dynamic batching, Safetensors, Open Telemetry, Prometheus.

<details><summary>v1 key -> v2 key</summary>

v1:

```json
{
 "check_url_contains": "/docs/text-embeddings-inference/index",
 "end_markers": {
  "host": "huggingface.co",
  "url_contains": "/docs/text-embeddings-inference/index",
  "deny": [
   "/signin",
   "/login",
   "/sorry/"
  ],
  "answer_in_text": "Optimized Inference: TEI leverages Flash Attention, Candle, and cuBLASLt by using optimized transformers code for inference."
 },
 "full_answer": "Optimized Inference: TEI leverages Flash Attention, Candle, and cuBLASLt by using optimized transformers code for inference.; Streamlined Deployment: TEI eliminates the need for a model graph compilation step for an easier deployment process.; Efficient Resource Utilization: Benefit from small Docker images and rapid boot times, allowing for true serverless capabilities.; Dynamic Batching: TEI incorporates token-based dynamic batching thus optimizing resource utilization during inference.; Safetensors weight loading: TEI loads Safetensors weights for faster boot times.; Production-Ready: TEI supports distributed tracing through Open Telemetry and exports Prometheus metrics.",
 "answer_parts": [
  "Optimized Inference: TEI leverages Flash Attention, Candle, and cuBLASLt by using optimized transformers code for inference.",
  "Streamlined Deployment: TEI eliminates the need for a model graph compilation step for an easier deployment process.",
  "Efficient Resource Utilization: Benefit from small Docker images and rapid boot times, allowing for true serverless capabilities.",
  "Dynamic Batching: TEI incorporates token-based dynamic batching thus optimizing resource utilization during inference.",
  "Safetensors weight loading: TEI loads Safetensors weights for faster boot times.",
  "Production-Ready: TEI supports distributed tracing through Open Telemetry and exports Prometheus metrics."
 ]
}
```

v2:

```json
{
 "deliverable": "answer",
 "host": "huggingface.co",
 "facts": [
  [
   "Flash Attention"
  ],
  [
   "Candle"
  ],
  [
   "cuBLASLt"
  ],
  [
   "graph compilation"
  ],
  [
   "Docker"
  ],
  [
   "boot time",
   "boot times",
   "startup",
   "start-up",
   "boot"
  ],
  [
   "dynamic batching"
  ],
  [
   "Safetensors"
  ],
  [
   "OpenTelemetry",
   "Open Telemetry"
  ],
  [
   "Prometheus"
  ]
 ],
 "reference": "Optimized Inference: TEI leverages Flash Attention, Candle, and cuBLASLt by using optimized transformers code for inference. Streamlined Deployment: TEI eliminates the need for a model graph compilation step for an easier deployment process. Efficient Resource Utilization: Benefit from small Docker images and rapid boot times, allowing for true serverless capabilities. Dynamic Batching: TEI incorporates token-based dynamic batching thus optimizing resource utilization during inference. Safetensors weight loading: TEI loads Safetensors weights for faster boot times. Production-Ready: TEI supports distributed tracing through Open Telemetry and exports Prometheus metrics.",
 "basis": "v1 sentences reduced to the distinctive term of each listed strength."
}
```

</details>

## extdev_nav_ronaldo_world_cup_stats

- Task: Find the statistics of the player Cristiano Ronaldo for the national team of Portugal in all the world cups in espn.com.
- Change: **same content**
- Deliverable: `page`
- Evidence: Page deliverable on the v1 URL; reference is the World Cup table on that page (D72).

<details><summary>v1 key -> v2 key</summary>

v1:

```json
{
 "check_url_contains": "/soccer/player/stats/_/id/22774/team/482/type/fifa.world",
 "end_markers": {
  "host": "espn.com",
  "url_contains": "/soccer/player/stats/_/id/22774/team/482/type/fifa.world",
  "deny": [
   "/signin",
   "/login",
   "/sorry/"
  ],
  "answer_in_text": "FIFA World Cup"
 },
 "full_answer": "FIFA World Cup",
 "answer_parts": [
  "FIFA World Cup"
 ],
 "url_answer_ok": true
}
```

v2:

```json
{
 "deliverable": "page",
 "host": "espn.com",
 "pages": [
  {
   "path": "/soccer/player/stats/_/id/22774/team/482/type/fifa.world"
  }
 ],
 "reference": "Season | Team | STRT | FC | FA | YC | RC | G | A | SHOT | SOG | OFF\n2026 FIFA World Cup | POR | 5 | 2 | 5 | 0 | 0 | 3 | 0 | 18 | 9 | 6\n2022 FIFA World Cup | POR | 3 | 2 | 5 | 0 | 0 | 1 | 0 | 11 | 3 | 0\n2018 FIFA World Cup | POR | 4 | 2 | 14 | 2 | 0 | 4 | 0 | 21 | 8 | 1\n2014 FIFA World Cup | POR | 3 | 2 | 10 | 0 | 0 | 1 | 1 | 23 | 14 | 3\n2010 FIFA World Cup | POR | 4 | 1 | 8 | 1 | 0 | 1 | 1 | 22 | 7 | 3\n2006 FIFA World Cup | POR | 6 | 7 | 23 | 1 | 0 | 1 | 0 | 29 | 13 | 0",
 "basis": "v1 URL key; reference is the World Cup table the task asks for."
}
```

</details>

## extdev_nav_nets_schedule

- Task: Find the team schedule of the Brooklyn Nets on espn
- Change: **same content**
- Deliverable: `page`
- Evidence: v1 URL.

<details><summary>v1 key -> v2 key</summary>

v1:

```json
{
 "check_url_contains": "/nba/team/schedule/_/name/bkn/brooklyn-nets",
 "end_markers": {
  "host": "espn.com",
  "url_contains": "/nba/team/schedule/_/name/bkn/brooklyn-nets",
  "deny": [
   "/signin",
   "/login",
   "/sorry/"
  ],
  "answer_in_text": "Brooklyn Nets Schedule"
 },
 "url_answer_ok": true
}
```

v2:

```json
{
 "deliverable": "page",
 "host": "espn.com",
 "pages": [
  {
   "path": "/nba/team/schedule/_/name/bkn/brooklyn-nets"
  }
 ],
 "reference": "https://www.espn.com/nba/team/schedule/_/name/bkn/brooklyn-nets",
 "basis": "v1 URL key."
}
```

</details>

## extdev_nav_fiestatexas_events

- Task: Show me all the events at any six flags park in Texas in sixflags
- Change: **Also accepts Six Flags Over Texas events.**
- Deliverable: `page`
- Evidence: Task text: "all the events at any six flags park in Texas".
- Evidence: https://www.sixflags.com/overtexas: page heading "Six Flags Over Texas" and "Hurricane Harbor Arlington".

<details><summary>v1 key -> v2 key</summary>

v1:

```json
{
 "check_url_contains": "/fiestatexas/events",
 "end_markers": {
  "host": "sixflags.com",
  "url_contains": "/fiestatexas/events",
  "deny": [
   "/signin",
   "/login",
   "/sorry/"
  ],
  "answer_in_text": "Our Events"
 },
 "full_answer": "Our Events",
 "answer_parts": [
  "Our Events"
 ]
}
```

v2:

```json
{
 "deliverable": "page",
 "host": "sixflags.com",
 "pages": [
  {
   "path": "/fiestatexas/events"
  },
  {
   "path": "/overtexas/events"
  }
 ],
 "reference": "Holiday in the Park; Countdown To New Year's; New Year's 360 Fireworks Celebration; Mardi Gras Festival; Viva La Fiesta; Star-Spangled Nights Fireworks presented by M&M'S; Oktoberfest; Fright Fest; Tricks and Treats - each with its dates (Select Dates, November 21 - January 4, 2027; December 26-30, 2026; December 31, 2026; February 6 - March 15, 2027; April 3 - 25, 2027; July 3 - 4, 2027; Sept. 4 - Oct. 31, 2027; Sept. 10 - Oct. 31, 2027; Sept 11 - Oct. 31, 2027)",
 "basis": "task says 'any six flags park in Texas'; Six Flags Over Texas is one (overtexas slug)."
}
```

</details>

## extdev_nav_spothero_marketing

- Task: Find career openings in the marketing department in spothero
- Change: **Careers page plus 'Marketing Analyst' in the answer, instead of the single role page.**
- Deliverable: `both`
- Evidence: D81 (spothero.com/careers): "Engineering ... Marketing Marketing Analyst Product Product Manager, Acquisitions".

<details><summary>v1 key -> v2 key</summary>

v1:

```json
{
 "check_url_contains": "/careers/8069541",
 "end_markers": {
  "host": "spothero.com",
  "url_contains": "/careers/8069541",
  "deny": [
   "/signin",
   "/login",
   "/sorry/"
  ],
  "answer_in_text": "Marketing Analyst"
 },
 "full_answer": "Marketing Analyst",
 "answer_parts": [
  "Marketing Analyst"
 ],
 "url_answer_ok": true
}
```

v2:

```json
{
 "deliverable": "both",
 "host": "spothero.com",
 "pages": [
  {
   "path": "/careers"
  }
 ],
 "facts": [
  [
   "Marketing Analyst"
  ]
 ],
 "reference": "Marketing Analyst (Chicago, IL)",
 "basis": "careers page lists 'Marketing Marketing Analyst' (D81); the role page is one click deeper."
}
```

</details>

## extdev_filter_amazon_puppy_food

- Task: Browse dog food for puppies that is rated at least 4 stars and sort the results by price from low to high in amazon
- Change: **Search words may be any phrase with 'puppy'/'puppies'; rh must include p_72:2661618011 among other filters.**
- Deliverable: `page`
- Evidence: D85 (amazon.com/s?k=puppy+dog+food&rh=p_72%3A2661618011&s=price-asc-rank...): "1-48 of over 1,000 results for \"puppy dog food\" Sort by: ... Price: Low to High".
- Evidence: U22 URL: "rh=p_n_g-101015646925111%3A204428486011%2Cp_72%3A2661618011" (Amazon joins filters with commas).

<details><summary>v1 key -> v2 key</summary>

v1:

```json
{
 "check_url_contains": "/s?k=dog+food+for+puppies&rh=p_72%3A2661618011&s=price-asc-rank",
 "end_markers": {
  "host": "amazon.com",
  "url_contains": "/s?k=dog+food+for+puppies&rh=p_72%3A2661618011&s=price-asc-rank",
  "deny": [
   "/signin",
   "/login",
   "/sorry/"
  ],
  "answer_in_text": "Sort by:Price: Low to High"
 },
 "full_answer": "Sort by:Price: Low to High",
 "answer_parts": [
  "Sort by:Price: Low to High"
 ]
}
```

v2:

```json
{
 "deliverable": "page",
 "host": "amazon.com",
 "pages": [
  {
   "path": "/s",
   "path_mode": "prefix",
   "query": {
    "s": {
     "any": [
      "price-asc-rank"
     ]
    },
    "rh": {
     "has": "p_72:2661618011"
    },
    "k": {
     "contains": [
      "puppy",
      "puppies"
     ]
    }
   }
  }
 ],
 "reference": "Puppy dog food, 4 Stars & Up, sorted by Price: Low to High.",
 "basis": "v1 query parameters; search words 'puppy dog food' are the task's words."
}
```

</details>

## extdev_nav_eventbrite_planning

- Task: Browse the page with event planning tips on eventbrite
- Change: **same content**
- Deliverable: `page`
- Evidence: v1 URL.

<details><summary>v1 key -> v2 key</summary>

v1:

```json
{
 "check_url_contains": "/blog/category/event-planning/",
 "end_markers": {
  "host": "eventbrite.com",
  "url_contains": "/blog/category/event-planning/",
  "deny": [
   "/signin",
   "/login",
   "/sorry/"
  ],
  "answer_in_text": "EVENT PLANNING"
 },
 "url_answer_ok": true
}
```

v2:

```json
{
 "deliverable": "page",
 "host": "eventbrite.com",
 "pages": [
  {
   "path": "/blog/category/event-planning"
  }
 ],
 "reference": "https://www.eventbrite.com/blog/category/event-planning/",
 "basis": "v1 URL key."
}
```

</details>

## extdev_filter_sam_harris_paperback

- Task: Find a book by Sam Harris that has a rating of at least 4 stars and is available in paperback format in amazon
- Change: **Answer task: Free Will or The End of Faith; the filter URL is no longer required.**
- Deliverable: `answer`
- Evidence: U24 (amazon.com/s?k=Sam+Harris+paperback): "The End of Faith: Religion, Terror, and the Future of Reason by Sam Harris | Sep 17, 2005 4.5 4.5 out of 5 stars (3.3K) Paperback".

<details><summary>v1 key -> v2 key</summary>

v1:

```json
{
 "check_url_contains": "/s?k=Sam+harris&i=stripbooks&rh=n%3A283155%2Cp_72%3A1250221011%2Cp_n_feature_browse-bin%3A2656022011",
 "end_markers": {
  "host": "amazon.com",
  "url_contains": "/s?k=Sam+harris&i=stripbooks&rh=n%3A283155%2Cp_72%3A1250221011%2Cp_n_feature_browse-bin%3A2656022011",
  "deny": [
   "/signin",
   "/login",
   "/sorry/"
  ],
  "answer_in_text": "Free Will [Deckle Edge]"
 },
 "full_answer": "Free Will [Deckle Edge]; Paperback; by Sam Harris; 4.3 out of 5 stars",
 "answer_parts": [
  "Free Will [Deckle Edge]",
  "Paperback",
  "by Sam Harris",
  "4.3 out of 5 stars"
 ]
}
```

v2:

```json
{
 "deliverable": "answer",
 "host": "amazon.com",
 "facts": [
  [
   "Free Will",
   "The End of Faith"
  ]
 ],
 "reference": "Free Will [Deckle Edge] by Sam Harris, Paperback, 4.3 out of 5 stars",
 "basis": "v1 book; The End of Faith '4.5 out of 5 stars ... Paperback' on the saved results page (U24)."
}
```

</details>

## extdev_nav_steam_daily_players

- Task: Show most played games based on daily players in store.steampowered
- Change: **v1 marker moved from the answer to the page text.**
- Deliverable: `page`
- Evidence: U25 (store.steampowered.com/charts/mostplayed): "MOST PLAYED Top 100 played games By Daily Players RANK PRICE CHANGE PEAK TODAY".

<details><summary>v1 key -> v2 key</summary>

v1:

```json
{
 "check_url_contains": "/charts/mostplayed",
 "end_markers": {
  "host": "store.steampowered.com",
  "url_contains": "/charts/mostplayed",
  "deny": [
   "/signin",
   "/login",
   "/sorry/"
  ],
  "answer_in_text": "By Daily Players"
 },
 "full_answer": "By Daily Players",
 "answer_parts": [
  "By Daily Players"
 ]
}
```

v2:

```json
{
 "deliverable": "page",
 "host": "store.steampowered.com",
 "pages": [
  {
   "path": "/charts/mostplayed",
   "text": [
    "By Daily Players"
   ]
  }
 ],
 "reference": "Most Played: Top 100 played games By Daily Players - 1 Counter-Strike 2, 2 Dota 2, 3 PUBG",
 "basis": "v1 URL and v1 marker, moved from the answer to the page text."
}
```

</details>

## extdev_nav_commuter_benefits

- Task: Find guide for paying with commuter benefits in spothero
- Change: **same content**
- Deliverable: `page`
- Evidence: v1 URL.

<details><summary>v1 key -> v2 key</summary>

v1:

```json
{
 "check_url_contains": "/solutions/commuter-benefits",
 "end_markers": {
  "host": "spothero.com",
  "url_contains": "/solutions/commuter-benefits",
  "deny": [
   "/signin",
   "/login",
   "/sorry/"
  ],
  "answer_in_text": "How to Use Your Commuter Benefits Card"
 },
 "url_answer_ok": true
}
```

v2:

```json
{
 "deliverable": "page",
 "host": "spothero.com",
 "pages": [
  {
   "path": "/solutions/commuter-benefits"
  }
 ],
 "reference": "https://spothero.com/solutions/commuter-benefits",
 "basis": "v1 URL key."
}
```

</details>

## extdev_value_dream_blast_revenue

- Task: Which game contributed significantly to Rovio's revenue in both 2019 and 2022?
- Change: **Accepts 'Dream Blast' (v1 'Angry Birds Dream Blast').**
- Deliverable: `answer`
- Evidence: Same game; v1 marker.

<details><summary>v1 key -> v2 key</summary>

v1:

```json
{
 "check_url_contains": "/articles/rovios-q3-2022-interim-report-published/",
 "end_markers": {
  "host": "rovio.com",
  "url_contains": "/articles/rovios-q3-2022-interim-report-published/",
  "deny": [
   "/signin",
   "/login",
   "/sorry/"
  ],
  "answer_in_text": "Angry Birds Dream Blast"
 },
 "full_answer": "Angry Birds Dream Blast"
}
```

v2:

```json
{
 "deliverable": "answer",
 "host": "rovio.com",
 "facts": [
  [
   "Dream Blast"
  ]
 ],
 "reference": "Angry Birds Dream Blast",
 "basis": "v1 marker."
}
```

</details>

## extdev_value_pirate_treasures

- Task: Which characters are involved in the grand opening of Battle Brewmasters Artisanal Potion Shop in Kingdom Rush 5: Alliance, and what types of hidden treasures can be found in the upcoming Pirate Kings Campaign?
- Change: **Characters: either the named characters at the opening or the peoples; treasures split into their items.**
- Deliverable: `answer`
- Evidence: https://www.ironhidegames.com/News/Details/372: "Obelax: Thanks, Sheepy! With King Denas here, we've got a full house! ... customers are flocking in from all corners of the Kingdom: Linireans, elves, dwarves"; "Halfdan the Blunt: It's going quite well!".
- Evidence: WebWalkerQA source answer: "Characters like Linireans, elves, and dwarves participate in the grand opening".
- Evidence: U28 (News/Details/370): "Winners can pick any of Ironhide Games, heroes, towers, or DLCs."

<details><summary>v1 key -> v2 key</summary>

v1:

```json
{
 "check_url_contains": "/News/Details/370",
 "end_markers": {
  "host": "ironhidegames.com",
  "url_contains": "/News/Details/370",
  "deny": [
   "/signin",
   "/login",
   "/sorry/"
  ],
  "answer_in_text": "Winners can pick any of Ironhide Games, heroes, towers, or DLCs."
 },
 "full_answer": "Winners can pick any of Ironhide Games, heroes, towers, or DLCs.; Linireans, elves, dwarves; King Denas; Obelax; Halfdan",
 "answer_parts": [
  "Winners can pick any of Ironhide Games, heroes, towers, or DLCs.",
  "Linireans, elves, dwarves",
  "King Denas",
  "Obelax",
  "Halfdan"
 ]
}
```

v2:

```json
{
 "deliverable": "answer",
 "host": "ironhidegames.com",
 "facts": [
  {
   "any": [
    [
     "King Denas",
     "Obelax",
     "Halfdan"
    ],
    [
     "Linireans",
     "elves",
     "dwarves"
    ]
   ]
  },
  [
   "Ironhide Games",
   "games"
  ],
  [
   "heroes"
  ],
  [
   "towers"
  ],
  [
   "DLCs",
   "DLC"
  ]
 ],
 "reference": "Linireans, elves, dwarves (with King Denas, Obelax and Halfdan the Blunt); Winners can pick any of Ironhide Games, heroes, towers, or DLCs.",
 "basis": "article 372 names King Denas, Obelax, Halfdan at the opening and Linireans/elves/dwarves as customers (HTTP GET); treasures from article 370 (U28)."
}
```

</details>

## extdev_value_inclusive_strategy_role

- Task: Which position is identified as a key role in promoting inclusion strategy according to Rovio's guide for inclusive game design and 2023 Sustainability Report?
- Change: **Role only (the name is optional).**
- Deliverable: `answer`
- Evidence: v1 marker "Chief Sustainability Officer, Heini Kaihu"; the question asks for the position.

<details><summary>v1 key -> v2 key</summary>

v1:

```json
{
 "check_url_contains": "/articles/rovio-sustainability-report-2023-message-from-chief-sustainability-officer/",
 "end_markers": {
  "host": "rovio.com",
  "url_contains": "/articles/rovio-sustainability-report-2023-message-from-chief-sustainability-officer/",
  "deny": [
   "/signin",
   "/login",
   "/sorry/"
  ],
  "answer_in_text": "Chief Sustainability Officer, Heini Kaihu"
 },
 "full_answer": "Chief Sustainability Officer, Heini Kaihu"
}
```

v2:

```json
{
 "deliverable": "answer",
 "host": "rovio.com",
 "facts": [
  [
   "Chief Sustainability Officer"
  ]
 ],
 "reference": "Chief Sustainability Officer, Heini Kaihu",
 "basis": "v1 marker, role only."
}
```

</details>

## extdev_value_ironhide_historical_games

- Task: What new games were released by Ironhide Game Studio on April 10, 2023, and November 20, 2014?
- Change: **Game names instead of full headlines.**
- Deliverable: `answer`
- Evidence: U30 (News/Details/295): "IRON MARINES GOES FREE ON GOOGLE PLAY!"; v1 headline "KINGDOM RUSH ORIGINS COMING OUT NOVEMBER 20!".

<details><summary>v1 key -> v2 key</summary>

v1:

```json
{
 "check_url_contains": "/News/Details/98",
 "end_markers": {
  "host": "ironhidegames.com",
  "url_contains": "/News/Details/98",
  "deny": [
   "/signin",
   "/login",
   "/sorry/"
  ],
  "answer_in_text": "KINGDOM RUSH ORIGINS COMING OUT NOVEMBER 20!"
 },
 "full_answer": "KINGDOM RUSH ORIGINS COMING OUT NOVEMBER 20!; IRON MARINES GOES FREE ON GOOGLE PLAY!",
 "answer_parts": [
  "KINGDOM RUSH ORIGINS COMING OUT NOVEMBER 20!",
  "IRON MARINES GOES FREE ON GOOGLE PLAY!"
 ]
}
```

v2:

```json
{
 "deliverable": "answer",
 "host": "ironhidegames.com",
 "facts": [
  [
   "Kingdom Rush Origins"
  ],
  [
   "Iron Marines"
  ]
 ],
 "reference": "Iron Marines (April 10, 2023); Kingdom Rush Origins (November 20, 2014)",
 "basis": "v1 headlines reduced to the game names."
}
```

</details>

## extdev_value_ironhide_arcade_gdc

- Task: Which game developed by Ironhide was awarded a round trip to GDC as a prize, and what is the latest game they announced for Apple Arcade in 2023?
- Change: **Game names instead of the headline; the question's own words 'round trip to GDC' are no longer required in the answer.**
- Deliverable: `answer`
- Evidence: WebWalkerQA source answer (candidates_extdev.jsonl, main:562): "Kingdom Rush and Junkworld".
- Evidence: https://www.ironhidegames.com/News/Details/307: "Junkworld is Coming to Apple Arcade on September 22nd!".

<details><summary>v1 key -> v2 key</summary>

v1:

```json
{
 "check_url_contains": "/News/Details/307",
 "end_markers": {
  "host": "ironhidegames.com",
  "url_contains": "/News/Details/307",
  "deny": [
   "/signin",
   "/login",
   "/sorry/"
  ],
  "answer_in_text": "JUNKWORLD IS COMING TO APPLE ARCADE ON SEPTEMBER 22ND!"
 },
 "full_answer": "JUNKWORLD IS COMING TO APPLE ARCADE ON SEPTEMBER 22ND!; Kingdom Rush; round trip to GDC",
 "answer_parts": [
  "JUNKWORLD IS COMING TO APPLE ARCADE ON SEPTEMBER 22ND!",
  "Kingdom Rush",
  "round trip to GDC"
 ]
}
```

v2:

```json
{
 "deliverable": "answer",
 "host": "ironhidegames.com",
 "facts": [
  [
   "Junkworld"
  ],
  [
   "Kingdom Rush"
  ]
 ],
 "reference": "Kingdom Rush and Junkworld",
 "basis": "WebWalkerQA source answer 'Kingdom Rush and Junkworld'; v1 headline reduced to the game name."
}
```

</details>

## extdev_value_cambridge_euphoria

- Task: Look up the British pronunciation of the word "euphoria" and find an example sentence using that word on the Cambridge Dictionary.
- Change: **same content**
- Deliverable: `answer`
- Evidence: v1 parts.

<details><summary>v1 key -> v2 key</summary>

v1:

```json
{
 "check_url_contains": "/dictionary/english/euphoria",
 "end_markers": {
  "host": "dictionary.cambridge.org",
  "url_contains": "/dictionary/english/euphoria",
  "deny": [
   "/signin",
   "/login",
   "/sorry/"
  ],
  "answer_in_text": "They were in a state of euphoria for days after they won the prize."
 },
 "full_answer": "They were in a state of euphoria for days after they won the prize.; /juːˈfɔː.ri.ə/",
 "answer_parts": [
  "They were in a state of euphoria for days after they won the prize.",
  "/juːˈfɔː.ri.ə/"
 ]
}
```

v2:

```json
{
 "deliverable": "answer",
 "host": "dictionary.cambridge.org",
 "facts": [
  [
   "/juːˈfɔː.ri.ə/"
  ],
  [
   "They were in a state of euphoria for days after they won the prize."
  ]
 ],
 "reference": "/juːˈfɔː.ri.ə/; They were in a state of euphoria for days after they won the prize.",
 "basis": "v1 parts."
}
```

</details>

## extdev_value_hf_pytorch_tensorflow

- Task: Identify the steps to convert a PyTorch model to TensorFlow using the Hugging Face Transformers library as described in their documentation.
- Change: **same content**
- Deliverable: `answer`
- Evidence: v1 parts.

<details><summary>v1 key -> v2 key</summary>

v1:

```json
{
 "check_url_contains": "/blog/tf-serving",
 "end_markers": {
  "host": "huggingface.co",
  "url_contains": "/blog/tf-serving",
  "deny": [
   "/signin",
   "/login",
   "/sorry/"
  ],
  "answer_in_text": "from_pt=True"
 },
 "full_answer": "from_pt=True; TFAutoModel.from_pretrained(; AutoConfig.from_pretrained(\"./pt_model/config.json\"); save_pretrained",
 "answer_parts": [
  "from_pt=True",
  "TFAutoModel.from_pretrained(",
  "AutoConfig.from_pretrained(\"./pt_model/config.json\")",
  "save_pretrained"
 ]
}
```

v2:

```json
{
 "deliverable": "answer",
 "host": "huggingface.co",
 "facts": [
  [
   "from_pt=True"
  ],
  [
   "TFAutoModel.from_pretrained("
  ],
  [
   "AutoConfig.from_pretrained(\"./pt_model/config.json\")"
  ],
  [
   "save_pretrained"
  ]
 ],
 "reference": "from_pt=True; TFAutoModel.from_pretrained(; AutoConfig.from_pretrained(\"./pt_model/config.json\"); save_pretrained",
 "basis": "v1 parts unchanged."
}
```

</details>

## extdev_value_cambridge_gestalt

- Task: Look up the meaning, pronunciation, and an example sentence of the word "gestalt" using the Cambridge Dictionary.
- Change: **Meaning part without the trailing ':'; accepts the US IPA too.**
- Deliverable: `answer`
- Evidence: S2: "UK /ɡəˈʃtælt/ US /ɡəˈʃtɑːlt/ ... has qualities that are more than the total of all its parts: This new biography is the first to consider fully the writer's gestalt."

<details><summary>v1 key -> v2 key</summary>

v1:

```json
{
 "check_url_contains": "/dictionary/english/gestalt",
 "end_markers": {
  "host": "dictionary.cambridge.org",
  "url_contains": "/dictionary/english/gestalt",
  "deny": [
   "/signin",
   "/login",
   "/sorry/"
  ],
  "answer_in_text": "This new biography is the first to consider fully the writer's gestalt."
 },
 "full_answer": "This new biography is the first to consider fully the writer's gestalt.; /ɡəˈʃtælt/; something such as a structure or experience that, when considered as a whole, has qualities that are more than the total of all its parts:",
 "answer_parts": [
  "This new biography is the first to consider fully the writer's gestalt.",
  "/ɡəˈʃtælt/",
  "something such as a structure or experience that, when considered as a whole, has qualities that are more than the total of all its parts:"
 ]
}
```

v2:

```json
{
 "deliverable": "answer",
 "host": "dictionary.cambridge.org",
 "facts": [
  [
   "more than the total of all its parts"
  ],
  [
   "/ɡəˈʃtælt/",
   "/ɡəˈʃtɑːlt/"
  ],
  [
   "This new biography is the first to consider fully the writer's gestalt."
  ]
 ],
 "reference": "something such as a structure or experience that, when considered as a whole, has qualities that are more than the total of all its parts; /ɡəˈʃtælt/; This new biography is the first to consider fully the writer's gestalt.",
 "basis": "v1 parts without the trailing colon; US IPA from the same entry (S2)."
}
```

</details>

## extdev_value_cambridge_innovate

- Task: Look for the British English pronunciation of the word "innovate" and write down the International Phonetic Alphabet (IPA) notation, then find one example sentence provided in the Cambridge Dictionary that uses this word.
- Change: **same content**
- Deliverable: `answer`
- Evidence: v1 parts.

<details><summary>v1 key -> v2 key</summary>

v1:

```json
{
 "check_url_contains": "/dictionary/english/innovate",
 "end_markers": {
  "host": "dictionary.cambridge.org",
  "url_contains": "/dictionary/english/innovate",
  "deny": [
   "/signin",
   "/login",
   "/sorry/"
  ],
  "answer_in_text": "The fashion industry is always desperate to innovate."
 },
 "full_answer": "The fashion industry is always desperate to innovate.; /ˈɪn.ə.veɪt/",
 "answer_parts": [
  "The fashion industry is always desperate to innovate.",
  "/ˈɪn.ə.veɪt/"
 ]
}
```

v2:

```json
{
 "deliverable": "answer",
 "host": "dictionary.cambridge.org",
 "facts": [
  [
   "/ˈɪn.ə.veɪt/"
  ],
  [
   "The fashion industry is always desperate to innovate."
  ]
 ],
 "reference": "/ˈɪn.ə.veɪt/; The fashion industry is always desperate to innovate.",
 "basis": "v1 parts."
}
```

</details>

## extdev_filter_green_xbox_controller

- Task: Search an Xbox Wireless controller with green color and rated above 4 stars.
- Change: **same content**
- Deliverable: `both`
- Evidence: v1 rating filter and v1 marker.

<details><summary>v1 key -> v2 key</summary>

v1:

```json
{
 "check_url_contains": "p_72%3A1248885011",
 "end_markers": {
  "host": "amazon.com",
  "url_contains": "p_72%3A1248885011",
  "deny": [
   "/signin",
   "/login",
   "/sorry/"
  ],
  "answer_in_text": "XBOX Wireless Gaming Controller | Velocity Green",
  "path_suffix": "/s"
 },
 "full_answer": "XBOX Wireless Gaming Controller | Velocity Green",
 "answer_parts": [
  "XBOX Wireless Gaming Controller | Velocity Green"
 ]
}
```

v2:

```json
{
 "deliverable": "both",
 "host": "amazon.com",
 "pages": [
  {
   "path": "/s",
   "path_mode": "prefix",
   "query": {
    "rh": {
     "has": "p_72:1248885011"
    }
   }
  }
 ],
 "facts": [
  [
   "XBOX Wireless Gaming Controller | Velocity Green"
  ]
 ],
 "reference": "XBOX Wireless Gaming Controller | Velocity Green",
 "basis": "v1 rating filter and v1 marker unchanged."
}
```

</details>

## extdev_value_booking_parent

- Task: Browse Booking's homepage to find out which company it belongs to.
- Change: **Accepts 'Booking Holdings' without 'Inc.'.**
- Deliverable: `answer`
- Evidence: v1 marker "Booking Holdings Inc.".

<details><summary>v1 key -> v2 key</summary>

v1:

```json
{
 "check_url_contains": "/content/about.html",
 "end_markers": {
  "host": "booking.com",
  "url_contains": "/content/about.html",
  "deny": [
   "/signin",
   "/login",
   "/sorry/"
  ],
  "answer_in_text": "Booking Holdings Inc."
 }
}
```

v2:

```json
{
 "deliverable": "answer",
 "host": "booking.com",
 "facts": [
  [
   "Booking Holdings"
  ]
 ],
 "reference": "Booking Holdings Inc.",
 "basis": "v1 marker."
}
```

</details>

## extdev_filter_tiny_home_dates

- Task: Search for a tiny home anywhere for an adult and 2 pets to stay in from april 10 to april 12
- Change: **Any location (task: 'anywhere'); also accepts a tiny-home listing page with the same guests and dates.**
- Deliverable: `page`
- Evidence: U38 (airbnb.com/rooms/52007336?adults=1&check_in=2027-04-10&check_out=2027-04-12&pets=2...): "Forest Tiny House | Fire Pit | Olympic Peninsula Tiny home in Port Ludlow, Washington".

<details><summary>v1 key -> v2 key</summary>

v1:

```json
{
 "check_url_contains": "/s/United-States/homes?property_type_id%5B%5D=67&adults=1&pets=2&checkin=2027-04-10&checkout=2027-04-12",
 "end_markers": {
  "host": "airbnb.com",
  "url_contains": "/s/United-States/homes?property_type_id%5B%5D=67&adults=1&pets=2&checkin=2027-04-10&checkout=2027-04-12",
  "deny": [
   "/signin",
   "/login",
   "/sorry/"
  ],
  "answer_in_text": "Tiny home in"
 },
 "full_answer": "Tiny home in",
 "answer_parts": [
  "Tiny home in"
 ]
}
```

v2:

```json
{
 "deliverable": "page",
 "host": "airbnb.com",
 "pages": [
  {
   "path": "/homes",
   "query": {
    "property_type_id[]": {
     "any": [
      "67"
     ]
    },
    "adults": {
     "any": [
      "1"
     ]
    },
    "pets": {
     "any": [
      "2"
     ]
    },
    "checkin": {
     "any": [
      "2027-04-10"
     ]
    },
    "checkout": {
     "any": [
      "2027-04-12"
     ]
    }
   }
  },
  {
   "path": "/rooms/",
   "path_mode": "prefix",
   "text": [
    "Tiny home in"
   ],
   "query": {
    "adults": {
     "any": [
      "1"
     ]
    },
    "pets": {
     "any": [
      "2"
     ]
    },
    "check_in": {
     "any": [
      "2027-04-10"
     ]
    },
    "check_out": {
     "any": [
      "2027-04-12"
     ]
    }
   }
  }
 ],
 "reference": "Forest Tiny House | Fire Pit | Olympic Peninsula",
 "basis": "v1 search parameters; a tiny-home listing page with the same guests and dates (U38)."
}
```

</details>

## extdev_filter_sf_exercise_dates

- Task: Find exercise events taking place in San Francisco between July 10-31.
- Change: **same content**
- Deliverable: `page`
- Evidence: v1 URL parameters.

<details><summary>v1 key -> v2 key</summary>

v1:

```json
{
 "check_url_contains": "/d/ca--san-francisco/exercise/?start_date=2027-07-10&end_date=2027-07-31",
 "end_markers": {
  "host": "eventbrite.com",
  "url_contains": "/d/ca--san-francisco/exercise/?start_date=2027-07-10&end_date=2027-07-31",
  "deny": [
   "/signin",
   "/login",
   "/sorry/"
  ],
  "answer_in_text": "Exercise Events and Things to do in San Francisco, CA"
 },
 "full_answer": "Exercise Events and Things to do in San Francisco, CA",
 "answer_parts": [
  "Exercise Events and Things to do in San Francisco, CA"
 ]
}
```

v2:

```json
{
 "deliverable": "page",
 "host": "eventbrite.com",
 "pages": [
  {
   "path": "/d/ca--san-francisco/exercise/",
   "query": {
    "start_date": {
     "any": [
      "2027-07-10"
     ]
    },
    "end_date": {
     "any": [
      "2027-07-31"
     ]
    }
   }
  }
 ],
 "reference": "Somatic Breathwork and Deep relaxation: Creating Health and Healing!; Monday Yoga; Bachata Lab; Salsa Dance Classes and Salsa and Bachata Dancing - SalsaCrazy Mondays; Bachata Kizomba Sunday; Queer Bowling MBC; Breathing Ecstasy; Team Building - Archery Class in San Francisco",
 "basis": "v1 URL key; reference from the saved results page (U39)."
}
```

</details>

## extdev_filter_castles_europe_week

- Task: Search for Castles in Europe for a week next month and price below $1000 per night.
- Change: **Accepts the kg_and_tags[] alias, any price_max <= 1000, and a fixed 7-night December 2026 stay.**
- Deliverable: `page`
- Evidence: U40 URL: "kg_and_tags%5B%5D=Tag%3A8047 ... checkin=2026-12-01&checkout=2026-12-08 ... selected_filter_order%5B%5D=price_max%3A999 ... price_max=999".
- Evidence: Task text: "price below $1000 per night", "for a week next month" (runs were on 17 Nov 2026; v1 key already fixed December).

<details><summary>v1 key -> v2 key</summary>

v1:

```json
{
 "check_url_contains": "/s/Europe/homes?category_tag=Tag%3A8047&price_max=1000&flexible_trip_lengths%5B%5D=one_week&date_picker_type=flexible_dates&flexible_trip_dates%5B%5D=december",
 "end_markers": {
  "host": "airbnb.com",
  "url_contains": "/s/Europe/homes?category_tag=Tag%3A8047&price_max=1000&flexible_trip_lengths%5B%5D=one_week&date_picker_type=flexible_dates&flexible_trip_dates%5B%5D=december",
  "deny": [
   "/signin",
   "/login",
   "/sorry/"
  ],
  "answer_in_text": "Castle in"
 },
 "full_answer": "Castle in",
 "answer_parts": [
  "Castle in"
 ]
}
```

v2:

```json
{
 "deliverable": "page",
 "host": "airbnb.com",
 "pages": [
  {
   "path": "/s/Europe/homes",
   "query": {
    "category_tag": {
     "any": [
      "Tag:8047"
     ]
    },
    "price_max": {
     "max": 1000
    },
    "flexible_trip_lengths[]": {
     "any": [
      "one_week"
     ]
    },
    "flexible_trip_dates[]": {
     "any": [
      "december"
     ]
    }
   }
  },
  {
   "path": "/s/Europe/homes",
   "query": {
    "kg_and_tags[]": {
     "any": [
      "Tag:8047"
     ]
    },
    "price_max": {
     "max": 1000
    },
    "flexible_trip_lengths[]": {
     "any": [
      "one_week"
     ]
    },
    "flexible_trip_dates[]": {
     "any": [
      "december"
     ]
    }
   }
  },
  {
   "path": "/s/Europe/homes",
   "query": {
    "kg_and_tags[]": {
     "any": [
      "Tag:8047"
     ]
    },
    "price_max": {
     "max": 1000
    },
    "checkin": {
     "prefix": "2026-12-"
    }
   },
   "stay_nights": 7
  },
  {
   "path": "/s/Europe/homes",
   "query": {
    "category_tag": {
     "any": [
      "Tag:8047"
     ]
    },
    "price_max": {
     "max": 1000
    },
    "checkin": {
     "prefix": "2026-12-"
    }
   },
   "stay_nights": 7
  }
 ],
 "reference": "Castles in Europe, one week in December 2026, max $1000 per night.",
 "basis": "v1 tag/price/week/December; a fixed 7-night December stay is the same request."
}
```

</details>
