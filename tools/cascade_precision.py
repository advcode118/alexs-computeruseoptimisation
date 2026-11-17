"""Reproduce the saved-row cascade precision report without network or models."""

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bench.cascade_precision import build_report, markdown


if __name__ == "__main__":
    report = build_report(ROOT)
    out = ROOT / "docs/results/cascade_selfcheck_20261117"
    out.mkdir(parents=True, exist_ok=True)
    (out / "precision.json").write_text(json.dumps(report, indent=2) + "\n")
    (out / "report.md").write_text(markdown(report))
    print(markdown(report))
