"""Tai thu muc data/ tu Hugging Face (DragonBornRay/FluDataset) ve may.

Cach chay (tu thu muc goc cua repo):
    python scripts/download_data.py            # tai tat ca (khoang 290 MB)
    python scripts/download_data.py --samples  # chi tai bang da xu ly samples/ va reference/ (vai MB)

Chi tai file moi hoac da thay doi; chay lai nhieu lan duoc.
"""
import argparse
from pathlib import Path

from huggingface_hub import snapshot_download

ROOT = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser()
ap.add_argument("--samples", action="store_true", help="chi tai samples/, reference/ va README")
args = ap.parse_args()

patterns = ["samples/*", "reference/*", "README.md"] if args.samples else None
path = snapshot_download(repo_id="DragonBornRay/FluDataset", repo_type="dataset",
                         local_dir=ROOT / "data", allow_patterns=patterns)
print("Da tai ve:", path)
