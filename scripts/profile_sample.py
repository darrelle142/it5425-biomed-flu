"""Mo ta du lieu vua crawl va chay kiem tra thu cho tung RQ.

Cach chay (tu thu muc project): python scripts/profile_sample.py
Ket qua: data/samples/profile_results.json, data/samples/state_week_sample.csv.gz va
cac file xem truoc data/samples/preview_*.csv.

Moi nguong va dinh nghia o day la TAM de kiem tra tinh kha thi, chua phai dinh nghia chinh thuc.
"""
import datetime as dt
import glob
import gzip
import json
import math
import warnings
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "samples"
OUT.mkdir(parents=True, exist_ok=True)
R = {}
STATES = set(pd.read_csv(ROOT / "data" / "reference" / "cities_largest_per_state.csv").state)


def latest(source, name):
    return sorted(glob.glob(str(RAW / source / "*" / name)))[-1]


def load(source, name):
    df = pd.read_csv(latest(source, name), compression="gzip", low_memory=False)
    df["reference_time"] = pd.to_datetime(df["reference_time"])
    return df


def mmwr_year_week(d):
    """Tuan MMWR cua ngay Thu Bay ket thuc tuan."""
    wed = d - dt.timedelta(days=3)
    jan1 = dt.date(wed.year, 1, 1)
    first_sun = jan1 - dt.timedelta(days=(jan1.weekday() + 1) % 7)
    if (jan1.weekday() + 1) % 7 > 3:
        first_sun += dt.timedelta(days=7)
    return wed.year, (d - dt.timedelta(days=6) - first_sun).days // 7 + 1


def add_season(df, col="reference_time"):
    uniq = df[col].drop_duplicates()
    rows = []
    for t in uniq:
        y, w = mmwr_year_week(t.date())
        start = y if w >= 40 else y - 1
        rows.append((t, y, w, f"{start}-{str(start + 1)[2:]}"))
    m = pd.DataFrame(rows, columns=[col, "mmwr_year", "mmwr_week", "season"])
    return df.merge(m, on=col, how="left")


def describe(df, label):
    v = pd.to_numeric(df["value"], errors="coerce")
    info = {
        "rows": int(len(df)), "columns": list(df.columns),
        "from": str(df.reference_time.min().date()), "to": str(df.reference_time.max().date()),
        "geo_units": int(df.geo_value.nunique()),
        "missing_pct": round(float(v.isna().mean() * 100), 2),
        "min": None if v.isna().all() else round(float(v.min()), 3),
        "median": None if v.isna().all() else round(float(v.median()), 3),
        "max": None if v.isna().all() else round(float(v.max()), 3),
        "last_report": str(df.report_time.max())[:10],
    }
    R.setdefault("datasets", {})[label] = info
    df.head(20).to_csv(OUT / f"preview_{label}.csv", index=False)
    print(label, info, flush=True)


# ---------- nap du lieu ----------
sets = {
    "ili": ("fluview_ilinet", "ili__state.csv.gz"),
    "num_ili": ("fluview_ilinet", "num_ili__state.csv.gz"),
    "num_patients": ("fluview_ilinet", "num_patients__state.csv.gz"),
    "num_providers": ("fluview_ilinet", "num_providers__state.csv.gz"),
    "hosp": ("nhsn", "confirmed_admissions_flu_ew__state.csv.gz"),
    "hosp_rate": ("nhsn", "confirmed_admissions_flu_per100k_ew__state.csv.gz"),
    "hosp_reporting": ("nhsn", "hosprep_confirmed_admissions_flu_ew__state.csv.gz"),
    "beds_flu_pct": ("nhsn", "inpatient_beds_flu_pct_ew__state.csv.gz"),
    "ed_flu": ("nssp", "pct_ed_visits_influenza__state.csv.gz"),
    "ed_covid": ("nssp", "pct_ed_visits_covid__state.csv.gz"),
    "lab_pos": ("fluview_resp_lab_clinical", "pct_positive__state.csv.gz"),
    "lab_total": ("fluview_resp_lab_clinical", "total_specimens__state.csv.gz"),
    "flusurv": ("flusurv", "rate_overall__state.csv.gz"),
}
D = {k: load(*v) for k, v in sets.items()}
for k, df in D.items():
    describe(df, k)
ww = load("nwss", "flu_flowpop_lin__sewershed.csv.gz")
describe(ww, "wastewater")
R["wastewater_extra"] = {"sites": int(ww.geo_value.nunique()),
                         "sources": ww.nwss_source.value_counts().to_dict(),
                         "targets": ww.pcr_target.value_counts().to_dict()}


def wide(key, name, age=True):
    df = D[key]
    if "age_group" in df.columns:
        df = df[df.age_group == "all"]
    df = df[df.geo_value.isin(STATES)]
    return df[["geo_value", "reference_time", "value"]].rename(
        columns={"geo_value": "state", "reference_time": "week", "value": name}
    ).drop_duplicates(["state", "week"])


frame = None
for key, name in [("ili", "ili_pct"), ("num_ili", "num_ili"), ("num_patients", "num_patients"),
                  ("hosp", "hosp_flu"), ("hosp_rate", "rate_flu"), ("hosp_reporting", "hosp_reporting"),
                  ("beds_flu_pct", "beds_flu_pct"), ("ed_flu", "ed_pct_flu"), ("ed_covid", "ed_pct_covid"),
                  ("lab_pos", "lab_pct_pos")]:
    t = wide(key, name)
    frame = t if frame is None else frame.merge(t, on=["state", "week"], how="outer")
print("frame", frame.shape, flush=True)

# ---------- thoi tiet + PM2.5 ----------
wrows, prows = [], []
for f in glob.glob(str(RAW / "openmeteo_weather" / "*" / "*.json.gz")):
    st = Path(f).name[:2]
    d = json.load(gzip.open(f))["daily"]
    wrows.append(pd.DataFrame({"state": st, "date": pd.to_datetime(d["time"]),
                               "temp": d["temperature_2m_mean"], "rh": d["relative_humidity_2m_mean"]}))
for f in glob.glob(str(RAW / "openmeteo_pm25" / "*" / "*.json.gz")):
    st = Path(f).name[:2]
    d = json.load(gzip.open(f))["hourly"]
    prows.append(pd.DataFrame({"state": st, "time": pd.to_datetime(d["time"]), "pm25": d["pm2_5"]}))
wx = pd.concat(wrows)
wx["ah"] = 6.112 * np.exp(17.67 * wx.temp / (wx.temp + 243.5)) * wx.rh * 2.1674 / (273.15 + wx.temp)
wx["week"] = wx.date + pd.to_timedelta((5 - wx.date.dt.weekday) % 7, unit="D")
R["weather"] = {"rows": int(len(wx)), "states": int(wx.state.nunique()), "from": str(wx.date.min().date()),
                "to": str(wx.date.max().date()), "missing_pct": round(float(wx[["temp", "rh"]].isna().mean().mean() * 100), 3),
                "ah_median": round(float(wx.ah.median()), 2), "ah_min": round(float(wx.ah.min()), 2), "ah_max": round(float(wx.ah.max()), 2)}
print("weather", R["weather"], flush=True)
wk = wx.groupby(["state", "week"], as_index=False).agg(temp_mean=("temp", "mean"), abs_humidity=("ah", "mean"))
frame = frame.merge(wk, on=["state", "week"], how="outer")

pm = pd.concat(prows)
R["pm25"] = {"rows": int(len(pm)), "states": int(pm.state.nunique()),
             "first_nonnull": str(pm.dropna().time.min().date()), "to": str(pm.time.max().date()),
             "missing_pct": round(float(pm.pm25.isna().mean() * 100), 2), "median": round(float(pm.pm25.median()), 2),
             "max": round(float(pm.pm25.max()), 1)}
print("pm25", R["pm25"], flush=True)
pm["date"] = pm.time.dt.normalize()
pd_ = pm.groupby(["state", "date"], as_index=False).pm25.mean()
pd_["week"] = pd_.date + pd.to_timedelta((5 - pd_.date.dt.weekday) % 7, unit="D")
frame = frame.merge(pd_.groupby(["state", "week"], as_index=False).agg(pm25_mean=("pm25", "mean"), pm25_max=("pm25", "max")),
                    on=["state", "week"], how="left")

# ---------- EPA + dan so + FluVaxView ----------
z = zipfile.ZipFile(latest("epa_airdata", "daily_88101_2024.zip"))
epa = pd.read_csv(z.open(z.namelist()[0]), low_memory=False)
R["epa"] = {"rows": int(len(epa)), "columns": list(epa.columns), "states": int(epa["State Name"].nunique()),
            "sites": int(epa[["State Code", "County Code", "Site Num"]].drop_duplicates().shape[0]),
            "from": str(epa["Date Local"].min()), "to": str(epa["Date Local"].max())}
print("epa", R["epa"], flush=True)
pop = pd.read_csv(latest("population", "state_pop_2020_delphi.csv"))
R["population"] = {"rows": int(len(pop)), "columns": list(pop.columns), "total": int(pop["pop"].sum())}
pages = {}
for f in glob.glob(str(RAW / "fluvaxview_pages" / "*" / "*.html.gz")):
    html = gzip.open(f).read().decode("utf-8", "replace")
    pages[Path(f).name[:9]] = {"bytes": len(html), "tables": html.count("<table"), "alabama": html.count("Alabama")}
R["fluvaxview_pages"] = pages
print("fluvax", pages, flush=True)

frame = add_season(frame, "week").sort_values(["state", "week"])
frame.to_csv(OUT / "state_week_sample.csv.gz", index=False)
R["joined"] = {"rows": int(len(frame)), "columns": list(frame.columns), "states": int(frame.state.nunique())}

# ---------- do phu theo mua ----------
core = frame[frame.season >= "2010-11"]
cov = []
for season, g in core.groupby("season"):
    weeks = g.week.nunique()
    row = {"season": season, "weeks": int(weeks)}
    for c in ["ili_pct", "rate_flu", "ed_pct_flu", "lab_pct_pos", "abs_humidity", "pm25_mean"]:
        cnt = g[g[c].notna()].groupby("state").size()
        row[c + "_states70"] = int((cnt >= 0.7 * weeks).sum())
    cov.append(row)
R["coverage"] = cov
print(pd.DataFrame(cov).to_string(), flush=True)
s2526 = frame[(frame.season == "2025-26") & frame.ili_pct.notna()].state.unique()
R["ili_missing_2025_26"] = sorted(STATES - set(s2526))
s2627 = frame[(frame.season == "2026-27") & frame.ili_pct.notna()]
R["ili_2026_27"] = {"states": int(s2627.state.nunique()), "weeks": int(s2627.week.nunique()),
                    "missing": sorted(STATES - set(s2627.state))}
R["ili_first_week"] = {s: str(frame[(frame.state == s) & frame.ili_pct.notna()].week.min().date()) for s in ["fl", "la", "ny", "ca"]}
print("ili gaps", R["ili_missing_2025_26"], R["ili_2026_27"], R["ili_first_week"], flush=True)

# ---------- muc do sua so lieu ----------
rev = {}
curve_rows = []
for key, src, name in [("ili", "fluview_ilinet", "archive__ili__state.csv.gz"),
                       ("hosp", "nhsn", "archive__confirmed_admissions_flu_ew__state.csv.gz"),
                       ("ed", "nssp", "archive__pct_ed_visits_influenza__state.csv.gz")]:
    a = load(src, name)
    if "age_group" in a.columns:
        a = a[a.age_group == "all"]
    a = a[a.geo_value.isin(STATES)].dropna(subset=["value"])
    a["report_time"] = pd.to_datetime(a.report_time).dt.tz_localize(None)
    a = a[a.reference_time >= "2024-10-01"].sort_values("report_time")
    a["lag_w"] = ((a.report_time - a.reference_time).dt.days // 7).clip(lower=0)
    final = a.groupby(["geo_value", "reference_time"]).value.last().rename("final")
    first = a.groupby(["geo_value", "reference_time"]).agg(first=("value", "first"), versions=("value", "size"),
                                                           first_lag=("lag_w", "first"))
    j = first.join(final)
    j = j[j.final.abs() > 0]
    j = j[j.index.get_level_values(1) <= a.reference_time.max() - pd.Timedelta(weeks=8)]
    j["abs_pct"] = (j["first"] - j.final).abs() / j.final.abs() * 100
    rev[key] = {"keys": int(len(j)), "pct_keys_revised": round(float((j.versions > 1).mean() * 100), 1),
                "median_abs_pct_first_vs_final": round(float(j.abs_pct.median()), 2),
                "p90_abs_pct_first_vs_final": round(float(j.abs_pct.quantile(.9)), 2),
                "median_first_lag_weeks": float(j.first_lag.median())}
    for lag in range(0, 7):
        # gia tri moi nhat da biet tai do tre <= lag, so voi gia tri cuoi cung
        known = a[a.lag_w <= lag].groupby(["geo_value", "reference_time"]).value.last().rename("v")
        c = pd.concat([known, final], axis=1, join="inner")
        c = c[(c.final.abs() > 0) & (c.index.get_level_values(1) <= a.reference_time.max() - pd.Timedelta(weeks=8))]
        if len(c):
            curve_rows.append({"source": key, "lag_weeks": lag, "median_abs_pct": round(float(((c.v - c.final).abs() / c.final.abs() * 100).median()), 2),
                               "p90_abs_pct": round(float(((c.v - c.final).abs() / c.final.abs() * 100).quantile(.9)), 2), "n": int(len(c))})
R["revisions"] = rev
R["revision_curve"] = curve_rows
print(json.dumps(rev), flush=True)
print(pd.DataFrame(curve_rows).to_string(), flush=True)

# ---------- RQ1, RQ2: mua vu quoc gia ----------
f = frame.copy()
nat = f[f.season >= "2022-23"].groupby(["season", "week", "mmwr_week"], as_index=False).agg(hosp=("hosp_flu", "sum"))
popt = pop[pop.state_id.isin(STATES)]["pop"].sum()
nat["rate"] = nat.hosp / popt * 1e5
nat["season_week"] = nat.groupby("season").cumcount() + 1
sumr = []
for s, g in nat.groupby("season"):
    if s == "2026-27":
        continue
    p = g.loc[g.hosp.idxmax()]
    sumr.append({"season": s, "total": int(g.hosp.sum()), "peak_week": str(p.week.date()), "peak_rate": round(float(p.rate), 2), "season_week_peak": int(p.season_week)})
R["nat_seasons"] = sumr
R["nat_curve"] = nat[["season", "season_week", "rate"]].round(3).to_dict("records")
print(pd.DataFrame(sumr).to_string(), flush=True)
cur = nat[(nat.season == "2026-27") & (nat.hosp > 0)]  # bo tuan chua co so lieu nhap vien
R["current_season"] = {"weeks": int(len(cur)), "last_week": str(cur.week.max().date()) if len(cur) else None,
                       "last_rate": round(float(cur.rate.iloc[-1]), 3) if len(cur) else None}
print("current", R["current_season"], flush=True)

# RQ3: phan tan tuan dinh giua cac bang va do giong nhau cua duong cong
peak = []
for s, g in f[(f.season >= "2022-23") & (f.season <= "2025-26") & f.rate_flu.notna()].groupby("season"):
    idx = g.groupby("state").rate_flu.idxmax()
    w = g.loc[idx]
    order = ((w.week - w.week.min()).dt.days / 7)
    peak.append({"season": s, "first_peak": str(w.week.min().date()), "last_peak": str(w.week.max().date()),
                 "iqr_weeks": float(order.quantile(.75) - order.quantile(.25)),
                 "first_states": ",".join(sorted(w[w.week == w.week.min()].state))[:40]})
R["peak_spread"] = peak
print(pd.DataFrame(peak).to_string(), flush=True)
ili_pv = f[(f.season >= "2010-11") & (f.season != "2020-21")].pivot_table(index="week", columns="state", values="ili_pct")
good = ili_pv.columns[ili_pv.notna().mean() > .9]
corr = ili_pv[good].corr().where(np.triu(np.ones((len(good), len(good))), 1) == 1).stack()
R["ili_state_corr"] = {"states": int(len(good)), "median": round(float(corr.median()), 3), "p10": round(float(corr.quantile(.1)), 3)}
print(R["ili_state_corr"], flush=True)

# RQ4: tuong quan tho va sau khi loai mua vu
g = f[(f.season >= "2010-11") & (f.season != "2020-21") & f.ili_pct.notna() & f.abs_humidity.notna()].copy()
wk_all = f[f.abs_humidity.notna()].copy()
wk_all["ah_anom"] = wk_all.abs_humidity - wk_all.groupby(["state", "mmwr_week"]).abs_humidity.transform("mean")
f = f.merge(wk_all[["state", "week", "ah_anom"]], on=["state", "week"], how="left")
f["ah_anom_lag1"] = f.groupby("state").ah_anom.shift(1)
f["ah_lag1"] = f.groupby("state").abs_humidity.shift(1)
g = f[(f.season >= "2010-11") & (f.season != "2020-21") & f.ili_pct.notna()].copy()
g["log_ili"] = np.log(g.ili_pct + 0.1)
g["ili_anom"] = g.log_ili - g.groupby(["state", "mmwr_week"]).log_ili.transform("mean")


def med_corr(df, a, b):
    vals = df.groupby("state").apply(lambda x: x[a].corr(x[b]))
    return round(float(vals.median()), 3)


R["rq4_corr"] = {"raw_ah_vs_ili": med_corr(g, "ah_lag1", "log_ili"),
                 "anom_ah_vs_raw_ili": med_corr(g, "ah_anom_lag1", "log_ili"),
                 "anom_ah_vs_anom_ili": med_corr(g, "ah_anom_lag1", "ili_anom")}
lags = {}
for k in range(0, 5):
    f[f"a{k}"] = f.groupby("state").ah_anom.shift(k)
    gg = f[(f.season >= "2010-11") & (f.season != "2020-21") & f.ili_pct.notna()].copy()
    gg["log_ili"] = np.log(gg.ili_pct + 0.1)
    gg["ili_anom"] = gg.log_ili - gg.groupby(["state", "mmwr_week"]).log_ili.transform("mean")
    lags[k] = med_corr(gg, f"a{k}", "ili_anom")
R["rq4_lag_corr"] = lags
print(R["rq4_corr"], lags, flush=True)

# GLM thu: Poisson + offset, do overdispersion, sai so thuong va sai so robust theo bang
m = f[(f.season >= "2010-11") & (f.season != "2020-21") & f.num_ili.notna() & (f.num_patients > 0) & f.ah_anom_lag1.notna()].copy()
m["sw"] = m.mmwr_week.astype(str)
X = pd.get_dummies(m[["state", "season", "sw"]], drop_first=True, dtype=float)
X["ah_anom_lag1"] = m.ah_anom_lag1.values
X = sm.add_constant(X)
off = np.log(m.num_patients.values)
pois = sm.GLM(m.num_ili.values, X, family=sm.families.Poisson(), offset=off).fit()
disp = float(pois.pearson_chi2 / pois.df_resid)
mu = pois.mu
alpha = float(((m.num_ili.values - mu) ** 2 - mu).sum() / (mu ** 2).sum())
nb = sm.GLM(m.num_ili.values, X, family=sm.families.NegativeBinomial(alpha=max(alpha, 1e-3)), offset=off)
nb_naive = nb.fit()
nb_cl = nb.fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(m.state)[0]})
nb_disp = float(nb_naive.pearson_chi2 / nb_naive.df_resid)
b = float(nb_naive.params["ah_anom_lag1"])
R["glm"] = {"n": int(len(m)), "k": int(X.shape[1]), "poisson_pearson_chi2_df": round(disp, 2),
            "nb_alpha": round(alpha, 4), "nb_pearson_chi2_df": round(nb_disp, 3),
            "rr_per_1g": round(math.exp(b), 4),
            "se_naive": round(float(nb_naive.bse["ah_anom_lag1"]), 5), "se_cluster_state": round(float(nb_cl.bse["ah_anom_lag1"]), 5),
            "z_naive": round(float(b / nb_naive.bse["ah_anom_lag1"]), 2), "z_cluster": round(float(b / nb_cl.bse["ah_anom_lag1"]), 2),
            "aic_poisson": round(float(pois.aic)), "aic_nb": round(float(nb_naive.aic))}
print(R["glm"], flush=True)
# tu tuong quan phan du theo tuan
res = pd.Series(nb_naive.resid_pearson, index=m.index)
m["res"] = res
m["res_lag"] = m.groupby("state").res.shift(1)
R["glm"]["resid_lag1_autocorr"] = round(float(m[["res", "res_lag"]].corr().iloc[0, 1]), 3)
print("resid ac", R["glm"]["resid_lag1_autocorr"], flush=True)

# RQ5: canh bao tam: tuan sau rate >= 3/100k
THR = 3.0
h = f[f.rate_flu.notna() & (f.season >= "2022-23") & (f.season <= "2025-26")].copy().sort_values(["state", "week"])
h = h[(h.mmwr_week >= 40) | (h.mmwr_week <= 20)]
h["y"] = (h.groupby("state").rate_flu.shift(-1) >= THR).astype(float)
h.loc[h.groupby("state").rate_flu.shift(-1).isna(), "y"] = np.nan
h["d_rate"] = h.rate_flu - h.groupby("state").rate_flu.shift(1)
h["d_ed"] = h.ed_pct_flu - h.groupby("state").ed_pct_flu.shift(1)
h["log_rate"] = np.log1p(h.rate_flu)
FEATS = {"chi_nhap_vien": ["log_rate", "d_rate"], "them_cap_cuu": ["log_rate", "d_rate", "ed_pct_flu", "d_ed"]}
hh = h.dropna(subset=["y", "d_rate", "d_ed", "ed_pct_flu", "log_rate"])


def boot_ci(t, score, n=300):
    rng = np.random.default_rng(7)
    states = t.state.unique()
    groups = {s: i for s, i in t.groupby("state").indices.items()}
    vals = []
    y = t.y.values
    for _ in range(n):
        idx = np.concatenate([groups[s] for s in rng.choice(states, len(states))])
        if y[idx].min() != y[idx].max():
            vals.append(roc_auc_score(y[idx], score[idx]))
    return round(float(np.quantile(vals, .025)), 3), round(float(np.quantile(vals, .975)), 3)


rq5 = []
for test in ["2024-25", "2025-26"]:
    tr = hh[hh.season < test]
    te = hh[hh.season == test].reset_index(drop=True)
    row = {"test": test, "train_rows": int(len(tr)), "test_rows": int(len(te)), "positive_pct": round(float(te.y.mean() * 100), 1)}
    pers = te.rate_flu.values
    row["auc_persistence"] = round(float(roc_auc_score(te.y, pers)), 3)
    row["ci_persistence"] = boot_ci(te, pers)
    for nm, cols in FEATS.items():
        mdl = make_pipeline(StandardScaler(), LogisticRegression(max_iter=500)).fit(tr[cols], tr.y)
        p = mdl.predict_proba(te[cols])[:, 1]
        row["auc_" + nm] = round(float(roc_auc_score(te.y, p)), 3)
        row["ci_" + nm] = boot_ci(te, p)
        row["brier_" + nm] = round(float(brier_score_loss(te.y, p)), 4)
        row["mean_pred_" + nm] = round(float(p.mean()), 3)
    rq5.append(row)
R["rq5"] = {"threshold_per_100k": THR, "results": rq5}
print(json.dumps(rq5, indent=0), flush=True)

# NSSP so voi NHSN: chenh tuan dinh va do tre tuong quan
lead = []
bh = f[(f.season >= "2022-23") & (f.season <= "2025-26") & f.rate_flu.notna() & f.ed_pct_flu.notna()]
for (st, s), g2 in bh.groupby(["state", "season"]):
    if g2.rate_flu.max() > 0 and g2.ed_pct_flu.max() > 0:
        lead.append((g2.loc[g2.rate_flu.idxmax()].week - g2.loc[g2.ed_pct_flu.idxmax()].week).days / 7)
lead = pd.Series(lead)
R["ed_lead"] = {"n": int(len(lead)), "median_weeks_ed_before_hosp": float(lead.median()), "pct_ed_first": round(float((lead > 0).mean() * 100), 1),
                "pct_same": round(float((lead == 0).mean() * 100), 1), "pct_hosp_first": round(float((lead < 0).mean() * 100), 1)}
print(R["ed_lead"], flush=True)

(OUT / "profile_results.json").write_text(json.dumps(R, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print("done", flush=True)
