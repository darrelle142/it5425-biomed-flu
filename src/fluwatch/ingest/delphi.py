"""Delphi Epidata V5: ILINet, NHSN, NSSP, xet nghiem, FluSurv-NET, NWSS (ban chup + lich su sua so)."""
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
