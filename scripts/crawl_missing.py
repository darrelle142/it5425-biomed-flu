"""Tai cac bo du lieu con thieu (2/11/2026). Moi file ghi vao data/raw/<nguon>/<ngay>/ va manifest.

Cach chay (tu thu muc project):
    python scripts/crawl_missing.py

Khong thu lai va khong tim cach vuot qua khi bi 403: nguon nao bi chan thi ghi vao
data/raw/blocked_<ngay>.json de nhom tai tay.
"""
import json
import time

from crawl_sample import RAW, TODAY, fetch, save

targets = []

# 1. EPA AirData PM2.5 theo ngay, 2010-2026 (2024 da co)
for y in range(2010, 2027):
    if y != 2024:
        targets.append(("epa_airdata", f"daily_88101_{y}.zip", f"https://aqs.epa.gov/aqsweb/airdata/daily_88101_{y}.zip", False))

# 2. Census Gazetteer: toa do cac thanh pho de lap cities.csv 3-5 thanh pho moi bang
targets.append(("census_gazetteer", "2024_Gaz_place_national.zip",
                "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/2024_Gaz_place_national.zip", False))

# 3. Trang phuong phap HRD cua CDC (co bang nguong muc do theo bang)
targets.append(("cdc_methods", "hrd_data_methods.html",
                "https://www.cdc.gov/nhsn/psc/hospital-respiratory-reporting/data-methods.html", True))

# 4. Cac bo tren data.cdc.gov: thu mot lan de xac nhan con bi chan hay khong
for name, ds in [("nhsn_levels", "vdzy-6i9v"), ("nhsn_hrd", "ua7e-t2fy")]:
    targets.append(("cdc_socrata", f"{name}.csv", f"https://data.cdc.gov/api/views/{ds}/rows.csv?accessType=DOWNLOAD", True))

blocked = []
for source, name, url, gz in targets:
    status, body = fetch(url, timeout=600)
    ok = save(source, name, url, status, body, gz=gz)
    if not ok:
        blocked.append({"source": source, "file": name, "url": url, "http_status": status})
    time.sleep(2)

(RAW / f"blocked_{TODAY}.json").write_text(json.dumps(blocked, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"\n{len(targets) - len(blocked)}/{len(targets)} file tai duoc; bi chan hoac loi: {len(blocked)}")
