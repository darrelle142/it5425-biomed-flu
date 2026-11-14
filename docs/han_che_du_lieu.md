# Hạn chế dữ liệu và ảnh hưởng tới các RQ

> 📍 [Mục lục tài liệu](README.md) · Thẻ dữ liệu: [../data/README.md](../data/README.md)

Cập nhật 14/11/2026 (bổ sung các điểm phát hiện khi kiểm tra lại dữ liệu ngày 08/11; số liệu trên Hugging Face đến tuần kết thúc 07/11/2026 (cập nhật 14/11)). Mọi dữ liệu tải tự động đã đủ (kiểm tra bằng `python scripts/audit_data.py`). Các khoảng trống dưới đây do nguồn gốc không có số liệu, tải lại không khắc phục được. Không RQ nào bị chặn.

| Khoảng trống | RQ bị ảnh hưởng | Mức ảnh hưởng | Cách xử lý |
| --- | --- | --- | --- |
| ILINet thiếu 8 bang (AK, CT, HI, NY, OK, OR, SD, UT) từ 04/10/2025 đến 03/10/2026 | RQ1, RQ2, RQ3 (mùa 2025–26) | Trung bình. Khoảng 11% dân số Mỹ, riêng NY khoảng 6% | Với 8 bang này ở mùa 2025–26, xác định khởi phát và đỉnh bằng NSSP rồi NHSN (đủ 51 bang). Báo AUC và độ trễ mùa 2025–26 trên 43 bang, ghi rõ lý do |
| Xét nghiệm lâm sàng không có NY, RI | RQ1 | Thấp. NY mùa 2025–26 mất cả ILINet lẫn tỷ lệ dương tính | Dùng NSSP và NHSN thay thế; dashboard đánh dấu "suy từ nguồn khác" |
| NHSN báo cáo ít từ 5/2024 đến 10/2024 | RQ2, RQ5 | Thấp. Ngoài mùa cúm; báo cáo bắt buộc trở lại từ 11/2024 | Loại các tuần này khi huấn luyện RQ5 và khi tính mức nền |
| FluSurv-NET chỉ có 18 bang | RQ2 | Thấp. Chỉ là nguồn đối chiếu độ nặng | Thước đo độ nặng chính là tỷ lệ nhập viện NHSN |
| WVAL không có ND | RQ5 (lớp nước thải) | Rất thấp | ND để trống lớp nước thải trên bản đồ |
| Vaccine chưa có mùa 2026–27 | RQ4 | Thấp. Phân tích dùng các mùa cũ (đã đủ) | Workflow `crawl_cdc.yml` tự tải khi CDC cập nhật; dự phòng theo `docs/ke_hoach_tu_dong_crawl_cdc.md` mục 9.4 |
| DC, HI, RI chỉ có 1 đô thị | RQ4 | Rất thấp | Cột `n_cities` trong `weather_state_week` ghi rõ số thành phố |
| ILINet thiếu FL từ 2010 đến 2021, LA từ 2010 đến 2016 | RQ1–RQ4 (mức nền, phân cụm, Shaman, Negative Binomial) | Trung bình với FL (bang đông dân), thấp với LA | Loại 2 bang ở các mùa thiếu; ghi rõ số bang thực dùng trong từng phân tích |
| Vaccine trống ở nguồn CDC: MS mùa 2025–26; DC, NJ mùa 2018–19 (chỉ có nhóm trẻ em tháng 7); DC mùa 2017–18 chỉ có đến tháng 11 | RQ4 | Thấp | Để trống, không nội suy; ghi chú trong Chương 4 |
| Vaccine CA mùa 2013–14: tháng 5 là "NR", số cuối có là tháng 11 (42,6%) | RQ4 | Rất thấp | Khi làm sạch, lấy tháng cuối có số và gắn cờ |
| EPA PM2.5 có 8 tuần trung bình âm (MT, 2026, chỉ 1 trạm) | RQ4 | Rất thấp | Đặt thành thiếu, ghi log (quy tắc chất lượng mức giá trị) |
| Có vùng lãnh thổ lẫn vào bảng: PR trong `epa_pm25_state_week`; GU, VI trong `wval_state_week` | Mọi RQ khi ghép | Rất thấp nếu lọc | Lọc về 50 bang + DC khi dựng `clean/` |
| Cột thời tiết trong `samples/state_week_sample` chỉ lấy thành phố lớn nhất mỗi bang (lệch trung bình 0,72 °C, 0,35 g/m³ so với bản 3–5 thành phố) | RQ4 | Trung bình nếu dùng nhầm | Luôn lấy thời tiết từ `samples/weather_state_week` (hoặc `business/` từ 16/11) |

## Quy tắc ưu tiên nguồn khi thiếu ILINet

NSSP (cấp cứu) trước, rồi đến NHSN (nhập viện).

## Ảnh hưởng theo RQ

- **RQ1, RQ2:** làm được đầy đủ; mùa 2025–26 có 8 bang dùng nguồn thay thế.
- **RQ3:** mùa 2025–26 nên chạy phân cụm trên NSSP cho cả 51 bang.
- **RQ4:** gần như không ảnh hưởng, với điều kiện lấy thời tiết đúng bảng và loại FL, LA ở các mùa thiếu ILINet.
- **RQ5:** không ảnh hưởng đáng kể. AUC với nhãn mức Cao của CDC: 0,98 (trước 1 tuần), 0,95 (trước 2 tuần).
