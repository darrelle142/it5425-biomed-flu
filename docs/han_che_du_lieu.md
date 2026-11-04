# Hạn chế dữ liệu và ảnh hưởng tới các RQ

Cập nhật 04/11/2026. Mọi dữ liệu tải tự động đã đủ (kiểm tra bằng `python scripts/audit_data.py`). Các khoảng trống dưới đây do nguồn gốc không có số liệu, tải lại không khắc phục được. Không RQ nào bị chặn.

| Khoảng trống | RQ bị ảnh hưởng | Mức ảnh hưởng | Cách xử lý |
| --- | --- | --- | --- |
| ILINet thiếu 8 bang (AK, CT, HI, NY, OK, OR, SD, UT) từ 04/10/2025 đến 03/10/2026 | RQ1, RQ2, RQ3 (mùa 2025–26) | Trung bình. Khoảng 11% dân số Mỹ, riêng NY khoảng 6% | Với 8 bang này ở mùa 2025–26, xác định khởi phát và đỉnh bằng NSSP rồi NHSN (đủ 51 bang). Báo AUC và độ trễ mùa 2025–26 trên 43 bang, ghi rõ lý do |
| Xét nghiệm lâm sàng không có NY, RI | RQ1 | Thấp. NY mùa 2025–26 mất cả ILINet lẫn tỷ lệ dương tính | Dùng NSSP và NHSN thay thế; dashboard đánh dấu "suy từ nguồn khác" |
| NHSN báo cáo ít từ 5/2024 đến 10/2024 | RQ2, RQ5 | Thấp. Ngoài mùa cúm; báo cáo bắt buộc trở lại từ 11/2024 | Loại các tuần này khi huấn luyện RQ5 và khi tính mức nền |
| FluSurv-NET chỉ có 18 bang | RQ2 | Thấp. Chỉ là nguồn đối chiếu độ nặng | Thước đo độ nặng chính là tỷ lệ nhập viện NHSN |
| WVAL không có ND | RQ5 (lớp nước thải) | Rất thấp | ND để trống lớp nước thải trên bản đồ |
| Vaccine chưa có mùa 2026–27 | RQ4 | Thấp. Phân tích dùng các mùa cũ (đã đủ) | Tải tay hằng tháng theo `docs/can_tai_tay.txt` |
| DC, HI, RI chỉ có 1 đô thị | RQ4 | Rất thấp | Cột `n_cities` trong `weather_state_week` ghi rõ số thành phố |

## Quy tắc ưu tiên nguồn khi thiếu ILINet

NSSP (cấp cứu) trước, rồi đến NHSN (nhập viện).

## Ảnh hưởng theo RQ

- **RQ1, RQ2:** làm được đầy đủ; mùa 2025–26 có 8 bang dùng nguồn thay thế.
- **RQ3:** mùa 2025–26 nên chạy phân cụm trên NSSP cho cả 51 bang.
- **RQ4:** gần như không ảnh hưởng.
- **RQ5:** không ảnh hưởng đáng kể. AUC với nhãn mức Cao của CDC: 0,98 (trước 1 tuần), 0,95 (trước 2 tuần).
