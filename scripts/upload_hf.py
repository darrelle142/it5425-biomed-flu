"""Day phan du lieu moi tren may len Hugging Face trong mot commit.

Cach chay (tu thu muc goc cua repo, can bien HF_TOKEN co quyen write hoac da `hf auth login`):
    python scripts/upload_hf.py --dry-run              # chi liet ke nhung gi se day
    python scripts/upload_hf.py -m "Cap nhat tuan ..."

Day len:
- file trong raw/ ma manifest tren may co nhung tren Hugging Face chua co (khong bao gio sua file cu);
- raw/manifest.jsonl, samples/*.csv(.gz), reference/*.csv, README.md neu noi dung khac ban tren HF.
Khong day: samples/preview_*, samples/*_results.json, sandbox/, .cache/.

Bao toan du lieu tho:
- Manifest tren may phai bat dau bang dung toan bo manifest tren HF (chi them dong, khong sua, khong xoa).
- Commit dua tren commit da tai (data/.hf_revision); neu co nguoi day len chen giua thi HF tu choi,
  khong ghi de. Khi do tai lai (download_data.py), chay lai pipeline roi day.
"""
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

from huggingface_hub import CommitOperationAdd, HfApi, hf_hub_download

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
MANIFEST = "raw/manifest.jsonl"
SKIP = ("samples/preview_",)


def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def git_blob_sha1(p):  # file nho (khong qua LFS) duoc HF dinh danh bang sha1 kieu git
    b = Path(p).read_bytes()
    return hashlib.sha1(b"blob %d\0" % len(b) + b).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=os.environ.get("HF_REPO") or "DragonBornRay/FluDataset")
    ap.add_argument("-m", "--message", default="Cap nhat du lieu")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    token = os.environ.get("HF_TOKEN") or None
    api = HfApi(token=token)

    rev_file = DATA / ".hf_revision"
    if not rev_file.exists():
        sys.exit("Thieu data/.hf_revision: chay scripts/download_data.py truoc de biet ban HF goc.")
    repo, parent = rev_file.read_text(encoding="utf-8").split()
    if repo.lower() != a.repo.lower():
        sys.exit(f"data/ duoc tai tu {repo}, khong phai {a.repo}.")

    # 1. Manifest chi duoc them dong
    remote_manifest = hf_hub_download(a.repo, MANIFEST, repo_type="dataset", revision=parent, token=token)
    rem = Path(remote_manifest).read_text(encoding="utf-8").splitlines()
    loc = (DATA / MANIFEST).read_text(encoding="utf-8").splitlines()
    if loc[:len(rem)] != rem:
        sys.exit("manifest tren may khong bat dau bang manifest tren HF (co dong bi sua hoac xoa). Dung lai.")
    new_lines = [json.loads(x) for x in loc[len(rem):] if x.strip()]

    # 2. File raw moi: co trong cac dong manifest moi, chua co tren HF
    info = api.dataset_info(a.repo, revision=parent, files_metadata=True)
    remote = {s.rfilename: s for s in info.siblings}
    ops, listed = [], []
    for m in new_lines:
        rel = (m.get("file") or "").removeprefix("data/")
        if not rel or rel in remote or rel in listed:
            continue
        if not (DATA / rel).exists():
            sys.exit(f"manifest ghi {rel} nhung file khong co tren may.")
        listed.append(rel)

    # 3. Bang da xu ly, tra cuu, the du lieu: day neu khac ban tren HF
    for p in [*sorted((DATA / "samples").glob("*.csv*")), *sorted((DATA / "reference").glob("*.csv")),
              DATA / "README.md"]:
        rel = p.relative_to(DATA).as_posix()
        if rel.startswith(SKIP):
            continue
        r = remote.get(rel)
        r_sha = r.lfs.sha256 if r is not None and r.lfs else None
        if r is None or (r_sha and r_sha != sha256(p)) or (not r_sha and r.blob_id != git_blob_sha1(p)):
            listed.append(rel)
    if new_lines:
        listed.append(MANIFEST)

    print(f"Repo {a.repo}, dua tren commit {parent[:8]}; {len(new_lines)} dong manifest moi; {len(listed)} file:")
    for rel in listed:
        print("  ", rel)
    if not listed:
        print("Khong co gi moi de day.")
        return
    if a.dry_run:
        print("(dry-run) khong day.")
        return
    ops = [CommitOperationAdd(path_in_repo=rel, path_or_fileobj=str(DATA / rel)) for rel in listed]
    c = api.create_commit(a.repo, ops, commit_message=a.message, repo_type="dataset", parent_commit=parent)
    rev_file.write_text(f"{a.repo} {c.oid}\n", encoding="utf-8")
    print("Da day:", c.commit_url)


if __name__ == "__main__":
    main()
