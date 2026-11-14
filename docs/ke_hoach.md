# Kế hoạch về đích (14/11 – 22/11/2026)

> 📍 [Mục lục tài liệu](README.md) · Việc chi tiết từng người: [phan_cong.md](phan_cong.md) · Kế hoạch gốc: [ke_hoach_v2.docx](ke_hoach_v2.docx)

Đây là **kế hoạch hiện hành duy nhất** của nhóm (cập nhật 14/11/2026, người quản lý tiến độ: Dũng, kiêm TV4). Khi tài liệu khác nói khác, theo file này.

## 1. Tóm tắt 1 phút

- **Nộp bài: chủ nhật 22/11/2026.** Khóa số liệu: thứ Năm 19/11, 18:00 (tag `v2026-11-19` trên Hugging Face).
- **Cả 6 người làm song song từ 15/11**, nhờ chốt trước tên file và tên cột (mục 4). Không ai phải chờ người khác xong mới bắt đầu.
- **Dữ liệu chung** chỉ ở Hugging Face `DragonBornRay/FluDataset`, đã có số liệu đến tuần 07/11/2026, tự cập nhật mỗi thứ Bảy.
- **Mỗi người:** đọc đoạn của mình trong [phan_cong.md](phan_cong.md), dòng của mình trong lịch (mục 5), và các file mình phải giao (mục 4.2).
- **Mỗi tối 21:00** báo 3 dòng trên nhóm chat và mở PR phần đã chạy được (mục 8, 9).

## 2. Phạm vi: làm gì, hoãn gì

Làm hết phần **bắt buộc** của kế hoạch v2 (mục 11.1). Phần **mở rộng** chỉ làm khi đã khóa số liệu (19/11) mà còn thời gian.

| Thành viên | Giữ (bắt buộc) | Hoãn sang "mở rộng" |
| --- | --- | --- |
| TV1 | Đã xong 14/11: workflow CDC và cập nhật hằng tuần chạy thật, kiểm tra toàn vẹn sha256, tag phiên bản, bản sao lưu, chạy thử khôi phục. Còn: lịch tự chạy, khuôn báo cáo | – |
| TV2 | `clean/`, `business/` star schema (Parquet + DuckDB); kiểm tra chất lượng 4 mức; chạy trên dữ liệu chèn lỗi; từ điển dữ liệu, lineage | Báo cáo chất lượng dạng HTML đẹp (bản Markdown là đủ) |
| TV3 | Mức nền, tuần khởi phát, tuần đỉnh, độ nặng; EDA; phân cụm; Kruskal-Wallis | Mann-Kendall, phân tích hướng lan theo tọa độ |
| TV4 | Bảng bằng chứng; `ah_anomaly`; tương quan trễ; kiểm chứng Shaman; Negative Binomial + LR test, AIC, overdispersion; forest plot; dữ liệu chèn lỗi; what-if vaccine | Power curve đầy đủ (chỉ làm 1 kịch bản cài hiệu ứng), rootogram, kịch bản "mùa đông khô" |
| TV5 | Lịch sử nhập viện giả lập; logistic vượt ngưỡng 1–2 tuần và khởi phát; ROC/AUC, calibration, Brier, Hosmer-Lemeshow, Youden, DeLong; backtest mùa 2025-26 | Dự báo dạng quạt `pred_1w..4w` (thay bằng xác suất vượt ngưỡng) |
| TV6 | Dashboard Streamlit 5 trang + Phương pháp, đăng lên Streamlit Cloud; slide | Tile map có hiệu ứng chuyển động, kiểm tra mù màu bằng công cụ (thay bằng dùng sẵn bảng màu Okabe-Ito) |

**Chuyển việc để cân tải:** TV1 đã xong phần lớn mảng của mình, nên nhận thêm **ghép quyển báo cáo**, **chạy thử toàn bộ pipeline từ máy trống** và **hỗ trợ TV2** dựng kho (mục 6). TV6 chỉ còn dashboard và slide.

## 3. Vì sao làm song song được

Chuỗi phụ thuộc cũ: TV2 dựng kho → TV3, TV4, TV5 phân tích → TV6 vẽ dashboard → báo cáo. Ai đi sau đều phải chờ người đi trước, nên chỉ còn 8 ngày là không kịp.

Cách gỡ: **chốt trước "hợp đồng" (tên file, tên cột) giữa các bên ngay hôm nay**, rồi ai cũng làm ngay trên hợp đồng đó:

| Ai đang chờ ai | Gỡ bằng |
| --- | --- |
| TV3, TV4, TV5 chờ kho dữ liệu của TV2 | Hàm đọc chung `load_flu_week()` (mục 4.1): ngày đầu đọc từ `samples/`, khi TV2 xong thì đọc từ `business/`. **Code phân tích không phải sửa** |
| TV6 chờ kết quả của TV3, TV4, TV5 | Mỗi bên giao trước một **file stub** đúng tên cột, số liệu giả (mục 4.2). TV6 vẽ dashboard trên stub, sau thay bằng file thật cùng tên |
| TV4, TV5 chờ mốc mùa của TV3 | Định nghĩa mốc mùa đã thống nhất (kế hoạch v2 mục 6); TV3 giao stub ngày 15/11, bản thật 17/11 |
| Báo cáo chờ kết quả | Viết song song: phần dữ liệu và phương pháp viết ngay từ hôm nay, phần kết quả điền sau khi khóa số liệu |
| Hai người sửa chung file | Mỗi người chỉ sửa gói của mình (`src/fluwatch/<gói>/`, `pipelines/0X_*.py`, `reports/chapters/0X_*.md`); file chung (README, `docs/`) chỉ người quản lý tiến độ sửa |

## 4. Hợp đồng dữ liệu (chốt 14/11, không đổi tên cột sau 16/11)

Quy ước chung: `state` là mã bang 2 chữ **viết thường** (`ca`, `tx`, như dữ liệu hiện có), chỉ 50 bang + DC; `week` là ngày **thứ Bảy kết thúc tuần MMWR** (kiểu ngày); `season` dạng `2024-25`, bắt đầu từ tuần MMWR 40; `season_week` = 1 ở tuần 40.

### 4.1. Hàm đọc chung (TV2 sở hữu: `src/fluwatch/warehouse/load.py`)

| Hàm | Một dòng là | Cột |
| --- | --- | --- |
| `load_flu_week()` | bang × tuần | `state`, `week`, `epiweek` (YYYYWW), `season`, `season_week`, `ili_pct`, `num_ili`, `num_patients`, `hosp_flu`, `rate_flu`, `cdc_level` (0–4), `ed_pct_flu`, `lab_pct_pos`, `wval` (nước thải cúm A), `temp_mean`, `abs_humidity`, `ah_anomaly`, `pm25_mean` (EPA; thiếu thì Open-Meteo), `flu_vax_pct`, `holiday_week`, `winter_break`, `weeks_to_holiday`, `is_preliminary` (4 tuần gần nhất) |
| `load_dim_state()` | bang | `state`, `state_name`, `hhs_region` (1–10), `population`, `contiguous` (48 bang lục địa + DC), `cluster_id` (để trống đến khi TV3 giao) |
| `load_dim_time()` | tuần | `week`, `epiweek`, `season`, `season_week`, `year`, `month`, `holiday_week` |
| `load_season_summary()` | bang × mùa | `state`, `season`, `flu_vax_pct`, và các cột mốc mùa của TV3 (mục 4.2) |

- **Hôm nay đến 16/11:** hàm đọc từ `data/samples/` và `data/reference/`, ghép sẵn đúng tên cột trên (thời tiết lấy từ `weather_state_week`, không lấy cột thời tiết trong `state_week_sample`; lọc GU, VI, PR).
- **Từ 17/11:** cùng hàm đó đọc `data/business/*.parquet`. Người dùng không phải đổi gì.
- `ah_anomaly` = `abs_humidity` trừ trung bình `abs_humidity` của cùng bang, cùng tuần MMWR qua các năm 2010–2025. TV4 dùng đúng cột này, không tự tính lại.

### 4.2. File kết quả mỗi người giao (lưu trong `data/business/`, đẩy lên Hugging Face)

| File | Người giao | Một dòng là | Cột | Stub | Bản thật |
| --- | --- | --- | --- | --- | --- |
| `season_milestones.parquet` | TV3 | bang × mùa | `state`, `season`, `baseline`, `onset_week`, `peak_week`, `peak_value`, `severity`, `source` (`ili` hoặc `nssp`) | 15/11 | 17/11 |
| `season_phase.parquet` | TV3 | bang × tuần (mùa hiện tại) | `state`, `week`, `season_phase` (`chua_bat_dau`, `dang_len`, `dinh`, `dang_giam`) | 15/11 | 17/11 |
| `state_cluster.parquet` | TV3 | bang | `state`, `cluster_id` | 15/11 | 18/11 |
| `risk_rate_ratios.csv` | TV4 | yếu tố | `factor`, `lag_weeks`, `rr`, `ci_low`, `ci_high`, `p_lr`, `model` | 15/11 | 18/11 |
| `whatif.parquet` | TV4 | bang × tuần × kịch bản | `state`, `week`, `scenario`, `value_base`, `value_scenario`, `is_synthetic` (= 1) | 15/11 | 18/11 |
| `alert_forecast.parquet` | TV5 | bang × tuần dự báo × tầm | `state`, `week`, `horizon` (1, 2), `prob_exceed`, `prob_onset`, `alert_level` (`thap`, `trung_binh`, `cao`) | 15/11 | 18/11 |
| `model_eval.json` + `roc_points.csv` | TV5 | – | AUC + khoảng tin cậy, Brier, p Hosmer-Lemeshow, ngưỡng Youden; `fpr`, `tpr`, `model` | 15/11 | 18/11 |
| `audit_results.json` | TV1 (đã có) | nguồn | như hiện tại | Đã có | Hằng tuần |

- **Stub** = file đúng tên, đúng cột, số liệu giả hoặc làm nhanh, có cột hoặc khóa `is_stub = true`. TV6 dựng dashboard ngay trên stub.
- Bản thật **thay đúng file đó**, không đổi tên cột. Muốn thêm cột thì được, muốn đổi hoặc bỏ cột thì báo người quản lý tiến độ trước.
- Hình cho báo cáo: `reports/figures/tvX_<ten>.png`. Chương: `reports/chapters/0X_<ten>.md`.

## 5. Lịch 6 luồng song song

Mỗi luồng đi độc lập từ hôm nay. Ô **in đậm** là thứ giao cho người khác.

| Ngày | TV1 | TV2 | TV3 | TV4 | TV5 | TV6 |
| --- | --- | --- | --- | --- | --- | --- |
| **T7 14/11** (tối) | Đọc hợp đồng; sửa phút lẻ trong `cron` | Đọc hợp đồng | Đọc hợp đồng | Đọc hợp đồng | Đọc hợp đồng | Đọc hợp đồng |
| **CN 15/11** | Khuôn báo cáo `reports/` (LaTeX hoặc Word) + khuôn slide chung | **`load.py` bản đọc `samples/` (trưa)** | **Stub 3 file**; mức nền, tuần khởi phát | **Stub 2 file**; bảng bằng chứng; bộ chèn lỗi | **Stub 2 file**; nhãn vượt ngưỡng | Khung Streamlit 5 trang + Phương pháp |
| **T2 16/11** | Chương 1 | `clean/` từng nguồn; quy tắc chất lượng 4 mức | Tuần đỉnh, độ nặng, `season_phase`; EDA | Tương quan trễ; NB bản đầu | Lịch sử nhập viện giả lập; logistic bản đầu | Trang 1 Hiện tại, trang 2 Mùa vụ (trên stub + `load_flu_week`) |
| **T3 17/11** | Chương 2.1; chạy thử pipeline từ máy trống | **`business/` v1 lên HF; `load.py` chuyển sang `business/`** | **`season_milestones`, `season_phase` thật** | Shaman (dùng mốc mùa thật); NB + LR test, AIC | ROC/AUC, calibration, Brier, HL | Trang 3 Địa lý; tile map |
| **T4 18/11** | Gọi `pipelines/02`–`05` trong workflow hằng tuần | Chạy kiểm tra trên bộ chèn lỗi; DuckDB OLAP | **`state_cluster` thật**; Kruskal-Wallis | **`risk_rate_ratios`, `whatif` thật**; forest plot | **`alert_forecast`, `model_eval` thật**; DeLong, Youden, backtest | Trang 4, 5, Phương pháp; thay stub bằng file thật |
| **T5 19/11** | **Gắn tag `v2026-11-19` (khóa số liệu, 18:00)** | Chương 2.2–2.4 | Chương 3 | Chương 4 | Chương 5 | Đăng Streamlit Cloud; slide nháp |
| **T6 20/11** | Ghép báo cáo (nhận chương trước 12:00) | Đọc chéo Chương 3 | Đọc chéo Chương 4 | Đọc chéo Chương 5 | Đọc chéo Chương 6 | Chương 6, Kết luận; slide |
| **T7 21/11** | Sửa báo cáo theo góp ý | Đọc chéo Chương 1–2.1 | | | | Slide hoàn chỉnh |
| | **Cả nhóm: tập thuyết trình (tối 21/11)** | | | | | |
| **CN 22/11** | **Nộp báo cáo PDF và slide lên Drive** | | | | | |

**Viết báo cáo song song:** từ 15/11, mỗi người mở `reports/chapters/0X_*.md` và viết ngay phần dữ liệu và phương pháp (không cần kết quả). Phần kết quả điền sau 18/11 từ số liệu đã khóa.

## 6. Đường găng (chậm là kéo cả nhóm)

1. **TV2 `load.py` (15/11 trưa) và `business/` v1 (17/11).** Đây là việc duy nhất nhiều người phụ thuộc. **TV1 đã xong mảng chính nên hỗ trợ TV2**: TV1 làm phần đọc thời tiết, EPA, vaccine trong `clean/`; TV2 làm Delphi, star schema, kiểm tra chất lượng. Hai người chia file, không sửa chung một file.
2. **TV3 mốc mùa thật (17/11)**: TV4 cần cho Shaman, TV5 cần cho nhãn khởi phát. Trễ thì TV4, TV5 dùng stub và ghi chú.
3. **Khóa số liệu 19/11 18:00.** Sau giờ này không chạy lại mô hình; mọi số trong báo cáo, slide, dashboard lấy từ tag `v2026-11-19`.

## 7. Ai sở hữu file nào

| Thứ | Người duy nhất được sửa | Người khác cần gì thì |
| --- | --- | --- |
| `scripts/`, `.github/workflows/`, `data/raw/`, repo Hugging Face | TV1 | Nhắn TV1 |
| `data/clean/`, `data/business/`, từ điển dữ liệu | TV2 | Giao file kết quả của mình (Parquet), TV2 ghép vào |
| Mốc mùa, `cluster_id` | TV3 | TV3 xuất file, TV2 ghép vào `fact_season_summary`, `dim_state` |
| `data/sandbox/` (giả lập, chèn lỗi, what-if) | TV4 (riêng lịch sử nhập viện giả lập: TV5) | – |
| `models/`, cột dự báo | TV5 | TV5 xuất file, TV2 ghép vào |
| `src/fluwatch/dashboard/` | TV6 | Giao hình hoặc file Parquet cho TV6 |
| Quyển báo cáo tổng | TV1 | Nộp chương dạng Markdown/Word riêng |
| Slide | TV6 | Gửi 1–2 slide nội dung của mình cho TV6 |
| Mỗi `src/fluwatch/<mảng>/`, `pipelines/0X_*.py` | Chủ mảng | – |

Gộp vào `main` qua Pull Request, người duyệt là TV1 (hoặc người quản lý tiến độ khi TV1 bận).

## 8. Quy tắc phối hợp

- **Nhánh riêng, PR nhỏ, gộp mỗi ngày.** Tên nhánh `tvX/<viec>`. Mỗi tối trước 22:00 mở PR phần đã chạy được; TV1 duyệt và gộp vào `main`. Không ai giữ code trên máy quá 1 ngày.
- **Chỉ sửa phần của mình** (bảng ở mục 7). Cần đổi phần người khác thì nhắn người đó.
- **Dữ liệu dùng chung chỉ qua Hugging Face** `DragonBornRay/FluDataset`. Không gửi file qua chat.
- **Không đổi hợp đồng một mình.** Thêm cột được, đổi hoặc bỏ cột phải báo người quản lý tiến độ, người này báo những ai bị ảnh hưởng.
- **Trễ thì báo trước ít nhất nửa ngày**; người nhận tiếp tục trên stub.

## 9. Theo dõi tiến độ

- **Mỗi tối 21:00**: mỗi người 3 dòng trên nhóm chat (xong gì, mai làm gì, vướng gì) kèm link PR.
- **Họp 15 phút**: CN 15/11 tối (tất cả stub và `load.py` đã có chưa), T3 17/11 tối (`business/` v1, mốc mùa thật), T5 19/11 tối (khóa số liệu).

| Mốc | Kiểm tra | Xong |
| --- | --- | --- |
| CN 15/11 trưa | `load.py` đọc `samples/` trả đúng tên cột | ☐ |
| CN 15/11 tối | Đủ 7 file stub trên HF; khuôn báo cáo có trong `reports/`; dashboard có khung | ☐ |
| T2 16/11 | Mỗi người có ít nhất 1 PR đã gộp; mỗi chương có phần phương pháp | ☐ |
| T3 17/11 | `business/` v1 trên HF; `load.py` đọc `business/`; mốc mùa thật | ☐ |
| T4 18/11 | Mọi file stub đã thay bằng bản thật; dashboard chạy trên file thật | ☐ |
| T5 19/11 18:00 | Tag `v2026-11-19`; dashboard online; đủ hình trong `reports/figures/` | ☐ |
| T6 20/11 12:00 | Đủ chương gửi TV1 | ☐ |
| T7 21/11 | Đọc chéo xong; tập thuyết trình | ☐ |
| CN 22/11 | Nộp | ☐ |

## 10. Đính chính so với kế hoạch v2

Kế hoạch v2 vẫn là tài liệu gốc cho định nghĩa và phương pháp. Các điểm dưới đây đã thay đổi; khi hai tài liệu khác nhau thì theo bảng này.

| Kế hoạch v2 ghi | Thực tế hiện nay |
| --- | --- |
| Mục 4: "Mọi nguồn đều lấy được bằng code, không cần tải tay" | data.cdc.gov và census.gov chặn máy ở Việt Nam. Các nguồn này tải qua GitHub Actions (máy chủ ở Mỹ), xem `docs/ke_hoach_tu_dong_crawl_cdc.md` |
| Mục 3–4: NHSN (`ua7e-t2fy`), NSSP (`rdmq-nq56`) lấy qua Socrata API | Lấy qua Delphi Epidata V5 (khớp 100% với file NHSN của CDC) |
| Mục 3: mức độ CDC lấy từ bộ `vdzy-6i9v` | Tự tính từ bảng ngưỡng CDC (`reference/cdc_level_thresholds.csv`), khớp 99,4% |
| Mục 4: dùng package `epidatpy` / `epidatr` | API cũ của Delphi đã ngừng trả dữ liệu từ 22/09/2026; dùng script của nhóm gọi Delphi V5 |
| Mục 3: nước thải `atcp-73re`; vaccine không ghi id | Đã kiểm chứng: nước thải `atcp-73re`, vaccine `vh55-3he6` |
| Mục 1: dashboard "Tableau Public hoặc Streamlit" | Chốt Streamlit (đọc thẳng dữ liệu từ Hugging Face, tự cập nhật) |
| Mục 5.2: vùng `raw/`, `clean/`, `business/`, `sandbox/` | Giữ nguyên; thêm `samples/` là bảng thử, dùng đến 15/11 |
| Mục 7.1 mục đích 4: giả lập để dựng dashboard sớm | Không cần nữa: dashboard dựng trên dữ liệu thật đã có |
| Mục 10: phân công 6 vai trò cũ | Theo `docs/phan_cong.md` |
| Mục 11.2: lộ trình 6 tuần | Theo file này: về đích 22/11/2026, phạm vi ở mục 2 |
