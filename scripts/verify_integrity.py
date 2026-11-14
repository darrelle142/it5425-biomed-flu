"""Kiem tra toan ven du lieu tho: manifest <-> file tren may <-> file tren Hugging Face.

Cach chay (tu thu muc goc cua repo, sau scripts/download_data.py):
    python scripts/verify_integrity.py            # kiem tra, thoat ma 1 neu co loi
    python scripts/verify_integrity.py --local    # chi kiem tra manifest voi file tren may (khong goi HF)

Ba lop kiem tra:
1. Moi dong manifest co file: file ton tai tren may va sha256 khop. Manifest ghi sha cua noi dung goc,
   nen file .gz duoc giai nen truoc khi so (file tai tay .zip/.xlsx/.csv so nguyen trang).
2. Moi file trong raw/ deu co trong manifest (khong co file "la" ai do tu them vao).
3. Ban tren may giong het ban tren Hugging Face o commit da tai (data/.hf_revision): cung danh sach file
   raw/, cung sha256 (file LFS) hoac cung git blob sha1 (file nho).
Ket qua ghi vao data/samples/integrity_results.json. Logic: src/fluwatch/ingest/integrity.py.
"""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fluwatch.ingest.integrity import verify, write_report  # noqa: E402
from fluwatch.ingest.paths import Paths  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--local", action="store_true", help="khong so voi Hugging Face")
    a = ap.parse_args()

    paths = Paths(ROOT)
    result = verify(paths, remote=not a.local, token=os.environ.get("HF_TOKEN") or None)
    write_report(paths, result)
    print(json.dumps(result["summary"], ensure_ascii=False, indent=1))
    for k, v in result["warnings"].items():
        if v:
            print(f"CANH BAO {k}: {len(v)} file, vi du {v[:3]}")
    bad = {k: v for k, v in result["problems"].items() if v}
    for k, v in bad.items():
        print(f"LOI {k}: {len(v)} file, vi du {v[:5]}")
    if bad:
        sys.exit(1)
    print("Toan ven: OK")


if __name__ == "__main__":
    main()
