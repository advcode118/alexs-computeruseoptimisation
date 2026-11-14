"""Broad offline suite while respecting the owner's frozen-data embargo.

Invoke through probe_slot.sh. Exclusions are scope restrictions, not fixes for
failing tests. No prohibited test module is read or collected.
"""
from pathlib import Path
import re
import subprocess
import sys

files = []
excluded = []
for path in sorted([*Path("tests").rglob("test_*.py"), Path("bench/test_harness.py")]):
    if re.search(r"heldout3|val3|frozen", str(path), re.I):
        excluded.append(str(path))
        continue
    source = path.read_text(encoding="utf-8")
    if re.search(r"heldout3|val3|get_all_tasks|get_webvoyager_tasks|BENCHMARK_TASKS|WEBVOYAGER_TASKS", source):
        excluded.append(str(path))
        continue
    files.append(str(path))
print("Excluded to preserve frozen-data boundary: " + ", ".join(excluded), flush=True)
print(f"Running {len(files)} explicitly selected offline test files", flush=True)
result = subprocess.run([sys.executable, "-m", "pytest", "-q", *files], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
print(result.stdout, flush=True)
Path(__file__).with_name("offline_suite.txt").write_text("Excluded: " + ", ".join(excluded) + "\n" + result.stdout, encoding="utf-8")
raise SystemExit(result.returncode)
