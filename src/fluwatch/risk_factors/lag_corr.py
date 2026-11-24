"""Tuong quan tre (nhat ky Q13).

Spearman giua do chenh cua yeu to o tuan t-k va ili_anomaly o tuan t, k = 0-4. Truoc khi tinh, tru trung binh theo
bang x mua o ca hai bien (khu thay doi muc nen ILI sau COVID va khac biet giua cac mua). Tinh rieng tung bang roi lay
trung vi giua cac bang; khoang tin cay 95% bootstrap theo bang (lay mau lai cac bang). Bao du 5 do tre, khong chon
do tre dep nhat.
"""
import numpy as np
import pandas as pd

from .data import LAGS

FACTORS = {"ah_anomaly": "Độ ẩm tuyệt đối (độ chênh)", "pm25_epa_anomaly": "PM2.5 EPA (độ chênh)"}
N_BOOT = 2000
MIN_WEEKS = 30


def _demean(s, keys):
    return s - s.groupby(keys).transform("mean")


def state_correlations(f):
    keys = [f["state"], f["season"]]
    y = _demean(f["ili_anomaly"], keys)
    rows = []
    for fac in FACTORS:
        for k in LAGS:
            x = _demean(f[f"{fac}_l{k}"], keys)
            d = pd.DataFrame({"state": f["state"], "x": x, "y": y}).dropna()
            for st, g in d.groupby("state"):
                if len(g) >= MIN_WEEKS:
                    rows.append(dict(factor=fac, lag_weeks=k, state=st, n=len(g),
                                     rho=g["x"].rank().corr(g["y"].rank())))
    return pd.DataFrame(rows)


def summarize(per_state, seed=2026):
    rng = np.random.default_rng(seed)
    out = []
    for (fac, k), g in per_state.groupby(["factor", "lag_weeks"]):
        r = g["rho"].to_numpy()
        boot = np.median(rng.choice(r, size=(N_BOOT, len(r)), replace=True), axis=1)
        out.append(dict(factor=fac, lag_weeks=k, n_states=len(r), rho_median=np.median(r),
                        ci_low=np.quantile(boot, 0.025), ci_high=np.quantile(boot, 0.975),
                        share_negative=(r < 0).mean()))
    return pd.DataFrame(out)
