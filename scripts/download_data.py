"""Tai thu muc data/ tu Hugging Face ve may (mac dinh tdu175/FluDataset, doi bang --repo hoac HF_REPO).

Cach chay (tu thu muc goc cua repo):
    python scripts/download_data.py            # tai tat ca (khoang 290 MB)
    python scripts/download_data.py --samples  # chi tai bang da xu ly samples/ va reference/ (vai MB)
    python scripts/download_data.py --repo <user>/FluDataset   # tai tu repo khac (hoac dat bien HF_REPO)

Chi tai file moi hoac da thay doi; chay lai nhieu lan duoc.
"""
import argparse
import os
from pathlib import Path

from huggingface_hub import snapshot_download

ROOT = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser()
ap.add_argument("--samples", action="store_true", help="chi tai samples/, reference/ va README")
ap.add_argument("--repo", default=os.environ.get("HF_REPO") or "tdu175/FluDataset",
                help="repo dataset tren Hugging Face (mac dinh: bien HF_REPO)")
args = ap.parse_args()

patterns = ["samples/*", "reference/*", "README.md"] if args.samples else None
path = snapshot_download(repo_id=args.repo, repo_type="dataset",
                         local_dir=ROOT / "data", allow_patterns=patterns)
print("Da tai ve:", path)
