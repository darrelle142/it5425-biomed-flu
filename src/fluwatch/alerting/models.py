"""Mô hình cảnh báo (TV5): logistic dự đoán vượt ngưỡng 1-2 tuần và khởi phát trong 2 tuần.

Quy ước thời điểm: dự báo "phát hành" ở tuần t chỉ dùng số liệu có đến tuần t.
Chia theo MÙA: huấn luyện các mùa <= TRAIN_LAST, kiểm tra TEST_SEASON, mùa sau đó là 'live'.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, roc_curve
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from fluwatch.warehouse.load import ROOT

TRAIN_LAST = "2024-25"
TEST_SEASON = "2025-26"
EXCEED_TRAIN_FIRST = "2022-23"  # mùa đầu có đủ nhãn mức Cao thật (NHSN)

# Biến thể mô hình, thứ tự ưu tiên khi dự báo thật: full -> base -> nhsn
EXCEED_FEATS = {
    "nhsn": ["rate_log", "rate_delta", "ah_anomaly", "season_week"],
    "base": ["rate_log", "rate_delta", "ili_pct", "ili_delta", "ah_anomaly", "season_week"],
    "full": ["rate_log", "rate_delta", "ili_pct", "ili_delta", "ed_pct_flu", "wval", "ah_anomaly", "season_week"],
}
ONSET_FEATS = {
    "base": ["ili_ratio", "ili_delta", "ah_anomaly", "season_week"],
    "full": ["ili_ratio", "ili_delta", "ed_pct_flu", "wval", "ah_anomaly", "season_week"],
}
PRIORITY = ["full", "base", "nhsn"]


def high_thresholds() -> pd.Series:
    """Ngưỡng 'Cao' (= moderate_max, vượt là cdc_level >= 3) theo bang, chữ thường."""
    t = pd.read_csv(ROOT / "data" / "reference" / "cdc_level_thresholds.csv")
    t = t[t["virus"] == "Influenza"]
    return t.set_index(t["jurisdiction"].str.lower())["moderate_max"]


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    thr = df["state"].map(high_thresholds())
    ratio = df["rate_flu"] / thr
    ratio_prev = df["rate_flu_lag1"] / thr
    df["rate_ratio"] = ratio
    df["rate_log"] = np.log1p(ratio)
    df["rate_delta"] = np.log1p(ratio) - np.log1p(ratio_prev)
    df["ili_delta"] = df["ili_pct"] - df["ili_pct_lag1"]
    df["ili_ratio"] = df["ili_pct"] / df["ili_baseline"]
    return df


def make_model() -> object:
    return make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=1000))


def _rows(df, feats, label, season_mask):
    m = df["train_ok"] & season_mask & df[label].notna() & df[feats].notna().all(axis=1)
    return df[m]


def youden_threshold(y, p) -> float:
    fpr, tpr, thr = roc_curve(y, p)
    return float(thr[np.argmax(tpr - fpr)])


def fit_all(df: pd.DataFrame) -> dict:
    """Huấn luyện mọi biến thể. Trả {(tên_nhãn, biến_thể): {model, feats, threshold, n_train}}."""
    out = {}
    train_ex = df["season"].between(EXCEED_TRAIN_FIRST, TRAIN_LAST)
    train_on = df["season"] <= TRAIN_LAST
    specs = [(f"y_exceed_{h}w", v, EXCEED_FEATS[v], train_ex) for h in (1, 2) for v in EXCEED_FEATS]
    specs += [("y_onset_next2w", v, ONSET_FEATS[v], train_on) for v in ONSET_FEATS]
    for label, variant, feats, mask in specs:
        tr = _rows(df, feats, label, mask)
        if tr[label].nunique() < 2:
            continue
        mdl = make_model().fit(tr[feats], tr[label].astype(int))
        p = mdl.predict_proba(tr[feats])[:, 1]
        out[(label, variant)] = {
            "model": mdl, "feats": feats, "n_train": int(len(tr)), "n_pos": int(tr[label].sum()),
            "threshold": youden_threshold(tr[label].astype(int), p),
        }
    return out


def predict_best(df: pd.DataFrame, fitted: dict, label: str, order=PRIORITY) -> pd.DataFrame:
    """Mỗi dòng dùng biến thể ưu tiên cao nhất mà đủ đặc trưng. Trả cột prob, model, thr."""
    res = pd.DataFrame({"prob": np.nan, "model": None, "thr": np.nan}, index=df.index)
    for variant in order:
        key = (label, variant)
        if key not in fitted:
            continue
        f = fitted[key]
        todo = res["prob"].isna() & df[f["feats"]].notna().all(axis=1)
        if todo.any():
            res.loc[todo, "prob"] = f["model"].predict_proba(df.loc[todo, f["feats"]])[:, 1]
            res.loc[todo, "model"] = variant
            res.loc[todo, "thr"] = f["threshold"]
    return res


def split_of(season: pd.Series) -> pd.Series:
    return pd.Series(np.where(season <= TRAIN_LAST, "train", np.where(season == TEST_SEASON, "test", "live")),
                     index=season.index)


def quick_auc(df, fitted, label, variant, season_mask):
    """AUC nhanh để kiểm tra; đánh giá đầy đủ ở evaluate.py (B4)."""
    f = fitted[(label, variant)]
    te = _rows(df, f["feats"], label, season_mask)
    if te[label].nunique() < 2:
        return np.nan, len(te)
    return roc_auc_score(te[label].astype(int), f["model"].predict_proba(te[f["feats"]])[:, 1]), len(te)


def build_alert_forecast(df: pd.DataFrame, fitted: dict) -> pd.DataFrame:
    """Bảng alert_forecast: bang x tuần phát hành x tầm (1, 2)."""
    onset = predict_best(df, fitted, "y_onset_next2w", order=["full", "base"])
    # đã khởi phát (và đã xác nhận) thì xác suất khởi phát không còn ý nghĩa
    started = df["onset_week_ili"].notna() & (df["onset_week_ili"] + pd.Timedelta(days=14) <= df["week"])
    onset.loc[started, "prob"] = np.nan

    frames = []
    for h in (1, 2):
        e = predict_best(df, fitted, f"y_exceed_{h}w")
        p, t = e["prob"], e["thr"]
        level = np.where(p >= t, "cao", np.where(p >= t / 2, "trung_binh", "thap"))
        fr = pd.DataFrame({
            "state": df["state"], "week": df["week"], "horizon": h,
            "prob_exceed": p, "prob_onset": onset["prob"],
            "alert_level": np.where(p.notna(), level, None),
            "target_week": df["week"] + pd.Timedelta(weeks=h),
            "model": e["model"], "split": split_of(df["season"]),
            "is_preliminary": df["is_preliminary"], "is_stub": False,
        })
        frames.append(fr[p.notna()])
    out = pd.concat(frames, ignore_index=True)
    return out.sort_values(["state", "week", "horizon"]).reset_index(drop=True)
