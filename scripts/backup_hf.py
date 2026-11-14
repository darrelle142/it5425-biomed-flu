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
Logic: src/fluwatch/ingest/hf.py.
"""
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from huggingface_hub import CommitOperationAdd, HfApi  # noqa: E402

from fluwatch.ingest import hf  # noqa: E402
from fluwatch.ingest.paths import Paths  # noqa: E402

BATCH = 150  # so file moi commit


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backup-repo", default=os.environ.get("HF_BACKUP_REPO") or hf.BACKUP_REPO)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    paths = Paths(ROOT)
    src = HfApi(token=os.environ.get("HF_TOKEN") or None)
    dst = HfApi(token=os.environ.get("HF_BACKUP_TOKEN") or None)  # khong dat thi dung tai khoan da `hf auth login`
    try:
        repo, revision = hf.read_revision(paths)
        main_files, todo = hf.plan_backup(src, dst, paths, repo, revision, a.backup_repo)
    except hf.Refused as err:
        sys.exit(f"{err} Dung lai.")

    size = sum((paths.data / r).stat().st_size for r in todo)
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

    oid = None
    for i in range(0, len(todo), BATCH):
        part = todo[i:i + BATCH]
        ops = [CommitOperationAdd(path_in_repo=r, path_or_fileobj=str(paths.data / r)) for r in part]
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
    bad = [r for r in main_files if r not in backup or not hf.same_as_remote(backup[r], (paths.data / r).read_bytes())]
    if bad:
        sys.exit(f"Sau khi sao luu van con {len(bad)} file khac (vd. {bad[:3]}).")
    print(f"Sao luu xong: repo du phong giong ban chinh o {len(main_files)} file (commit {oid[:8]}).")


if __name__ == "__main__":
    main()
