"""Nhãn cho mô hình cảnh báo (TV5).

build_labels(df) nhận bảng từ load_flu_week() và thêm các cột:
  ili_baseline                 : mức nền ILI (tự tính, dùng làm đặc trưng ili_ratio)
  onset_week_ili               : ngày tuần khởi phát. Mặc định lấy từ season_milestones.parquet của TV3 (một định nghĩa
                                 chung cho cả nhóm: 3 tuần ≥ mức nền + xét nghiệm dương tính ≥ 2% từ 2016-17);
                                 không có file thì tự tính như bản đầu (onset_source = 'tv5')
  alert_level                  : thap | trung_binh | cao (từ cdc_level)
  y_exceed_1w, y_exceed_2w     : 1 nếu 1 / 2 tuần sau bang ở mức Cao
  y_onset_next2w               : 1 nếu mùa khởi phát trong 2 tuần tới (chỉ tính tuần chưa khởi phát)
  train_ok                     : True nếu dòng dùng được để huấn luyện/đánh giá (bỏ số sơ bộ, 2020-21 và các tuần
                                 low_reporting: NHSN báo cáo ít 5-10/2024, nhãn mức CDC không đáng tin)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

EXCLUDED_SEASON = "2020-21"
SUMMER_WEEKS = (21, 39)  # tuần MMWR không có cúm, dùng tính mức nền
N_PRIOR = 3
MIN_PRIOR = 2
RUN = 3  # số tuần liên tiếp ≥ mức nền để tính là khởi phát


def alert_level_from_cdc(cdc_level: pd.Series) -> pd.Series:
    """0-1 -> thap, 2 -> trung_binh, 3-4 -> cao (thiếu giữ thiếu)."""
    lv = pd.to_numeric(cdc_level, errors="coerce")
    out = pd.Series(pd.NA, index=lv.index, dtype="object")
    out[lv <= 1] = "thap"
    out[lv == 2] = "trung_binh"
    out[lv >= 3] = "cao"
    return out


def _season_order(seasons) -> list[str]:
    return sorted(set(seasons))


def ili_baseline(df: pd.DataFrame) -> pd.DataFrame:
    """Mức nền ILI theo (state, season): mean + 2 SD của tuần hè 3 mùa trước (bỏ 2020-21)."""
    summer = df[df["mmwr_week"].between(*SUMMER_WEEKS) & df["ili_pct"].notna()]
    summer = summer[summer["season"] != EXCLUDED_SEASON]
    pooled = {k: g["ili_pct"].to_numpy() for k, g in summer.groupby(["state", "season"])}
    order = _season_order(df["season"])
    rows = []
    for state in df["state"].unique():
        for i, season in enumerate(order):
            prior = [s for s in order[:i] if s != EXCLUDED_SEASON][-N_PRIOR:]
            vals = [pooled[(state, s)] for s in prior if (state, s) in pooled]
            if len(vals) < MIN_PRIOR:
                base = np.nan
            else:
                x = np.concatenate(vals)
                base = x.mean() + 2 * x.std(ddof=1)
            rows.append((state, season, base))
    return pd.DataFrame(rows, columns=["state", "season", "ili_baseline"])


def _first_run(above: np.ndarray, run: int) -> int | None:
    """Chỉ số đầu tiên của `run` giá trị True liên tiếp, hoặc None."""
    n = len(above)
    for i in range(n - run + 1):
        if above[i : i + run].all():
            return i
    return None


def onset_weeks(df: pd.DataFrame, base: pd.DataFrame) -> pd.DataFrame:
    """Tuần khởi phát theo (state, season). Chuỗi có tuần thiếu ILI thì không tính 'liên tiếp' qua chỗ thiếu."""
    d = df[["state", "season", "week", "ili_pct"]].merge(base, on=["state", "season"], how="left")
    out = []
    for (state, season), g in d.groupby(["state", "season"]):
        g = g.sort_values("week")
        b = g["ili_baseline"].iloc[0]
        onset = pd.NaT
        if season != EXCLUDED_SEASON and pd.notna(b):
            above = (g["ili_pct"] >= b).to_numpy()  # NaN >= b là False
            i = _first_run(above, RUN)
            if i is not None:
                onset = g["week"].iloc[i]
        out.append((state, season, onset))
    return pd.DataFrame(out, columns=["state", "season", "onset_week_ili"])


def _shift_forward(df: pd.DataFrame, col: str, weeks: int) -> pd.Series:
    """Giá trị của `col` ở tuần t+weeks, cùng bang, ghép theo ngày (không theo vị trí dòng)."""
    right = df[["state", "week", col]].copy()
    right["week"] = right["week"] - pd.Timedelta(weeks=weeks)
    right = right.rename(columns={col: "_v"})
    m = df[["state", "week"]].merge(right, on=["state", "week"], how="left")
    return pd.Series(m["_v"].to_numpy(), index=df.index)


def onset_from_milestones(milestones: pd.DataFrame) -> pd.DataFrame:
    """Mốc khởi phát của TV3 -> (state, season, onset_week_ili = ngày, onset_baseline)."""
    m = milestones.copy()
    m["state"], m["season"] = m["state"].astype(str), m["season"].astype(str)
    return pd.DataFrame({"state": m["state"], "season": m["season"],
                         "onset_week_ili": pd.to_datetime(m["onset_date"]), "onset_baseline": m["baseline"]})


def build_labels(df: pd.DataFrame, milestones: pd.DataFrame | None = None) -> pd.DataFrame:
    df = df.sort_values(["state", "week"]).reset_index(drop=True).copy()

    base = ili_baseline(df)
    if milestones is not None:
        onset = onset_from_milestones(milestones)
        src = "tv3"
    else:
        onset = onset_weeks(df, base).merge(base.rename(columns={"ili_baseline": "onset_baseline"}),
                                            on=["state", "season"], how="left")
        src = "tv5"
    df = df.merge(base, on=["state", "season"], how="left").merge(onset, on=["state", "season"], how="left")
    df["onset_source"] = src

    df["alert_level"] = alert_level_from_cdc(df["cdc_level"])
    is_high = df["alert_level"].map({"cao": 1.0, "thap": 0.0, "trung_binh": 0.0})
    df["_high"] = is_high
    df["_prelim"] = df["is_preliminary"].astype(float)
    last_week = df["week"].max()

    for h in (1, 2):
        df[f"y_exceed_{h}w"] = _shift_forward(df, "_high", h)
        # tuần đích còn là số sơ bộ thì nhãn chưa đáng tin
        target_prelim = _shift_forward(df, "_prelim", h)
        df.loc[target_prelim == 1, f"y_exceed_{h}w"] = np.nan

    # khởi phát trong 2 tuần tới; chỉ xét tuần chưa khởi phát
    dt = (df["onset_week_ili"] - df["week"]).dt.days
    y = pd.Series(np.nan, index=df.index)
    has_onset = df["onset_week_ili"].notna()
    before = has_onset & (dt > 0)
    y[before] = (dt[before] <= 14).astype(float)
    # mùa không có khởi phát: nhãn 0 nếu đã đủ dữ liệu quan sát (t + 2 tuần + 3 tuần xác nhận)
    # chỉ khi bang đó thực sự có ILI (≥80% tuần của mùa); thiếu ILI thì để trống chứ không coi là "không khởi phát"
    ili_cov = df.groupby(["state", "season"])["ili_pct"].transform(lambda s: s.notna().mean())
    no_onset = ~has_onset & df["onset_baseline"].notna() & (df["season"] != EXCLUDED_SEASON) & (ili_cov >= 0.8)
    observed = (last_week - df["week"]).dt.days >= 28
    y[no_onset & observed] = 0.0
    df["y_onset_next2w"] = y

    low = df["low_reporting"].astype("boolean").fillna(False).astype(bool) if "low_reporting" in df else False
    df["train_ok"] = (~df["is_preliminary"].astype(bool)) & (df["season"] != EXCLUDED_SEASON) & ~low
    return df.drop(columns=["_high", "_prelim"])
