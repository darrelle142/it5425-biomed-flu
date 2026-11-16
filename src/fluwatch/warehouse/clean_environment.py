"""clean/: moi truong theo bang x tuan MMWR.

- weather: nhiet do, do am tuyet doi, PM2.5 Open-Meteo, trung binh co trong so dan so cua 3-5 thanh pho moi bang
  (reference/cities.csv). Cung cach tinh voi scripts/build_environment.py cua TV1.
- epa_pm25: PM2.5 tram do EPA AirData (dai luong 88101), trung binh cac tram trong bang.
PM2.5 am (sai so thiet bi) dat thanh thieu truoc khi lay trung binh, co ghi log.
"""
import gzip
import json
import re
import unicodedata
import zipfile

import numpy as np
import pandas as pd

from .common import add_time_keys, keep_states, negative_to_na, raw_files, state_names, to_saturday


def _slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def _city_files(paths, source_city, source_state, row, is_top):
    """Moi file cua mot thanh pho, cu -> moi: lich su day du truoc, doan cap nhat (__recent) sau.

    Thanh pho lon nhat cua bang con dung file theo bang cua crawl_sample.py khi chua co lich su rieng.
    """
    base = f"{row.state}__{_slug(row.city)}"
    hist = raw_files(paths, source_city, base, ".json.gz")
    hist = [p for p in hist if "__recent" not in p.name]
    if is_top and not hist:
        hist = raw_files(paths, source_state, row.state, ".json.gz")
    recent = raw_files(paths, source_city, f"{base}__recent", ".json.gz")
    return hist + recent


def _load_series(files, key, cols):
    """Ghep cac file theo thoi gian; trung thoi diem thi giu ban tai sau cung."""
    parts = []
    for i, f in enumerate(files):
        d = json.load(gzip.open(f))[key]
        parts.append(pd.DataFrame({"time": pd.to_datetime(d["time"]), **{c: d[c] for c in cols}, "_o": i}))
    d = pd.concat(parts).sort_values(["time", "_o"]).drop_duplicates("time", keep="last")
    for c in cols:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    return d.drop(columns="_o").reset_index(drop=True)


def _full_weeks(df, name, clog):
    """Bo tuan cuoi chua du 7 ngay (Open-Meteo, EPA dung giua tuan)."""
    last = df["date"].max()
    last_sat = last - pd.Timedelta(days=(last.weekday() - 5) % 7)
    part = df["week"] > last_sat
    if part.any():
        clog.step(name, "bo tuan cuoi chua du 7 ngay", part.sum(), f"sau {last_sat.date()}")
    return df[~part]


def _wavg(df, value_cols):
    """Trung binh co trong so theo bang x tuan; trong so chuan hoa lai tren cac thanh pho co so lieu."""
    out = []
    for c in value_cols:
        g = df.dropna(subset=[c])
        wsum = g.groupby(["state", "week"]).w.transform("sum")
        r = (g[c] * g.w / wsum).groupby([g.state, g.week]).sum().rename(c)
        out.append(r)
    n = df.dropna(subset=value_cols[:1]).groupby(["state", "week"]).city.nunique().rename("n_cities")
    return pd.concat(out + [n], axis=1).reset_index()


def clean_weather(paths, clog):
    name = "weather"
    cities = pd.read_csv(paths.reference / "cities.csv")
    clog.source(name, paths, paths.reference / "cities.csv")
    is_top = cities.groupby("state").population.transform("max") == cities.population
    wrows, prows, missing = [], [], []
    for (_, r), top in zip(cities.iterrows(), is_top):
        fw = _city_files(paths, "openmeteo_weather_cities", "openmeteo_weather", r, top)
        fp = _city_files(paths, "openmeteo_pm25_cities", "openmeteo_pm25", r, top)
        if fw:
            d = _load_series(fw, "daily", ["temperature_2m_mean", "relative_humidity_2m_mean"])
            wrows.append(pd.DataFrame({"state": r.state, "city": r.city, "w": r.weight, "date": d.time,
                                       "temp": d.temperature_2m_mean, "rh": d.relative_humidity_2m_mean}))
        if fp:
            p = _load_series(fp, "hourly", ["pm2_5"]).rename(columns={"pm2_5": "pm25"})
            p["date"] = p.time.dt.normalize()
            prows.append(p.assign(state=r.state, city=r.city, w=r.weight))
        if not (fw and fp):
            missing.append(f"{r.state}/{r.city}")
    clog.table(name)["sources"] += ["data/raw/openmeteo_weather_cities/*", "data/raw/openmeteo_pm25_cities/*",
                                    "data/raw/openmeteo_weather/* (thanh pho lon nhat, khi chua co lich su rieng)"]
    if missing:
        clog.step(name, "thanh pho thieu file thoi tiet hoac PM2.5", len(missing), ", ".join(missing[:20]))

    wx = pd.concat(wrows, ignore_index=True)
    wx = keep_states(wx, name, clog)
    bad_rh = (wx.rh < 0) | (wx.rh > 100)
    if bad_rh.any():
        clog.step(name, "do am tuong doi ngoai 0-100 -> thieu", bad_rh.sum())
        wx.loc[bad_rh, "rh"] = np.nan
    # Do am tuyet doi (g/m3), cong thuc Magnus nhu TV1
    wx["ah"] = 6.112 * np.exp(17.67 * wx.temp / (wx.temp + 243.5)) * wx.rh * 2.1674 / (273.15 + wx.temp)
    wx["week"] = to_saturday(wx.date)
    wx = _full_weeks(wx, name, clog)
    cw = wx.groupby(["state", "city", "week"], as_index=False).agg(w=("w", "first"), temp_mean=("temp", "mean"),
                                                                  abs_humidity=("ah", "mean"))
    ws = _wavg(cw, ["abs_humidity", "temp_mean"])

    pm = pd.concat(prows, ignore_index=True)
    pm = keep_states(pm, name, clog)
    pm = negative_to_na(pm, ["pm25"], name, clog)                   # theo gio
    pm = pm.groupby(["state", "city", "date"], as_index=False).agg(w=("w", "first"), pm25=("pm25", "mean"))
    pm["week"] = to_saturday(pm.date)
    pm = _full_weeks(pm, name, clog)
    cp = pm.dropna(subset=["pm25"]).groupby(["state", "city", "week"], as_index=False).agg(
        w=("w", "first"), pm25_om_mean=("pm25", "mean"), pm25_om_max=("pm25", "max"))
    ps = _wavg(cp, ["pm25_om_mean", "pm25_om_max"]).drop(columns="n_cities")

    out = ws.merge(ps, on=["state", "week"], how="left")
    out["n_cities"] = out["n_cities"].astype("Int64")
    out = add_time_keys(out)
    cols = ["state", "week", "epiweek", "season", "season_week", "temp_mean", "abs_humidity",
            "pm25_om_mean", "pm25_om_max", "n_cities"]
    return out[cols].sort_values(["state", "week"]).reset_index(drop=True)


def clean_epa(paths, clog):
    name = "epa_pm25"
    names, fpop = state_names(paths)
    clog.source(name, paths, fpop)
    files = sorted((paths.raw / "epa_airdata").glob("*/daily_88101_*.zip"))
    # moi nam lay ban tai moi nhat
    by_year = {}
    for f in files:
        by_year[f.name] = f
    rows = []
    for fname in sorted(by_year):
        f = by_year[fname]
        clog.source(name, paths, f)
        z = zipfile.ZipFile(f)
        e = pd.read_csv(z.open(z.namelist()[0]), low_memory=False,
                        usecols=["State Name", "County Code", "Site Num", "Date Local", "Arithmetic Mean"])
        rows.append(e)
    e = pd.concat(rows, ignore_index=True)
    e["state"] = e["State Name"].str.lower().map(names)
    unk = e["state"].isna()
    if unk.any():
        clog.step(name, "bo dong ten bang khong khop", unk.sum(), ", ".join(sorted(e.loc[unk, "State Name"].unique())))
    e = keep_states(e[~unk], name, clog)
    e = e.rename(columns={"Arithmetic Mean": "pm25"})
    e = negative_to_na(e, ["pm25"], name, clog)                     # theo ngay, tung may do
    e["date"] = pd.to_datetime(e["Date Local"])
    e["site"] = e["County Code"].astype(str) + "-" + e["Site Num"].astype(str)
    e = e.groupby(["state", "site", "date"], as_index=False).pm25.mean()   # nhieu may do cung tram
    e["week"] = to_saturday(e.date)
    e = _full_weeks(e, name, clog)
    ep = e.dropna(subset=["pm25"]).groupby(["state", "week"]).agg(
        epa_pm25_mean=("pm25", "mean"), epa_sites=("site", "nunique")).reset_index()
    ep["epa_sites"] = ep["epa_sites"].astype("Int64")
    ep = add_time_keys(ep)
    cols = ["state", "week", "epiweek", "season", "season_week", "epa_pm25_mean", "epa_sites"]
    return ep[cols].sort_values(["state", "week"]).reset_index(drop=True)
