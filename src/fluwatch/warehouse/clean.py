"""Dung vung data/clean/: moi nguon mot bang Parquet da chuan hoa.

Chuan chung moi bang: state (ma 2 chu viet thuong, chi 50 bang + DC), week (thu Bay ket thuc tuan MMWR),
epiweek (YYYYWW), season ('2024-25', bat dau tuan MMWR 40), season_week (1 = tuan 40); bang theo mua chi co season.
Moi bien doi (bo dong, dat thieu, bo trung) ghi vao data/clean/_clean_log.json.

Chay: python pipelines/02_warehouse.py --steps clean
"""
import datetime as dt
import logging
import time

from .clean_cdc import clean_vaccine, clean_wval
from .clean_delphi import DELPHI_TABLES, clean_delphi
from .clean_environment import clean_epa, clean_weather
from .common import CleanLog

log = logging.getLogger("fluwatch.warehouse")

# bang -> (ham dung, khoa chinh)
TABLES = {
    **{t: ((lambda p, c, t=t: clean_delphi(p, t, c)), ["state", "week"]) for t in DELPHI_TABLES},
    "wval": (clean_wval, ["state", "week"]),
    "vaccine": (clean_vaccine, ["state", "season"]),
    "weather": (clean_weather, ["state", "week"]),
    "epa_pm25": (clean_epa, ["state", "week"]),
}


def build_clean(paths, only=None):
    """Dung cac bang clean/; tra ve {ten bang: DataFrame}. `only`: danh sach ten bang can dung lai."""
    out_dir = paths.data / "clean"
    out_dir.mkdir(parents=True, exist_ok=True)
    clog = CleanLog()
    result = {}
    for name, (fn, keys) in TABLES.items():
        if only and name not in only:
            continue
        t0 = time.time()
        df = fn(paths, clog)
        dup = df.duplicated(keys).sum()
        if dup:
            raise ValueError(f"clean/{name}: {dup} dong trung khoa {keys}")
        clog.summary(name, df, keys)
        clog.table(name)["built_at"] = dt.datetime.now().isoformat(timespec="seconds")
        df.to_parquet(out_dir / f"{name}.parquet", index=False)
        result[name] = df
        log.info("clean/%s.parquet: %d dong, %.1fs", name, len(df), time.time() - t0)
    log_path = out_dir / "_clean_log.json"
    if only and log_path.exists():                     # dung lai mot phan: giu nhat ky cac bang khac
        import json
        old = json.loads(log_path.read_text(encoding="utf-8"))
        old.update(clog.tables)
        clog.tables = old
    clog.write(log_path)
    return result
