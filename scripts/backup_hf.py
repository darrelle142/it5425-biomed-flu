"""Sao luu repo du lieu chinh sang repo du phong rieng tu tren Hugging Face.

Cach chay (tu thu muc goc cua repo, sau download_data.py hoac sau khi vua day len bang upload_hf.py):
    python scripts/backup_hf.py --dry-run    # chi liet ke nhung gi se sao luu
    python scripts/backup_hf.py

Bien moi truong:
    HF_TOKEN          doc repo chinh (repo public nen co the bo trong)
    HF_BACKUP_TOKEN   ghi repo du phong (token fine-grained chi co quyen tren repo du phong)
    HF_BACKUP_REPO    mac dinh DragonBornRay/FluDataset-backup

Quy tac:
- Sao luu dung ban cua repo chinh o commit da tai (data/.hf_revision), doc file tu ban tren may
  (ban nay da duoc verify_integrity.py doi chieu voi Hugging Face).
- File raw/ chi duoc them: neu repo du phong da co file cung duong dan ma noi dung khac thi dung lai.
- manifest, samples/, reference/, README duoc cap nhat khi thay doi.
- Cac tag cua repo chinh tro toi commit nay duoc gan lai tren repo du phong (cung ten).
- Lan dau sao luu toan bo (~500 MB) thanh nhieu commit nho; cac tuan sau chi vai chuc MB.
"""
import argparse
import hashlib
import os
import sys
from pathlib import Path

from huggingface_hub import CommitOperationAdd, HfApi

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
BATCH = 150  # so file moi commit


def sha256(b):
    return hashlib.sha256(b).hexdigest()


def git_blob_sha1(b):
    return hashlib.sha1(b"blob %d\0" % len(b) + b).hexdigest()


def same(sibling, b):
    return sibling.lfs.sha256 == sha256(b) if sibling.lfs else sibling.blob_id == git_blob_sha1(b)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backup-repo", default=os.environ.get("HF_BACKUP_REPO") or "DragonBornRay/FluDataset-backup")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    repo, revision = (DATA / ".hf_revision").read_text(encoding="utf-8").split()
    src = HfApi(token=os.environ.get("HF_TOKEN") or None)
    dst = HfApi(token=os.environ.get("HF_BACKUP_TOKEN") or None)  # khong dat thi dung tai khoan da `hf auth login`

    main_files = [s.rfilename for s in src.dataset_info(repo, revision=revision).siblings]
    backup = {s.rfilename: s for s in dst.dataset_info(a.backup_repo, files_metadata=True).siblings}

    todo, conflicts = [], []
    for rel in main_files:
        p = DATA / rel
        if not p.exists():
            sys.exit(f"Thieu {rel} tren may: chay download_data.py (ban day du) truoc khi sao luu.")
        b = p.read_bytes()
        s = backup.get(rel)
        if s is None:
            todo.append(rel)
        elif not same(s, b):
            (conflicts if rel.startswith("raw/") and rel != "raw/manifest.jsonl" else todo).append(rel)
    if conflicts:
        sys.exit(f"Repo du phong co {len(conflicts)} file raw/ khac ban chinh (vd. {conflicts[:3]}); khong ghi de. Dung lai.")

    size = sum((DATA / r).stat().st_size for r in todo)
    print(f"Sao luu {repo}@{revision[:8]} -> {a.backup_repo}: {len(todo)} file ({size / 1e6:.1f} MB) "
          f"trong tong {len(main_files)} file")
    for rel in todo[:15]:
        print("  ", rel)
    if len(todo) > 15:
        print(f"   ... va {len(todo) - 15} file khac")
    tags = [t for t in src.list_repo_refs(repo, repo_type="dataset").tags if t.target_commit == revision]
    if a.dry_run:
        print("(dry-run) khong ghi gi. Tag se gan:", [t.name for t in tags])
        return

    # manifest day len sau cung: repo du phong luon co du file ma manifest cua no ghi
    todo.sort(key=lambda r: r == "raw/manifest.jsonl")
    oid = None
    for i in range(0, len(todo), BATCH):
        part = todo[i:i + BATCH]
        ops = [CommitOperationAdd(path_in_repo=r, path_or_fileobj=str(DATA / r)) for r in part]
        c = dst.create_commit(a.backup_repo, ops, repo_type="dataset",
                              commit_message=f"Sao luu {repo}@{revision[:8]} ({i // BATCH + 1}/{-(-len(todo) // BATCH)})")
        oid = c.oid
        print(f"  da day {i + len(part)}/{len(todo)} file")
    if oid is None:
        oid = dst.dataset_info(a.backup_repo).sha
        print("Repo du phong da giong ban chinh, khong can day.")

    have = {t.name for t in dst.list_repo_refs(a.backup_repo, repo_type="dataset").tags}
    for t in tags:
        if t.name not in have:
            dst.create_tag(a.backup_repo, tag=t.name, revision=oid, repo_type="dataset",
                           tag_message=f"Ban sao cua {repo} tag {t.name} ({revision[:8]})")
            print(f"Da gan tag {t.name} tren repo du phong")

    # Doi chieu lai sau khi sao luu
    backup = {s.rfilename: s for s in dst.dataset_info(a.backup_repo, revision=oid, files_metadata=True).siblings}
    bad = [r for r in main_files if r not in backup or not same(backup[r], (DATA / r).read_bytes())]
    if bad:
        sys.exit(f"Sau khi sao luu van con {len(bad)} file khac (vd. {bad[:3]}).")
    print(f"Sao luu xong: repo du phong giong ban chinh o {len(main_files)} file (commit {oid[:8]}).")


if __name__ == "__main__":
    main()
