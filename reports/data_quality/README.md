# Báo cáo chất lượng dữ liệu

Sinh tự động bởi `python pipelines/02_warehouse.py --steps quality` lúc 2026-11-16 23:07, trên `data/business/` dựng lúc 2026-11-16T23:07:42 (tuần cuối 2026-11-07). Code: `src/fluwatch/warehouse/quality.py`.

**28 quy tắc**: 27 đạt, 0 không đạt, 1 cảnh báo, 0 lỗi chạy. Mức độ `loi` phải bằng 0 vi phạm; `canh_bao` là giá trị bất thường cần xem, chưa chắc sai.

## 1. Tổng hợp theo quy tắc

### Mức 1 – Giá trị

| Mã | Quy tắc | Bảng | Mức độ | Số ô/dòng kiểm | Vi phạm | Kết quả |
| --- | --- | --- | --- | --- | --- | --- |
| V01 | Tỷ lệ % nằm trong 0–100 | fact_flu_week | loi | 144890 | 0 | ✅ Đạt |
| V02 | Tỷ lệ % (vaccine, khoảng tin cậy) trong 0–100 | fact_season_summary | loi | 2583 | 0 | ✅ Đạt |
| V03 | Số đếm là số nguyên ≥ 0 | fact_flu_week | loi | 276493 | 0 | ✅ Đạt |
| V04 | Tỷ suất nhập viện (ca/100.000 dân/tuần) trong 0–100 | fact_flu_week | loi | 22807 | 0 | ✅ Đạt |
| V05 | Thời tiết, PM2.5 trong miền vật lý (°C −60–55; g/m³ 0–40; µg/m³ 0–1000) | fact_flu_week | loi | 145556 | 0 | ✅ Đạt |
| V06 | WVAL nước thải trong miền hợp lý 0–100 (Very High của CDC từ 15,6) | fact_flu_week | canh_bao | 9831 | 0 | ✅ Đạt |
| V07 | Giá trị danh mục hợp lệ (mức CDC, cờ 0/1, nguồn PM2.5, mã bang) | fact_flu_week | loi | 211409 | 0 | ✅ Đạt |
| V08 | Tuần là thứ Bảy kết thúc tuần MMWR; mùa dạng YYYY-YY | fact_flu_week | loi | 89760 | 0 | ✅ Đạt |

### Mức 2 – Bản ghi

| Mã | Quy tắc | Bảng | Mức độ | Số ô/dòng kiểm | Vi phạm | Kết quả |
| --- | --- | --- | --- | --- | --- | --- |
| R01 | Khóa chính không trống, không trùng (fact: bang × tuần; season: bang × mùa; dim) | * | loi | 46800 | 0 | ✅ Đạt |
| R02 | Đủ khung 51 bang × mọi tuần (không mất dòng, không mất khối tuần) | fact_flu_week | loi | 44880 | 0 | ✅ Đạt |
| R03 | ILI nhất quán trong dòng: num_ili ≤ num_patients; ili_pct = num_ili / num_patients × 100 | fact_flu_week | loi | 41529 | 0 | ✅ Đạt |
| R04 | Mẫu số bằng 0 thì tỷ lệ phải để trống (không có báo cáo ≠ không có cúm) | fact_flu_week | loi | 62909 | 0 | ✅ Đạt |
| R05 | Cờ missing_* khớp với ô giá trị tương ứng | fact_flu_week | loi | 359040 | 0 | ✅ Đạt |
| R06 | Biến trễ khớp giá trị tuần trước của cùng bang (col_lagk tuần t = col tuần t−k) | fact_flu_week | loi | 1432692 | 0 | ✅ Đạt |
| R07 | Biến phái sinh khớp: wow_pct, ili_wow_pct; mức CDC tính lại từ rate_flu và ngưỡng | fact_flu_week | loi | 134640 | 0 | ✅ Đạt |
| R08 | Cờ is_preliminary đúng 4 tuần cuối | fact_flu_week | loi | 44880 | 0 | ✅ Đạt |
| R09 | rate_flu khớp hosp_flu / dân số × 100.000 (dân số suy ra = trung vị theo bang × mùa), lệch ≤ 5% | fact_flu_week | canh_bao | 13924 | 4 | ⚠️ Cảnh báo |
| R10 | PM2.5 EPA năm mới nhất chỉ dùng khi đủ trạm (epa_sites ≥ 50% trung vị 2022–2025 của bang) | fact_flu_week | canh_bao | 691 | 0 | ✅ Đạt |

### Mức 3 – Quan hệ

| Mã | Quy tắc | Bảng | Mức độ | Số ô/dòng kiểm | Vi phạm | Kết quả |
| --- | --- | --- | --- | --- | --- | --- |
| Q01 | Khóa ngoại: fact.state, fact.week, season.state, season.season đều có trong dim | * | loi | 91596 | 0 | ✅ Đạt |
| Q02 | Thuộc tính thời gian trong fact khớp dim_time (epiweek, mùa, tuần trong mùa, nghỉ lễ) | fact_flu_week | loi | 359040 | 0 | ✅ Đạt |
| Q03 | dim_state đúng 51 mã, vùng HHS đúng bảng chuẩn, dân số > 0 | dim_state | loi | 153 | 0 | ✅ Đạt |
| Q04 | dim_source trỏ đúng: bảng clean tồn tại, cột fact_columns có trong fact/dim và ngược lại (cột fact từ nguồn nào thì nguồn đó liệt kê); có người phụ trách | dim_source | loi | 69 | 0 | ✅ Đạt |
| Q05 | Vaccine trong fact_flu_week khớp fact_season_summary theo (bang, mùa) | fact_flu_week | loi | 44880 | 0 | ✅ Đạt |
| Q06 | Mọi cột của bảng business đều có trong từ điển dữ liệu (catalog.py) và ngược lại | * | loi | 160 | 0 | ✅ Đạt |

### Mức 4 – Nhiều bảng

| Mã | Quy tắc | Bảng | Mức độ | Số ô/dòng kiểm | Vi phạm | Kết quả |
| --- | --- | --- | --- | --- | --- | --- |
| M01 | Tổng nhập viện 51 bang = toàn quốc (CDC NHSN HRD, USA trừ lãnh thổ), lệch ≤ 2% hoặc ≤ 10 ca | fact_flu_week | loi | 315 | 0 | ✅ Đạt |
| M02 | Tổng nhập viện các bang trong vùng = vùng HHS (CDC NHSN HRD), lệch ≤ 2% hoặc ≤ 10 ca | fact_flu_week | loi | 3111 | 0 | ✅ Đạt |
| M03 | Đối soát lineage: mỗi ô nguồn trong business bằng đúng ô trong clean/ (không mất, không sửa) | fact_flu_week | loi | 1032240 | 0 | ✅ Đạt |
| M04 | fact_season_summary khớp roll-up tuần → mùa tính lại từ fact_flu_week | fact_season_summary | loi | 4590 | 0 | ✅ Đạt |

Ghi chú M01/M02: 4 tuần cuối của bản chụp HRD là số sơ bộ lúc tải, CDC đã sửa sau đó, nên chỉ đếm, không tính vi phạm (M01: 3 tuần lệch, M02: 12 vùng × tuần lệch). Đây là bằng chứng trực tiếp cho quy tắc cập nhật 4 tuần gần nhất.

## 2. Chi tiết vi phạm (tối đa 10 dòng mỗi quy tắc)

Toàn bộ vi phạm: `reports/data_quality/violations.csv`.

### R09. rate_flu khớp hosp_flu / dân số × 100.000 (dân số suy ra = trung vị theo bang × mùa), lệch ≤ 5%

4 vi phạm; theo cột: `hosp_flu` 2, `rate_flu` 2.

| table | state | week | season | column | value | detail |
| --- | --- | --- | --- | --- | --- | --- |
| fact_flu_week | mn | 2020-11-14 | 2020-21 | rate_flu | 0.52 | rate_flu = 0.52, tinh tu hosp_flu = 0.57 |
| fact_flu_week | mn | 2021-03-06 | 2020-21 | rate_flu | 0.31 | rate_flu = 0.31, tinh tu hosp_flu = 0.34 |
| fact_flu_week | mn | 2020-11-14 | 2020-21 | hosp_flu | 30 | rate_flu = 0.52, tinh tu hosp_flu = 0.57 |
| fact_flu_week | mn | 2021-03-06 | 2020-21 | hosp_flu | 18 | rate_flu = 0.31, tinh tu hosp_flu = 0.34 |

## 3. Độ phủ bang × năm

% tuần thiếu của mỗi (bang, năm), chỉ tính trong khoảng nguồn có dữ liệu. Ô thiếu > 30% bị gắn cờ. Bảng đầy đủ: `reports/data_quality/coverage_state_year.csv`.

| Tín hiệu | Khoảng có dữ liệu | Ô bang × năm | Ô thiếu > 30% | Bang × năm bị gắn cờ |
| --- | --- | --- | --- | --- |
| ILINet ILI% (`ili_pct`) | 2010-10-09 → 2026-11-07 | 867 | 28 (3%) | **LA**: 2010–2016 (100%); **FL**: 2010–2021 (100%); **DE**: 2011 (32%); **AK, CT, HI, NY, OK, OR, SD, UT**: 2026 (89%) |
| NHSN nhập viện (`rate_flu`) | 2020-08-08 → 2026-11-07 | 357 | 46 (13%) | **CT**: 2020 (33%); **AZ, SD**: 2020 (38%); **ID, NE, OK, WI**: 2020 (43%); **AK, AR, CA, CO, FL, HI, IL, KS, LA, MD, ME, MO, MS, MT, NC, NH, NJ, OR, PA, TN, TX, UT, VA, WY**: 2020 (48%); **AL, DC, DE, IA, IN, KY, MN, ND, NM, OH, RI, VT, WV**: 2020 (52%); **MA**: 2020 (52%), 2024 (33%) |
| NSSP cấp cứu (`ed_pct_flu`) | 2022-10-01 → 2026-11-07 | 255 | 0 (0%) | – |
| Xét nghiệm % dương tính (`lab_pct_pos`) | 2016-10-08 → 2026-11-07 | 561 | 132 (24%) | **ME**: 2016–2018 (92%), 2022–2023 (75%); **FL**: 2016–2021 (100%); **NJ**: 2016–2023 (100%); **NV**: 2016–2024 (100%); **AK, DC, NY, RI, WY**: 2016–2026 (100%); **ND**: 2017 (54%), 2021–2023 (100%); **ID**: 2017–2019 (42%), 2021 (36%); **NH**: 2017–2026 (100%); **SC**: 2020 (31%); **DE**: 2020–2026 (100%); **NC**: 2021–2022 (76%); **UT**: 2021–2026 (100%); **KS**: 2024–2026 (100%); **LA, OK, TN**: 2025–2026 (100%); **MS**: 2025–2026 (89%); **CT, HI, OR, SD**: 2026 (89%) |
| Nước thải WVAL (`wval`) | 2022-01-01 → 2026-11-07 | 255 | 71 (28%) | **DE, HI, NV, VT, WV**: 2022 (100%); **MI**: 2022 (30%); **OK**: 2022 (36%); **CO**: 2022 (38%); **GA**: 2022 (51%); **IL, KS, NJ, PA, WI**: 2022 (58%); **AL**: 2022 (60%); **IN**: 2022 (62%); **NC**: 2022 (64%); **MN**: 2022 (66%); **ME**: 2022 (68%); **UT**: 2022 (72%); **NH**: 2022 (77%); **IA, MA, MD, OH, VA**: 2022 (94%); **AK, AR, AZ, CT, DC, LA, MS, NE, NM, NY, SC, SD, TN, WA, WY**: 2022–2023 (100%); **MO**: 2022–2023 (96%); **RI**: 2022–2024 (100%); **MT**: 2022–2024 (100%), 2026 (42%); **ND**: 2022–2026 (100%); **OR**: 2023 (35%) |
| Độ ẩm tuyệt đối (`abs_humidity`) | 2010-01-02 → 2026-11-07 | 867 | 0 (0%) | – |
| PM2.5 (`pm25_mean`) | 2010-01-02 → 2026-11-07 | 867 | 10 (1%) | **ME**: 2010–2012 (100%); **IL**: 2011–2014 (100%); **MS**: 2012–2014 (100%) |
| Độ phủ vaccine (`flu_vax_pct`) | 2010-01-02 → 2026-10-03 | 867 | 6 (1%) | **CA**: 2014 (75%); **MS**: 2014 (75%), 2026 (100%); **DC**: 2018–2019 (100%); **NJ**: 2019 (75%) |
