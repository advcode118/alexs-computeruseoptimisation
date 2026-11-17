"""Re-grade committed benchmark evidence without browsers, providers or network."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bench.regrade import build_report, discover, markdown, task_catalog


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = build_report(ROOT, discover(ROOT), task_catalog())
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "report.md").write_text(markdown(report), encoding="utf-8")
    (args.out / "regrade.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {args.out}/report.md and regrade.json ({len(report['sources'])} sources with arm rows)")


if __name__ == "__main__":
    main()
