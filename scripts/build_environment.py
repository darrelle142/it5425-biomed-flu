"""Gop thoi tiet, PM2.5 Open-Meteo (3-5 thanh pho, trong so dan so) va PM2.5 EPA ve bang x tuan MMWR.

Chay sau crawl_cities_weather.py va build_reference.py.
Dau ra:
    data/samples/weather_state_week.csv.gz    temp_mean, abs_humidity, pm25_mean, pm25_max, n_cities
    data/samples/epa_pm25_state_week.csv.gz   epa_pm25_mean, epa_sites (trung binh cac tram trong bang)
Tuan ket thuc vao thu Bay (tuan MMWR).
"""
import glob
import gzip
import json
import re
import unicodedata
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "samples"
cities = pd.read_csv(ROOT / "data" / "reference" / "cities.csv")
names = pd.read_csv(sorted(glob.glob(str(RAW / "population" / "*" / "state_pop_2020_delphi.csv")))[-1])


def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def find(source_city, source_state, row, top):
    """Moi file cua mot thanh pho, xep tu cu den moi: (ngay tai, lich su day du truoc, doan gan day sau).

    Thanh pho lon nhat con dung file cua crawl_sample.py (theo bang). Doan gan day do
    crawl_cities_weather.py --update luu thanh <bang>__<thanh_pho>__recent.json.
    """
    base = f"{row.state}__{slug(row.city)}"
    f = glob.glob(str(RAW / source_city / "*" / f"{base}.json.gz"))
    if top and not f:  # chi dung file theo bang khi thanh pho chua co lich su rieng
        f += glob.glob(str(RAW / source_state / "*" / f"{row.state}.json.gz"))
    f += glob.glob(str(RAW / source_city / "*" / f"{base}__recent.json.gz"))
    return sorted(f, key=lambda x: (Path(x).parent.name, "__recent" in x))


def load(files, key, cols):
    """Ghep cac file theo thoi gian; thoi diem trung thi giu ban tai sau cung."""
    parts = []
    for i, x in enumerate(files):
        d = json.load(gzip.open(x))[key]
        parts.append(pd.DataFrame({"time": pd.to_datetime(d["time"]), **{c: d[c] for c in cols}, "_order": i}))
    d = pd.concat(parts).sort_values(["time", "_order"]).drop_duplicates("time", keep="last")
    return d.drop(columns="_order").reset_index(drop=True)


def to_week(d):
    return d + pd.to_timedelta((5 - d.dt.weekday) % 7, unit="D")


def full_weeks(df):
    """Bo tuan cuoi chua du 7 ngay (so lieu Open-Meteo dung giua tuan)."""
    last = df.date.max()
    last_sat = last - pd.Timedelta(days=(last.weekday() - 5) % 7)
    return df[df.week <= last_sat]


wrows, prows, missing = [], [], []
top = cities.groupby("state").population.transform("max") == cities.population
for (_, r), is_top in zip(cities.iterrows(), top):
    fw = find("openmeteo_weather_cities", "openmeteo_weather", r, is_top)
    fp = find("openmeteo_pm25_cities", "openmeteo_pm25", r, is_top)
    if fw:
        d = load(fw, "daily", ["temperature_2m_mean", "relative_humidity_2m_mean"])
        wrows.append(pd.DataFrame({"state": r.state, "city": r.city, "w": r.weight, "date": d.time,
                                   "temp": d.temperature_2m_mean, "rh": d.relative_humidity_2m_mean}))
    if fp:
        p = load(fp, "hourly", ["pm2_5"]).rename(columns={"pm2_5": "pm25"})
        p = p.groupby(p.time.dt.normalize()).pm25.mean().rename_axis("date").reset_index()
        prows.append(p.assign(state=r.state, city=r.city, w=r.weight))
    if not (fw and fp):
        missing.append((r.state, r.city, bool(fw), bool(fp)))

wx = pd.concat(wrows)
wx["temp"] = pd.to_numeric(wx.temp, errors="coerce")
wx["rh"] = pd.to_numeric(wx.rh, errors="coerce")
wx["ah"] = 6.112 * np.exp(17.67 * wx.temp / (wx.temp + 243.5)) * wx.rh * 2.1674 / (273.15 + wx.temp)
wx["week"] = to_week(wx.date)
wx = full_weeks(wx)
cw = wx.groupby(["state", "city", "week"], as_index=False).agg(w=("w", "first"), temp=("temp", "mean"), ah=("ah", "mean"))
cw = cw.dropna(subset=["ah"])


def wavg(g, cols):
    w = g.w / g.w.sum()  # chuan hoa lai trong so theo cac thanh pho co so lieu tuan do
    return pd.Series({c: float((g[c] * w).sum()) for c in cols} | {"n_cities": len(g)})


ws = cw.groupby(["state", "week"]).apply(lambda g: wavg(g, ["temp", "ah"]), include_groups=False).reset_index()
ws = ws.rename(columns={"temp": "temp_mean", "ah": "abs_humidity"})

pm = pd.concat(prows)
pm["week"] = to_week(pm.date)
pm = full_weeks(pm)
cp = pm.dropna(subset=["pm25"]).groupby(["state", "city", "week"], as_index=False).agg(
    w=("w", "first"), pm25_mean=("pm25", "mean"), pm25_max=("pm25", "max"))
ps = cp.groupby(["state", "week"]).apply(lambda g: wavg(g, ["pm25_mean", "pm25_max"]), include_groups=False).reset_index()
env = ws.merge(ps.drop(columns="n_cities"), on=["state", "week"], how="left")
env.to_csv(OUT / "weather_state_week.csv.gz", index=False)

# So sanh voi ban 1 thanh pho moi bang trong bang mau
f = pd.read_csv(OUT / "state_week_sample.csv.gz", parse_dates=["week"])[["state", "week", "abs_humidity", "mmwr_week"]]
c = f.merge(env[["state", "week", "abs_humidity"]], on=["state", "week"], suffixes=("_1city", "_weighted")).dropna()
for k in ["1city", "weighted"]:
    c[f"anom_{k}"] = c[f"abs_humidity_{k}"] - c.groupby(["state", "mmwr_week"])[f"abs_humidity_{k}"].transform("mean")
cor_raw = c.groupby("state").apply(lambda g: g.abs_humidity_1city.corr(g.abs_humidity_weighted), include_groups=False)
cor_anom = c.groupby("state").apply(lambda g: g.anom_1city.corr(g.anom_weighted), include_groups=False)

# PM2.5 EPA, tat ca cac nam da tai
erows = []
for zp in sorted(glob.glob(str(RAW / "epa_airdata" / "*" / "daily_88101_*.zip"))):
    z = zipfile.ZipFile(zp)
    e = pd.read_csv(z.open(z.namelist()[0]), usecols=["State Name", "Site Num", "County Code", "Date Local", "Arithmetic Mean"],
                    low_memory=False)
    e["date"] = pd.to_datetime(e["Date Local"])
    e["site"] = e["State Name"] + e["County Code"].astype(str) + "-" + e["Site Num"].astype(str)
    e = e.groupby(["State Name", "site", "date"], as_index=False)["Arithmetic Mean"].mean()  # nhieu may do cung tram
    erows.append(e)
e = pd.concat(erows)
e["key"] = e["State Name"].str.lower()  # EPA ghi "District Of Columbia"
e = e.merge(names.assign(key=names.state_name.str.lower()), on="key")
e["week"] = to_week(e.date)
ep = e.groupby(["state_id", "week"]).agg(epa_pm25_mean=("Arithmetic Mean", "mean"), epa_sites=("site", "nunique")).reset_index()
ep = ep.rename(columns={"state_id": "state"})
ep.to_csv(OUT / "epa_pm25_state_week.csv.gz", index=False)

R = {"cities_total": int(len(cities)), "cities_with_weather": int(cw.groupby(["state", "city"]).ngroups),
     "cities_missing": missing[:30], "n_missing": len(missing),
     "weather_state_weeks": int(len(ws)), "weather_range": [str(ws.week.min().date()), str(ws.week.max().date())],
     "n_cities_per_state_median": float(ws.groupby("state").n_cities.max().median()),
     "ah_corr_weighted_vs_1city_median": round(float(cor_raw.median()), 3),
     "ah_anom_corr_weighted_vs_1city": {"median": round(float(cor_anom.median()), 3), "min": [cor_anom.idxmin(), round(float(cor_anom.min()), 3)]},
     "epa_state_weeks": int(len(ep)), "epa_range": [str(ep.week.min().date()), str(ep.week.max().date())],
     "epa_states": int(ep.state.nunique()), "epa_sites_per_state_week_median": float(ep.epa_sites.median())}
(OUT / "environment_results.json").write_text(json.dumps(R, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print(json.dumps(R, ensure_ascii=False, indent=1, default=str))
