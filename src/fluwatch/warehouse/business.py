"""Dung vung data/business/: star schema (fact constellation) tu data/clean/.

    dim_state  dim_time  dim_source
         \\       |       /
        fact_flu_week (bang x tuan)      fact_season_summary (bang x mua; dung chung dim_state)

Theo ke hoach v2 muc 5.3 va muc 6:
- Bang khung: du moi cap bang x tuan (51 x so tuan), moi nguon ghep TRAI vao khung -> o thieu van la thieu, khong mat dong.
- Cot phai sinh: ah_anomaly, bien tre, wow_pct, yoy_pct, cdc_level, is_preliminary, missing_*, issue_date.
- Khong tinh moc mua, muc nen, season_phase (TV3) va nhan canh bao (TV5): de cho trong, tu ghep khi ho giao file.

Chay: python pipelines/02_warehouse.py --steps business
"""
import datetime as dt
import json
import logging

import numpy as np
import pandas as pd

from .clean_delphi import DELPHI_TABLES
from .common import HHS_REGION, NON_CONTIGUOUS, STATE_TO_HHS, STATES, add_time_keys, mmwr_year_week, rel, season_of

log = logging.getLogger("fluwatch.warehouse")

PRELIM_WEEKS = 4                      # 4 tuan gan nhat la so lieu so bo (CDC con sua)
AH_CLIMATOLOGY_YEARS = (2010, 2025)   # ah_anomaly: tru trung binh cung bang, cung tuan MMWR cac nam nay
FACT_START = pd.Timestamp("2010-01-02")   # tuan MMWR dau tien co thoi tiet; ILINet bat dau 10/2010
LAG_COLS = {"ili_pct": 3, "rate_flu": 3, "hosp_flu": 3, "ed_pct_flu": 3, "lab_pct_pos": 3, "wval": 3,
            "ah_anomaly": 4, "pm25_mean": 4, "temp_mean": 3}
MISSING_FLAGS = {"missing_ili": "ili_pct", "missing_hosp": "rate_flu", "missing_ed": "ed_pct_flu",
                 "missing_lab": "lab_pct_pos", "missing_wval": "wval", "missing_weather": "abs_humidity",
                 "missing_pm25": "pm25_mean", "missing_vax": "flu_vax_pct"}
MILESTONE_COLS = ["baseline", "onset_week", "peak_week", "peak_value", "severity", "source"]
LEVEL_NAMES = ["rat_thap", "thap", "trung_binh", "cao", "rat_cao"]   # 0..4 theo CDC


def _clean(paths, name):
    p = paths.data / "clean" / f"{name}.parquet"
    if not p.exists():
        raise FileNotFoundError(f"Chua co {p}. Chay truoc: python pipelines/02_warehouse.py --steps clean")
    return pd.read_parquet(p)


# ============================== Dimension ==============================

def build_dim_state(paths):
    """Bang -> vung HHS -> toan quoc; dan so 2020, co 48 bang luc dia + DC, toa do trong tam dan so, cluster_id."""
    from .common import latest_raw
    pop = pd.read_csv(latest_raw(paths, "population", "state_pop_2020_delphi", ".csv"))
    pop = pop.rename(columns={"state_id": "state", "pop": "population"})
    pop["state"] = pop["state"].str.lower()
    cities = pd.read_csv(paths.reference / "cities.csv")
    cen = cities.groupby("state").apply(
        lambda g: pd.Series({"lat": np.average(g.lat, weights=g.population), "lon": np.average(g.lon, weights=g.population)}),
        include_groups=False).reset_index()
    d = pd.DataFrame({"state": STATES})
    d = d.merge(pop[["state", "state_name", "population"]], on="state", how="left")
    d["hhs_region"] = d["state"].map(STATE_TO_HHS).astype("Int64")
    d["hhs_region_name"] = "Vung " + d["hhs_region"].astype(str)
    d["country"] = "us"
    d["contiguous"] = ~d["state"].isin(NON_CONTIGUOUS)
    d = d.merge(cen, on="state", how="left")
    d["cluster_id"] = pd.Series(pd.NA, index=d.index, dtype="Int64")
    d["population"] = d["population"].astype("Int64")
    return d[["state", "state_name", "hhs_region", "hhs_region_name", "country", "population", "contiguous",
              "lat", "lon", "cluster_id"]]


def build_dim_time(paths, last_week):
    """Tuan -> thang -> mua; thu tu tuan trong mua, co nghi le. Tu 2010 den het nam sau tuan cuoi co so lieu."""
    hol = pd.read_csv(paths.reference / "holidays.csv", parse_dates=["week"])
    end = pd.Timestamp(year=last_week.year + 1, month=12, day=31)
    t = pd.DataFrame({"week": pd.date_range(FACT_START, end, freq="W-SAT")})
    t = t.merge(hol[["week", "holiday_week", "holiday_name", "winter_break", "weeks_to_holiday"]], on="week", how="left")
    y, w = mmwr_year_week(t["week"])
    t["mmwr_year"], t["mmwr_week"] = y, w
    t["epiweek"] = (y * 100 + w).astype("Int64")
    t["season"], t["season_week"] = season_of(t["week"])
    t["week_start"] = t["week"] - pd.Timedelta(days=6)
    t["week_end"] = t["week"]
    t["year"] = t["week"].dt.year.astype("Int64")
    t["month"] = t["week"].dt.month.astype("Int64")
    t["in_flu_season"] = (t["mmwr_week"] >= 40) | (t["mmwr_week"] <= 20)   # tuan 40 -> 20: mua cum CDC theo doi
    for c in ("holiday_week", "winter_break", "weeks_to_holiday"):
        t[c] = t[c].astype("Int64")
    return t[["week", "epiweek", "mmwr_year", "mmwr_week", "week_start", "week_end", "season", "season_week",
              "year", "month", "in_flu_season", "holiday_week", "holiday_name", "winter_break", "weeks_to_holiday"]]


# Nguon -> metadata quan tri (owner: nguoi phu trach; steward: nguoi lam sach / dua vao kho)
SOURCES = [
    dict(source_id="ilinet", source_name="ILINet (FluView)", provider="CDC qua Delphi Epidata V5", access="API",
         dataset_id="fluview_ilinet", raw_path="data/raw/fluview_ilinet/", clean_table="ilinet",
         fact_columns="ili_pct, num_ili, num_patients, num_providers", unit="% luot kham; so luot",
         frequency="tuan", geo_level="bang (NY gop NYC)", revised=True, update_rule="thu Bay; tai lai ca lich su, 4 tuan gan nhat la so bo",
         license="Cong cong (CDC); trich dan Delphi", owner="TV1", steward="TV2"),
    dict(source_id="nhsn", source_name="NHSN nhap vien cum", provider="CDC qua Delphi Epidata V5", access="API",
         dataset_id="nhsn", raw_path="data/raw/nhsn/", clean_table="nhsn",
         fact_columns="hosp_flu, rate_flu, hosp_reporting, beds_flu_pct, cdc_level", unit="ca/tuan; ca/100.000 dan; %",
         frequency="tuan", geo_level="bang", revised=True, update_rule="thu Bay; tai lai ca lich su, 4 tuan gan nhat la so bo",
         license="Cong cong (CDC); trich dan Delphi", owner="TV1", steward="TV2"),
    dict(source_id="nssp", source_name="NSSP cap cuu", provider="CDC qua Delphi Epidata V5", access="API",
         dataset_id="nssp", raw_path="data/raw/nssp/", clean_table="nssp",
         fact_columns="ed_pct_flu, ed_pct_covid", unit="% luot cap cuu",
         frequency="tuan", geo_level="bang", revised=True, update_rule="thu Bay; tai lai ca lich su, 4 tuan gan nhat la so bo",
         license="Cong cong (CDC); trich dan Delphi", owner="TV1", steward="TV2"),
    dict(source_id="lab_clinical", source_name="Xet nghiem lam sang (FluView)", provider="CDC qua Delphi Epidata V5",
         access="API", dataset_id="fluview_resp_lab_clinical", raw_path="data/raw/fluview_resp_lab_clinical/",
         clean_table="lab_clinical", fact_columns="lab_pct_pos, lab_specimens", unit="% duong tinh; so mau",
         frequency="tuan", geo_level="bang", revised=True, update_rule="thu Bay; tai lai ca lich su",
         license="Cong cong (CDC); trich dan Delphi", owner="TV1", steward="TV2"),
    dict(source_id="flusurv", source_name="FluSurv-NET", provider="CDC qua Delphi Epidata V5", access="API",
         dataset_id="flusurv", raw_path="data/raw/flusurv/", clean_table="flusurv",
         fact_columns="flusurv_rate", unit="ca/100.000 dan", frequency="tuan", geo_level="18 bang tham gia",
         revised=True, update_rule="thu Bay; tai lai ca lich su", license="Cong cong (CDC); trich dan Delphi",
         owner="TV1", steward="TV2"),
    dict(source_id="wval", source_name="Nuoc thai WVAL cum A", provider="CDC NWSS (data.cdc.gov)",
         access="GitHub Actions (may chu My)", dataset_id="atcp-73re", raw_path="data/raw/cdc_wastewater_wval/",
         clean_table="wval", fact_columns="wval, wval_sites", unit="WVAL (khong don vi, 0 = muc nen)",
         frequency="tuan", geo_level="tram -> bang (trong so dan so phuc vu)", revised=True,
         update_rule="thu Bay (crawl_cdc.yml); moi lan tai la ca lich su, moi tuan dung ban moi nhat",
         license="Cong cong (CDC)", owner="TV1", steward="TV2"),
    dict(source_id="vaccine", source_name="Do phu vaccine cum (FluVaxView)", provider="CDC (data.cdc.gov)",
         access="GitHub Actions (may chu My)", dataset_id="vh55-3he6", raw_path="data/raw/cdc_fluvax_coverage/",
         clean_table="vaccine", fact_columns="flu_vax_pct", unit="% dan so >= 6 thang",
         frequency="thang (lay thang cuoi co so cua mua)", geo_level="bang", revised=True,
         update_rule="hang thang; gan cho moi tuan cua mua", license="Cong cong (CDC)", owner="TV1", steward="TV2"),
    dict(source_id="weather", source_name="Thoi tiet + PM2.5 Open-Meteo", provider="Open-Meteo", access="API",
         dataset_id="archive-api, air-quality-api", raw_path="data/raw/openmeteo_*_cities/", clean_table="weather",
         fact_columns="temp_mean, abs_humidity, ah_anomaly, pm25_mean (khi thieu EPA), pm25_max",
         unit="do C; g/m3; ug/m3", frequency="ngay/gio -> tuan", geo_level="3-5 thanh pho -> bang (trong so dan so)",
         revised=False, update_rule="thu Bay; tai lai 35 ngay gan nhat", license="CC BY 4.0", owner="TV1", steward="TV2"),
    dict(source_id="epa", source_name="EPA AirData PM2.5 (88101)", provider="US EPA", access="file zip theo nam",
         dataset_id="daily_88101", raw_path="data/raw/epa_airdata/", clean_table="epa_pm25",
         fact_columns="pm25_mean (uu tien)", unit="ug/m3", frequency="ngay -> tuan", geo_level="tram -> bang",
         revised=True, update_rule="tai lai file nam hien tai khi EPA cap nhat (tre vai thang)",
         license="Cong cong (EPA)", owner="TV1", steward="TV2"),
    dict(source_id="population", source_name="Dan so 2020", provider="Census qua Delphi", access="file csv",
         dataset_id="state_pop_2020_delphi", raw_path="data/raw/population/", clean_table="",
         fact_columns="dim_state.population", unit="nguoi", frequency="co dinh", geo_level="bang",
         revised=False, update_rule="khong doi", license="Cong cong (Census)", owner="TV1", steward="TV2"),
    dict(source_id="holidays", source_name="Ngay le va ky nghi dong", provider="Nhom tu lap", access="build_reference.py",
         dataset_id="holidays.csv", raw_path="data/reference/holidays.csv", clean_table="",
         fact_columns="holiday_week, winter_break, weeks_to_holiday", unit="co 0/1; tuan", frequency="tuan",
         geo_level="toan quoc", revised=False, update_rule="khong doi", license="Nhom", owner="TV1", steward="TV2"),
    dict(source_id="cdc_thresholds", source_name="Nguong muc do nhap vien CDC", provider="CDC (trang phuong phap HRD)",
         access="GitHub Actions", dataset_id="cdc_level_thresholds.csv", raw_path="data/raw/cdc_methods/",
         clean_table="", fact_columns="cdc_level", unit="muc 0-4", frequency="co dinh", geo_level="bang",
         revised=False, update_rule="khi CDC doi nguong", license="Cong cong (CDC)", owner="TV1", steward="TV2"),
]


def build_dim_source(paths, clean_log):
    d = pd.DataFrame(SOURCES)
    rng = {t: v.get("range", [None, None]) for t, v in clean_log.items()}
    d["first_period"] = d.clean_table.map(lambda t: rng.get(t, [None, None])[0])
    d["last_period"] = d.clean_table.map(lambda t: rng.get(t, [None, None])[1])
    d["raw_files"] = d.clean_table.map(lambda t: "; ".join(clean_log.get(t, {}).get("sources", [])[-3:]))
    d["built_at"] = dt.datetime.now().isoformat(timespec="seconds")
    return d


# ============================== Fact ==============================

def _cdc_level(paths, df):
    th = pd.read_csv(paths.reference / "cdc_level_thresholds.csv")
    th = th[th.virus == "Influenza"].assign(state=lambda d: d.jurisdiction.str.lower()).set_index("state")
    cuts = th[["very_low_max", "low_max", "moderate_max", "high_max"]]
    lvl = pd.Series(pd.NA, index=df.index, dtype="Int64")
    for s, g in df[df.rate_flu.notna()].groupby("state"):
        if s in cuts.index:   # 'Up to x' nghia la <= x
            lvl[g.index] = np.searchsorted(cuts.loc[s].values, g.rate_flu.values, side="left")
    return lvl


def _pct_change(cur, prev):
    out = (cur - prev) / prev * 100
    return out.where(prev > 0)          # tuan truoc = 0 -> khong xac dinh (khong de vo cung)


def build_fact_flu_week(paths, dim_time):
    sig = {t: _clean(paths, t) for t in DELPHI_TABLES}
    last = max(sig[t].week.max() for t in ("ilinet", "nhsn", "nssp"))
    weeks = pd.date_range(FACT_START, last, freq="W-SAT")
    f = pd.MultiIndex.from_product([STATES, weeks], names=["state", "week"]).to_frame(index=False)

    issue = []
    for t, d in sig.items():
        cols = [c for _, _, c, _ in DELPHI_TABLES[t]]
        f = f.merge(d[["state", "week"] + cols + ["report_date"]].rename(columns={"report_date": f"_rd_{t}"}),
                    on=["state", "week"], how="left")
        issue.append(f"_rd_{t}")
    f["issue_date"] = f[issue].max(axis=1)
    f = f.drop(columns=issue)

    wx = _clean(paths, "weather")[["state", "week", "temp_mean", "abs_humidity", "pm25_om_mean", "pm25_om_max", "n_cities"]]
    epa = _clean(paths, "epa_pm25")[["state", "week", "epa_pm25_mean", "epa_sites"]]
    ww = _clean(paths, "wval")[["state", "week", "wval", "wval_sites"]]
    f = f.merge(wx, on=["state", "week"], how="left").merge(epa, on=["state", "week"], how="left") \
         .merge(ww, on=["state", "week"], how="left")
    f["pm25_mean"] = f["epa_pm25_mean"].fillna(f["pm25_om_mean"])
    f["pm25_source"] = pd.Series(np.where(f.epa_pm25_mean.notna(), "epa",
                                          np.where(f.pm25_om_mean.notna(), "openmeteo", None)), dtype="string")
    f["pm25_max"] = f["pm25_om_max"]

    t = dim_time[["week", "epiweek", "mmwr_year", "mmwr_week", "season", "season_week",
                  "holiday_week", "winter_break", "weeks_to_holiday"]]
    f = f.merge(t, on="week", how="left")

    vax = _clean(paths, "vaccine")[["state", "season", "flu_vax_pct"]]
    f = f.merge(vax, on=["state", "season"], how="left")

    # ah_anomaly = abs_humidity - trung binh cung bang, cung tuan MMWR, nam 2010-2025 (tuan 53 dung trung binh tuan 52)
    y0, y1 = AH_CLIMATOLOGY_YEARS
    f["_mw"] = f["mmwr_week"].where(f["mmwr_week"] != 53, 52)
    clim = f[f.mmwr_year.between(y0, y1)].groupby(["state", "_mw"]).abs_humidity.mean().rename("_clim")
    f = f.merge(clim, left_on=["state", "_mw"], right_index=True, how="left")
    f["ah_anomaly"] = f["abs_humidity"] - f["_clim"]
    f = f.drop(columns=["_mw", "_clim"])

    f["cdc_level"] = _cdc_level(paths, f)
    f["cdc_level_name"] = f["cdc_level"].map(dict(enumerate(LEVEL_NAMES))).astype("string")

    # Bien tre: tren khung du tuan nen shift(k) dung la k tuan truoc
    f = f.sort_values(["state", "week"]).reset_index(drop=True)
    g = f.groupby("state", sort=False)
    for c, k in LAG_COLS.items():
        for i in range(1, k + 1):
            f[f"{c}_lag{i}"] = g[c].shift(i)

    # wow: so tuan truoc; yoy: so cung season_week mua truoc
    f["wow_pct"] = _pct_change(f.rate_flu, f.rate_flu_lag1)
    f["ili_wow_pct"] = _pct_change(f.ili_pct, f.ili_pct_lag1)
    prev = f[["state", "season", "season_week", "rate_flu", "ili_pct"]].copy()
    prev["season"] = prev["season"].map(lambda s: f"{int(s[:4]) + 1}-{(int(s[:4]) + 2) % 100:02d}" if pd.notna(s) else s)
    prev = prev.rename(columns={"rate_flu": "_rate_prev", "ili_pct": "_ili_prev"})
    f = f.merge(prev, on=["state", "season", "season_week"], how="left")
    f["yoy_pct"] = _pct_change(f.rate_flu, f._rate_prev)
    f["ili_yoy_pct"] = _pct_change(f.ili_pct, f._ili_prev)
    f = f.drop(columns=["_rate_prev", "_ili_prev"])

    f["is_preliminary"] = f["week"] > last - pd.Timedelta(weeks=PRELIM_WEEKS)
    for flag, c in MISSING_FLAGS.items():
        f[flag] = f[c].isna()

    first = ["state", "week", "epiweek", "season", "season_week",
             "ili_pct", "num_ili", "num_patients", "hosp_flu", "rate_flu", "cdc_level", "ed_pct_flu", "lab_pct_pos",
             "wval", "temp_mean", "abs_humidity", "ah_anomaly", "pm25_mean", "flu_vax_pct",
             "holiday_week", "winter_break", "weeks_to_holiday", "is_preliminary"]      # hop dong muc 4.1
    extra = ["mmwr_year", "mmwr_week", "num_providers", "hosp_reporting", "beds_flu_pct", "cdc_level_name",
             "ed_pct_covid", "lab_specimens", "flusurv_rate", "wval_sites", "pm25_max", "pm25_source", "epa_sites",
             "n_cities", "wow_pct", "yoy_pct", "ili_wow_pct", "ili_yoy_pct"]
    lags = [f"{c}_lag{i}" for c, k in LAG_COLS.items() for i in range(1, k + 1)]
    quality = list(MISSING_FLAGS) + ["issue_date"]
    return f[first + extra + lags + quality].sort_values(["state", "week"]).reset_index(drop=True)


def build_fact_season_summary(paths, fact):
    """Bang x mua: vaccine, cac tong hop mo ta (roll-up tuan -> mua), cho trong cho moc mua cua TV3."""
    vax = _clean(paths, "vaccine").rename(columns={"vax_month": "vax_month"})
    in_season = fact[(fact.mmwr_week >= 40) | (fact.mmwr_week <= 20)]
    g = in_season.groupby(["state", "season"])
    s = pd.DataFrame({
        "weeks_in_data": fact.groupby(["state", "season"]).week.nunique(),
        "ili_weeks": g.ili_pct.count(), "ili_mean": g.ili_pct.mean(), "ili_max": g.ili_pct.max(),
        "hosp_weeks": g.rate_flu.count(), "hosp_total": g.hosp_flu.sum(min_count=1),
        "rate_flu_cum": g.rate_flu.sum(min_count=1), "rate_flu_max": g.rate_flu.max(),
        "weeks_cdc_high": g.cdc_level.apply(lambda x: int((x >= 3).sum()) if x.notna().any() else pd.NA),
        "ah_anomaly_mean": g.ah_anomaly.mean(), "pm25_mean": g.pm25_mean.mean(),
    }).reset_index()
    s = s.merge(vax[["state", "season", "flu_vax_pct", "vax_ci_low", "vax_ci_high", "vax_month"]],
                on=["state", "season"], how="outer")
    for c in MILESTONE_COLS:            # TV3 dien (season_milestones.parquet)
        s[c] = pd.Series(pd.NA, index=s.index, dtype="datetime64[ns]" if c.endswith("_week") else "object")
    s["baseline"] = s["baseline"].astype("float64")
    s["peak_value"] = s["peak_value"].astype("float64")
    s["severity"] = s["severity"].astype("string")
    s["source"] = s["source"].astype("string")
    s["is_current_season"] = s["season"] == fact.loc[fact.week.idxmax(), "season"]
    for c in ("weeks_in_data", "ili_weeks", "hosp_weeks", "weeks_cdc_high", "vax_month"):
        s[c] = s[c].astype("Int64")
    s = s[s.state.isin(STATES)]
    first = ["state", "season", "flu_vax_pct"] + MILESTONE_COLS
    return s[first + [c for c in s.columns if c not in first]].sort_values(["state", "season"]).reset_index(drop=True)


# ============================== Ghep file cua TV3, TV5 ==============================

def merge_partner_files(paths, dim_state, season_summary):
    """Ghep ket qua cua TV3 vao dim_state / fact_season_summary neu da co trong data/business/. Tra ve trang thai."""
    biz = paths.data / "business"
    status = {}
    p = biz / "state_cluster.parquet"
    if p.exists():
        c = pd.read_parquet(p)
        c["state"] = c["state"].str.lower()
        dim_state = dim_state.drop(columns="cluster_id").merge(c[["state", "cluster_id"]], on="state", how="left")
        dim_state["cluster_id"] = pd.to_numeric(dim_state["cluster_id"], errors="coerce").astype("Int64")
        status["state_cluster"] = f"da ghep ({'stub' if c.get('is_stub', pd.Series([False])).any() else 'that'})"
    else:
        status["state_cluster"] = "chua co (TV3) -> cluster_id de trong"
    p = biz / "season_milestones.parquet"
    if p.exists():
        m = pd.read_parquet(p)
        m["state"] = m["state"].str.lower()
        m["season"] = m["season"].astype("string")
        cols = [c for c in MILESTONE_COLS if c in m]
        season_summary = season_summary.drop(columns=cols).merge(m[["state", "season"] + cols],
                                                                 on=["state", "season"], how="left")
        status["season_milestones"] = f"da ghep {len(cols)} cot"
    else:
        status["season_milestones"] = "chua co (TV3) -> cot moc mua de trong"
    for name, who in [("season_phase.parquet", "TV3"), ("alert_forecast.parquet", "TV5"),
                      ("model_eval.json", "TV5"), ("roc_points.csv", "TV5"),
                      ("risk_rate_ratios.csv", "TV4"), ("whatif.parquet", "TV4")]:
        status[name] = "co" if (biz / name).exists() else f"chua co ({who} giao thang vao data/business/)"
    return dim_state, season_summary, status


# ============================== Chay ==============================

def build_business(paths):
    biz = paths.data / "business"
    biz.mkdir(parents=True, exist_ok=True)
    log_path = paths.data / "clean" / "_clean_log.json"
    clean_log = json.loads(log_path.read_text(encoding="utf-8")) if log_path.exists() else {}

    last = max(_clean(paths, t).week.max() for t in ("ilinet", "nhsn", "nssp"))
    dim_time = build_dim_time(paths, last)
    dim_state = build_dim_state(paths)
    dim_source = build_dim_source(paths, clean_log)
    fact = build_fact_flu_week(paths, dim_time)
    season = build_fact_season_summary(paths, fact)
    dim_state, season, status = merge_partner_files(paths, dim_state, season)

    # Toan ven tham chieu (khoa ngoai) truoc khi ghi
    assert fact.state.isin(dim_state.state).all(), "fact_flu_week co state khong co trong dim_state"
    assert fact.week.isin(dim_time.week).all(), "fact_flu_week co week khong co trong dim_time"
    assert season.state.isin(dim_state.state).all(), "fact_season_summary co state khong co trong dim_state"
    assert not fact.duplicated(["state", "week"]).any() and not season.duplicated(["state", "season"]).any()

    tables = {"dim_state": dim_state, "dim_time": dim_time, "dim_source": dim_source,
              "fact_flu_week": fact, "fact_season_summary": season}
    for name, df in tables.items():
        df.to_parquet(biz / f"{name}.parquet", index=False, compression="snappy")
        log.info("business/%s.parquet: %d dong x %d cot", name, len(df), df.shape[1])
    meta = {"built_at": dt.datetime.now().isoformat(timespec="seconds"),
            "last_week": str(last.date()), "preliminary_from": str((last - pd.Timedelta(weeks=PRELIM_WEEKS - 1)).date()),
            "tables": {n: {"rows": len(d), "columns": list(d.columns)} for n, d in tables.items()},
            "partner_files": status}
    (biz / "_business_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return tables, status
