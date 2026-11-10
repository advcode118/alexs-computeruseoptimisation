#!/usr/bin/env bash
# Install the Python package (with dev extras) and Playwright's browsers.
# Safe to re-run. Does not read or write API keys.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

if command -v python3 >/dev/null 2>&1; then
  py=python3
elif command -v python >/dev/null 2>&1; then
  py=python
else
  echo "python3 is not on PATH" >&2
  exit 1
fi

if [[ ! -x .venv/bin/python ]]; then
  rm -rf .venv
  if ! "$py" -m venv .venv; then
    rm -rf .venv
    if command -v sudo >/dev/null 2>&1 && sudo -n true >/dev/null 2>&1 && command -v apt-get >/dev/null 2>&1; then
      sudo apt-get update
      sudo apt-get install -y python3-venv
      "$py" -m venv .venv
    else
      echo "python venv module is missing; install python3-venv" >&2
      exit 1
    fi
  fi
fi
# shellcheck disable=SC1091
source .venv/bin/activate

python -m pip install -e ".[dev]"

if command -v sudo >/dev/null 2>&1 && sudo -n true >/dev/null 2>&1; then
  python -m playwright install --with-deps
else
  python -m playwright install
fi
