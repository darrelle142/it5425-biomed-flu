"""File DuckDB data/business/fluwatch.duckdb va cac truy van OLAP mau (roll-up, drill-down, slice, dice, pivot).

Bang trong DuckDB la ban sao cac file Parquet cua business/ (file .duckdb tu chua du lieu, mang di may khac van chay).
View:
    v_flu_week       fact_flu_week + dim_state + dim_time (bang phang de loc theo moi chieu)
    v_region_week    roll-up bang -> vung HHS theo tuan
    v_nation_week    roll-up bang -> toan quoc theo tuan
    v_state_season   roll-up tuan -> mua theo bang

Quy tac roll-up (do do khong cong duoc): khong lay trung binh cong cac ty le.
    rate_flu   = sum(hosp_flu) / sum(population cac bang co so) * 100000
    ili_pct    = sum(num_ili) / sum(num_patients) * 100   (ILI co trong so theo luot kham)
    con lai (ed_pct_flu, abs_humidity...) = trung binh co trong so dan so

Chay: python pipelines/02_warehouse.py --steps olap   (ghi ket qua mau vao reports/olap/README.md)
"""
import datetime as dt
import logging

import duckdb
import pandas as pd

log = logging.getLogger("fluwatch.warehouse")

TABLES = ["dim_state", "dim_time", "dim_source", "fact_flu_week", "fact_season_summary"]

VIEWS = """
CREATE OR REPLACE VIEW v_flu_week AS
SELECT f.*, s.state_name, s.hhs_region, s.hhs_region_name, s.country, s.population, s.contiguous, s.cluster_id,
       t.year, t.month, t.in_flu_season, t.holiday_name
FROM fact_flu_week f
JOIN dim_state s USING (state)
JOIN dim_time  t USING (week);

CREATE OR REPLACE VIEW v_region_week AS
SELECT hhs_region, week, any_value(season) AS season, any_value(season_week) AS season_week,
       sum(hosp_flu) AS hosp_flu,
       sum(hosp_flu) / nullif(sum(CASE WHEN hosp_flu IS NOT NULL THEN population END), 0) * 1e5 AS rate_flu,
       sum(num_ili) / nullif(sum(num_patients), 0) * 100 AS ili_pct,
       sum(ed_pct_flu * population) / nullif(sum(CASE WHEN ed_pct_flu IS NOT NULL THEN population END), 0) AS ed_pct_flu,
       sum(abs_humidity * population) / nullif(sum(CASE WHEN abs_humidity IS NOT NULL THEN population END), 0) AS abs_humidity,
       count(hosp_flu) AS states_hosp, count(ili_pct) AS states_ili, bool_or(is_preliminary) AS is_preliminary
FROM v_flu_week GROUP BY hhs_region, week;

CREATE OR REPLACE VIEW v_nation_week AS
SELECT week, any_value(season) AS season, any_value(season_week) AS season_week,
       sum(hosp_flu) AS hosp_flu,
       sum(hosp_flu) / nullif(sum(CASE WHEN hosp_flu IS NOT NULL THEN population END), 0) * 1e5 AS rate_flu,
       sum(num_ili) / nullif(sum(num_patients), 0) * 100 AS ili_pct,
       sum(ed_pct_flu * population) / nullif(sum(CASE WHEN ed_pct_flu IS NOT NULL THEN population END), 0) AS ed_pct_flu,
       count(hosp_flu) AS states_hosp, count(ili_pct) AS states_ili, bool_or(is_preliminary) AS is_preliminary
FROM v_flu_week GROUP BY week;

CREATE OR REPLACE VIEW v_state_season AS
SELECT state, hhs_region, season,
       sum(hosp_flu) AS hosp_total, max(rate_flu) AS rate_peak, sum(rate_flu) AS rate_cum,
       sum(num_ili) / nullif(sum(num_patients), 0) * 100 AS ili_season_pct, max(ili_pct) AS ili_peak,
       arg_max(season_week, rate_flu) AS season_week_peak_rate
FROM v_flu_week WHERE in_flu_season GROUP BY state, hhs_region, season;
"""

# (phep OLAP, cau hoi, SQL)
EXAMPLES = [
    ("Roll-up", "Bang -> toan quoc, tuan -> mua: dinh nhap vien toan quoc moi mua (chi cac mua co NHSN)",
     """SELECT season, round(max(rate_flu), 2) AS rate_peak_per100k,
               arg_max(week, rate_flu) AS peak_week, sum(hosp_flu)::BIGINT AS hosp_total
        FROM v_nation_week WHERE season >= '2022-23' AND states_hosp >= 45
        GROUP BY season ORDER BY season"""),
    ("Roll-up", "Bang -> vung HHS: ILI ca mua theo vung, mua 2024-25 (co trong so luot kham)",
     """SELECT hhs_region, round(sum(num_ili) / sum(num_patients) * 100, 2) AS ili_season_pct,
               round(max(ili_pct), 2) AS ili_state_max, count(DISTINCT state) AS states
        FROM v_flu_week WHERE season = '2024-25' AND in_flu_season
        GROUP BY hhs_region ORDER BY hhs_region"""),
    ("Drill-down", "Toan quoc -> vung 4 -> tung bang vung 4: dinh nhap vien mua 2024-25",
     """SELECT cap, hhs_region, state, rate_peak FROM (
            SELECT 1 AS lvl, 'toan quoc' AS cap, NULL AS hhs_region, NULL AS state, round(max(rate_flu), 2) AS rate_peak
            FROM v_nation_week WHERE season = '2024-25'
            UNION ALL
            SELECT 2, 'vung', hhs_region, NULL, round(max(rate_flu), 2) FROM v_region_week
            WHERE season = '2024-25' AND hhs_region = 4 GROUP BY hhs_region
            UNION ALL
            SELECT 3, 'bang', hhs_region, state, round(max(rate_flu), 2) FROM v_flu_week
            WHERE season = '2024-25' AND hhs_region = 4 GROUP BY hhs_region, state)
        ORDER BY lvl, rate_peak DESC"""),
    ("Drill-down", "Bang -> tung tuan: Georgia quanh dinh mua 2024-25",
     """SELECT week, season_week, round(rate_flu, 2) AS rate_flu, cdc_level_name, round(ili_pct, 2) AS ili_pct,
               round(wow_pct, 1) AS wow_pct
        FROM v_flu_week WHERE state = 'ga' AND season = '2024-25' AND season_week BETWEEN 12 AND 20
        ORDER BY week"""),
    ("Slice", "Cat mot lat theo thoi gian: tuan moi nhat, 10 bang co ty le nhap vien cao nhat",
     """SELECT state, state_name, round(rate_flu, 2) AS rate_flu, cdc_level_name, round(wow_pct, 1) AS wow_pct,
               is_preliminary
        FROM v_flu_week WHERE week = (SELECT max(week) FROM fact_flu_week) AND rate_flu IS NOT NULL
        ORDER BY rate_flu DESC LIMIT 10"""),
    ("Dice", "Loc nhieu chieu: vung 4, mua 2022-23 -> 2025-26, tuan 40 -> 20; so tuan o muc Cao tro len",
     """SELECT season, count(*) FILTER (WHERE cdc_level >= 3) AS state_weeks_high,
               count(rate_flu) AS state_weeks_reported,
               round(100.0 * count(*) FILTER (WHERE cdc_level >= 3) / count(rate_flu), 1) AS pct_high
        FROM v_flu_week WHERE hhs_region = 4 AND season BETWEEN '2022-23' AND '2025-26' AND in_flu_season
        GROUP BY season ORDER BY season"""),
    ("Pivot", "Xoay bang: vung HHS (dong) x mua (cot), gia tri = dinh ty le nhap vien cua vung",
     """PIVOT (SELECT hhs_region, season, round(max(rate_flu), 1) AS peak FROM v_region_week
               WHERE season BETWEEN '2022-23' AND '2025-26' GROUP BY ALL)
        ON season USING first(peak) GROUP BY hhs_region ORDER BY hhs_region"""),
    ("Pivot", "Xoay heatmap bang x tuan thanh mua x tuan trong mua: ILI toan quoc (tuan trong mua 1, 5, ..., 33)",
     """PIVOT (SELECT season, season_week, round(ili_pct, 2) AS ili FROM v_nation_week
               WHERE season BETWEEN '2016-17' AND '2025-26')
        ON season_week IN (1, 5, 9, 13, 17, 21, 25, 29, 33) USING first(ili) GROUP BY season ORDER BY season"""),
]


def build_duckdb(paths):
    biz = paths.data / "business"
    db = biz / "fluwatch.duckdb"
    tmp = biz / "fluwatch.duckdb.tmp"
    tmp.unlink(missing_ok=True)
    con = duckdb.connect(str(tmp))
    for t in TABLES:
        p = (biz / f"{t}.parquet").as_posix()
        con.execute(f"CREATE TABLE {t} AS SELECT * FROM read_parquet('{p}')")
    con.execute("ALTER TABLE dim_state ADD PRIMARY KEY (state)")
    con.execute("ALTER TABLE dim_time ADD PRIMARY KEY (week)")
    con.execute("ALTER TABLE dim_source ADD PRIMARY KEY (source_id)")
    con.execute("ALTER TABLE fact_flu_week ADD PRIMARY KEY (state, week)")
    con.execute("ALTER TABLE fact_season_summary ADD PRIMARY KEY (state, season)")
    con.execute(VIEWS)
    con.close()
    db.unlink(missing_ok=True)
    tmp.rename(db)
    log.info("business/fluwatch.duckdb: %d bang, 4 view", len(TABLES))
    return db


def _md(df):
    def fmt(v):
        if v is None or (not isinstance(v, str) and pd.isna(v)):
            return ""
        if isinstance(v, pd.Timestamp):
            return str(v.date())
        return str(v)
    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join(" --- " for _ in cols) + "|"]
    lines += ["| " + " | ".join(fmt(v) for v in r) + " |" for r in df.itertuples(index=False)]
    return "\n".join(lines)


def run_examples(paths, out_md=None):
    db = paths.data / "business" / "fluwatch.duckdb"
    con = duckdb.connect(str(db), read_only=True)
    parts = ["# Truy van OLAP mau tren kho du lieu", "",
             f"Sinh tu dong boi `python pipelines/02_warehouse.py --steps olap` luc "
             f"{dt.datetime.now():%Y-%m-%d %H:%M}, tren `data/business/fluwatch.duckdb`. "
             "Do do ty le khi roll-up duoc gop co trong so (xem docstring `src/fluwatch/warehouse/olap.py`).", ""]
    results = {}
    for i, (op, q, sql) in enumerate(EXAMPLES, 1):
        df = con.execute(sql).df()
        results[f"{i}. {op}"] = df
        parts += [f"## {i}. {op}: {q}", "", "```sql", "\n".join(s.strip() for s in sql.strip().splitlines()), "```", "",
                  _md(df), ""]
    con.close()
    if out_md:
        out_md.parent.mkdir(parents=True, exist_ok=True)
        out_md.write_text("\n".join(parts), encoding="utf-8")
    return results
