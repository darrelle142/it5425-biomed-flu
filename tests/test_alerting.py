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
