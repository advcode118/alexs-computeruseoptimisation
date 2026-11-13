# Heldout3a public-page verification

Verified 2026-11-13 02:20 UTC with local headless Chromium.

This is page and marker validation, not an agent benchmark. No model calls and no bench probes were run.
Each task was done in headless Chromium, then graded with evidence_verdict.
For every task a wrong value failed, and so did a wrong host, a wrong path on the right host, and a child path, or a sibling path where the marker is slash-tolerant (each with the canonical link removed).
Each directory URL outside the form tasks was loaded again with its trailing slash toggled. That page passed too, or the site answered with an HTTP error, so no agent can end there. Pages without a required fragment passed with an added fragment. The grader was not changed.
Value answers are not the first h1. JavaScript tasks were absent from the no-script HTML.

Reproduce: `python -m bench.verify_heldout3_a` (public network; no model calls).

| Task id | Start status | End URL | Verdict | First-h1 claim | Slash toggle |
| --- | --- | --- | --- | --- | --- |
| ho3a_nav_man_execve | 200 | https://man7.org/linux/man-pages/man2/execve.2.html | PASS | FAIL | file URL |
| ho3a_nav_freebsd_jails | 200 | https://docs.freebsd.org/en/books/handbook/jails/ | PASS | heading is the answer | PASS |
| ho3a_nav_ecma_script | 200 | https://ecma-international.org/publications-and-standards/standards/ecma-262/ | PASS | heading is the answer | PASS |
| ho3a_nav_llvm_parser | 200 | https://llvm.org/docs/tutorial/MyFirstLanguageFrontend/LangImpl02.html | PASS | heading is the answer | file URL |
| ho3a_nav_julia_missing | 200 | https://docs.julialang.org/en/v1/manual/missing/ | PASS | heading is the answer | PASS |
| ho3a_nav_cmake_library | 200 | https://cmake.org/cmake/help/latest/command/add_library.html | PASS | heading is the answer | file URL |
| ho3a_nav_haskell_expressions | 200 | https://www.haskell.org/onlinereport/haskell2010/haskellch3.html#x8-220003 | PASS | not applicable | file URL |
| ho3a_nav_clojure_atoms | 200 | https://clojure.org/reference/atoms | PASS | heading is the answer | HTTP 403 |
| ho3a_value_errno_eperm | 200 | https://man7.org/linux/man-pages/man3/errno.3.html | PASS | FAIL | file URL |
| ho3a_value_bipm_quecto | 200 | https://www.bipm.org/en/measurement-units/si-prefixes | PASS | FAIL | PASS |
| ho3a_value_loc_afar | 200 | https://www.loc.gov/standards/iso639-2/php/code_list.php | PASS | FAIL | file URL |
| ho3a_value_clickhouse_int8 | 200 | https://clickhouse.com/docs/reference/data-types/int-uint | PASS | FAIL | PASS |
| ho3a_value_julia_int64 | 200 | https://docs.julialang.org/en/v1/manual/integers-and-floating-point-numbers/ | PASS | FAIL | PASS |
| ho3a_value_kotlin_int_min | 200 | https://kotlinlang.org/docs/numbers.html | PASS | FAIL | file URL |
| ho3a_value_ascii_soh | 200 | https://man7.org/linux/man-pages/man7/ascii.7.html | PASS | FAIL | file URL |
| ho3a_value_imagemagick_aai | 200 | https://imagemagick.org/formats/#gsc.tab=0 | PASS | FAIL | PASS |
| ho3a_search_llvm_lexicon | 200 | https://llvm.org/docs/Lexicon.html | PASS | heading is the answer | file URL |
| ho3a_search_kernel_sysrq | 200 | https://www.kernel.org/doc/html/latest/admin-guide/sysrq.html | PASS | FAIL | file URL |
| ho3a_search_cmake_custom_target | 200 | https://cmake.org/cmake/help/latest/command/add_custom_target.html#command:add_custom_target | PASS | heading is the answer | file URL |
| ho3a_search_debian_chmod | 200 | https://manpages.debian.org/trixie/coreutils/chmod.1.en.html | PASS | FAIL | file URL |
| ho3a_form_bonigarcia_received | 200 | https://bonigarcia.dev/selenium-webdriver-java/submitted-form.html?my-text=Ada&my-password=&my-textarea=&my-readonly=Readonly+input&my-select=Open+this+select+menu&my-datalist=&my-file=&my-check=on&my-radio=on&my-colors=%23563d7c&my-date=&my-range=5&my-hidden= | PASS | FAIL | file URL |
| ho3a_form_bonigarcia_login | 200 | https://bonigarcia.dev/selenium-webdriver-java/login-sucess.html?username=user&password=user | PASS | FAIL | file URL |
| ho3a_form_httpbingo_type | 200 | https://httpbingo.org/post | PASS | not applicable | file URL |
| ho3a_form_globalsqa_sent | 200 | https://www.globalsqa.com/samplepagetest/?contact-form-id=2599&contact-form-sent=62708&contact-form-hash=740f3db3b251a0bcbd28bce26964be89cbd6de1c&_wpnonce=df88d8d62c#contact-form-2599 | PASS | FAIL | file URL |
| ho3a_js_material_button | 200 | https://material.angular.dev/components/button/overview | PASS | not applicable | PASS |
| ho3a_js_material_checkbox | 200 | https://material.angular.dev/components/checkbox/overview | PASS | not applicable | PASS |
| ho3a_js_desmos_clear | 200 | https://www.desmos.com/scientific | PASS | not applicable | PASS |
| ho3a_title_freebsd_handbook | 200 | https://docs.freebsd.org/en/books/handbook/ | PASS | heading is the answer | PASS |
| ho3a_title_debian_policy | 200 | https://www.debian.org/doc/debian-policy/ | PASS | heading is the answer | PASS |
| ho3a_title_ietf_intro | 200 | https://www.ietf.org/about/introduction/ | PASS | heading is the answer | PASS |

## Candidates dropped before finalization

- lua.org: the server closed repeat connections, so the Lua manual task was replaced by Clojure's reference.
- ISO Open Browsing Platform: Cloudflare challenge in headless Chromium.
- packages.debian.org search: an interstitial challenge page.
- GNU libc manual and MicroPython docs: HTTP 403.
- computer-database.gatling.io: the name did not resolve.
- Maven Central artifact page: HTTP 403.
- Matplotlib's search field stayed hidden, so it was not used as a site search.
- Godot and MongoDB doc search did not expose a result link in time.
- MySQL's search left for search.oracle.com, outside the a–m domain rule.
- MongoDB's BSON size sentence sat past the grader's text cap.
- angular.dev, Ant Design, MUI, Ionic, Chakra, Lit, and Elm already contained the sample string in the no-script HTML, so they were not used as script-only pages.
