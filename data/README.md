---
pretty_name: FluDataset – US state-level influenza surveillance (raw + processed)
license: other
language:
  - vi
  - en
tags:
  - influenza
  - epidemiology
  - public-health
  - time-series
size_categories:
  - 10K<n<100K
configs:
  - config_name: state_week
    data_files: samples/state_week_sample.csv.gz
    default: true
  - config_name: cdc_level_state_week
    data_files: samples/cdc_level_state_week.csv.gz
  - config_name: wval_state_week
    data_files: samples/wval_state_week.csv.gz
  - config_name: vaccine_state_season
    data_files: samples/vaccine_state_season.csv
  - config_name: cdc_level_thresholds
    data_files: reference/cdc_level_thresholds.csv
  - config_name: weather_state_week
    data_files: samples/weather_state_week.csv.gz
  - config_name: epa_pm25_state_week
    data_files: samples/epa_pm25_state_week.csv.gz
  - config_name: holidays
    data_files: reference/holidays.csv
  - config_name: cities
    data_files: reference/cities.csv
---

# FluDataset

Dữ liệu giám sát cúm mùa theo bang × tuần MMWR ở Mỹ (50 bang + DC), dùng cho project dashboard cảnh báo sớm mùa cúm (môn Quản trị dữ liệu và trực quan hóa).

*US state × MMWR-week influenza surveillance data (ILINet, NHSN, NSSP, wastewater, weather, PM2.5, vaccination, population), raw snapshots plus joined tables.*

Bản chụp: 01–04/11/2026 (thời tiết 236 thành phố hoàn tất 04/11/2026). Mọi bảng trong `samples/` dùng định nghĩa và ngưỡng **tạm** của nhóm. Đây là bảng thử, chưa phải bản phát hành cuối.

## Cấu trúc

```
raw/<nguồn>/<YYYY-MM-DD>/   dữ liệu gốc, lưu nguyên trạng (ngày = ngày tải)
raw/manifest.jsonl          nguồn gốc từng file: url, thời điểm tải, kích thước, sha256, mã HTTP
                            ("manual" = nhóm tải tay bằng trình duyệt)
raw/blocked_<ngày>.json     các URL script không tải được (HTTP 403)
reference/                  bảng tra cứu: ngưỡng mức độ CDC, thành phố đo thời tiết, tuần nghỉ lễ
samples/                    bảng đã ghép và làm sạch thử
```

## Nguồn dữ liệu

| Thư mục `raw/` | Nguồn | Cách lấy | Đơn vị |
| --- | --- | --- | --- |
| `fluview_ilinet`, `nhsn`, `nssp`, `fluview_resp_lab_clinical`, `flusurv`, `nwss`, `delphi_meta` | CDC qua [Delphi Epidata API V5](https://cmu-delphi.github.io/delphi-epidata/api/v5.html) | Script, gồm cả lịch sử phiên bản (`archive__*`) | Bang × tuần; NWSS theo điểm lấy mẫu |
| `cdc_wastewater_wval` | CDC NWSS – Wastewater Viral Activity Level | Tải tay | Điểm lấy mẫu × tuần |
| `cdc_fluvax_coverage` | CDC FluVaxView – Influenza Vaccination Coverage, 6+ months | Tải tay | Bang × mùa × tháng |
| `cdc_nhsn_hrd` | CDC NHSN – Hospital Respiratory Data | Tải tay | Bang × tuần |
| `cdc_nhsn_levels` | CDC NHSN – Admission Levels and Rates | Tải tay | Bang × tuần |
| `cdc_methods` | Trang phương pháp HRD của CDC (bảng ngưỡng mức độ) | Script | – |
| `fluvaxview_pages` | Các trang FluVaxView theo mùa | Script | – |
| `census_popest_state`, `census_popest_places` | US Census Bureau, Vintage 2025 | Tải tay | Bang, đô thị × năm |
| `census_gazetteer` | US Census Bureau, Gazetteer 2024 (places) | Tải tay | Tọa độ đô thị |
| `population` | Bảng dân số 2020 của Delphi | Script | Bang |
| `openmeteo_weather`, `openmeteo_pm25` | [Open-Meteo](https://open-meteo.com/) Historical Weather và Air Quality | Script | Thành phố lớn nhất mỗi bang, ngày / giờ |
| `openmeteo_weather_cities`, `openmeteo_pm25_cities` | Open-Meteo, như trên | Script | Các thành phố còn lại trong `reference/cities.csv` |
| `epa_airdata` | EPA AirData, PM2.5 (88101) theo ngày, 2010–2026 | Script | Trạm × ngày |

## Bảng đã xử lý (`samples/`)

| File | Một dòng là | Cột chính |
| --- | --- | --- |
| `state_week_sample.csv.gz` | bang × tuần | `ili_pct`, `num_ili`, `num_patients`, `hosp_flu`, `rate_flu`, `ed_pct_flu`, `lab_pct_pos`, `temp_mean`, `abs_humidity`, `pm25_mean`, `season` |
| `cdc_level_state_week.csv.gz` | bang × tuần | `rate_flu`, `level` (0 = Very Low … 4 = Very High, tính từ ngưỡng CDC) |
| `wval_state_week.csv.gz` | bang × tuần | `wval` (WVAL cúm A, trung bình có trọng số dân số phục vụ), `sites` |
| `vaccine_state_season.csv` | bang × mùa | `est` (% độ phủ ≥6 tháng, tháng cuối mùa) |
| `epa_pm25_state_week.csv.gz` | bang × tuần | `epa_pm25_mean` (trung bình các trạm EPA trong bang), `epa_sites`; 2010 đến 6/2026 |
| `weather_state_week.csv.gz` | bang × tuần | `temp_mean`, `abs_humidity`, `pm25_mean`, `pm25_max`, trung bình có trọng số dân số các thành phố; `n_cities` |

## Bảng tra cứu (`reference/`)

| File | Nội dung |
| --- | --- |
| `cdc_level_thresholds.csv` | Ngưỡng mức độ nhập viện của CDC theo bang × virus (cận trên của Very Low, Low, Moderate, High), tách từ trang phương pháp HRD |
| `cities.csv` | 236 đô thị (tối đa 5 mỗi bang, cách nhau ≥ 40 km) với tọa độ Gazetteer, dân số 2025 và trọng số; `large_area = 1` khi đô thị rộng hơn 500 dặm² nên tâm có thể xa khu dân cư |
| `cities_largest_per_state.csv` | Danh sách cũ, 1 thành phố mỗi bang, tọa độ nhập tay |
| `holidays.csv` | 992 tuần MMWR 2010–2028: `holiday_week` (Thanksgiving, Giáng sinh, Năm mới), `winter_break` (tạm: từ 18/12 đến 1/1), `weeks_to_holiday` |

## Hạn chế đã biết

- ILINet thiếu AK, CT, HI, NY, OK, OR, SD, UT từ 04/10/2025 đến 03/10/2026.
- Các tín hiệu NHSN, NSSP và ILINet bị sửa về sau ở khoảng 2/3 số điểm dữ liệu. Bảng `samples/` dùng bản mới nhất, không phải bản lúc công bố.
- `weather_state_week` có cột `n_cities` cho biết số thành phố thực có trong tuần đó. DC, HI và RI chỉ có 1 đô thị theo quy tắc chọn.
- Các file tải tay chỉ là bản chụp, không có lịch sử phiên bản.

## Giấy phép và trích dẫn

- Dữ liệu của CDC, US Census Bureau và EPA là dữ liệu của chính phủ liên bang Mỹ, thuộc phạm vi công cộng.
- Dữ liệu qua Delphi Epidata: trích dẫn Delphi Research Group, Carnegie Mellon University theo hướng dẫn của Delphi.
- Dữ liệu Open-Meteo: CC BY 4.0, cần ghi nguồn "Weather data by Open-Meteo.com".

Vì gộp nhiều nguồn có điều khoản khác nhau nên giấy phép chung để là `other`. Khi dùng lại một file, hãy theo điều khoản của nguồn gốc file đó.
