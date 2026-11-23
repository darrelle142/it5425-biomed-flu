"""Chuan bi du lieu cho TV4 (RQ4). Dac ta chot TRUOC khi xem ket qua (nhat ky Q12-Q14):

- Mua 2010-11 den 2025-26, bo 2020-21 (gan nhu khong co cum) va 2009-10, 2026-27 (khong du mua).
- Chi tuan mua 1-33 (MMWR 40-20): giai doan gia thuyet do am / PM2.5 co tac dung.
- Bo bang-mua thieu ILINet > 30% (FL 2010-2021, LA 2010-2016, DE 2010-11; 8 bang mua 2025-26).
- Bien moi truong dung do chenh so voi trung binh cung bang, cung tuan MMWR 2010-2025 (cung cong thuc ah_anomaly
  cua kho): ah_anomaly co san; ili_anomaly va pm25_epa_anomaly tinh o day.
- PM2.5 chi dung pm25_epa (khong dung pm25_mean ghep hai nguon); bien tre tu tinh bang shift theo bang.
- Vaccine dung flu_vax_pct_prev (do phu cuoi mua truoc, da biet tu dau mua); nghi le chi dung holiday_week.
"""
import numpy as np
import pandas as pd

from fluwatch.warehouse.load import AH_CLIMATOLOGY_YEARS, load_dim_state, load_flu_week

EXCLUDED_SEASONS = ("2009-10", "2020-21", "2026-27")
SEASON_WEEKS = (1, 33)
MAX_ILI_MISSING = 0.3
LAGS = range(0, 5)


def add_anomaly(df, col, out):
    """col tru trung binh cung (bang, tuan MMWR) cac nam AH_CLIMATOLOGY_YEARS; tuan 53 dung tuan 52."""
    y0, y1 = AH_CLIMATOLOGY_YEARS
    mw = df["mmwr_week"].where(df["mmwr_week"] != 53, 52)
    base = df[df["mmwr_year"].between(y0, y1)]
    clim = base.groupby(["state", mw.loc[base.index]])[col].mean().rename("_clim")
    clim.index.names = ["state", "_mw"]
    tmp = df.assign(_mw=mw).merge(clim.reset_index(), on=["state", "_mw"], how="left")
    df[out] = (tmp[col] - tmp["_clim"]).to_numpy()
    return df


def weekly_panel():
    """Bang x tuan day du (truoc khi loc), co do chenh va bien tre cua TV4. Kieu du lieu thuong (float, str)."""
    f = load_flu_week().sort_values(["state", "week"]).reset_index(drop=True)
    for c in ["num_ili", "num_patients", "ili_pct", "ah_anomaly", "pm25_epa", "flu_vax_pct_prev",
              "holiday_week", "lab_pct_pos", "mmwr_week", "mmwr_year", "season_week"]:
        f[c] = pd.to_numeric(f[c], errors="coerce").astype(float)
    f["state"] = f["state"].astype(str)
    f["season"] = f["season"].astype(str)

    f = add_anomaly(f, "ili_pct", "ili_anomaly")
    f = add_anomaly(f, "pm25_epa", "pm25_epa_anomaly")
    g = f.groupby("state")
    for k in LAGS:
        f[f"ah_anomaly_l{k}"] = g["ah_anomaly"].shift(k)
        f[f"pm25_epa_anomaly_l{k}"] = g["pm25_epa_anomaly"].shift(k)
    return f


def analysis_sample(f=None):
    """Loc theo Q12. Tra ve (du lieu da loc, bang dem loai tru de ghi vao bao cao)."""
    f = weekly_panel() if f is None else f
    steps = [("tat ca bang x tuan", len(f))]
    f = f[~f["season"].isin(EXCLUDED_SEASONS)]
    steps.append(("bo mua 2009-10, 2020-21, 2026-27", len(f)))
    f = f[f["season_week"].between(*SEASON_WEEKS)]
    steps.append(("chi tuan mua 1-33", len(f)))
    miss = f.groupby(["state", "season"])["ili_pct"].transform(lambda s: s.isna().mean())
    f = f[miss <= MAX_ILI_MISSING]
    steps.append(("bo bang-mua thieu ILINet > 30%", len(f)))
    f = f[f["num_patients"] > 0].dropna(subset=["num_ili", "ili_anomaly"])
    steps.append(("co so ILINet trong tuan", len(f)))
    return f.reset_index(drop=True), pd.DataFrame(steps, columns=["buoc", "so_dong"])


def contiguous_states():
    d = load_dim_state()
    return sorted(d.loc[d["contiguous"].astype(bool), "state"].astype(str))
