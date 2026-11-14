"""Tai thoi tiet va PM2.5 Open-Meteo cho cac thanh pho trong data/reference/cities.csv.

Cach chay (tu thu muc project):
    python scripts/crawl_cities_weather.py            # tai lich su day du cho thanh pho chua co file
    python scripts/crawl_cities_weather.py --update   # cap nhat hang tuan: chi tai doan gan day

Che do --update tai 35 ngay gan nhat cho ca 236 thanh pho, gom 50 thanh pho mot lan goi, luu thanh
<bang>__<thanh_pho>__recent.json trong thu muc ngay tai. build_environment.py ghep moi file cua mot thanh pho
theo ngay, ngay trung thi lay ban tai sau cung (Open-Meteo sua so lieu vai ngay gan nhat).

Che do mac dinh chay lai duoc nhieu lan: file da tai (o bat ky ngay nao) thi bo qua. Neu Open-Meteo bao het luot
trong ngay (HTTP 429 lap lai), script dung lai voi ma 2; chay lai vao hom sau de tai not phan con thieu.
Thanh pho lon nhat cua moi bang dung lai file da tai o crawl_sample.py neu cach toa do cu duoi 15 km.
Logic nam trong src/fluwatch/ingest/openmeteo.py.
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fluwatch.ingest import openmeteo  # noqa: E402
from fluwatch.ingest.net import QuotaExceeded  # noqa: E402
from fluwatch.ingest.paths import Paths  # noqa: E402
from fluwatch.ingest.store import RawStore  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--update", action="store_true", help=f"chi tai {openmeteo.RECENT_DAYS} ngay gan nhat cho moi thanh pho")
args = ap.parse_args()

paths = Paths(ROOT)
store = RawStore(paths)
cities = openmeteo.load_cities(paths.reference / "cities.csv")
try:
    if args.update:  # loi le te van chay tiep (bang dung tam so lieu cu); loi tren 10% thi bao that bai
        sys.exit(1 if openmeteo.update_cities(store, cities) > 0.1 * 2 * len(cities) else 0)
    largest = openmeteo.load_cities(paths.reference / "cities_largest_per_state.csv")
    done, skipped = openmeteo.crawl_city_history(store, cities, largest)
    print(f"Xong: tai moi {done} file, dung lai {skipped} thanh pho da co.")
except QuotaExceeded:
    print("Open-Meteo van tra 429: co the da het luot trong ngay. Dung lai, hay chay lai vao ngay mai.")
    sys.exit(2)
