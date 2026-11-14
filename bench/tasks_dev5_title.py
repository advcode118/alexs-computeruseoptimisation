"""dev5title: twelve public title tasks, written fresh to study title false accepts.

The tasks were written on 14 Nov 2026 before any title fix. val3 and heldout3
showed title tasks failing mostly by confident wrong answers, and the earlier
dev title tasks pass about 90% of the time, so they cannot show the failure.
Each task needs at least one navigation step from its start page, and each
end page has a nearby trap: a tab title with a site suffix, a breadcrumb, a
section label, several h1 elements, a neighbouring item or a same-titled
preview page. All twelve sites are new to every earlier set. Answers are
literal page text, and end markers are used by the judge only. Live checks
are in bench/verify_dev5_title.py.
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


DEV5_TITLE_TASKS = [
    _task(
        "dev5_title_tldp_conditionals",
        "In TLDP's Bash Guide for Beginners, open the chapter about if/then/else tests and case statements, and "
        "report its full chapter heading, number included.",
        "https://tldp.org/LDP/Bash-Beginners-Guide/html/index.html",
        "Chapter 7. Conditional statements", "tldp.org", "/Bash-Beginners-Guide/html/chap_07.html",
        path_suffix="/chap_07.html",
    ),
    _task(
        "dev5_title_openssl_req",
        "In the OpenSSL 3.0 command manual pages, open the page for the command that creates PKCS#10 certificate "
        "requests, and report the one-line entry under its NAME heading.",
        "https://docs.openssl.org/3.0/man1/",
        "openssl-req - PKCS#10 certificate request and certificate generating command", "docs.openssl.org",
        "/3.0/man1/openssl-req",
    ),
    _task(
        "dev5_title_docsrs_deserialize",
        "In the docs.rs documentation for the serde crate, open the page of the trait that a data structure "
        "implements so it can be built from any data format, and report the page's main heading.",
        "https://docs.rs/serde/latest/serde/",
        "Trait Deserialize", "docs.rs", "/serde/trait.Deserialize.html", path_suffix="/trait.Deserialize.html",
    ),
    _task(
        "dev5_title_gitlab_ciyaml",
        "In the GitLab documentation, open the reference page that lists every keyword you can use in a "
        ".gitlab-ci.yml file, and report its main heading.",
        "https://docs.gitlab.com/",
        "CI/CD YAML syntax reference", "docs.gitlab.com", "/ci/yaml",
    ),
    _task(
        "dev5_title_scala_control",
        "In the Scala 3 Book, open the full chapter (not the short 'taste' preview) that covers if/then/else, for "
        "loops and match expressions, and report its main heading.",
        "https://docs.scala-lang.org/scala3/book/introduction.html",
        "Control Structures", "docs.scala-lang.org", "/scala3/book/control-structures.html",
        path_suffix="/book/control-structures.html",
    ),
    _task(
        "dev5_title_ruby_comparable",
        "In the Ruby 3.3 core documentation, open the page of the mixin module that provides <, <=, ==, >=, > and "
        "between? from a <=> method, and report the page's main heading.",
        "https://ruby-doc.org/3.3/",
        "module Comparable", "ruby-doc.org", "/3.3/Comparable.html", path_suffix="/Comparable.html",
    ),
    _task(
        "dev5_title_qt_qstring",
        "In the Qt 6 documentation's list of all C++ classes, open the class that holds a Unicode character string, "
        "and report the page's main heading.",
        "https://doc.qt.io/qt-6/classes.html",
        "QString Class", "doc.qt.io", "/qt-6/qstring.html", path_suffix="/qstring.html",
    ),
    _task(
        "dev5_title_fastapi_numeric",
        "In the FastAPI tutorial, open the page that shows how to declare ge, gt, le and lt limits on path "
        "parameters, and report that page's main heading.",
        "https://fastapi.tiangolo.com/tutorial/",
        "Path Parameters and Numeric Validations", "fastapi.tiangolo.com", "/tutorial/path-params-numeric-validations",
    ),
    _task(
        "dev5_title_celery_periodic",
        "In the Celery user guide, open the chapter on running tasks on a schedule with celery beat, and report its "
        "main heading.",
        "https://docs.celeryq.dev/en/stable/userguide/index.html",
        "Periodic Tasks", "docs.celeryq.dev", "/userguide/periodic-tasks.html", path_suffix="/periodic-tasks.html",
    ),
    _task(
        "dev5_title_meson_deps",
        "In the Meson build system's manual, open the page that explains how to find and use external libraries "
        "with the dependency() function, and report its main heading.",
        "https://mesonbuild.com/Manual.html",
        "Dependencies", "mesonbuild.com", "/Dependencies.html", path_suffix="/Dependencies.html",
    ),
    _task(
        "dev5_title_gentoo_disks",
        "In the Gentoo AMD64 Handbook, open the installation step about partitioning and formatting the disks, "
        "and report that page's main heading.",
        "https://wiki.gentoo.org/wiki/Handbook:AMD64",
        "Preparing the disks", "wiki.gentoo.org", "/wiki/Handbook:AMD64/Installation/Disks",
    ),
    _task(
        "dev5_title_gtk_button",
        "In the GTK 4 API reference, open the page of the widget class that emits a signal when it is clicked, the "
        "plain push button, and report the page's main heading.",
        "https://docs.gtk.org/gtk4/index.html",
        "GtkButton", "docs.gtk.org", "/gtk4/class.Button.html", path_suffix="/class.Button.html",
    ),
]

DEV5_TITLE_TASK_IDS = tuple(task["id"] for task in DEV5_TITLE_TASKS)
