"""dev3: forty public browser tasks for tuning. Not a scored set.

Sites' registrable names start with a through m. Answers are literal page
text, and end markers are judge-only, as in heldout2. Live checks are in
bench/verify_dev3.py.
"""

from __future__ import annotations


def _task(task_id, description, start_url, expected, host, url_contains, *, path_suffix="", deny=(), answer=False):
    markers = {"host": host, "url_contains": url_contains}
    if path_suffix:
        markers["path_suffix"] = path_suffix
    markers["deny"] = ["/search", *deny]
    if answer:
        markers["answer_in_text"] = expected
    return {
        "id": task_id,
        "description": description,
        "start_url": start_url,
        "expected_answer": expected,
        "check_url_contains": url_contains,
        "end_markers": markers,
    }


DEV3_TASKS = [
    # nav: reach one page from a start page.
    _task(
        "dev3_nav_ffmpeg_ffprobe",
        "From the FFmpeg documentation index, open the documentation page for FFmpeg's command-line tool that inspects multimedia streams and prints information about them.",
        "https://ffmpeg.org/documentation.html",
        "ffprobe Documentation", "ffmpeg.org", "/ffprobe.html", path_suffix="/ffprobe.html",
    ),
    _task(
        "dev3_nav_mit_hamlet",
        "On MIT's Complete Works of William Shakespeare site, open the whole text of the tragedy about the Prince of Denmark as one single page.",
        "https://shakespeare.mit.edu/",
        "Hamlet: Entire Play", "shakespeare.mit.edu", "/hamlet/full.html", path_suffix="/hamlet/full.html",
    ),
    _task(
        "dev3_nav_fish_tutorial",
        "From the fish shell home page, open the getting-started guide for new users in the current documentation.",
        "https://fishshell.com/",
        "Tutorial", "fishshell.com", "/docs/current/tutorial.html", path_suffix="/docs/current/tutorial.html",
    ),
    _task(
        "dev3_nav_godot_gdscript",
        "From the Godot Engine documentation home, open the main language reference page for GDScript.",
        "https://docs.godotengine.org/en/stable/",
        "GDScript reference", "docs.godotengine.org", "/tutorials/scripting/gdscript/gdscript_basics.html",
        path_suffix="/gdscript/gdscript_basics.html",
    ),
    _task(
        "dev3_nav_mysql_json",
        "In the MySQL 8.4 Reference Manual, open the section that describes the data type for storing JSON documents.",
        "https://dev.mysql.com/doc/refman/8.4/en/",
        "The JSON Data Type", "dev.mysql.com", "/doc/refman/8.4/en/json.html", path_suffix="/en/json.html",
    ),
    _task(
        "dev3_nav_commonmark_030",
        "From the CommonMark home page, open the version of the CommonMark specification that was published in June 2021.",
        "https://commonmark.org/",
        "Version 0.30 (2021-06-19)", "spec.commonmark.org", "/0.30/", path_suffix="/0.30/",
    ),
    _task(
        "dev3_nav_freedesktop_desktop_entry",
        "From the freedesktop.org specifications index, open the latest version of the specification for .desktop application launcher files.",
        "https://specifications.freedesktop.org/",
        "Desktop Entry Specification", "specifications.freedesktop.org", "/desktop-entry/latest/",
        path_suffix="/desktop-entry/latest/",
    ),
    _task(
        "dev3_nav_erlang_getting_started",
        "From the Erlang/OTP documentation, open the first page of the Getting Started With Erlang user's guide.",
        "https://www.erlang.org/doc/",
        "Introduction", "www.erlang.org", "/doc/system/getting_started.html", path_suffix="/system/getting_started.html",
    ),
    _task(
        "dev3_nav_mslearn_keywords",
        "From Microsoft Learn's C# documentation home, open the language reference page that lists all of C#'s reserved and contextual keywords.",
        "https://learn.microsoft.com/en-us/dotnet/csharp/",
        "C# keywords", "learn.microsoft.com", "/dotnet/csharp/language-reference/keywords/",
        path_suffix="/language-reference/keywords/",
    ),
    _task(
        "dev3_nav_express_middleware",
        "From the Express.js home page, open the guide page that explains how to use middleware in an Express app.",
        "https://expressjs.com/",
        "Using middleware", "expressjs.com", "/guide/using-middleware", path_suffix="/guide/using-middleware/",
    ),
    # value: one exact value from a page reached by navigating.
    _task(
        "dev3_value_commonmark_028",
        "On the CommonMark site, find the list of all versions of the specification and report the release date of version 0.28, as written there.",
        "https://commonmark.org/",
        "2017-08-01", "spec.commonmark.org", "spec.commonmark.org", answer=True,
    ),
    _task(
        "dev3_value_ffmpeg_codename",
        "On the FFmpeg download pages, find the list of older releases and report the codename of the FFmpeg 5.0 release line.",
        "https://ffmpeg.org/download.html",
        "Lorentz", "ffmpeg.org", "/olddownload.html", path_suffix="/olddownload.html", answer=True,
    ),
    _task(
        "dev3_value_mysql_mediumint",
        "In the MySQL 8.4 Reference Manual, find the data type storage requirements and report how much storage a MEDIUMINT column needs.",
        "https://dev.mysql.com/doc/refman/8.4/en/",
        "3 bytes", "dev.mysql.com", "/doc/refman/8.4/en/storage-requirements.html",
        path_suffix="/storage-requirements.html", answer=True,
    ),
    _task(
        "dev3_value_colorhexa_websafe",
        "On ColorHexa, look up the hex color ff7f50 and report the closest web safe color it gives, with the leading hash sign.",
        "https://www.colorhexa.com/",
        "#ff6666", "www.colorhexa.com", "/ff7f50", path_suffix="/ff7f50", answer=True,
    ),
    _task(
        "dev3_value_fileformat_snowman",
        "On FileFormat.Info, open the Unicode character page for SNOWMAN (U+2603) and report its UTF-8 encoding in hex, written with 0x prefixes as on the page.",
        "https://www.fileformat.info/info/unicode/",
        "0xE2 0x98 0x83", "www.fileformat.info", "/info/unicode/char/2603/", path_suffix="/char/2603/index.htm",
        deny=("search.htm",), answer=True,
    ),
    _task(
        "dev3_value_exif_gpsaltref",
        "In ExifTool's tag name documentation, open the GPS tags table and report the hexadecimal tag ID of GPSAltitudeRef.",
        "https://exiftool.org/TagNames/",
        "0x0005", "exiftool.org", "/TagNames/GPS.html", path_suffix="/TagNames/GPS.html", answer=True,
    ),
    _task(
        "dev3_value_crummy_bs3",
        "From crummy.com, go to the Beautiful Soup project page and report the version number of the final Beautiful Soup 3 release.",
        "https://www.crummy.com/",
        "3.2.2", "www.crummy.com", "/software/BeautifulSoup/", path_suffix="/software/BeautifulSoup/", answer=True,
    ),
    _task(
        "dev3_value_eso_vlt_at",
        "On ESO's public website, open the page about the Very Large Telescope and report the diameter of its movable Auxiliary Telescopes.",
        "https://www.eso.org/public/",
        "1.8m", "www.eso.org", "/teles-instr/paranal-observatory/vlt/", path_suffix="/paranal-observatory/vlt/",
        answer=True,
    ),
    _task(
        "dev3_value_khronos_gl46",
        "On the Khronos Group website, open the OpenGL page and report the date on which the OpenGL 4.6 specifications were released.",
        "https://www.khronos.org/",
        "July 31, 2017", "www.khronos.org", "/opengl/", path_suffix="/opengl/", answer=True,
    ),
    _task(
        "dev3_value_mslearn_decimal",
        "In Microsoft Learn's C# language reference, find the floating-point numeric types and report the precision listed for decimal.",
        "https://learn.microsoft.com/en-us/dotnet/csharp/",
        "28-29 digits", "learn.microsoft.com", "/builtin-types/floating-point-numeric-types",
        path_suffix="/floating-point-numeric-types", answer=True,
    ),
    # search: the site's own search box, then the finished page.
    _task(
        "dev3_search_metacpan_moose",
        "Use MetaCPAN's search box to find the Moose object system for Perl and open its documentation page. Do not stop at search results.",
        "https://metacpan.org/",
        "Moose - A postmodern object system for Perl 5", "metacpan.org", "/pod/Moose", path_suffix="/pod/Moose",
        deny=("q=",),
    ),
    _task(
        "dev3_search_hex_plug",
        "Use the Hex package search to find the Elixir package named plug and open its package page. Do not stop at search results.",
        "https://hex.pm/",
        "Compose web applications with functions", "hex.pm", "/packages/plug", path_suffix="/packages/plug",
        deny=("search=",),
    ),
    _task(
        "dev3_search_archlinux_nginx",
        "Use the Arch Linux package search to find the stable nginx web server package (not the mainline one) in the extra repository and open its package details page. Do not stop at search results.",
        "https://archlinux.org/packages/",
        "Package Details: nginx", "archlinux.org", "/packages/extra/x86_64/nginx/", path_suffix="/packages/extra/x86_64/nginx/",
        deny=("q=",),
    ),
    _task(
        "dev3_search_godot_signals",
        "Use the Godot documentation's search box to look up signals, then open the step-by-step getting-started page that teaches how to connect and use them. Do not stop at search results.",
        "https://docs.godotengine.org/en/stable/",
        "Using signals", "docs.godotengine.org", "/getting_started/step_by_step/signals.html",
        path_suffix="/step_by_step/signals.html", deny=("search.html",),
    ),
    _task(
        "dev3_search_fileformat_heart",
        "Use FileFormat.Info's Unicode character search to find the playing-card heart symbol (the suit, not the heavy heart) and open its character page. Do not stop at search results.",
        "https://www.fileformat.info/info/unicode/char/search.htm",
        "Unicode Character 'BLACK HEART SUIT' (U+2665)", "www.fileformat.info", "/info/unicode/char/2665/",
        path_suffix="/char/2665/index.htm", deny=("search.htm",),
    ),
    _task(
        "dev3_search_erlang_lists",
        "Use the Erlang/OTP documentation's search to find the standard library module for list processing and open its reference page. Do not stop at search results.",
        "https://www.erlang.org/doc/",
        "lists", "www.erlang.org", "/doc/apps/stdlib/lists.html", path_suffix="/stdlib/lists.html",
        deny=("search.html",),
    ),
    # form: fill and submit a public demo form, then report the result text.
    _task(
        "dev3_form_demoqa_textbox",
        "On the DemoQA text box demo, enter the full name Alex Example and the email alex@example.com, submit, and report the name line shown in the output.",
        "https://demoqa.com/text-box",
        "Name:Alex Example", "demoqa.com", "/text-box", answer=True,
    ),
    _task(
        "dev3_form_demoqa_practice",
        "Fill in DemoQA's student registration practice form with first name Alex, last name Example, gender Other, and mobile number 0123456789. Submit it and report the heading of the confirmation dialog.",
        "https://demoqa.com/automation-practice-form",
        "Thanks for submitting the form", "demoqa.com", "/automation-practice-form", answer=True,
    ),
    _task(
        "dev3_form_formy_complete",
        "Complete the Formy web form with first name Alex, last name Example and job title Tester, submit it, and report the success message shown afterwards.",
        "https://formy-project.herokuapp.com/form",
        "The form was successfully submitted!", "formy-project.herokuapp.com", "/thanks", path_suffix="/thanks",
        answer=True,
    ),
    _task(
        "dev3_form_blazedemo_purchase",
        "On BlazeDemo, find flights from Boston to London, choose any flight, complete the purchase form with the name Alex Example, and report the thank-you heading on the confirmation page.",
        "https://blazedemo.com/",
        "Thank you for your purchase today!", "blazedemo.com", "/confirmation.php", path_suffix="/confirmation.php",
        answer=True,
    ),
    _task(
        "dev3_form_aito_contact",
        "On the Shady Meadows B&B demo site, send the contact form with name Alex Example, email alex@example.com, phone 01234567890, subject Booking enquiry, and a message of at least twenty characters. Report the thank-you heading that appears.",
        "https://automationintesting.online/",
        "Thanks for getting in touch Alex Example!", "automationintesting.online", "automationintesting.online/",
        answer=True,
    ),
    _task(
        "dev3_form_guru99_register",
        "Register on the Guru99 Mercury Tours demo with first name Alex, last name Example, user name alexexample and password Demo1234, then report the sentence that thanks you for registering.",
        "https://demo.guru99.com/test/newtours/register.php",
        "Thank you for registering.", "demo.guru99.com", "/test/newtours/register", answer=True,
    ),
    # title: report a page or item title.
    _task(
        "dev3_title_adaic_protected",
        "In the Ada 2012 Reference Manual, open the section that defines protected types and protected objects, and report its full numbered section heading.",
        "https://www.adaic.org/resources/add_content/standards/12rm/html/RM-TOC.html",
        "9.4 Protected Units and Protected Objects", "www.adaic.org", "/standards/12rm/html/RM-9-4.html",
        path_suffix="/RM-9-4.html", answer=True,
    ),
    _task(
        "dev3_title_mit_romeo",
        "On MIT's Shakespeare site, open Act 2, Scene 2 of Romeo and Juliet (the balcony scene) and report the scene heading exactly as shown.",
        "https://shakespeare.mit.edu/",
        "SCENE II. Capulet's orchard.", "shakespeare.mit.edu", "/romeo_juliet/romeo_juliet.2.2.html",
        path_suffix="/romeo_juliet.2.2.html", answer=True,
    ),
    _task(
        "dev3_title_die_nl",
        "On die.net's Linux man pages, open the section 1 page for the nl command and report the one-line entry under its Name heading.",
        "https://linux.die.net/man/",
        "nl - number lines of files", "linux.die.net", "/man/1/nl", path_suffix="/man/1/nl", answer=True,
    ),
    _task(
        "dev3_title_babel_typescript",
        "In the Babel documentation, open the page for the preset that strips TypeScript type annotations and report the page's main heading.",
        "https://babeljs.io/docs/",
        "@babel/preset-typescript", "babeljs.io", "/docs/babel-preset-typescript",
        path_suffix="/docs/babel-preset-typescript", answer=True,
    ),
    # spa: content rendered by JavaScript, or revealed by a click.
    _task(
        "dev3_spa_devdocs_flat",
        "On DevDocs, open the JavaScript reference entry for the array method that flattens nested sub-arrays into a new array, and report the entry's title.",
        "https://devdocs.io/",
        "Array.prototype.flat()", "devdocs.io", "/javascript/global_objects/array/flat",
        path_suffix="/global_objects/array/flat", answer=True,
    ),
    _task(
        "dev3_spa_elm_repeat",
        "On the Elm package site, open the List module docs for elm/core version 1.0.5 and report the full type signature line of the repeat function.",
        "https://package.elm-lang.org/",
        "repeat : Int -> a -> List a", "package.elm-lang.org", "/packages/elm/core/1.0.5/List",
        path_suffix="/core/1.0.5/List", answer=True,
    ),
    _task(
        "dev3_spa_letcode_total",
        "On LetCode's practice workspace, open the table practice page and report the total shown at the bottom of the shopping list.",
        "https://letcode.in/test",
        "858", "letcode.in", "/table", path_suffix="/table", answer=True,
    ),
    _task(
        "dev3_spa_demoqa_origin",
        "On DemoQA's tabs demo, open the Origin tab and report the name of the college where the Latin professor mentioned there worked.",
        "https://demoqa.com/tabs",
        "Hampden-Sydney College", "demoqa.com", "/tabs", answer=True,
    ),
]

DEV3_TASK_IDS = tuple(task["id"] for task in DEV3_TASKS)
