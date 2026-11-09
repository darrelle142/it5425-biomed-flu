# Dashboard giám sát và cảnh báo sớm mùa cúm theo bang ở Mỹ

Project môn Quản trị dữ liệu và trực quan hóa. Dashboard theo tuần MMWR cho 50 bang + DC, giúp cán bộ y tế biết mùa cúm năm nay bắt đầu khi nào, lên đỉnh lúc nào, nặng đến đâu, bang nào lên trước và cần chuẩn bị gì.

## Câu hỏi nghiên cứu

| RQ | Câu hỏi |
| --- | --- |
| RQ1 | Mùa cúm năm nay đã bắt đầu chưa, đang ở giai đoạn nào? |
| RQ2 | So với các mùa trước, năm nay đến sớm hay muộn, nhẹ hay nặng? |
| RQ3 | Bang nào lên dịch sớm nhất, nhanh nhất; bang nào giống nhau; cúm lan từ đâu sang đâu? |
| RQ4 | Yếu tố nào (độ ẩm tuyệt đối, PM2.5, vaccine, kỳ nghỉ lễ) đi kèm mùa cúm sớm hoặc nặng hơn, trễ bao nhiêu tuần? |
| RQ5 | 1–4 tuần tới có vượt ngưỡng báo động không, và cần chuẩn bị gì? |

Kế hoạch chi tiết: [`docs/ke_hoach_v2.docx`](docs/ke_hoach_v2.docx).

## Cấu trúc thư mục

```
.
├── README.md
├── requirements.txt
├── data/                     dữ liệu (chỉ reference/ được lưu trên GitHub)
│   ├── README.md             thẻ dữ liệu, giống trang Hugging Face
│   ├── reference/            bảng tra cứu nhỏ: ngưỡng CDC, thành phố, ngày lễ   [git]
│   ├── raw/                  dữ liệu gốc theo raw/<nguồn>/<ngày tải>/ + manifest  [Hugging Face]
│   ├── samples/              bảng đã xử lý bang × tuần                            [Hugging Face]
│   └── sandbox/              dữ liệu giả lập (tạo khi cần, không commit)
├── scripts/                  pipeline: crawl, xây bảng, kiểm tra
├── notebooks/                phân tích và mô hình (xem notebooks/README.md)
├── dashboard/                mã hoặc file dashboard
├── reports/                  báo cáo PDF, slide
└── docs/                     kế hoạch, yêu cầu môn học, hạn chế dữ liệu, lịch tải tay
```

Dữ liệu lớn (khoảng 290 MB) nằm trên Hugging Face: [tdu175/FluDataset](https://huggingface.co/datasets/tdu175/FluDataset) (từ 08/11/2026; bản gốc ban đầu ở `DragonbornRay/FluDataset`). GitHub chỉ chứa mã, tài liệu và `data/reference/`.

## Bắt đầu

```bash
pip install -r requirements.txt
python scripts/download_data.py --samples   # chỉ bảng đã xử lý, vài MB: đủ cho notebook và dashboard
python scripts/download_data.py             # toàn bộ, gồm raw/: cần khi chạy lại pipeline
```

Chạy mọi lệnh từ thư mục gốc của repo.

## Pipeline

Hướng dẫn dựng lại dữ liệu khi lỗi, kể cả khi phải dùng VPN: [`docs/ke_hoach_tu_dong_crawl_cdc.md`](docs/ke_hoach_tu_dong_crawl_cdc.md) mục 9.

| Bước | Lệnh | Kết quả |
| --- | --- | --- |
| 1. Crawl tự động | `python scripts/crawl_sample.py delphi` (cả `weather`, `files`) | `raw/` Delphi (ILINet, NHSN, NSSP, FluSurv, xét nghiệm, NWSS), Open-Meteo, file tĩnh |
| 2. Crawl bổ sung | `python scripts/crawl_missing.py` | EPA AirData 2010–2026, trang phương pháp CDC |
| 2b. CDC bị chặn (tự động) | `python scripts/crawl_cdc_us.py` (GitHub Actions chạy mỗi thứ Bảy) | `raw/` WVAL, vaccine, trang ngưỡng CDC; tự đẩy lên Hugging Face |
| 3. Ghi file tải tay | `python scripts/register_manual.py --by "Tên"` | Thêm file CDC tải tay vào `raw/manifest.jsonl` |
| 4. Bảng tra cứu | `python scripts/build_reference.py` | `reference/cities.csv` (3–5 thành phố mỗi bang), `reference/holidays.csv` |
| 5. Thời tiết 236 thành phố | `python scripts/crawl_cities_weather.py` | `raw/openmeteo_*_cities/` (chạy lại được, tự bỏ qua file đã có) |
| 6. Môi trường | `python scripts/build_environment.py` | `samples/weather_state_week.csv.gz`, `samples/epa_pm25_state_week.csv.gz` |
| 7. Bảng mẫu | `python scripts/profile_sample.py` | `samples/state_week_sample.csv.gz` |
| 8. Ngưỡng CDC | `python scripts/build_thresholds.py` (đọc `state_week_sample`, nên chạy sau bước 7) | `reference/cdc_level_thresholds.csv`, `samples/cdc_level_state_week.csv.gz` |
| 8b. Hồ sơ dữ liệu | `python scripts/profile_extras.py`, `profile_dataset.py` | `samples/wval_state_week`, `vaccine_state_season` |
| 9. Kiểm tra độ đầy đủ | `python scripts/audit_data.py` | `samples/audit_results.json` |

`crawl_cities_weather.py` và `crawl_missing.py` import từ `crawl_sample.py`, nên chạy bằng `python scripts/...` (không dùng `python -I`).

## Nguồn CDC bị chặn từ Việt Nam

`data.cdc.gov` trả lỗi 403 cho máy ở Việt Nam. Nước thải WVAL (hằng tuần), độ phủ vaccine (hằng tháng) và trang ngưỡng CDC được tải tự động bằng GitHub Actions (máy chủ ở Mỹ) qua workflow [`crawl_cdc.yml`](.github/workflows/crawl_cdc.yml), chạy 10:00 sáng thứ Bảy giờ Việt Nam và đẩy thẳng lên Hugging Face. Cần secret `HF_TOKEN` trong repo GitHub. Kế hoạch và các bước cài đặt: [`docs/ke_hoach_tu_dong_crawl_cdc.md`](docs/ke_hoach_tu_dong_crawl_cdc.md).

Nếu workflow báo lỗi (job đỏ), dùng phương án dự phòng: bật VPN Mỹ rồi chạy `python scripts/crawl_cdc_us.py --upload`, hoặc tải bằng trình duyệt theo [`docs/can_tai_tay.txt`](docs/can_tai_tay.txt).

## Cập nhật dữ liệu lên Hugging Face

Sau khi crawl hoặc tải tay, chạy từ thư mục gốc của repo:

```powershell
hf upload tdu175/FluDataset ./data . --repo-type dataset --exclude ".cache/*" --exclude "samples/preview_*" --exclude "samples/*_results.json" --exclude "sandbox/*" --commit-message "Cap nhat du lieu tuan ..."
```

## Hạn chế dữ liệu

Xem [`docs/han_che_du_lieu.md`](docs/han_che_du_lieu.md).

## Phân công

| Người | Vai trò |
| --- | --- |
| 1 | Trưởng nhóm: nghiệp vụ, bảng bằng chứng, quản trị dữ liệu, tổng hợp báo cáo |
| 2 | Data engineer CDC: pipeline Delphi hằng tuần, số liệu theo ngày công bố, tải tay |
| 3 | Data engineer môi trường và tích hợp: star schema, kiểm tra tầng 1, chèn lỗi |
| 4 | Phân tích mùa vụ: mốc mùa, EDA, phân cụm, tương quan trễ (RQ1–RQ3) |
| 5 | Mô hình: kiểm tra phương pháp, Negative Binomial (RQ4), mô hình cảnh báo (RQ5) |
| 6 | Dashboard và storytelling |

## Nguồn và giấy phép dữ liệu

Dữ liệu CDC, Census, EPA thuộc phạm vi công cộng của chính phủ liên bang Mỹ. Dữ liệu qua [Delphi Epidata](https://cmu-delphi.github.io/delphi-epidata/) cần trích dẫn Delphi. Dữ liệu Open-Meteo theo CC BY 4.0. Chi tiết trong [`data/README.md`](data/README.md).
