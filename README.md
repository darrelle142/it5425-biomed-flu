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

Thư viện nằm trong `src/fluwatch/`, lệnh chạy nằm ngoài (`pipelines/`, `scripts/`).

```
.
├── README.md
├── requirements.txt
├── pyproject.toml            gói fluwatch (pip install -e . để dùng trong notebook)
├── src/fluwatch/             thư viện, mỗi thành viên một gói con
│   ├── ingest/               TV1: thu thập, tự động hóa, bảo toàn dữ liệu thô
│   │   ├── paths.py          đường dẫn data/, raw/, manifest (tính từ thư mục gốc của lệnh chạy)
│   │   ├── net.py            tải HTTP; chờ khi bị 429, không thử vượt chặn 403
│   │   ├── store.py          lưu file thô nguyên trạng + ghi manifest, không ghi đè
│   │   ├── delphi.py         Delphi V5: ILINet, NHSN, NSSP, xét nghiệm, FluSurv, NWSS
│   │   ├── openmeteo.py      thời tiết và PM2.5 theo thành phố (lịch sử, cập nhật hằng tuần)
│   │   ├── hf.py             Hugging Face: kế hoạch đẩy lên, sao lưu, tag phiên bản
│   │   └── integrity.py      kiểm tra toàn vẹn manifest ↔ file ↔ Hugging Face
│   ├── warehouse/            TV2: clean/, business/, star schema, chất lượng
│   ├── seasonality/          TV3: mốc mùa, EDA, phân cụm
│   ├── risk_factors/         TV4: giả lập, yếu tố ảnh hưởng
│   ├── alerting/             TV5: mô hình cảnh báo, ROC
│   └── dashboard/            TV6: ứng dụng Streamlit
├── pipelines/                mỗi thành viên một lệnh chạy: 01_ingest.py … 06_dashboard.py
├── scripts/                  lệnh chạy từng bước (crawl, xây bảng, kiểm tra, sao lưu, khôi phục)
├── data/                     dữ liệu (chỉ reference/ được lưu trên GitHub)
│   ├── README.md             thẻ dữ liệu, giống trang Hugging Face
│   ├── reference/            bảng tra cứu nhỏ: ngưỡng CDC, thành phố, ngày lễ   [git]
│   ├── raw/                  dữ liệu gốc theo raw/<nguồn>/<ngày tải>/ + manifest  [Hugging Face]
│   ├── samples/              bảng đã xử lý bang × tuần                            [Hugging Face]
│   └── sandbox/              dữ liệu giả lập (tạo khi cần, không commit)
├── notebooks/                phân tích và mô hình (xem notebooks/README.md)
├── dashboard/                mã hoặc file dashboard
├── reports/                  báo cáo PDF, slide
└── docs/                     kế hoạch, yêu cầu môn học, hạn chế dữ liệu, bảo toàn dữ liệu, lịch tải tay
```

Dùng thư viện trong notebook: chạy một lần `pip install -e .` ở thư mục gốc, rồi `from fluwatch.ingest.paths import Paths`. Các lệnh trong `scripts/` tự thêm `src/` vào đường dẫn nên không cần cài.

Dữ liệu lớn (khoảng 500 MB) nằm trên Hugging Face: [DragonBornRay/FluDataset](https://huggingface.co/datasets/DragonBornRay/FluDataset). GitHub chỉ chứa mã, tài liệu và `data/reference/`.

## Bắt đầu

```bash
pip install -r requirements.txt
python scripts/download_data.py --samples   # chỉ bảng đã xử lý, vài MB: đủ cho notebook và dashboard
python scripts/download_data.py             # toàn bộ, gồm raw/: cần khi chạy lại pipeline
```

Chạy mọi lệnh từ thư mục gốc của repo.

## Pipeline

**Cập nhật hằng tuần bằng một lệnh** (Thành viên 1). Workflow [`weekly_update.yml`](.github/workflows/weekly_update.yml) chạy lệnh này lúc 13:00 thứ Bảy giờ Việt Nam, sau `crawl_cdc.yml`:

```bash
python pipelines/01_ingest.py                    # Delphi + thời tiết 35 ngày gần nhất, dựng bảng, audit --strict
python pipelines/01_ingest.py --upload -m "..."  # như trên, audit đạt thì đẩy phần mới lên Hugging Face
```

Từng bước riêng lẻ:

Hướng dẫn dựng lại dữ liệu khi lỗi, kể cả khi phải dùng VPN: [`docs/ke_hoach_tu_dong_crawl_cdc.md`](docs/ke_hoach_tu_dong_crawl_cdc.md) mục 9.

| Bước | Lệnh | Kết quả |
| --- | --- | --- |
| 1. Crawl tự động | `python scripts/crawl_sample.py delphi` (cả `weather`, `files`) | `raw/` Delphi (ILINet, NHSN, NSSP, FluSurv, xét nghiệm, NWSS), Open-Meteo, file tĩnh |
| 2. Crawl bổ sung | `python scripts/crawl_missing.py` | EPA AirData 2010–2026, trang phương pháp CDC |
| 2b. CDC bị chặn (tự động) | `python scripts/crawl_cdc_us.py` (GitHub Actions chạy mỗi thứ Bảy) | `raw/` WVAL, vaccine, trang ngưỡng CDC; tự đẩy lên Hugging Face |
| 3. Ghi file tải tay | `python scripts/register_manual.py --by "Tên"` | Thêm file CDC tải tay vào `raw/manifest.jsonl` |
| 4. Bảng tra cứu | `python scripts/build_reference.py` | `reference/cities.csv` (3–5 thành phố mỗi bang), `reference/holidays.csv` |
| 5. Thời tiết 236 thành phố | `python scripts/crawl_cities_weather.py` (lịch sử đầy đủ), `--update` (35 ngày gần nhất, hằng tuần) | `raw/openmeteo_*_cities/` |
| 6. Môi trường | `python scripts/build_environment.py` | `samples/weather_state_week.csv.gz`, `samples/epa_pm25_state_week.csv.gz` |
| 7. Bảng mẫu | `python scripts/profile_sample.py` | `samples/state_week_sample.csv.gz` |
| 8. Ngưỡng CDC | `python scripts/build_thresholds.py` (đọc `state_week_sample`, nên chạy sau bước 7) | `reference/cdc_level_thresholds.csv`, `samples/cdc_level_state_week.csv.gz` |
| 8b. Hồ sơ dữ liệu | `python scripts/profile_extras.py`, `profile_dataset.py` | `samples/wval_state_week`, `vaccine_state_season` |
| 9. Kiểm tra độ đầy đủ | `python scripts/audit_data.py` (`--strict`: thoát mã 1 nếu có nguồn không đạt) | `samples/audit_results.json` |
| 10. Đẩy lên Hugging Face | `python scripts/upload_hf.py` | Chỉ đẩy phần mới; manifest chỉ được thêm dòng; không ghi đè khi có người đẩy chen giữa |
| 11. Kiểm tra toàn vẹn | `python scripts/verify_integrity.py` | Đối chiếu manifest ↔ file trên máy ↔ Hugging Face (sha256) |
| 12. Sao lưu | `python scripts/backup_hf.py` | Sao chép sang repo riêng tư `DragonBornRay/FluDataset-backup`, gắn lại cùng tag |
| 13. Khôi phục | `python scripts/restore.py [--revision vYYYY-MM-DD]` | Tải từ bản sao, kiểm tra, dựng lại bảng và so sánh (đã chạy thử 10/11/2026: đạt) |

Cơ chế bảo toàn dữ liệu thô và kết quả chạy thử khôi phục: [`docs/bao_toan_du_lieu.md`](docs/bao_toan_du_lieu.md).

`crawl_cities_weather.py` và `crawl_missing.py` import từ `crawl_sample.py`, nên chạy bằng `python scripts/...` (không dùng `python -I`).

## Nguồn CDC bị chặn từ Việt Nam

`data.cdc.gov` trả lỗi 403 cho máy ở Việt Nam. Nước thải WVAL (hằng tuần), độ phủ vaccine (hằng tháng) và trang ngưỡng CDC được tải tự động bằng GitHub Actions (máy chủ ở Mỹ) qua workflow [`crawl_cdc.yml`](.github/workflows/crawl_cdc.yml), chạy 10:00 sáng thứ Bảy giờ Việt Nam và đẩy thẳng lên Hugging Face. Cần secret `HF_TOKEN` trong repo GitHub. Kế hoạch và các bước cài đặt: [`docs/ke_hoach_tu_dong_crawl_cdc.md`](docs/ke_hoach_tu_dong_crawl_cdc.md).

Nếu workflow báo lỗi (job đỏ), dùng phương án dự phòng: bật VPN Mỹ rồi chạy `python scripts/crawl_cdc_us.py --upload`, hoặc tải bằng trình duyệt theo [`docs/can_tai_tay.txt`](docs/can_tai_tay.txt).

## Cập nhật dữ liệu lên Hugging Face

Sau khi crawl hoặc tải tay, chạy từ thư mục gốc của repo (cần `hf auth login` bằng token write, hoặc biến `HF_TOKEN`):

```bash
python scripts/upload_hf.py --dry-run          # xem những gì sẽ đẩy
python scripts/upload_hf.py -m "Cap nhat tuan ..."
```

`upload_hf.py` dựa trên commit Hugging Face đã tải về (`data/.hf_revision`, do `download_data.py` ghi). Nếu báo commit thất bại vì có người đẩy chen giữa: chạy lại `download_data.py`, chạy lại pipeline, rồi đẩy.

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
