"""val3: an independently authored public validation set of forty tasks.

Sites' registrable domains start with n through z and share no host with the
held-out, heldout2 or heldout3 sets. Mix: 10 nav, 10 value, 6 search, 6 form,
4 title, 4 spa. Live checks are in bench.verify_val3; this is an
aggregate-only gate, so do not print per-task answers in reports.
"""

from __future__ import annotations


def _task(task_id, description, start_url, expected, host, url_contains, *, suffix="", deny=(), answer=""):
    markers = {"host": host, "url_contains": url_contains}
    if suffix:
        markers["path_suffix"] = suffix
    markers["deny"] = ["/search", *deny]
    if answer:
        markers["answer_in_text"] = answer
    return {
        "id": task_id,
        "description": description,
        "start_url": start_url,
        "expected_answer": expected,
        "check_url_contains": url_contains,
        "end_markers": markers,
    }


VAL3_TASKS = [
    # nav: reach a specific page.
    _task(
        "val3_nav_perldoc_regex",
        "On Perldoc, open the main reference page for Perl's regular expressions, not the tutorial or the quick reference.",
        "https://perldoc.perl.org/",
        "perlre",
        "perldoc.perl.org", "/perlre", suffix="/perlre",
    ),
    _task(
        "val3_nav_vimhelp_undo",
        "On the Vim help site, open the help file that covers undoing and redoing changes.",
        "https://vimhelp.org/",
        "undo.txt",
        "vimhelp.org", "/undo.txt.html", suffix="/undo.txt.html",
    ),
    _task(
        "val3_nav_nmap_scantypes",
        "From the Nmap Reference Guide, open the section that describes each of Nmap's scan techniques, such as SYN and connect scans.",
        "https://nmap.org/book/man.html",
        "Port Scanning Techniques",
        "nmap.org", "/book/man-port-scanning-techniques.html", suffix="/book/man-port-scanning-techniques.html",
    ),
    _task(
        "val3_nav_osi_mit",
        "From the Open Source Initiative's list of licenses, open the page for the short permissive license named after the Massachusetts Institute of Technology.",
        "https://opensource.org/licenses",
        "The MIT License",
        "opensource.org", "/license/mit", suffix="/license/mit", deny=("mit-0",),
    ),
    _task(
        "val3_nav_sass_modules",
        "In the Sass documentation, open the page for the at-rule that loads mixins, functions and variables from other stylesheets as modules.",
        "https://sass-lang.com/documentation/",
        "@use",
        "sass-lang.com", "/documentation/at-rules/use", deny=("/import",),
    ),
    _task(
        "val3_nav_ruby_newcomers",
        "From the Ruby documentation page, open the introduction written for programmers who already know another language such as C, Java or Python.",
        "https://www.ruby-lang.org/en/documentation/",
        "Ruby From Other Languages",
        "www.ruby-lang.org", "/en/documentation/ruby-from-other-languages/",
        suffix="/en/documentation/ruby-from-other-languages/",
    ),
    _task(
        "val3_nav_toml_spec",
        "On the TOML website, open the full English specification for version 1.0.0, not a release candidate.",
        "https://toml.io/en/",
        "TOML v1.0.0",
        "toml.io", "/en/v1.0.0", suffix="/en/v1.0.0", deny=("-rc",),
    ),
    _task(
        "val3_nav_zig_features",
        "From the Learn section of the Zig language website, open the in-depth page that walks through the language's feature highlights.",
        "https://ziglang.org/learn/",
        "Overview",
        "ziglang.org", "/learn/overview/", suffix="/learn/overview/",
    ),
    _task(
        "val3_nav_pip_everyday",
        "In pip's documentation, open the general guide to everyday usage, which covers installing packages, requirements files and constraints.",
        "https://pip.pypa.io/en/stable/",
        "User Guide",
        "pip.pypa.io", "/en/stable/user_guide/", suffix="/user_guide/",
    ),
    _task(
        "val3_nav_tcpdump_filter",
        "On the tcpdump and libpcap site, open the manual page that describes the syntax of packet filter expressions.",
        "https://www.tcpdump.org/",
        "pcap-filter",
        "www.tcpdump.org", "/manpages/pcap-filter.7.html", suffix="/manpages/pcap-filter.7.html",
    ),
    # value: read one exact value off a page reached by navigating.
    _task(
        "val3_value_yaml_revision",
        "On the YAML website, open the specification for YAML revision 1.2.2 and report the date of that revision.",
        "https://yaml.org/",
        "2021-10-01",
        "yaml.org", "/spec/1.2.2/", suffix="/spec/1.2.2/", answer="2021-10-01",
    ),
    _task(
        "val3_value_webelements_gallium",
        "On WebElements, open the essentials page for the element gallium and report its CAS registry number.",
        "https://www.webelements.com/",
        "7440-55-3",
        "www.webelements.com", "/gallium/", suffix="/gallium/", answer="7440-55-3",
    ),
    _task(
        "val3_value_webelements_tungsten",
        "On WebElements, open the essentials page for tungsten and report the shell structure it lists.",
        "https://www.webelements.com/",
        "2.8.18.32.12.2",
        "www.webelements.com", "/tungsten/", suffix="/tungsten/", answer="2.8.18.32.12.2",
    ),
    _task(
        "val3_value_sep_frege",
        "Open the Stanford Encyclopedia of Philosophy entry on Gottlob Frege and report the date it was first published, as month, day and year.",
        "https://plato.stanford.edu/",
        "Sep 14, 1995",
        "plato.stanford.edu", "/entries/frege/", suffix="/entries/frege/", answer="Sep 14, 1995",
    ),
    _task(
        "val3_value_periodni_osmium",
        "On the EniG periodic table site, open the page for osmium and report its melting point in degrees Celsius. Give the number only.",
        "https://www.periodni.com/",
        "3033",
        "www.periodni.com", "/os.html", suffix="/os.html", answer="3033",
    ),
    _task(
        "val3_value_osi_zope",
        "From the Open Source Initiative's list of licenses, open the page for the Zope Public License 2.0 and report the name of the person who submitted it.",
        "https://opensource.org/licenses",
        "Gregor Hoffleit",
        "opensource.org", "/license/zpl-2.0", answer="Gregor Hoffleit",
    ),
    _task(
        "val3_value_rapidtables_del",
        "On RapidTables, open the ASCII table and report the hexadecimal code listed for the DEL control character.",
        "https://www.rapidtables.com/",
        "7F",
        "www.rapidtables.com", "/code/text/ascii-table.html", suffix="/code/text/ascii-table.html", answer="7F",
    ),
    _task(
        "val3_value_ninja_iphone",
        "In the tutorialsninja demo store, open the iPhone product page and report its product code.",
        "https://tutorialsninja.com/demo/",
        "product 11",
        "tutorialsninja.com", "product_id=40", deny=("route=product/search",), answer="product 11",
    ),
    _task(
        "val3_value_ruby_eol",
        "On ruby-lang.org, find the page listing the maintenance status of Ruby's release branches and report the end-of-life date given for Ruby 2.6.",
        "https://www.ruby-lang.org/en/",
        "2022-04-12",
        "www.ruby-lang.org", "/en/downloads/branches/", suffix="/en/downloads/branches/", answer="2022-04-12",
    ),
    _task(
        "val3_value_tad_acst",
        "On timeanddate.com, open the time zone abbreviation page for Australian Central Standard Time and report its offset from UTC.",
        "https://www.timeanddate.com/time/zones/",
        "+9:30",
        "www.timeanddate.com", "/time/zones/acst", suffix="/time/zones/acst", answer="+9:30",
    ),
    # search: use the site's own search box.
    _task(
        "val3_search_sep_ockham",
        "Use the Stanford Encyclopedia of Philosophy's own search box to look up Ockham, then open the encyclopedia entry on the medieval philosopher. Do not stop at the search results.",
        "https://plato.stanford.edu/",
        "William of Ockham",
        "plato.stanford.edu", "/entries/ockham/", suffix="/entries/ockham/", deny=("searcher",),
    ),
    _task(
        "val3_search_sqlalchemy_hybrid",
        "Use the SQLAlchemy 2.0 documentation's own search box to look up hybrid properties, then open the ORM extension reference page for them. Do not stop at the search results.",
        "https://docs.sqlalchemy.org/en/20/",
        "Hybrid Attributes",
        "docs.sqlalchemy.org", "/en/20/orm/extensions/hybrid.html", suffix="/orm/extensions/hybrid.html",
        deny=("search.html",),
    ),
    _task(
        "val3_search_pip_reqfiles",
        "Use pip's documentation search box to look up requirements, then open the reference page that specifies the syntax of requirements files. Do not stop at the search results.",
        "https://pip.pypa.io/en/stable/",
        "Requirements File Format",
        "pip.pypa.io", "/en/stable/reference/requirements-file-format/",
        suffix="/reference/requirements-file-format/", deny=("search.html",),
    ),
    _task(
        "val3_search_psycopg_copy",
        "Use the psycopg 3 documentation's search box to look up COPY, then open the basic-usage page about copying data in bulk to and from the server. Do not stop at the search results.",
        "https://www.psycopg.org/psycopg3/docs/",
        "Using COPY TO and COPY FROM",
        "www.psycopg.org", "/psycopg3/docs/basic/copy.html", suffix="/basic/copy.html", deny=("search.html",),
    ),
    _task(
        "val3_search_sympy_sets",
        "Use the SymPy documentation's search box to find the module that solves equations and returns the solutions as sets, then open its reference page. Do not stop at the search results.",
        "https://docs.sympy.org/latest/index.html",
        "Solveset",
        "docs.sympy.org", "/latest/modules/solvers/solveset.html", suffix="/modules/solvers/solveset.html",
        deny=("search.html",),
    ),
    _task(
        "val3_search_perldoc_format",
        "Use Perldoc's search box to look up Perl's built-in function that returns a formatted string rather than printing it, and open that function's documentation page.",
        "https://perldoc.perl.org/",
        "sprintf",
        "perldoc.perl.org", "/functions/sprintf", suffix="/functions/sprintf",
    ),
    # form: fill and submit a form on a public practice or demo site.
    _task(
        "val3_form_qaplayground_register",
        "On QA Playground, open the Register & Login app and create an account with name Alex Example, email alex@example.com and password Practice123. Report the confirmation message shown after you register.",
        "https://qaplayground.dev/",
        "Account created successfully!",
        "qaplayground.dev", "/apps/register-login/", answer="Account created successfully",
    ),
    _task(
        "val3_form_trytesting_login",
        "On the Try Testing This practice site, submit the sample login form using the username and password the page tells you to use, and report the message you get.",
        "https://trytestingthis.netlify.app/",
        "Login Successful",
        "trytestingthis.netlify.app", "/login.html", answer="Login Successful",
    ),
    _task(
        "val3_form_tad_duration",
        "Use timeanddate.com's date duration calculator to count the days from 1 January 2000 to 1 January 2024, without including the end date. Report the number of days.",
        "https://www.timeanddate.com/date/",
        "8766",
        "www.timeanddate.com", "/date/durationresult.html", answer="8766",
    ),
    _task(
        "val3_form_tad_dateadd",
        "Use timeanddate.com's calculator for adding to a date: add 100 days to 1 January 2024 and report the resulting date, including the weekday, as the page shows it.",
        "https://www.timeanddate.com/date/",
        "Wednesday, 10 April 2024",
        "www.timeanddate.com", "/date/dateadded.html", answer="10 April 2024",
    ),
    _task(
        "val3_form_sweetshop_account",
        "Log in to the Sweet Shop demo with its demo email address for the customer who has two previous orders (any password is accepted), and report the total spent shown on the account page.",
        "https://sweetshop.netlify.app/",
        "£7.30",
        "sweetshop.netlify.app", "/00efc23d-b605-4f31-b97b-6bb276de447e.html", deny=("/login",), answer="7.30",
    ),
    _task(
        "val3_form_qaplayground_verify",
        "On QA Playground, open the Verify Your Account app, enter the six-digit confirmation code the page gives you, and report the message shown afterwards.",
        "https://qaplayground.dev/",
        "Success",
        "qaplayground.dev", "/apps/verify-account/", answer="Success",
    ),
    # title: report a page or item title.
    _task(
        "val3_title_vite_server",
        "In Vite's guide, open the page about rendering the app on the server and report the page's main heading.",
        "https://vite.dev/guide/",
        "Server-Side Rendering (SSR)",
        "vite.dev", "/guide/ssr", suffix="/guide/ssr", answer="Server-Side Rendering (SSR)",
    ),
    _task(
        "val3_title_prettier_reasons",
        "In Prettier's docs, open the page that sets out the reasons to adopt Prettier and report its title.",
        "https://prettier.io/docs/",
        "Why Prettier?",
        "prettier.io", "/docs/why-prettier", suffix="/docs/why-prettier", answer="Why Prettier",
    ),
    _task(
        "val3_title_ninja_laptop",
        "In the tutorialsninja demo store, open the Laptops & Notebooks category and report the name of the product priced at $2,000.00.",
        "https://tutorialsninja.com/demo/",
        "Sony VAIO",
        "tutorialsninja.com", "path=18", deny=("route=product/search",), answer="Sony VAIO",
    ),
    _task(
        "val3_title_zod_first",
        "In Zod's documentation, open the page that walks through defining a first schema and parsing data with it, and report the page's title.",
        "https://zod.dev/",
        "Basic usage",
        "zod.dev", "/basics", suffix="/basics", answer="Basic usage",
    ),
    # spa: content rendered by JavaScript or revealed by a click.
    _task(
        "val3_spa_seleniumbase_coffee",
        "From the SeleniumBase home page, open the Coffee Cart demo, add one Cappuccino and one Flat White to the cart, and report the cart total.",
        "https://seleniumbase.io/",
        "$37.00",
        "seleniumbase.io", "/coffee/", answer="$37.00",
    ),
    _task(
        "val3_spa_seleniumbase_button",
        "From the SeleniumBase home page, open its Demo Page, click the button in the Automation Practice table, and report the sentence in the paragraph whose text changes.",
        "https://seleniumbase.io/",
        "This Text is Purple",
        "seleniumbase.io", "/demo_page", answer="This Text is Purple",
    ),
    _task(
        "val3_spa_sweetshop_basket",
        "On the Sweet Shop demo, add one Chocolate Cups and one Bon Bons to the basket, open the basket, and report the total in GBP.",
        "https://sweetshop.netlify.app/sweets",
        "£2.00",
        "sweetshop.netlify.app", "/basket", suffix="/basket", answer="2.00",
    ),
    _task(
        "val3_spa_qaplayground_covered",
        "On QA Playground, open the Covered Elements app, click the button hidden on that page, and report the message that replaces the instruction text.",
        "https://qaplayground.dev/",
        "Mission accomplished",
        "qaplayground.dev", "/apps/covered/", answer="Mission accomplished",
    ),
]

VAL3_TASK_IDS = tuple(task["id"] for task in VAL3_TASKS)
