# Kiểm tra bộ kiểm tra chất lượng trên dữ liệu chèn lỗi

Sinh tự động bởi `python pipelines/02_warehouse.py --steps inject` lúc 2026-11-24 08:17. Code: `src/fluwatch/warehouse/inject.py` (chèn lỗi, chấm điểm), `quality.py` (các quy tắc).

**Cách chấm.** Chạy toàn bộ quy tắc trên dữ liệu gốc (baseline: 13 vi phạm có sẵn, là vấn đề thật của dữ liệu, xem `README.md`) và trên dữ liệu bị chèn lỗi. Chỉ tính vi phạm **mới**. Một lỗi trong đáp án là *bị bắt* khi có vi phạm mới trỏ đúng ô (bang, tuần, cột); lỗi cả dòng (dòng bị xóa, dòng trùng) cần vi phạm mới ở đúng (bang, tuần). Vi phạm mới không khớp đáp án nào là *báo động giả*.

## Tổng hợp

| Bộ dữ liệu | Số lỗi chèn | Bắt được | Recall | Bắt chỉ bằng quy tắc nội bộ (không cần M01–M03) | Vi phạm mới | Báo động giả |
| --- | --- | --- | --- | --- | --- | --- |
| TV4 (`data/sandbox/corrupted/fact_flu_week.parquet`) | 285 | 233 | **81.8%** | 233 (81.8%) | 727 | 0 |
| tự sinh, seed 2026, chế độ `raw` | 510 | 417 | **81.8%** | 417 (81.8%) | 987 | 0 |
| tự sinh, seed 2026, chế độ `consistent` | 510 | 155 | **30.4%** | 155 (30.4%) | 464 | 0 |

Chế độ `raw`: chỉ sửa ô dữ liệu, cột phái sinh giữ như cũ (lỗi xảy ra sau khi dựng bảng). Chế độ `consistent`: kẻ sửa tính lại mọi cột phái sinh cho khớp (biến trễ, `wow_pct`, `missing_*`, `cdc_level`), nên quy tắc nội bộ khó thấy hơn; lớp đối chiếu nguồn (M01–M03) vẫn phải bắt được.

**Độ ổn định qua các seed khác** (mỗi seed chèn lỗi ở vị trí khác):

| Seed | Chế độ | Lỗi chèn | Bắt được | Báo động giả | Quy tắc báo giả |
| --- | --- | --- | --- | --- | --- |
| 1 | `raw` | 504 | 422 (83.7%) | 6 | R09 |
| 1 | `consistent` | 504 | 143 (28.4%) | 6 | R09 |
| 2 | `raw` | 513 | 423 (82.5%) | 0 | – |
| 2 | `consistent` | 513 | 151 (29.4%) | 0 | – |
| 3 | `raw` | 511 | 427 (83.6%) | 0 | – |
| 3 | `consistent` | 511 | 159 (31.1%) | 0 | – |

Báo động giả đến từ R09; R09 là quy tắc mức *cảnh báo* suy dân số từ trung vị theo bang × mùa: khi một khối tuần bị xóa, trung vị dịch nhẹ và một tuần vốn sát ngưỡng 5% bị gắn cờ.


Không quy tắc mức *lỗi* nào báo giả.

## TV4 (`data/sandbox/corrupted/fact_flu_week.parquet`)

Bảng lỗi: 44952 dòng.

| Loại lỗi | Ô/dòng chèn | Bắt được | Recall | Quy tắc bắt (số lỗi) |
| --- | --- | --- | --- | --- |
| Mất khối nhiều tuần liên tiếp (mất dòng hoặc mất cả đoạn một tín hiệu) (`missing_block`) | 19 | 19 | 100.0% | R05 (14), R06 (14), R07 (6), R02 (5) |
| Thiếu ngẫu nhiên (ô bị xóa rải rác) (`missing_random`) | 200 | 148 | 74.0% | R06 (148), R05 (136), R07 (90) |
| Số sơ bộ (4 tuần cuối) bị sửa ±10–50% (`preliminary_revised`) | 40 | 40 | 100.0% | R09 (40), R06 (29), R07 (23) |
| Trùng dòng (`duplicate`) | 26 | 26 | 100.0% | R01 (26) |

Lỗi **không** bắt được:

| error_id | error_type | state | week | column |
| --- | --- | --- | --- | --- |
| 22 | missing_random | ca | 2021-04-10 | num_ili |
| 23 | missing_random | wy | 2017-08-05 | num_ili |
| 28 | missing_random | mi | 2024-12-14 | num_ili |
| 30 | missing_random | wv | 2021-09-11 | num_ili |
| 33 | missing_random | co | 2016-03-19 | num_ili |
| 36 | missing_random | hi | 2023-12-23 | num_ili |
| 38 | missing_random | az | 2016-01-30 | num_ili |
| 40 | missing_random | dc | 2024-08-24 | num_ili |
| 43 | missing_random | wa | 2011-09-24 | num_ili |
| 45 | missing_random | me | 2025-05-10 | num_ili |
| 50 | missing_random | dc | 2019-10-12 | num_ili |
| 52 | missing_random | tn | 2021-08-07 | num_ili |
| 56 | missing_random | ks | 2014-02-22 | num_ili |
| 59 | missing_random | pa | 2025-04-19 | num_ili |
| 61 | missing_random | tx | 2019-07-27 | num_ili |
| 62 | missing_random | pa | 2023-05-27 | num_ili |
| 64 | missing_random | co | 2016-09-03 | num_ili |
| 78 | missing_random | hi | 2021-06-26 | num_ili |
| 84 | missing_random | mn | 2016-11-05 | num_ili |
| 85 | missing_random | mt | 2011-03-12 | num_ili |
| 87 | missing_random | pa | 2018-04-07 | num_ili |
| 90 | missing_random | ma | 2015-08-15 | num_ili |
| 103 | missing_random | ar | 2015-02-21 | num_ili |
| 116 | missing_random | nj | 2022-07-23 | num_ili |
| 121 | missing_random | wv | 2012-01-07 | num_ili |
| 126 | missing_random | oh | 2026-04-04 | num_ili |
| 130 | missing_random | ct | 2022-08-13 | num_ili |
| 133 | missing_random | il | 2015-09-19 | num_ili |
| 136 | missing_random | nv | 2014-02-22 | num_ili |
| 137 | missing_random | nc | 2013-06-29 | num_ili |

## tự sinh, seed 2026, chế độ `raw`

Bảng lỗi: 44975 dòng.

| Loại lỗi | Ô/dòng chèn | Bắt được | Recall | Quy tắc bắt (số lỗi) |
| --- | --- | --- | --- | --- |
| Thiếu ngẫu nhiên (ô bị xóa rải rác) (`missing_random`) | 300 | 219 | 73.0% | R06 (178), R05 (168), R07 (42) |
| Mất khối nhiều tuần liên tiếp (mất dòng hoặc mất cả đoạn một tín hiệu) (`missing_block`) | 70 | 70 | 100.0% | R02 (36), R05 (34), R06 (10), R07 (10) |
| Số sơ bộ (4 tuần cuối) bị sửa ±10–50% (`preliminary_revised`) | 60 | 48 | 80.0% | R06 (36), R09 (29), R07 (24), R03 (10) |
| Trùng dòng (`duplicate`) | 80 | 80 | 100.0% | R01 (80) |

Lỗi **không** bắt được:

| error_id | error_type | state | week | column |
| --- | --- | --- | --- | --- |
| 6 | missing_random | ri | 2024-11-23 | num_ili |
| 9 | missing_random | me | 2014-01-25 | num_patients |
| 13 | missing_random | me | 2023-12-09 | num_patients |
| 17 | missing_random | ne | 2016-03-12 | num_ili |
| 21 | missing_random | ne | 2016-01-23 | num_patients |
| 27 | missing_random | wv | 2024-11-23 | num_ili |
| 28 | missing_random | tn | 2021-08-07 | num_patients |
| 40 | missing_random | ma | 2023-11-18 | num_ili |
| 56 | missing_random | or | 2025-05-17 | num_ili |
| 57 | missing_random | ia | 2023-04-01 | num_ili |
| 61 | missing_random | ga | 2011-11-26 | num_ili |
| 75 | missing_random | de | 2020-06-20 | num_ili |
| 80 | missing_random | dc | 2026-05-02 | num_ili |
| 86 | missing_random | vt | 2019-12-07 | num_patients |
| 87 | missing_random | dc | 2021-12-11 | num_ili |
| 89 | missing_random | az | 2012-12-08 | num_ili |
| 91 | missing_random | me | 2023-11-18 | num_ili |
| 92 | missing_random | nm | 2014-01-04 | num_patients |
| 95 | missing_random | nv | 2014-05-17 | num_patients |
| 96 | missing_random | wi | 2025-08-02 | num_patients |
| 97 | missing_random | ar | 2018-09-15 | num_ili |
| 100 | missing_random | la | 2025-03-08 | num_ili |
| 102 | missing_random | mo | 2019-10-12 | num_ili |
| 117 | missing_random | pa | 2017-11-18 | num_ili |
| 118 | missing_random | mt | 2014-09-27 | num_ili |
| 120 | missing_random | mt | 2022-02-05 | num_patients |
| 123 | missing_random | pa | 2019-12-21 | num_ili |
| 124 | missing_random | ms | 2021-02-27 | num_patients |
| 125 | missing_random | sd | 2024-07-06 | num_patients |
| 129 | missing_random | md | 2016-12-17 | num_patients |

## tự sinh, seed 2026, chế độ `consistent`

Bảng lỗi: 44975 dòng.

| Loại lỗi | Ô/dòng chèn | Bắt được | Recall | Quy tắc bắt (số lỗi) |
| --- | --- | --- | --- | --- |
| Thiếu ngẫu nhiên (ô bị xóa rải rác) (`missing_random`) | 300 | 0 | 0.0% |  |
| Mất khối nhiều tuần liên tiếp (mất dòng hoặc mất cả đoạn một tín hiệu) (`missing_block`) | 70 | 36 | 51.4% | R02 (36) |
| Số sơ bộ (4 tuần cuối) bị sửa ±10–50% (`preliminary_revised`) | 60 | 39 | 65.0% | R09 (29), R03 (10) |
| Trùng dòng (`duplicate`) | 80 | 80 | 100.0% | R01 (80) |

Lỗi **không** bắt được:

| error_id | error_type | state | week | column |
| --- | --- | --- | --- | --- |
| 1 | missing_random | az | 2023-02-18 | ili_pct |
| 2 | missing_random | tx | 2026-07-18 | temp_mean |
| 3 | missing_random | nj | 2018-11-03 | abs_humidity |
| 4 | missing_random | ok | 2011-05-28 | pm25_mean |
| 5 | missing_random | wi | 2023-08-19 | ili_pct |
| 6 | missing_random | ri | 2024-11-23 | num_ili |
| 7 | missing_random | az | 2017-12-23 | pm25_mean |
| 8 | missing_random | ia | 2017-09-02 | lab_pct_pos |
| 9 | missing_random | me | 2014-01-25 | num_patients |
| 10 | missing_random | sd | 2018-12-29 | ili_pct |
| 11 | missing_random | mn | 2024-03-23 | rate_flu |
| 12 | missing_random | ms | 2023-08-12 | abs_humidity |
| 13 | missing_random | me | 2023-12-09 | num_patients |
| 14 | missing_random | ca | 2014-08-16 | pm25_mean |
| 15 | missing_random | il | 2026-05-09 | hosp_flu |
| 16 | missing_random | oh | 2025-02-15 | rate_flu |
| 17 | missing_random | ne | 2016-03-12 | num_ili |
| 18 | missing_random | ar | 2021-12-25 | hosp_flu |
| 19 | missing_random | nd | 2020-04-18 | ili_pct |
| 20 | missing_random | ma | 2023-08-12 | ed_pct_flu |
| 21 | missing_random | ne | 2016-01-23 | num_patients |
| 22 | missing_random | az | 2024-08-17 | temp_mean |
| 23 | missing_random | nh | 2026-06-13 | abs_humidity |
| 24 | missing_random | mi | 2016-06-25 | abs_humidity |
| 25 | missing_random | ks | 2018-02-24 | ili_pct |
| 26 | missing_random | id | 2015-01-31 | temp_mean |
| 27 | missing_random | wv | 2024-11-23 | num_ili |
| 28 | missing_random | tn | 2021-08-07 | num_patients |
| 29 | missing_random | ar | 2022-07-09 | lab_pct_pos |
| 30 | missing_random | or | 2024-06-08 | abs_humidity |
