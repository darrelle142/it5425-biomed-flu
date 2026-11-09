# Kế hoạch: tự động tải dữ liệu, bỏ phụ thuộc VPN

Cập nhật 08/11/2026. Người phụ trách đề xuất: Người 2 (data engineer CDC).

Đọc nhanh: dữ liệu có đủ cho kế hoạch v2 không → **mục 8**. Dữ liệu lỗi, cần tải lại hoặc phải dùng VPN → **mục 9**.

## 1. Đối chiếu 9 nguồn của kế hoạch v2

Kiểm tra ngày 08/11/2026 từ máy ở Việt Nam, không bật VPN, gọi đúng endpoint mà script của nhóm dùng.

| # | Nguồn trong kế hoạch v2 | Dùng cho (cột, RQ) | Nhóm lấy bằng | Từ VN không VPN | Cập nhật | Tự động hóa |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | NHSN Hospital Respiratory Data (`ua7e-t2fy`) | `hosp_flu`, `rate_flu`; RQ1, RQ2, RQ5 | Delphi `nhsn` (`crawl_sample.py delphi`) | ✅ | Hằng tuần | Chạy tay từ VN được; **chưa có lịch** (giai đoạn 2) |
| 2 | NHSN Admission Levels (`vdzy-6i9v`) | `cdc_level_flu`, `alert_level`; RQ5 | Tự tính từ bảng ngưỡng (`build_thresholds.py`) + trang phương pháp HRD trên www.cdc.gov | ✅ (trang ngưỡng trả 200 cho script; curl từng bị 403) | Ngưỡng: CDC xem lại định kỳ | **Workflow `crawl_cdc.yml`** (trang ngưỡng) |
| 3 | ILINet (Delphi `fluview`) | `ili_pct`; RQ1–RQ4, chuỗi chính | Delphi `fluview_ilinet` | ✅ | Hằng tuần | Như nguồn 1 |
| 4 | FluSurv-NET (Delphi `flusurv`) | Đối chiếu độ nặng; RQ2 | Delphi `flusurv` | ✅ | Hằng tuần | Như nguồn 1 |
| 5 | NWSS Wastewater Viral Activity Level | `ww_flua_level`; RQ5 | File WVAL trên data.cdc.gov (tải tay); dự phòng Delphi `nwss` | ❌ 403 (data.cdc.gov) | Thứ Sáu hằng tuần | **Workflow `crawl_cdc.yml`** |
| 6 | NSSP ED visits (`rdmq-nq56`) | `ed_pct_flu`; RQ1, RQ5 | Delphi `nssp` | ✅ | Hằng tuần | Như nguồn 1 |
| 7a | Open-Meteo Historical Weather | `temp_mean`, `abs_humidity`, `ah_anomaly`; RQ4 | `crawl_sample.py weather`, `crawl_cities_weather.py` | ✅ | Liên tục (trễ ~5 ngày) | Chạy tay từ VN được; chưa có lịch |
| 7b | Open-Meteo Air Quality + EPA AirData | `pm25_mean`, `pm25_max`; RQ4 | Open-Meteo (từ 08/2022) + EPA (`crawl_missing.py`, 2010–2026) | ✅ | EPA: vài lần mỗi năm | Chạy lại EPA đầu 01/2027 |
| 8 | CDC FluVaxView | `flu_vax_pct`; RQ4 | File "Influenza Vaccination Coverage for All Ages (6+ Months)" trên data.cdc.gov (tải tay) | ❌ 403 (data.cdc.gov) | Hằng tháng, trễ 1–2 tháng | **Workflow `crawl_cdc.yml`** |
| 9 | Census Vintage 2025 | Dân số bang, trọng số thành phố | File tải tay (bang, đô thị, Gazetteer) | ❌ 403 (census.gov) | Hằng năm | Không cần: đã đủ. Vintage 2026 (dự kiến 12/2026) chỉ cần nếu muốn cập nhật |
| – | Ngày lễ, kỳ nghỉ | `holiday_week`, `weeks_to_holiday`; RQ4 | Tự tạo (`build_reference.py`) | Không cần mạng | – | – |
| – | Dân số 2020 của Delphi (map tên bang) | Khóa bang | GitHub raw | ✅ | Cố định | – |

Trạng thái Delphi ngày 08/11/2026 (metadata V5): ILINet, NHSN, NSSP, FluSurv, xét nghiệm và NWSS đều đang cập nhật, có số liệu đến tuần kết thúc **31/10/2026**. Đã cập nhật lên Hugging Face cùng ngày (mục 3).

**Kết luận:**

- **Nguồn bị chặn từ Việt Nam chỉ có trên data.cdc.gov (WVAL, vaccine) và census.gov.** Census đã đủ, không cần tải lại. WVAL và vaccine chuyển sang GitHub Actions.
- **Phần còn lại (Delphi, Open-Meteo, EPA, trang CDC) tải được từ Việt Nam**, nhưng hiện phải có người chạy tay. Để "bật cập nhật hằng tuần" (tuần 5 của kế hoạch v2) cần thêm lịch chạy cho chúng (giai đoạn 2, mục 7).
- Không nguồn nào của kế hoạch v2 bị bỏ sót. Hai nguồn đổi cách lấy so với kế hoạch: NHSN HRD lấy qua Delphi (khớp 100%), NHSN Levels tự tính từ ngưỡng (khớp 99,4%; phần lệch do CDC sửa số).
- Id `atcp-73re` ghi cho NWSS trong kế hoạch v2 chưa được kiểm chứng (không truy cập được data.cdc.gov). Script tra id theo tên bộ dữ liệu và ghi id thật vào manifest; sau lần chạy đầu cần sửa lại kế hoạch v2 cho đúng.

**Ghi chú khi kiểm tra:** máy dùng để test có lúc không phân giải được tên `delphi.cmu.edu` (lỗi DNS trên máy), trong khi máy chủ Delphi vẫn trả 200. Đây là lỗi mạng cục bộ, không phải bị chặn. Nếu gặp `nodename nor servname provided` thì đổi DNS (ví dụ 8.8.8.8) hoặc chạy lại sau.

API cũ `api.delphi.cmu.edu/epidata/fluview` đã ngừng trả dữ liệu sau 22/09/2026. Script của nhóm dùng V5 (`delphi.cmu.edu/epidata/v5`) nên không bị ảnh hưởng. **Không dùng `epidatpy`/`epidatr` bản cũ** như kế hoạch v2 gợi ý.

## 2. Giải pháp cho nguồn bị chặn

Chạy script tải trên **GitHub Actions**. Máy chạy (runner) của GitHub đặt ở Mỹ nên không bị chặn theo địa lý. Kết quả được đẩy thẳng lên Hugging Face, nên các thành viên chỉ cần `download_data.py` như bình thường, không cần VPN.

```
GitHub Actions (Mỹ, thứ Bảy hằng tuần)
  └─ scripts/crawl_cdc_us.py
       1. tải manifest.jsonl hiện tại từ Hugging Face
       2. tra id bộ dữ liệu theo tên (Socrata catalog), tải CSV, kiểm tra cột
       3. so sha256 với bản mới nhất trong manifest: giống thì chỉ ghi log, khác thì lưu bản mới
       4. ghi thêm dòng vào manifest, đẩy file mới + manifest lên Hugging Face (1 commit)
  └─ nếu nguồn nào lỗi/403: job báo đỏ, GitHub gửi email → nhóm tải tay bằng VPN như cũ
```

Script dùng được cả trên máy cá nhân có VPN (`--upload` để đẩy lên HF), nên thay luôn cho quy trình tải tay bằng trình duyệt.

### 2.1. Script `scripts/crawl_cdc_us.py`

| Nguồn | Thư mục `raw/` | Tìm bộ dữ liệu | Định dạng lưu |
| --- | --- | --- | --- |
| WVAL | `cdc_wastewater_wval` | Tên: "CDC Wastewater Viral Activity Level for SARS-CoV-2, Influenza A and RSV" | CSV nguyên trạng, tên `<Tên_bộ>_<YYYYMMDD>.csv` như file CDC export |
| Vaccine | `cdc_fluvax_coverage` | Tên: "Influenza Vaccination Coverage for All Ages (6+ Months)" | Như trên |
| Trang ngưỡng | `cdc_methods` | URL cố định (như `crawl_missing.py`) | `hrd_data_methods.html.gz` |

Quy tắc:

- **Tra id theo tên, không ghi cứng id.** Không xác minh được id từ Việt Nam (catalog API cũng bị chặn). Script gọi `api.us.socrata.com/api/catalog/v1`, chọn bộ có tên trùng khớp; có thể ép id bằng `--id-wval`, `--id-vax` khi cần.
- **Kiểm tra cột** so với file nhóm đã tải ngày 01/11/2026. Thiếu cột thì không lưu, báo lỗi (tránh tải nhầm bộ dữ liệu, hoặc CDC đổi cấu trúc mà không ai biết).
- **Không lưu bản trùng.** Nếu sha256 giống bản mới nhất trong manifest thì chỉ ghi một dòng `"unchanged": true`. WVAL ~75 MB, vaccine ~33 MB; lưu trùng mỗi tuần sẽ phình kho dữ liệu vô ích.
- **Giữ định dạng cũ** (CSV không nén, tên file kiểu CDC) để `audit_data.py`, `profile_dataset.py`, `build_thresholds.py` đọc được ngay, không phải sửa.
- **Manifest** giữ đúng các trường hiện có (`source`, `file`, `url`, `fetched_at`, `http_status`, `bytes`, `sha256`), thêm `dataset_id`, `rows_updated_at` (thời điểm CDC cập nhật dữ liệu, lấy từ metadata Socrata), `runner` (`github-actions` hoặc tên máy).
- **Không thử vượt chặn.** Bị 403 thì ghi vào manifest và thoát với mã lỗi, đúng nguyên tắc của `crawl_missing.py`. User-Agent ghi rõ tên crawler của repo.
- **Repo Hugging Face đổi được** bằng `--repo` hoặc biến môi trường `HF_REPO` (mặc định `DragonBornRay/FluDataset`).

### 2.2. Workflow `.github/workflows/crawl_cdc.yml`

- Lịch: `cron: "0 3 * * 6"` = 10:00 sáng thứ Bảy giờ Việt Nam, sau bản cập nhật thứ Sáu của CDC. Vaccine và trang ngưỡng chạy cùng lịch; tháng nào CDC không đổi thì bước "không lưu bản trùng" tự bỏ qua.
- Có nút chạy tay (`workflow_dispatch`) với tùy chọn `dry_run` (tải và kiểm tra nhưng không đẩy lên HF).
- Bí mật `HF_TOKEN` (GitHub Secrets) và biến `HF_REPO` (GitHub Variables). Token không bao giờ nằm trong mã hay log.
- Không cần checkout dữ liệu 290 MB: chỉ tải `manifest.jsonl` từ HF.
- `concurrency` để hai lần chạy không ghi đè manifest của nhau; khi đẩy lên HF dùng `parent_commit`, nếu có người đẩy chen giữa thì commit thất bại thay vì ghi đè.

## 3. Repo Hugging Face chung: `DragonBornRay/FluDataset`

**Chốt ngày 09/11/2026:** cả nhóm chỉ dùng [DragonBornRay/FluDataset](https://huggingface.co/datasets/DragonBornRay/FluDataset) (chủ repo: Hiếu). Mặc định trong `download_data.py`, `crawl_cdc_us.py`, README và workflow đều trỏ về repo này.

Lịch sử: từ 08/11 đến 09/11/2026 nhóm thử một repo riêng `tdu175/FluDataset` (cập nhật Delphi 08/11 và lượt chạy GitHub Actions đầu tiên 09/11). Ngày 09/11 toàn bộ file và dòng manifest của repo đó đã được gộp về `DragonBornRay/FluDataset` cùng bản cập nhật 07/11 trên máy Hiếu. Repo `tdu175/FluDataset` không còn được cập nhật; không đẩy dữ liệu lên đó nữa.

**Bước 1: Tạo token cho GitHub Actions**

1. Đăng nhập Hugging Face bằng tài khoản chủ repo (`DragonBornRay`), vào **Settings → Access Tokens → Create new token**, chọn **Fine-grained**.
2. Token name: `github-actions-fludataset`.
3. Mục **Repositories permissions**: tìm và chọn `DragonBornRay/FluDataset`, tích **Write access to contents/settings of selected repos**. Không tích quyền nào khác.
4. Bấm **Create token** và chép token ngay (chỉ hiện một lần). Không dán token vào chat, mã nguồn hay file nào trong repo.

**Bước 2: Khai báo cho GitHub (cần quyền admin repo GitHub)**

Trên repo GitHub của nhóm: **Settings → Secrets and variables → Actions**.

- Tab **Secrets → New repository secret**: Name `HF_TOKEN`, Secret là token vừa chép.
- Tab **Variables → New repository variable**: Name `HF_REPO`, Value `DragonBornRay/FluDataset`.

Nếu không thấy mục Settings thì bạn chưa có quyền admin; nhờ chủ repo (`darrelle142`) làm bước này.

**Bước 3: Chạy thử workflow**

GitHub chỉ hiện nút chạy tay khi file workflow đã có trên nhánh mặc định (`main`). Vì vậy cần gộp nhánh `trongdung` vào `main` (qua Pull Request), rồi:

1. Tab **Actions → "Tai nguon CDC (WVAL, vaccine, nguong)" → Run workflow**.
2. Giữ `dry_run` được tích, bấm **Run workflow**. Mở lần chạy để xem bảng kết quả: 3 nguồn trả 200 nghĩa là máy chủ GitHub không bị CDC chặn.
3. Chạy lại với `dry_run` bỏ tích. Xem trên repo Hugging Face: tab **Files and versions** có commit mới "Tu dong tai CDC ...".

**Bước 4: Cả nhóm dùng chung một repo**

Mỗi người kéo nhánh mới nhất của repo GitHub rồi chạy `python scripts/download_data.py` (mặc định là `DragonBornRay/FluDataset`). Chỉ đẩy dữ liệu lên repo này.

## 4. Việc cần làm

| # | Việc | Ai | Trạng thái |
| --- | --- | --- | --- |
| 1 | Viết `scripts/crawl_cdc_us.py` | Claude / Người 2 | Xong |
| 2 | Viết `.github/workflows/crawl_cdc.yml` | Claude / Người 2 | Xong |
| 3 | Chạy thử trên máy: dry-run thật từ Việt Nam (WVAL, vaccine báo lỗi 403 đúng cách, trang ngưỡng 200, không ghi gì); 5 test logic với phản hồi giả lập từ file 01/11 (không lưu bản trùng, lưu bản mới, chặn khi đổi cột, lấy manifest từ HF) | Claude | Xong. Bước đẩy lên HF chưa test được vì cần token write |
| 4 | Kiểm tra từng nguồn của kế hoạch v2 truy cập được từ Việt Nam (mục 1) | Claude | Xong |
| 5 | Cho phép đổi repo HF (`--repo`, `HF_REPO`) trong `download_data.py`, `crawl_cdc_us.py`, workflow | Claude | Xong |
| 6 | Thử repo riêng `DragonBornRay/FluDataset` (mục 3) | Dũng | Đã bỏ 09/11, gộp về `DragonBornRay/FluDataset` |
| 6a | Cập nhật Delphi đến 31/10, dựng lại `samples/`, upload và đối chiếu 559/559 file | Dũng | Xong 08/11 |
| 6b | Tạo token write cho GitHub Actions trên `DragonBornRay/FluDataset` (mục 3, bước 1) | Hiếu (chủ repo HF) | Chưa |
| 7 | Thêm secret `HF_TOKEN` và variable `HF_REPO` vào GitHub repo | Người có quyền admin repo GitHub | Chưa |
| 8 | Commit trên nhánh `trongdung`, mở Pull Request và gộp vào `main` (lịch và nút chạy tay chỉ có trên nhánh mặc định) | Dũng / nhóm | Chưa |
| 9 | Bấm "Run workflow" với `dry_run = true`: xác nhận data.cdc.gov không chặn runner, id tìm đúng, cột khớp | Người 2 | Chưa |
| 10 | Chạy thật lần đầu (`dry_run = false`), kiểm tra commit mới trên HF và chạy `audit_data.py` | Người 2 | Chưa |
| 11 | Sửa id NWSS và vaccine trong kế hoạch v2 theo id thật trong manifest | Người 2 | Chưa |
| 12 | Cập nhật `can_tai_tay.txt` và `README.md`: tải tay chỉ còn là phương án dự phòng | Claude | Xong |

## 5. Kiểm thử và tiêu chí hoàn thành

- Lần chạy tay đầu tiên trên GitHub: 3/3 nguồn trả 200, cột khớp, id được ghi trong log.
- Sau lần chạy thật: trên HF có `raw/cdc_wastewater_wval/<ngày>/...csv` mới (nếu CDC đã cập nhật), manifest có dòng `runner: github-actions`; tải về bằng `download_data.py` rồi chạy `audit_data.py` không báo file chưa ghi hay dòng trỏ file mất.
- Chạy lại ngay lần hai: mọi nguồn báo `unchanged`, không có file mới trên HF.
- Hai tuần liên tiếp chạy theo lịch thành công mà không ai phải bật VPN.

## 6. Rủi ro và phương án dự phòng

| Rủi ro | Cách xử lý |
| --- | --- |
| data.cdc.gov cũng chặn IP của GitHub (dải IP đám mây) | Biết ngay ở bước 9. Khi đó dùng script này trên máy cá nhân có VPN (`python scripts/crawl_cdc_us.py --upload`): vẫn nhanh hơn tải bằng trình duyệt và tự ghi manifest, tự đẩy HF |
| CDC đổi tên bộ dữ liệu hoặc cột | Script báo lỗi rõ ràng, job đỏ, không lưu file sai. Ép id bằng `--id-wval/--id-vax` hoặc cập nhật cột trong script |
| GitHub tắt lịch chạy sau 60 ngày repo không có commit | Mỗi tuần nhóm vẫn commit; nếu bị tắt thì vào tab Actions bật lại |
| Token HF bị lộ | Dùng fine-grained token chỉ cho 1 repo dataset; thu hồi và tạo lại nếu nghi ngờ |
| Kho HF lớn dần (WVAL ~75 MB mỗi bản có thay đổi) | Khoảng 30 tuần × 75 MB ≈ 2,3 GB vẫn trong giới hạn HF. `download_data.py --samples` không bị ảnh hưởng; bản đầy đủ sẽ tải lâu hơn, cân nhắc thêm tùy chọn chỉ tải bản mới nhất nếu cần |
| Trang ngưỡng đổi mà không ai chạy lại `build_thresholds.py` | Giai đoạn 2: workflow so bảng ngưỡng tách từ trang mới với `reference/cdc_level_thresholds.csv` và báo khi khác |
| Delphi đổi API (bản cũ đã ngừng từ 22/09/2026) | Theo dõi trang Delphi; V5 hiện đang hoạt động |

## 7. Giai đoạn 2: cập nhật hằng tuần toàn bộ (làm nếu kịp)

Hiện workflow chỉ lo các nguồn bị chặn. Để dashboard chạy với dữ liệu mới nhất (tuần 5 của kế hoạch v2), cần thêm một workflow thứ hai chạy sau khi Delphi cập nhật (thứ Năm/thứ Sáu):

- `crawl_sample.py delphi` (khoảng 8 phút do giới hạn tốc độ ẩn danh của Delphi).
- Thời tiết: chỉ tải đoạn mới thay vì cả lịch sử từ 2010 (cần sửa `crawl_sample.py weather` và `crawl_cities_weather.py`, vì tải lại 236 thành phố × 16 năm mỗi tuần là quá nặng).
- Chạy lại `build_thresholds.py`, `build_environment.py`, `profile_sample.py`, `audit_data.py`, rồi đẩy `samples/` mới lên HF.
- Các script này cần toàn bộ `raw/` (~290 MB), nên workflow phải tải dữ liệu từ HF trước khi chạy.

## 8. Dữ liệu đã đủ để bám kế hoạch v2 chưa

Kiểm tra ngày 08/11/2026 trên bản chụp 01–04/11/2026. Độ phủ = % ô bang × tuần có số liệu, 51 đơn vị (50 bang + DC), các mùa 2010-11 đến 2025-26.

### 8.1. Từng cột trong từ điển dữ liệu (kế hoạch v2, mục 6)

| Cột kế hoạch v2 | Lấy từ | Có từ mùa | Mùa phủ ≥95% | 2024-25 | 2025-26 | Đánh giá |
| --- | --- | --- | --- | --- | --- | --- |
| `ili_pct` | `samples/state_week_sample` (ILINet) | 2010-11 | 15/16 | 100% | 84% | ✅ Đủ. Thiếu FL 2010–2021, LA 2010–2016; 8 bang thiếu mùa 2025-26 (xem `han_che_du_lieu.md`) |
| `hosp_flu`, `rate_flu` | `state_week_sample` (NHSN qua Delphi) | 2019-20 | 6/16 | 100% | 100% | ✅ Đủ cho cảnh báo. Chỉ 2024-25, 2025-26 là báo cáo bắt buộc |
| `cdc_level_flu`, `alert_level` | `samples/cdc_level_state_week` | 2019-20 | 6/16 | 100% | 100% | ✅ Đủ |
| `ed_pct_flu` | `state_week_sample` (NSSP) | 2021-22 | 4/16 | 100% | 100% | ✅ Đủ (chuỗi ngắn, kế hoạch đã lường trước) |
| `ww_flua_level` | `samples/wval_state_week` (WVAL) | 2021-22 | 5/5 | 100% | 100% | ✅ Đủ. Thiếu ND; cần lọc GU, VI |
| `temp_mean`, `abs_humidity` | `samples/weather_state_week` (3–5 thành phố) | 2010-11 | 16/16 | 100% | 100% | ✅ Đủ. **Dùng bảng này, không dùng cột thời tiết trong `state_week_sample`** (chỉ 1 thành phố mỗi bang) |
| `ah_anomaly` | Tính từ `abs_humidity` | 2010-11 | – | – | – | ✅ Đủ dữ liệu để tính (16 mùa làm trung bình nền) |
| `pm25_mean`, `pm25_max` | `samples/epa_pm25_state_week` (EPA) + `weather_state_week` (Open-Meteo) | EPA 2010-11; Open-Meteo 2021-22 | EPA 16/16 | 100% | 100% | ✅ Đủ. EPA đến 06/2026, mùa 2026-27 dùng Open-Meteo. EPA có 8 tuần âm (MT 2026), cần đặt thành thiếu |
| `flu_vax_pct` | `samples/vaccine_state_season` | 2009-10 | 49–51 đơn vị/mùa | ✅ | ✅ | ✅ Đủ. Trống có sẵn từ CDC: MS 2025-26, DC/NJ 2018-19; CA 2013-14 nên lấy tháng cuối có số |
| `holiday_week`, `weeks_to_holiday` | `reference/holidays.csv` | 2010–2028 | – | ✅ | ✅ | ✅ Đủ |
| `population` | Census Vintage 2025 (2020–2025) | – | – | ✅ | ✅ | ✅ Đủ |
| FluSurv (đối chiếu) | `raw/flusurv` | 2003 | 18 bang | – | – | ✅ Đúng như kế hoạch (chỉ đối chiếu) |
| `issue_date`, backtest "đúng như lúc công bố" | `raw/*/archive__*` (ILINet, NHSN, NSSP) | Bản công bố từ 10/2024 | – | ✅ | ✅ | ✅ Đủ để test trên 2024-25 và 2025-26. Muốn backtest ILINet các mùa cũ hơn thì phải crawl thêm archive trước 10/2024 (Delphi có từ 2003) |

### 8.2. Theo câu hỏi nghiên cứu

| RQ | Dữ liệu cần | Kết luận |
| --- | --- | --- |
| RQ1 Mùa cúm đang ở giai đoạn nào | ILINet, NHSN, NSSP, mức CDC | ✅ Đủ; 8 bang mùa 2025-26 dùng NSSP thay ILINet |
| RQ2 Sớm hay muộn, nhẹ hay nặng | ILINet 16 mùa, NHSN, FluSurv | ✅ Đủ |
| RQ3 Bang nào lên trước, phân cụm | ILINet theo bang | ✅ Đủ; mùa 2025-26 phân cụm trên NSSP |
| RQ4 Độ ẩm, PM2.5, vaccine, nghỉ lễ | Thời tiết 16 mùa, EPA 16 mùa, vaccine 17 mùa, ngày lễ | ✅ Đủ; Shaman 2010 chạy trên 48 bang lục địa + DC |
| RQ5 Cảnh báo 1–4 tuần | NHSN, mức CDC, NSSP, WVAL, ILINet, archive | ✅ Đủ; huấn luyện cần thêm dữ liệu giả lập như kế hoạch v2 mục 7 |

**Kết luận: đủ dữ liệu cho cả 5 RQ, không thiếu nguồn nào.** Các điểm cần xử lý nằm ở bước làm sạch, không phải thiếu dữ liệu: lọc GU/VI/PR, EPA âm, lấy thời tiết từ `weather_state_week`, vaccine CA 2013-14. Phần chưa có là các lớp của kế hoạch v2 phải tự xây: `clean/`, `business/` (Parquet, star schema), các cột phái sinh, dữ liệu giả lập trong `sandbox/`.

## 9. Hướng dẫn dựng lại dữ liệu khi có lỗi

Dành cho mọi thành viên. Chạy mọi lệnh từ thư mục gốc của repo, trong môi trường đã `pip install -r requirements.txt`.

### 9.1. Trường hợp thường gặp: chỉ cần dữ liệu để làm việc

```bash
python scripts/download_data.py --samples   # vài MB, đủ cho notebook và dashboard
python scripts/download_data.py             # toàn bộ (~300 MB), cần khi chạy lại pipeline
```

Không cần VPN. Lỗi `ModuleNotFoundError: huggingface_hub` nghĩa là chưa `pip install -r requirements.txt`.

### 9.2. Bảng nguồn: script nào tải, có cần VPN không

| Nguồn | Thư mục `raw/` | Lệnh | VPN Mỹ | Khi nào chạy lại |
| --- | --- | --- | --- | --- |
| ILINet, NHSN, NSSP, xét nghiệm, FluSurv, NWSS (Delphi) | `fluview_ilinet`, `nhsn`, `nssp`, `fluview_resp_lab_clinical`, `flusurv`, `nwss`, `delphi_meta` | `python scripts/crawl_sample.py delphi` (~8 phút) | Không | Hằng tuần, sau khi Delphi cập nhật (thứ Năm–thứ Sáu) |
| Thời tiết, PM2.5 thành phố lớn nhất | `openmeteo_weather`, `openmeteo_pm25` | `python scripts/crawl_sample.py weather` | Không | Khi cần thêm tuần mới |
| Thời tiết, PM2.5 các thành phố còn lại | `openmeteo_weather_cities`, `openmeteo_pm25_cities` | `python scripts/crawl_cities_weather.py` | Không | Như trên. Gặp 429/503 thì chạy lại hôm sau, script tự bỏ qua file đã có |
| EPA PM2.5, trang ngưỡng CDC | `epa_airdata`, `cdc_methods` | `python scripts/crawl_missing.py` | Không (trang ngưỡng có lúc 403) | EPA: đầu tháng 1. Ngưỡng: hằng tháng |
| Dân số Delphi 2020, trang FluVaxView | `population`, `fluvaxview_pages` | `python scripts/crawl_sample.py files` | Không | Một lần |
| **WVAL, vaccine, trang ngưỡng** | `cdc_wastewater_wval`, `cdc_fluvax_coverage`, `cdc_methods` | GitHub Actions `crawl_cdc.yml` (tự động). Dự phòng: `python scripts/crawl_cdc_us.py --upload` | **Có**, nếu chạy trên máy | Tự động mỗi thứ Bảy |
| **Census bang, đô thị, Gazetteer** | `census_popest_state`, `census_popest_places`, `census_gazetteer` | Tải bằng trình duyệt (mục 9.4) rồi `python scripts/register_manual.py --by "Tên"` | **Có** | Một lần; Vintage 2026 khi Census công bố |
| NHSN HRD, NHSN Levels (file CDC) | `cdc_nhsn_hrd`, `cdc_nhsn_levels` | Đã có bản 01/11/2026, **không cần tải lại** | (Có) | Không. Chỉ dùng để kiểm chứng; số liệu chính lấy qua Delphi |

### 9.3. Thứ tự dựng lại các bảng `samples/` và `reference/`

Sau khi `raw/` đã đủ (tải từ HF hoặc crawl lại), chạy đúng thứ tự sau. **Thứ tự trong bảng Pipeline của README bị sai ở chỗ `build_thresholds.py`**: script này đọc `state_week_sample.csv.gz` nên phải chạy sau `profile_sample.py`.

| # | Lệnh | Đọc | Tạo ra |
| --- | --- | --- | --- |
| 1 | `python scripts/build_reference.py` | Census đô thị, Gazetteer, dân số Delphi | `reference/cities.csv`, `reference/holidays.csv` |
| 2 | `python scripts/crawl_cities_weather.py` | `reference/cities.csv` | `raw/openmeteo_*_cities/` |
| 3 | `python scripts/build_environment.py` | Thời tiết, PM2.5 Open-Meteo, EPA | `samples/weather_state_week.csv.gz`, `samples/epa_pm25_state_week.csv.gz` |
| 4 | `python scripts/profile_sample.py` | Delphi, thời tiết thành phố lớn nhất | `samples/state_week_sample.csv.gz` |
| 5 | `python scripts/build_thresholds.py` | Trang ngưỡng, file NHSN Levels, `state_week_sample` | `reference/cdc_level_thresholds.csv`, `samples/cdc_level_state_week.csv.gz` |
| 6 | `python scripts/profile_extras.py` | `state_week_sample`, EPA, Delphi metadata (cần mạng) | `samples/profile_results.json` |
| 7 | `python scripts/profile_dataset.py` | `state_week_sample`, các file CDC và Census tải tay | `samples/wval_state_week.csv.gz`, `samples/vaccine_state_season.csv` |
| 8 | `python scripts/audit_data.py` | Toàn bộ | `samples/audit_results.json` và bảng kiểm tra in ra màn hình |

Bước 1–2 chỉ cần khi đổi danh sách thành phố; bình thường bắt đầu từ bước 3.

Kết quả đạt: `audit_data.py` in `ok = True` ở mọi dòng, `units_51 = 51/51` cho các nguồn cấp bang (trừ xét nghiệm 49/51, FluSurv 18/51, WVAL 50/51 là đúng với nguồn gốc), dòng `manifest.jsonl` không có file chưa ghi, dòng trỏ file mất hay sha lệch.

### 9.4. Khi bắt buộc phải dùng VPN

Chỉ cần trong 2 trường hợp: workflow GitHub Actions báo đỏ vì data.cdc.gov chặn, hoặc cần tải Census mới.

**Nguồn CDC (WVAL, vaccine, trang ngưỡng): dùng script, không tải bằng trình duyệt**

1. Bật VPN đặt ở Mỹ.
2. Đăng nhập Hugging Face một lần: `hf auth login`, dán token write của repo `DragonBornRay/FluDataset` (xin Hiếu).
3. Chạy thử, không ghi gì: `python scripts/crawl_cdc_us.py --dry-run`. Bảng cuối phải có 3 dòng không có chữ `LOI`.
4. Chạy thật: `python scripts/crawl_cdc_us.py --upload`. Script tự lưu vào `raw/`, ghi manifest và đẩy lên HF trong một commit.
5. Nếu script báo không tra được id (CDC đổi tên bộ dữ liệu): mở data.cdc.gov bằng trình duyệt (vẫn bật VPN), tìm bộ dữ liệu, lấy id dạng `xxxx-xxxx` trên URL rồi chạy `python scripts/crawl_cdc_us.py --upload --id-wval <id>` (hoặc `--id-vax <id>`).

**Census (bằng trình duyệt)**

1. Bật VPN Mỹ, tải các file:
   - Dân số bang: trang "State Population Totals: 2020-2025" trên census.gov, file `NST-EST2025-ALLDATA.csv`
   - Dân số đô thị: trang "City and Town Population Totals: 2020-2025", file `SUB-IP-EST2025-POP.xlsx`
   - Tọa độ đô thị: `https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/2024_Gaz_place_national.zip`
2. Lưu vào `data/raw/<nguồn>/<YYYY-MM-DD>/` (ngày tải), giữ nguyên tên file. Thư mục nguồn: `census_popest_state`, `census_popest_places`, `census_gazetteer`.
3. `python scripts/register_manual.py --by "Tên"` để ghi vào manifest.
4. Chạy lại `build_reference.py` rồi các bước 3–8 ở mục 9.3.
5. Đẩy lên HF: `hf upload DragonBornRay/FluDataset ./data . --repo-type dataset --exclude ".cache/*" --exclude "samples/preview_*" --exclude "samples/*_results.json" --exclude "sandbox/*"`

### 9.5. Lỗi thường gặp

| Triệu chứng | Nguyên nhân | Cách xử lý |
| --- | --- | --- |
| `ModuleNotFoundError: huggingface_hub` | Chưa cài thư viện | `pip install -r requirements.txt` (nên dùng `python -m venv .venv`) |
| `HTTP 403` từ data.cdc.gov, census.gov | Chặn theo địa lý | Mục 9.4 |
| `nodename nor servname provided` khi gọi delphi.cmu.edu | Lỗi DNS trên máy, không phải bị chặn | Đổi DNS (8.8.8.8) hoặc chạy lại sau |
| Open-Meteo `429` | Hết lượt miễn phí trong ngày | Chạy lại hôm sau; script bỏ qua file đã có |
| Open-Meteo `503` | Máy chủ quá tải | Chạy lại; script bỏ qua file đã có |
| API `api.delphi.cmu.edu/epidata/fluview` trả rỗng | API cũ đã ngừng từ 22/09/2026 | Dùng script của nhóm (Delphi V5), không dùng `epidatpy` bản cũ |
| `hf upload` báo lỗi quyền | Token chỉ đọc, hoặc không có quyền trên `DragonBornRay/FluDataset` | Xin chủ repo token write |
| `crawl_cdc_us.py --upload` báo commit thất bại | Có người đẩy lên HF chen giữa | Chạy lại lệnh |
