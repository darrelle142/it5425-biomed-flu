# Notebooks

Notebook dùng để khám phá và trình bày. Code chạy chính thức nằm trong `src/fluwatch/<mảng>/` và chạy bằng `python pipelines/0X_*.py` (xem [`docs/phan_cong.md`](../docs/phan_cong.md)).

Đặt tên theo `<số>_<chủ đề>_<tên người>.ipynb`, ví dụ `03_moc_mua_tenban.ipynb`.

| Số | Chủ đề | Người phụ trách |
| --- | --- | --- |
| 02 | Kho dữ liệu: kiểm tra `business/`, truy vấn OLAP bằng DuckDB | TV2 |
| 03 | Mốc mùa dịch, độ nặng, EDA, phân cụm bang (RQ1–RQ3) | TV3 |
| 04 | Yếu tố ảnh hưởng: tương quan trễ, kiểm chứng Shaman 2010, Negative Binomial, giả lập kiểm tra phương pháp (RQ4) | TV4 |
| 05 | Mô hình cảnh báo, ROC, AUC, calibration, backtest (RQ5) | TV5 |

Quy ước:

- **Đọc dữ liệu qua hàm chung của TV2** (`pip install -e .` một lần, rồi `from fluwatch.warehouse.load import load_flu_week`). Hàm tự đọc `data/samples/` đến 16/11 và `data/business/` từ 17/11; tên cột ở [`docs/ke_hoach.md`](../docs/ke_hoach.md) mục 4.1. Không đọc từ thư mục draft bên ngoài.
- Xóa output lớn trước khi commit (Kernel > Restart & Clear Output) để repo nhẹ.
- Dữ liệu giả lập chỉ lưu trong `data/sandbox/` và phải có cột `is_synthetic`, `sim_scenario`, `sim_seed`.
- Hình dùng trong báo cáo lưu vào `reports/figures/` (PNG 300 dpi). Sau ngày khóa số liệu 19/11 không chạy lại notebook để ra số mới.
