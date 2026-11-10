# Bảo toàn dữ liệu thô

Cập nhật 10/11/2026. Người phụ trách: Thành viên 1.

Mục tiêu: dữ liệu thô đã tải **không bao giờ bị sửa, ghi đè hay mất**; mọi thay đổi đều truy được nguồn gốc; khi kho chính hỏng thì khôi phục lại được đúng trạng thái của một tuần bất kỳ.

## 1. Các lớp bảo vệ

| Lớp | Cơ chế | Ở đâu |
| --- | --- | --- |
| Lưu nguyên trạng | Mỗi lần tải lưu vào `raw/<nguồn>/<ngày tải>/`, giữ nguyên nội dung gốc (chỉ nén gzip). Tải lại trong cùng ngày thì thêm giờ vào tên file, không ghi đè | `scripts/crawl_sample.py` (`save()`), `scripts/crawl_cdc_us.py` |
| Nhật ký nguồn gốc | `raw/manifest.jsonl`: mỗi lần tải một dòng (URL, thời điểm, mã HTTP, kích thước, sha256, người tải hoặc máy chạy). Lần tải lỗi cũng được ghi | mọi script tải |
| Chỉ thêm, không sửa | Khi đẩy lên Hugging Face, manifest trên máy phải bắt đầu bằng đúng manifest trên HF. Dòng manifest mới trỏ tới file đã có trên HF thì dừng lại | `scripts/upload_hf.py` |
| Không ghi đè khi đẩy chen | Mọi commit dùng `parent_commit` = commit đã tải; có người đẩy chen giữa thì HF từ chối. Hai workflow dùng chung nhóm `concurrency` | `upload_hf.py`, `crawl_cdc_us.py`, `.github/workflows/*.yml` |
| Kiểm tra toàn vẹn hằng tuần | Đối chiếu 3 chiều: manifest ↔ file trên máy (sha256) ↔ file trên HF. Lệch thì dừng pipeline trước khi tải hay đẩy gì | `scripts/verify_integrity.py`, bước `verify` |
| Cổng chất lượng | `audit_data.py --strict`: nguồn nào không đạt thì không đẩy | bước `audit` |
| Phiên bản | Mỗi lần cập nhật hằng tuần gắn tag `vYYYY-MM-DD`; tải lại đúng phiên bản bằng `download_data.py --revision <tag>` | `upload_hf.py --tag` |
| Bản sao thứ hai | Sau mỗi lần đẩy, sao chép sang repo riêng tư `DragonBornRay/FluDataset-backup` (token riêng `HF_BACKUP_TOKEN`); `raw/` chỉ được thêm; gắn lại cùng tag | `scripts/backup_hf.py`, bước `backup` |
| Khôi phục đã chạy thử | Tải từ bản sao → kiểm tra toàn vẹn → dựng lại bảng → so với bảng đã lưu | `scripts/restore.py` |

Thứ tự trong `pipelines/01_ingest.py --upload` (workflow `weekly_update.yml`, 13:00 thứ Bảy): tải từ HF → **verify** → Delphi → thời tiết → dựng bảng → **audit** → đẩy + **tag** → **sao lưu**.

## 2. Sự cố đã phát hiện nhờ kiểm tra toàn vẹn

Lần chạy đầu tiên của `verify_integrity.py` (10/11/2026) báo 472 file `raw/openmeteo_*_cities/2026-11-10/*__recent.json.gz` có sha256 không khớp dòng manifest mới nhất.

- Nguyên nhân: cùng ngày 10/11, thời tiết được tải 2 lần (trên máy lúc sáng, trên GitHub Actions lúc 11:34) vào cùng đường dẫn. Khi đẩy, `upload_hf.py` thấy file đã có trên HF nên bỏ qua bản sau, nhưng manifest vẫn ghi sha của bản sau.
- Hậu quả: không mất dữ liệu cũ; chỉ bản tải lại (35 ngày gần nhất) không được lưu, tuần sau sẽ được tải lại.
- Đã sửa: tải trùng tên trong ngày thì thêm giờ vào tên file; `upload_hf.py` dừng lại thay vì bỏ qua. Vì manifest chỉ được thêm dòng, 472 file này được ghi nhận là **cảnh báo** `tai_lai_khong_luu` (file khớp dòng manifest đầu tiên), không phải lỗi.

## 3. Chạy thử khôi phục (10/11/2026)

Lệnh: `python scripts/restore.py` (bản mới nhất của `DragonBornRay/FluDataset-backup`, vào thư mục riêng `restore_test/`).

| Bước | Kết quả |
| --- | --- |
| Sao lưu lần đầu (`backup_hf.py`) | 1.071 file, 492 MB, 8 commit; đối chiếu sau khi chép: khớp 1.071/1.071 file |
| Tải về từ bản sao | 1.072 file (commit `43cd0714`) |
| Kiểm tra toàn vẹn bản khôi phục | OK (1.732 dòng manifest, 1.057 file thô) |
| Dựng lại bảng từ `raw/` | 4/4 script chạy xong |
| So với bảng đã lưu | 6/6 bảng khớp: `state_week_sample` 44.829 dòng, `cdc_level_state_week` 44.829, `wval_state_week` 9.901, `vaccine_state_season` 865, `weather_state_week` 44.829, `epa_pm25_state_week` 43.753 |
| Tổng thời gian | 533 giây (khoảng 9 phút) |

Kết luận: từ bản sao thứ hai dựng lại được toàn bộ kho dữ liệu và các bảng đã xử lý, giống hệt bản chính.

## 4. Quy trình khi kho chính bị hỏng hoặc mất

1. `python scripts/restore.py` (hoặc `--revision vYYYY-MM-DD` để lấy một tuần cụ thể). Phải thấy dòng cuối `DAT`.
2. Nếu repo chính bị xóa: tạo lại `DragonBornRay/FluDataset` (public).
3. Đẩy bản khôi phục lên: `hf upload DragonBornRay/FluDataset restore_test/data . --repo-type dataset --exclude ".cache/*" --exclude ".hf_revision"`.
4. `python scripts/download_data.py` rồi `python scripts/verify_integrity.py` để xác nhận repo chính đã đúng.
5. Ghi sự cố vào mục 2 của tài liệu này.

## 5. Cài đặt cần có

- GitHub → Settings → Secrets and variables → Actions → Secrets:
  - `HF_TOKEN`: token fine-grained, quyền write chỉ trên `DragonBornRay/FluDataset`.
  - `HF_BACKUP_TOKEN`: token fine-grained, quyền write chỉ trên `DragonBornRay/FluDataset-backup`.
- Thiếu `HF_BACKUP_TOKEN` thì workflow vẫn cập nhật repo chính và chỉ cảnh báo "bỏ qua sao lưu".
