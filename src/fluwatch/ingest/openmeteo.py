"""Open-Meteo: thoi tiet lich su (archive API) va PM2.5 (air-quality API) theo thanh pho."""
import csv
import datetime as dt
import json
import re
import time
import unicodedata
import urllib.parse
from math import asin, cos, radians, sin, sqrt

from .net import get_json, get_polite

ARCHIVE = "https://archive-api.open-meteo.com/v1/archive?"
AIR = "https://air-quality-api.open-meteo.com/v1/air-quality?"
DAILY = "temperature_2m_mean,relative_humidity_2m_mean"
WEATHER_START = "2010-01-01"
PM25_START = "2022-08-01"  # air-quality API co so lieu tu 08/2022
RECENT_DAYS = 35  # che do cap nhat: chong lap voi lan truoc, phong khi mot tuan bi loi
BATCH = 50  # so toa do moi lan goi (Open-Meteo tra danh sach dung thu tu)


def history_end():
    """Ngay cuoi lay so lieu: 7 ngay truoc (archive API tre khoang 5 ngay)."""
    return (dt.date.today() - dt.timedelta(days=7)).isoformat()


def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def km(lat1, lon1, lat2, lon2):
    h = sin(radians(lat2 - lat1) / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(radians(lon2 - lon1) / 2) ** 2
    return 12742 * asin(sqrt(h))


def load_cities(path):
    with open(path, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def chunks(end):
    """Chia lich su thoi tiet thanh doan ngan: yeu cau 16 nam mot lan hay bi may chu timeout."""
    return [("2010-01-01", "2014-12-31"), ("2015-01-01", "2019-12-31"), ("2020-01-01", "2023-12-31"), ("2024-01-01", end)]


def get_chunked(base, query, end):
    """Tai tung doan roi ghep cot 'daily'. Tra ve (ma HTTP, noi dung byte, cac URL noi bang ' | ')."""
    urls, merged = [], None
    for start, stop in chunks(end):
        url = base + urllib.parse.urlencode({**query, "start_date": start, "end_date": stop})
        urls.append(url)
        status, body, js = get_json(url)
        if js is None:
            return status, body, " | ".join(urls)
        if merged is None:
            merged = js
        else:
            for k, v in js["daily"].items():
                merged["daily"][k] += v
        time.sleep(2)
    return 200, json.dumps(merged).encode(), " | ".join(urls)


def crawl_largest_cities(store, cities, end=None):
    """Thanh pho lon nhat moi bang (cities_largest_per_state.csv): lich su day du, mot lan goi moi API."""
    end = end or history_end()
    for city in cities:
        state = city["state"]
        for source, base, extra in [("openmeteo_weather", ARCHIVE, {"start_date": WEATHER_START, "daily": DAILY}),
                                    ("openmeteo_pm25", AIR, {"start_date": PM25_START, "hourly": "pm2_5"})]:
            query = {"latitude": city["lat"], "longitude": city["lon"], "timezone": "auto", "end_date": end, **extra}
            url = base + urllib.parse.urlencode(query)
            status, body = get_polite(url, timeout=180, waits=(70, 70))
            store.save(source, f"{state}.json", url, status, body)
            time.sleep(2)


def crawl_city_history(store, cities, largest, end=None):
    """Lich su day du cho cac thanh pho trong cities.csv chua co file (o bat ky ngay tai nao).

    Thanh pho lon nhat cua bang dung lai file cua crawl_largest_cities neu toa do cach duoi 15 km.
    Tra ve (so file tai moi, so thanh pho dung lai).
    """
    end = end or history_end()
    old = {r["state"]: r for r in largest}
    done = skipped = 0
    for c in cities:
        s, lat, lon = c["state"], float(c["lat"]), float(c["lon"])
        o = old.get(s)
        if o and km(lat, lon, float(o["lat"]), float(o["lon"])) < 15 and store.have("openmeteo_weather", f"{s}.json.gz"):
            skipped += 1
            continue
        name = f"{s}__{slug(c['city'])}.json"
        for source in ("openmeteo_weather_cities", "openmeteo_pm25_cities"):
            if store.have(source, name + ".gz"):
                continue
            q = {"latitude": lat, "longitude": lon, "timezone": "auto"}
            if source == "openmeteo_weather_cities":
                status, body, url = get_chunked(ARCHIVE, {**q, "daily": DAILY}, end)
            else:
                url = AIR + urllib.parse.urlencode({**q, "start_date": PM25_START, "end_date": end, "hourly": "pm2_5"})
                status, body, _ = get_json(url)
            store.save(source, name, url, status, body)
            done += 1
            time.sleep(3)
    return done, skipped


def update_cities(store, cities, days=RECENT_DAYS, end=None, batch=BATCH):
    """Che do cap nhat hang tuan: `days` ngay gan nhat cho moi thanh pho, gom `batch` thanh pho mot lan goi.

    Moi thanh pho van luu thanh mot file <bang>__<thanh_pho>__recent.json. Tra ve so file loi.
    """
    end = end or history_end()
    start = (dt.date.fromisoformat(end) - dt.timedelta(days=days)).isoformat()
    bad = 0
    for source, base, extra in [("openmeteo_weather_cities", ARCHIVE, {"daily": DAILY}),
                                ("openmeteo_pm25_cities", AIR, {"hourly": "pm2_5"})]:
        for i in range(0, len(cities), batch):
            group = cities[i:i + batch]
            q = {"latitude": ",".join(c["lat"] for c in group), "longitude": ",".join(c["lon"] for c in group),
                 "timezone": "auto", "start_date": start, "end_date": end, **extra}
            url = base + urllib.parse.urlencode(q)
            status, body, js = get_json(url, timeout=60, waits=(10, 30))
            if js is not None and not isinstance(js, list):
                js = [js]  # chi mot toa do thi Open-Meteo tra ve mot object
            if js is not None and len(js) != len(group):
                print(f"  {source}: gui {len(group)} toa do, nhan {len(js)} ket qua", flush=True)
                status, js = 0, None
            for k, c in enumerate(group):
                part = json.dumps(js[k]).encode() if js is not None else body
                store.save(source, f"{c['state']}__{slug(c['city'])}__recent.json", url, status, part)
                bad += js is None
            time.sleep(2)
    print(f"Xong cap nhat {start} -> {end}: {2 * len(cities) - bad}/{2 * len(cities)} file thanh cong.")
    return bad
