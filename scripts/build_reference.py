"""Tao cac bang tra cuu: cities.csv (3-5 thanh pho moi bang) va holidays.csv (tuan nghi le).

Dau vao:
    data/raw/census_popest_places/<ngay>/SUB-IP-EST2025-POP.xlsx   dan so do thi 2025
    data/raw/census_gazetteer/<ngay>/2024_Gaz_place_national.zip   toa do do thi
Dau ra:
    data/reference/cities.csv     state, city, lat, lon, population, weight
    data/reference/holidays.csv   moi tuan MMWR 2010-2028: co nghi le, nghi dong, so tuan toi ky nghi

Quy tac chon thanh pho (TAM): xet 15 do thi dong dan nhat moi bang theo thu tu dan so, bo do thi
cach mot do thi da chon duoi 40 km (thuong la vung ven cua cung mot thanh pho), lay toi da 5.
Trong so thoi tiet = dan so do thi / tong dan so cac do thi da chon cua bang.
"""
import datetime as dt
import glob
import re
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
REF = ROOT / "data" / "reference"
MAX_CITIES, MIN_KM, POOL = 5, 40, 15


def latest(source, pattern):
    return sorted(glob.glob(str(RAW / source / "*" / pattern)))[-1]


def km(lat1, lon1, lat2, lon2):
    p = np.pi / 180
    a = np.sin((lat2 - lat1) * p / 2) ** 2 + np.cos(lat1 * p) * np.cos(lat2 * p) * np.sin((lon2 - lon1) * p / 2) ** 2
    return 12742 * np.arcsin(np.sqrt(a))


# ---------- cities.csv ----------
names = pd.read_csv(latest("population", "state_pop_2020_delphi.csv"))
name2id = dict(zip(names.state_name, names.state_id))

x = pd.read_excel(latest("census_popest_places", "SUB-IP-EST*.xlsx"), header=None, skiprows=4)
x = x[x[0].astype(str).str.contains(", ")].iloc[:, [0, 7]]
x.columns = ["area", "population"]
x[["name", "state_name"]] = x.area.str.rsplit(", ", n=1, expand=True)
x["state"] = x.state_name.map(name2id)
x = x.dropna(subset=["state", "population"])

z = zipfile.ZipFile(latest("census_gazetteer", "2024_Gaz_place_national.zip"))
g = pd.read_csv(z.open(z.namelist()[0]), sep="\t", dtype={"GEOID": str})
g.columns = [c.strip() for c in g.columns]
g["state"] = g.USPS.str.lower()
g = g[["state", "NAME", "INTPTLAT", "INTPTLONG", "ALAND_SQMI"]].rename(columns={"NAME": "name", "INTPTLAT": "lat", "INTPTLONG": "lon"})

m = x.merge(g, on=["state", "name"], how="left")
unmatched = m[m.lat.isna()].sort_values("population", ascending=False)
rows = []
for s, grp in m.dropna(subset=["lat"]).sort_values("population", ascending=False).groupby("state", sort=True):
    chosen = []
    for _, r in grp.head(POOL).iterrows():
        if all(km(r.lat, r.lon, c.lat, c.lon) >= MIN_KM for c in chosen):
            chosen.append(r)
        if len(chosen) == MAX_CITIES:
            break
    tot = sum(c.population for c in chosen)
    for c in chosen:
        city = re.sub(r"\s+(city and borough|city|town|village|CDP|borough|municipality|metro government|"
                      r"metropolitan government|consolidated government|unified government|urban county)( .*)?$", "", c["name"])
        rows.append({"state": s, "city": city, "census_name": c["name"], "lat": round(c.lat, 4), "lon": round(c.lon, 4),
                     "population": int(c.population), "weight": round(c.population / tot, 4),
                     "large_area": int(c.ALAND_SQMI > 500)})  # diem trung tam cua do thi rat rong co the xa khu dan cu
cities = pd.DataFrame(rows)
cities.to_csv(REF / "cities.csv", index=False)
per = cities.groupby("state").size()
print(f"cities.csv: {len(cities)} do thi, {cities.state.nunique()} bang; so do thi moi bang: {per.value_counts().sort_index().to_dict()}")
print("top-15 khong khop toa do:", unmatched.groupby("state").head(1).head(10)[["state", "name", "population"]].to_dict("records"))
old = pd.read_csv(REF / "cities_largest_per_state.csv")
top1 = cities.sort_values("population", ascending=False).groupby("state").head(1).merge(old, on="state", suffixes=("", "_old"))
top1["km_from_old"] = km(top1.lat, top1.lon, top1.lat_old, top1.lon_old).round(1)
print("lech toa do nhap tay so voi Gazetteer (km): median", top1.km_from_old.median(), "max",
      top1.loc[top1.km_from_old.idxmax(), ["state", "city", "km_from_old"]].to_dict())


# ---------- holidays.csv ----------
def mmwr(saturday):
    """Nam va tuan MMWR cua tuan ket thuc vao thu Bay nay (tuan thuoc nam chua ngay thu Tu)."""
    wed = saturday - dt.timedelta(days=3)
    return wed.year, (wed.timetuple().tm_yday - 1) // 7 + 1


def thanksgiving(y):
    d = dt.date(y, 11, 1)
    return d + dt.timedelta(days=(3 - d.weekday()) % 7 + 21)


hol = {}
for y in range(2009, 2030):
    hol[thanksgiving(y)] = "Thanksgiving"
    hol[dt.date(y, 12, 25)] = "Christmas"
    hol[dt.date(y, 1, 1)] = "New Year"
weeks = []
d = dt.date(2010, 1, 2)  # thu Bay dau tien cua 2010
while d <= dt.date(2028, 12, 30):
    days = [d - dt.timedelta(days=i) for i in range(7)]
    names_w = sorted({hol[x] for x in days if x in hol})
    winter = any((x.month == 12 and x.day >= 18) or (x.month == 1 and x.day <= 1) for x in days)  # TAM: 2 tuan cuoi thang 12
    y, w = mmwr(d)
    weeks.append({"week": d, "mmwr_year": y, "mmwr_week": w,
                  "season": f"{y}-{str(y + 1)[2:]}" if w >= 40 else f"{y - 1}-{str(y)[2:]}",
                  "holiday_week": int(bool(names_w)), "holiday_name": "; ".join(names_w), "winter_break": int(winter)})
    d += dt.timedelta(days=7)
h = pd.DataFrame(weeks)
nxt = h.week.where(h.holiday_week == 1).bfill()
h["weeks_to_holiday"] = ((pd.to_datetime(nxt) - pd.to_datetime(h.week)).dt.days // 7).astype("Int64")
h.to_csv(REF / "holidays.csv", index=False)
print(f"holidays.csv: {len(h)} tuan, {int(h.holiday_week.sum())} tuan co le")

# Kiem tra tuan MMWR voi bang da ghep (Delphi tra ve san so tuan MMWR)
f = pd.read_csv(ROOT / "data" / "samples" / "state_week_sample.csv.gz", usecols=["week", "mmwr_year", "mmwr_week"]).drop_duplicates()
f["week"] = pd.to_datetime(f.week).dt.date
c = f.merge(h, on="week", suffixes=("", "_mine"))
print("khop tuan MMWR voi bang mau:", round(float(((c.mmwr_year == c.mmwr_year_mine) & (c.mmwr_week == c.mmwr_week_mine)).mean() * 100), 2), "% tren", len(c), "tuan")
