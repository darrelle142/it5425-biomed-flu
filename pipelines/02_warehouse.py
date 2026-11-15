"""TV2: kho du lieu. Mot lenh chay toan bo phan cua TV2.

    python pipelines/02_warehouse.py                          # moi buoc: clean -> business -> olap
    python pipelines/02_warehouse.py --steps clean            # chi dung data/clean/
    python pipelines/02_warehouse.py --steps clean --tables ilinet weather   # dung lai vai bang clean/
    python pipelines/02_warehouse.py --steps business olap    # dung lai star schema + DuckDB tu clean/ co san

Can data/raw/ (python scripts/download_data.py). Chay tu thu muc goc repo.
"""
import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fluwatch.ingest.paths import Paths  # noqa: E402
from fluwatch.warehouse.business import build_business  # noqa: E402
from fluwatch.warehouse.clean import TABLES, build_clean  # noqa: E402
from fluwatch.warehouse.olap import build_duckdb, run_examples  # noqa: E402

STEPS = ["clean", "business", "olap"]

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--steps", nargs="+", choices=STEPS, default=STEPS)
ap.add_argument("--tables", nargs="+", choices=sorted(TABLES), help="chi dung lai cac bang clean/ nay")
args = ap.parse_args()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
paths = Paths(ROOT)

if "clean" in args.steps:
    res = build_clean(paths, only=args.tables)
    print("\n== data/clean/")
    for name, df in res.items():
        rng = (f"{df.week.min().date()} -> {df.week.max().date()}" if "week" in df
               else f"{df.season.min()} -> {df.season.max()}")
        print(f"  {name:<13} {len(df):>7} dong  {df.state.nunique():>2} bang  {rng}")

if "business" in args.steps:
    tables, status = build_business(paths)
    print("\n== data/business/")
    for name, df in tables.items():
        print(f"  {name:<20} {len(df):>7} dong x {df.shape[1]:>3} cot")
    print("  File cua thanh vien khac:")
    for k, v in status.items():
        print(f"    {k:<24} {v}")

if "olap" in args.steps:
    build_duckdb(paths)
    out = ROOT / "reports" / "olap" / "README.md"
    res = run_examples(paths, out)
    print(f"\n== data/business/fluwatch.duckdb; {len(res)} truy van mau -> {out.relative_to(ROOT).as_posix()}")
