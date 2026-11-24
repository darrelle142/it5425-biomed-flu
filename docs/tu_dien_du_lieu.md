# Từ điển dữ liệu và lineage

> 📍 [Mục lục tài liệu](README.md) · Quản trị dữ liệu: [quan_tri_du_lieu.md](quan_tri_du_lieu.md) · Chất lượng: [reports/data_quality/README.md](../reports/data_quality/README.md)

Sinh tự động bởi `python pipelines/02_warehouse.py --steps docs` lúc 2026-11-24 08:30 từ `src/fluwatch/warehouse/catalog.py` và các file `data/business/*.parquet` thật (kiểu, % thiếu). Muốn sửa mô tả thì sửa `catalog.py` rồi chạy lại; quy tắc chất lượng Q06 báo lỗi khi có cột chưa được mô tả.

**Cách đọc cột Lineage**: `raw/<nguồn>` (dữ liệu gốc, giữ nguyên) → `clean/<bảng>` (chuẩn hóa từng nguồn) → `business/` (ghép theo khóa bang × tuần). Cột *Nguồn* trỏ tới `source_id` trong `dim_source` (xem [quan_tri_du_lieu.md](quan_tri_du_lieu.md)); *phái sinh* là cột TV2 tính trong `business.py`; *dim* là khóa hoặc thuộc tính chiều; *TV3* là cột do TV3 giao.

Cột đánh dấu ★ thuộc hợp đồng dữ liệu (`docs/ke_hoach.md` mục 4.1): không đổi tên, không bỏ.

## `dim_state`

Chiều địa lý: bang → vùng HHS → toàn quốc. Khóa chính: `state`. 51 dòng × 10 cột.

| Cột | Kiểu | % thiếu | Ý nghĩa | Đơn vị | Nguồn | Lineage / phép biến đổi |
| --- | --- | --- | --- | --- | --- | --- |
| `state` | object | 0.0 | Mã bang 2 chữ viết thường | – | `population` (Dan so 2020) | khóa; 50 bang + DC |
| `state_name` | object | 0.0 | Tên bang | – | `population` (Dan so 2020) | `raw/population/state_pop_2020_delphi` |
| `hhs_region` | Int64 | 0.0 | Vùng HHS 1–10 | – | dim | bảng cố định HHS (`common.HHS_REGION`) |
| `hhs_region_name` | object | 0.0 | Tên vùng HHS | – | dim | ‘Vung ’ + số vùng |
| `country` | object | 0.0 | Quốc gia (us), cấp trên cùng để roll-up | – | dim | hằng |
| `population` | Int64 | 0.0 | Dân số 2020 | người | `population` (Dan so 2020) | `raw/population/state_pop_2020_delphi.csv` |
| `contiguous` | bool | 0.0 | Thuộc 48 bang lục địa + DC (không gồm AK, HI) | bool | dim | hằng |
| `lat` | float64 | 0.0 | Vĩ độ trọng tâm dân số (các đô thị đo thời tiết) | độ | dim | trung bình có trọng số dân số các đô thị trong `reference/cities.csv` |
| `lon` | float64 | 0.0 | Kinh độ trọng tâm dân số | độ | dim | như `lat` |
| `cluster_id` | Int64 | 2.0 | Cụm bang theo hình dạng đường cong mùa (TV3, Ward, k theo silhouette); FL trống vì thiếu ILINet | – | TV3 | TV3 → `state_cluster.parquet`, TV2 ghép; trống khi chưa giao |

## `dim_time`

Chiều thời gian: tuần → tháng → năm. tuần → mùa; có nghỉ lễ. Khóa chính: `week`. 939 dòng × 15 cột.

| Cột | Kiểu | % thiếu | Ý nghĩa | Đơn vị | Nguồn | Lineage / phép biến đổi |
| --- | --- | --- | --- | --- | --- | --- |
| `week` | datetime64[ns] | 0.0 | Thứ Bảy kết thúc tuần MMWR | ngày | dim | khóa; từ 2010-01-02 đến hết năm sau tuần cuối có số |
| `epiweek` | Int64 | 0.0 | Năm-tuần MMWR YYYYWW | – | dim | tính từ `week` |
| `mmwr_year` | Int64 | 0.0 | Năm MMWR | năm | dim | năm của ngày thứ Tư trong tuần |
| `mmwr_week` | Int64 | 0.0 | Tuần MMWR 1–53 | tuần | dim | tuần 1 là tuần CN–T7 chứa ngày 4/1 |
| `week_start` | datetime64[ns] | 0.0 | Chủ nhật đầu tuần | ngày | dim | `week` − 6 ngày |
| `week_end` | datetime64[ns] | 0.0 | Thứ Bảy cuối tuần (= `week`) | ngày | dim | = `week` |
| `season` | string | 0.0 | Mùa cúm (bắt đầu tuần MMWR 40) | – | dim | `season_of` |
| `season_week` | Int64 | 0.0 | Tuần trong mùa (1 = tuần MMWR 40) | tuần | dim | `season_of` |
| `year` | Int64 | 0.0 | Năm dương lịch của `week` | năm | dim | tính từ `week` |
| `month` | Int64 | 0.0 | Tháng dương lịch của `week` | tháng | dim | tính từ `week` |
| `in_flu_season` | boolean | 0.0 | Thuộc mùa cúm CDC theo dõi (tuần MMWR 40–20) | bool | dim | `mmwr_week` ≥ 40 hoặc ≤ 20 |
| `holiday_week` | Int64 | 0.0 | Tuần có lễ lớn | 0/1 | `holidays` (Ngay le va ky nghi dong) | `reference/holidays.csv` |
| `holiday_name` | object | 94.2 | Tên lễ (Thanksgiving, Christmas, New Year) | – | `holidays` (Ngay le va ky nghi dong) | `reference/holidays.csv` |
| `winter_break` | Int64 | 0.0 | Tuần nghỉ đông (tạm) | 0/1 | `holidays` (Ngay le va ky nghi dong) | `reference/holidays.csv` |
| `weeks_to_holiday` | Int64 | 0.0 | Số tuần đến tuần lễ gần nhất | tuần | `holidays` (Ngay le va ky nghi dong) | `reference/holidays.csv` |

## `dim_source`

Chiều nguồn dữ liệu: metadata quản trị (người phụ trách. quy tắc cập nhật. giấy phép). Khóa chính: `source_id`. 12 dòng × 21 cột.

| Cột | Kiểu | % thiếu | Ý nghĩa | Đơn vị | Nguồn | Lineage / phép biến đổi |
| --- | --- | --- | --- | --- | --- | --- |
| `source_id` | object | 0.0 | Mã nguồn | – | dim | khóa; khai báo tay trong `business.SOURCES` |
| `source_name` | object | 0.0 | Tên nguồn | – | dim | khai báo tay |
| `provider` | object | 0.0 | Đơn vị cung cấp / đường lấy | – | dim | khai báo tay |
| `access` | object | 0.0 | Cách truy cập (API, GitHub Actions, file…) | – | dim | khai báo tay |
| `dataset_id` | object | 0.0 | Mã bộ dữ liệu ở nguồn | – | dim | khai báo tay |
| `raw_path` | object | 0.0 | Thư mục dữ liệu thô | – | dim | khai báo tay |
| `clean_table` | object | 0.0 | Bảng trong `data/clean/` | – | dim | khai báo tay; Q04 kiểm tra tồn tại |
| `fact_columns` | object | 0.0 | Các cột business lấy từ nguồn này | – | dim | khai báo tay; Q04 kiểm tra tồn tại |
| `unit` | object | 0.0 | Đơn vị | – | dim | khai báo tay |
| `frequency` | object | 0.0 | Tần suất | – | dim | khai báo tay |
| `geo_level` | object | 0.0 | Cấp địa lý gốc | – | dim | khai báo tay |
| `revised` | bool | 0.0 | Nguồn có sửa số liệu cũ không | bool | dim | khai báo tay |
| `update_rule` | object | 0.0 | Quy tắc cập nhật | – | dim | khai báo tay (xem `docs/quan_tri_du_lieu.md`) |
| `license` | object | 0.0 | Giấy phép | – | dim | khai báo tay |
| `owner` | object | 0.0 | Người phụ trách thu thập (owner) | – | dim | khai báo tay |
| `steward` | object | 0.0 | Người làm sạch, đưa vào kho (steward) | – | dim | khai báo tay |
| `users` | object | 0.0 | Thành viên dùng nguồn này | – | dim | khai báo tay |
| `first_period` | object | 25.0 | Kỳ đầu tiên trong `clean/` | ngày/mùa | dim | đọc `_clean_log.json` |
| `last_period` | object | 25.0 | Kỳ cuối cùng trong `clean/` | ngày/mùa | dim | đọc `_clean_log.json` |
| `raw_files` | object | 0.0 | Các file raw đã đọc (tối đa 3) | – | dim | đọc `_clean_log.json` |
| `built_at` | object | 0.0 | Thời điểm dựng | thời điểm | dim | lúc chạy |

## `fact_flu_week`

Bảng sự kiện chính: một dòng là một bang × một tuần MMWR (51 bang × mọi tuần từ 2010-01-02). Khóa chính: `(state. week)`. 44.931 dòng × 90 cột.

| Cột | Kiểu | % thiếu | Ý nghĩa | Đơn vị | Nguồn | Lineage / phép biến đổi |
| --- | --- | --- | --- | --- | --- | --- |
| `state` ★ | object | 0.0 | Mã bang 2 chữ viết thường (50 bang + DC) | – | dim | khóa; mã CDC/Delphi → viết thường, bỏ GU, VI, PR, nyc… (`keep_states`) |
| `week` ★ | datetime64[ns] | 0.0 | Thứ Bảy kết thúc tuần MMWR (CN–T7) | ngày | dim | khóa; `reference_time` của Delphi / `Week_End` của CDC / ngày quy về thứ Bảy |
| `epiweek` ★ | Int64 | 0.0 | Năm-tuần MMWR dạng YYYYWW | – | dim | tính từ `week` (`mmwr_year_week`), nhận từ `dim_time` |
| `season` ★ | object | 0.0 | Mùa cúm dạng 2024-25, bắt đầu tuần MMWR 40 | – | dim | tính từ `week` (`season_of`) |
| `season_week` ★ | Int64 | 0.0 | Thứ tự tuần trong mùa (1 = tuần MMWR 40) | tuần | dim | tính từ `week` (`season_of`) |
| `ili_pct` ★ | float64 | 7.5 | % lượt khám có hội chứng giống cúm (ILI) trong ILINet | % | `ilinet` (ILINet (FluView)) | Delphi Epidata V5 `fluview_ilinet/ili__state` (file mới nhất) → `clean/ilinet`: lọc 50 bang + DC, bỏ trùng (bang, tuần) giữ bản công bố mới nhất, âm → thiếu; nhóm tuổi `all` |
| `num_ili` ★ | Int64 | 7.5 | Số lượt khám ILI trong tuần | lượt | `ilinet` (ILINet (FluView)) | Delphi Epidata V5 `fluview_ilinet/num_ili__state` (file mới nhất) → `clean/ilinet`: lọc 50 bang + DC, bỏ trùng (bang, tuần) giữ bản công bố mới nhất, âm → thiếu; làm tròn số nguyên |
| `num_patients` ★ | Int64 | 7.5 | Tổng lượt khám tại các cơ sở báo cáo ILINet | lượt | `ilinet` (ILINet (FluView)) | Delphi Epidata V5 `fluview_ilinet/num_patients__state` (file mới nhất) → `clean/ilinet`: lọc 50 bang + DC, bỏ trùng (bang, tuần) giữ bản công bố mới nhất, âm → thiếu |
| `hosp_flu` ★ | Int64 | 63.9 | Ca nhập viện cúm xác nhận trong tuần (NHSN) | ca | `nhsn` (NHSN nhap vien cum) | Delphi Epidata V5 `nhsn/confirmed_admissions_flu_ew__state` (file mới nhất) → `clean/nhsn`: lọc 50 bang + DC, bỏ trùng (bang, tuần) giữ bản công bố mới nhất, âm → thiếu |
| `rate_flu` ★ | float64 | 63.9 | Ca nhập viện cúm / 100.000 dân / tuần (NHSN) | ca/100.000 dân | `nhsn` (NHSN nhap vien cum) | Delphi Epidata V5 `nhsn/confirmed_admissions_flu_per100k_ew__state` (file mới nhất) → `clean/nhsn`: lọc 50 bang + DC, bỏ trùng (bang, tuần) giữ bản công bố mới nhất, âm → thiếu |
| `cdc_level` ★ | Int64 | 63.9 | Mức độ nhập viện cúm theo ngưỡng CDC: 0 Very Low … 4 Very High | 0–4 | `cdc_thresholds` (Nguong muc do nhap vien CDC) | phái sinh: so `rate_flu` với ngưỡng của bang trong `reference/cdc_level_thresholds.csv` (cận trên ‘Up to x’ tính ≤) |
| `ed_pct_flu` ★ | float64 | 75.5 | % lượt cấp cứu do cúm (NSSP) | % | `nssp` (NSSP cap cuu) | Delphi Epidata V5 `nssp/pct_ed_visits_influenza__state` (file mới nhất) → `clean/nssp`: lọc 50 bang + DC, bỏ trùng (bang, tuần) giữ bản công bố mới nhất, âm → thiếu |
| `lab_pct_pos` ★ | float64 | 53.1 | % mẫu xét nghiệm lâm sàng dương tính cúm | % | `lab_clinical` (Xet nghiem lam sang (FluView)) | Delphi Epidata V5 `fluview_resp_lab_clinical/pct_positive__state` (file mới nhất) → `clean/lab_clinical`: lọc 50 bang + DC, bỏ trùng (bang, tuần) giữ bản công bố mới nhất, âm → thiếu |
| `wval` ★ | float64 | 78.0 | Mức virus cúm A trong nước thải (WVAL), trung vị có trọng số dân số phục vụ các trạm trong bang | không đơn vị (1 = mức nền) | `wval` (Nuoc thai WVAL cum A) | CDC `atcp-73re` (mọi lần tải, mỗi tuần giữ bản mới nhất) → `clean/wval`: chỉ cúm A, bỏ trạm WVAL > 1000 (sai miền), chặn trần 100 cho trạm 100–1000, trung vị có trọng số `Population_Served` |
| `temp_mean` ★ | float64 | 0.0 | Nhiệt độ trung bình tuần, có trọng số dân số 3–5 đô thị | °C | `weather` (Thoi tiet + PM2.5 Open-Meteo) | Open-Meteo theo ngày từng đô thị (`reference/cities.csv`) → trung bình tuần → trung bình có trọng số dân số (`clean/weather`) |
| `abs_humidity` ★ | float64 | 0.0 | Độ ẩm tuyệt đối trung bình tuần | g/m³ | `weather` (Thoi tiet + PM2.5 Open-Meteo) | Open-Meteo nhiệt độ + độ ẩm tương đối theo ngày → công thức Magnus → trung bình tuần → trọng số dân số (`clean/weather`) |
| `ah_anomaly` ★ | float64 | 0.0 | Độ ẩm tuyệt đối trừ trung bình nhiều năm cùng bang, cùng tuần MMWR (loại mùa vụ) | g/m³ | phái sinh | `abs_humidity` − trung bình cùng (bang, tuần MMWR) các năm 2010–2025; tuần 53 dùng trung bình tuần 52 |
| `pm25_mean` ★ | float64 | 1.0 | PM2.5 trung bình tuần, **ghép hai nguồn** (EPA, thiếu thì Open-Meteo), có số đến tuần hiện tại: **dùng để hiển thị** (dashboard; đoạn Open-Meteo vẽ khác, theo `pm25_source`). **Phân tích, hồi quy dùng `pm25_epa`**, biến trễ cũng tự tính từ `pm25_epa` (không dùng `pm25_mean_lag*`, vì năm 2026 cũng là số ghép). Hai nguồn lệch thang đo: Open-Meteo là số mô hình CAMS, cao hơn EPA ~25%, tương quan 0,55; ở các đợt khói cháy rừng chỉ bằng khoảng nửa EPA | µg/m³ | `epa` (EPA AirData PM2.5 (88101)) | `pm25_epa`, ô trống thì lấy `pm25_om`; nguồn ghi ở `pm25_source` |
| `flu_vax_pct` ★ | float64 | 1.4 | Độ phủ vaccine cúm ≥ 6 tháng tuổi của mùa (tháng cuối mùa có số) | % dân số | `vaccine` (Do phu vaccine cum (FluVaxView)) | CDC `vh55-3he6` → `clean/vaccine`: lấy tháng 5 (cuối mùa) → gán cho mọi tuần của mùa; mùa CDC dừng công bố trước tháng 5 (CA, MS 2013-14; DC 2017-18) để trống vì độ phủ là số cộng dồn, số giữa mùa thấp hơn thật (xem `fact_season_summary.vax_month`). **Chú ý**: là số cuối mùa, không dùng làm biến dự báo các tuần đầu mùa (dùng `flu_vax_pct_prev`) |
| `holiday_week` ★ | Int64 | 0.0 | Tuần có Lễ Tạ ơn, Giáng sinh hoặc Năm mới | 0/1 | `holidays` (Ngay le va ky nghi dong) | `reference/holidays.csv` (nhóm tự lập) qua `dim_time` |
| `winter_break` ★ | Int64 | 0.0 | Tuần nằm trong kỳ nghỉ đông (tạm: 18/12 – 1/1) | 0/1 | `holidays` (Ngay le va ky nghi dong) | `reference/holidays.csv` qua `dim_time` |
| `weeks_to_holiday` ★ | Int64 | 0.0 | Số tuần đến tuần lễ gần nhất phía trước | tuần | `holidays` (Ngay le va ky nghi dong) | `reference/holidays.csv` qua `dim_time` |
| `is_preliminary` ★ | bool | 0.0 | Số liệu sơ bộ: 4 tuần gần nhất, CDC còn sửa | bool | phái sinh | `week` > tuần cuối − 4 tuần (tuần cuối = tuần mới nhất của ILINet/NHSN/NSSP) |
| `mmwr_year` | Int64 | 0.0 | Năm MMWR (năm của ngày thứ Tư trong tuần) | năm | dim | tính từ `week` |
| `mmwr_week` | Int64 | 0.0 | Tuần MMWR 1–53 | tuần | dim | tính từ `week` |
| `num_providers` | Int64 | 7.5 | Số cơ sở báo cáo ILINet trong tuần | cơ sở | `ilinet` (ILINet (FluView)) | Delphi Epidata V5 `fluview_ilinet/num_providers__state` (file mới nhất) → `clean/ilinet`: lọc 50 bang + DC, bỏ trùng (bang, tuần) giữ bản công bố mới nhất, âm → thiếu |
| `hosp_reporting` | Int64 | 62.8 | Số bệnh viện báo cáo NHSN trong tuần | bệnh viện | `nhsn` (NHSN nhap vien cum) | Delphi Epidata V5 `nhsn/hosprep_confirmed_admissions_flu_ew__state` (file mới nhất) → `clean/nhsn`: lọc 50 bang + DC, bỏ trùng (bang, tuần) giữ bản công bố mới nhất, âm → thiếu |
| `low_reporting` | bool | 0.0 | Cờ: số bệnh viện báo cáo NHSN tuần này < 50% mức thường của bang → `rate_flu`, `hosp_flu`, `cdc_level` thấp giả tạo (báo cáo tự nguyện 5–10/2024, giai đoạn khởi động 2020–2021); nên loại khi huấn luyện/đánh giá | bool | `nhsn` (NHSN nhap vien cum) | `hosp_reporting` < 0.5 × trung vị `hosp_reporting` của bang các năm 2023–2025 |
| `beds_flu_pct` | float64 | 63.9 | % giường nội trú có bệnh nhân cúm | % | `nhsn` (NHSN nhap vien cum) | Delphi Epidata V5 `nhsn/inpatient_beds_flu_pct_ew__state` (file mới nhất) → `clean/nhsn`: lọc 50 bang + DC, bỏ trùng (bang, tuần) giữ bản công bố mới nhất, âm → thiếu |
| `cdc_level_name` | string | 63.9 | Tên mức CDC: rat_thap, thap, trung_binh, cao, rat_cao | – | phái sinh | ánh xạ từ `cdc_level` |
| `ed_pct_covid` | float64 | 75.5 | % lượt cấp cứu do COVID-19 (NSSP) | % | `nssp` (NSSP cap cuu) | Delphi Epidata V5 `nssp/pct_ed_visits_covid__state` (file mới nhất) → `clean/nssp`: lọc 50 bang + DC, bỏ trùng (bang, tuần) giữ bản công bố mới nhất, âm → thiếu |
| `lab_specimens` | Int64 | 52.3 | Số mẫu xét nghiệm lâm sàng trong tuần | mẫu | `lab_clinical` (Xet nghiem lam sang (FluView)) | Delphi Epidata V5 `fluview_resp_lab_clinical/total_specimens__state` (file mới nhất) → `clean/lab_clinical`: lọc 50 bang + DC, bỏ trùng (bang, tuần) giữ bản công bố mới nhất, âm → thiếu |
| `flusurv_rate` | float64 | 85.2 | Tỷ suất nhập viện cúm FluSurv-NET (chỉ các bang tham gia) | ca/100.000 dân | `flusurv` (FluSurv-NET) | Delphi Epidata V5 `flusurv/rate_overall__state` (file mới nhất) → `clean/flusurv`: lọc 50 bang + DC, bỏ trùng (bang, tuần) giữ bản công bố mới nhất, âm → thiếu |
| `wval_mean` | float64 | 78.0 | WVAL trung bình có trọng số dân số phục vụ (nhạy hơn `wval` ở mức thấp, vì trung vị hay dính ở 1) | không đơn vị | `wval` (Nuoc thai WVAL cum A) | như `wval` nhưng lấy trung bình có trọng số thay cho trung vị (`clean/wval.wval_mean`) |
| `wval_sites` | Int64 | 78.0 | Số trạm nước thải góp vào `wval` trong tuần | trạm | `wval` (Nuoc thai WVAL cum A) | đếm trạm sau khi bỏ trạm sai miền (`clean/wval`) |
| `wval_sites_extreme` | Int64 | 78.0 | Số trạm bị bỏ vì WVAL > 1000 (sai miền) | trạm | `wval` (Nuoc thai WVAL cum A) | đếm trong `clean/wval`, có ghi `_clean_log.json` |
| `wval_sites_capped` | Int64 | 78.0 | Số trạm có WVAL 100–1000 bị chặn trần ở 100 | trạm | `wval` (Nuoc thai WVAL cum A) | đếm trong `clean/wval`, có ghi `_clean_log.json` |
| `flu_vax_pct_prev` | float64 | 4.7 | Độ phủ vaccine cuối mùa **trước** (đã biết từ đầu mùa này): dùng cột này làm biến dự báo | % dân số | `vaccine` (Do phu vaccine cum (FluVaxView)) | `clean/vaccine.flu_vax_pct` của mùa trước, ghép theo (bang, mùa); mùa trước CDC không công bố thì mượn mùa gần nhất có số (tối đa 1 mùa), đánh dấu ở `vax_prev_carried` |
| `vax_prev_carried` | bool | 0.0 | `flu_vax_pct_prev` là số **mượn** từ mùa cũ hơn (mùa trước không có số) | bool | phái sinh | True khi mùa trước trống mà lùi ≤ 1 mùa nữa có số (vd. MS 2026-27 mượn 2024-25) |
| `pm25_epa` | float64 | 4.7 | PM2.5 trung bình tuần chỉ từ EPA AirData 88101 (một thước đo xuyên suốt 2010 → 5/2026): dùng cột này cho hồi quy | µg/m³ | `epa` (EPA AirData PM2.5 (88101)) | `clean/epa_pm25.epa_pm25_mean` (trung bình các trạm trong bang); trong năm mới nhất của EPA (file công bố dở), tuần có `epa_sites` < 50% trung vị 2022–2025 của bang thì để trống |
| `pm25_om` | float64 | 74.6 | PM2.5 trung bình tuần chỉ từ Open-Meteo (mô hình CAMS, có đến tuần hiện tại), có trọng số dân số | µg/m³ | `weather` (Thoi tiet + PM2.5 Open-Meteo) | Open-Meteo theo giờ → trung bình tuần từng đô thị → trọng số dân số (`clean/weather.pm25_om_mean`) |
| `pm25_max` | float64 | 74.6 | PM2.5 theo giờ lớn nhất trong tuần (Open-Meteo), có trọng số dân số | µg/m³ | `weather` (Thoi tiet + PM2.5 Open-Meteo) | Open-Meteo theo giờ → max tuần từng đô thị → trọng số dân số (`clean/weather.pm25_om_max`) |
| `pm25_source` | string | 1.0 | Nguồn của `pm25_mean`: epa hoặc openmeteo | – | phái sinh | `epa` nếu `pm25_epa` có số, không thì `openmeteo` |
| `epa_sites` | Int64 | 4.4 | Số trạm EPA có số PM2.5 trong tuần (kể cả tuần bị bỏ vì thiếu trạm) | trạm | `epa` (EPA AirData PM2.5 (88101)) | đếm trạm trong `clean/epa_pm25` |
| `n_cities` | Int64 | 0.0 | Số đô thị có số thời tiết trong tuần (1–5) | đô thị | `weather` (Thoi tiet + PM2.5 Open-Meteo) | đếm trong `clean/weather` |
| `wow_pct` | float64 | 69.0 | % thay đổi `rate_flu` so với tuần trước | % | phái sinh | (`rate_flu` − `rate_flu_lag1`) / `rate_flu_lag1` × 100; trống khi tuần trước = 0 |
| `yoy_pct` | float64 | 74.8 | % thay đổi `rate_flu` so với cùng `season_week` mùa trước | % | phái sinh | như `wow_pct`, mẫu số là cùng tuần trong mùa của mùa trước |
| `ili_wow_pct` | float64 | 9.6 | % thay đổi `ili_pct` so với tuần trước | % | phái sinh | như `wow_pct` với `ili_pct` |
| `ili_yoy_pct` | float64 | 15.8 | % thay đổi `ili_pct` so với cùng `season_week` mùa trước | % | phái sinh | như `yoy_pct` với `ili_pct` |
| `ili_pct_lag1`, `ili_pct_lag2`, `ili_pct_lag3` | float64 | 7.8 | Giá trị `ili_pct` của 1…3 tuần trước, cùng bang | % | phái sinh | `ili_pct` của tuần `week` − k |
| `rate_flu_lag1`, `rate_flu_lag2`, `rate_flu_lag3` | float64 | 64.1 | Giá trị `rate_flu` của 1…3 tuần trước, cùng bang | ca/100.000 dân | phái sinh | `rate_flu` của tuần `week` − k |
| `hosp_flu_lag1`, `hosp_flu_lag2`, `hosp_flu_lag3` | Int64 | 64.1 | Giá trị `hosp_flu` của 1…3 tuần trước, cùng bang | ca | phái sinh | `hosp_flu` của tuần `week` − k |
| `ed_pct_flu_lag1`, `ed_pct_flu_lag2`, `ed_pct_flu_lag3` | float64 | 75.7 | Giá trị `ed_pct_flu` của 1…3 tuần trước, cùng bang | % | phái sinh | `ed_pct_flu` của tuần `week` − k |
| `lab_pct_pos_lag1`, `lab_pct_pos_lag2`, `lab_pct_pos_lag3` | float64 | 53.3 | Giá trị `lab_pct_pos` của 1…3 tuần trước, cùng bang | % | phái sinh | `lab_pct_pos` của tuần `week` − k |
| `wval_lag1`, `wval_lag2`, `wval_lag3` | float64 | 78.2 | Giá trị `wval` của 1…3 tuần trước, cùng bang | không đơn vị (1 = mức nền) | phái sinh | `wval` của tuần `week` − k |
| `wval_mean_lag1`, `wval_mean_lag2`, `wval_mean_lag3` | float64 | 78.2 | Giá trị `wval_mean` của 1…3 tuần trước, cùng bang | không đơn vị | phái sinh | `wval_mean` của tuần `week` − k |
| `ah_anomaly_lag1`, `ah_anomaly_lag2`, `ah_anomaly_lag3`, `ah_anomaly_lag4` | float64 | 0.3 | Giá trị `ah_anomaly` của 1…4 tuần trước, cùng bang | g/m³ | phái sinh | `ah_anomaly` của tuần `week` − k |
| `pm25_mean_lag1`, `pm25_mean_lag2`, `pm25_mean_lag3`, `pm25_mean_lag4` | float64 | 1.3 | Giá trị `pm25_mean` của 1…4 tuần trước, cùng bang | µg/m³ | phái sinh | `pm25_mean` của tuần `week` − k |
| `temp_mean_lag1`, `temp_mean_lag2`, `temp_mean_lag3` | float64 | 0.2 | Giá trị `temp_mean` của 1…3 tuần trước, cùng bang | °C | phái sinh | `temp_mean` của tuần `week` − k |
| `missing_ili` | bool | 0.0 | Cờ: `ili_pct` bị thiếu ở dòng này | bool | phái sinh | `ili_pct` là NA |
| `missing_hosp` | bool | 0.0 | Cờ: `rate_flu` bị thiếu ở dòng này | bool | phái sinh | `rate_flu` là NA |
| `missing_ed` | bool | 0.0 | Cờ: `ed_pct_flu` bị thiếu ở dòng này | bool | phái sinh | `ed_pct_flu` là NA |
| `missing_lab` | bool | 0.0 | Cờ: `lab_pct_pos` bị thiếu ở dòng này | bool | phái sinh | `lab_pct_pos` là NA |
| `missing_wval` | bool | 0.0 | Cờ: `wval` bị thiếu ở dòng này | bool | phái sinh | `wval` là NA |
| `missing_weather` | bool | 0.0 | Cờ: `abs_humidity` bị thiếu ở dòng này | bool | phái sinh | `abs_humidity` là NA |
| `missing_pm25` | bool | 0.0 | Cờ: `pm25_mean` bị thiếu ở dòng này | bool | phái sinh | `pm25_mean` là NA |
| `missing_vax` | bool | 0.0 | Cờ: `flu_vax_pct` bị thiếu ở dòng này | bool | phái sinh | `flu_vax_pct` là NA |
| `issue_date` | datetime64[us] | 5.8 | Ngày công bố mới nhất của các tín hiệu Delphi trong dòng | ngày | phái sinh | max(`report_time`) của ILINet, NHSN, NSSP, xét nghiệm, FluSurv; dùng để biết dòng đã bị CDC sửa khi nào |

## `fact_season_summary`

Bảng sự kiện theo mùa: một dòng là một bang × một mùa (roll-up tuần → mùa. vaccine. mốc mùa của TV3). Khóa chính: `(state. season)`. 918 dòng × 24 cột.

| Cột | Kiểu | % thiếu | Ý nghĩa | Đơn vị | Nguồn | Lineage / phép biến đổi |
| --- | --- | --- | --- | --- | --- | --- |
| `state` | object | 0.0 | Mã bang | – | dim | khóa |
| `season` | object | 0.0 | Mùa cúm (2024-25) | – | dim | khóa |
| `flu_vax_pct` | float64 | 6.2 | Độ phủ vaccine cúm ≥ 6 tháng, tháng cuối mùa có số | % dân số | `vaccine` (Do phu vaccine cum (FluVaxView)) | `clean/vaccine` (xem `fact_flu_week.flu_vax_pct`) |
| `baseline` | float64 | 18.5 | Mức nền kiểu CDC của bang × mùa: trung bình + 2 độ lệch chuẩn tuần ngoài mùa của 3 mùa trước (ILI, hoặc NSSP khi `source` = nssp) | % | TV3 | TV3 tính (`season_milestones.parquet`), TV2 ghép; trống khi TV3 chưa giao |
| `onset_week` | float64 | 24.1 | Tuần khởi phát mùa: tuần đầu của 3 tuần liên tiếp ≥ mức nền; từ 2016-17 tuần đó phải có xét nghiệm dương tính ≥ 2% (thiếu thì lấy trung vị vùng HHS). Ngày tương ứng: `onset_date` trong `season_milestones.parquet` | tuần trong mùa (1 = MMWR 40) | TV3 | TV3 → `season_milestones.parquet` |
| `peak_week` | float64 | 18.5 | Tuần đỉnh mùa (mùa đã kết thúc). Ngày tương ứng: `peak_date` trong `season_milestones.parquet` | tuần trong mùa (1 = MMWR 40) | TV3 | TV3 → `season_milestones.parquet` |
| `peak_value` | float64 | 18.5 | Giá trị đỉnh của tín hiệu dùng tính mốc mùa (ILI hoặc NSSP) | % | TV3 | TV3 → `season_milestones.parquet` |
| `severity` | float64 | 72.2 | Độ nặng của mùa: tỷ lệ nhập viện vì cúm cao nhất mùa (NHSN); chỉ từ mùa 2021-22 | ca/100.000 | TV3 | TV3 → `season_milestones.parquet` |
| `source` | object | 7.5 | Tín hiệu dùng để tính mốc mùa: `ili` (ILINet) hoặc `nssp` (8 bang thiếu ILINet mùa 2025-26) | – | TV3 | TV3 → `season_milestones.parquet` |
| `weeks_in_data` | Int64 | 0.0 | Số tuần của mùa có trong `fact_flu_week` | tuần | phái sinh | đếm tuần theo (bang, mùa) |
| `ili_weeks` | Int64 | 0.0 | Số tuần trong mùa cúm (MMWR 40–20) có `ili_pct` | tuần | phái sinh | roll-up tuần → mùa, chỉ tuần MMWR ≥ 40 hoặc ≤ 20 |
| `ili_mean` | float64 | 8.3 | ILI% trung bình các tuần mùa cúm | % | phái sinh | trung bình cộng `ili_pct` (MMWR 40–20) |
| `ili_max` | float64 | 8.3 | ILI% lớn nhất trong mùa cúm | % | phái sinh | max `ili_pct` (MMWR 40–20) |
| `hosp_weeks` | Int64 | 0.0 | Số tuần mùa cúm có `rate_flu` | tuần | phái sinh | đếm (MMWR 40–20) |
| `hosp_total` | Int64 | 61.1 | Tổng ca nhập viện cúm trong mùa cúm | ca | phái sinh | tổng `hosp_flu` (MMWR 40–20) |
| `rate_flu_cum` | float64 | 61.1 | Tỷ suất nhập viện cộng dồn mùa cúm | ca/100.000 dân | phái sinh | tổng `rate_flu` (MMWR 40–20) |
| `rate_flu_max` | float64 | 61.1 | Tỷ suất nhập viện tuần cao nhất | ca/100.000 dân | phái sinh | max `rate_flu` (MMWR 40–20) |
| `weeks_cdc_high` | Int64 | 61.1 | Số tuần ở mức CDC Cao hoặc Rất cao | tuần | phái sinh | đếm `cdc_level` ≥ 3 (MMWR 40–20) |
| `ah_anomaly_mean` | float64 | 0.0 | Dị thường độ ẩm tuyệt đối trung bình mùa cúm | g/m³ | phái sinh | trung bình `ah_anomaly` (MMWR 40–20) |
| `pm25_mean` | float64 | 0.9 | PM2.5 trung bình mùa cúm | µg/m³ | phái sinh | trung bình `pm25_mean` (MMWR 40–20) |
| `vax_ci_low` | float64 | 6.2 | Cận dưới khoảng tin cậy 95% của độ phủ vaccine | % | `vaccine` (Do phu vaccine cum (FluVaxView)) | tách từ cột `95% CI (%)` của CDC |
| `vax_ci_high` | float64 | 6.2 | Cận trên khoảng tin cậy 95% của độ phủ vaccine | % | `vaccine` (Do phu vaccine cum (FluVaxView)) | tách từ cột `95% CI (%)` của CDC |
| `vax_month` | Int64 | 5.9 | Tháng cuối mùa có số vaccine; khác 5 nghĩa là CDC dừng công bố giữa mùa và `flu_vax_pct` để trống | tháng | `vaccine` (Do phu vaccine cum (FluVaxView)) | `clean/vaccine` |
| `is_current_season` | bool | 0.0 | Mùa đang diễn ra (mùa của tuần mới nhất) | bool | phái sinh | `season` = mùa của tuần cuối trong fact |
