"""Test nhỏ cho phần TV5 (không cần dữ liệu thật). Chạy: python -m pytest tests -q"""
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from fluwatch.alerting.evaluate import auc_fast, delong_test, hosmer_lemeshow
from fluwatch.alerting.labels import _shift_forward, alert_level_from_cdc


def test_alert_level_mapping():
    s = alert_level_from_cdc(pd.Series([0, 1, 2, 3, 4, None]))
    assert s.tolist()[:5] == ["thap", "thap", "trung_binh", "cao", "cao"]
    assert pd.isna(s.iloc[5])


def test_shift_forward_by_state_and_date():
    w = pd.to_datetime(["2025-01-04", "2025-01-11", "2025-01-25"])  # thiếu tuần 18/01
    df = pd.DataFrame({"state": ["ca"] * 3 + ["tx"] * 3, "week": list(w) * 2, "v": [1.0, 2, 3, 10, 20, 30]})
    out = _shift_forward(df, "v", 1)
    # ca 04/01 -> 11/01 = 2; ca 11/01 -> 18/01 không có -> NaN; không lấy nhầm sang bang tx
    assert out.iloc[0] == 2 and np.isnan(out.iloc[1]) and np.isnan(out.iloc[2])
    assert out.iloc[3] == 20


def test_auc_matches_sklearn():
    rng = np.random.default_rng(0)
    y = rng.integers(0, 2, 500)
    s = y + rng.normal(0, 1, 500)
    s[:50] = np.round(s[:50])  # có giá trị trùng
    assert np.isclose(auc_fast(y, s), roc_auc_score(y, s))


def test_delong_detects_difference_only_when_real():
    rng = np.random.default_rng(1)
    y = rng.integers(0, 2, 800)
    strong, weak = y + rng.normal(0, 1, 800), 0.2 * y + rng.normal(0, 1, 800)
    assert delong_test(y, strong, weak)["p"] < 1e-6
    same = y + rng.normal(0, 1, 800)  # cùng độ mạnh, nhiễu khác
    assert delong_test(y, strong, same)["p"] > 0.05
    assert delong_test(y, strong, strong)["p"] is None  # giống hệt: không kiểm định được


def test_hosmer_lemeshow():
    rng = np.random.default_rng(2)
    p = rng.uniform(0.01, 0.99, 5000)
    y = (rng.uniform(size=5000) < p).astype(int)
    assert hosmer_lemeshow(y, p)["p_df_g_minus_2"] > 0.01
    assert hosmer_lemeshow(y, np.clip(p + 0.15, 0, 0.999))["p_df_g_minus_2"] < 1e-6


def test_onset_label_from_tv3_milestones():
    """Nhan khoi phat lay tu moc cua TV3: 1 neu khoi phat trong 2 tuan toi, khong tinh tuan da khoi phat."""
    from fluwatch.alerting.labels import onset_from_milestones
    m = pd.DataFrame({"state": ["ca"], "season": ["2025-26"], "onset_date": [pd.Timestamp("2025-11-22")],
                      "baseline": [2.0]})
    o = onset_from_milestones(m)
    weeks = pd.to_datetime(["2025-11-01", "2025-11-08", "2025-11-15", "2025-11-22"])
    dt = (o["onset_week_ili"].iloc[0] - pd.Series(weeks)).dt.days
    y = np.where(dt > 0, (dt <= 14).astype(float), np.nan)
    assert y[0] == 0 and y[1] == 1 and y[2] == 1 and np.isnan(y[3])


# ---------- mô hình vận hành (live) và số liệu chương ----------
def _toy_df(seed=0):
    """Bảng giả: 4 bang x 6 mùa x 30 tuần, nhãn vượt ngưỡng phụ thuộc rate_log."""
    from fluwatch.alerting.models import EXCEED_FEATS, ONSET_FEATS
    rng = np.random.default_rng(seed)
    seasons = ["2021-22", "2022-23", "2023-24", "2024-25", "2025-26", "2026-27"]
    rows = []
    for si, s in enumerate(seasons):
        start = pd.Timestamp(f"{2021 + si}-10-02")
        for st in ["ca", "tx", "ny", "wa"]:
            for k in range(30):
                rows.append({"state": st, "season": s, "week": start + pd.Timedelta(weeks=k), "season_week": k + 1})
    df = pd.DataFrame(rows)
    feats = sorted(set(sum(EXCEED_FEATS.values(), []) + sum(ONSET_FEATS.values(), [])) - {"season_week"})
    for c in feats:
        df[c] = rng.normal(size=len(df))
    for lab in ("y_exceed_1w", "y_exceed_2w", "y_onset_next2w"):
        df[lab] = (df["rate_log"] + rng.normal(0, 0.5, len(df)) > 1).astype(float)
    df["train_ok"] = True
    df["is_preliminary"] = False
    df["onset_week_ili"] = pd.NaT
    return df


def test_live_model_never_sees_current_season():
    from fluwatch.alerting.models import fit_all, last_complete_season
    df = _toy_df()
    assert last_complete_season(df) == "2025-26"
    # nếu mùa hiện tại bị học, đổi nhãn của nó sẽ đổi mô hình; mô hình vận hành phải giữ nguyên
    a = fit_all(df, train_last="2025-26")
    df2 = df.copy()
    cur = df2["season"] == "2026-27"
    df2.loc[cur, "y_exceed_1w"] = 1 - df2.loc[cur, "y_exceed_1w"]
    b = fit_all(df2, train_last="2025-26")
    ca = a[("y_exceed_1w", "base")]["model"][-1].coef_
    cb = b[("y_exceed_1w", "base")]["model"][-1].coef_
    assert np.allclose(ca, cb)
    assert a[("y_exceed_1w", "base")]["trained_through"] == "2025-26"


def test_forecast_uses_live_model_only_for_live_rows():
    from fluwatch.alerting.models import build_alert_forecast, fit_all
    df = _toy_df()
    fc = build_alert_forecast(df, fit_all(df), fit_all(df, train_last="2025-26"))
    t = pd.crosstab(fc["split"], fc["trained_through"])
    assert set(t.columns) == {"2024-25", "2025-26"}
    assert t.loc["live", "2025-26"] > 0 and t.loc["live"].get("2024-25", 0) == 0
    assert t.loc[["train", "test"], "2025-26"].sum() == 0
    assert fc["prob_exceed"].between(0, 1).all() and set(fc["horizon"]) == {1, 2}


def test_chapter_number_formatting():
    from fluwatch.alerting.chapter_numbers import _n, _p
    assert _n(0.9927) == "0,993"
    assert _p(6.2e-17) == "p < 10^-16"
    assert _p(0.0099) == "p = 0,010"
    assert _p(0.00055) == "p = 0,0006"
    assert _p(None) == "–"
