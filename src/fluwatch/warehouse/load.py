"""Ham doc chung cho ca nhom (hop dong du lieu: docs/ke_hoach.md muc 4.1).

    from fluwatch.warehouse.load import load_flu_week, load_dim_state, load_dim_time, load_season_summary

Nguon doc:
- Neu da co data/business/fact_flu_week.parquet: doc data/business/ (star schema cua TV2, tu 17/11).
- Neu chua: ghep tu data/samples/ va data/reference/ (tai bang `python scripts/download_data.py --samples`).
Ep nguon bang bien moi truong FLUWATCH_SOURCE=samples hoac FLUWATCH_SOURCE=business.

Quy uoc: `state` ma 2 chu viet thuong, chi 50 bang + DC; `week` la ngay thu Bay ket thuc tuan MMWR (datetime64);
`season` dang 2024-25, bat dau tu tuan MMWR 40; `season_week` = 1 o tuan MMWR 40.
Moi ham tra ve mot DataFrame moi (sua thoai mai, khong anh huong lan goi sau).
"""
import functools
import logging
import os
from pathlib import Path

import numpy as np
import pandas as pd

from fluwatch.ingest.paths import Paths
from fluwatch.warehouse.common import NON_CONTIGUOUS, STATE_TO_HHS, STATES, season_of

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[3]
PATHS = Paths(ROOT)
BUSINESS = PATHS.data / "business"
HF_REPO = os.environ.get("HF_REPO", "DragonBornRay/FluDataset")

# --- Hop dong cot (khong doi ten, khong bo cot sau 16/11; them cot thi duoc) ---
FLU_WEEK_COLS = [
    "state", "week", "epiweek", "season", "season_week",
    "ili_pct", "num_ili", "num_patients", "hosp_flu", "rate_flu", "cdc_level",
    "ed_pct_flu", "lab_pct_pos", "wval",
    "temp_mean", "abs_humidity", "ah_anomaly", "pm25_mean", "flu_vax_pct",
    "holiday_week", "winter_break", "weeks_to_holiday", "is_preliminary",
]
DIM_STATE_COLS = ["state", "state_name", "hhs_region", "population", "contiguous", "cluster_id"]
DIM_TIME_COLS = ["week", "epiweek", "season", "season_week", "year", "month", "holiday_week"]
MILESTONE_COLS = ["baseline", "onset_week", "peak_week", "peak_value", "severity", "source"]
SEASON_SUMMARY_COLS = ["state", "season", "flu_vax_pct"] + MILESTONE_COLS

PRELIM_WEEKS = 4                      # 4 tuan gan nhat la so lieu so bo
AH_CLIMATOLOGY_YEARS = (2010, 2025)   # ah_anomaly: tru trung binh cung bang, cung tuan MMWR qua cac nam nay



# ============================== Ham cong khai ==============================

def load_flu_week():
    """Bang x tuan: dung cac cot FLU_WEEK_COLS."""
    return _flu_week().copy()


def load_dim_state():
    """Bang: state, state_name, hhs_region (1-10), population, contiguous (48 bang luc dia + DC), cluster_id."""
    return _dim_state().copy()


def load_dim_time():
    """Tuan: week, epiweek, season, season_week, year, month (nam, thang cua ngay thu Bay), holiday_week."""
    return _dim_time().copy()


def load_season_summary():
    """Bang x mua: state, season, flu_vax_pct + cac cot moc mua cua TV3 (trong neu TV3 chua giao)."""
    return _season_summary().copy()


def source():
    """'business' hoac 'samples': nguon ma cac ham load_* dang doc."""
    forced = os.environ.get("FLUWATCH_SOURCE", "").strip().lower()
    if forced in ("samples", "business"):
        return forced
    return "business" if (BUSINESS / "fact_flu_week.parquet").exists() else "samples"


def clear_cache():
    """Xoa bo nho dem (goi sau khi tai lai du lieu trong cung phien notebook)."""
    for f in (_flu_week, _dim_state, _dim_time, _season_summary, _population):
        f.cache_clear()


# ============================== Doc file ==============================

def _read(name, **kw):
    p = PATHS.samples / name
    if not p.exists():
        raise FileNotFoundError(
            f"Khong thay {p}. Chay: python scripts/download_data.py --samples (tu thu muc goc repo)")
    return pd.read_csv(p, **kw)


def _clean_keys(df, label):
    """state viet thuong, loc GU/VI/PR va moi ma ngoai 50 bang + DC; week thanh datetime."""
    df = df.copy()
    df["state"] = df["state"].astype("string").str.strip().str.lower()
    bad = ~df["state"].isin(STATES)
    if bad.any():
        log.info("%s: bo %d dong ngoai 50 bang + DC (%s)", label, int(bad.sum()),
                 ", ".join(sorted(df.loc[bad, "state"].dropna().unique())))
        df = df[~bad]
    if "week" in df:
        df["week"] = pd.to_datetime(df["week"])
    return df


@functools.lru_cache(maxsize=1)
def _population():
    """Dan so 2020 theo bang (raw/population/*/state_pop_2020_delphi.csv; tai rieng file nay neu chua co)."""
    files = sorted(PATHS.raw.glob("population/*/state_pop_2020_delphi.csv"))
    if not files:
        from huggingface_hub import snapshot_download
        log.info("Chua co raw/population/: tai tu Hugging Face %s", HF_REPO)
        snapshot_download(repo_id=HF_REPO, repo_type="dataset", local_dir=PATHS.data,
                          allow_patterns=["raw/population/*/state_pop_2020_delphi.csv"])
        files = sorted(PATHS.raw.glob("population/*/state_pop_2020_delphi.csv"))
    pop = pd.read_csv(files[-1]).rename(columns={"state_id": "state", "pop": "population"})
    return _clean_keys(pop[["state", "state_name", "population"]], "population")


# ============================== Dung tu samples/ ==============================

def _flu_week_from_samples():
    base = _clean_keys(_read("state_week_sample.csv.gz"), "state_week_sample")
    # Thoi tiet lay tu weather_state_week (ban 3-5 thanh pho), KHONG lay cot thoi tiet trong state_week_sample
    base = base.drop(columns=["temp_mean", "abs_humidity", "pm25_mean", "pm25_max"], errors="ignore")
    base["epiweek"] = (base["mmwr_year"] * 100 + base["mmwr_week"]).astype("int64")

    weather = _clean_keys(_read("weather_state_week.csv.gz"), "weather_state_week")
    weather = weather[["state", "week", "temp_mean", "abs_humidity", "pm25_mean"]].rename(
        columns={"pm25_mean": "pm25_openmeteo"})

    epa = _clean_keys(_read("epa_pm25_state_week.csv.gz"), "epa_pm25_state_week")
    neg = epa["epa_pm25_mean"] < 0
    if neg.any():
        log.warning("EPA PM2.5: %d gia tri am -> dat thanh thieu", int(neg.sum()))
        epa.loc[neg, "epa_pm25_mean"] = np.nan
    epa = epa[["state", "week", "epa_pm25_mean"]]

    level = _clean_keys(_read("cdc_level_state_week.csv.gz"), "cdc_level_state_week")
    level = level[["state", "week", "level"]].rename(columns={"level": "cdc_level"})

    wval = _clean_keys(_read("wval_state_week.csv.gz"), "wval_state_week")[["state", "week", "wval"]]

    hol = pd.read_csv(PATHS.reference / "holidays.csv", parse_dates=["week"])
    hol = hol[["week", "holiday_week", "winter_break", "weeks_to_holiday"]]

    df = (base.merge(weather, on=["state", "week"], how="left")
              .merge(epa, on=["state", "week"], how="left")
              .merge(level, on=["state", "week"], how="left")
              .merge(wval, on=["state", "week"], how="left")
              .merge(hol, on="week", how="left"))

    # PM2.5: EPA, thieu thi Open-Meteo; ghi lai nguon
    df["pm25_source"] = np.where(df["epa_pm25_mean"].notna(), "epa",
                                 np.where(df["pm25_openmeteo"].notna(), "openmeteo", None))
    df["pm25_mean"] = df["epa_pm25_mean"].fillna(df["pm25_openmeteo"])

    # season, season_week tinh lai tu ngay (season = mua cua tuan MMWR 40)
    season, season_week = season_of(df["week"])
    mismatch = df["season"].notna() & (df["season"].astype("string") != season)
    if mismatch.any():
        log.warning("season trong samples lech %d dong so voi cach tinh tuan 40; dung cach tinh", int(mismatch.sum()))
    df["season"], df["season_week"] = season, season_week

    # ah_anomaly = abs_humidity - trung binh cung bang, cung tuan MMWR, nam 2010-2025 (tuan 53 dung trung binh tuan 52)
    y0, y1 = AH_CLIMATOLOGY_YEARS
    mw = df["mmwr_week"].where(df["mmwr_week"] != 53, 52)
    ref = df[df["mmwr_year"].between(y0, y1)].assign(mw=mw)
    clim = ref.groupby(["state", "mw"])["abs_humidity"].mean().rename("ah_clim")
    df = df.assign(mw=mw).merge(clim, left_on=["state", "mw"], right_index=True, how="left")
    df["ah_anomaly"] = df["abs_humidity"] - df["ah_clim"]

    # Vaccine: theo bang x mua (thang cuoi co so), trai ra moi tuan cua mua
    vax = _clean_keys(_read("vaccine_state_season.csv"), "vaccine_state_season")
    vax = vax.rename(columns={"est": "flu_vax_pct"})[["state", "season", "flu_vax_pct"]]
    vax["season"] = vax["season"].astype("string")
    df = df.merge(vax, on=["state", "season"], how="left")

    # So bo: 4 tuan gan nhat cua du lieu
    last = df.loc[df["ili_pct"].notna() | df["hosp_flu"].notna(), "week"].max()
    df["is_preliminary"] = df["week"] > last - pd.Timedelta(weeks=PRELIM_WEEKS)

    return df


def _dim_state_from_samples():
    pop = _population()
    d = pd.DataFrame({"state": STATES})
    d = d.merge(pop, on="state", how="left")
    d["hhs_region"] = d["state"].map(STATE_TO_HHS)
    d["contiguous"] = ~d["state"].isin(NON_CONTIGUOUS)
    d["cluster_id"] = pd.NA
    cluster = BUSINESS / "state_cluster.parquet"      # TV3 giao (stub 15/11, that 18/11)
    if cluster.exists():
        c = pd.read_parquet(cluster, columns=["state", "cluster_id"])
        d = d.drop(columns="cluster_id").merge(c, on="state", how="left")
    return d


def _dim_time_from_samples():
    hol = pd.read_csv(PATHS.reference / "holidays.csv", parse_dates=["week"])
    t = hol[["week", "mmwr_year", "mmwr_week", "holiday_week"]].copy()
    t["epiweek"] = t["mmwr_year"] * 100 + t["mmwr_week"]
    t["season"], t["season_week"] = season_of(t["week"])
    t["year"] = t["week"].dt.year
    t["month"] = t["week"].dt.month
    return t


def _season_summary_from_samples():
    fw = _flu_week()
    s = fw[["state", "season"]].drop_duplicates()
    vax = fw.groupby(["state", "season"], as_index=False)["flu_vax_pct"].first()
    s = s.merge(vax, on=["state", "season"], how="left")
    ms = BUSINESS / "season_milestones.parquet"        # TV3 giao (stub 15/11, that 17/11)
    if ms.exists():
        m = pd.read_parquet(ms)
        m["state"] = m["state"].str.lower()
        m["season"] = m["season"].astype("string")
        keep = ["state", "season"] + [c for c in MILESTONE_COLS if c in m]
        s = s.merge(m[keep], on=["state", "season"], how="left")
    return s


# ============================== Kieu du lieu va thu tu cot ==============================

INT_COLS = ["epiweek", "season_week", "cdc_level", "holiday_week", "winter_break", "weeks_to_holiday",
            "hhs_region", "population", "year", "month", "num_ili", "num_patients"]


def _finalize(df, cols, sort):
    for c in cols:
        if c not in df:
            df[c] = pd.NA
    extra = [c for c in df.columns if c not in cols and c in ("pm25_source",)]
    df = df[cols + extra].copy()
    for c in ("state", "season", "state_name", "source", "pm25_source"):
        if c in df:
            df[c] = df[c].astype("string")
    for c in INT_COLS:
        if c in df:
            df[c] = pd.to_numeric(df[c], errors="coerce").round().astype("Int64")
    for c in ("week", "onset_week", "peak_week"):
        if c in df:
            df[c] = pd.to_datetime(df[c])
    for c in ("is_preliminary", "contiguous"):
        if c in df:
            df[c] = df[c].astype("boolean")
    for c in ("baseline", "peak_value"):
        if c in df:
            df[c] = pd.to_numeric(df[c], errors="coerce").astype("float64")
    if "cluster_id" in df:
        df["cluster_id"] = pd.to_numeric(df["cluster_id"], errors="coerce").astype("Int64")
    return df.sort_values(sort).reset_index(drop=True)


# ============================== Bo nho dem theo nguon ==============================

def _business(name):
    return pd.read_parquet(BUSINESS / f"{name}.parquet")


@functools.lru_cache(maxsize=1)
def _flu_week():
    df = _business("fact_flu_week") if source() == "business" else _flu_week_from_samples()
    return _finalize(df, FLU_WEEK_COLS, ["state", "week"])


@functools.lru_cache(maxsize=1)
def _dim_state():
    df = _business("dim_state") if source() == "business" else _dim_state_from_samples()
    return _finalize(df, DIM_STATE_COLS, ["state"])


@functools.lru_cache(maxsize=1)
def _dim_time():
    df = _business("dim_time") if source() == "business" else _dim_time_from_samples()
    return _finalize(df, DIM_TIME_COLS, ["week"])


@functools.lru_cache(maxsize=1)
def _season_summary():
    df = _business("fact_season_summary") if source() == "business" else _season_summary_from_samples()
    return _finalize(df, SEASON_SUMMARY_COLS, ["state", "season"])
