# Tình hình kho dữ liệu (TV2), 16/11/2026

> 📍 [Mục lục tài liệu](README.md) · Từ điển dữ liệu: [tu_dien_du_lieu.md](tu_dien_du_lieu.md) · Quản trị dữ liệu: [quan_tri_du_lieu.md](quan_tri_du_lieu.md) · Báo cáo chất lượng: [../reports/data_quality/README.md](../reports/data_quality/README.md)

**Tóm tắt 30 giây.** Đã xong cả 5 việc của TV2: kho `clean/`, `business/` (star schema + DuckDB), bộ kiểm tra chất lượng 4 mức, bài kiểm tra trên dữ liệu chèn lỗi, và 2 tài liệu quản trị. Dữ liệu hiện tại đạt 27/28 quy tắc chất lượng; quy tắc còn lại chỉ là 4 cảnh báo do làm tròn số. Đã sửa 3 vấn đề dữ liệu: **thêm cột thì có, nhưng không cột hợp đồng nào bị đổi tên hay bỏ**. Tuy nhiên, giá trị của `ili_pct`, `lab_pct_pos` và `wval` đã thay đổi ở một số ô; ai đã chạy phân tích trên các cột này nên đọc mục 2.

## 1. Đã xong

| Việc | Kết quả | Xem ở đâu |
| --- | --- | --- |
| 1. `data/clean/` | 9 bảng, mỗi nguồn một bảng; mọi thao tác làm sạch ghi kèm số dòng | `data/clean/_clean_log.json` |
| 2. `data/business/` | `fact_flu_week` (44.880 dòng = 51 bang × 880 tuần, 90 cột), `fact_season_summary`, `dim_state`, `dim_time`, `dim_source`; file `fluwatch.duckdb` có 4 view và 8 truy vấn mẫu roll-up, drill-down, slice, dice, pivot | [reports/olap/README.md](../reports/olap/README.md) |
| 3. Kiểm tra chất lượng | 28 quy tắc ở 4 mức (giá trị, bản ghi, quan hệ, nhiều bảng) và báo cáo độ phủ bang × năm. Tổng 51 bang khớp từng ca với số toàn quốc và từng vùng HHS trong file NHSN của CDC | [reports/data_quality/README.md](../reports/data_quality/README.md) |
| 4. Dữ liệu chèn lỗi | Chèn khoảng 510 lỗi thuộc 4 loại (thiếu ngẫu nhiên, mất khối nhiều tuần, trùng dòng, số sơ bộ bị sửa): **bắt được 100%, 0 báo động giả**, thử với 4 seed × 2 chế độ | [reports/data_quality/injection_test.md](../reports/data_quality/injection_test.md) |
| 5. Tài liệu | Từ điển dữ liệu kèm lineage từng cột; người phụ trách từng nguồn; quy tắc cập nhật 4 tuần gần nhất | [tu_dien_du_lieu.md](tu_dien_du_lieu.md), [quan_tri_du_lieu.md](quan_tri_du_lieu.md) |

Lệnh chạy toàn bộ: `python pipelines/02_warehouse.py`. Bài chèn lỗi chạy riêng (khoảng 1,5 phút): `python pipelines/02_warehouse.py --steps inject`.

## 2. Thay đổi dữ liệu mọi người cần biết

| Thay đổi | Lý do | Ai bị ảnh hưởng |
| --- | --- | --- |
| **`ili_pct` trống ở 39 ô, `lab_pct_pos` trống ở 371 ô** (trước đây ghi 0) | Các tuần này có 0 lượt khám hoặc 0 mẫu xét nghiệm, tức là không có báo cáo, không phải 0% cúm. Để 0 sẽ kéo thấp mức nền và tạo ra "tuần không có cúm" giả | TV3 (mức nền), TV4, TV5 |
| **`wval`: trạm báo WVAL > 1000 bị bỏ (244 dòng trạm), trạm 100–1000 bị chặn trần ở 100 (547 dòng trạm)**; `wval` lớn nhất giờ là 100 (trước là 311) | Nguồn `State_Territory` của OK, VA có trạm báo tới 6,9 × 10⁸. Mức "Very High" của CDC bắt đầu từ 15,6. Không bỏ hẳn các trạm 100–1000 vì chúng rơi đúng vào các đợt tăng thật (OK 12/2022, MN 1/2026) | TV5, TV6 |
| **Cột mới `wval_mean`**: trung bình có trọng số thay cho trung vị | `wval` (trung vị) bằng đúng 1,0 ở 52% số bang-tuần nên phẳng lì ở mức thấp; `wval_mean` chỉ 22%. Tương quan Spearman với nhập viện: 0,65 so với 0,60; với cấp cứu: 0,70 so với 0,65 | TV5: **nên dùng `wval_mean` làm biến nước thải trong mô hình**; giữ `wval` để hiển thị |
| **Cột mới `flu_vax_pct_prev`**: độ phủ vaccine cuối mùa trước | `flu_vax_pct` là số **tháng 5 (cuối mùa)** gán cho mọi tuần của mùa. Dùng nó dự báo tuần tháng 10 là dùng thông tin chưa có lúc đó | TV4, TV5: **biến dự báo dùng `flu_vax_pct_prev`**; `flu_vax_pct` chỉ dùng để mô tả cả mùa |
| Cột phụ mới: `wval_sites_capped` (số trạm bị chặn trần), `users` trong `dim_source` | Truy vết làm sạch, quản trị | – |

## 3. Việc cần từng người

**TV1**
- Thêm `python pipelines/02_warehouse.py --strict` vào `weekly_update.yml`, chạy sau bước tải. `--strict` thoát mã 1 khi có quy tắc mức lỗi không đạt; hãy dùng nó để chặn việc đẩy dữ liệu hỏng lên Hugging Face.

**TV3**
- Giao 2 file thẳng vào `data/business/`:
  - `state_cluster.parquet` với cột `state`, `cluster_id`.
  - `season_milestones.parquet` với cột `state`, `season`, `baseline`, `onset_week`, `peak_week`, `peak_value`, `severity`, `source`.
- Lần dựng kho tiếp theo sẽ tự ghép; hiện các cột này còn trống 100%.
- Lưu ý: mùa 2009-10 chỉ có từ 01/2010 (thiếu đỉnh H1N1 tháng 10/2009), nên bỏ khỏi mức nền.

**TV4**
- **Giao bộ dữ liệu chèn lỗi trước T4 18/11.** Đặt vào `data/sandbox/corrupted/`:
  - `fact_flu_week.parquet`: cùng cột với `business/fact_flu_week`.
  - `answer_key.csv` gồm các cột `error_id, error_type, state, week, column`:
    - `error_type` là một trong `missing_random`, `missing_block`, `duplicate`, `preliminary_revised`.
    - `column` là tên cột bị sửa, hoặc `*` nếu lỗi cả dòng (dòng bị xóa hoặc bị nhân đôi).
- Mẫu đúng định dạng: `reports/data_quality/injection_key_raw.csv`. Có file là TV2 chạy lại lệnh `inject`, kết quả của TV4 sẽ đứng đầu báo cáo.
- Biến vaccine trong hồi quy: xem mục 2.

**TV5**
- Biến nước thải: dùng `wval_mean`. Biến vaccine: dùng `flu_vax_pct_prev`.
- Backtest dùng số liệu đúng như lúc công bố, lấy từ `raw/*/archive__*`, không dùng `business/`. Số liệu thật cho thấy bản công bố đầu của NHSN có 40% bang-tuần lệch quá 5% so với bản cuối ([quan_tri_du_lieu.md](quan_tri_du_lieu.md) mục 3).
- Loại các tuần 5–10/2024 khi huấn luyện, vì giai đoạn này số bệnh viện báo cáo NHSN giảm từ khoảng 90 xuống khoảng 27 mỗi bang.

**TV6**
- Trang "Sức khỏe dữ liệu" đọc `reports/data_quality/results.json` (kết quả từng quy tắc) và `coverage_state_year.csv` (độ phủ bang × năm).
- Các tuần có `is_preliminary = True` vẽ nét đứt.
- `wow_pct`, `yoy_pct` có giá trị rất lớn (tới hàng chục nghìn %) khi mẫu số nhỏ; nếu dùng cho "top 10 bang tăng nhanh nhất" thì nên lọc các bang có `rate_flu` tuần trước dưới khoảng 1.

## 4. Còn mở

- **Dữ liệu `business/` này đang ở máy TV2.** TV2 sẽ đẩy lên Hugging Face và chuyển `load.py` sang đọc `business/` trước T3 17/11 (đúng mốc kế hoạch).
- **4 cảnh báo R09** (MN mùa 2020-21): `rate_flu` và `hosp_flu` lệch hơn 5% do làm tròn ở tỷ suất rất nhỏ. Không xử lý.
- **Độ phủ**: 290/4.896 ô bang × năm thiếu quá 30%. Phần lớn là các hạn chế đã biết của nguồn: ILINet thiếu FL, LA những năm đầu và 8 bang năm 2026; xét nghiệm thiếu NY, RI; nước thải mới có từ 2022. Danh sách đầy đủ ở mục 3 của báo cáo chất lượng.
- **Đề nghị người quản lý tiến độ** bổ sung vào [han_che_du_lieu.md](han_che_du_lieu.md) 3 dòng mới ở mục 2 (số 0 giả khi mẫu số bằng 0, WVAL sai miền, vaccine cuối mùa); file đó TV2 không được sửa.
