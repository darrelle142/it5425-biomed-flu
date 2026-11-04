"""Cac kiem tra bo sung cho ban thu hoach. Chay sau profile_sample.py.

Ket qua duoc gop vao data/samples/profile_results.json. Moi nguong o day la TAM.
"""
import glob
import gzip
import json
import re
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "samples"
RAW = ROOT / "data" / "raw"
R = json.loads((OUT / "profile_results.json").read_text(encoding="utf-8"))
f = pd.read_csv(OUT / "state_week_sample.csv.gz", parse_dates=["week"]).sort_values(["state", "week"])
X = {}

# Gia tri bat thuong cua ty le nhap vien
top = f.nlargest(5, "rate_flu")[["state", "week", "hosp_flu", "rate_flu", "hosp_reporting"]]
X["rate_top"] = top.astype(str).to_dict("records")
X["rate_p999_51units"] = round(float(f.rate_flu.quantile(.999)), 2)

# Thieu NHSN theo giai doan
per = {}
for name, a, b in [("2020-08..2022-01", "2020-08-01", "2022-01-31"), ("2022-02..2024-04", "2022-02-01", "2024-04-30"),
                   ("2024-05..2024-10", "2024-05-01", "2024-10-31"), ("2024-11..nay", "2024-11-01", "2026-10-24")]:
    g = f[(f.week >= a) & (f.week <= b)]
    per[name] = {"missing_pct": round(float(g.rate_flu.isna().mean() * 100), 1),
                 "median_hosp_per_state": float(g.hosp_reporting.median())}
X["nhsn_periods"] = per

# Khoang thieu ILI 2025-26: tung bang
gap = {}
for s in ["ak", "ct", "hi", "ny", "ok", "or", "sd", "ut"]:
    g = f[(f.state == s) & f.ili_pct.notna()]
    gg = g[g.week >= "2025-01-01"].week
    prior = gg[gg < "2025-10-01"].max()
    nxt = gg[gg >= "2025-10-01"].min()
    gap[s] = {"last_before": str(prior.date()), "first_after": str(nxt.date())}
X["ili_gap"] = gap

# Hien trang mua 2026-27
cur = f[(f.season == "2026-27") & f.rate_flu.notna()]
X["season_2026_27"] = {"weeks": int(cur.week.nunique()), "last": str(cur.week.max().date()),
                       "median_state_rate_last": round(float(cur[cur.week == cur.week.max()].rate_flu.median()), 3),
                       "max_state_rate_last": round(float(cur[cur.week == cur.week.max()].rate_flu.max()), 3)}

# ILI va cap cuu: ILI co phan anh rieng cum khong
h = f[(f.season >= "2022-23") & f.ili_pct.notna() & f.ed_pct_flu.notna() & f.ed_pct_covid.notna()].copy()
X["ili_vs_ed"] = {
    "corr_ili_ed_flu": round(float(h.groupby("state").apply(lambda g: g.ili_pct.corr(g.ed_pct_flu)).median()), 3),
    "corr_ili_ed_covid": round(float(h.groupby("state").apply(lambda g: g.ili_pct.corr(g.ed_pct_covid)).median()), 3),
    "corr_ili_hosp": round(float(h.groupby("state").apply(lambda g: g.ili_pct.corr(g.rate_flu)).median()), 3),
}
coef = []
for s, g in h.groupby("state"):
    g = g.dropna(subset=["ili_pct", "ed_pct_flu", "ed_pct_covid"])
    if len(g) > 30:
        A = np.column_stack([np.ones(len(g)), g.ed_pct_flu, g.ed_pct_covid])
        b = np.linalg.lstsq(A, g.ili_pct, rcond=None)[0]
        coef.append((b[0], b[1], b[2]))
coef = np.array(coef)
X["ili_decomp_median"] = {"intercept": round(float(np.median(coef[:, 0])), 3), "per_ed_flu": round(float(np.median(coef[:, 1])), 3),
                          "per_ed_covid": round(float(np.median(coef[:, 2])), 3)}

# RQ1: thu dinh nghia khoi phat tam
rows = []
d = f[f.ili_pct.notna() & (f.state != "")].copy()
seasons = ["2019-20", "2021-22", "2022-23", "2023-24", "2024-25", "2025-26", "2026-27"]
all_seasons = sorted(d.season.dropna().unique())
for s in seasons:
    prior = [x for x in all_seasons if x < s and x != "2020-21" and x >= "2016-17"][-3:]
    if len(prior) < 3:
        continue
    for st, g in d.groupby("state"):
        base = g[g.season.isin(prior) & (g.lab_pct_pos < 2)].ili_pct
        cur_g = g[g.season == s].sort_values("week")
        if len(base) < 20 or len(cur_g) < 3:
            continue
        thr = base.mean() + 2 * base.std()
        above = (cur_g.ili_pct >= thr).astype(int).values
        onset = None
        for i in range(len(above) - 2):
            if above[i:i + 3].sum() == 3:
                onset = cur_g.week.iloc[i]
                break
        rows.append({"season": s, "state": st, "baseline": thr, "onset": onset})
on = pd.DataFrame(rows)
on["onset"] = pd.to_datetime(on.onset)
summ = []
for s, g in on.groupby("season"):
    ok = g.dropna(subset=["onset"])
    summ.append({"season": s, "state_units": int(len(g)), "onset_found": int(len(ok)),
                 "earliest": str(ok.onset.min().date()) if len(ok) else None,
                 "median": str(ok.onset.quantile(.5).date()) if len(ok) else None,
                 "latest": str(ok.onset.max().date()) if len(ok) else None,
                 "median_baseline": round(float(g.baseline.median()), 2)})
X["onset_trial"] = summ

# RQ5: ca vuot nguong moi, khong tinh cac tuan da o tren nguong
THR = 3.0
h = f[f.rate_flu.notna() & (f.season >= "2022-23") & (f.season <= "2025-26")].copy()
h = h[(h.mmwr_week >= 40) | (h.mmwr_week <= 20)].sort_values(["state", "week"])
nxt = h.groupby("state").rate_flu.shift(-1)
h["y"] = (nxt >= THR).astype(float)
h.loc[nxt.isna(), "y"] = np.nan
h["d_rate"] = h.rate_flu - h.groupby("state").rate_flu.shift(1)
h["d_ed"] = h.ed_pct_flu - h.groupby("state").ed_pct_flu.shift(1)
h["log_rate"] = np.log1p(h.rate_flu)
h = h.dropna(subset=["y", "d_rate", "d_ed", "ed_pct_flu"])
risk = h[h.rate_flu < THR].copy()
feats = {"Tỷ lệ hiện tại": None, "Thêm tốc độ tăng": ["log_rate", "d_rate"], "Thêm cấp cứu": ["log_rate", "d_rate", "ed_pct_flu", "d_ed"]}


def ci(t, score, n=400):
    rng = np.random.default_rng(11)
    idx = t.groupby("state").indices
    states = list(idx)
    y = t.y.values
    vals = []
    for _ in range(n):
        b = np.concatenate([idx[s] for s in rng.choice(states, len(states))])
        if 0 < y[b].sum() < len(b):
            vals.append(roc_auc_score(y[b], score[b]))
    return [round(float(np.quantile(vals, .025)), 3), round(float(np.quantile(vals, .975)), 3)]


out = []
for test in ["2024-25", "2025-26"]:
    tr, te = risk[risk.season < test], risk[risk.season == test].reset_index(drop=True)
    row = {"test": test, "rows": int(len(te)), "events": int(te.y.sum())}
    for name, cols in feats.items():
        if cols is None:
            p = te.rate_flu.values
        else:
            p = make_pipeline(StandardScaler(), LogisticRegression(max_iter=500)).fit(tr[cols], tr.y).predict_proba(te[cols])[:, 1]
        row[name] = {"auc": round(float(roc_auc_score(te.y, p)), 3), "ci": ci(te, p)}
    # Hieu chinh: quan sat so voi du doan theo 5 nhom
    q = pd.qcut(p, 5, duplicates="drop")
    cal = pd.DataFrame({"p": p, "y": te.y, "q": q}).groupby("q", observed=True).agg(pred=("p", "mean"), obs=("y", "mean"), n=("y", "size"))
    row["calibration_full_model"] = cal.round(3).reset_index(drop=True).to_dict("records")
    out.append(row)
X["rq5_new_crossing"] = out

# Kiem chung PM2.5: Open-Meteo 1 diem so voi trung binh tram EPA cua bang, nam 2024
z = zipfile.ZipFile(sorted(glob.glob(str(RAW / "epa_airdata" / "*" / "daily_88101_2024.zip")))[-1])
e = pd.read_csv(z.open(z.namelist()[0]), usecols=["State Name", "Date Local", "Arithmetic Mean", "Sample Duration"], low_memory=False)
e["date"] = pd.to_datetime(e["Date Local"])
e["week"] = e.date + pd.to_timedelta((5 - e.date.dt.weekday) % 7, unit="D")
names = pd.read_csv(sorted(glob.glob(str(RAW / "population" / "*" / "state_pop_2020_delphi.csv")))[-1])
e = e.merge(names, left_on="State Name", right_on="state_name")
ew = e.groupby(["state_id", "week"], as_index=False)["Arithmetic Mean"].mean().rename(columns={"state_id": "state", "Arithmetic Mean": "epa"})
c = f[(f.week >= "2024-01-06") & (f.week <= "2024-12-28")][["state", "week", "pm25_mean"]].merge(ew, on=["state", "week"])
cors = c.groupby("state").apply(lambda g: g.pm25_mean.corr(g.epa))
X["pm25_validation"] = {"state_weeks": int(len(c)), "states": int(c.state.nunique()), "median_corr": round(float(cors.median()), 3),
                        "p10_corr": round(float(cors.quantile(.1)), 3), "mean_openmeteo": round(float(c.pm25_mean.mean()), 2), "mean_epa": round(float(c.epa.mean()), 2)}

# Nuoc thai: co the anh xa ve bang khong
try:
    u = "https://delphi.cmu.edu/epidata/v5/metadata/aux_schema/?source=nwss"
    X["nwss_aux_schema"] = urllib.request.urlopen(u, timeout=60).read().decode("utf-8", "replace")[:1500]
except Exception as err:
    X["nwss_aux_schema"] = f"ERR {err}"

# Trang FluVaxView: co bang so lieu theo bang khong
pg = {}
for p in glob.glob(str(RAW / "fluvaxview_pages" / "*" / "*.html.gz")):
    t = gzip.open(p).read().decode("utf-8", "replace")
    tb = re.search(r"<table.*?</table>", t, flags=re.S)
    txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", tb.group(0)))[:220] if tb else ""
    i = t.find("Alabama")
    pg[Path(p).name[:9]] = {"table_text": txt, "alabama_context": re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t[max(0, i - 200):i + 200])) if i >= 0 else ""}
X["fluvax_pages"] = pg

R["extras"] = X
(OUT / "profile_results.json").write_text(json.dumps(R, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print(json.dumps(X, ensure_ascii=False, indent=0, default=str))
