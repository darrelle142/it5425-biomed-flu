"""Delphi Epidata V5: ILINet, NHSN, NSSP, xet nghiem, FluSurv-NET, NWSS (ban chup + lich su sua so)."""
import json
import time
import urllib.parse

from .net import fetch

V5 = "https://delphi.cmu.edu/epidata/v5"
SNAPSHOT_WAIT = 21  # gioi han an danh: 3 yeu cau snapshot moi phut
ARCHIVE_WAIT = 13  # gioi han an danh: 5 yeu cau archive moi phut

# (nguon, tin hieu, cap dia ly)
SNAPSHOTS = [
    ("fluview_ilinet", "ili", "state"),
    ("fluview_ilinet", "num_ili", "state"),
    ("fluview_ilinet", "num_patients", "state"),
    ("fluview_ilinet", "num_providers", "state"),
    ("nhsn", "confirmed_admissions_flu_ew", "state"),
    ("nhsn", "confirmed_admissions_flu_per100k_ew", "state"),
    ("nhsn", "hosprep_confirmed_admissions_flu_ew", "state"),
    ("nhsn", "inpatient_beds_flu_pct_ew", "state"),
    ("nssp", "pct_ed_visits_influenza", "state"),
    ("nssp", "pct_ed_visits_covid", "state"),
    ("fluview_resp_lab_clinical", "pct_positive", "state"),
    ("fluview_resp_lab_clinical", "total_specimens", "state"),
    ("flusurv", "rate_overall", "state"),
    ("nwss", "flu_flowpop_lin", "sewershed"),
]
# Lich su sua so lieu tu 10/2024, dung de backtest "dung nhu luc cong bo"
ARCHIVES = [
    ("fluview_ilinet", "ili", "state"),
    ("nhsn", "confirmed_admissions_flu_ew", "state"),
    ("nssp", "pct_ed_visits_influenza", "state"),
]
ARCHIVE_SINCE = ">2024-10-01"


def crawl(store):
    """Tai metadata, moi ban chup va moi lich su sua so vao store (RawStore)."""
    meta_url = f"{V5}/metadata/"
    status, body = fetch(meta_url)
    store.save("delphi_meta", "metadata.json", meta_url, status, body, gz=False)

    for source, signal, geo in SNAPSHOTS:
        query = {"source": source, "signal": signal, "geo_type": geo}
        url = f"{V5}/snapshot/?{urllib.parse.urlencode(query)}"
        status, body = fetch(url, timeout=500)
        store.save(source, f"{signal}__{geo}.csv", url, status, body)
        time.sleep(SNAPSHOT_WAIT)

    for source, signal, geo in ARCHIVES:
        query = {"source": source, "signal": signal, "geo_type": geo, "report_time_query": ARCHIVE_SINCE}
        url = f"{V5}/archive/?{urllib.parse.urlencode(query)}"
        status, body = fetch(url, timeout=500)
        store.save(source, f"archive__{signal}__{geo}.csv", url, status, body)
        time.sleep(ARCHIVE_WAIT)

SOURCES = sorted({s for s, _, _ in SNAPSHOTS})


def latest_saved_metadata(paths):
    """Ban metadata Delphi tai gan nhat trong raw/delphi_meta/ (hoac None)."""
    files = sorted(paths.raw.glob("delphi_meta/*/metadata*.json"), key=lambda p: (p.parent.name, p.name))
    return json.loads(files[-1].read_text(encoding="utf-8")) if files else None


def new_updates(paths):
    """Nguon Delphi nao co latest_update moi hon ban metadata da luu. Tra ve (danh sach nguon, ghi chu).

    Dung de lich tu chay chi lam viec khi Delphi da co so lieu moi (khong tai trung moi tuan).
    """
    status, body = fetch(f"{V5}/metadata/", timeout=60)
    if status != 200:
        return SOURCES, f"khong doc duoc metadata Delphi (HTTP {status}): coi nhu co moi"
    now, old = json.loads(body), latest_saved_metadata(paths) or {}
    changed = [s for s in SOURCES if (now.get(s) or {}).get("latest_update") != (old.get(s) or {}).get("latest_update")]
    note = ", ".join(f"{s} {(now.get(s) or {}).get('latest_update')}" for s in changed) or "khong nguon nao doi"
    return changed, note
