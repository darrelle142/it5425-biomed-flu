"""Tai thu muc data/ tu Hugging Face ve may (mac dinh DragonBornRay/FluDataset, doi bang --repo hoac HF_REPO).

Cach chay (tu thu muc goc cua repo):
    python scripts/download_data.py            # tai tat ca (khoang 500 MB)
    python scripts/download_data.py --samples  # chi tai bang da xu ly samples/ va reference/ (vai MB)
    python scripts/download_data.py --repo <user>/FluDataset   # tai tu repo khac (hoac dat bien HF_REPO)
    python scripts/download_data.py --revision v2026-11-14     # tai dung phien ban da gan tag (hoac ma commit)

Chi tai file moi hoac da thay doi; chay lai nhieu lan duoc.
Commit Hugging Face vua tai duoc ghi vao data/.hf_revision; upload_hf.py dung no de khong ghi de
nhung gi nguoi khac day len sau thoi diem tai.
"""
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from huggingface_hub import HfApi, snapshot_download  # noqa: E402

from fluwatch.ingest import hf  # noqa: E402
from fluwatch.ingest.paths import Paths  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--samples", action="store_true", help="chi tai samples/, reference/ va README")
ap.add_argument("--repo", default=os.environ.get("HF_REPO") or hf.MAIN_REPO,
                help="repo dataset tren Hugging Face (mac dinh: bien HF_REPO)")
ap.add_argument("--revision", default=None, help="tag (vd. v2026-11-14) hoac ma commit; mac dinh: ban moi nhat")
args = ap.parse_args()

paths = Paths(ROOT)
sha = HfApi().dataset_info(args.repo, revision=args.revision).sha
patterns = ["samples/*", "reference/*", "README.md"] if args.samples else None
path = snapshot_download(repo_id=args.repo, repo_type="dataset", revision=sha,
                         local_dir=paths.data, allow_patterns=patterns)
hf.write_revision(paths, args.repo, sha)
print(f"Da tai ve: {path} (commit {sha[:8]})")
