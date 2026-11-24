"""Đánh giá mô hình cảnh báo (TV5): ROC/AUC, bootstrap theo bang, DeLong, Brier, Hosmer-Lemeshow, Youden.

Đánh giá trên mùa TEST_SEASON, mọi mô hình so trên CÙNG tập dòng (có đủ đặc trưng của bản 'full').
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.metrics import average_precision_score, roc_curve

from fluwatch.alerting.models import EXCEED_FEATS, ONSET_FEATS, TEST_SEASON

N_BOOT = 1000
SEED = 20261123


# ---------- AUC và DeLong (Sun & Xu 2014) ----------
def _midrank(x: np.ndarray) -> np.ndarray:
    return stats.rankdata(x, method="average")


def auc_fast(y: np.ndarray, s: np.ndarray) -> float:
    n1 = int(y.sum())
    n0 = len(y) - n1
    r = _midrank(s)
    return float((r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def delong_components(y: np.ndarray, scores: np.ndarray):
    """scores: (k mô hình, n). Trả AUC (k,) và hiệp phương sai (k,k) của các AUC."""
    pos, neg = scores[:, y == 1], scores[:, y == 0]
    m, n = pos.shape[1], neg.shape[1]
    k = scores.shape[0]
    tx, ty, tz = (np.empty((k, m)), np.empty((k, n)), np.empty((k, m + n)))
    for r in range(k):
        tx[r], ty[r] = _midrank(pos[r]), _midrank(neg[r])
        tz[r] = _midrank(np.concatenate([pos[r], neg[r]]))
    aucs = tz[:, :m].sum(axis=1) / m / n - (m + 1.0) / 2.0 / n
    v01 = (tz[:, :m] - tx) / n
    v10 = 1.0 - (tz[:, m:] - ty) / m
    cov = np.atleast_2d(np.cov(v01)) / m + np.atleast_2d(np.cov(v10)) / n
    return aucs, cov


def delong_test(y, s1, s2) -> dict:
    """Kiểm định hai phía H0: AUC1 = AUC2 (hai ROC tương quan, cùng tập mẫu)."""
    aucs, cov = delong_components(y, np.vstack([s1, s2]))
    var = cov[0, 0] + cov[1, 1] - 2 * cov[0, 1]
    diff = float(aucs[0] - aucs[1])
    if var <= 1e-18:
        return {"auc_a": float(aucs[0]), "auc_b": float(aucs[1]), "diff": diff, "z": None, "p": None}
    z = diff / np.sqrt(var)
    return {"auc_a": float(aucs[0]), "auc_b": float(aucs[1]), "diff": diff, "z": float(z),
            "p": float(2 * stats.norm.sf(abs(z)))}


def bootstrap_auc_by_state(y, s, states, n_boot=N_BOOT, seed=SEED):
    """CI 95% percentile: rút lại các BANG (cụm) có hoàn lại, vì các tuần cùng bang không độc lập."""
    rng = np.random.default_rng(seed)
    groups = [np.flatnonzero(states == u) for u in np.unique(states)]
    vals = []
    for _ in range(n_boot):
        idx = np.concatenate([groups[i] for i in rng.integers(0, len(groups), len(groups))])
        yy = y[idx]
        if yy.min() == yy.max():
            continue
        vals.append(auc_fast(yy, s[idx]))
    lo, hi = np.percentile(vals, [2.5, 97.5])
    return float(lo), float(hi), len(vals)


# ---------- Hiệu chỉnh ----------
def brier(y, p) -> float:
    return float(np.mean((p - y) ** 2))


def hosmer_lemeshow(y, p, groups=10) -> dict:
    """Chia theo phân vị của p. df = g-2 (quy ước) và df = g (mẫu kiểm tra độc lập)."""
    d = pd.DataFrame({"y": y, "p": p})
    d["g"] = pd.qcut(d["p"].rank(method="first"), groups, labels=False)
    t = d.groupby("g").agg(n=("y", "size"), obs=("y", "sum"), exp=("p", "sum"), pbar=("p", "mean"))
    chi2 = float((((t.obs - t.exp) ** 2) / (t.n * t.pbar * (1 - t.pbar)).clip(lower=1e-12)).sum())
    g = len(t)
    return {"chi2": chi2, "groups": g, "p_df_g_minus_2": float(stats.chi2.sf(chi2, g - 2)),
            "p_df_g": float(stats.chi2.sf(chi2, g)),
            "table": t.reset_index().round(4).to_dict("records")}


def youden(y, s) -> float:
    fpr, tpr, thr = roc_curve(y, s)
    return float(thr[np.argmax(tpr - fpr)])


def _at(y, p, thr) -> dict:
    pred = p >= thr
    tp, fn = int((pred & (y == 1)).sum()), int((~pred & (y == 1)).sum())
    fp, tn = int((pred & (y == 0)).sum()), int((~pred & (y == 0)).sum())
    return {"threshold": float(thr), "sensitivity": tp / max(tp + fn, 1), "specificity": tn / max(tn + fp, 1),
            "ppv": tp / max(tp + fp, 1), "tp": tp, "fn": fn, "fp": fp, "tn": tn}


# ---------- Gom lại ----------
def _scores(df, fitted, label, variants):
    s = {}
    for v in variants:
        f = fitted[(label, v)]
        s[v] = f["model"].predict_proba(df[f["feats"]])[:, 1]
    return s


def _eval_target(df, fitted, label, variants, baselines, full_feats):
    te = df[df["train_ok"] & (df["season"] == TEST_SEASON) & df[label].notna() & df[full_feats].notna().all(axis=1)]
    te = te.reset_index(drop=True)
    y = te[label].astype(int).to_numpy()
    states = te["state"].to_numpy()
    scores = _scores(te, fitted, label, variants)
    for name, fn in baselines.items():
        scores[name] = fn(te)

    res = {"n": int(len(te)), "n_pos": int(y.sum()), "base_rate": float(y.mean()), "models": {}, "delong": []}
    roc_rows = []
    for name, s in scores.items():
        is_prob = name == "persistence" and label != "y_onset_next2w"
        lo, hi, nb = bootstrap_auc_by_state(y, s, states)
        m = {"auc": auc_fast(y, s), "auc_ci_low": lo, "auc_ci_high": hi, "boot_valid": nb,
             "average_precision": float(average_precision_score(y, s))}
        if name in variants:
            p = s
            thr_train = fitted[(label, name)]["threshold"]
            m.update({"brier": brier(y, p), "brier_skill_vs_base_rate": 1 - brier(y, p) / brier(y, np.full(len(y), y.mean())),
                      "hosmer_lemeshow": hosmer_lemeshow(y, p), "youden_threshold_train": thr_train,
                      "at_train_threshold": _at(y, p, thr_train), "youden_threshold_test": youden(y, p)})
        elif is_prob:
            m["brier"] = brier(y, s)
        res["models"][name] = m
        fpr, tpr, _ = roc_curve(y, s)
        roc_rows.append(pd.DataFrame({"fpr": fpr, "tpr": tpr, "model": name, "target": label}))

    pairs = [("full", "base"), ("base", "persistence"), ("base", "nhsn"), ("full", "persistence"),
             ("nhsn", "hien_trang"), ("base", "hien_trang"), ("full", "hien_trang")]
    for a, b in pairs:
        if a in scores and b in scores:
            res["delong"].append({"a": a, "b": b, **delong_test(y, scores[a], scores[b])})

    # chỉ các tuần chưa ở mức Cao (lúc cần cảnh báo sớm)
    ew = (te["cdc_level"] < 3).to_numpy() if label != "y_onset_next2w" else np.ones(len(te), bool)
    ye = y[ew]
    if label != "y_onset_next2w" and ye.min() != ye.max():
        e = {"n": int(ew.sum()), "n_pos": int(ye.sum()), "models": {}}
        for name in variants:
            lo, hi, _ = bootstrap_auc_by_state(ye, scores[name][ew], states[ew])
            e["models"][name] = {"auc": auc_fast(ye, scores[name][ew]), "auc_ci_low": lo, "auc_ci_high": hi}
        res["early_warning_not_yet_high"] = e
    return res, pd.concat(roc_rows, ignore_index=True)


def evaluate(df: pd.DataFrame, fitted: dict) -> tuple[dict, pd.DataFrame]:
    out = {"is_stub": False, "test_season": TEST_SEASON, "n_boot": N_BOOT, "bootstrap_unit": "state",
           "targets": {}}
    rocs = []
    ex_variants = [v for v in ("nhsn", "base", "full")]
    for h in (1, 2):
        label = f"y_exceed_{h}w"
        # hai mô hình nền: persistence (tuần này đã ở mức Cao: 0/1) và hien_trang (tỉ lệ nhập viện / ngưỡng Cao hiện
        # tại, liên tục) - mô hình nền mạnh: mô hình chỉ có ý nghĩa nếu hơn được việc nhìn số nhập viện hiện tại
        r, roc = _eval_target(df, fitted, label, ex_variants,
                              {"persistence": lambda t: (t["cdc_level"] >= 3).astype(float).to_numpy(),
                               "hien_trang": lambda t: t["rate_ratio"].to_numpy()}, EXCEED_FEATS["full"])
        out["targets"][label] = r
        rocs.append(roc)
    r, roc = _eval_target(df, fitted, "y_onset_next2w", ["base", "full"],
                          {"hien_trang": lambda t: t["ili_ratio"].to_numpy()}, ONSET_FEATS["full"])
    out["targets"]["y_onset_next2w"] = r
    rocs.append(roc)

    # khóa tóm tắt theo hợp đồng (mô hình chính: vượt ngưỡng 1 tuần, bản full)
    m = out["targets"]["y_exceed_1w"]["models"]["full"]
    out.update({"primary": "y_exceed_1w/full", "auc": m["auc"], "auc_ci": [m["auc_ci_low"], m["auc_ci_high"]],
                "brier": m["brier"], "p_hosmer_lemeshow": m["hosmer_lemeshow"]["p_df_g_minus_2"],
                "youden_threshold": m["youden_threshold_train"]})
    return out, pd.concat(rocs, ignore_index=True)
