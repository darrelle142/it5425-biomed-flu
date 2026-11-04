"""Tai thoi tiet va PM2.5 Open-Meteo cho cac thanh pho trong data/reference/cities.csv.

Cach chay (tu thu muc project):
    python scripts/crawl_cities_weather.py

Chay lai duoc nhieu lan: file da tai (o bat ky ngay nao) thi bo qua. Neu Open-Meteo bao het luot
trong ngay (HTTP 429 lap lai), script dung lai; chay lai vao hom sau de tai not phan con thieu.
Thanh pho lon nhat cua moi bang dung lai file da tai o crawl_sample.py neu cach toa do cu duoi 15 km.
"""
import csv
import datetime as dt
import glob
import json
import re
import sys
import time
import unicodedata
import urllib.parse

from crawl_sample import REF, RAW, fetch, save

END = (dt.date.today() - dt.timedelta(days=7)).isoformat()


def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def have(source, name):
    return bool(glob.glob(str(RAW / source / "*" / (name + ".gz"))))


def km(a, b, c, d):
    from math import asin, cos, radians, sin, sqrt
    h = sin(radians(c - a) / 2) ** 2 + cos(radians(a)) * cos(radians(c)) * sin(radians(d - b) / 2) ** 2
    return 12742 * asin(sqrt(h))


def get(url):
    for wait in (70, 300):
        status, body = fetch(url, timeout=180)
        if status != 429:
            return status, body
        print(f"  429, cho {wait} giay", flush=True)
        time.sleep(wait)
    status, body = fetch(url, timeout=180)
    if status == 429:
        print("Open-Meteo van tra 429: co the da het luot trong ngay. Dung lai, hay chay lai vao ngay mai.")
        sys.exit(2)
    return status, body


def get_json(url, tries=3):
    """Goi get() va kiem tra JSON; thu lai khi 503, loi mang hoac 200 kem thong bao loi."""
    for i in range(tries):
        status, body = get(url)
        if status == 200:
            try:
                return 200, body, json.loads(body)
            except ValueError:  # Open-Meteo doi khi tra 200 kem thong bao loi (vd. timeoutReached)
                print("  noi dung khong phai JSON:", body[:80], flush=True)
                status = 0
        if i < tries - 1:
            print(f"  loi {status}, thu lai sau {30 * (i + 1)} giay", flush=True)
            time.sleep(30 * (i + 1))
    return status, body, None


# Tai thoi tiet thanh nhieu doan ngan: yeu cau 16 nam mot lan hay bi may chu timeout
CHUNKS = [("2010-01-01", "2014-12-31"), ("2015-01-01", "2019-12-31"), ("2020-01-01", "2023-12-31"), ("2024-01-01", END)]


def get_chunked(base, q):
    urls, merged = [], None
    for start, end in CHUNKS:
        url = base + urllib.parse.urlencode({**q, "start_date": start, "end_date": end})
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


old = {r["state"]: r for r in csv.DictReader((REF / "cities_largest_per_state.csv").open(encoding="utf-8"))}
cities = list(csv.DictReader((REF / "cities.csv").open(encoding="utf-8")))
done = skipped = 0
for c in cities:
    s, lat, lon = c["state"], float(c["lat"]), float(c["lon"])
    o = old.get(s)
    if o and km(lat, lon, float(o["lat"]), float(o["lon"])) < 15 and have("openmeteo_weather", f"{s}.json"):
        skipped += 1  # dung lai file thanh pho lon nhat da tai
        continue
    name = f"{s}__{slug(c['city'])}.json"
    jobs = [("openmeteo_weather_cities", "https://archive-api.open-meteo.com/v1/archive?", {
                "start_date": "2010-01-01", "daily": "temperature_2m_mean,relative_humidity_2m_mean"}),
            ("openmeteo_pm25_cities", "https://air-quality-api.open-meteo.com/v1/air-quality?", {
                "start_date": "2022-08-01", "hourly": "pm2_5"})]
    for source, base, extra in jobs:
        if have(source, name):
            continue
        q = {"latitude": lat, "longitude": lon, "timezone": "auto", "end_date": END, **extra}
        if source == "openmeteo_weather_cities":
            q = {k: v for k, v in q.items() if k not in ("start_date", "end_date")}
            status, body, url = get_chunked(base, q)
        else:
            url = base + urllib.parse.urlencode(q)
            status, body, _ = get_json(url)
        save(source, name, url, status, body)
        done += 1
        time.sleep(3)
print(f"Xong: tai moi {done} file, dung lai {skipped} thanh pho da co.")
