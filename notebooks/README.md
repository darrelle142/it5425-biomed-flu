# Notebooks

Đặt tên theo `<số>_<chủ đề>_<tên người>.ipynb`, ví dụ `01_moc_mua_dung.ipynb`.

| Số | Chủ đề | Người phụ trách |
| --- | --- | --- |
| 01 | Mốc mùa dịch, độ nặng (RQ1, RQ2) | Người 4 |
| 02 | EDA, phân cụm bang, tương quan trễ (RQ3, RQ4) | Người 4 |
| 03 | Kiểm tra phương pháp và cỡ mẫu bằng giả lập | Người 5 |
| 04 | Negative Binomial trên ILINet (RQ4) | Người 5 |
| 05 | Mô hình cảnh báo, ROC, AUC, calibration (RQ5) | Người 5 |

Quy ước:

- Đọc dữ liệu từ `data/samples/` hoặc `data/reference/`, đường dẫn tương đối từ gốc repo. Không đọc từ thư mục draft bên ngoài.
- Xóa output lớn trước khi commit (Kernel > Restart & Clear Output) để repo nhẹ.
- Dữ liệu giả lập chỉ lưu trong `data/sandbox/` và phải có cột `is_synthetic`, `sim_scenario`, `sim_seed`.
