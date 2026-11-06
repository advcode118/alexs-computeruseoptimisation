"""Deterministic page checks. This module never calls a model."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import unquote, urlparse

from loop.actions import ActionError, AssertText, AssertTitle, AssertUrl, check_url
from loop.browser import BrowserSession, check

REPO_ROOT = Path(__file__).resolve().parents[1]
REPLAY_DIR = REPO_ROOT / "tests" / "replay"
NAV_TIMEOUT_MS = 5000
_MAX_DIAGNOSTICS = 20
_MAX_TEXT = 500


class Diagnostics:
    """Console errors and failed requests recorded during one load."""

    def __init__(self) -> None:
        self.console_errors: list[dict] = []
        self.failed_requests: list[dict] = []

    def clear(self) -> None:
        self.console_errors.clear()
        self.failed_requests.clear()

    def add_console(self, text: str) -> None:
        if len(self.console_errors) >= _MAX_DIAGNOSTICS:
            return
        self.console_errors.append({"type": "error", "text": text[:_MAX_TEXT]})

    def add_failed(self, url: str, method: str, error: str, status: int | None = None) -> None:
        if len(self.failed_requests) >= _MAX_DIAGNOSTICS:
            return
        item = {"url": url[:_MAX_TEXT], "method": method, "error": (error or "request failed")[:_MAX_TEXT]}
        if status is not None:
            item["status"] = status
        self.failed_requests.append(item)


class PageProbe:
    """One Playwright page. Listeners are attached before any navigation."""

    def __init__(self, *, headless: bool = True, cdp: str | None = None):
        self.session = BrowserSession(headless=headless, cdp=cdp)
        self.diagnostics = Diagnostics()
        self._attached = False

    def open(self):
        page = self.session.open()
        self._attach(page)
        return page

    def close(self) -> None:
        self.session.close()

    @property
    def page(self):
        if self.session.page is None:
            raise ActionError("The browser is not open.")
        return self.session.page

    def _attach(self, page) -> None:
        if self._attached:
            return

        def on_console(msg) -> None:
            if msg.type != "error":
                return
            self.diagnostics.add_console(msg.text)

        def on_request_failed(request) -> None:
            self.diagnostics.add_failed(
                request.url,
                request.method,
                request.failure or "request failed",
            )

        def on_response(response) -> None:
            if response.status != 404:
                return
            self.diagnostics.add_failed(
                response.url,
                response.request.method,
                "404",
                status=404,
            )

        page.on("console", on_console)
        page.on("requestfailed", on_request_failed)
        page.on("response", on_response)
        self._attached = True

    def open_url(self, url: str) -> dict:
        """Start: navigate to url. End: the load finished. No assertion and no model call."""
        opened = self._goto(url)
        return self._load_report(start_url=opened)

    def reload(self) -> dict:
        """Start: the current page. End: that page after reload. No assertion and no model call."""
        self.diagnostics.clear()
        try:
            self.page.reload(wait_until="load", timeout=NAV_TIMEOUT_MS)
        except Exception as exc:
            message = _short(exc)
            raise ActionError(f"reload failed: {message}") from exc
        return self._load_report(start_url=self.page.url)

    def console_errors(self) -> dict:
        return {"console_errors": list(self.diagnostics.console_errors), "model_calls": 0}

    def failed_requests(self) -> dict:
        return {"failed_requests": list(self.diagnostics.failed_requests), "model_calls": 0}

    def check_page(
        self,
        *,
        start_url: str | None = None,
        url: str | None = None,
        title: str | None = None,
        text: str | None = None,
        save: str | None = None,
        save_path: Path | None = None,
    ) -> dict:
        """Start: start_url, or the current page when start_url is blank.

        End: the url, title, and text assertions. Each one passes or fails.
        A console.error or a failed request (including a 404 asset) fails the check.
        """
        expect_url = _optional_text(url, "url")
        expect_title = _optional_text(title, "title")
        expect_text = _optional_text(text, "text")
        if expect_url is None and expect_title is None and expect_text is None:
            raise ActionError("check_page needs an end assertion: url, title, or text.")
        if start_url is not None and not isinstance(start_url, str):
            raise ActionError("start_url must be a string")
        given_start = start_url or ""
        opened = ""
        if given_start.strip():
            opened = self._goto(given_start)
        page = self.page
        end: dict = {}
        failures: list[str] = []
        if expect_url is not None:
            ok, detail = check(page, AssertUrl(expect_url))
            end["url"] = {"expect": expect_url, "ok": ok, "detail": detail}
            if not ok:
                failures.append(detail)
        if expect_title is not None:
            ok, detail = check(page, AssertTitle(expect_title))
            end["title"] = {"expect": expect_title, "ok": ok, "detail": detail}
            if not ok:
                failures.append(detail)
        if expect_text is not None:
            ok, detail = check(page, AssertText(expect_text))
            end["text"] = {"expect": expect_text, "ok": ok, "detail": detail}
            if not ok:
                failures.append(detail)
        if self.diagnostics.console_errors:
            failures.append("console error")
        if self.diagnostics.failed_requests:
            failures.append("failed request")
        passed = not failures
        result = {
            "ok": passed,
            "start": {"url": opened or _current_start(page.url)},
            "end": end,
            "page": {"url": page.url, "title": page.title()},
            "console_errors": list(self.diagnostics.console_errors),
            "failed_requests": list(self.diagnostics.failed_requests),
            "model_calls": 0,
            "reason": "passed" if passed else "; ".join(failures),
        }
        if save or save_path is not None:
            result.update(_maybe_save(result, given_start, expect_url, expect_title, expect_text, save, save_path))
        return result

    def _goto(self, url: str) -> str:
        target = resolve_url(url)
        self.diagnostics.clear()
        try:
            self.page.goto(target, wait_until="load", timeout=NAV_TIMEOUT_MS)
        except Exception as exc:
            message = _short(exc)
            raise ActionError(f"open {url} failed: {message}") from exc
        return target

    def _load_report(self, *, start_url: str) -> dict:
        page = self.page
        return {
            "loaded": True,
            "start": {"url": start_url},
            "end": {"url": page.url, "title": page.title()},
            "page": {"url": page.url, "title": page.title()},
            "console_errors": list(self.diagnostics.console_errors),
            "failed_requests": list(self.diagnostics.failed_requests),
            "model_calls": 0,
        }


def resolve_url(url: str) -> str:
    """Accept http(s), file, or a path relative to the repository."""
    if not isinstance(url, str) or not url.strip():
        raise ActionError("url is empty")
    text = url.strip()
    if "://" not in text and ":" in text and not text.startswith("/"):
        candidate = REPO_ROOT / text
        if not candidate.is_file():
            text = "http://" + text
    parsed = urlparse(text)
    if parsed.scheme in ("http", "https", "file"):
        return check_url(text)
    path = Path(text)
    if not path.is_absolute():
        path = REPO_ROOT / path
    path = path.resolve()
    if not path.is_file():
        raise ActionError(f"url is not a file: {url}")
    return path.as_uri()


def portable_start(url: str | None) -> str:
    """Store a spec start as a repo-relative path when the file lives in this repo."""
    if url is None:
        return ""
    text = str(url).strip()
    if not text:
        return ""
    parsed = urlparse(text)
    file_path: Path | None = None
    if parsed.scheme == "file":
        file_path = Path(unquote(parsed.path))
    elif parsed.scheme == "":
        file_path = Path(text)
        if not file_path.is_absolute():
            file_path = REPO_ROOT / file_path
    if file_path is None:
        return text
    try:
        return file_path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return text


def load_spec(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ActionError(f"Could not read spec {path.name}: {exc}") from exc
    if not isinstance(data, dict) or data.get("version") != 1:
        raise ActionError("spec version must be 1")
    start = data.get("start", {})
    end = data.get("end")
    if not isinstance(start, dict):
        raise ActionError("spec start must be an object with a url")
    if not isinstance(end, dict):
        raise ActionError("spec end must be an object")
    if not any(isinstance(end.get(key), str) and end.get(key).strip() for key in ("url", "title", "text")):
        raise ActionError("spec end needs a url, title, or text assertion")
    return data


def write_spec(path: Path, spec: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")


def replay_file(path: str | Path, *, probe: PageProbe | None = None) -> dict:
    """Replay a saved check. Start and end come from the file. Zero model calls."""
    spec_path = Path(path)
    spec = load_spec(spec_path)
    created: PageProbe | None = None
    if probe is None:
        created = PageProbe()
        try:
            created.open()
        except Exception:
            created.close()
            raise
        probe = created
    try:
        result = _run_spec(probe, spec)
    finally:
        if created is not None:
            created.close()
    result["spec"] = {"name": spec.get("name", ""), "file": spec_path.name}
    result["model_calls"] = 0
    return result


def spec_destination(file: str) -> Path:
    """A save target under tests/replay. Basename only."""
    if not isinstance(file, str) or not file.strip():
        raise ActionError("save needs a file name")
    name = Path(file.strip()).name
    if name != file.strip() and file.strip() not in {name, f"tests/replay/{name}"}:
        raise ActionError("save path must stay inside tests/replay")
    if not name.endswith(".json") or len(name) > 80 or not _safe_name(name):
        raise ActionError("save name must be a simple .json file name")
    return REPLAY_DIR / name


def _run_spec(probe: PageProbe, spec: dict) -> dict:
    start = spec.get("start") or {}
    end = spec["end"]
    start_url = start.get("url") if isinstance(start.get("url"), str) else ""
    return probe.check_page(
        start_url=start_url,
        url=end.get("url") if isinstance(end.get("url"), str) else None,
        title=end.get("title") if isinstance(end.get("title"), str) else None,
        text=end.get("text") if isinstance(end.get("text"), str) else None,
    )


def _maybe_save(result, given_start, expect_url, expect_title, expect_text, save, save_path) -> dict:
    if not result["ok"]:
        return {"saved": False, "save_error": "Only a passing check is saved."}
    path = save_path if save_path is not None else spec_destination(save)
    name = path.stem
    spec = {
        "version": 1,
        "name": name,
        "start": {"url": portable_start(given_start)},
        "end": {key: value for key, value in (("url", expect_url), ("title", expect_title), ("text", expect_text)) if value},
    }
    write_spec(path, spec)
    try:
        shown = path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        shown = path.name
    return {"saved": True, "file": shown}


def _optional_text(value: str | None, label: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ActionError(f"{label} must be a string")
    text = value.strip()
    return text or None


def _current_start(url: str) -> str:
    if not url or url == "about:blank":
        return ""
    return url


def _short(exc: Exception) -> str:
    return str(exc).split("\n", 1)[0][:300]


def _safe_name(name: str) -> bool:
    stem = name[: -len(".json")]
    if not stem:
        return False
    for char in stem:
        if not (char.isalnum() or char in "._-"):
            return False
    return True
