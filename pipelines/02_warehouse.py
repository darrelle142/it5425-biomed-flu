"""TV2: kho du lieu. Mot lenh chay toan bo phan cua TV2.

    python pipelines/02_warehouse.py                          # clean -> business -> olap -> quality -> docs
    python pipelines/02_warehouse.py --steps clean            # chi dung data/clean/
    python pipelines/02_warehouse.py --steps clean --tables ilinet weather   # dung lai vai bang clean/
    python pipelines/02_warehouse.py --steps business olap    # dung lai star schema + DuckDB tu clean/ co san
    python pipelines/02_warehouse.py --steps quality          # kiem tra chat luong 4 muc -> reports/data_quality/
    python pipelines/02_warehouse.py --steps inject           # chay kiem tra tren du lieu chen loi (TV4 hoac tu sinh)
    python pipelines/02_warehouse.py --steps docs             # tu dien du lieu + lineage -> docs/

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

STEPS = ["clean", "business", "olap", "quality", "inject", "docs"]
DEFAULT = ["clean", "business", "olap", "quality", "docs"]      # inject chay rieng (cham, ~1-2 phut)

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--steps", nargs="+", choices=STEPS, default=DEFAULT)
ap.add_argument("--strict", action="store_true", help="thoat ma 1 neu co quy tac muc loi khong dat")
ap.add_argument("--tables", nargs="+", choices=sorted(TABLES), help="chi dung lai cac bang clean/ nay")
args = ap.parse_args()

if hasattr(sys.stdout, "reconfigure"):          # ten quy tac co dau tieng Viet; console Windows mac dinh cp1252
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
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

if "quality" in args.steps:
    from fluwatch.warehouse.quality import build_quality
    summary, viol, cov, md = build_quality(paths)
    print(f"\n== Chat luong: {len(summary)} quy tac -> {md.relative_to(ROOT).as_posix()}")
    for r in summary.itertuples():
        print(f"  {r.rule}  muc {r.level}  {r.status:<10} {r.violations:>6} vi pham  {r.name}")
    print(f"  Do phu: {int(cov.flag.sum())}/{len(cov)} o bang x nam thieu > 30%")
    if args.strict and (summary.status.isin(["KHONG_DAT", "LOI_CHAY"])).any():
        sys.exit(1)

if "inject" in args.steps:
    from fluwatch.warehouse.inject import run_injection_test
    out = ROOT / "reports" / "data_quality" / "injection_test.md"
    res = run_injection_test(paths, out)
    print(f"\n== Du lieu chen loi -> {out.relative_to(ROOT).as_posix()}")
    for r in res:
        k = r["key"]
        print(f"  {r['mode']:<11} bat {int(k.caught.sum())}/{len(k)} loi ({k.caught.mean() * 100:.1f}%), "
              f"bao dong gia {int((~r['new'].explained).sum())}")

if "docs" in args.steps:
    from fluwatch.warehouse.catalog import build_docs
    for p in build_docs(paths):
        print(f"\n== {p.relative_to(ROOT).as_posix()}")
