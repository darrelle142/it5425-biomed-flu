# Truy van OLAP mau tren kho du lieu

Sinh tu dong boi `python pipelines/02_warehouse.py --steps olap` luc 2026-11-16 23:07, tren `data/business/fluwatch.duckdb`. Do do ty le khi roll-up duoc gop co trong so (xem docstring `src/fluwatch/warehouse/olap.py`).

## 1. Roll-up: Bang -> toan quoc, tuan -> mua: dinh nhap vien toan quoc moi mua (chi cac mua co NHSN)

```sql
SELECT season, round(max(rate_flu), 2) AS rate_peak_per100k,
arg_max(week, rate_flu) AS peak_week, sum(hosp_flu)::BIGINT AS hosp_total
FROM v_nation_week WHERE season >= '2022-23' AND states_hosp >= 45
GROUP BY season ORDER BY season
```

| season | rate_peak_per100k | peak_week | hosp_total |
| --- | --- | --- | --- |
| 2022-23 | 8.11 | 2022-12-03 | 228725 |
| 2023-24 | 6.55 | 2023-12-30 | 247152 |
| 2024-25 | 16.78 | 2025-02-08 | 551438 |
| 2025-26 | 12.78 | 2026-01-03 | 336899 |
| 2026-27 | 2.84 | 2026-11-07 | 32766 |

## 2. Roll-up: Bang -> vung HHS: ILI ca mua theo vung, mua 2024-25 (co trong so luot kham)

```sql
SELECT hhs_region, round(sum(num_ili) / sum(num_patients) * 100, 2) AS ili_season_pct,
round(max(ili_pct), 2) AS ili_state_max, count(DISTINCT state) AS states
FROM v_flu_week WHERE season = '2024-25' AND in_flu_season
GROUP BY hhs_region ORDER BY hhs_region
```

| hhs_region | ili_season_pct | ili_state_max | states |
| --- | --- | --- | --- |
| 1 | 3.63 | 11.8 | 6 |
| 2 | 5.5 | 10.53 | 2 |
| 3 | 3.58 | 11.12 | 6 |
| 4 | 3.8 | 17.01 | 8 |
| 5 | 3.24 | 13.51 | 6 |
| 6 | 4.21 | 13.66 | 5 |
| 7 | 2.88 | 9.6 | 4 |
| 8 | 2.89 | 7.46 | 6 |
| 9 | 4.11 | 9.25 | 4 |
| 10 | 3.58 | 11.66 | 4 |

## 3. Drill-down: Toan quoc -> vung 4 -> tung bang vung 4: dinh nhap vien mua 2024-25

```sql
SELECT cap, hhs_region, state, rate_peak FROM (
SELECT 1 AS lvl, 'toan quoc' AS cap, NULL AS hhs_region, NULL AS state, round(max(rate_flu), 2) AS rate_peak
FROM v_nation_week WHERE season = '2024-25'
UNION ALL
SELECT 2, 'vung', hhs_region, NULL, round(max(rate_flu), 2) FROM v_region_week
WHERE season = '2024-25' AND hhs_region = 4 GROUP BY hhs_region
UNION ALL
SELECT 3, 'bang', hhs_region, state, round(max(rate_flu), 2) FROM v_flu_week
WHERE season = '2024-25' AND hhs_region = 4 GROUP BY hhs_region, state)
ORDER BY lvl, rate_peak DESC
```

| cap | hhs_region | state | rate_peak |
| --- | --- | --- | --- |
| toan quoc |  |  | 16.78 |
| vung | 4 |  | 17.17 |
| bang | 4 | ky | 26.68 |
| bang | 4 | sc | 24.1 |
| bang | 4 | nc | 21.24 |
| bang | 4 | ms | 20.12 |
| bang | 4 | fl | 16.79 |
| bang | 4 | tn | 15.01 |
| bang | 4 | al | 14.4 |
| bang | 4 | ga | 12.51 |

## 4. Drill-down: Bang -> tung tuan: Georgia quanh dinh mua 2024-25

```sql
SELECT week, season_week, round(rate_flu, 2) AS rate_flu, cdc_level_name, round(ili_pct, 2) AS ili_pct,
round(wow_pct, 1) AS wow_pct
FROM v_flu_week WHERE state = 'ga' AND season = '2024-25' AND season_week BETWEEN 12 AND 20
ORDER BY week
```

| week | season_week | rate_flu | cdc_level_name | ili_pct | wow_pct |
| --- | --- | --- | --- | --- | --- |
| 2024-12-21 | 12 | 3.62 | trung_binh | 6.05 | 84.7 |
| 2024-12-28 | 13 | 7.29 | trung_binh | 8.57 | 101.4 |
| 2025-01-04 | 14 | 10.43 | cao | 7.8 | 43.1 |
| 2025-01-11 | 15 | 7.5 | trung_binh | 6.49 | -28.1 |
| 2025-01-18 | 16 | 9.04 | cao | 7.47 | 20.5 |
| 2025-01-25 | 17 | 10.89 | cao | 8.78 | 20.5 |
| 2025-02-01 | 18 | 12.51 | cao | 8.43 | 14.9 |
| 2025-02-08 | 19 | 11.86 | cao | 8.19 | -5.2 |
| 2025-02-15 | 20 | 6.78 | trung_binh | 6.02 | -42.8 |

## 5. Slice: Cat mot lat theo thoi gian: tuan moi nhat, 10 bang co ty le nhap vien cao nhat

```sql
SELECT state, state_name, round(rate_flu, 2) AS rate_flu, cdc_level_name, round(wow_pct, 1) AS wow_pct,
is_preliminary
FROM v_flu_week WHERE week = (SELECT max(week) FROM fact_flu_week) AND rate_flu IS NOT NULL
ORDER BY rate_flu DESC LIMIT 10
```

| state | state_name | rate_flu | cdc_level_name | wow_pct | is_preliminary |
| --- | --- | --- | --- | --- | --- |
| la | Louisiana | 6.67 | trung_binh | 23.5 | True |
| fl | Florida | 5.68 | trung_binh | 0.5 | True |
| hi | Hawaii | 4.8 | trung_binh | 24.0 | True |
| nj | New Jersey | 4.09 | thap | 48.2 | True |
| pa | Pennsylvania | 4.05 | thap | -8.8 | True |
| sc | South Carolina | 3.94 | trung_binh | 40.2 | True |
| tn | Tennessee | 3.64 | trung_binh | 33.8 | True |
| tx | Texas | 3.6 | thap | 25.0 | True |
| ms | Mississippi | 3.48 | trung_binh | 15.6 | True |
| al | Alabama | 3.41 | trung_binh | 8.6 | True |

## 6. Dice: Loc nhieu chieu: vung 4, mua 2022-23 -> 2025-26, tuan 40 -> 20; so tuan o muc Cao tro len

```sql
SELECT season, count(*) FILTER (WHERE cdc_level >= 3) AS state_weeks_high,
count(rate_flu) AS state_weeks_reported,
round(100.0 * count(*) FILTER (WHERE cdc_level >= 3) / count(rate_flu), 1) AS pct_high
FROM v_flu_week WHERE hhs_region = 4 AND season BETWEEN '2022-23' AND '2025-26' AND in_flu_season
GROUP BY season ORDER BY season
```

| season | state_weeks_high | state_weeks_reported | pct_high |
| --- | --- | --- | --- |
| 2022-23 | 11 | 264 | 4.2 |
| 2023-24 | 6 | 264 | 2.3 |
| 2024-25 | 66 | 264 | 25.0 |
| 2025-26 | 26 | 272 | 9.6 |

## 7. Pivot: Xoay bang: vung HHS (dong) x mua (cot), gia tri = dinh ty le nhap vien cua vung

```sql
PIVOT (SELECT hhs_region, season, round(max(rate_flu), 1) AS peak FROM v_region_week
WHERE season BETWEEN '2022-23' AND '2025-26' GROUP BY ALL)
ON season USING first(peak) GROUP BY hhs_region ORDER BY hhs_region
```

| hhs_region | 2022-23 | 2023-24 | 2024-25 | 2025-26 |
| --- | --- | --- | --- | --- |
| 1 | 9.9 | 6.5 | 19.7 | 19.3 |
| 2 | 8.2 | 7.3 | 17.4 | 19.6 |
| 3 | 8.6 | 7.3 | 25.1 | 18.9 |
| 4 | 6.5 | 8.3 | 17.2 | 14.0 |
| 5 | 8.1 | 5.4 | 20.8 | 15.2 |
| 6 | 9.8 | 7.0 | 16.8 | 10.3 |
| 7 | 10.3 | 5.7 | 19.5 | 13.2 |
| 8 | 5.9 | 5.9 | 11.6 | 12.7 |
| 9 | 8.7 | 6.1 | 14.4 | 5.3 |
| 10 | 12.2 | 3.6 | 10.4 | 7.1 |

## 8. Pivot: Xoay heatmap bang x tuan thanh mua x tuan trong mua: ILI toan quoc (tuan trong mua 1, 5, ..., 33)

```sql
PIVOT (SELECT season, season_week, round(ili_pct, 2) AS ili FROM v_nation_week
WHERE season BETWEEN '2016-17' AND '2025-26')
ON season_week IN (1, 5, 9, 13, 17, 21, 25, 29, 33) USING first(ili) GROUP BY season ORDER BY season
```

| season | 1 | 5 | 9 | 13 | 17 | 21 | 25 | 29 | 33 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2016-17 | 1.25 | 1.56 | 1.85 | 3.54 | 3.54 | 4.62 | 3.17 | 1.64 | 1.34 |
| 2017-18 | 1.29 | 1.7 | 2.25 | 5.51 | 7.02 | 5.21 | 2.49 | 1.59 | 1.22 |
| 2018-19 | 1.41 | 1.84 | 2.25 | 4.2 | 3.89 | 5.31 | 3.51 | 1.96 | 1.49 |
| 2019-20 | 1.49 | 2.0 | 3.44 | 7.15 | 6.01 | 5.61 | 7.36 | 2.57 | 1.23 |
| 2020-21 | 1.02 | 1.13 | 1.45 | 1.38 | 1.1 | 0.78 | 0.81 | 0.89 | 1.05 |
| 2021-22 | 1.96 | 2.07 | 2.55 | 5.06 | 1.97 | 1.36 | 1.72 | 2.16 | 2.59 |
| 2022-23 | 2.59 | 5.55 | 7.24 | 5.47 | 2.67 | 2.59 | 2.41 | 1.95 | 1.96 |
| 2023-24 | 2.25 | 2.91 | 3.96 | 6.91 | 4.23 | 4.33 | 3.15 | 2.29 | 2.03 |
| 2024-25 | 1.85 | 2.23 | 3.12 | 6.67 | 6.86 | 6.02 | 3.31 | 2.21 | 1.79 |
| 2025-26 | 1.47 | 1.71 | 2.68 | 8.02 | 4.43 | 4.34 | 2.81 | 1.8 | 1.62 |
