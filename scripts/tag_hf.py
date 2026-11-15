"""Gan tag dat ten rieng cho ban hien tai tren Hugging Face (vd. khoa so lieu), ca repo chinh lan repo du phong.

Cach chay (tu thu muc goc cua repo):
    python scripts/download_data.py                            # ban tren may = ban moi nhat tren HF
    python scripts/tag_hf.py v2026-11-19 -m "Khoa so lieu 19/11/2026 18:00"

- Chi gan khi data/ tren may dung la ban moi nhat cua repo chinh (de tag tro dung ban moi nguoi dang dung).
- Ten tag da co thi tu choi (khong di chuyen tag cu).
- Sau khi gan o repo chinh, chay backup_hf.py: sao luu ban nay (neu chua) va gan cung tag o repo du phong.
Moi nguoi lay dung ban da khoa bang: python scripts/download_data.py --revision v2026-11-19
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from huggingface_hub import HfApi  # noqa: E402

from fluwatch.ingest import hf  # noqa: E402
from fluwatch.ingest.paths import Paths  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name", help="ten tag, vd. v2026-11-19")
    ap.add_argument("-m", "--message", required=True)
    ap.add_argument("--no-backup", action="store_true", help="khong chay backup_hf.py sau khi gan tag")
    a = ap.parse_args()
    api = HfApi(token=os.environ.get("HF_TOKEN") or None)
    paths = Paths(ROOT)
    try:
        repo, revision = hf.read_revision(paths)
        head = api.dataset_info(repo).sha
        if head != revision:
            raise hf.Refused(f"Ban tren may ({revision[:8]}) khac ban moi nhat cua {repo} ({head[:8]}): "
                             "chay scripts/download_data.py truoc.")
        hf.tag_version(api, repo, head, a.message, name=a.name)
    except hf.Refused as err:
        sys.exit(f"{err} Dung lai.")
    print(f"Da gan tag {a.name} cho {repo}@{head[:8]}")
    if not a.no_backup:
        sys.exit(subprocess.run([sys.executable, str(ROOT / "scripts" / "backup_hf.py")], cwd=ROOT).returncode)


if __name__ == "__main__":
    main()
