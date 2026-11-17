"""Kiem tra chat luong du lieu tu dong, 4 muc (ke hoach v2 muc 6; phan cong TV2 viec 3).

    Muc 1 - gia tri    : tung o nam trong mien hop le (ty le 0-100, so dem >= 0, danh muc dung).
    Muc 2 - ban ghi    : khoa khong trung, du khung bang x tuan, nhat quan trong dong va voi tuan truoc
                         (bien tre, wow), co thieu khop gia tri, so so bo dung 4 tuan cuoi.
    Muc 3 - quan he    : khoa ngoai fact -> dim, thuoc tinh trong fact khop dim, metadata nguon tro dung bang/cot.
    Muc 4 - nhieu bang : tong 51 bang = toan quoc va = vung HHS (doi chieu file NHSN HRD cua CDC, nguon doc lap);
                         business khop clean (doi soat lineage); fact_season_summary khop roll-up tu fact.
    Them: do phu bang x nam cho tung tin hieu (co > 30% thieu).

Moi quy tac tra ve cac dong vi pham dang (table, state, week, season, column, value, detail) de truy duoc
den tung o - dung de cham diem bo du lieu chen loi (inject.py).

Chay: python pipelines/02_warehouse.py --steps quality   -> reports/data_quality/README.md
"""
import datetime as dt
import json
import logging
from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd

from .business import (EPA_MIN_SITE_SHARE, EPA_SITE_BASE_YEARS, LAG_COLS, LEVEL_NAMES, MISSING_FLAGS, PRELIM_WEEKS,
                       _cdc_level, epa_usable)
from .common import HHS_REGION, STATE_TO_HHS, STATES

log = logging.getLogger("fluwatch.warehouse")

BIZ_TABLES = ["dim_state", "dim_time", "dim_source", "fact_flu_week", "fact_season_summary"]
VCOLS = ["table", "state", "week", "season", "column", "value", "detail"]
COVERAGE_FLAG = 30.0          # % thieu bang x nam vuot nguong nay thi gan co
COVERAGE_SIGNALS = {          # cot -> ten hien thi
    "ili_pct": "ILINet ILI%", "rate_flu": "NHSN nhập viện", "ed_pct_flu": "NSSP cấp cứu",
    "lab_pct_pos": "Xét nghiệm % dương tính", "wval": "Nước thải WVAL", "abs_humidity": "Độ ẩm tuyệt đối",
    "pm25_mean": "PM2.5", "flu_vax_pct": "Độ phủ vaccine",
}
TERRITORIES = {"PR": 2, "VI": 2, "GU": 9, "AS": 9, "MP": 9}   # lanh tho -> vung HHS (HRD gop vao USA va vung)

# cot fact -> (bang clean, cot clean); khoa (state, week), rieng vaccine khoa (state, season)
LINEAGE_CHECK = {
    "ili_pct": ("ilinet", "ili_pct"), "num_ili": ("ilinet", "num_ili"), "num_patients": ("ilinet", "num_patients"),
    "num_providers": ("ilinet", "num_providers"),
    "hosp_flu": ("nhsn", "hosp_flu"), "rate_flu": ("nhsn", "rate_flu"), "hosp_reporting": ("nhsn", "hosp_reporting"),
    "beds_flu_pct": ("nhsn", "beds_flu_pct"),
    "ed_pct_flu": ("nssp", "ed_pct_flu"), "ed_pct_covid": ("nssp", "ed_pct_covid"),
    "lab_pct_pos": ("lab_clinical", "lab_pct_pos"), "lab_specimens": ("lab_clinical", "lab_specimens"),
    "flusurv_rate": ("flusurv", "flusurv_rate"),
    "wval": ("wval", "wval"), "wval_mean": ("wval", "wval_mean"), "wval_sites": ("wval", "wval_sites"),
    "temp_mean": ("weather", "temp_mean"), "abs_humidity": ("weather", "abs_humidity"),
    "pm25_max": ("weather", "pm25_om_max"), "pm25_om": ("weather", "pm25_om_mean"),
    "flu_vax_pct": ("vaccine", "flu_vax_pct"),
}


# ============================== Khung quy tac ==============================

@dataclass
class Rule:
    id: str
    level: int
    name: str            # mo ta ngan (tieng Viet)
    table: str
    severity: str        # "loi" (phai = 0) | "canh_bao" (bat thuong can xem, chua chac sai)
    fn: Callable


RULES: list[Rule] = []


def rule(id, level, name, table, severity="loi"):
    def deco(fn):
        RULES.append(Rule(id, level, name, table, severity, fn))
        return fn
    return deco


def _num(s):
    return pd.to_numeric(s, errors="coerce").astype("float64")


def _viol(df, table, column, value=None, detail=""):
    """Dong vi pham chuan tu cac dong `df` (can co state/week hoac state/season neu co)."""
    n = len(df)
    out = pd.DataFrame({
        "table": [table] * n,
        "state": df["state"].astype("object").to_numpy() if "state" in df else [None] * n,
        "week": pd.to_datetime(df["week"]).to_numpy() if "week" in df else [pd.NaT] * n,
        "season": df["season"].astype("object").to_numpy() if "season" in df else [None] * n,
        "column": df["_col"].to_numpy() if "_col" in df else [column] * n,
        "value": (df[value].astype("object").to_numpy() if isinstance(value, str) and value in df
                  else [value] * n),
        "detail": df["_detail"].to_numpy() if "_detail" in df else [detail] * n,
    })
    return out


def _empty():
    return pd.DataFrame(columns=VCOLS)


def _neq(a, b):
    """a != b theo tung phan tu, coi NaN == NaN, so thuc sai so 1e-9."""
    a, b = _num(a), _num(b)
    both_na = a.isna() & b.isna()
    one_na = a.isna() ^ b.isna()
    diff = ~np.isclose(a.fillna(0), b.fillna(0), rtol=1e-9, atol=1e-9)
    return (one_na | (diff & ~a.isna() & ~b.isna())) & ~both_na


def _range(df, table, cols, lo, hi):
    parts, n = [], 0
    for c in cols:
        if c not in df:
            continue
        v = _num(df[c])
        n += int(v.notna().sum())
        bad = v.notna() & ((v < lo) | (v > hi))
        if bad.any():
            parts.append(_viol(df[bad].assign(_v=v[bad]), table, c, "_v", f"ngoai [{lo}, {hi}]"))
    return n, (pd.concat(parts, ignore_index=True) if parts else _empty())


def _dedup(f):
    return f.drop_duplicates(["state", "week"], keep="first")


# ============================== Muc 1: gia tri ==============================

PCT_COLS = ["ili_pct", "ed_pct_flu", "ed_pct_covid", "lab_pct_pos", "beds_flu_pct", "flu_vax_pct"]
COUNT_COLS = ["num_ili", "num_patients", "num_providers", "hosp_flu", "hosp_reporting", "lab_specimens",
              "wval_sites", "epa_sites", "n_cities"]


@rule("V01", 1, "Tỷ lệ % nằm trong 0–100", "fact_flu_week")
def v01(c):
    return _range(c["fact_flu_week"], "fact_flu_week", PCT_COLS, 0, 100)


@rule("V02", 1, "Tỷ lệ % (vaccine, khoảng tin cậy) trong 0–100", "fact_season_summary")
def v02(c):
    return _range(c["fact_season_summary"], "fact_season_summary", ["flu_vax_pct", "vax_ci_low", "vax_ci_high"], 0, 100)


@rule("V03", 1, "Số đếm là số nguyên ≥ 0", "fact_flu_week")
def v03(c):
    f = c["fact_flu_week"]
    parts, n = [], 0
    for col in COUNT_COLS:
        v = _num(f[col])
        n += int(v.notna().sum())
        bad = v.notna() & ((v < 0) | (v != np.round(v)))
        if bad.any():
            parts.append(_viol(f[bad].assign(_v=v[bad]), "fact_flu_week", col, "_v", "am hoac khong nguyen"))
    return n, (pd.concat(parts, ignore_index=True) if parts else _empty())


@rule("V04", 1, "Tỷ suất nhập viện (ca/100.000 dân/tuần) trong 0–100", "fact_flu_week")
def v04(c):
    return _range(c["fact_flu_week"], "fact_flu_week", ["rate_flu", "flusurv_rate"], 0, 100)


@rule("V05", 1, "Thời tiết, PM2.5 trong miền vật lý (°C −60–55; g/m³ 0–40; µg/m³ 0–1000)", "fact_flu_week")
def v05(c):
    f = c["fact_flu_week"]
    n1, a = _range(f, "fact_flu_week", ["temp_mean"], -60, 55)
    n2, b = _range(f, "fact_flu_week", ["abs_humidity"], 0, 40)
    n3, d = _range(f, "fact_flu_week", ["pm25_mean", "pm25_max"], 0, 1000)
    return n1 + n2 + n3, pd.concat([a, b, d], ignore_index=True)


@rule("V06", 1, "WVAL nước thải trong miền hợp lý 0–100 (Very High của CDC từ 15,6)", "fact_flu_week", "canh_bao")
def v06(c):
    return _range(c["fact_flu_week"], "fact_flu_week", ["wval"], 0, 100)


@rule("V07", 1, "Giá trị danh mục hợp lệ (mức CDC, cờ 0/1, nguồn PM2.5, mã bang)", "fact_flu_week")
def v07(c):
    f = c["fact_flu_week"]
    checks = {
        "cdc_level": set(range(5)), "cdc_level_name": set(LEVEL_NAMES), "pm25_source": {"epa", "openmeteo"},
        "holiday_week": {0, 1}, "winter_break": {0, 1}, "state": set(STATES),
    }
    parts, n = [], 0
    for col, ok in checks.items():
        s = f[col]
        present = s.notna()
        n += int(present.sum())
        vals = s[present].astype("object")
        bad_idx = vals.index[~vals.isin(ok)]
        if len(bad_idx):
            parts.append(_viol(f.loc[bad_idx], "fact_flu_week", col, col, "ngoai danh muc"))
    return n, (pd.concat(parts, ignore_index=True) if parts else _empty())


@rule("V08", 1, "Tuần là thứ Bảy kết thúc tuần MMWR; mùa dạng YYYY-YY", "fact_flu_week")
def v08(c):
    f = c["fact_flu_week"]
    wk = pd.to_datetime(f["week"])
    bad_w = wk.isna() | (wk.dt.weekday != 5)
    s = f["season"].astype("string")
    y0 = pd.to_numeric(s.str[:4], errors="coerce")
    y1 = pd.to_numeric(s.str[5:7], errors="coerce")
    bad_s = ~s.str.fullmatch(r"\d{4}-\d{2}").fillna(False) | ((y0 + 1) % 100 != y1)
    parts = [_viol(f[bad_w], "fact_flu_week", "week", "week", "khong phai thu Bay"),
             _viol(f[bad_s.to_numpy()], "fact_flu_week", "season", "season", "sai dinh dang mua")]
    return 2 * len(f), pd.concat(parts, ignore_index=True)


# ============================== Muc 2: ban ghi ==============================

@rule("R01", 2, "Khóa chính không trống, không trùng (fact: bang × tuần; season: bang × mùa; dim)", "*")
def r01(c):
    keys = {"fact_flu_week": ["state", "week"], "fact_season_summary": ["state", "season"],
            "dim_state": ["state"], "dim_time": ["week"], "dim_source": ["source_id"]}
    parts, n = [], 0
    for t, k in keys.items():
        d = c[t]
        n += len(d)
        null = d[k].isna().any(axis=1)
        dup = d.duplicated(k, keep=False) & ~null
        if null.any():
            parts.append(_viol(d[null], t, "*", None, f"khoa {k} trong"))
        if dup.any():
            x = d[dup].copy()
            x["_detail"] = "trung khoa, " + x.groupby(k, dropna=False)[k[0]].transform("size").astype(str) + " dong"
            parts.append(_viol(x.drop_duplicates(k), t, "*"))
    return n, (pd.concat(parts, ignore_index=True) if parts else _empty())


@rule("R02", 2, "Đủ khung 51 bang × mọi tuần (không mất dòng, không mất khối tuần)", "fact_flu_week")
def r02(c):
    f = c["fact_flu_week"]
    wk = pd.to_datetime(f["week"])
    weeks = pd.date_range(wk.min(), wk.max(), freq="W-SAT")
    full = pd.MultiIndex.from_product([STATES, weeks], names=["state", "week"]).to_frame(index=False)
    have = f[["state", "week"]].drop_duplicates().assign(_h=1)
    m = full.merge(have, on=["state", "week"], how="left")
    miss = m[m._h.isna()]
    return len(full), _viol(miss, "fact_flu_week", "*", None, "thieu dong (bang, tuan)")


@rule("R03", 2, "ILI nhất quán trong dòng: num_ili ≤ num_patients; ili_pct = num_ili / num_patients × 100", "fact_flu_week")
def r03(c):
    f = c["fact_flu_week"]
    ili, n_ili, n_pat = _num(f.ili_pct), _num(f.num_ili), _num(f.num_patients)
    a = n_ili > n_pat
    calc = n_ili / n_pat.where(n_pat > 0) * 100
    b = ili.notna() & calc.notna() & ((ili - calc).abs() > 0.01)
    parts = [_viol(f[a.to_numpy()], "fact_flu_week", "num_ili", "num_ili", "num_ili > num_patients"),
             _viol(f[b.to_numpy()].assign(_v=ili[b]), "fact_flu_week", "ili_pct", "_v", "lech num_ili/num_patients")]
    return int((n_pat.notna()).sum()), pd.concat(parts, ignore_index=True)


@rule("R04", 2, "Mẫu số bằng 0 thì tỷ lệ phải để trống (không có báo cáo ≠ không có cúm)", "fact_flu_week")
def r04(c):
    f = c["fact_flu_week"]
    a = (_num(f.num_patients) == 0) & f.ili_pct.notna()
    b = (_num(f.lab_specimens) == 0) & f.lab_pct_pos.notna()
    parts = [_viol(f[a.to_numpy()], "fact_flu_week", "ili_pct", "ili_pct", "num_patients = 0"),
             _viol(f[b.to_numpy()], "fact_flu_week", "lab_pct_pos", "lab_pct_pos", "lab_specimens = 0")]
    return int(f.num_patients.notna().sum() + f.lab_specimens.notna().sum()), pd.concat(parts, ignore_index=True)


@rule("R05", 2, "Cờ missing_* khớp với ô giá trị tương ứng", "fact_flu_week")
def r05(c):
    f = c["fact_flu_week"]
    parts, n = [], 0
    for flag, col in MISSING_FLAGS.items():
        if flag not in f:
            continue
        n += len(f)
        bad = f[flag].astype("boolean").fillna(False).to_numpy() != f[col].isna().to_numpy()
        if bad.any():
            parts.append(_viol(f[bad], "fact_flu_week", col, col, f"{flag} khong khop"))
    return n, (pd.concat(parts, ignore_index=True) if parts else _empty())


@rule("R06", 2, "Biến trễ khớp giá trị tuần trước của cùng bang (col_lagk tuần t = col tuần t−k)", "fact_flu_week")
def r06(c):
    f = _dedup(c["fact_flu_week"])
    parts, n = [], 0
    for col, k in LAG_COLS.items():
        for i in range(1, k + 1):
            lag = f"{col}_lag{i}"
            if lag not in f:
                continue
            # lag cua tuan t+i phai bang gia tri tuan t -> vi pham ghi vao o (bang, tuan t, col)
            later = f[["state", "week", lag]].assign(week=lambda d: d.week - pd.Timedelta(weeks=i))
            m = f[["state", "week", "season", col]].merge(later, on=["state", "week"], how="inner")
            n += len(m)
            bad = _neq(m[col], m[lag])
            if bad.any():
                x = m[bad.to_numpy()].assign(_detail=f"khac {lag} cua tuan sau {i} tuan")
                parts.append(_viol(x, "fact_flu_week", col, col))
    v = pd.concat(parts, ignore_index=True) if parts else _empty()
    return n, v.drop_duplicates(["state", "week", "column"])


@rule("R07", 2, "Biến phái sinh khớp: wow_pct, ili_wow_pct; mức CDC tính lại từ rate_flu và ngưỡng", "fact_flu_week")
def r07(c):
    f = _dedup(c["fact_flu_week"]).reset_index(drop=True)
    parts = []
    for out, cur, prev in [("wow_pct", "rate_flu", "rate_flu_lag1"), ("ili_wow_pct", "ili_pct", "ili_pct_lag1")]:
        cu, pr = _num(f[cur]), _num(f[prev])
        calc = ((cu - pr) / pr * 100).where(pr > 0)
        bad = _neq(f[out], calc)
        if bad.any():
            parts.append(_viol(f[bad.to_numpy()].assign(_detail=f"{out} khong khop"), "fact_flu_week", cur, cur))
    lvl = _cdc_level(c["paths"], f.assign(rate_flu=_num(f.rate_flu)))
    bad = _neq(f["cdc_level"], lvl)
    if bad.any():
        parts.append(_viol(f[bad.to_numpy()].assign(_detail="cdc_level khac muc tinh tu nguong"),
                           "fact_flu_week", "rate_flu", "rate_flu"))
    name = f["cdc_level"].map(lambda v: LEVEL_NAMES[int(v)] if pd.notna(v) and 0 <= v < 5 else None)
    bad = name.astype("object").fillna("") != f["cdc_level_name"].astype("object").fillna("")
    if bad.any():
        parts.append(_viol(f[bad.to_numpy()], "fact_flu_week", "cdc_level_name", "cdc_level_name", "ten muc khong khop"))
    return 3 * len(f), (pd.concat(parts, ignore_index=True) if parts else _empty())


@rule("R08", 2, f"Cờ is_preliminary đúng {PRELIM_WEEKS} tuần cuối", "fact_flu_week")
def r08(c):
    f = c["fact_flu_week"]
    last = pd.to_datetime(f.week).max()
    exp = pd.to_datetime(f.week) > last - pd.Timedelta(weeks=PRELIM_WEEKS)
    bad = f.is_preliminary.astype("boolean").fillna(False).to_numpy() != exp.to_numpy()
    return len(f), _viol(f[bad], "fact_flu_week", "is_preliminary", "is_preliminary", "sai co so bo")


@rule("R09", 2, "rate_flu khớp hosp_flu / dân số × 100.000 (dân số suy ra = trung vị theo bang × mùa), lệch ≤ 5%",
      "fact_flu_week", "canh_bao")
def r09(c):
    f = _dedup(c["fact_flu_week"])
    hosp, rate = _num(f.hosp_flu), _num(f.rate_flu)
    ok = (rate > 0) & hosp.notna()
    x = f[ok.to_numpy()].assign(_h=hosp[ok], _r=rate[ok])
    pop = (x._h * 1e5 / x._r).groupby([x.state, x.season]).transform("median")   # Delphi dung dan so rieng
    calc = x._h * 1e5 / pop
    bad = (x._r - calc).abs() > np.maximum(0.05 * x._r, 0.03)          # rate_flu lam tron 2 chu so
    v = x[bad.to_numpy()].copy()
    v["_detail"] = "rate_flu = " + v._r.round(2).astype(str) + ", tinh tu hosp_flu = " + calc[bad].round(2).astype(str)
    # khong biet o nao sai -> ghi ca hai o
    return len(x), pd.concat([_viol(v, "fact_flu_week", "rate_flu", "_r"), _viol(v, "fact_flu_week", "hosp_flu", "_h")],
                             ignore_index=True)


@rule("R10", 2, f"PM2.5 EPA năm mới nhất chỉ dùng khi đủ trạm (epa_sites ≥ {int(EPA_MIN_SITE_SHARE * 100)}% trung vị "
      f"{EPA_SITE_BASE_YEARS[0]}–{EPA_SITE_BASE_YEARS[1]} của bang)", "fact_flu_week", "canh_bao")
def r10(c):
    f = _dedup(c["fact_flu_week"])
    epa_col = "pm25_epa" if "pm25_epa" in f else "pm25_mean"
    used = (f.pm25_source == "epa").fillna(False) & _num(f[epa_col]).notna()
    sites = _num(f.epa_sites)
    yr = pd.to_datetime(f.week).dt.year
    if not sites.notna().any():
        return 0, _empty()
    y0, y1 = EPA_SITE_BASE_YEARS
    base = sites[yr.between(y0, y1)].groupby(f.state).median()
    need = f.state.map(base) * EPA_MIN_SITE_SHARE
    latest = yr == yr[sites.notna()].max()
    chk = (used & latest).to_numpy()
    bad = chk & (sites < need).fillna(False).to_numpy()
    x = f[bad].assign(_v=sites[bad])
    x["_detail"] = "epa_sites = " + x._v.astype(int).astype(str) + " < " + need[bad].round(1).astype(str) + \
        " nhung van dung EPA"
    return int(chk.sum()), _viol(x, "fact_flu_week", "epa_sites", "_v")


# ============================== Muc 3: quan he ==============================

@rule("Q01", 3, "Khóa ngoại: fact.state, fact.week, season.state, season.season đều có trong dim", "*")
def q01(c):
    f, s, ds, dt_ = c["fact_flu_week"], c["fact_season_summary"], c["dim_state"], c["dim_time"]
    parts = []
    for t, d, col, ref in [("fact_flu_week", f, "state", ds.state), ("fact_flu_week", f, "week", dt_.week),
                           ("fact_season_summary", s, "state", ds.state),
                           ("fact_season_summary", s, "season", dt_.season)]:
        bad = ~d[col].isin(set(ref.dropna()))
        if bad.any():
            parts.append(_viol(d[bad.to_numpy()], t, col, col, f"khong co trong dim ({col})"))
    return 2 * len(f) + 2 * len(s), (pd.concat(parts, ignore_index=True) if parts else _empty())


@rule("Q02", 3, "Thuộc tính thời gian trong fact khớp dim_time (epiweek, mùa, tuần trong mùa, nghỉ lễ)", "fact_flu_week")
def q02(c):
    f, t = c["fact_flu_week"], c["dim_time"]
    cols = ["epiweek", "season", "season_week", "mmwr_year", "mmwr_week", "holiday_week", "winter_break",
            "weeks_to_holiday"]
    cols = [x for x in cols if x in f and x in t]
    m = f[["state", "week"] + cols].merge(t[["week"] + cols], on="week", how="inner", suffixes=("", "_dim"))
    parts = []
    for col in cols:
        a, b = m[col].astype("object"), m[f"{col}_dim"].astype("object")
        bad = ~((a == b) | (a.isna() & b.isna()))
        if bad.any():
            x = m[bad.to_numpy()].assign(_detail=f"{col} khac dim_time")
            parts.append(_viol(x, "fact_flu_week", col, col))
    return len(m) * len(cols), (pd.concat(parts, ignore_index=True) if parts else _empty())


@rule("Q03", 3, "dim_state đúng 51 mã, vùng HHS đúng bảng chuẩn, dân số > 0", "dim_state")
def q03(c):
    d = c["dim_state"]
    parts = []
    miss = sorted(set(STATES) - set(d.state))
    if miss:
        parts.append(_viol(pd.DataFrame({"state": miss}), "dim_state", "state", None, "thieu bang"))
    bad = d.state.map(STATE_TO_HHS).astype("Int64").to_numpy() != _num(d.hhs_region).astype("Int64").to_numpy()
    bad = pd.Series(bad).fillna(True).to_numpy()
    if bad.any():
        parts.append(_viol(d[bad], "dim_state", "hhs_region", "hhs_region", "sai vung HHS"))
    bp = ~(_num(d.population) > 0)
    if bp.any():
        parts.append(_viol(d[bp.to_numpy()], "dim_state", "population", "population", "dan so <= 0 hoac trong"))
    return 3 * len(d), (pd.concat(parts, ignore_index=True) if parts else _empty())


@rule("Q04", 3, "dim_source trỏ đúng: bảng clean tồn tại, cột fact_columns có trong fact/dim và ngược lại "
      "(cột fact từ nguồn nào thì nguồn đó liệt kê); có người phụ trách",
      "dim_source")
def q04(c):
    d, f = c["dim_source"], c["fact_flu_week"]
    clean_dir = c["paths"].data / "clean"
    known = set(f.columns) | {f"dim_state.{x}" for x in c["dim_state"].columns}
    parts = []
    for _, r in d.iterrows():
        row = pd.DataFrame({"state": [None], "_detail": [""]})
        if r.clean_table and not (clean_dir / f"{r.clean_table}.parquet").exists():
            parts.append(_viol(row.assign(_detail=f"{r.source_id}: thieu clean/{r.clean_table}.parquet"),
                               "dim_source", "clean_table"))
        for col in str(r.fact_columns).split(","):
            col = col.split("(")[0].strip()
            if col and col not in known:
                parts.append(_viol(row.assign(_detail=f"{r.source_id}: cot '{col}' khong co"), "dim_source",
                                   "fact_columns"))
        for col in ("owner", "steward"):
            if not str(r.get(col) or "").strip():
                parts.append(_viol(row.assign(_detail=f"{r.source_id}: thieu {col}"), "dim_source", col))
    # Chieu nguoc: cot fact ma tu dien ghi nguon X thi dim_source X phai liet ke (bien tre, co missing_* la phai sinh)
    from .catalog import describe
    listed = {r.source_id: {x.split("(")[0].strip() for x in str(r.fact_columns).split(",")} for _, r in d.iterrows()}
    n_rev = 0
    for col in f.columns:
        desc = describe("fact_flu_week", col)
        if not desc or desc[2] not in listed:
            continue
        n_rev += 1
        if col not in listed[desc[2]]:
            row = pd.DataFrame({"state": [None], "_detail": [f"{desc[2]}: fact_columns thieu '{col}'"]})
            parts.append(_viol(row, "dim_source", "fact_columns"))
    return len(d) * 3 + n_rev, (pd.concat(parts, ignore_index=True) if parts else _empty())


@rule("Q05", 3, "Vaccine trong fact_flu_week khớp fact_season_summary theo (bang, mùa)", "fact_flu_week")
def q05(c):
    f, s = c["fact_flu_week"], c["fact_season_summary"]
    m = f[["state", "week", "season", "flu_vax_pct"]].merge(
        s[["state", "season", "flu_vax_pct"]].drop_duplicates(["state", "season"]),
        on=["state", "season"], how="left", suffixes=("", "_s"))
    bad = _neq(m.flu_vax_pct, m.flu_vax_pct_s)
    return len(m), _viol(m[bad.to_numpy()], "fact_flu_week", "flu_vax_pct", "flu_vax_pct", "khac fact_season_summary")


@rule("Q06", 3, "Mọi cột của bảng business đều có trong từ điển dữ liệu (catalog.py) và ngược lại", "*")
def q06(c):
    from .catalog import missing_entries
    t = {n: c[n] for n in BIZ_TABLES}
    miss = missing_entries(t)
    v = pd.DataFrame({"state": [None] * len(miss), "_t": [m[0] for m in miss], "_col": [m[1] for m in miss],
                      "_detail": [m[2] for m in miss]})
    out = _viol(v, "", None)
    out["table"] = v._t.to_numpy()
    return sum(df.shape[1] for df in t.values()), out


# ============================== Muc 4: nhieu bang ==============================

def _hrd(paths):
    """File NHSN HRD tai tay (CDC): tong nhap vien cum theo bang, vung, USA. None neu chua tai raw."""
    files = sorted((paths.raw / "cdc_nhsn_hrd").glob("*/*.csv"))
    if not files:
        return None, None
    d = pd.read_csv(files[-1], low_memory=False,
                    usecols=["Week Ending Date", "Geographic aggregation", "Total Influenza Admissions"])
    d["week"] = pd.to_datetime(d["Week Ending Date"])
    d["geo"] = d["Geographic aggregation"].astype(str)
    d["hosp"] = pd.to_numeric(d["Total Influenza Admissions"].astype(str).str.replace(",", ""), errors="coerce")
    return d[["week", "geo", "hosp"]], files[-1]


def _total_check(fact_sum, ref, label, snap_last):
    """So tong cac bang voi tong tham chieu; 4 tuan cuoi cua ban chup la so so bo -> chi dem, khong tinh vi pham."""
    m = pd.DataFrame({"fact": fact_sum, "ref": ref}).dropna()
    m = m[m.ref > 0]
    tol = np.maximum(0.02 * m.ref, 10)             # lech <= 2% hoac <= 10 ca (CDC sua le te sau ban chup)
    bad = (m.fact - m.ref).abs() > tol
    recent = m.index > snap_last - pd.Timedelta(weeks=PRELIM_WEEKS)
    return m, bad & ~recent, bad & recent


@rule("M01", 4, "Tổng nhập viện 51 bang = toàn quốc (CDC NHSN HRD, USA trừ lãnh thổ), lệch ≤ 2% hoặc ≤ 10 ca", "fact_flu_week")
def m01(c):
    hrd = c["hrd"]
    if hrd is None:
        return 0, _empty()
    f = c["fact_flu_week"]                      # khong bo trung: dong trung lam lech tong -> cung bi bat
    fs = f.groupby("week").hosp_flu.apply(lambda x: _num(x).sum(min_count=1))
    us = hrd[hrd.geo == "USA"].set_index("week").hosp
    terr = hrd[hrd.geo.isin(TERRITORIES)].groupby("week").hosp.sum()
    ref = us - terr.reindex(us.index).fillna(0)
    m, bad, revised = _total_check(fs.reindex(ref.index), ref, "USA", hrd.week.max())
    c["_revised"]["M01"] = int(revised.sum())
    x = m[bad].reset_index().rename(columns={"index": "week"})
    x["_detail"] = "51 bang = " + x.fact.round().astype(int).astype(str) + ", CDC = " + x.ref.round().astype(int).astype(str)
    return len(m), _viol(x, "fact_flu_week", "hosp_flu", "fact")


@rule("M02", 4, "Tổng nhập viện các bang trong vùng = vùng HHS (CDC NHSN HRD), lệch ≤ 2% hoặc ≤ 10 ca", "fact_flu_week")
def m02(c):
    hrd = c["hrd"]
    if hrd is None:
        return 0, _empty()
    f = c["fact_flu_week"].assign(_r=lambda d: d.state.map(STATE_TO_HHS))
    parts, n, rev = [], 0, 0
    for r in HHS_REGION:
        fs = f[f._r == r].groupby("week").hosp_flu.apply(lambda x: _num(x).sum(min_count=1))
        reg = hrd[hrd.geo == f"Region {r}"].set_index("week").hosp
        ter = [t for t, rr in TERRITORIES.items() if rr == r]
        if ter:
            reg = reg - hrd[hrd.geo.isin(ter)].groupby("week").hosp.sum().reindex(reg.index).fillna(0)
        m, bad, revised = _total_check(fs.reindex(reg.index), reg, f"Region {r}", hrd.week.max())
        n += len(m)
        rev += int(revised.sum())
        if bad.any():
            x = m[bad].reset_index().rename(columns={"index": "week"})
            x["_detail"] = f"vung {r}: cac bang = " + x.fact.round().astype(int).astype(str) + \
                ", CDC = " + x.ref.round().astype(int).astype(str)
            parts.append(_viol(x, "fact_flu_week", "hosp_flu", "fact"))
    c["_revised"]["M02"] = rev
    return n, (pd.concat(parts, ignore_index=True) if parts else _empty())


@rule("M03", 4, "Đối soát lineage: mỗi ô nguồn trong business bằng đúng ô trong clean/ (không mất, không sửa)",
      "fact_flu_week")
def m03(c):
    f = c["fact_flu_week"]
    clean = c["clean"]
    parts, n = [], 0
    by_table = {}
    for col, (t, ccol) in LINEAGE_CHECK.items():
        by_table.setdefault(t, []).append((col, ccol))
    for t, cols in by_table.items():
        if t not in clean or not all(col in f for col, _ in cols):
            continue
        key = ["state", "season"] if t == "vaccine" else ["state", "week"]
        src = clean[t][key + [cc for _, cc in cols]].rename(columns={cc: f"{col}__c" for col, cc in cols})
        m = f[["state", "week", "season"] + [col for col, _ in cols]].merge(src, on=key, how="left")
        for col, _ in cols:
            bad = _neq(m[col], m[f"{col}__c"])
            n += len(m)
            if bad.any():
                x = m[bad.to_numpy()].copy()
                x["_detail"] = ("business = " + x[col].astype(str) + ", clean/" + t + " = " + x[f"{col}__c"].astype(str))
                parts.append(_viol(x, "fact_flu_week", col, col))
    # pm25_epa: EPA khi du tram; pm25_mean: pm25_epa, khong thi Open-Meteo
    if "epa_pm25" in clean and "weather" in clean:
        epa = clean["epa_pm25"][["state", "week", "epa_pm25_mean", "epa_sites"]]
        epa = epa.assign(_epa=epa.epa_pm25_mean.where(epa_usable(epa)))[["state", "week", "_epa"]]
        cols = [c for c in ("pm25_mean", "pm25_epa") if c in f]
        m = f[["state", "week", "season"] + cols].merge(epa, on=["state", "week"], how="left").merge(
            clean["weather"][["state", "week", "pm25_om_mean"]], on=["state", "week"], how="left")
        for col, exp in [("pm25_epa", m._epa), ("pm25_mean", m._epa.fillna(m.pm25_om_mean))]:
            if col not in m:
                continue
            bad = _neq(m[col], exp)
            n += len(m)
            if bad.any():
                parts.append(_viol(m[bad.to_numpy()].assign(_detail="khac EPA (du tram)/Open-Meteo trong clean"),
                                   "fact_flu_week", col, col))
    return n, (pd.concat(parts, ignore_index=True) if parts else _empty())


@rule("M04", 4, "fact_season_summary khớp roll-up tuần → mùa tính lại từ fact_flu_week", "fact_season_summary")
def m04(c):
    f, s = c["fact_flu_week"], c["fact_season_summary"]
    ins = f[(_num(f.mmwr_week) >= 40) | (_num(f.mmwr_week) <= 20)]
    g = ins.groupby(["state", "season"])
    calc = pd.DataFrame({
        "weeks_in_data": f.groupby(["state", "season"]).week.size(),
        "ili_weeks": g.ili_pct.count(), "ili_max": g.ili_pct.max(),
        "hosp_total": g.hosp_flu.apply(lambda x: _num(x).sum(min_count=1)), "rate_flu_max": g.rate_flu.max(),
    }).reset_index()
    m = s.merge(calc, on=["state", "season"], how="inner", suffixes=("", "__c"))
    parts, n = [], 0
    for col in ["weeks_in_data", "ili_weeks", "ili_max", "hosp_total", "rate_flu_max"]:
        n += len(m)
        bad = _neq(m[col], m[f"{col}__c"])
        if bad.any():
            x = m[bad.to_numpy()].copy()
            x["_detail"] = "summary = " + x[col].astype(str) + ", tinh lai = " + x[f"{col}__c"].astype(str)
            parts.append(_viol(x, "fact_season_summary", col, col))
    return n, (pd.concat(parts, ignore_index=True) if parts else _empty())


# ============================== Do phu bang x nam ==============================

def coverage(f):
    """% thieu theo bang x nam cho tung tin hieu, chi tinh trong khoang nguon co du lieu (tuan dau -> tuan cuoi
    co it nhat 1 bang co so), de NHSN truoc 2020 khong bi tinh la thieu."""
    f = _dedup(f).copy()
    f["year"] = pd.to_datetime(f.week).dt.year
    rows = []
    for col, label in COVERAGE_SIGNALS.items():
        has = f[f[col].notna()]
        if has.empty:
            continue
        lo, hi = has.week.min(), has.week.max()
        w = f[(f.week >= lo) & (f.week <= hi)]
        g = w.groupby(["state", "year"])[col]
        cov = (1 - g.count() / g.size()) * 100
        d = cov.rename("missing_pct").reset_index()
        d["weeks"] = g.size().to_numpy()
        d.insert(0, "signal", col)
        d.insert(1, "label", label)
        d["active_from"], d["active_to"] = lo.date(), hi.date()
        rows.append(d)
    out = pd.concat(rows, ignore_index=True)
    out["missing_pct"] = out.missing_pct.round(1)
    out["flag"] = out.missing_pct > COVERAGE_FLAG
    return out


# ============================== Chay ==============================

def load_business(paths, fact=None):
    biz = paths.data / "business"
    t = {n: pd.read_parquet(biz / f"{n}.parquet") for n in BIZ_TABLES}
    if fact is not None:
        t["fact_flu_week"] = fact
    return t


def load_clean(paths):
    d = paths.data / "clean"
    names = {t for t, _ in LINEAGE_CHECK.values()} | {"epa_pm25"}
    return {n: pd.read_parquet(d / f"{n}.parquet") for n in names if (d / f"{n}.parquet").exists()}


def run_checks(paths, tables=None, clean=None, hrd=None):
    """Chay moi quy tac. Tra ve (bang tong hop theo quy tac, DataFrame moi vi pham, thong tin phu)."""
    tables = tables or load_business(paths)
    clean = clean if clean is not None else load_clean(paths)
    if hrd is None:
        hrd, _ = _hrd(paths)
    ctx = dict(tables, paths=paths, clean=clean, hrd=hrd, _revised={})
    summary, allv = [], []
    for r in RULES:
        try:
            n, v = r.fn(ctx)
            err = ""
        except Exception as e:          # mot quy tac hong khong lam dung ca bao cao
            log.exception("Quy tac %s loi", r.id)
            n, v, err = 0, _empty(), f"{type(e).__name__}: {e}"
        v = v.assign(rule=r.id, level=r.level, severity=r.severity) if len(v) else \
            pd.DataFrame(columns=VCOLS + ["rule", "level", "severity"])
        status = "LOI_CHAY" if err else ("DAT" if len(v) == 0 else ("CANH_BAO" if r.severity == "canh_bao" else "KHONG_DAT"))
        summary.append(dict(rule=r.id, level=r.level, name=r.name, table=r.table, severity=r.severity,
                            checked=int(n), violations=len(v), status=status, error=err))
        allv.append(v)
    nonempty = [v for v in allv if len(v)]
    viol = pd.concat(nonempty, ignore_index=True) if nonempty else \
        pd.DataFrame(columns=VCOLS + ["rule", "level", "severity"])
    return pd.DataFrame(summary), viol, {"revised": ctx["_revised"]}


# ============================== Bao cao ==============================

LEVEL_TITLE = {1: "Mức 1 – Giá trị", 2: "Mức 2 – Bản ghi", 3: "Mức 3 – Quan hệ", 4: "Mức 4 – Nhiều bảng"}
STATUS_ICON = {"DAT": "✅ Đạt", "KHONG_DAT": "❌ Không đạt", "CANH_BAO": "⚠️ Cảnh báo", "LOI_CHAY": "💥 Lỗi chạy"}


def _fmt(v):
    if v is None or (not isinstance(v, str) and pd.isna(v)):
        return ""
    if isinstance(v, (pd.Timestamp, np.datetime64)):
        return str(pd.Timestamp(v).date())
    if isinstance(v, float):
        return f"{v:.4g}"
    return str(v).replace("|", "\\|")


def _md(df):
    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join(" --- " for _ in cols) + "|"]
    lines += ["| " + " | ".join(_fmt(v) for v in r) + " |" for r in df.itertuples(index=False)]
    return "\n".join(lines)


def _runs(years, pcts):
    """[2010, 2011, 2012, 2016] -> '2010–2012 (100%), 2016 (76%)': gop cac nam lien tiep, ghi % thieu cao nhat."""
    out, start, prev, mx = [], None, None, 0
    for y, p in zip(years, pcts):
        if prev is not None and y == prev + 1:
            prev, mx = y, max(mx, p)
            continue
        if start is not None:
            out.append((start, prev, mx))
        start, prev, mx = y, y, p
    if start is not None:
        out.append((start, prev, mx))
    return ", ".join(f"{a}{'' if a == b else f'–{b}'} ({m:.0f}%)" for a, b, m in out)


def _coverage_md(cov):
    parts = ["| Tín hiệu | Khoảng có dữ liệu | Ô bang × năm | Ô thiếu > 30% | Bang × năm bị gắn cờ |",
             "| --- | --- | --- | --- | --- |"]
    for sig, d in cov.groupby("signal", sort=False):
        fl = d[d.flag].sort_values(["state", "year"])
        if fl.empty:
            parts.append(f"| {d.label.iloc[0]} (`{sig}`) | {d.active_from.iloc[0]} → {d.active_to.iloc[0]} | "
                         f"{len(d)} | 0 (0%) | – |")
            continue
        # nhom cac bang co cung mau thieu (vd. cung thieu nam 2020) cho gon
        pat = fl.groupby("state").apply(lambda x: _runs(list(x.year), list(x.missing_pct)), include_groups=False)
        grp = pat.groupby(pat).apply(lambda x: ", ".join(s.upper() for s in x.index))
        txt = "; ".join(f"**{states}**: {runs}" for runs, states in grp.items()) if len(grp) else "–"
        parts.append(f"| {d.label.iloc[0]} (`{sig}`) | {d.active_from.iloc[0]} → {d.active_to.iloc[0]} | {len(d)} | "
                     f"{int(d.flag.sum())} ({d.flag.mean() * 100:.0f}%) | {txt} |")
    return "\n".join(parts)


def write_report(paths, summary, viol, cov, extra, out_dir, title_note=""):
    out_dir.mkdir(parents=True, exist_ok=True)
    meta_p = paths.data / "business" / "_business_meta.json"
    meta = json.loads(meta_p.read_text(encoding="utf-8")) if meta_p.exists() else {}
    tot = summary.status.value_counts().to_dict()
    p = ["# Báo cáo chất lượng dữ liệu", "",
         f"Sinh tự động bởi `python pipelines/02_warehouse.py --steps quality` lúc {dt.datetime.now():%Y-%m-%d %H:%M}, "
         f"trên `data/business/` dựng lúc {meta.get('built_at', '?')} (tuần cuối {meta.get('last_week', '?')}). "
         f"Code: `src/fluwatch/warehouse/quality.py`.{title_note}", "",
         f"**{len(summary)} quy tắc**: {tot.get('DAT', 0)} đạt, {tot.get('KHONG_DAT', 0)} không đạt, "
         f"{tot.get('CANH_BAO', 0)} cảnh báo, {tot.get('LOI_CHAY', 0)} lỗi chạy. "
         "Mức độ `loi` phải bằng 0 vi phạm; `canh_bao` là giá trị bất thường cần xem, chưa chắc sai.", "",
         "## 1. Tổng hợp theo quy tắc", ""]
    for lvl in sorted(LEVEL_TITLE):
        s = summary[summary.level == lvl]
        p += [f"### {LEVEL_TITLE[lvl]}", "",
              _md(s.assign(status=s.status.map(STATUS_ICON))[["rule", "name", "table", "severity", "checked",
                                                                "violations", "status"]]
                  .rename(columns={"rule": "Mã", "name": "Quy tắc", "table": "Bảng", "severity": "Mức độ",
                                   "checked": "Số ô/dòng kiểm", "violations": "Vi phạm", "status": "Kết quả"})), ""]
    rev = extra.get("revised", {})
    if rev:
        p += [f"Ghi chú M01/M02: {PRELIM_WEEKS} tuần cuối của bản chụp HRD là số sơ bộ lúc tải, CDC đã sửa sau đó, "
              f"nên chỉ đếm, không tính vi phạm (M01: {rev.get('M01', 0)} tuần lệch, M02: {rev.get('M02', 0)} "
              "vùng × tuần lệch). Đây là bằng chứng trực tiếp cho quy tắc cập nhật 4 tuần gần nhất.", ""]
    p += ["## 2. Chi tiết vi phạm (tối đa 10 dòng mỗi quy tắc)", "",
          "Toàn bộ vi phạm: `reports/data_quality/violations.csv`.", ""]
    if viol.empty:
        p += ["Không có vi phạm.", ""]
    for rid, d in viol.groupby("rule", sort=False):
        name = summary.set_index("rule").loc[rid, "name"]
        top = d.groupby("column").size().sort_values(ascending=False)
        p += [f"### {rid}. {name}", "",
              f"{len(d)} vi phạm; theo cột: " + ", ".join(f"`{k}` {v}" for k, v in top.items()) + ".", "",
              _md(d.head(10)[["table", "state", "week", "season", "column", "value", "detail"]]), ""]
    p += ["## 3. Độ phủ bang × năm", "",
          f"% tuần thiếu của mỗi (bang, năm), chỉ tính trong khoảng nguồn có dữ liệu. Ô thiếu > {COVERAGE_FLAG:.0f}% "
          "bị gắn cờ. Bảng đầy đủ: `reports/data_quality/coverage_state_year.csv`.", "",
          _coverage_md(cov), ""]
    (out_dir / "README.md").write_text("\n".join(p), encoding="utf-8")
    viol.to_csv(out_dir / "violations.csv", index=False)
    cov.to_csv(out_dir / "coverage_state_year.csv", index=False)
    res = {"built_at": dt.datetime.now().isoformat(timespec="seconds"), "business_built_at": meta.get("built_at"),
           "rules": summary.to_dict(orient="records"), "revised_in_snapshot": rev,
           "coverage_flagged_cells": int(cov.flag.sum()), "coverage_cells": len(cov)}
    (out_dir / "results.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return out_dir / "README.md"


def build_quality(paths, out_dir=None):
    out_dir = out_dir or paths.root / "reports" / "data_quality"
    tables = load_business(paths)
    summary, viol, extra = run_checks(paths, tables)
    cov = coverage(tables["fact_flu_week"])
    md = write_report(paths, summary, viol, cov, extra, out_dir)
    return summary, viol, cov, md
