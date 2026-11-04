"""Khao sat 6 bo du lieu nhom tai tay (data/raw/cdc_*, data/raw/census_*) va thu ghep voi bang mau.

Chay sau profile_sample.py. Ket qua ghi vao data/samples/dataset_results.json.
Moi nguong va dinh nghia o day la TAM, chi de danh gia tinh kha thi.
"""
import glob
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]


def latest(source, pattern="*"):
    """File moi nhat cua mot nguon tai tay: data/raw/<nguon>/<ngay>/<file>."""
    return sorted(glob.glob(str(ROOT / "data" / "raw" / source / "*" / pattern)))[-1]

OUT = ROOT / "data" / "samples"
RAW = ROOT / "data" / "raw"
R = {}

names = pd.read_csv(sorted(glob.glob(str(RAW / "population" / "*" / "state_pop_2020_delphi.csv")))[-1])
name2id = dict(zip(names.state_name, names.state_id))
f = pd.read_csv(OUT / "state_week_sample.csv.gz", parse_dates=["week"]).sort_values(["state", "week"])
UNITS = sorted(f.state.unique())

# 1. Dan so hang nam cua Census
p = pd.read_csv(latest("census_popest_state", "NST-EST2025-*.csv"))
p = p[p.SUMLEV == 40].copy()
p["state"] = p.NAME.map(name2id)
pop = p.melt(id_vars="state", value_vars=[f"POPESTIMATE{y}" for y in range(2020, 2026)], var_name="year", value_name="pop")
pop["year"] = pop.year.str[-4:].astype(int)
chg = p.set_index("state").eval("(POPESTIMATE2025 / POPESTIMATE2020 - 1) * 100").sort_values()
d20 = names.set_index("state_id")["pop"]
R["census_pop"] = {
    "states": int(p.state.notna().sum()), "years": "2020-2025",
    "unmatched": p[p.state.isna()].NAME.tolist(),
    "chg_2020_2025_pct": {"min": [chg.index[0], round(chg.iloc[0], 2)], "max": [chg.index[-1], round(chg.iloc[-1], 2)],
                          "median": round(float(chg.median()), 2)},
    "us_2025": int(p.POPESTIMATE2025.sum()),
    "delphi2020_vs_census2020_pct_median": round(float(((p.set_index("state").POPESTIMATE2020 / d20) - 1).abs().median() * 100), 3),
}

# 2. Dan so tung do thi (incorporated places)
x = pd.read_excel(latest("census_popest_places", "SUB-IP-EST*.xlsx"), header=None, skiprows=4)
x = x[x[0].astype(str).str.contains(", ")].iloc[:, [0, 7]]
x.columns = ["area", "pop2025"]
x[["place", "state_name"]] = x.area.str.rsplit(", ", n=1, expand=True)
x["state"] = x.state_name.map(name2id)
x = x.dropna(subset=["state", "pop2025"])
big = x.sort_values("pop2025", ascending=False).groupby("state").head(1).set_index("state")
mine = pd.read_csv(ROOT / "data" / "reference" / "cities_largest_per_state.csv").set_index("state")
mis = []
for s, row in mine.iterrows():
    top = big.loc[s, "place"] if s in big.index else None
    if top is None or not str(top).startswith(row.city):
        mis.append({"state": s, "mine": row.city, "census_largest": top})
top5 = x.sort_values("pop2025", ascending=False).groupby("state").head(5)
share = top5.groupby("state").pop2025.sum() / p.set_index("state").POPESTIMATE2025
R["census_places"] = {"places": int(len(x)), "states": int(x.state.nunique()), "mismatch_vs_my_list": mis,
                      "top5_share_of_state_pop_pct": {"median": round(float(share.median() * 100), 1),
                                                      "min": [share.idxmin(), round(float(share.min() * 100), 1)]}}

# 3. NHSN HRD day du
h = pd.read_csv(latest("cdc_nhsn_hrd", "*.csv"), low_memory=False)
h["week"] = pd.to_datetime(h["Week Ending Date"])
h["state"] = h["Geographic aggregation"].str.lower()
hs = h[h.state.isin(UNITS)].copy()
hs["Total Influenza Admissions"] = pd.to_numeric(hs["Total Influenza Admissions"].astype(str).str.replace(",", ""), errors="coerce")
cmp = hs[["state", "week", "Total Influenza Admissions", "Total number of Influenza Admissions per 100,000 population"]].merge(
    f[["state", "week", "hosp_flu", "rate_flu"]], on=["state", "week"]).dropna()
age_col = "Number of Adult Influenza Admissions, 65-74 years"
icu_col = "Total ICU Patients Hospitalized with Influenza"
def span(col):
    g = hs[hs[col].notna()].week
    return [str(g.min().date()), str(g.max().date()), int(g.nunique())] if len(g) else None
R["hrd"] = {
    "rows": int(len(h)), "cols": int(h.shape[1]), "geos": int(h.state.nunique()),
    "weeks": [str(h.week.min().date()), str(h.week.max().date()), int(h.week.nunique())],
    "match_counts_with_delphi_pct": round(float((cmp["Total Influenza Admissions"] == cmp.hosp_flu).mean() * 100), 2),
    "abs_diff_rate_median": round(float((cmp["Total number of Influenza Admissions per 100,000 population"] - cmp.rate_flu).abs().median()), 4),
    "abs_diff_rate_p99": round(float((cmp["Total number of Influenza Admissions per 100,000 population"] - cmp.rate_flu).abs().quantile(.99)), 4),
    "compared_rows": int(len(cmp)),
    "span_total_flu": span("Total Influenza Admissions"), "span_age_groups": span(age_col),
    "span_flu_icu": span(icu_col), "span_peds_flu": span("Total Pediatric Influenza Admissions"),
    "seasons_col": sorted(h["Respiratory Virus Season"].dropna().unique().tolist()),
}
# Ty le nhap vien theo tuoi, dinh mua 2024-25 va 2025-26 toan quoc
us = h[h.state == "usa"].set_index("week").sort_index()
ages = {"0-4": "Number of Pediatric Influenza Admissions, 0-4 years, per 100,000 population",
        "5-17": "Number of Pediatric Influenza Admissions, 5-17 years, per 100,000 population",
        "18-49": "Number of Adult Influenza Admissions, 18-49 years, per 100,000 population",
        "50-64": "Number of Adult Influenza Admissions, 50-64 years, per 100,000 population",
        "65-74": "Number of Adult Influenza Admissions, 65-74 years, per 100,000 population",
        "75+": "Number of Adult Influenza Admissions, 75+ years, per 100,000 population"}
peak = {}
for s, a, b in [("2024-25", "2024-10-01", "2025-05-31"), ("2025-26", "2025-10-01", "2026-05-31")]:
    g = us.loc[a:b]
    peak[s] = {k: round(float(g[c].max()), 2) for k, c in ages.items()}
R["hrd"]["us_peak_rate_by_age"] = peak

# 4. Muc do CDC
lv = pd.read_csv(latest("cdc_nhsn_levels", "*.csv"))
lv["state"] = lv.jurisdiction.str.lower()
lv["week"] = pd.to_datetime(lv.weekEndingDate)
order = ["Very Low", "Low", "Moderate", "High", "Very High"]
lvs = lv[lv.state.isin(UNITS) & lv.totalConfFluNewAdmPer100kLevel.isin(order)].copy()
lvs["k"] = lvs.totalConfFluNewAdmPer100kLevel.map({v: i for i, v in enumerate(order)})
# Muc co la nguong co dinh chung cho moi bang khong: kiem tra chong lan giua cac muc
over = []
for s, g in lvs.groupby("state"):
    vl, lo = g[g.k == 0].totalConfFluNewAdmPer100k, g[g.k >= 1].totalConfFluNewAdmPer100k
    if len(vl) and len(lo):
        over.append({"state": s, "max_very_low": float(vl.max()), "min_low_or_more": float(lo.min())})
ov = pd.DataFrame(over)
R["levels"] = {
    "weeks": [str(lv.week.min().date()), str(lv.week.max().date()), int(lv.week.nunique())],
    "jurisdictions": int(lv.state.nunique()),
    "flu_level_counts": lv.totalConfFluNewAdmPer100kLevel.value_counts().to_dict(),
    "rate_range_by_level": lvs.groupby("totalConfFluNewAdmPer100kLevel").totalConfFluNewAdmPer100k.agg(["min", "max"]).round(2).to_dict("index"),
    "states_with_both_levels": ov.to_dict("records"),
    "global_overlap": bool(lvs[lvs.k == 0].totalConfFluNewAdmPer100k.max() > lvs[lvs.k >= 1].totalConfFluNewAdmPer100k.min()),
}
c2 = lvs.merge(f[["state", "week", "rate_flu"]], on=["state", "week"]).dropna(subset=["rate_flu", "totalConfFluNewAdmPer100k"])
R["levels"]["abs_diff_rate_vs_delphi_median"] = round(float((c2.totalConfFluNewAdmPer100k - c2.rate_flu).abs().median()), 3)

# 5. Nuoc thai WVAL cum A
ww = pd.read_csv(latest("cdc_wastewater_wval", "*.csv"), low_memory=False)
ww = ww[ww.Pathogen_Target == "Influenza A virus"].copy()
ww["state"] = ww["State/Territory"].map(name2id)
ww["week"] = pd.to_datetime(ww.Week_End)
ww["wval"] = pd.to_numeric(ww.Site_WVAL, errors="coerce")
ww["popserv"] = pd.to_numeric(ww.Population_Served.astype(str).str.replace(",", ""), errors="coerce")
R["wval_raw"] = {"rows_fluA": int(len(ww)), "sites": int(ww.Site.nunique()), "states": int(ww.state.nunique()),
                 "unmatched_names": sorted(ww[ww.state.isna()]["State/Territory"].unique().tolist()),
                 "weeks": [str(ww.week.min().date()), str(ww.week.max().date())],
                 "wval_median_p99": [round(float(ww.wval.median()), 2), round(float(ww.wval.quantile(.99)), 2)],
                 "date_updated": ww.date_updated.unique().tolist()[:3],
                 "category_ranges": ww.groupby("Site_WVAL_Category").wval.agg(["min", "max"]).round(2).to_dict("index")}
ww = ww.dropna(subset=["state", "wval"])
ww["w"] = ww.popserv.fillna(ww.popserv.median())
sw = ww.groupby(["state", "week"]).apply(lambda g: pd.Series({"wval": np.average(g.wval, weights=g.w), "sites": len(g)}), include_groups=False).reset_index()
cov = sw[sw.week >= "2023-10-01"].groupby("state").sites.median()
R["wval_state"] = {"state_weeks": int(len(sw)), "units": int(sw.state.nunique()),
                   "sites_per_state_median": float(cov.median()), "states_lt3_sites": cov[cov < 3].index.tolist(),
                   "units_per_week_since_2023_10_median": float(sw[sw.week >= "2023-10-01"].groupby("week").state.nunique().median())}
sw.to_csv(OUT / "wval_state_week.csv.gz", index=False)
m = f.merge(sw, on=["state", "week"], how="left").sort_values(["state", "week"])
# Tuong quan va do tre: WVAL tuan t-k voi nhap vien tuan t
lagc = {}
for k in range(0, 4):
    m["wl"] = m.groupby("state").wval.shift(k)
    g = m[(m.season >= "2022-23") & (m.season <= "2025-26")].dropna(subset=["wl", "rate_flu"])
    lagc[k] = round(float(g.groupby("state").apply(lambda q: q.wl.corr(q.rate_flu), include_groups=False).median()), 3)
R["wval_lag_corr_median"] = lagc
# Dinh nuoc thai so voi dinh nhap vien
pk = []
for (s, se), g in m[(m.season >= "2022-23") & (m.season <= "2025-26")].groupby(["state", "season"]):
    g = g.dropna(subset=["wval", "rate_flu"])
    if len(g) > 20:
        pk.append((g.loc[g.rate_flu.idxmax(), "week"] - g.loc[g.wval.idxmax(), "week"]).days / 7)
pk = np.array(pk)
R["wval_peak_lead_weeks"] = {"pairs": int(len(pk)), "median": float(np.median(pk)), "pct_ww_earlier": round(float((pk > 0).mean() * 100), 1),
                             "pct_same": round(float((pk == 0).mean() * 100), 1), "pct_ww_later": round(float((pk < 0).mean() * 100), 1)}

# RQ5 lap lai voi bien nuoc thai, cung dinh nghia vuot nguong moi nhu profile_extras.py
THR = 3.0
q = m[m.rate_flu.notna() & (m.season >= "2022-23") & (m.season <= "2025-26")].copy()
q = q[(q.mmwr_week >= 40) | (q.mmwr_week <= 20)].sort_values(["state", "week"])
nxt = q.groupby("state").rate_flu.shift(-1)
q["y"] = (nxt >= THR).astype(float)
q.loc[nxt.isna(), "y"] = np.nan
q["d_rate"] = q.rate_flu - q.groupby("state").rate_flu.shift(1)
q["d_ed"] = q.ed_pct_flu - q.groupby("state").ed_pct_flu.shift(1)
q["log_rate"] = np.log1p(q.rate_flu)
q["log_wval"] = np.log1p(q.wval)
q["d_wval"] = q.log_wval - q.groupby("state").log_wval.shift(1)
q = q.dropna(subset=["y", "d_rate", "d_ed", "ed_pct_flu", "log_wval", "d_wval"])
risk = q[q.rate_flu < THR]
feats = {"base_growth_ed": ["log_rate", "d_rate", "ed_pct_flu", "d_ed"],
         "plus_wval": ["log_rate", "d_rate", "ed_pct_flu", "d_ed", "log_wval", "d_wval"],
         "growth_wval_no_ed": ["log_rate", "d_rate", "log_wval", "d_wval"],
         "growth_only": ["log_rate", "d_rate"]}


def boot_diff(t, p1, p2, n=400):
    rng = np.random.default_rng(7)
    idx = t.groupby("state").indices
    st = list(idx)
    y = t.y.values
    out = []
    for _ in range(n):
        b = np.concatenate([idx[s] for s in rng.choice(st, len(st))])
        if 0 < y[b].sum() < len(b):
            out.append(roc_auc_score(y[b], p2[b]) - roc_auc_score(y[b], p1[b]))
    return [round(float(np.quantile(out, .025)), 3), round(float(np.quantile(out, .975)), 3)]


res = []
for test in ["2024-25", "2025-26"]:
    tr, te = risk[risk.season < test], risk[risk.season == test].reset_index(drop=True)
    row = {"test": test, "rows": int(len(te)), "events": int(te.y.sum()), "units": int(te.state.nunique())}
    pr = {}
    for k, cols in feats.items():
        pr[k] = make_pipeline(StandardScaler(), LogisticRegression(max_iter=500)).fit(tr[cols], tr.y).predict_proba(te[cols])[:, 1]
        row[k] = round(float(roc_auc_score(te.y, pr[k])), 3)
    row["diff_plus_wval_ci"] = boot_diff(te, pr["base_growth_ed"], pr["plus_wval"])
    row["diff_wval_vs_growth_ci"] = boot_diff(te, pr["growth_only"], pr["growth_wval_no_ed"])
    res.append(row)
R["rq5_with_wval"] = res

# 6. Do phu vaccine theo bang
vx = pd.read_csv(latest("cdc_fluvax_coverage", "*.csv"), dtype=str)
v = vx[(vx.Vaccine == "Seasonal Influenza") & (vx["Geography Type"] == "States/Local Areas") &
       vx.Dimension.isin([">=6 Months", "Greater than 6 Months flu"])].copy()  # mua 2023-24 dung nhan thu hai
v["state"] = v.Geography.map(name2id)
v["est"] = pd.to_numeric(v["Estimate (%)"], errors="coerce")
v["m"] = v.Month.astype(int)
v["mo"] = (v.m - 7) % 12  # thang 7 = 0 ... thang 6 = 11: thu tu trong mua
v = v.dropna(subset=["state"])
fin = v.sort_values("mo").groupby(["state", "Season/Survey Year"]).tail(1)
fin = fin[fin.state.isin(UNITS)]
R["vaccine"] = {
    "rows": int(len(vx)), "geo_types": vx["Geography Type"].value_counts().to_dict(),
    "seasons_state": sorted(fin["Season/Survey Year"].unique().tolist()),
    "units_per_season": fin.groupby("Season/Survey Year").state.nunique().to_dict(),
    "final_month_counts": fin.Month.value_counts().to_dict(),
    "nr_share_pct": round(float(v.est.isna().mean() * 100), 1),
    "non_state_geos": sorted(set(v.Geography) - set(names.state_name))[:20],
    "dims": vx[vx["Geography Type"] == "States/Local Areas"]["Dimension Type"].value_counts().to_dict(),
}
fin = fin.rename(columns={"Season/Survey Year": "season"})[["state", "season", "est", "Month"]]
fin.to_csv(OUT / "vaccine_state_season.csv", index=False)
cs = fin.groupby("season").est.agg(["median", "min", "max"]).round(1)
R["vaccine"]["coverage_by_season"] = cs.loc[[s for s in cs.index if s >= "2018-19"]].to_dict("index")
# Lien he sinh thai trong tung mua: do phu va gang nang cua mua
sev = f[(f.mmwr_week >= 40) | (f.mmwr_week <= 20)].groupby(["state", "season"]).agg(
    cum_rate=("rate_flu", "sum"), peak_ili=("ili_pct", "max"), n_rate=("rate_flu", "count")).reset_index()
j = sev.merge(fin, on=["state", "season"])
rows = []
for s, g in j.groupby("season"):
    g = g.dropna(subset=["est"])
    g1 = g[g.n_rate > 25]
    r1 = spearmanr(g1.est, g1.cum_rate) if len(g1) > 20 else None
    g2 = g.dropna(subset=["peak_ili", "est"])
    r2 = spearmanr(g2.est, g2.peak_ili) if len(g2) > 20 else None
    rows.append({"season": s, "n_hosp": int(len(g1)), "rho_cum_hosp": round(float(r1[0]), 3) if r1 else None,
                 "p_cum_hosp": round(float(r1[1]), 3) if r1 else None,
                 "n_ili": int(len(g2)), "rho_peak_ili": round(float(r2[0]), 3) if r2 else None})
R["vaccine_vs_severity"] = [r for r in rows if r["season"] >= "2016-17"]
# Tuong quan voi tuoi gia (dan so) co the gay nhieu: kiem tra do phu so voi % 65+ khong co, nen chi ghi chu

(OUT / "dataset_results.json").write_text(json.dumps(R, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print(json.dumps(R, ensure_ascii=False, indent=1, default=str))
