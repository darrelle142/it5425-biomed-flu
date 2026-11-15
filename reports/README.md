# Quyển báo cáo và slide

Người ghép: TV1. Mỗi người **chỉ sửa file chương của mình**; TV1 ghép thành Word và PDF.

## Cấu trúc

```
reports/
├── chapters/                    mỗi chương một file Markdown, ghép theo thứ tự tên file
│   ├── 00_tom_tat.md            Tóm tắt + bảng phân công, % đóng góp      TV1 (tổng hợp)
│   ├── 01_bai_toan.md           Chương 1: bài toán, người dùng, RQ, dữ liệu   TV1
│   ├── 02_1_thu_thap.md         Chương 2.1: thu thập, tự động hóa, bảo toàn   TV1
│   ├── 02_2_kho_du_lieu.md      Chương 2.2–2.4: data lake, star schema, chất lượng   TV2
│   ├── 03_mua_vu.md             Chương 3: mùa vụ, EDA, phân cụm               TV3
│   ├── 04_yeu_to.md             Chương 4: yếu tố ảnh hưởng, giả lập           TV4
│   ├── 05_canh_bao.md           Chương 5: mô hình cảnh báo, ROC               TV5
│   ├── 06_dashboard.md          Chương 6: dashboard, storytelling             TV6
│   ├── 07_ket_luan.md           Chương 7: kết luận, liên hệ Việt Nam          TV6
│   └── 99_tai_lieu_tham_khao.md tự sinh từ references.bib (không sửa)
├── figures/                     hình cho báo cáo: tvX_<ten>.png, 300 dpi
├── references.bib               tài liệu tham khảo chung (ai cũng thêm được)
├── metadata.yaml                tên đề tài, thành viên, khổ giấy, phông chữ (TV1)
├── templates/reference.docx     khuôn định dạng Word (tạo bằng make_reference_docx.py)
├── slides/khuon_slide.pptx      khuôn slide chung 16:9 (tạo bằng make_slide_template.py)
├── build_report.py              ghép các chương → build/bao_cao.docx, build/bao_cao.pdf
└── build/                       kết quả ghép (không commit)
```

## Viết chương

Mở file của mình trong `chapters/`. Phần hướng dẫn trong `<!-- ... -->` ở đầu file không hiện trong báo cáo.

- **Mục**: `## Tên mục`, mục nhỏ `### Tên mục nhỏ`. Không tự đánh số, số chương và mục tự sinh.
- **Hình**: lưu `figures/tvX_<ten>.png` rồi chèn
  `![Tiêu đề là câu kết luận](figures/tvX_ten.png){width=90%}`
- **Bảng**: bảng Markdown, dòng tiêu đề bảng đặt ngay dưới bảng, bắt đầu bằng `: `.
- **Trích dẫn**: `[@shaman2010]`. Tài liệu mới thì thêm vào `references.bib` (kiểm tra tác giả, năm, DOI).
- **Số liệu kết quả** lấy từ bản đã khóa (tag `v2026-11-19` trên Hugging Face).
- TV2 viết tiếp Chương 2 nên `02_2_kho_du_lieu.md` **không có tiêu đề cấp 1** (`#`), chỉ bắt đầu từ `##`.

Hạn (theo `docs/ke_hoach.md`): phần dữ liệu và phương pháp viết từ 15/11; nộp chương cho TV1 trước **12:00 thứ Sáu 20/11** bằng Pull Request.

## Xem thử quyển báo cáo

```bash
pip install -r reports/requirements.txt     # một lần: pandoc (đi kèm pypandoc_binary), python-docx, python-pptx
python reports/build_report.py --docx       # nhanh: reports/build/bao_cao.docx
python reports/build_report.py              # Word + PDF (PDF cần xelatex: MiKTeX hoặc TeX Live)
```

Script báo các hình được chèn mà chưa có file (`THIEU HINH`). Không có xelatex thì mở `bao_cao.docx` bằng Word → File → Save As → PDF.

## Slide

`slides/khuon_slide.pptx` (16:9, phông Arial, màu Okabe-Ito) gồm:
1. **Phân công và % đóng góp**: yêu cầu môn học, phải là slide đầu tiên.
2. Câu hỏi nghiên cứu.
3. Slide chuyển phần.
4. Slide hình kèm thông điệp: tiêu đề là câu kết luận, hình bên trái, 2–3 điểm chính bên phải.
5. Kết luận.
6. Bảng màu chung (xóa trước khi trình bày).

Mỗi người gửi 1–2 slide nội dung của mình cho TV6 theo khuôn này.
