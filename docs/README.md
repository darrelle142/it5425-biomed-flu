# Mục lục tài liệu

Cập nhật 14/11/2026. Mọi tài liệu của nhóm nằm trong `docs/`. Mỗi file có một việc riêng, không trùng nhau; đầu mỗi file có dòng 📍 để quay lại đây.

## Bắt đầu ở đây (ai cũng đọc, khoảng 20 phút)

| Thứ tự | File | Đọc để biết |
| --- | --- | --- |
| 1 | [ke_hoach.md](ke_hoach.md) | **Kế hoạch hiện hành duy nhất.** Mục 1 tóm tắt trong 1 phút; mục 4 tên file, tên cột mọi người dùng chung; mục 5 lịch từng ngày của mình |
| 2 | [phan_cong.md](phan_cong.md) | Đoạn "Gửi Thành viên X" của mình: việc cụ thể, đầu vào, sản phẩm nộp, chương báo cáo |
| 3 | [han_che_du_lieu.md](han_che_du_lieu.md) | Dữ liệu thiếu ở đâu và xử lý thế nào, để không ra kết luận sai |
| 4 | [yeu_cau_mon_hoc.md](yeu_cau_mon_hoc.md) | Topic được giao, cách nộp, tiêu chí chấm |

Cách tải dữ liệu và chạy code: [README của repo](../README.md).

## Tra cứu khi cần

| File | Dùng khi |
| --- | --- |
| [ke_hoach_v2.docx](ke_hoach_v2.docx) | Cần định nghĩa và phương pháp gốc (mức nền, tuần khởi phát, quy tắc chất lượng, từ điển dữ liệu, thiết kế dashboard). Các điểm đã thay đổi: [ke_hoach.md](ke_hoach.md) mục 10 |
| [ke_hoach_tu_dong_crawl_cdc.md](ke_hoach_tu_dong_crawl_cdc.md) | Tài liệu kỹ thuật về thu thập dữ liệu: nguồn nào lấy ở đâu, cần VPN không (mục 1); cách tải tự động nguồn CDC bị chặn (mục 2); dữ liệu đủ cho RQ nào (mục 8); **dựng lại dữ liệu khi lỗi** (mục 9) |
| [bao_toan_du_lieu.md](bao_toan_du_lieu.md) | Cơ chế bảo toàn dữ liệu thô (kiểm tra toàn vẹn, tag phiên bản, sao lưu) và **quy trình khôi phục khi kho hỏng** |
| [tv4/ap_dung_kien_thuc_mon_hoc.md](tv4/ap_dung_kien_thuc_mon_hoc.md) | TV4: kiến thức bài giảng áp dụng cho từng việc |
| [../data/README.md](../data/README.md) | Thẻ dữ liệu (cũng là trang Hugging Face): mỗi thư mục `raw/`, mỗi bảng `samples/` chứa gì |
| [../notebooks/README.md](../notebooks/README.md) | Quy ước đặt tên và đọc dữ liệu trong notebook |

## Đọc thêm theo vai trò

| TV | Sau 4 file đầu, đọc thêm |
| --- | --- |
| 1 Thu thập, bảo toàn | [ke_hoach_tu_dong_crawl_cdc.md](ke_hoach_tu_dong_crawl_cdc.md), [bao_toan_du_lieu.md](bao_toan_du_lieu.md) |
| 2 Kho dữ liệu | [ke_hoach.md](ke_hoach.md) mục 4 (hợp đồng phải làm đúng); kế hoạch v2 mục 5–6; [ke_hoach_tu_dong_crawl_cdc.md](ke_hoach_tu_dong_crawl_cdc.md) mục 8 (lỗi cần làm sạch); [../data/README.md](../data/README.md) |
| 3 Mùa vụ, EDA | Kế hoạch v2 mục 6 (định nghĩa mức nền, khởi phát, đỉnh), mục 9.1 |
| 4 Yếu tố ảnh hưởng | Kế hoạch v2 mục 7, 8; [tv4/ap_dung_kien_thuc_mon_hoc.md](tv4/ap_dung_kien_thuc_mon_hoc.md) |
| 5 Cảnh báo, ROC | Kế hoạch v2 mục 6 (nhãn), 7.2, 8 (tầng 3), 9.1; [ke_hoach_tu_dong_crawl_cdc.md](ke_hoach_tu_dong_crawl_cdc.md) mục 8 (file lịch sử sửa số để backtest) |
| 6 Dashboard | Kế hoạch v2 mục 1, 9.2, 9.3; [ke_hoach.md](ke_hoach.md) mục 4.2 (file kết quả để vẽ) |
| Quản lý tiến độ | [ke_hoach.md](ke_hoach.md) mục 6 (đường găng), 9 (bảng kiểm) |

## Quy tắc cho tài liệu

- Kế hoạch và lịch chỉ ghi ở [ke_hoach.md](ke_hoach.md); file khác trỏ tới đó, không chép lại.
- Chỉ người quản lý tiến độ sửa file trong `docs/`, trừ: `bao_toan_du_lieu.md`, `ke_hoach_tu_dong_crawl_cdc.md` (TV1 giữ); `tu_dien_du_lieu.md`, `quan_tri_du_lieu.md` (TV2 tạo và giữ, sản phẩm phải nộp); `tv4/` (TV4 giữ). File mới thì thêm một dòng vào mục lục này.
- Tài liệu hết dùng thì xóa, lịch sử vẫn còn trong git.
