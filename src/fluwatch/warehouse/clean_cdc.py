"""clean/: cac file CDC tai qua GitHub Actions (data.cdc.gov chan may o Viet Nam).

- wval: muc virus cum A trong nuoc thai (WVAL, bo atcp-73re), theo tram -> bang x tuan,
  trung binh co trong so dan so phuc vu cua tram. Gop moi lan tai (moi lan CDC chi tra mot khoang thoi gian),
  trung (tram, tuan) thi giu ban tai moi nhat.
- vaccine: do phu vaccine cum >= 6 thang tuoi theo bang x mua (bo vh55-3he6), lay THANG CUOI CO SO cua mua.
"""
import re

import numpy as np
import pandas as pd

from .common import add_time_keys, dedupe, keep_states, negative_to_na, state_names

WVAL_GLOB = "CDC_Wastewater_Viral_Activity_Level_for_SARS-CoV-2,_Influenza_A_and_RSV_*.csv"
VAX_GLOB = "Influenza_Vaccination_Coverage_for_All_Ages_(6+_Months)_*.csv"


def _files(paths, source, pattern):
    return sorted((paths.raw / source).glob(f"*/{pattern}"), key=lambda p: (p.parent.name, p.name))


def clean_wval(paths, clog):
    name = "wval"
    names, fpop = state_names(paths)
    clog.source(name, paths, fpop)
    parts = []
    for i, f in enumerate(_files(paths, "cdc_wastewater_wval", WVAL_GLOB)):
        clog.source(name, paths, f)
        d = pd.read_csv(f, low_memory=False, dtype={"Site": str})
        parts.append(d.assign(_order=i))
    if not parts:
        raise FileNotFoundError("Khong thay data/raw/cdc_wastewater_wval/*/*.csv")
    ww = pd.concat(parts, ignore_index=True)
    other = ww.Pathogen_Target != "Influenza A virus"
    clog.step(name, "bo tac nhan khac cum A (SARS-CoV-2, RSV)", other.sum())
    ww = ww[~other].copy()
    ww["week"] = pd.to_datetime(ww.Week_End)
    # Moi lan tai la ca lich su: moi tuan chi dung ban tai moi nhat co tuan do (CDC co the loai tram khoi WVAL);
    # ban cu chi bu cho nhung tuan ma ban moi khong con.
    newest = ww.groupby("week")["_order"].transform("max")
    old = ww["_order"] < newest
    clog.step(name, "bo dong cua ban tai cu (tuan da co trong ban moi hon)", old.sum())
    ww = dedupe(ww[~old], ["Site", "week"], name, clog, order="_order")
    ww["state"] = ww["State/Territory"].str.lower().map(names)
    unk = ww["state"].isna()
    if unk.any():
        clog.step(name, "bo dong ten bang khong khop", unk.sum(),
                  ", ".join(sorted(ww.loc[unk, "State/Territory"].astype(str).unique())))
    ww = keep_states(ww[~unk], name, clog)
    ww["wval"] = pd.to_numeric(ww.Site_WVAL, errors="coerce")
    ww = negative_to_na(ww, ["wval"], name, clog)
    ww = ww.dropna(subset=["wval"])
    ww["pop"] = pd.to_numeric(ww.Population_Served.astype(str).str.replace(",", ""), errors="coerce")
    nopop = ww["pop"].isna() | (ww["pop"] <= 0)
    if nopop.any():
        clog.step(name, "tram thieu dan so phuc vu -> dung trung vi lam trong so", nopop.sum())
    ww["w"] = ww["pop"].where(~nopop, ww.loc[~nopop, "pop"].median())
    ww["wx"] = ww.wval * ww.w
    g = ww.groupby(["state", "week"])
    sw = pd.DataFrame({"wval": g.wx.sum() / g.w.sum(), "wval_sites": g.Site.nunique(),
                       "wval_pop_served": g.w.sum()}).reset_index()
    sw["wval_sites"] = sw["wval_sites"].astype("Int64")
    sw["wval_pop_served"] = sw["wval_pop_served"].round().astype("Int64")
    sw = add_time_keys(sw)
    cols = ["state", "week", "epiweek", "season", "season_week", "wval", "wval_sites", "wval_pop_served"]
    return sw[cols].sort_values(["state", "week"]).reset_index(drop=True)


def _ci(s):
    m = re.match(r"\s*([\d.]+)\s*to\s*([\d.]+)", str(s))
    return (float(m.group(1)), float(m.group(2))) if m else (np.nan, np.nan)


def clean_vaccine(paths, clog):
    name = "vaccine"
    names, fpop = state_names(paths)
    clog.source(name, paths, fpop)
    files = _files(paths, "cdc_fluvax_coverage", VAX_GLOB)
    if not files:
        raise FileNotFoundError("Khong thay data/raw/cdc_fluvax_coverage/*/*.csv")
    f = files[-1]
    clog.source(name, paths, f)
    vx = pd.read_csv(f, dtype=str)
    keep = ((vx.Vaccine == "Seasonal Influenza") & (vx["Geography Type"] == "States/Local Areas")
            & vx.Dimension.isin([">=6 Months", "Greater than 6 Months flu"]))   # mua 2023-24 dung nhan thu hai
    clog.step(name, "bo dong khong phai vaccine cum mua / bang / nhom >= 6 thang", (~keep).sum())
    v = vx[keep].copy()
    v["state"] = v.Geography.str.lower().map(names)
    unk = v["state"].isna()
    if unk.any():
        clog.step(name, "bo dia ban khong phai bang (thanh pho, vung)", unk.sum(),
                  ", ".join(sorted(v.loc[unk, "Geography"].unique())[:12]))
    v = keep_states(v[~unk], name, clog)
    v["flu_vax_pct"] = pd.to_numeric(v["Estimate (%)"], errors="coerce")
    v = negative_to_na(v, ["flu_vax_pct"], name, clog)
    over = v.flu_vax_pct > 100
    if over.any():
        clog.step(name, "do phu > 100% -> thieu", over.sum())
        v.loc[over, "flu_vax_pct"] = np.nan
    nr = v.flu_vax_pct.isna()
    clog.step(name, "bo thang khong co so (NR)", nr.sum())
    v = v[~nr]
    v["vax_month"] = v.Month.astype(int)
    v["_order"] = (v.vax_month - 7) % 12        # thang 7 = dau mua ... thang 6 = cuoi mua
    v = v.rename(columns={"Season/Survey Year": "season"})
    last = v.sort_values("_order").groupby(["state", "season"]).tail(1).copy()
    last[["vax_ci_low", "vax_ci_high"]] = last["95% CI (%)"].apply(lambda s: pd.Series(_ci(s))).values
    last["vax_sample_size"] = pd.to_numeric(last["Sample Size"].str.replace(",", ""), errors="coerce").astype("Int64")
    last["season"] = last["season"].astype("string")
    cols = ["state", "season", "flu_vax_pct", "vax_ci_low", "vax_ci_high", "vax_sample_size", "vax_month"]
    return last[cols].sort_values(["state", "season"]).reset_index(drop=True)
