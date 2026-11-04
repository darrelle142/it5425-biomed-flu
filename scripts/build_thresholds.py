"""Tach bang nguong muc do nhap vien cua CDC tu trang phuong phap HRD, kiem chung va thu lai RQ5.

Dau vao: data/raw/cdc_methods/<ngay>/hrd_data_methods.html.gz (crawl_missing.py tai ve).
Dau ra:
    data/reference/cdc_level_thresholds.csv     nguong theo bang x virus (canh tren cua 4 muc dau)
    data/samples/thresholds_results.json        kiem chung voi file muc do va ket qua RQ5
"""
import glob
import gzip
import html
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "samples"
REF = ROOT / "data" / "reference"
LEVELS = ["Very Low", "Low", "Moderate", "High", "Very High"]

src = sorted(glob.glob(str(RAW / "cdc_methods" / "*" / "hrd_data_methods.html.gz")))[-1]
page = gzip.open(src).read().decode("utf-8", "replace")
rows = []
for tb in re.findall(r"<table.*?</table>", page, flags=re.S):
    cells = [[html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", c))).strip()
              for c in re.findall(r"<t[hd].*?</t[hd]>", r, flags=re.S)] for r in re.findall(r"<tr.*?</tr>", tb, flags=re.S)]
    virus = cells[0][0]
    for c in cells[1:]:
        ups = [float(re.findall(r"[\d.]+", x)[-1]) for x in c[1:5]]  # canh tren cua Very Low..High
        rows.append({"virus": virus, "jurisdiction": c[0], "very_low_max": ups[0], "low_max": ups[1],
                     "moderate_max": ups[2], "high_max": ups[3]})
th = pd.DataFrame(rows)
th["source_file"] = str(Path(src).relative_to(ROOT)).replace("\\", "/")
REF.mkdir(exist_ok=True)
th.to_csv(REF / "cdc_level_thresholds.csv", index=False)
R = {"rows": len(th), "viruses": th.virus.value_counts().to_dict()}

flu = th[th.virus == "Influenza"].assign(state=lambda d: d.jurisdiction.str.lower()).set_index("state")
cuts = flu[["very_low_max", "low_max", "moderate_max", "high_max"]]
R["flu_distinct_threshold_sets"] = int(cuts.drop_duplicates().shape[0])


def level(state, rate):
    """Muc do (0..4) theo nguong CDC: 'Up to x' nghia la <= x."""
    if pd.isna(rate) or state not in cuts.index:
        return np.nan
    return int(np.searchsorted(cuts.loc[state].values, rate, side="left"))


# Kiem chung: tinh lai muc do tu ty le trong file muc do cua nhom
lv = pd.read_csv(sorted(glob.glob(str(RAW / "cdc_nhsn_levels" / "*" / "*.csv")))[-1])
lv = lv[lv.totalConfFluNewAdmPer100kLevel.isin(LEVELS)].copy()
lv["state"] = lv.jurisdiction.str.lower()
lv["k_cdc"] = lv.totalConfFluNewAdmPer100kLevel.map({v: i for i, v in enumerate(LEVELS)})
lv["k_mine"] = [level(s, r) for s, r in zip(lv.state, lv.totalConfFluNewAdmPer100k)]
v = lv.dropna(subset=["k_mine"])
R["validation"] = {"rows": int(len(v)), "agree_pct": round(float((v.k_cdc == v.k_mine).mean() * 100), 2),
                   "disagree": v[v.k_cdc != v.k_mine][["state", "weekEndingDate", "totalConfFluNewAdmPer100k",
                                                       "totalConfFluNewAdmPer100kLevel"]].head(10).to_dict("records")}

# Gan muc do cho toan bo lich su NHSN cua Delphi
f = pd.read_csv(OUT / "state_week_sample.csv.gz", parse_dates=["week"]).sort_values(["state", "week"])
f["level"] = [level(s, r) for s, r in zip(f.state, f.rate_flu)]
dist = f[f.season.between("2022-23", "2025-26")].groupby("season")["level"].apply(
    lambda s: s.value_counts(normalize=True).sort_index().round(3).to_dict()).unstack().fillna(0)
R["level_share_by_season"] = {s: {LEVELS[int(k)]: v for k, v in r.items()} for s, r in dist.to_dict("index").items()}
f[["state", "week", "season", "rate_flu", "level"]].to_csv(OUT / "cdc_level_state_week.csv.gz", index=False)

# RQ5 voi nhan dung ke hoach: tuan sau (va 2 tuan sau) dat muc High tro len, xet bang dang duoi High
q = f[f.rate_flu.notna() & f.season.between("2022-23", "2025-26")].copy()
q = q[(q.mmwr_week >= 40) | (q.mmwr_week <= 20)].sort_values(["state", "week"])
g = q.groupby("state")
q["d_rate"] = q.rate_flu - g.rate_flu.shift(1)
q["d_ed"] = q.ed_pct_flu - g.ed_pct_flu.shift(1)
q["log_rate"] = np.log1p(q.rate_flu)
q["gap_to_high"] = q.state.map(cuts.moderate_max) - q.rate_flu  # khoang cach toi nguong High
out = []
for h in [1, 2]:
    nl = g["level"].shift(-h)
    q[f"y{h}"] = np.where(nl.isna(), np.nan, (nl >= 3).astype(float))
    d = q.dropna(subset=[f"y{h}", "d_rate", "d_ed", "ed_pct_flu"])
    d = d[d.level < 3]
    feats = {"Tỷ lệ hiện tại": None, "Khoảng cách tới ngưỡng High": ["gap_to_high"],
             "Thêm tốc độ tăng": ["gap_to_high", "log_rate", "d_rate"],
             "Thêm cấp cứu": ["gap_to_high", "log_rate", "d_rate", "ed_pct_flu", "d_ed"]}
    for test in ["2024-25", "2025-26"]:
        tr, te = d[d.season < test], d[d.season == test]
        row = {"horizon_weeks": h, "test": test, "rows": int(len(te)), "events": int(te[f"y{h}"].sum())}
        for name, cols in feats.items():
            p = te.rate_flu.values if cols is None else make_pipeline(StandardScaler(), LogisticRegression(max_iter=500)) \
                .fit(tr[cols], tr[f"y{h}"]).predict_proba(te[cols])[:, 1]
            row[name] = round(float(roc_auc_score(te[f"y{h}"], p)), 3)
        out.append(row)
R["rq5_cdc_high"] = out

(OUT / "thresholds_results.json").write_text(json.dumps(R, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print(json.dumps(R, ensure_ascii=False, indent=1, default=str))
