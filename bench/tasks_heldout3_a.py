"""Held-out web tasks, split heldout3a.

Registrable domains start with a–m and are not used by bench.tasks.
Answers are literal page text. Markers are judge-only.
"""

from __future__ import annotations

HELDOUT3A_TASKS = [
    {
        "id": "ho3a_nav_man_execve",
        "description": (
            "From the Linux man-pages index, open section 2, then the manual page "
            "for the call that replaces the current process image with a new program. "
            "Report the NAME line, including the call and its short description."
        ),
        "start_url": "https://man7.org/linux/man-pages/",
        "expected_answer": "execve - execute program",
        "check_url_contains": "/linux/man-pages/man2/execve.2.html",
        "end_markers": {
            "host": "man7.org",
            "url_contains": "/linux/man-pages/man2/execve.2.html",
            "path_suffix": "/linux/man-pages/man2/execve.2.html",
            "deny": ["/search", "dir_section", "execveat"],
            "answer_in_text": "execve - execute program",
        },
    },
    {
        "id": "ho3a_nav_freebsd_jails",
        "description": (
            "From the FreeBSD home page, open the handbook, then the chapter about "
            "the operating system's lightweight virtualization that isolates a process "
            "tree from the rest of the system. Report that chapter's main heading."
        ),
        "start_url": "https://www.freebsd.org/",
        "expected_answer": "Chapter 17. Jails and Containers",
        "check_url_contains": "/books/handbook/jails",
        "end_markers": {
            "host": "docs.freebsd.org",
            "url_contains": "/books/handbook/jails",
            "path_suffix": "/books/handbook/jails",
            "deny": ["/search"],
            "answer_in_text": "Chapter 17. Jails and Containers",
        },
    },
    {
        "id": "ho3a_nav_ecma_script",
        "description": (
            "From the Ecma International home page, open the publications and standards "
            "catalogue, then the specification for the ECMAScript programming language. "
            "Report the standard number shown as the main heading."
        ),
        "start_url": "https://ecma-international.org/",
        "expected_answer": "ECMA-262",
        "check_url_contains": "/publications-and-standards/standards/ecma-262",
        "end_markers": {
            "host": "ecma-international.org",
            "url_contains": "/publications-and-standards/standards/ecma-262",
            "path_suffix": "/publications-and-standards/standards/ecma-262",
            "deny": ["/search", "/technical-committees/"],
            "answer_in_text": "ECMA-262",
        },
    },
    {
        "id": "ho3a_nav_llvm_parser",
        "description": (
            "From the LLVM project home page, open the documentation, then the "
            "Kaleidoscope tutorial chapter that turns a token stream into a parser "
            "and an abstract syntax tree. Report the full chapter heading."
        ),
        "start_url": "https://llvm.org/",
        "expected_answer": "2. Kaleidoscope: Implementing a Parser and AST",
        "check_url_contains": "/docs/tutorial/MyFirstLanguageFrontend/LangImpl02.html",
        "end_markers": {
            "host": "llvm.org",
            "url_contains": "/docs/tutorial/MyFirstLanguageFrontend/LangImpl02.html",
            "path_suffix": "/docs/tutorial/MyFirstLanguageFrontend/LangImpl02.html",
            "deny": ["/search"],
            "answer_in_text": "2. Kaleidoscope: Implementing a Parser and AST",
        },
    },
    {
        "id": "ho3a_nav_julia_missing",
        "description": (
            "From the Julia language home page, open the documentation, then the "
            "manual page about the value used for a hole in a collection of data. "
            "Report the main heading."
        ),
        "start_url": "https://julialang.org/",
        "expected_answer": "Missing Values",
        "check_url_contains": "/en/v1/manual/missing",
        "end_markers": {
            "host": "docs.julialang.org",
            "url_contains": "/en/v1/manual/missing",
            "path_suffix": "/en/v1/manual/missing",
            "deny": ["/search"],
            "answer_in_text": "Missing Values",
        },
    },
    {
        "id": "ho3a_nav_cmake_library",
        "description": (
            "From the CMake home page, open the documentation, then the current "
            "reference, then the command index, then the command that declares a "
            "library build target. Report the command name shown as the heading."
        ),
        "start_url": "https://cmake.org/",
        "expected_answer": "add_library",
        "check_url_contains": "/cmake/help/latest/command/add_library.html",
        "end_markers": {
            "host": "cmake.org",
            "url_contains": "/cmake/help/latest/command/add_library.html",
            "path_suffix": "/cmake/help/latest/command/add_library.html",
            "deny": ["/search", "add_custom"],
            "answer_in_text": "add_library",
        },
    },
    {
        "id": "ho3a_nav_haskell_expressions",
        "description": (
            "From the Haskell home page, open the documentation, then the language "
            "report, then the chapter that defines expression syntax. Report that "
            "chapter's heading."
        ),
        "start_url": "https://www.haskell.org/",
        "expected_answer": "Chapter 3 Expressions",
        "check_url_contains": "/onlinereport/haskell2010/haskellch3.html",
        "end_markers": {
            "host": "haskell.org",
            "url_contains": "/onlinereport/haskell2010/haskellch3.html",
            "path_suffix": "/onlinereport/haskell2010/haskellch3.html",
            "deny": ["/search"],
            "answer_in_text": "Chapter 3 Expressions",
        },
    },
    {
        "id": "ho3a_nav_lua_coroutines",
        "description": (
            "From the Lua website, open the documentation, then the current reference "
            "manual, then the section about collaborative threads that can suspend "
            "and later resume. Report that section's heading."
        ),
        "start_url": "https://www.lua.org/",
        "expected_answer": "2.6 \u2013 Coroutines",
        "check_url_contains": "#2.6",
        "end_markers": {
            "host": "lua.org",
            "url_contains": "#2.6",
            "path_suffix": "/manual.html",
            "deny": ["/search"],
            "answer_in_text": "2.6 \u2013 Coroutines",
        },
    },
    {
        "id": "ho3a_value_errno_eperm",
        "description": (
            "Open the Linux errno(3) manual page. In the list of error numbers, "
            "report the symbolic name for numeric value 1."
        ),
        "start_url": "https://man7.org/linux/man-pages/",
        "expected_answer": "EPERM",
        "check_url_contains": "/linux/man-pages/man3/errno.3.html",
        "end_markers": {
            "host": "man7.org",
            "url_contains": "/linux/man-pages/man3/errno.3.html",
            "path_suffix": "/linux/man-pages/man3/errno.3.html",
            "deny": ["/search"],
            "answer_in_text": "EPERM",
        },
    },
    {
        "id": "ho3a_value_bipm_quecto",
        "description": (
            "Open the BIPM table of SI prefixes and report the prefix name whose "
            "symbol is the single lowercase letter q."
        ),
        "start_url": "https://www.bipm.org/en/measurement-units",
        "expected_answer": "quecto",
        "check_url_contains": "/en/measurement-units/si-prefixes",
        "end_markers": {
            "host": "www.bipm.org",
            "url_contains": "/en/measurement-units/si-prefixes",
            "path_suffix": "/en/measurement-units/si-prefixes",
            "deny": ["/search"],
            "answer_in_text": "quecto",
        },
    },
    {
        "id": "ho3a_value_loc_afar",
        "description": (
            "Open the Library of Congress ISO 639-2 language code list and report "
            "the three-letter bibliographic code for Afar."
        ),
        "start_url": "https://www.loc.gov/standards/iso639-2/",
        "expected_answer": "aar",
        "check_url_contains": "/standards/iso639-2/php/code_list.php",
        "end_markers": {
            "host": "www.loc.gov",
            "url_contains": "/standards/iso639-2/php/code_list.php",
            "path_suffix": "/standards/iso639-2/php/code_list.php",
            "deny": ["/search"],
            "answer_in_text": "aar",
        },
    },
    {
        "id": "ho3a_value_clickhouse_int8",
        "description": (
            "Open the ClickHouse integer types reference and report the range shown "
            "for Int8, including the brackets, the spaces, and the colon."
        ),
        "start_url": "https://clickhouse.com/docs",
        "expected_answer": "[-128 : 127]",
        "check_url_contains": "/docs/reference/data-types/int-uint",
        "end_markers": {
            "host": "clickhouse.com",
            "url_contains": "/docs/reference/data-types/int-uint",
            "path_suffix": "/docs/reference/data-types/int-uint",
            "deny": ["/search"],
            "answer_in_text": "[-128 : 127]",
        },
    },
    {
        "id": "ho3a_value_julia_int64",
        "description": (
            "Open the Julia manual page about integers and floating-point numbers. "
            "Report the maximum value of the default 64-bit signed integer type, "
            "as a decimal integer with no separators."
        ),
        "start_url": "https://docs.julialang.org/en/v1/",
        "expected_answer": "9223372036854775807",
        "check_url_contains": "/en/v1/manual/integers-and-floating-point-numbers",
        "end_markers": {
            "host": "docs.julialang.org",
            "url_contains": "/en/v1/manual/integers-and-floating-point-numbers",
            "path_suffix": "/en/v1/manual/integers-and-floating-point-numbers",
            "deny": ["/search"],
            "answer_in_text": "9223372036854775807",
        },
    },
    {
        "id": "ho3a_value_kotlin_int_min",
        "description": (
            "Open the Kotlin documentation page on numbers. In the integer types "
            "table, report the minimum value shown for the Int type, including the "
            "minus sign and the thousands separators."
        ),
        "start_url": "https://kotlinlang.org/docs/home.html",
        "expected_answer": "-2,147,483,648",
        "check_url_contains": "/docs/numbers.html",
        "end_markers": {
            "host": "kotlinlang.org",
            "url_contains": "/docs/numbers.html",
            "path_suffix": "/docs/numbers.html",
            "deny": ["/search"],
            "answer_in_text": "-2,147,483,648",
        },
    },
    {
        "id": "ho3a_value_ascii_soh",
        "description": (
            "Open the Linux ascii(7) manual page and report the parenthetical "
            "description of the control character whose abbreviation is SOH."
        ),
        "start_url": "https://man7.org/linux/man-pages/",
        "expected_answer": "start of heading",
        "check_url_contains": "/linux/man-pages/man7/ascii.7.html",
        "end_markers": {
            "host": "man7.org",
            "url_contains": "/linux/man-pages/man7/ascii.7.html",
            "path_suffix": "/linux/man-pages/man7/ascii.7.html",
            "deny": ["/search"],
            "answer_in_text": "start of heading",
        },
    },
    {
        "id": "ho3a_value_imagemagick_aai",
        "description": (
            "Open ImageMagick's image formats reference and report the description "
            "cell for the format code AAI."
        ),
        "start_url": "https://imagemagick.org/",
        "expected_answer": "AAI Dune image",
        "check_url_contains": "/formats",
        "end_markers": {
            "host": "imagemagick.org",
            "url_contains": "/formats",
            "path_suffix": "/formats",
            "deny": ["/search"],
            "answer_in_text": "AAI Dune image",
        },
    },
    {
        "id": "ho3a_search_llvm_lexicon",
        "description": (
            "Use the LLVM documentation's own search box to look up Lexicon, then "
            "open that page. Do not stop at search results. Report its main heading."
        ),
        "start_url": "https://llvm.org/docs/",
        "expected_answer": "The LLVM Lexicon",
        "check_url_contains": "/docs/Lexicon.html",
        "end_markers": {
            "host": "llvm.org",
            "url_contains": "/docs/Lexicon.html",
            "path_suffix": "/docs/Lexicon.html",
            "deny": ["/search", "search.html"],
            "answer_in_text": "The LLVM Lexicon",
        },
    },
    {
        "id": "ho3a_search_kernel_sysrq",
        "description": (
            "Use the Linux kernel HTML documentation's own search box to look up "
            "sysrq, then open the administrator-guide page for that key. Do not "
            "stop at search results. Report the page's specific heading."
        ),
        "start_url": "https://www.kernel.org/doc/html/latest/",
        "expected_answer": "Linux Magic System Request Key Hacks",
        "check_url_contains": "/doc/html/latest/admin-guide/sysrq.html",
        "end_markers": {
            "host": "www.kernel.org",
            "url_contains": "/doc/html/latest/admin-guide/sysrq.html",
            "path_suffix": "/doc/html/latest/admin-guide/sysrq.html",
            "deny": ["/search", "search.html"],
            "answer_in_text": "Linux Magic System Request Key Hacks",
        },
    },
    {
        "id": "ho3a_search_cmake_custom_target",
        "description": (
            "Use the CMake documentation's own search box to look up custom target, "
            "then open the command reference for a build target with no output file. "
            "Do not stop at search results. Report the command name shown as the heading."
        ),
        "start_url": "https://cmake.org/cmake/help/latest/index.html",
        "expected_answer": "add_custom_target",
        "check_url_contains": "/cmake/help/latest/command/add_custom_target.html",
        "end_markers": {
            "host": "cmake.org",
            "url_contains": "/cmake/help/latest/command/add_custom_target.html",
            "path_suffix": "/cmake/help/latest/command/add_custom_target.html",
            "deny": ["/search", "search.html"],
            "answer_in_text": "add_custom_target",
        },
    },
    {
        "id": "ho3a_search_debian_chmod",
        "description": (
            "Use the Debian manpages site's own search box to look up chmod and "
            "open the English section 1 page. Report the short description from "
            "the NAME section, without the command name."
        ),
        "start_url": "https://manpages.debian.org/",
        "expected_answer": "change file mode bits",
        "check_url_contains": "chmod.1.en.html",
        "end_markers": {
            "host": "manpages.debian.org",
            "url_contains": "chmod.1.en.html",
            "path_suffix": "chmod.1.en.html",
            "deny": ["/search", "jump?"],
            "answer_in_text": "change file mode bits",
        },
    },
    {
        "id": "ho3a_form_bonigarcia_received",
        "description": (
            "On the practice web form, enter Ada in the text input and submit the "
            "form. Report the one-word confirmation, including the exclamation mark."
        ),
        "start_url": "https://bonigarcia.dev/selenium-webdriver-java/web-form.html",
        "expected_answer": "Received!",
        "check_url_contains": "/selenium-webdriver-java/submitted-form.html",
        "end_markers": {
            "host": "bonigarcia.dev",
            "url_contains": "/selenium-webdriver-java/submitted-form.html",
            "path_suffix": "/selenium-webdriver-java/submitted-form.html",
            "deny": ["/web-form.html", "/search"],
            "answer_in_text": "Received!",
        },
    },
    {
        "id": "ho3a_form_bonigarcia_login",
        "description": (
            "On the practice login form, sign in with username user and password "
            "user. Submit it and report the confirmation sentence."
        ),
        "start_url": "https://bonigarcia.dev/selenium-webdriver-java/login-form.html",
        "expected_answer": "Login successful",
        "check_url_contains": "/selenium-webdriver-java/login-sucess.html",
        "end_markers": {
            "host": "bonigarcia.dev",
            "url_contains": "/selenium-webdriver-java/login-sucess.html",
            "path_suffix": "/selenium-webdriver-java/login-sucess.html",
            "deny": ["/login-form.html", "/search"],
            "answer_in_text": "Login successful",
        },
    },
    {
        "id": "ho3a_form_httpbingo_type",
        "description": (
            "From the HTTP Bingo home page, open the HTML form demo (the pizza order "
            "form). Fill customer name Ada Example, telephone 555-0100, and email "
            "ada@example.com. Choose the medium size and submit. Report the "
            "Content-Type header value shown in the response."
        ),
        "start_url": "https://httpbingo.org/",
        "expected_answer": "application/x-www-form-urlencoded",
        "check_url_contains": "httpbingo.org/post",
        "end_markers": {
            "host": "httpbingo.org",
            "url_contains": "httpbingo.org/post",
            "path_suffix": "/post",
            "deny": ["/forms/", "/search"],
            "answer_in_text": "application/x-www-form-urlencoded",
        },
    },
    {
        "id": "ho3a_form_globalsqa_sent",
        "description": (
            "From the GlobalSQA home page, open the Sample Page Test. On its contact "
            "form, enter name Ada Example, email ada@example.com, and comment Hello "
            "from the checker. Submit the form and report the sentence that says the "
            "message was sent."
        ),
        "start_url": "https://www.globalsqa.com/",
        "expected_answer": "Your message has been sent",
        "check_url_contains": "contact-form-sent",
        "end_markers": {
            "host": "www.globalsqa.com",
            "url_contains": "contact-form-sent",
            "path_suffix": "/samplepagetest/",
            "deny": ["/search"],
            "answer_in_text": "Your message has been sent",
        },
    },
    {
        "id": "ho3a_js_material_button",
        "description": (
            "Open the Angular Material button overview and report the component "
            "class name the page uses when it discusses screen-reader capitalization."
        ),
        "start_url": "https://material.angular.dev/",
        "expected_answer": "MatButton",
        "check_url_contains": "/components/button/overview",
        "end_markers": {
            "host": "material.angular.dev",
            "url_contains": "/components/button/overview",
            "path_suffix": "/components/button/overview",
            "deny": ["/search"],
            "answer_in_text": "MatButton",
        },
    },
    {
        "id": "ho3a_js_material_checkbox",
        "description": (
            "Open the Angular Material checkbox overview and report the component "
            "class name shown for the checkbox."
        ),
        "start_url": "https://material.angular.dev/",
        "expected_answer": "MatCheckbox",
        "check_url_contains": "/components/checkbox/overview",
        "end_markers": {
            "host": "material.angular.dev",
            "url_contains": "/components/checkbox/overview",
            "path_suffix": "/components/checkbox/overview",
            "deny": ["/search"],
            "answer_in_text": "MatCheckbox",
        },
    },
    {
        "id": "ho3a_js_desmos_clear",
        "description": (
            "Open the Desmos scientific calculator and report the lowercase label "
            "of the control that clears the whole calculation."
        ),
        "start_url": "https://www.desmos.com/",
        "expected_answer": "clear all",
        "check_url_contains": "/scientific",
        "end_markers": {
            "host": "www.desmos.com",
            "url_contains": "/scientific",
            "path_suffix": "/scientific",
            "deny": ["/search"],
            "answer_in_text": "clear all",
        },
    },
    {
        "id": "ho3a_title_freebsd_handbook",
        "description": "Open the handbook for FreeBSD and report its main heading.",
        "start_url": "https://www.freebsd.org/",
        "expected_answer": "FreeBSD Handbook",
        "check_url_contains": "/books/handbook",
        "end_markers": {
            "host": "docs.freebsd.org",
            "url_contains": "/en/books/handbook",
            "path_suffix": "/en/books/handbook",
            "deny": ["/search", "/jails"],
            "answer_in_text": "FreeBSD Handbook",
        },
    },
    {
        "id": "ho3a_title_debian_policy",
        "description": (
            "From the Debian documentation index, open the developers' manuals list, "
            "then the policy manual for Debian packages. Report its main heading."
        ),
        "start_url": "https://www.debian.org/doc/",
        "expected_answer": "Debian Policy Manual",
        "check_url_contains": "/doc/debian-policy",
        "end_markers": {
            "host": "debian.org",
            "url_contains": "/doc/debian-policy",
            "path_suffix": "/doc/debian-policy",
            "deny": ["/search", "devel-manuals"],
            "answer_in_text": "Debian Policy Manual",
        },
    },
    {
        "id": "ho3a_title_ietf_intro",
        "description": (
            "From the IETF home page, open the page that introduces the organization. "
            "Report its main heading."
        ),
        "start_url": "https://www.ietf.org/",
        "expected_answer": "Introduction to the IETF",
        "check_url_contains": "/about/introduction",
        "end_markers": {
            "host": "www.ietf.org",
            "url_contains": "/about/introduction",
            "path_suffix": "/about/introduction",
            "deny": ["/search"],
            "answer_in_text": "Introduction to the IETF",
        },
    },
]
