"""Ghi cac file tai tay vao data/raw/manifest.jsonl. Chay sau moi lan tai tay.

Cach dung:
    1. Luu file vao data/raw/<nguon>/<YYYY-MM-DD>/ (nguon: cdc_wastewater_wval, cdc_fluvax_coverage,
       census_gazetteer, ...), giu nguyen ten file CDC dat.
    2. python scripts/register_manual.py --by "Ten nguoi tai"

File nao da co trong manifest thi bo qua, nen chay lai nhieu lan khong sao.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
MANIFEST = RAW / "manifest.jsonl"
MANUAL = ["cdc_wastewater_wval", "cdc_fluvax_coverage", "cdc_nhsn_hrd", "cdc_nhsn_levels",
          "census_popest_state", "census_popest_places", "census_gazetteer"]

ap = argparse.ArgumentParser()
ap.add_argument("--by", required=True, help="nguoi tai file")
ap.add_argument("--url", default=None, help="link da dung de tai (neu co)")
a = ap.parse_args()

seen = {json.loads(line).get("file") for line in MANIFEST.read_text(encoding="utf-8").splitlines() if line.strip()}
n = 0
with MANIFEST.open("a", encoding="utf-8") as fh:
    for src in MANUAL:
        for p in sorted((RAW / src).glob("*/*")):
            rel = str(p.relative_to(ROOT)).replace("\\", "/")
            if not p.is_file() or rel in seen:
                continue
            b = p.read_bytes()
            fh.write(json.dumps({"source": src, "file": rel, "url": a.url, "fetched_at": p.parent.name,
                                 "http_status": "manual", "bytes": len(b), "sha256": hashlib.sha256(b).hexdigest(),
                                 "note": f"Tai tay boi {a.by}"}, ensure_ascii=False) + "\n")
            print("da ghi", rel)
            n += 1
print(f"{n} file moi duoc ghi vao manifest")
