"""Settings shared by playwright_mcp, script_first, stagehand, and browser_use.

Where those arms differed, the longer timeout is the one they all use, and
the browser is Google Chrome. The model string is whatever the probe was
given. The page-text read is one function and one call.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

# AnthropicClient and the OpenAI client already wait this long. browser-use's
# cell timeout is the same 120s. Its Chat classes reject a timeout argument,
# so the Claude and OpenAI constructors stay model plus api_key.
MODEL_HTTP_TIMEOUT_S = 120
# @playwright/mcp@0.0.84 waits 60s to navigate. script_first waited 10s.
# stagehand used Playwright's 30s default. The shared navigation wait is 60s.
NAV_TIMEOUT_MS = 60_000
# stagehand used Playwright's 30s default. script_first and Playwright MCP
# waited 5s. The shared action wait is 30s.
ACTION_TIMEOUT_MS = 30_000
# Playwright's default. script_first stopped an evaluate at 5s, and the
# browser-use tab read stopped at 5s.
EVALUATE_TIMEOUT_S = 30
# stagehand's settle cap. script_first stopped the landing read at 0.8s.
# Playwright MCP's settle default is 0.5s.
SETTLE_TIMEOUT_MS = 3_000
LAND_TIMEOUT_S = SETTLE_TIMEOUT_MS / 1000
PAGE_READ_TIMEOUT_S = EVALUATE_TIMEOUT_S
# browser-use Agent.run defaults to 1700s. playwright_mcp and stagehand have
# no run cap and allow 30 steps. Thirty steps at the 120s model wait is longer
# than 1700s. script_first keeps its own call cap; that cap is not a timeout.
ARM_RUN_TIMEOUT_S = 30 * MODEL_HTTP_TIMEOUT_S

# Fresh Google Chrome, not a cloud browser and not the user's open profile.
# Playwright asks for it with channel "chrome" and --browser chrome.
# browser-use's fresh-profile kind is the string "chromium"; that launcher
# is pointed at this same Chrome executable when one is installed.
BROWSER = "chrome"


def chrome_launch_attempts(headless: bool) -> tuple[dict, ...]:
    """Google Chrome, then bundled Chromium if Chrome will not launch."""
    return (
        {"channel": BROWSER, "headless": headless},
        {"headless": headless},
    )


def apply_page_timeouts(page) -> None:
    """The shared action and navigation waits, on a Playwright page."""
    action = getattr(page, "set_default_timeout", None)
    if callable(action):
        action(ACTION_TIMEOUT_MS)
    navigation = getattr(page, "set_default_navigation_timeout", None)
    if callable(navigation):
        navigation(NAV_TIMEOUT_MS)


def google_chrome_executable() -> str | None:
    """The Google Chrome binary Playwright's chrome channel launches, if it is installed."""
    env = os.environ.get("CHROME_PATH", "").strip()
    candidates: list[str] = [env] if env else []
    if sys.platform == "darwin":
        candidates.extend(
            [
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                str(Path.home() / "Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
            ]
        )
    elif sys.platform == "win32":
        for key in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
            root = os.environ.get(key, "").strip()
            if root:
                candidates.append(str(Path(root) / "Google" / "Chrome" / "Application" / "chrome.exe"))
    else:
        for name in ("google-chrome-stable", "google-chrome", "chrome"):
            found = shutil.which(name)
            if found:
                candidates.append(found)
        candidates.extend(
            [
                "/opt/google/chrome/chrome",
                "/usr/bin/google-chrome-stable",
                "/usr/bin/google-chrome",
            ]
        )
    for path in candidates:
        if path and Path(path).is_file():
            return path
    return None
