"""One serial gated checkpoint. Invoke through the owner's slot wrapper."""
import subprocess
import sys
from pathlib import Path

root = Path(__file__).parent


def run(*args):
    subprocess.run([sys.executable, *map(str, args)], check=True)


for attempt in (3, 4):
    output = root / f"author_attempt{attempt}.jsonl"
    assert not output.exists(), f"refuse to overwrite {output}"
    run("-m", "bench.verify_dev4_search", "--output", output)
run(root / "run_safe_suite.py")
for split, mode, label, kind in (
    ("dev3", "off", "dev3_off1", "search"),
    ("dev3", "on", "dev3_on1", "search"),
    ("dev4search", "off", "dev4search_off1", "search"),
    ("dev4search", "on", "dev4search_on1", "search"),
    ("heldout2", "off", "heldout2_off1", ""),
    ("heldout2", "on", "heldout2_on1", ""),
    ("held-out", "off", "heldout_off1", ""),
    ("held-out", "on", "heldout_on1", ""),
):
    run(root / "run_probe.py", split, mode, label, "--kind", kind)
run(root / "summarize.py")
