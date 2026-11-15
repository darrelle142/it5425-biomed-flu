"""Phan dung chung cua warehouse: danh sach bang, tuan MMWR, mua, tim file raw, nhat ky lam sach."""
import datetime as dt
import json
import logging
import re
from pathlib import Path

import numpy as np
import pandas as pd

log = logging.getLogger("fluwatch.warehouse")

# ============================== Bang va vung ==============================

# Vung HHS (co dinh theo HHS); 50 bang + DC
HHS_REGION = {
    1: ["ct", "me", "ma", "nh", "ri", "vt"],
    2: ["nj", "ny"],
    3: ["de", "dc", "md", "pa", "va", "wv"],
    4: ["al", "fl", "ga", "ky", "ms", "nc", "sc", "tn"],
    5: ["il", "in", "mi", "mn", "oh", "wi"],
    6: ["ar", "la", "nm", "ok", "tx"],
    7: ["ia", "ks", "mo", "ne"],
    8: ["co", "mt", "nd", "sd", "ut", "wy"],
    9: ["az", "ca", "hi", "nv"],
    10: ["ak", "id", "or", "wa"],
}
STATE_TO_HHS = {s: r for r, states in HHS_REGION.items() for s in states}
STATES = sorted(STATE_TO_HHS)          # 51 ma: 50 bang + DC
NON_CONTIGUOUS = {"ak", "hi"}


def state_names(paths):
    """Bang ten bang day du -> ma 2 chu viet thuong (raw/population, 50 bang + DC + lanh tho)."""
    f = latest_raw(paths, "population", "state_pop_2020_delphi", ".csv")
    pop = pd.read_csv(f)
    return dict(zip(pop.state_name.str.lower(), pop.state_id.str.lower())), f


# ============================== Tuan MMWR va mua ==============================

def mmwr_week1_end(year):
    """Ngay thu Bay ket thuc tuan MMWR 1 cua nam: tuan CN-T7 chua ngay 4/1."""
    jan4 = dt.date(year, 1, 4)
    return jan4 + dt.timedelta(days=(5 - jan4.weekday()) % 7)


def to_saturday(dates):
    """Ngay bat ky -> thu Bay ket thuc tuan MMWR (CN-T7) chua ngay do."""
    d = pd.to_datetime(dates)
    return (d + pd.to_timedelta((5 - d.dt.weekday) % 7, unit="D")).dt.normalize()


def mmwr_year_week(week):
    """Series thu Bay -> (mmwr_year, mmwr_week). Nam MMWR = nam cua ngay thu Tu trong tuan."""
    week = pd.to_datetime(week)
    uniq = pd.Series(week.dropna().unique())
    rows = {}
    for d in uniq:
        y = (d - pd.Timedelta(days=3)).year
        rows[d] = (y, (d.date() - mmwr_week1_end(y)).days // 7 + 1)
    yr = week.map(lambda d: rows.get(d, (pd.NA, pd.NA))[0])
    wk = week.map(lambda d: rows.get(d, (pd.NA, pd.NA))[1])
    return yr.astype("Int64"), wk.astype("Int64")


def season_of(week):
    """Series thu Bay -> (season 'YYYY-YY', season_week); mua bat dau o tuan MMWR 40 (season_week = 1)."""
    week = pd.to_datetime(week)
    out_season = pd.Series(pd.NA, index=week.index, dtype="string")
    out_sw = pd.Series(pd.NA, index=week.index, dtype="Int64")
    if week.notna().any():
        for y in range(int(week.dt.year.min()) - 1, int(week.dt.year.max()) + 1):
            start = pd.Timestamp(mmwr_week1_end(y) + dt.timedelta(weeks=39))
            end = pd.Timestamp(mmwr_week1_end(y + 1) + dt.timedelta(weeks=39))
            m = (week >= start) & (week < end)
            out_season[m] = f"{y}-{(y + 1) % 100:02d}"
            out_sw[m] = ((week[m] - start).dt.days // 7 + 1).astype("int64")
    return out_season, out_sw


def add_time_keys(df, week="week"):
    """Them epiweek (YYYYWW), season, season_week vao bang co cot tuan (thu Bay)."""
    df = df.copy()
    y, w = mmwr_year_week(df[week])
    df["epiweek"] = (y * 100 + w).astype("Int64")
    df["season"], df["season_week"] = season_of(df[week])
    return df


# ============================== File raw ==============================

_STAMP = re.compile(r"_(\d{6})$")


def raw_files(paths, source, stem, ext):
    """Moi ban cua mot file raw, xep tu cu den moi.

    Thu tu: ngay tai (thu muc), roi ban tai lai trong ngay (<stem>_HHMMSS<ext>, store.py khong ghi de).
    """
    out = []
    for p in (paths.raw / source).glob(f"*/{stem}*{ext}"):
        name = p.name[: -len(ext)]
        if name == stem:
            out.append(((p.parent.name, ""), p))
        elif name.startswith(stem) and _STAMP.fullmatch(name[len(stem):]):
            out.append(((p.parent.name, name[len(stem) + 1:]), p))
    return [p for _, p in sorted(out)]


def latest_raw(paths, source, stem, ext):
    files = raw_files(paths, source, stem, ext)
    if not files:
        raise FileNotFoundError(
            f"Khong thay data/raw/{source}/*/{stem}{ext}. Chay: python scripts/download_data.py (tai ca raw/)")
    return files[-1]


def rel(paths, p):
    """Duong dan tuong doi tu thu muc goc (ghi vao nhat ky / lineage)."""
    try:
        return Path(p).resolve().relative_to(paths.root.resolve()).as_posix()
    except ValueError:
        return str(p)


# ============================== Nhat ky lam sach ==============================

class CleanLog:
    """Ghi lai moi thao tac lam bien doi du lieu (bo dong, dat thieu, bo trung) cho tung bang clean/."""

    def __init__(self):
        self.tables = {}

    def table(self, name):
        return self.tables.setdefault(name, {"sources": [], "steps": []})

    def source(self, name, paths, p):
        self.table(name)["sources"].append(rel(paths, p))

    def step(self, name, action, n, detail=""):
        n = int(n)
        self.table(name)["steps"].append({"action": action, "rows": n, "detail": detail})
        if n:
            log.info("[%s] %s: %d dong%s", name, action, n, f" ({detail})" if detail else "")

    def summary(self, name, df, keys):
        t = self.table(name)
        t["rows"] = int(len(df))
        t["columns"] = list(df.columns)
        t["keys"] = keys
        if "state" in df:
            t["states"] = int(df["state"].nunique())
        wk = "week" if "week" in df else None
        if wk:
            t["range"] = [str(df[wk].min().date()), str(df[wk].max().date())]
        elif "season" in df:
            t["range"] = [str(df["season"].min()), str(df["season"].max())]
        t["missing_pct"] = {c: round(float(df[c].isna().mean() * 100), 2)
                            for c in df.columns if c not in keys and df[c].isna().any()}

    def write(self, path):
        path.write_text(json.dumps(self.tables, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


def keep_states(df, name, clog, col="state", what=""):
    """state viet thuong, chi giu 50 bang + DC; ghi lai cac ma bi loai (GU, VI, PR, nyc...)."""
    df = df.copy()
    df[col] = df[col].astype("string").str.strip().str.lower()
    bad = ~df[col].isin(STATES)
    if bad.any():
        codes = df.loc[bad, col].fillna("<trong>").value_counts().sort_index()
        clog.step(name, f"{what + ': ' if what else ''}bo ma ngoai 50 bang + DC", bad.sum(),
                  ", ".join(f"{k}:{v}" for k, v in codes.items()))
    return df[~bad]


def negative_to_na(df, cols, name, clog):
    """Gia tri am o dai luong khong the am (%, so ca, PM2.5...) -> thieu, co ghi log."""
    for c in cols:
        neg = df[c] < 0
        if neg.any():
            clog.step(name, f"{c} am -> thieu", neg.sum(), f"min={df.loc[neg, c].min():.3g}")
            df.loc[neg, c] = np.nan
    return df


def dedupe(df, keys, name, clog, order=None):
    """Bo dong trung khoa; giu dong sau cung theo `order` (vd. ngay cong bo)."""
    if order is not None:
        df = df.sort_values(order, kind="stable")
    dup = df.duplicated(keys, keep="last")
    if dup.any():
        clog.step(name, "bo dong trung khoa (giu ban moi nhat)", dup.sum(), ",".join(keys))
    return df[~dup]
