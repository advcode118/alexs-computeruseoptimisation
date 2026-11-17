"""Fetch only five Mind2Web train columns through projected HTTP-range Parquet reads.

The datasets-server rows API was probed but exposes actions/HTML with no column
projection. This optional data-preparation command requires pyarrow; the sampler
and benchmark do not. No test split, ZIP or HTML-bearing JSON file is requested.
"""

from __future__ import annotations

import hashlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

FIELDS = ("annotation_id", "confirmed_task", "website", "domain", "subdomain")
SERVER = "https://datasets-server.huggingface.co/parquet?dataset=osunlp/Mind2Web"
DEST = Path(__file__).parent / "ext_sources"


class RangeFile(io.RawIOBase):
    def __init__(self, url, size):
        self.url, self.size, self.position, self.bytes_read = url, size, 0, 0

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=0):
        self.position = offset + (self.position if whence == 1 else self.size if whence == 2 else 0)
        return self.position

    def read(self, size=-1):
        end = self.size if size < 0 else min(self.size, self.position + size)
        if end <= self.position:
            return b""
        request = Request(self.url, headers={"Range": f"bytes={self.position}-{end - 1}"})
        with urlopen(request, timeout=90) as response:
            expected = f"bytes {self.position}-{end - 1}/{self.size}"
            if response.status != 206 or response.headers.get("Content-Range") != expected:
                raise RuntimeError(f"Range read refused: {response.status}, {response.headers.get('Content-Range')}, expected {expected}")
            data = response.read(end - self.position)
        self.position = end
        self.bytes_read += len(data)
        return data


def main():
    import pyarrow.parquet as pq

    manifest = json.load(urlopen(SERVER, timeout=30))
    files = [entry for entry in manifest["parquet_files"] if entry["config"] == "default" and entry["split"] == "train"]
    rows, evidence = [], []
    for entry in files:
        source = RangeFile(entry["url"], entry["size"])
        table = pq.ParquetFile(source).read(columns=list(FIELDS), use_threads=False)
        rows.extend(table.to_pylist())
        evidence.append(dict(url=entry["url"], rows=table.num_rows, parquet_bytes=entry["size"], transferred_bytes=source.bytes_read))
        print(entry["filename"], table.num_rows, source.bytes_read, flush=True)
    assert rows and len({row["annotation_id"] for row in rows}) == len(rows)
    target = DEST / "mind2web_train_slim.jsonl"
    target.write_text("".join(json.dumps({field: row[field] for field in FIELDS}, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    provenance = dict(dataset="osunlp/Mind2Web", config="default", split="train", fields=FIELDS,
                      licence="CC-BY-4.0", downloaded_at=datetime.now(timezone.utc).isoformat(),
                      method="HTTP-range Parquet projection; rows API probe had no projection",
                      rows=len(rows), sha256=hashlib.sha256(target.read_bytes()).hexdigest(), shards=evidence)
    (DEST / "mind2web_train_provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    print(json.dumps({k: v for k, v in provenance.items() if k != "shards"}), flush=True)


if __name__ == "__main__":
    main()
