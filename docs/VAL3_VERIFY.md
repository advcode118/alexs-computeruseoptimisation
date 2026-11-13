# val3 public-page verification

val3 is a 40-task validation set used as an aggregate-only gate. This file gives totals and sites only: no answers, end pages or reproducer details.

These are page and grader checks, not an agent benchmark. No LLM API calls and no bench probes were run. The tasks were written without reading agent results, `bench/runs/`, `docs/results/` or any heldout3 file.

Mix: 10 nav, 10 value, 6 search (on the site's own search box), 6 form (public practice and demo sites), 4 title, 4 spa.

Method: `python -m bench.verify_val3` uses local headless Chromium. Evidence comes from the runner's `collect_page_evidence`. Each task must reach its end state and pass both `evidence_verdict` and the probe's `grade_observation`. Two negative controls must fail: the start page (or the app state before the action) claimed with the expected answer, and, on answer tasks, a wrong value read off the finished page.

## Runs (13 Nov 2026, UTC)

| Run | Started | Passed |
| --- | --- | --- |
| 1 | 21:30 | 40/40 |
| 2 | 21:34 | 40/40 |

Tasks were replaced before these runs for these reasons:
- A docs site whose evidence text did not contain the page.
- A login demo whose end path was a prefix of its start URL.

Sites dropped while scouting:
- Bot walls or 403s: unesco, un.org, rhymezone, wordreference, raspberrypi, poetryfoundation, senate.
- Bad TLS certificate: uitestingplayground.
- Form behind a captcha: vinothqaacademy.
- Search box not reliably present in headless mode: openlibrary.

## Sites (27 registrable domains, at most 3 tasks each)

nmap.org, opensource.org, periodni.com, perl.org (perldoc), prettier.io, psycopg.org, pypa.io (pip), qaplayground.dev, rapidtables.com, ruby-lang.org, sass-lang.com, seleniumbase.io, stanford.edu (plato), sqlalchemy.org, sweetshop.netlify.app, sympy.org, tcpdump.org, timeanddate.com, toml.io, trytestingthis.netlify.app, tutorialsninja.com, vimhelp.org, vite.dev, webelements.com, yaml.org, ziglang.org, zod.dev.
