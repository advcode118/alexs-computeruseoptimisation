"""dev4nav: twelve public read tasks (8 value, 4 title) for the nav read step.

Written before the read step was designed, as its first-contact check. Values
sit in tables, definition lists and prose on ten sites none of the earlier
sets use. Answers are literal page text and end markers are judge-only, as in
dev3. Live checks are in bench/verify_dev4_nav.py.
"""

from __future__ import annotations


def _task(task_id, description, start_url, expected, host, url_contains, *, path_suffix="", deny=()):
    markers = {"host": host, "url_contains": url_contains}
    if path_suffix:
        markers["path_suffix"] = path_suffix
    markers["deny"] = ["/search", *deny]
    markers["answer_in_text"] = expected
    return {
        "id": task_id,
        "description": description,
        "start_url": start_url,
        "expected_answer": expected,
        "check_url_contains": url_contains,
        "end_markers": markers,
    }


DEV4_NAV_TASKS = [
    # value: one cell, one definition or one phrase from a page reached by navigating.
    _task(
        "dev4nav_value_wireshark_srcport",
        "In Wireshark's display filter reference, open the fields of the Transmission Control Protocol and report the type of the tcp.srcport field.",
        "https://www.wireshark.org/docs/dfref/",
        "Unsigned integer (16 bits)", "www.wireshark.org", "/docs/dfref/t/tcp.html", path_suffix="/t/tcp.html",
    ),
    _task(
        "dev4nav_value_lua_51",
        "On the Lua website, find the version history and report the date on which Lua 5.1 was released, as written there.",
        "https://www.lua.org/",
        "21 Feb 2006", "www.lua.org", "/versions.html", path_suffix="/versions.html",
    ),
    _task(
        "dev4nav_value_nano_justify",
        "On the GNU nano documentation page, open the cheatsheet of keyboard shortcuts and report the shortcut that justifies the entire buffer.",
        "https://www.nano-editor.org/docs.php",
        "Alt+J", "www.nano-editor.org", "/dist/latest/cheatsheet.html", path_suffix="/cheatsheet.html",
    ),
    _task(
        "dev4nav_value_openssh_90",
        "On the OpenSSH website, open the release notes and report the release date of OpenSSH 9.0, as written there.",
        "https://www.openssh.com/",
        "2022-04-08", ("openssh.org", "openssh.com"), "/releasenotes.html", path_suffix="/releasenotes.html",
    ),
    _task(
        "dev4nav_value_gradle_java21",
        "In the Gradle User Manual, open the compatibility matrix and report the first Gradle version that supports running Gradle itself on Java 21.",
        "https://docs.gradle.org/current/userguide/userguide.html",
        "8.5", "docs.gradle.org", "/userguide/compatibility.html", path_suffix="/compatibility.html",
    ),
    _task(
        "dev4nav_value_elixir_otp119",
        "In the Elixir documentation on HexDocs, open the compatibility and deprecations page and report which Erlang/OTP versions Elixir 1.19 supports.",
        "https://hexdocs.pm/elixir/",
        "26 - 28", "hexdocs.pm", "/compatibility-and-deprecations.html",
        path_suffix="/compatibility-and-deprecations.html",
    ),
    _task(
        "dev4nav_value_netbsd_90",
        "On the NetBSD releases page, open the history of formal releases and report the release date of NetBSD 9.0.",
        "https://www.netbsd.org/releases/",
        "February 14, 2020", "www.netbsd.org", "/releases/formal.html", path_suffix="/releases/formal.html",
    ),
    _task(
        "dev4nav_value_countrycode_iceland",
        "On CountryCode.org, open the page for Iceland and report its three-letter ISO country code.",
        "https://www.countrycode.org/",
        "ISL", "www.countrycode.org", "/iceland", path_suffix="/iceland",
    ),
    # title: the heading of the page or section reached.
    _task(
        "dev4nav_title_lua_metatables",
        "In the Lua 5.4 reference manual, go to the section about metatables and metamethods and report its full numbered section heading.",
        "https://www.lua.org/manual/5.4/",
        "2.4 – Metatables and Metamethods", "www.lua.org", "/manual/5.4/manual.html",
        path_suffix="/manual/5.4/manual.html",
    ),
    _task(
        "dev4nav_title_elixir_genserver",
        "In the Elixir documentation on HexDocs, open the page for the GenServer module and report the page's main heading.",
        "https://hexdocs.pm/elixir/",
        "GenServer behaviour", "hexdocs.pm", "/GenServer.html", path_suffix="/GenServer.html",
    ),
    _task(
        "dev4nav_title_wireshark_capture",
        "In the Wireshark User's Guide (the chunked HTML version), open the chapter about capturing live network data and report its full chapter heading.",
        "https://www.wireshark.org/docs/wsug_html_chunked/",
        "Chapter 4. Capturing Live Network Data", "www.wireshark.org", "/wsug_html_chunked/ChapterCapture.html",
        path_suffix="/ChapterCapture.html",
    ),
    _task(
        "dev4nav_title_putty_pscp",
        "From the PuTTY documentation page, open the latest user manual, go to the chapter about PSCP and report its full chapter heading.",
        "https://www.chiark.greenend.org.uk/~sgtatham/putty/docs.html",
        "Chapter 5: Using PSCP to transfer files securely", "the.earth.li", "/htmldoc/Chapter5.html",
        path_suffix="/htmldoc/Chapter5.html",
    ),
]

DEV4_NAV_TASK_IDS = tuple(task["id"] for task in DEV4_NAV_TASKS)
