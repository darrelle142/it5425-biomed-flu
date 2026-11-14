"""Day phan du lieu moi tren may len Hugging Face trong mot commit.

Cach chay (tu thu muc goc cua repo, can bien HF_TOKEN co quyen write hoac da `hf auth login`):
    python scripts/upload_hf.py --dry-run              # chi liet ke nhung gi se day
    python scripts/upload_hf.py -m "Cap nhat tuan ..."
    python scripts/upload_hf.py -m "..." --tag    # them tag phien ban vYYYY-MM-DD (UTC) cho commit vua day

Day len:
- file trong raw/ ma manifest tren may co nhung tren Hugging Face chua co (khong bao gio sua file cu);
- raw/manifest.jsonl, samples/*.csv(.gz), reference/*.csv, README.md neu noi dung khac ban tren HF.
Khong day: samples/preview_*, samples/*_results.json, sandbox/, .cache/.

Bao toan du lieu tho:
- Manifest tren may phai bat dau bang dung toan bo manifest tren HF (chi them dong, khong sua, khong xoa).
- Commit dua tren commit da tai (data/.hf_revision); neu co nguoi day len chen giua thi HF tu choi,
  khong ghi de. Khi do tai lai (download_data.py), chay lai pipeline roi day.
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=os.environ.get("HF_REPO") or hf.MAIN_REPO)
    ap.add_argument("-m", "--message", default="Cap nhat du lieu")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--tag", action="store_true", help="gan tag vYYYY-MM-DD cho commit vua day (trung thi them -2, -3...)")
    a = ap.parse_args()
    token = os.environ.get("HF_TOKEN") or None
    api = HfApi(token=token)
    paths = Paths(ROOT)

    try:
        repo, parent = hf.read_revision(paths)
        if repo.lower() != a.repo.lower():
            raise hf.Refused(f"data/ duoc tai tu {repo}, khong phai {a.repo}.")
        n_new, listed = hf.plan_upload(api, paths, a.repo, parent, token)
    except hf.Refused as err:
        sys.exit(f"{err} Dung lai.")

    print(f"Repo {a.repo}, dua tren commit {parent[:8]}; {n_new} dong manifest moi; {len(listed)} file:")
    for rel in listed:
        print("  ", rel)
    if not listed:
        print("Khong co gi moi de day.")
        return
    if a.dry_run:
        print("(dry-run) khong day.")
        return
    ops = [CommitOperationAdd(path_in_repo=rel, path_or_fileobj=str(paths.data / rel)) for rel in listed]
    c = api.create_commit(a.repo, ops, commit_message=a.message, repo_type="dataset", parent_commit=parent)
    hf.write_revision(paths, a.repo, c.oid)
    print("Da day:", c.commit_url)
    if a.tag:
        try:  # du lieu da len HF; loi gan tag chi canh bao, gan lai tay duoc
            print(f"Da gan tag {hf.tag_version(api, a.repo, c.oid, a.message)} cho commit {c.oid[:8]}")
        except Exception as err:
            print(f"CANH BAO: khong gan duoc tag cho {c.oid[:8]}: {err}")


if __name__ == "__main__":
    main()
