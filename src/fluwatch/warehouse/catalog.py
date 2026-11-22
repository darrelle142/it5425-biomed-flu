"""Danh muc cot (data catalog) cua data/business/: y nghia, don vi, nguon, lineage tung cot.

Mot noi duy nhat mo ta cot -> sinh docs/tu_dien_du_lieu.md (tu dien + lineage) va duoc quality.py (Q06) doi chieu
voi file Parquet that: them cot ma quen mo ta thi bao cao chat luong bao loi.

Moi muc: cot -> (mo ta, don vi, source_id trong dim_source hoac "phai sinh"/"dim"/"TV3", lineage raw -> clean -> business).

Chay: python pipelines/02_warehouse.py --steps docs
"""
import datetime as dt
import re

import pandas as pd

from .business import (AH_CLIMATOLOGY_YEARS, EPA_MIN_SITE_SHARE, EPA_SITE_BASE_YEARS, LAG_COLS, MISSING_FLAGS,
                       NHSN_BASE_YEARS, NHSN_LOW_SHARE, PRELIM_WEEKS, SOURCES, VAX_CARRY_MAX)

DELPHI = "Delphi Epidata V5 `{f}` (file mới nhất) → `clean/{t}`: lọc 50 bang + DC, bỏ trùng (bang, tuần) giữ bản công bố mới nhất, âm → thiếu"

C = {
    # ------------------------------------------------------------------ fact_flu_week
    "fact_flu_week": {
        "state": ("Mã bang 2 chữ viết thường (50 bang + DC)", "–", "dim", "khóa; mã CDC/Delphi → viết thường, bỏ GU, VI, PR, nyc… (`keep_states`)"),
        "week": ("Thứ Bảy kết thúc tuần MMWR (CN–T7)", "ngày", "dim", "khóa; `reference_time` của Delphi / `Week_End` của CDC / ngày quy về thứ Bảy"),
        "epiweek": ("Năm-tuần MMWR dạng YYYYWW", "–", "dim", "tính từ `week` (`mmwr_year_week`), nhận từ `dim_time`"),
        "season": ("Mùa cúm dạng 2024-25, bắt đầu tuần MMWR 40", "–", "dim", "tính từ `week` (`season_of`)"),
        "season_week": ("Thứ tự tuần trong mùa (1 = tuần MMWR 40)", "tuần", "dim", "tính từ `week` (`season_of`)"),
        "ili_pct": ("% lượt khám có hội chứng giống cúm (ILI) trong ILINet", "%", "ilinet", DELPHI.format(f="fluview_ilinet/ili__state", t="ilinet") + "; nhóm tuổi `all`"),
        "num_ili": ("Số lượt khám ILI trong tuần", "lượt", "ilinet", DELPHI.format(f="fluview_ilinet/num_ili__state", t="ilinet") + "; làm tròn số nguyên"),
        "num_patients": ("Tổng lượt khám tại các cơ sở báo cáo ILINet", "lượt", "ilinet", DELPHI.format(f="fluview_ilinet/num_patients__state", t="ilinet")),
        "hosp_flu": ("Ca nhập viện cúm xác nhận trong tuần (NHSN)", "ca", "nhsn", DELPHI.format(f="nhsn/confirmed_admissions_flu_ew__state", t="nhsn")),
        "rate_flu": ("Ca nhập viện cúm / 100.000 dân / tuần (NHSN)", "ca/100.000 dân", "nhsn", DELPHI.format(f="nhsn/confirmed_admissions_flu_per100k_ew__state", t="nhsn")),
        "cdc_level": ("Mức độ nhập viện cúm theo ngưỡng CDC: 0 Very Low … 4 Very High", "0–4", "cdc_thresholds", "phái sinh: so `rate_flu` với ngưỡng của bang trong `reference/cdc_level_thresholds.csv` (cận trên ‘Up to x’ tính ≤)"),
        "ed_pct_flu": ("% lượt cấp cứu do cúm (NSSP)", "%", "nssp", DELPHI.format(f="nssp/pct_ed_visits_influenza__state", t="nssp")),
        "lab_pct_pos": ("% mẫu xét nghiệm lâm sàng dương tính cúm", "%", "lab_clinical", DELPHI.format(f="fluview_resp_lab_clinical/pct_positive__state", t="lab_clinical")),
        "wval": ("Mức virus cúm A trong nước thải (WVAL), trung vị có trọng số dân số phục vụ các trạm trong bang", "không đơn vị (1 = mức nền)", "wval", "CDC `atcp-73re` (mọi lần tải, mỗi tuần giữ bản mới nhất) → `clean/wval`: chỉ cúm A, bỏ trạm WVAL > 1000 (sai miền), chặn trần 100 cho trạm 100–1000, trung vị có trọng số `Population_Served`"),
        "temp_mean": ("Nhiệt độ trung bình tuần, có trọng số dân số 3–5 đô thị", "°C", "weather", "Open-Meteo theo ngày từng đô thị (`reference/cities.csv`) → trung bình tuần → trung bình có trọng số dân số (`clean/weather`)"),
        "abs_humidity": ("Độ ẩm tuyệt đối trung bình tuần", "g/m³", "weather", "Open-Meteo nhiệt độ + độ ẩm tương đối theo ngày → công thức Magnus → trung bình tuần → trọng số dân số (`clean/weather`)"),
        "ah_anomaly": ("Độ ẩm tuyệt đối trừ trung bình nhiều năm cùng bang, cùng tuần MMWR (loại mùa vụ)", "g/m³", "phái sinh", f"`abs_humidity` − trung bình cùng (bang, tuần MMWR) các năm {AH_CLIMATOLOGY_YEARS[0]}–{AH_CLIMATOLOGY_YEARS[1]}; tuần 53 dùng trung bình tuần 52"),
        "pm25_mean": ("PM2.5 trung bình tuần, **ghép hai nguồn** (EPA, thiếu thì Open-Meteo), có số đến tuần hiện tại: **dùng để hiển thị** (dashboard; đoạn Open-Meteo vẽ khác, theo `pm25_source`). **Phân tích, hồi quy dùng `pm25_epa`**, biến trễ cũng tự tính từ `pm25_epa` (không dùng `pm25_mean_lag*`, vì năm 2026 cũng là số ghép). Hai nguồn lệch thang đo: Open-Meteo là số mô hình CAMS, cao hơn EPA ~25%, tương quan 0,55; ở các đợt khói cháy rừng chỉ bằng khoảng nửa EPA", "µg/m³", "epa", "`pm25_epa`, ô trống thì lấy `pm25_om`; nguồn ghi ở `pm25_source`"),
        "flu_vax_pct": ("Độ phủ vaccine cúm ≥ 6 tháng tuổi của mùa (tháng cuối mùa có số)", "% dân số", "vaccine", "CDC `vh55-3he6` → `clean/vaccine`: lấy tháng 5 (cuối mùa) → gán cho mọi tuần của mùa; mùa CDC dừng công bố trước tháng 5 (CA, MS 2013-14; DC 2017-18) để trống vì độ phủ là số cộng dồn, số giữa mùa thấp hơn thật (xem `fact_season_summary.vax_month`). **Chú ý**: là số cuối mùa, không dùng làm biến dự báo các tuần đầu mùa (dùng `flu_vax_pct_prev`)"),
        "holiday_week": ("Tuần có Lễ Tạ ơn, Giáng sinh hoặc Năm mới", "0/1", "holidays", "`reference/holidays.csv` (nhóm tự lập) qua `dim_time`"),
        "winter_break": ("Tuần nằm trong kỳ nghỉ đông (tạm: 18/12 – 1/1)", "0/1", "holidays", "`reference/holidays.csv` qua `dim_time`"),
        "weeks_to_holiday": ("Số tuần đến tuần lễ gần nhất phía trước", "tuần", "holidays", "`reference/holidays.csv` qua `dim_time`"),
        "is_preliminary": (f"Số liệu sơ bộ: {PRELIM_WEEKS} tuần gần nhất, CDC còn sửa", "bool", "phái sinh", f"`week` > tuần cuối − {PRELIM_WEEKS} tuần (tuần cuối = tuần mới nhất của ILINet/NHSN/NSSP)"),
        "mmwr_year": ("Năm MMWR (năm của ngày thứ Tư trong tuần)", "năm", "dim", "tính từ `week`"),
        "mmwr_week": ("Tuần MMWR 1–53", "tuần", "dim", "tính từ `week`"),
        "num_providers": ("Số cơ sở báo cáo ILINet trong tuần", "cơ sở", "ilinet", DELPHI.format(f="fluview_ilinet/num_providers__state", t="ilinet")),
        "hosp_reporting": ("Số bệnh viện báo cáo NHSN trong tuần", "bệnh viện", "nhsn", DELPHI.format(f="nhsn/hosprep_confirmed_admissions_flu_ew__state", t="nhsn")),
        "low_reporting": (f"Cờ: số bệnh viện báo cáo NHSN tuần này < {int(NHSN_LOW_SHARE * 100)}% mức thường của bang → `rate_flu`, `hosp_flu`, `cdc_level` thấp giả tạo (báo cáo tự nguyện 5–10/2024, giai đoạn khởi động 2020–2021); nên loại khi huấn luyện/đánh giá", "bool", "nhsn", f"`hosp_reporting` < {NHSN_LOW_SHARE} × trung vị `hosp_reporting` của bang các năm {NHSN_BASE_YEARS[0]}–{NHSN_BASE_YEARS[1]}"),
        "beds_flu_pct": ("% giường nội trú có bệnh nhân cúm", "%", "nhsn", DELPHI.format(f="nhsn/inpatient_beds_flu_pct_ew__state", t="nhsn")),
        "cdc_level_name": ("Tên mức CDC: rat_thap, thap, trung_binh, cao, rat_cao", "–", "phái sinh", "ánh xạ từ `cdc_level`"),
        "ed_pct_covid": ("% lượt cấp cứu do COVID-19 (NSSP)", "%", "nssp", DELPHI.format(f="nssp/pct_ed_visits_covid__state", t="nssp")),
        "lab_specimens": ("Số mẫu xét nghiệm lâm sàng trong tuần", "mẫu", "lab_clinical", DELPHI.format(f="fluview_resp_lab_clinical/total_specimens__state", t="lab_clinical")),
        "flusurv_rate": ("Tỷ suất nhập viện cúm FluSurv-NET (chỉ các bang tham gia)", "ca/100.000 dân", "flusurv", DELPHI.format(f="flusurv/rate_overall__state", t="flusurv")),
        "wval_sites": ("Số trạm nước thải góp vào `wval` trong tuần", "trạm", "wval", "đếm trạm sau khi bỏ trạm sai miền (`clean/wval`)"),
        "wval_sites_extreme": ("Số trạm bị bỏ vì WVAL > 1000 (sai miền)", "trạm", "wval", "đếm trong `clean/wval`, có ghi `_clean_log.json`"),
        "wval_sites_capped": ("Số trạm có WVAL 100–1000 bị chặn trần ở 100", "trạm", "wval", "đếm trong `clean/wval`, có ghi `_clean_log.json`"),
        "wval_mean": ("WVAL trung bình có trọng số dân số phục vụ (nhạy hơn `wval` ở mức thấp, vì trung vị hay dính ở 1)", "không đơn vị", "wval", "như `wval` nhưng lấy trung bình có trọng số thay cho trung vị (`clean/wval.wval_mean`)"),
        "flu_vax_pct_prev": ("Độ phủ vaccine cuối mùa **trước** (đã biết từ đầu mùa này): dùng cột này làm biến dự báo", "% dân số", "vaccine", f"`clean/vaccine.flu_vax_pct` của mùa trước, ghép theo (bang, mùa); mùa trước CDC không công bố thì mượn mùa gần nhất có số (tối đa {VAX_CARRY_MAX} mùa), đánh dấu ở `vax_prev_carried`"),
        "vax_prev_carried": ("`flu_vax_pct_prev` là số **mượn** từ mùa cũ hơn (mùa trước không có số)", "bool", "phái sinh", f"True khi mùa trước trống mà lùi ≤ {VAX_CARRY_MAX} mùa nữa có số (vd. MS 2026-27 mượn 2024-25)"),
        "pm25_max": ("PM2.5 theo giờ lớn nhất trong tuần (Open-Meteo), có trọng số dân số", "µg/m³", "weather", "Open-Meteo theo giờ → max tuần từng đô thị → trọng số dân số (`clean/weather.pm25_om_max`)"),
        "pm25_epa": ("PM2.5 trung bình tuần chỉ từ EPA AirData 88101 (một thước đo xuyên suốt 2010 → 5/2026): dùng cột này cho hồi quy", "µg/m³", "epa", f"`clean/epa_pm25.epa_pm25_mean` (trung bình các trạm trong bang); trong năm mới nhất của EPA (file công bố dở), tuần có `epa_sites` < {int(EPA_MIN_SITE_SHARE * 100)}% trung vị {EPA_SITE_BASE_YEARS[0]}–{EPA_SITE_BASE_YEARS[1]} của bang thì để trống"),
        "pm25_om": ("PM2.5 trung bình tuần chỉ từ Open-Meteo (mô hình CAMS, có đến tuần hiện tại), có trọng số dân số", "µg/m³", "weather", "Open-Meteo theo giờ → trung bình tuần từng đô thị → trọng số dân số (`clean/weather.pm25_om_mean`)"),
        "pm25_source": ("Nguồn của `pm25_mean`: epa hoặc openmeteo", "–", "phái sinh", "`epa` nếu `pm25_epa` có số, không thì `openmeteo`"),
        "epa_sites": ("Số trạm EPA có số PM2.5 trong tuần (kể cả tuần bị bỏ vì thiếu trạm)", "trạm", "epa", "đếm trạm trong `clean/epa_pm25`"),
        "n_cities": ("Số đô thị có số thời tiết trong tuần (1–5)", "đô thị", "weather", "đếm trong `clean/weather`"),
        "wow_pct": ("% thay đổi `rate_flu` so với tuần trước", "%", "phái sinh", "(`rate_flu` − `rate_flu_lag1`) / `rate_flu_lag1` × 100; trống khi tuần trước = 0"),
        "yoy_pct": ("% thay đổi `rate_flu` so với cùng `season_week` mùa trước", "%", "phái sinh", "như `wow_pct`, mẫu số là cùng tuần trong mùa của mùa trước"),
        "ili_wow_pct": ("% thay đổi `ili_pct` so với tuần trước", "%", "phái sinh", "như `wow_pct` với `ili_pct`"),
        "ili_yoy_pct": ("% thay đổi `ili_pct` so với cùng `season_week` mùa trước", "%", "phái sinh", "như `yoy_pct` với `ili_pct`"),
        "issue_date": ("Ngày công bố mới nhất của các tín hiệu Delphi trong dòng", "ngày", "phái sinh", "max(`report_time`) của ILINet, NHSN, NSSP, xét nghiệm, FluSurv; dùng để biết dòng đã bị CDC sửa khi nào"),
    },
    # ------------------------------------------------------------------ fact_season_summary
    "fact_season_summary": {
        "state": ("Mã bang", "–", "dim", "khóa"),
        "season": ("Mùa cúm (2024-25)", "–", "dim", "khóa"),
        "flu_vax_pct": ("Độ phủ vaccine cúm ≥ 6 tháng, tháng cuối mùa có số", "% dân số", "vaccine", "`clean/vaccine` (xem `fact_flu_week.flu_vax_pct`)"),
        "baseline": ("Mức nền ILI kiểu CDC của bang × mùa", "%", "TV3", "TV3 tính (`season_milestones.parquet`), TV2 ghép; trống khi TV3 chưa giao"),
        "onset_week": ("Tuần khởi phát mùa (3 tuần liên tiếp ≥ mức nền)", "ngày", "TV3", "TV3 → `season_milestones.parquet`"),
        "peak_week": ("Tuần đỉnh mùa", "ngày", "TV3", "TV3 → `season_milestones.parquet`"),
        "peak_value": ("Giá trị đỉnh", "% hoặc ca/100.000", "TV3", "TV3 → `season_milestones.parquet`"),
        "severity": ("Mức độ nặng của mùa", "–", "TV3", "TV3 → `season_milestones.parquet`"),
        "source": ("Tín hiệu dùng để tính mốc mùa (ILINet hoặc NSSP)", "–", "TV3", "TV3 → `season_milestones.parquet`"),
        "weeks_in_data": ("Số tuần của mùa có trong `fact_flu_week`", "tuần", "phái sinh", "đếm tuần theo (bang, mùa)"),
        "ili_weeks": ("Số tuần trong mùa cúm (MMWR 40–20) có `ili_pct`", "tuần", "phái sinh", "roll-up tuần → mùa, chỉ tuần MMWR ≥ 40 hoặc ≤ 20"),
        "ili_mean": ("ILI% trung bình các tuần mùa cúm", "%", "phái sinh", "trung bình cộng `ili_pct` (MMWR 40–20)"),
        "ili_max": ("ILI% lớn nhất trong mùa cúm", "%", "phái sinh", "max `ili_pct` (MMWR 40–20)"),
        "hosp_weeks": ("Số tuần mùa cúm có `rate_flu`", "tuần", "phái sinh", "đếm (MMWR 40–20)"),
        "hosp_total": ("Tổng ca nhập viện cúm trong mùa cúm", "ca", "phái sinh", "tổng `hosp_flu` (MMWR 40–20)"),
        "rate_flu_cum": ("Tỷ suất nhập viện cộng dồn mùa cúm", "ca/100.000 dân", "phái sinh", "tổng `rate_flu` (MMWR 40–20)"),
        "rate_flu_max": ("Tỷ suất nhập viện tuần cao nhất", "ca/100.000 dân", "phái sinh", "max `rate_flu` (MMWR 40–20)"),
        "weeks_cdc_high": ("Số tuần ở mức CDC Cao hoặc Rất cao", "tuần", "phái sinh", "đếm `cdc_level` ≥ 3 (MMWR 40–20)"),
        "ah_anomaly_mean": ("Dị thường độ ẩm tuyệt đối trung bình mùa cúm", "g/m³", "phái sinh", "trung bình `ah_anomaly` (MMWR 40–20)"),
        "pm25_mean": ("PM2.5 trung bình mùa cúm", "µg/m³", "phái sinh", "trung bình `pm25_mean` (MMWR 40–20)"),
        "vax_ci_low": ("Cận dưới khoảng tin cậy 95% của độ phủ vaccine", "%", "vaccine", "tách từ cột `95% CI (%)` của CDC"),
        "vax_ci_high": ("Cận trên khoảng tin cậy 95% của độ phủ vaccine", "%", "vaccine", "tách từ cột `95% CI (%)` của CDC"),
        "vax_month": ("Tháng cuối mùa có số vaccine; khác 5 nghĩa là CDC dừng công bố giữa mùa và `flu_vax_pct` để trống", "tháng", "vaccine", "`clean/vaccine`"),
        "is_current_season": ("Mùa đang diễn ra (mùa của tuần mới nhất)", "bool", "phái sinh", "`season` = mùa của tuần cuối trong fact"),
    },
    # ------------------------------------------------------------------ dim_state
    "dim_state": {
        "state": ("Mã bang 2 chữ viết thường", "–", "population", "khóa; 50 bang + DC"),
        "state_name": ("Tên bang", "–", "population", "`raw/population/state_pop_2020_delphi`"),
        "hhs_region": ("Vùng HHS 1–10", "–", "dim", "bảng cố định HHS (`common.HHS_REGION`)"),
        "hhs_region_name": ("Tên vùng HHS", "–", "dim", "‘Vung ’ + số vùng"),
        "country": ("Quốc gia (us), cấp trên cùng để roll-up", "–", "dim", "hằng"),
        "population": ("Dân số 2020", "người", "population", "`raw/population/state_pop_2020_delphi.csv`"),
        "contiguous": ("Thuộc 48 bang lục địa + DC (không gồm AK, HI)", "bool", "dim", "hằng"),
        "lat": ("Vĩ độ trọng tâm dân số (các đô thị đo thời tiết)", "độ", "dim", "trung bình có trọng số dân số các đô thị trong `reference/cities.csv`"),
        "lon": ("Kinh độ trọng tâm dân số", "độ", "dim", "như `lat`"),
        "cluster_id": ("Cụm bang theo hình dạng đường cong mùa (TV3)", "–", "TV3", "TV3 → `state_cluster.parquet`, TV2 ghép; trống khi chưa giao"),
    },
    # ------------------------------------------------------------------ dim_time
    "dim_time": {
        "week": ("Thứ Bảy kết thúc tuần MMWR", "ngày", "dim", "khóa; từ 2010-01-02 đến hết năm sau tuần cuối có số"),
        "epiweek": ("Năm-tuần MMWR YYYYWW", "–", "dim", "tính từ `week`"),
        "mmwr_year": ("Năm MMWR", "năm", "dim", "năm của ngày thứ Tư trong tuần"),
        "mmwr_week": ("Tuần MMWR 1–53", "tuần", "dim", "tuần 1 là tuần CN–T7 chứa ngày 4/1"),
        "week_start": ("Chủ nhật đầu tuần", "ngày", "dim", "`week` − 6 ngày"),
        "week_end": ("Thứ Bảy cuối tuần (= `week`)", "ngày", "dim", "= `week`"),
        "season": ("Mùa cúm (bắt đầu tuần MMWR 40)", "–", "dim", "`season_of`"),
        "season_week": ("Tuần trong mùa (1 = tuần MMWR 40)", "tuần", "dim", "`season_of`"),
        "year": ("Năm dương lịch của `week`", "năm", "dim", "tính từ `week`"),
        "month": ("Tháng dương lịch của `week`", "tháng", "dim", "tính từ `week`"),
        "in_flu_season": ("Thuộc mùa cúm CDC theo dõi (tuần MMWR 40–20)", "bool", "dim", "`mmwr_week` ≥ 40 hoặc ≤ 20"),
        "holiday_week": ("Tuần có lễ lớn", "0/1", "holidays", "`reference/holidays.csv`"),
        "holiday_name": ("Tên lễ (Thanksgiving, Christmas, New Year)", "–", "holidays", "`reference/holidays.csv`"),
        "winter_break": ("Tuần nghỉ đông (tạm)", "0/1", "holidays", "`reference/holidays.csv`"),
        "weeks_to_holiday": ("Số tuần đến tuần lễ gần nhất", "tuần", "holidays", "`reference/holidays.csv`"),
    },
    # ------------------------------------------------------------------ dim_source
    "dim_source": {
        "source_id": ("Mã nguồn", "–", "dim", "khóa; khai báo tay trong `business.SOURCES`"),
        "source_name": ("Tên nguồn", "–", "dim", "khai báo tay"),
        "provider": ("Đơn vị cung cấp / đường lấy", "–", "dim", "khai báo tay"),
        "access": ("Cách truy cập (API, GitHub Actions, file…)", "–", "dim", "khai báo tay"),
        "dataset_id": ("Mã bộ dữ liệu ở nguồn", "–", "dim", "khai báo tay"),
        "raw_path": ("Thư mục dữ liệu thô", "–", "dim", "khai báo tay"),
        "clean_table": ("Bảng trong `data/clean/`", "–", "dim", "khai báo tay; Q04 kiểm tra tồn tại"),
        "fact_columns": ("Các cột business lấy từ nguồn này", "–", "dim", "khai báo tay; Q04 kiểm tra tồn tại"),
        "unit": ("Đơn vị", "–", "dim", "khai báo tay"),
        "frequency": ("Tần suất", "–", "dim", "khai báo tay"),
        "geo_level": ("Cấp địa lý gốc", "–", "dim", "khai báo tay"),
        "revised": ("Nguồn có sửa số liệu cũ không", "bool", "dim", "khai báo tay"),
        "update_rule": ("Quy tắc cập nhật", "–", "dim", "khai báo tay (xem `docs/quan_tri_du_lieu.md`)"),
        "license": ("Giấy phép", "–", "dim", "khai báo tay"),
        "owner": ("Người phụ trách thu thập (owner)", "–", "dim", "khai báo tay"),
        "steward": ("Người làm sạch, đưa vào kho (steward)", "–", "dim", "khai báo tay"),
        "users": ("Thành viên dùng nguồn này", "–", "dim", "khai báo tay"),
        "first_period": ("Kỳ đầu tiên trong `clean/`", "ngày/mùa", "dim", "đọc `_clean_log.json`"),
        "last_period": ("Kỳ cuối cùng trong `clean/`", "ngày/mùa", "dim", "đọc `_clean_log.json`"),
        "raw_files": ("Các file raw đã đọc (tối đa 3)", "–", "dim", "đọc `_clean_log.json`"),
        "built_at": ("Thời điểm dựng", "thời điểm", "dim", "lúc chạy"),
    },
}

_LAG_RE = re.compile(r"^(?P<col>.+)_lag(?P<k>\d+)$")
_MISS = {flag: col for flag, col in MISSING_FLAGS.items()}


def describe(table, col):
    """(mo ta, don vi, nguon, lineage) cua mot cot; None neu chua co trong danh muc."""
    t = C.get(table, {})
    if col in t:
        return t[col]
    if table == "fact_flu_week":
        m = _LAG_RE.match(col)
        if m and m["col"] in LAG_COLS and int(m["k"]) <= LAG_COLS[m["col"]]:
            base = t.get(m["col"], ("", "", "", ""))
            return (f"Giá trị `{m['col']}` của {m['k']} tuần trước, cùng bang (biến trễ)", base[1], "phái sinh",
                    f"`{m['col']}` của tuần `week` − {m['k']} tuần (khung bang × tuần đầy đủ nên shift = đúng tuần)")
        if col in _MISS:
            return (f"Cờ: `{_MISS[col]}` bị thiếu ở dòng này", "bool", "phái sinh", f"`{_MISS[col]}` là NA")
    return None


def missing_entries(tables):
    """Cot co trong Parquet ma chua co mo ta, va mo ta ma khong con cot (de Q06 bao)."""
    out = []
    for t, df in tables.items():
        if t not in C:
            continue
        for col in df.columns:
            if describe(t, col) is None:
                out.append((t, col, "cot chua co trong tu dien"))
        for col in C[t]:
            if col not in df.columns:
                out.append((t, col, "tu dien co, bang khong co"))
    return out


# ============================== Sinh tai lieu ==============================

TABLE_INFO = {
    "fact_flu_week": ("Bảng sự kiện chính: một dòng là một bang × một tuần MMWR (51 bang × mọi tuần từ 2010-01-02).",
                      "(state, week)"),
    "fact_season_summary": ("Bảng sự kiện theo mùa: một dòng là một bang × một mùa (roll-up tuần → mùa, vaccine, "
                            "mốc mùa của TV3).", "(state, season)"),
    "dim_state": ("Chiều địa lý: bang → vùng HHS → toàn quốc.", "state"),
    "dim_time": ("Chiều thời gian: tuần → tháng → năm, tuần → mùa; có nghỉ lễ.", "week"),
    "dim_source": ("Chiều nguồn dữ liệu: metadata quản trị (người phụ trách, quy tắc cập nhật, giấy phép).",
                   "source_id"),
}


def _esc(s):
    return str(s).replace("|", "\\|").replace("\n", " ")


def build_docs(paths):
    from .load import FLU_WEEK_COLS
    from .quality import BIZ_TABLES, load_business
    tables = load_business(paths)
    src = {s["source_id"]: s["source_name"] for s in SOURCES}
    p = ["# Từ điển dữ liệu và lineage", "",
         "> 📍 [Mục lục tài liệu](README.md) · Quản trị dữ liệu: [quan_tri_du_lieu.md](quan_tri_du_lieu.md) · "
         "Chất lượng: [reports/data_quality/README.md](../reports/data_quality/README.md)", "",
         f"Sinh tự động bởi `python pipelines/02_warehouse.py --steps docs` lúc {dt.datetime.now():%Y-%m-%d %H:%M} "
         "từ `src/fluwatch/warehouse/catalog.py` và các file `data/business/*.parquet` thật (kiểu, % thiếu). "
         "Muốn sửa mô tả thì sửa `catalog.py` rồi chạy lại; quy tắc chất lượng Q06 báo lỗi khi có cột chưa được mô tả.", "",
         "**Cách đọc cột Lineage**: `raw/<nguồn>` (dữ liệu gốc, giữ nguyên) → `clean/<bảng>` (chuẩn hóa từng nguồn) → "
         "`business/` (ghép theo khóa bang × tuần). Cột *Nguồn* trỏ tới `source_id` trong `dim_source` "
         "(xem [quan_tri_du_lieu.md](quan_tri_du_lieu.md)); *phái sinh* là cột TV2 tính trong `business.py`; "
         "*dim* là khóa hoặc thuộc tính chiều; *TV3* là cột do TV3 giao.", "",
         "Cột đánh dấu ★ thuộc hợp đồng dữ liệu (`docs/ke_hoach.md` mục 4.1): không đổi tên, không bỏ.", ""]
    for t in BIZ_TABLES:
        df = tables[t]
        info, key = TABLE_INFO[t]
        p += [f"## `{t}`", "", f"{info} Khóa chính: `{key}`. {len(df):,} dòng × {df.shape[1]} cột.".replace(",", "."), "",
              "| Cột | Kiểu | % thiếu | Ý nghĩa | Đơn vị | Nguồn | Lineage / phép biến đổi |",
              "| --- | --- | --- | --- | --- | --- | --- |"]
        lag_done = set()
        for col in df.columns:
            d = describe(t, col) or ("**(chưa mô tả)**", "", "", "")
            m = _LAG_RE.match(col)
            if t == "fact_flu_week" and m and m["col"] in LAG_COLS:     # gop bien tre cho gon
                if m["col"] in lag_done:
                    continue
                lag_done.add(m["col"])
                k = LAG_COLS[m["col"]]
                names = ", ".join(f"`{m['col']}_lag{i}`" for i in range(1, k + 1))
                na = df[[f"{m['col']}_lag{i}" for i in range(1, k + 1)]].isna().mean().mean() * 100
                p.append(f"| {names} | {df[col].dtype} | {na:.1f} | Giá trị `{m['col']}` của 1…{k} tuần trước, cùng bang "
                         f"| {_esc(d[1])} | phái sinh | `{m['col']}` của tuần `week` − k |")
                continue
            star = " ★" if t == "fact_flu_week" and col in FLU_WEEK_COLS else ""
            na = df[col].isna().mean() * 100
            s = d[2]
            s_txt = f"`{s}` ({src[s]})" if s in src else s
            p.append(f"| `{col}`{star} | {df[col].dtype} | {na:.1f} | {_esc(d[0])} | {_esc(d[1])} | {_esc(s_txt)} | "
                     f"{_esc(d[3])} |")
        p.append("")
    out = paths.root / "docs" / "tu_dien_du_lieu.md"
    out.write_text("\n".join(p), encoding="utf-8")
    return [out] + _fill_owners(paths, tables["dim_source"])


BEGIN, END = "<!-- BEGIN dim_source (sinh tu dong, khong sua tay) -->", "<!-- END dim_source -->"


def _fill_owners(paths, ds):
    """Chep bang nguoi phu trach tu dim_source vao giua 2 dong danh dau cua docs/quan_tri_du_lieu.md."""
    f = paths.root / "docs" / "quan_tri_du_lieu.md"
    if not f.exists():
        return []
    txt = f.read_text(encoding="utf-8")
    if BEGIN not in txt or END not in txt:
        return []
    rows = ["| Nguồn (`source_id`) | Cung cấp | Owner | Steward | Users | Có sửa số cũ | Quy tắc cập nhật | Kỳ có trong `clean/` |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for r in ds.itertuples():
        per = f"{r.first_period} → {r.last_period}" if pd.notna(r.first_period) and r.first_period else "–"
        rows.append(f"| {_esc(r.source_name)} (`{r.source_id}`) | {_esc(r.provider)} | {r.owner} | {r.steward} | "
                    f"{_esc(getattr(r, 'users', ''))} | {'có' if r.revised else 'không'} | {_esc(r.update_rule)} | {per} |")
    head, rest = txt.split(BEGIN, 1)
    _, tail = rest.split(END, 1)
    f.write_text(head + BEGIN + "\n" + "\n".join(rows) + "\n" + END + tail, encoding="utf-8")
    return [f]
