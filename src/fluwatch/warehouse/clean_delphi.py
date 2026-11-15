"""clean/: cac nguon lay qua Delphi Epidata V5 (ILINet, NHSN, NSSP, xet nghiem, FluSurv).

Moi file raw Delphi la dang dai: geo_value, reference_time (thu Bay ket thuc tuan), report_time, value
(+ age_group voi ILINet, xet nghiem). Moi bang clean la dang rong bang x tuan, moi tin hieu mot cot.
Dung ban moi nhat cua tung file (gom ca ban tai lai trong ngay); lich su sua so (archive__*) giu nguyen o raw/
cho TV5 backtest.
"""
import pandas as pd

from .common import add_time_keys, dedupe, keep_states, latest_raw, negative_to_na

# bang clean -> [(nguon raw, ten file, cot dau ra, don vi)]
DELPHI_TABLES = {
    "ilinet": [
        ("fluview_ilinet", "ili__state", "ili_pct", "% luot kham co ILI (co trong so)"),
        ("fluview_ilinet", "num_ili__state", "num_ili", "so luot kham ILI / tuan"),
        ("fluview_ilinet", "num_patients__state", "num_patients", "tong luot kham / tuan"),
        ("fluview_ilinet", "num_providers__state", "num_providers", "so co so bao cao"),
    ],
    "nhsn": [
        ("nhsn", "confirmed_admissions_flu_ew__state", "hosp_flu", "ca nhap vien cum xac nhan / tuan"),
        ("nhsn", "confirmed_admissions_flu_per100k_ew__state", "rate_flu", "ca nhap vien / 100.000 dan / tuan"),
        ("nhsn", "hosprep_confirmed_admissions_flu_ew__state", "hosp_reporting", "so benh vien bao cao"),
        ("nhsn", "inpatient_beds_flu_pct_ew__state", "beds_flu_pct", "% giuong noi tru co benh nhan cum"),
    ],
    "nssp": [
        ("nssp", "pct_ed_visits_influenza__state", "ed_pct_flu", "% luot cap cuu do cum"),
        ("nssp", "pct_ed_visits_covid__state", "ed_pct_covid", "% luot cap cuu do COVID-19"),
    ],
    "lab_clinical": [
        ("fluview_resp_lab_clinical", "pct_positive__state", "lab_pct_pos", "% mau xet nghiem duong tinh cum"),
        ("fluview_resp_lab_clinical", "total_specimens__state", "lab_specimens", "so mau xet nghiem / tuan"),
    ],
    "flusurv": [
        ("flusurv", "rate_overall__state", "flusurv_rate", "ca nhap vien / 100.000 dan / tuan (FluSurv-NET)"),
    ],
}
COUNT_COLS = {"num_ili", "num_patients", "num_providers", "hosp_flu", "hosp_reporting", "lab_specimens"}


def _signal(paths, table, source, stem, col, clog):
    f = latest_raw(paths, source, stem, ".csv.gz")
    clog.source(table, paths, f)
    d = pd.read_csv(f, low_memory=False)
    if "age_group" in d:
        other = d.age_group != "all"
        if other.any():
            clog.step(table, f"{col}: bo nhom tuoi khac 'all'", other.sum())
        d = d[~other]
    d = d.rename(columns={"geo_value": "state", "reference_time": "week", "value": col})
    d["week"] = pd.to_datetime(d["week"])
    d["report_time"] = pd.to_datetime(d["report_time"], utc=True).dt.tz_localize(None)
    d = keep_states(d, table, clog, what=col)
    not_sat = d["week"].dt.weekday != 5
    if not_sat.any():
        raise ValueError(f"{f}: {int(not_sat.sum())} dong co reference_time khong phai thu Bay")
    d = dedupe(d, ["state", "week"], table, clog, order="report_time")
    d = negative_to_na(d, [col], table, clog)
    return d[["state", "week", col, "report_time"]]


def clean_delphi(paths, table, clog):
    """Mot bang clean Delphi: state, week, epiweek, season, season_week, <tin hieu...>, report_date."""
    out = None
    for source, stem, col, _unit in DELPHI_TABLES[table]:
        d = _signal(paths, table, source, stem, col, clog).rename(columns={"report_time": f"_rt_{col}"})
        out = d if out is None else out.merge(d, on=["state", "week"], how="outer")
    rt = [c for c in out.columns if c.startswith("_rt_")]
    out["report_date"] = out[rt].max(axis=1).dt.normalize()   # lan cong bo moi nhat cua dong nay
    out = out.drop(columns=rt)
    for _s, _f, col, _u in DELPHI_TABLES[table]:
        if col in COUNT_COLS:
            out[col] = out[col].round().astype("Int64")
    out = add_time_keys(out)
    cols = ["state", "week", "epiweek", "season", "season_week"] + [c for _, _, c, _ in DELPHI_TABLES[table]] + ["report_date"]
    return out[cols].sort_values(["state", "week"]).reset_index(drop=True)
