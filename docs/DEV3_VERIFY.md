# dev3 public-page verification

dev3 is a forty-task public tune set (not scored). Tasks are in `bench/tasks_dev3.py`; the split is `--split dev3`.

`python -m bench.verify_dev3` drives local headless Chromium from each start page to the end state with a short Playwright script (following links, using each site's own search box, filling and submitting the demo forms, clicking the tab). It then grades the live page with the probe's own `grade_observation` and `evidence_verdict`. No model or API calls.

Negative checks per task: the expected answer claimed on the start page must fail; for every value, title, form and spa task, a plausible wrong value claimed on the end page must fail. For the three JavaScript-rendered pages (DevDocs, Elm packages, LetCode), the end page loaded with JavaScript off must not contain the answer and must fail.

Mix: 10 nav, 10 value, 6 search, 6 form, 4 title, 4 spa.

## Runs

| Run | Started | Result |
| --- | --- | --- |
| 1 | 2026-11-13 21:35 UTC | 40/40 passed |
| 2 | 2026-11-13 21:38 UTC | 40/40 passed |

Replaced before these two runs: a Lua version-history task (lua.org dropped connections twice), an Angular versions task (`material.angular.dev` is already used, so `angular.dev` is out), a Lib.rs search task (search page timed out), and an Electron release task (the page is server-rendered, so not spa; and not reachable by links). Dropped while scouting: dblp (Anubis), etymonline and britannica (Cloudflare), LMFDB (reCAPTCHA check), FreshPorts search (Cloudflare), encyclopediaofmath (502), HyperPhysics (bad certificate), archive.org (JS shell).

## Sites (30 registrable domains, at most 3 tasks each)

| Site | Hosts | Tasks |
| --- | --- | --- |
| adaic.org | www.adaic.org | 1 |
| archlinux.org | archlinux.org | 1 |
| automationintesting.online | automationintesting.online | 1 |
| babeljs.io | babeljs.io | 1 |
| blazedemo.com | blazedemo.com | 1 |
| colorhexa.com | www.colorhexa.com | 1 |
| commonmark.org | commonmark.org, spec.commonmark.org | 2 |
| crummy.com | www.crummy.com | 1 |
| demoqa.com | demoqa.com | 3 |
| devdocs.io | devdocs.io | 1 |
| die.net | linux.die.net | 1 |
| elm-lang.org | package.elm-lang.org | 1 |
| erlang.org | www.erlang.org | 2 |
| eso.org | www.eso.org | 1 |
| exiftool.org | exiftool.org | 1 |
| expressjs.com | expressjs.com | 1 |
| ffmpeg.org | ffmpeg.org | 2 |
| fileformat.info | www.fileformat.info | 2 |
| fishshell.com | fishshell.com | 1 |
| formy-project.herokuapp.com | formy-project.herokuapp.com | 1 |
| freedesktop.org | specifications.freedesktop.org | 1 |
| godotengine.org | docs.godotengine.org | 2 |
| guru99.com | demo.guru99.com | 1 |
| hex.pm | hex.pm | 1 |
| khronos.org | www.khronos.org | 1 |
| letcode.in | letcode.in | 1 |
| metacpan.org | metacpan.org | 1 |
| microsoft.com | learn.microsoft.com | 2 |
| mit.edu | shakespeare.mit.edu | 2 |
| mysql.com | dev.mysql.com | 2 |
