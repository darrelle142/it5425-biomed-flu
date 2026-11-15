# Kiểm tra bộ kiểm tra chất lượng trên dữ liệu chèn lỗi

Sinh tự động bởi `python pipelines/02_warehouse.py --steps inject` lúc 2026-11-16 00:43. Code: `src/fluwatch/warehouse/inject.py` (chèn lỗi, chấm điểm), `quality.py` (các quy tắc).

**Cách chấm.** Chạy toàn bộ quy tắc trên dữ liệu gốc (baseline: 4 vi phạm có sẵn, là vấn đề thật của dữ liệu, xem `README.md`) và trên dữ liệu bị chèn lỗi. Chỉ tính vi phạm **mới**. Một lỗi trong đáp án là *bị bắt* khi có vi phạm mới trỏ đúng ô (bang, tuần, cột); lỗi cả dòng (dòng bị xóa, dòng trùng) cần vi phạm mới ở đúng (bang, tuần). Vi phạm mới không khớp đáp án nào là *báo động giả*.

> Chưa có bộ dữ liệu lỗi của TV4 (`data/sandbox/corrupted/fact_flu_week.parquet` + `answer_key.csv`). Bảng dưới dùng bộ tự sinh cùng 4 loại lỗi; khi TV4 giao file, chạy lại lệnh trên, kết quả của TV4 sẽ đứng đầu.

## Tổng hợp

| Bộ dữ liệu | Số lỗi chèn | Bắt được | Recall | Bắt chỉ bằng quy tắc nội bộ (không cần M01–M03) | Vi phạm mới | Báo động giả |
| --- | --- | --- | --- | --- | --- | --- |
| tự sinh, seed 2026, chế độ `raw` | 509 | 509 | **100.0%** | 421 (82.7%) | 1410 | 0 |
| tự sinh, seed 2026, chế độ `consistent` | 509 | 509 | **100.0%** | 160 (31.4%) | 842 | 0 |

Chế độ `raw`: chỉ sửa ô dữ liệu, cột phái sinh giữ như cũ (lỗi xảy ra sau khi dựng bảng). Chế độ `consistent`: kẻ sửa tính lại mọi cột phái sinh cho khớp (biến trễ, `wow_pct`, `missing_*`, `cdc_level`), nên quy tắc nội bộ khó thấy hơn; lớp đối chiếu nguồn (M01–M03) vẫn phải bắt được.

**Độ ổn định qua các seed khác** (mỗi seed chèn lỗi ở vị trí khác):

| Seed | Chế độ | Lỗi chèn | Bắt được | Báo động giả | Quy tắc báo giả |
| --- | --- | --- | --- | --- | --- |
| 1 | `raw` | 510 | 510 (100.0%) | 0 | – |
| 1 | `consistent` | 510 | 510 (100.0%) | 0 | – |
| 2 | `raw` | 508 | 508 (100.0%) | 0 | – |
| 2 | `consistent` | 508 | 508 (100.0%) | 0 | – |
| 3 | `raw` | 511 | 511 (100.0%) | 0 | – |
| 3 | `consistent` | 511 | 511 (100.0%) | 0 | – |

Không có báo động giả ở mọi seed.

## tự sinh, seed 2026, chế độ `raw`

Bảng lỗi: 44921 dòng.

| Loại lỗi | Ô/dòng chèn | Bắt được | Recall | Quy tắc bắt (số lỗi) |
| --- | --- | --- | --- | --- |
| Thiếu ngẫu nhiên (ô bị xóa rải rác) (`missing_random`) | 300 | 300 | 100.0% | M03 (300), R06 (184), R05 (177), R07 (58) |
| Mất khối nhiều tuần liên tiếp (mất dòng hoặc mất cả đoạn một tín hiệu) (`missing_block`) | 69 | 69 | 100.0% | R02 (39), M03 (30), R05 (30), R06 (30) |
| Số sơ bộ (4 tuần cuối) bị sửa ±10–50% (`preliminary_revised`) | 60 | 60 | 100.0% | M03 (60), R06 (35), R09 (28), R07 (28), R03 (13) |
| Trùng dòng (`duplicate`) | 80 | 80 | 100.0% | R01 (80) |

## tự sinh, seed 2026, chế độ `consistent`

Bảng lỗi: 44921 dòng.

| Loại lỗi | Ô/dòng chèn | Bắt được | Recall | Quy tắc bắt (số lỗi) |
| --- | --- | --- | --- | --- |
| Thiếu ngẫu nhiên (ô bị xóa rải rác) (`missing_random`) | 300 | 300 | 100.0% | M03 (300) |
| Mất khối nhiều tuần liên tiếp (mất dòng hoặc mất cả đoạn một tín hiệu) (`missing_block`) | 69 | 69 | 100.0% | R02 (39), M03 (30) |
| Số sơ bộ (4 tuần cuối) bị sửa ±10–50% (`preliminary_revised`) | 60 | 60 | 100.0% | M03 (60), R09 (28), R03 (13) |
| Trùng dòng (`duplicate`) | 80 | 80 | 100.0% | R01 (80) |
