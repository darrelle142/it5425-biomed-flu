"""Crawl thu cac bo du lieu cong khai cho project cum mua, luu nguyen trang vao data/raw.

Cach chay (tu thu muc project):
    python scripts/crawl_sample.py delphi     # Delphi V5, khoang 8 phut vi gioi han toc do
    python scripts/crawl_sample.py weather    # Open-Meteo thoi tiet va PM2.5, moi bang 1 diem
    python scripts/crawl_sample.py files      # File tinh: EPA AirData, dan so, trang FluVaxView

Moi file tai ve duoc ghi vao data/raw/manifest.jsonl (nguon, url, thoi diem, kich thuoc,
sha256, ma HTTP) de truy nguoc duoc nguon goc.
"""
import datetime as dt
import gzip
import hashlib
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
REF = ROOT / "data" / "reference"
TODAY = dt.date.today().isoformat()
MANIFEST = RAW / "manifest.jsonl"
V5 = "https://delphi.cmu.edu/epidata/v5"
SNAPSHOT_WAIT = 21  # gioi han an danh: 3 yeu cau snapshot moi phut
ARCHIVE_WAIT = 13  # gioi han an danh: 5 yeu cau archive moi phut


def fetch(url, timeout=300):
    """GET mot URL. Tra ve (ma HTTP, noi dung byte); khong thu lai khi bi tu choi."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as err:
        return err.code, err.read()
    except Exception as err:  # loi mang: ghi lai, khong dung ca dot crawl
        return 0, str(err).encode()


def save(source, name, url, status, body, gz=True):
    """Luu noi dung vao raw/<nguon>/<ngay tai>/ va them mot dong vao manifest."""
    folder = RAW / source / TODAY
    folder.mkdir(parents=True, exist_ok=True)
    ok = status == 200
    path = folder / (name + (".gz" if gz else ""))
    if ok:
        path.write_bytes(gzip.compress(body) if gz else body)
    with MANIFEST.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "source": source,
            "file": str(path.relative_to(ROOT)).replace("\\", "/") if ok else None,
            "url": url,
            "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "http_status": status,
            "bytes": len(body),
            "sha256": hashlib.sha256(body).hexdigest() if ok else None,
        }, ensure_ascii=False) + "\n")
    print(f"{status} {len(body):>11,} bytes  {source}/{name}", flush=True)
    return ok


def delphi():
    (RAW).mkdir(parents=True, exist_ok=True)
    meta_url = f"{V5}/metadata/"
    status, body = fetch(meta_url)
    save("delphi_meta", "metadata.json", meta_url, status, body, gz=False)

    # (nguon, tin hieu, cap dia ly, tham so them)
    snapshots = [
        ("fluview_ilinet", "ili", "state", {}),
        ("fluview_ilinet", "num_ili", "state", {}),
        ("fluview_ilinet", "num_patients", "state", {}),
        ("fluview_ilinet", "num_providers", "state", {}),
        ("nhsn", "confirmed_admissions_flu_ew", "state", {}),
        ("nhsn", "confirmed_admissions_flu_per100k_ew", "state", {}),
        ("nhsn", "hosprep_confirmed_admissions_flu_ew", "state", {}),
        ("nhsn", "inpatient_beds_flu_pct_ew", "state", {}),
        ("nssp", "pct_ed_visits_influenza", "state", {}),
        ("nssp", "pct_ed_visits_covid", "state", {}),
        ("fluview_resp_lab_clinical", "pct_positive", "state", {}),
        ("fluview_resp_lab_clinical", "total_specimens", "state", {}),
        ("flusurv", "rate_overall", "state", {}),
        ("nwss", "flu_flowpop_lin", "sewershed", {}),
    ]
    for source, signal, geo, extra in snapshots:
        query = {"source": source, "signal": signal, "geo_type": geo, **extra}
        url = f"{V5}/snapshot/?{urllib.parse.urlencode(query)}"
        status, body = fetch(url, timeout=500)
        save(source, f"{signal}__{geo}.csv", url, status, body)
        time.sleep(SNAPSHOT_WAIT)

    # Lich su sua so lieu tu 10/2024, dung de do muc do sua ve sau
    archives = [
        ("fluview_ilinet", "ili", "state"),
        ("nhsn", "confirmed_admissions_flu_ew", "state"),
        ("nssp", "pct_ed_visits_influenza", "state"),
    ]
    for source, signal, geo in archives:
        query = {"source": source, "signal": signal, "geo_type": geo,
                 "report_time_query": ">2024-10-01"}
        url = f"{V5}/archive/?{urllib.parse.urlencode(query)}"
        status, body = fetch(url, timeout=500)
        save(source, f"archive__{signal}__{geo}.csv", url, status, body)
        time.sleep(ARCHIVE_WAIT)


def load_cities():
    import csv
    with (REF / "cities_largest_per_state.csv").open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def get_json_with_wait(url):
    for attempt in range(3):
        status, body = fetch(url, timeout=180)
        if status != 429:
            return status, body
        print("  429, cho 70 giay theo gioi han cua Open-Meteo", flush=True)
        time.sleep(70)
    return status, body


def weather():
    end = (dt.date.today() - dt.timedelta(days=7)).isoformat()
    for city in load_cities():
        state = city["state"]
        query = {"latitude": city["lat"], "longitude": city["lon"], "timezone": "auto",
                 "start_date": "2010-01-01", "end_date": end,
                 "daily": "temperature_2m_mean,relative_humidity_2m_mean"}
        url = "https://archive-api.open-meteo.com/v1/archive?" + urllib.parse.urlencode(query)
        status, body = get_json_with_wait(url)
        save("openmeteo_weather", f"{state}.json", url, status, body)
        time.sleep(2)
        query = {"latitude": city["lat"], "longitude": city["lon"], "timezone": "auto",
                 "start_date": "2022-08-01", "end_date": end, "hourly": "pm2_5"}
        url = "https://air-quality-api.open-meteo.com/v1/air-quality?" + urllib.parse.urlencode(query)
        status, body = get_json_with_wait(url)
        save("openmeteo_pm25", f"{state}.json", url, status, body)
        time.sleep(2)


def files():
    targets = [
        ("epa_airdata", "daily_88101_2024.zip", "https://aqs.epa.gov/aqsweb/airdata/daily_88101_2024.zip", False),
        ("population", "state_pop_2020_delphi.csv",
         "https://raw.githubusercontent.com/cmu-delphi/covidcast-indicators/main/"
         "_delphi_utils_python/delphi_utils/data/2020/state_pop.csv", False),
    ]
    for season in ["2019-2020", "2020-2021", "2021-2022", "2022-2023", "2024-2025", "2025-2026"]:
        targets.append(("fluvaxview_pages", f"{season}.html",
                        f"https://www.cdc.gov/fluvaxview/coverage-by-season/{season}.html", True))
    for source, name, url, gz in targets:
        status, body = fetch(url)
        save(source, name, url, status, body, gz=gz)
        time.sleep(1)


if __name__ == "__main__":
    {"delphi": delphi, "weather": weather, "files": files}[sys.argv[1]]()
