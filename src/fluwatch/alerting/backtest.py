"""Backtest as-published mùa TEST_SEASON (TV5).

Với mỗi tuần phát hành t: chỉ dùng giá trị ILINet / NHSN đã được công bố đến ngày t + PUBLISH_LAG_DAYS
(lấy bản công bố mới nhất có report_time <= ngày đó, từ raw/*/archive__*), dự báo t+1 và t+2,
rồi so với kết quả thật (số đã sửa). So với dự báo hồi cứu (số đã sửa) trên CÙNG các dòng.
Không có lịch sử sửa số cho wval, ah_anomaly: dùng bản cuối (ghi trong problem.txt).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from fluwatch.alerting.evaluate import auc_fast, bootstrap_auc_by_state, brier, delong_test
from fluwatch.alerting.models import TEST_SEASON, high_thresholds
from fluwatch.warehouse.load import ROOT

PUBLISH_LAG_DAYS = 7
SOURCES = {"ili": ("fluview_ilinet", "archive__ili__state.csv.gz"),
           "nhsn": ("nhsn", "archive__confirmed_admissions_flu_ew__state.csv.gz")}
VARIANTS = ["nhsn", "base"]


def load_archives() -> dict[str, pd.DataFrame] | None:
    out = {}
    for key, (folder, fname) in SOURCES.items():
        dirs = sorted((ROOT / "data" / "raw" / folder).glob("*/" + fname)) if (ROOT / "data" / "raw" / folder).exists() else []
        if not dirs:
            return None
        a = pd.read_csv(dirs[-1])  # bản tải mới nhất chứa lịch sử sửa số đầy đủ nhất
        if "age_group" in a:
            a = a[a["age_group"] == "all"]
        a["rt"] = pd.to_datetime(a["report_time"].str[:10])
        a["ref"] = pd.to_datetime(a["reference_time"])
        out[key] = a[["geo_value", "ref", "rt", "value"]]
    return out


def _asof(a: pd.DataFrame, t: pd.Timestamp) -> pd.DataFrame:
    """state, giá trị của tuần t và t-1 theo bản công bố mới nhất đến t + lag."""
    cutoff = t + pd.Timedelta(days=PUBLISH_LAG_DAYS)
    refs = [t, t - pd.Timedelta(weeks=1)]
    s = a[(a["rt"] <= cutoff) & a["ref"].isin(refs)].sort_values("rt").groupby(["geo_value", "ref"], as_index=False)["value"].last()
    p = s.pivot(index="geo_value", columns="ref", values="value").reindex(columns=refs)
    return pd.DataFrame({"cur": p[refs[0]], "prev": p[refs[1]]})


def hosp_to_rate_factor(df: pd.DataFrame) -> pd.Series:
    x = df[(df["hosp_flu"] >= 10) & df["rate_flu"].notna()]
    return (x["rate_flu"] / x["hosp_flu"]).groupby(x["state"]).median()


def asof_features(df: pd.DataFrame, arch: dict) -> pd.DataFrame:
    """Đặc trưng as-published cho mọi (bang, tuần) của mùa test."""
    thr, fac = high_thresholds(), hosp_to_rate_factor(df)
    weeks = sorted(df.loc[df["season"] == TEST_SEASON, "week"].unique())
    rows = []
    for t in weeks:
        t = pd.Timestamp(t)
        ili, nh = _asof(arch["ili"], t), _asof(arch["nhsn"], t)
        f = pd.DataFrame({"ili_pct_a": ili["cur"], "ili_prev_a": ili["prev"], "hosp_a": nh["cur"], "hosp_prev_a": nh["prev"]})
        f.index.name = "state"
        f = f.reset_index()
        f["week"] = t
        rows.append(f)
    a = pd.concat(rows, ignore_index=True)
    a["thr"] = a["state"].map(thr)
    a["fac"] = a["state"].map(fac)
    ratio, ratio_prev = a["hosp_a"] * a["fac"] / a["thr"], a["hosp_prev_a"] * a["fac"] / a["thr"]
    a["rate_ratio_a"] = ratio
    a["rate_log"] = np.log1p(ratio)
    a["rate_delta"] = np.log1p(ratio) - np.log1p(ratio_prev)
    a["ili_pct"] = a["ili_pct_a"]
    a["ili_delta"] = a["ili_pct_a"] - a["ili_prev_a"]
    return a


def run_backtest(df: pd.DataFrame, fitted: dict) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    arch = load_archives()
    if arch is None:
        return {"skipped": "thiếu data/raw/*/archive__* (python scripts/download_data.py)"}, pd.DataFrame(), pd.DataFrame()
    af = asof_features(df, arch)
    base = df[df["train_ok"] & (df["season"] == TEST_SEASON)][
        ["state", "week", "season_week", "ah_anomaly", "cdc_level", "y_exceed_1w", "y_exceed_2w",
         "rate_log", "rate_delta", "ili_pct", "ili_delta"]].rename(
        columns={"rate_log": "rate_log_f", "rate_delta": "rate_delta_f", "ili_pct": "ili_pct_f", "ili_delta": "ili_delta_f"})
    bt = base.merge(af, on=["state", "week"], how="left")

    summary = {"publish_lag_days": PUBLISH_LAG_DAYS, "season": TEST_SEASON, "targets": {}}
    for h in (1, 2):
        lab = f"y_exceed_{h}w"
        res = {}
        for v in VARIANTS:
            f = fitted[(lab, v)]
            feats = f["feats"]
            fin = {c: c + "_f" if c in ("rate_log", "rate_delta", "ili_pct", "ili_delta") else c for c in feats}
            X_a = bt[feats]
            X_f = bt[[fin[c] for c in feats]].set_axis(feats, axis=1)
            # dự báo tính cho mọi dòng đủ đặc trưng (không đòi nhãn); chỉ khi chấm điểm mới đòi nhãn
            ma, mf = X_a.notna().all(axis=1), X_f.notna().all(axis=1)
            bt.loc[ma, f"p{h}_{v}_asof"] = f["model"].predict_proba(X_a[ma])[:, 1]
            bt.loc[mf, f"p{h}_{v}_retro"] = f["model"].predict_proba(X_f[mf])[:, 1]
            ok = ma & mf & bt[lab].notna()
            d = bt[ok]
            y, st = d[lab].astype(int).to_numpy(), d["state"].to_numpy()
            pers = (d["rate_ratio_a"] > 1).astype(float).to_numpy()
            pa, pr = d[f"p{h}_{v}_asof"].to_numpy(), d[f"p{h}_{v}_retro"].to_numpy()
            lo_a, hi_a, _ = bootstrap_auc_by_state(y, pa, st)
            res[v] = {"n": int(len(d)), "n_pos": int(y.sum()),
                      "auc_asof": auc_fast(y, pa), "auc_asof_ci": [lo_a, hi_a],
                      "auc_retro": auc_fast(y, pr), "brier_asof": brier(y, pa), "brier_retro": brier(y, pr),
                      "auc_persistence_asof": auc_fast(y, pers),
                      "auc_hien_trang_asof": auc_fast(y, d["rate_ratio_a"].to_numpy()),
                      "delong_asof_vs_hien_trang": delong_test(y, pa, d["rate_ratio_a"].to_numpy()),
                      "delong_asof_vs_retro": delong_test(y, pa, pr),
                      "delong_asof_vs_persistence": delong_test(y, pa, pers)}
        summary["targets"][lab] = res

    # thời gian báo trước (mô hình base, tầm 1 tuần, ngưỡng Youden của tập huấn luyện)
    # như pipeline thật: dùng bản base nếu có ILI, không thì bản nhsn (ngưỡng Youden riêng của từng bản)
    thr_b, thr_n = fitted[("y_exceed_1w", "base")]["threshold"], fitted[("y_exceed_1w", "nhsn")]["threshold"]
    use_base = bt["p1_base_asof"].notna()
    bt["p1_best_asof"] = np.where(use_base, bt["p1_base_asof"], bt["p1_nhsn_asof"])
    bt["thr_best"] = np.where(use_base, thr_b, thr_n)
    bt["model_best"] = np.where(use_base, "base", np.where(bt["p1_nhsn_asof"].notna(), "nhsn", None))
    thr1 = thr_b
    lead = []
    for state, g in bt.sort_values("week").groupby("state"):
        high = g.loc[g["cdc_level"] >= 3, "week"]
        alert = g.loc[g["p1_best_asof"] >= g["thr_best"], "week"]
        first_high = high.min() if len(high) else pd.NaT
        first_alert = alert.min() if len(alert) else pd.NaT
        lead.append({"state": state, "first_high": first_high, "first_alert": first_alert,
                     "lead_weeks": (first_high - first_alert).days / 7 if pd.notna(first_high) and pd.notna(first_alert) else np.nan})
    ld = pd.DataFrame(lead)
    reached = ld[ld["first_high"].notna()]
    has_data = bt.groupby("state")["p1_best_asof"].apply(lambda s: s.notna().any())
    never_high_alert = ld[ld["first_high"].isna() & ld["first_alert"].notna()]
    summary["alert_timing"] = {
        "threshold": thr1, "states_reached_high": int(len(reached)),
        "states_alerted_by_first_high": int((reached["lead_weeks"] >= 0).sum()),
        "states_alerted_after_first_high": int((reached["lead_weeks"] < 0).sum()),
        "states_reached_high_never_alerted": int(reached["first_alert"].isna().sum()),
        "lead_weeks_median": float(reached["lead_weeks"].median()),
        "lead_weeks_q25_q75": [float(reached["lead_weeks"].quantile(.25)), float(reached["lead_weeks"].quantile(.75))],
        "states_alerted_but_never_high": int(len(never_high_alert)),
        "states_with_asof_forecast": int(has_data.sum()),
    }
    return summary, bt, ld
