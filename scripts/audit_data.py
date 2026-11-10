"""Kiem tra do day du cua toan bo data/: doc thu tung nguon, do phu 51 don vi, khoang thoi gian, manifest.

Cach chay: python scripts/audit_data.py   -> in bang ket qua, ghi data/samples/audit_results.json
           python scripts/audit_data.py --strict   -> thoat voi ma 1 neu co dong ok = False (cong chat luong)
"""
import glob
import gzip
import hashlib
import io
import json
import sys
import zipfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "samples"
REF = ROOT / "data" / "reference"
names = pd.read_csv(sorted(glob.glob(str(RAW / "population" / "*" / "state_pop_2020_delphi.csv")))[-1])
UNITS = sorted(set(names.state_id) - {"as", "gu", "mp", "pr", "vi", "us", "pw"})  # 50 bang + DC
name2id = dict(zip(names.state_name, names.state_id))
rows = []


def add(source, ok, n_rows=None, period=None, units=None, note=""):
    rows.append({"source": source, "ok": ok, "rows": n_rows, "period": period,
                 "units_51": None if units is None else f"{len(set(units) & set(UNITS))}/51", "note": note,
                 "missing_units": None if units is None else sorted(set(UNITS) - set(units))})


def latest(src, pat):
    f = sorted(glob.glob(str(RAW / src / "*" / pat)))
    return f[-1] if f else None


def delphi(src, pat, note=""):
    """Kiem tra ban tai moi nhat cua tung file (cac ban cu van giu trong raw/ de truy lai lich su sua so)."""
    newest = {Path(f).name: f for f in sorted(glob.glob(str(RAW / src / "*" / pat)))}
    for f in newest.values():
        try:
            d = pd.read_csv(gzip.open(f), usecols=["geo_value", "reference_time", "value"])
            add(f"{src}/{Path(f).name[:-7]}", True, len(d), f"{d.reference_time.min()[:10]} → {d.reference_time.max()[:10]}",
                d.geo_value.str.lower().unique(), f"ban tai {Path(f).parent.name}" + (f"; {note}" if note else ""))
        except Exception as e:
            add(f"{src}/{Path(f).name}", False, note=f"LOI: {e}")


# 1. Delphi
for src in ["fluview_ilinet", "nhsn", "nssp", "fluview_resp_lab_clinical", "flusurv"]:
    delphi(src, "*.csv.gz")
f = latest("nwss", "*.csv.gz")
d = pd.read_csv(gzip.open(f), usecols=["geo_value", "reference_time"])
add("nwss/flu_flowpop_lin (theo diem)", True, len(d), f"{d.reference_time.min()[:10]} → {d.reference_time.max()[:10]}",
    note=f"{d.geo_value.nunique()} diem; da thay bang WVAL")

# 2. Tai tay CDC
f = latest("cdc_wastewater_wval", "*.csv")
d = pd.read_csv(f, usecols=["State/Territory", "Week_End", "Pathogen_Target", "Site"], low_memory=False)
d = d[d.Pathogen_Target == "Influenza A virus"]
add("cdc_wastewater_wval (cum A)", True, len(d), f"{d.Week_End.min()} → {d.Week_End.max()}",
    d["State/Territory"].map(name2id).dropna().unique(), f"{d.Site.nunique()} diem; tu dong thu Bay (crawl_cdc.yml)")
f = latest("cdc_fluvax_coverage", "*.csv")
d = pd.read_csv(f, dtype=str, usecols=["Geography", "Season/Survey Year"])
add("cdc_fluvax_coverage", True, len(d), f"{d['Season/Survey Year'].min()} → {d['Season/Survey Year'].max()}",
    d.Geography.map(name2id).dropna().unique(), "chua co mua 2026-27; tu dong thu Bay (crawl_cdc.yml)")
for src in ["cdc_nhsn_hrd", "cdc_nhsn_levels"]:
    f = latest(src, "*.csv")
    d = pd.read_csv(f, low_memory=False)
    wk = d.columns[0] if src == "cdc_nhsn_hrd" else "weekEndingDate"
    geo = d.columns[1] if src == "cdc_nhsn_hrd" else "jurisdiction"
    add(src, True, len(d), f"{d[wk].min()} → {d[wk].max()}", d[geo].str.lower().unique(),
        "ban chup; khong can tai lai (Delphi + nguong CDC thay the)")

# 3. Census
f = latest("census_popest_state", "*.csv")
d = pd.read_csv(f)
d = d[d.SUMLEV == 40]
add("census_popest_state", True, len(d), "2020 → 2025", d.NAME.map(name2id).dropna().unique())
f = latest("census_popest_places", "*.xlsx")
add("census_popest_places", f is not None, note="dan so do thi 2020-2025")
f = latest("census_gazetteer", "*.zip")
z = zipfile.ZipFile(f)
d = pd.read_csv(z.open(z.namelist()[0]), sep="\t", usecols=[0])
add("census_gazetteer", True, len(d), "2024", d.iloc[:, 0].str.lower().unique())

# 4. Moi truong
for src, key in [("openmeteo_weather", "daily"), ("openmeteo_pm25", "hourly")]:
    fs = glob.glob(str(RAW / src / "*" / "*.json.gz"))
    bad = []
    for x in fs:
        try:
            json.load(gzip.open(x))[key]
        except Exception:
            bad.append(Path(x).name)
    add(src + " (thanh pho lon nhat)", not bad, len(fs), None, [Path(x).name[:2] for x in fs], f"loi: {bad}" if bad else "")
cities = pd.read_csv(REF / "cities.csv")
wc = pd.read_csv(OUT / "weather_state_week.csv.gz")
full = cities.groupby("state").size()
got = wc.groupby("state").n_cities.max()
lack = (full - got.reindex(full.index).fillna(0)).astype(int)
add("thoi tiet 3-5 thanh pho (weather_state_week)", bool((lack == 0).all()), len(wc),
    f"{wc.week.min()} → {wc.week.max()}", wc.state.unique(),
    f"{int(got.reindex(full.index).fillna(0).sum())}/{len(cities)} thanh pho; bang con thieu: {lack[lack > 0].index.tolist()}")
eps = sorted(glob.glob(str(RAW / "epa_airdata" / "*" / "daily_88101_*.zip")))
years = sorted({int(Path(x).stem[-4:]) for x in eps})
ep = pd.read_csv(OUT / "epa_pm25_state_week.csv.gz")
add("epa_airdata", years == list(range(2010, 2027)), len(ep), f"{ep.week.min()} → {ep.week.max()}", ep.state.unique(),
    f"nam: {years[0]}-{years[-1]} ({len(years)} file)")

# 5. Tra cuu
th = pd.read_csv(REF / "cdc_level_thresholds.csv")
add("reference/cdc_level_thresholds", True, len(th), None, th[th.virus == "Influenza"].jurisdiction.str.lower().unique())
h = pd.read_csv(REF / "holidays.csv")
add("reference/holidays", True, len(h), f"{h.week.min()} → {h.week.max()}")
add("reference/cities", True, len(cities), None, cities.state.unique(), f"{(full < 3).sum()} bang duoi 3 do thi: {full[full < 3].index.tolist()}")

# 6. Manifest: moi file co trong manifest, sha256 khop, khong co dong tro toi file mat
man = [json.loads(x) for x in (RAW / "manifest.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
mf = {m["file"]: m for m in man if m.get("file")}
on_disk = {str(Path(x).relative_to(ROOT)).replace("\\", "/") for x in glob.glob(str(RAW / "*" / "*" / "*"))}
not_logged = sorted(on_disk - set(mf))
gone = sorted(set(mf) - on_disk)
mism = [k for k, m in mf.items() if k in on_disk and m.get("sha256") and m["http_status"] == "manual"
        and hashlib.sha256((ROOT / k).read_bytes()).hexdigest() != m["sha256"]]
add("manifest.jsonl", not (not_logged or gone or mism), len(man),
    note=f"file chua ghi: {len(not_logged)} {not_logged[:3]}; dong tro file mat: {len(gone)} {gone[:3]}; sha lech: {mism}")

R = pd.DataFrame(rows)
(OUT / "audit_results.json").write_text(R.to_json(orient="records", force_ascii=False, indent=1), encoding="utf-8")
pd.set_option("display.width", 250, "display.max_colwidth", 90, "display.max_rows", 100)
print(R.drop(columns="missing_units").to_string(index=False))
print("\nDon vi thieu theo nguon:")
for r in rows:
    if r["missing_units"]:
        print(f"  {r['source']}: {r['missing_units']}")

bad = R[R.ok != True]  # noqa: E712 (cot ok co the la object)
if len(bad):
    print()
    print("Co nguon KHONG dat:", bad.source.tolist())
    if "--strict" in sys.argv:
        sys.exit(1)
