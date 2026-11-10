"""Tai thu muc data/ tu Hugging Face ve may (mac dinh DragonBornRay/FluDataset, doi bang --repo hoac HF_REPO).

Cach chay (tu thu muc goc cua repo):
    python scripts/download_data.py            # tai tat ca (khoang 300 MB)
    python scripts/download_data.py --samples  # chi tai bang da xu ly samples/ va reference/ (vai MB)
    python scripts/download_data.py --repo <user>/FluDataset   # tai tu repo khac (hoac dat bien HF_REPO)
    python scripts/download_data.py --revision v2026-11-14     # tai dung phien ban da gan tag (hoac ma commit)

Chi tai file moi hoac da thay doi; chay lai nhieu lan duoc.
Commit Hugging Face vua tai duoc ghi vao data/.hf_revision; upload_hf.py dung no de khong ghi de
nhung gi nguoi khac day len sau thoi diem tai.
"""
import argparse
import os
from pathlib import Path

from huggingface_hub import HfApi, snapshot_download

ROOT = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser()
ap.add_argument("--samples", action="store_true", help="chi tai samples/, reference/ va README")
ap.add_argument("--repo", default=os.environ.get("HF_REPO") or "DragonBornRay/FluDataset",
                help="repo dataset tren Hugging Face (mac dinh: bien HF_REPO)")
ap.add_argument("--revision", default=None, help="tag (vd. v2026-11-14) hoac ma commit; mac dinh: ban moi nhat")
args = ap.parse_args()

sha = HfApi().dataset_info(args.repo, revision=args.revision).sha
patterns = ["samples/*", "reference/*", "README.md"] if args.samples else None
path = snapshot_download(repo_id=args.repo, repo_type="dataset", revision=sha,
                         local_dir=ROOT / "data", allow_patterns=patterns)
(ROOT / "data" / ".hf_revision").write_text(f"{args.repo} {sha}\n", encoding="utf-8")
print(f"Da tai ve: {path} (commit {sha[:8]})")
