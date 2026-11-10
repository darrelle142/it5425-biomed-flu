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
Ket qua ghi vao data/samples/integrity_results.json.
"""
import argparse
import gzip
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW = DATA / "raw"


def sha256(b):
    return hashlib.sha256(b).hexdigest()


def git_blob_sha1(b):
    return hashlib.sha1(b"blob %d\0" % len(b) + b).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--local", action="store_true", help="khong so voi Hugging Face")
    a = ap.parse_args()

    lines = [json.loads(x) for x in (RAW / "manifest.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    logged = {}  # duong dan -> moi dong manifest tro toi no
    for m in lines:
        if m.get("file"):
            logged.setdefault(m["file"].removeprefix("data/"), []).append(m)
    problems = {"thieu_file": [], "sha_lech": [], "file_la": [], "khac_hf": [], "chi_co_tren_hf": [], "chi_co_tren_may": []}
    # Canh bao (khong tinh la loi): mot duong dan duoc tai nhieu lan trong cung ngay; file giu ban dau tien
    # (Hugging Face khong ghi de), cac lan tai sau khong duoc luu. Loi nay da sua ngay 10/11/2026.
    warnings = {"tai_lai_khong_luu": []}

    # 1. Manifest -> file tren may
    for rel, ms in logged.items():
        p = DATA / rel
        if not p.exists():
            problems["thieu_file"].append(rel)
            continue
        shas = [m["sha256"] for m in ms if m.get("sha256")]
        if not shas:
            continue
        b = p.read_bytes()
        got = {sha256(b)} | ({sha256(gzip.decompress(b))} if p.suffix == ".gz" else set())
        if not got & set(shas):
            problems["sha_lech"].append(rel)
        elif len(shas) > 1:
            warnings["tai_lai_khong_luu"].append(rel)

    # 2. File tren may -> manifest
    on_disk = sorted(p.relative_to(DATA).as_posix() for p in RAW.glob("*/*/*") if p.is_file())
    problems["file_la"] = [rel for rel in on_disk if rel not in logged]

    # 3. Ban tren may <-> Hugging Face
    revision = None
    if not a.local:
        from huggingface_hub import HfApi
        repo, revision = (DATA / ".hf_revision").read_text(encoding="utf-8").split()
        info = HfApi(token=os.environ.get("HF_TOKEN") or None).dataset_info(repo, revision=revision, files_metadata=True)
        remote = {s.rfilename: s for s in info.siblings if s.rfilename.startswith("raw/")}
        local = set(on_disk) | {"raw/manifest.jsonl"} | {p.relative_to(DATA).as_posix() for p in RAW.glob("*.json")}
        problems["chi_co_tren_hf"] = sorted(set(remote) - local)
        problems["chi_co_tren_may"] = sorted(local - set(remote))
        for rel in sorted(local & set(remote)):
            b = (DATA / rel).read_bytes()
            s = remote[rel]
            same = s.lfs.sha256 == sha256(b) if s.lfs else s.blob_id == git_blob_sha1(b)
            if not same:
                problems["khac_hf"].append(rel)

    summary = {"revision": revision, "manifest_lines": len(lines), "files_logged": len(logged),
               "files_on_disk": len(on_disk), **{k: len(v) for k, v in problems.items()},
               **{f"canh_bao_{k}": len(v) for k, v in warnings.items()}}
    out = {"summary": summary, "problems": problems, "warnings": warnings}
    (DATA / "samples").mkdir(exist_ok=True)
    (DATA / "samples" / "integrity_results.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    for k, v in warnings.items():
        if v:
            print(f"CANH BAO {k}: {len(v)} file, vi du {v[:3]}")
    bad = {k: v for k, v in problems.items() if v}
    for k, v in bad.items():
        print(f"LOI {k}: {len(v)} file, vi du {v[:5]}")
    if bad:
        sys.exit(1)
    print("Toan ven: OK")


if __name__ == "__main__":
    main()
