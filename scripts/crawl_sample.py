"""Crawl cac bo du lieu cong khai cho project cum mua, luu nguyen trang vao data/raw.

Cach chay (tu thu muc project):
    python scripts/crawl_sample.py delphi     # Delphi V5, khoang 8 phut vi gioi han toc do
    python scripts/crawl_sample.py weather    # Open-Meteo thoi tiet va PM2.5, moi bang 1 diem
    python scripts/crawl_sample.py files      # File tinh: EPA AirData, dan so, trang FluVaxView

Moi file tai ve duoc ghi vao data/raw/manifest.jsonl (nguon, url, thoi diem, kich thuoc,
sha256, ma HTTP) de truy nguoc duoc nguon goc. Logic nam trong src/fluwatch/ingest/.
"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fluwatch.ingest import delphi as delphi_source  # noqa: E402
from fluwatch.ingest import openmeteo  # noqa: E402
from fluwatch.ingest.net import fetch  # noqa: E402,F401  (giu ten cu cho script khac import)
from fluwatch.ingest.paths import Paths  # noqa: E402
from fluwatch.ingest.store import RawStore  # noqa: E402

PATHS = Paths(ROOT)
RAW, REF = PATHS.raw, PATHS.reference
STORE = RawStore(PATHS)
TODAY = STORE.day
save = STORE.save


def delphi():
    RAW.mkdir(parents=True, exist_ok=True)
    delphi_source.crawl(STORE)


def weather():
    openmeteo.crawl_largest_cities(STORE, openmeteo.load_cities(REF / "cities_largest_per_state.csv"))


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
