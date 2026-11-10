"""Tai thoi tiet va PM2.5 Open-Meteo cho cac thanh pho trong data/reference/cities.csv.

Cach chay (tu thu muc project):
    python scripts/crawl_cities_weather.py            # tai lich su day du cho thanh pho chua co file
    python scripts/crawl_cities_weather.py --update   # cap nhat hang tuan: chi tai doan gan day

Che do --update tai RECENT_DAYS ngay gan nhat cho ca 236 thanh pho (2 luot goi moi thanh pho), luu thanh
<bang>__<thanh_pho>__recent.json trong thu muc ngay tai. build_environment.py ghep moi file cua mot thanh pho
theo ngay, ngay trung thi lay ban tai sau cung (Open-Meteo sua so lieu vai ngay gan nhat).

Che do mac dinh chay lai duoc nhieu lan: file da tai (o bat ky ngay nao) thi bo qua. Neu Open-Meteo bao het luot
trong ngay (HTTP 429 lap lai), script dung lai; chay lai vao hom sau de tai not phan con thieu.
Thanh pho lon nhat cua moi bang dung lai file da tai o crawl_sample.py neu cach toa do cu duoi 15 km.
"""
import argparse
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
RECENT_DAYS = 35  # chong lap voi lan cap nhat truoc, phong khi mot tuan bi loi


def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def have(source, name):
    return bool(glob.glob(str(RAW / source / "*" / (name + ".gz"))))


def km(a, b, c, d):
    from math import asin, cos, radians, sin, sqrt
    h = sin(radians(c - a) / 2) ** 2 + cos(radians(a)) * cos(radians(c)) * sin(radians(d - b) / 2) ** 2
    return 12742 * asin(sqrt(h))


def get(url, timeout=180):
    for wait in (70, 300):
        status, body = fetch(url, timeout=timeout)
        if status != 429:
            return status, body
        print(f"  429, cho {wait} giay", flush=True)
        time.sleep(wait)
    status, body = fetch(url, timeout=timeout)
    if status == 429:
        print("Open-Meteo van tra 429: co the da het luot trong ngay. Dung lai, hay chay lai vao ngay mai.")
        sys.exit(2)
    return status, body


def get_json(url, tries=3, timeout=180, waits=(30, 60)):
    """Goi get() va kiem tra JSON; thu lai khi 503, loi mang hoac 200 kem thong bao loi."""
    for i in range(tries):
        status, body = get(url, timeout)
        if status == 200:
            try:
                return 200, body, json.loads(body)
            except ValueError:  # Open-Meteo doi khi tra 200 kem thong bao loi (vd. timeoutReached)
                print("  noi dung khong phai JSON:", body[:80], flush=True)
                status = 0
        if i < tries - 1:
            print(f"  loi {status} ({body[:120]!r}), thu lai sau {waits[i]} giay", flush=True)
            time.sleep(waits[i])
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


ap = argparse.ArgumentParser()
ap.add_argument("--update", action="store_true", help=f"chi tai {RECENT_DAYS} ngay gan nhat cho moi thanh pho")
args = ap.parse_args()
cities = list(csv.DictReader((REF / "cities.csv").open(encoding="utf-8")))


BATCH = 50  # Open-Meteo nhan nhieu toa do trong mot lan goi, tra ve danh sach theo dung thu tu


def update():
    """Tai doan gan day (thoi tiet + PM2.5) cho moi thanh pho, gom BATCH thanh pho mot lan goi.

    Moi thanh pho van duoc luu thanh mot file rieng. Tra ve so file loi.
    """
    start = (dt.date.fromisoformat(END) - dt.timedelta(days=RECENT_DAYS)).isoformat()
    bad = 0
    for source, base, extra in [
            ("openmeteo_weather_cities", "https://archive-api.open-meteo.com/v1/archive?",
             {"daily": "temperature_2m_mean,relative_humidity_2m_mean"}),
            ("openmeteo_pm25_cities", "https://air-quality-api.open-meteo.com/v1/air-quality?",
             {"hourly": "pm2_5"})]:
        for i in range(0, len(cities), BATCH):
            group = cities[i:i + BATCH]
            q = {"latitude": ",".join(c["lat"] for c in group), "longitude": ",".join(c["lon"] for c in group),
                 "timezone": "auto", "start_date": start, "end_date": END, **extra}
            url = base + urllib.parse.urlencode(q)
            status, body, js = get_json(url, timeout=60, waits=(10, 30))
            if js is not None and not isinstance(js, list):
                js = [js]  # chi mot toa do thi Open-Meteo tra ve mot object
            if js is not None and len(js) != len(group):
                print(f"  {source}: gui {len(group)} toa do, nhan {len(js)} ket qua", flush=True)
                status, js = 0, None
            for k, c in enumerate(group):
                name = f"{c['state']}__{slug(c['city'])}__recent.json"
                part = json.dumps(js[k]).encode() if js is not None else body
                save(source, name, url, status, part)
                bad += js is None
            time.sleep(2)
    print(f"Xong cap nhat {start} -> {END}: {2 * len(cities) - bad}/{2 * len(cities)} file thanh cong.")
    return bad


if args.update:  # loi le te van chay tiep (bang dung tam so lieu cu); loi tren 10% thi bao that bai
    sys.exit(1 if update() > 0.1 * 2 * len(cities) else 0)

old = {r["state"]: r for r in csv.DictReader((REF / "cities_largest_per_state.csv").open(encoding="utf-8"))}
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
