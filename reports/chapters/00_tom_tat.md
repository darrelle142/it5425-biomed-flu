<!-- Nguoi phu trach: TV1 (tong hop). Chi sua file nay. -->
<!--
HUONG DAN (phan nay khong hien trong bao cao):
- Viet bang Markdown. Muc: "## Ten muc", muc nho: "### Ten muc nho". Khong tu danh so (tu dong danh so).
- Hinh: luu reports/figures/tvX_<ten>.png (300 dpi) roi chen (duong dan tinh tu thu muc reports/):
    ![Tieu de hinh la cau ket luan, vd. Mua 2024-25 len dinh som hon trung binh 3 tuan](figures/tvX_ten.png){width=90%}
- Bang: dong tieu de bang dat ngay duoi bang, bat dau bang dau hai cham:
    | Cot 1 | Cot 2 |
    | --- | --- |
    | ... | ... |

    : Tieu de bang
- Trich dan: [@shaman2010]; them tai lieu moi vao reports/references.bib.
- So lieu trong phan ket qua lay tu ban da khoa (tag v2026-11-19 tren Hugging Face).
- Xem thu ca quyen: python reports/build_report.py
-->

# Tóm tắt {-}

<!-- 5-8 cau: bai toan, du lieu, phuong phap chinh, ket qua chinh (so lieu tu ban khoa), y nghia. -->

*(Đang viết, TV1 tổng hợp.)*

## Phân công và mức đóng góp {-}

| Thành viên | Vai trò | Công việc chính | Đóng góp |
| --- | --- | --- | --- |
| TV1 | Thu thập, tự động hóa, bảo toàn dữ liệu | 9 nguồn dữ liệu; workflow tự động hằng tuần; kiểm tra toàn vẹn, tag phiên bản, sao lưu, khôi phục; ghép báo cáo | …% |
| TV2 | Kho dữ liệu, chất lượng dữ liệu | `clean/`, `business/` star schema, DuckDB; quy tắc chất lượng 4 mức; từ điển dữ liệu, lineage | …% |
| TV3 | Mùa vụ, EDA, phân cụm | Mốc mùa, độ nặng, EDA, phân cụm bang, kiểm định (RQ1–RQ3) | …% |
| TV4 | Giả lập, yếu tố ảnh hưởng | Bảng bằng chứng, tương quan trễ, Shaman, Negative Binomial, what-if (RQ4) | …% |
| TV5 | Mô hình cảnh báo | Logistic, ROC/AUC, calibration, DeLong, backtest (RQ5) | …% |
| TV6 | Dashboard, storytelling | Streamlit 5 trang và trang Phương pháp; slide | …% |

: Phân công công việc và mức đóng góp (tổng 100%)
