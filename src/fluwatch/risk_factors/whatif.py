"""Kich ban what-if: do phu vaccine mua truoc tang 10 diem % (ke hoach v2 muc 7.1, muc dich 5).

Do lon hieu ung: bai bao medRxiv 2025 trong bang bang chung chi cho p-value, khong cho do lon, nen khong lay duoc
hieu ung tu bai bao. Kich ban dung rate ratio cua chinh nhom (mo hinh NB tre 0, KTC 95% sai so chuan cum) kem
khoang bat dinh. Day la so GIA LAP (is_synthetic = 1), chi de minh hoa tren dashboard, khong phai ket luan.

value_base = ili_pct that cua mua gan nhat da xong; value_scenario = value_base x RR (diem va hai dau KTC).
"""
import numpy as np
import pandas as pd

SCENARIO = "vax_plus10"
SEASON = "2025-26"


def build(sample, rr):
    r = rr[(rr["factor"] == "vax") & (rr["model"] == "nb_lag0")].iloc[0]
    d = sample[sample["season"] == SEASON][["state", "week", "ili_pct"]].dropna().copy()
    out = pd.DataFrame({
        "state": d["state"], "week": d["week"], "scenario": SCENARIO,
        "value_base": d["ili_pct"], "value_scenario": d["ili_pct"] * r["rr"],
        "value_scenario_lo": d["ili_pct"] * r["ci_low"], "value_scenario_hi": d["ili_pct"] * r["ci_high"],
        "rr_used": r["rr"], "rr_source": "nb_lag0 cua TV4 (KTC 95% sai so chuan cum)",
        "is_synthetic": 1, "sim_scenario": SCENARIO, "sim_seed": np.nan,
    })
    return out.reset_index(drop=True)
