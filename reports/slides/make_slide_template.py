"""Tao khuon slide chung reports/slides/khuon_slide.pptx (16:9) cho TV6 va moi thanh vien.

Chay lai khi muon doi mau, phong chu:
    python reports/slides/make_slide_template.py
Theo yeu cau mon hoc: slide dau tien mo ta cong viec va % dong gop cua tung thanh vien.
Mau nhan Okabe-Ito (than thien voi nguoi mu mau), cung bang mau voi hinh va dashboard.
"""
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Emu, Pt

OUT = Path(__file__).resolve().parent / "khuon_slide.pptx"
FONT = "Arial"
INK = RGBColor(0x22, 0x22, 0x22)
MUTED = RGBColor(0x66, 0x66, 0x66)
BLUE = RGBColor(0x00, 0x72, 0xB2)      # Okabe-Ito: xanh duong (mau chinh)
ORANGE = RGBColor(0xE6, 0x9F, 0x00)    # cam (nhan manh)
VERMILION = RGBColor(0xD5, 0x5E, 0x00)  # do cam (canh bao)
LIGHT = RGBColor(0xF2, 0xF5, 0xF8)

prs = Presentation()
prs.slide_width, prs.slide_height = Emu(12192000), Emu(6858000)  # 13,33 x 7,5 in (16:9)
W, H = prs.slide_width, prs.slide_height
BLANK = prs.slide_layouts[6]
M = Emu(457200)  # le 0,5 in


def text(slide, x, y, w, h, s, size=18, bold=False, color=INK, align=PP_ALIGN.LEFT):
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    lines = s if isinstance(s, list) else [s]
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        r = p.add_run()
        r.text = line
        r.font.name, r.font.size, r.font.bold, r.font.color.rgb = FONT, Pt(size), bold, color
        p.space_after = Pt(6)
    return tb


def bar(slide, color=BLUE):
    s = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, W, Emu(91440))
    s.fill.solid()
    s.fill.fore_color.rgb = color
    s.line.fill.background()


def footer(slide, n):
    text(slide, M, H - Emu(420000), W - 2 * M, Emu(300000),
         f"Dashboard giám sát và cảnh báo sớm mùa cúm · {n}", size=10, color=MUTED, align=PP_ALIGN.RIGHT)


def content(title, bullets, n, note):
    s = prs.slides.add_slide(BLANK)
    bar(s)
    text(s, M, Emu(300000), W - 2 * M, Emu(900000), title, size=28, bold=True)
    text(s, M, Emu(1300000), W - 2 * M, H - Emu(2000000), bullets, size=20)
    footer(s, n)
    s.notes_slide.notes_text_frame.text = note
    return s


# 1. Phan cong va % dong gop (yeu cau mon hoc: slide dau tien)
s = prs.slides.add_slide(BLANK)
bar(s)
text(s, M, Emu(250000), W - 2 * M, Emu(700000), "Hệ thống dashboard giám sát và cảnh báo sớm mùa cúm theo bang ở Mỹ",
     size=26, bold=True)
text(s, M, Emu(850000), W - 2 * M, Emu(400000), "Phân công công việc và mức đóng góp", size=18, color=BLUE, bold=True)
rows = [("Thành viên", "Vai trò", "Công việc chính", "Đóng góp"),
        ("TV1 · Đặng Trung Hiếu", "Thu thập, tự động hóa, bảo toàn dữ liệu", "9 nguồn; workflow hằng tuần; toàn vẹn, tag, sao lưu; ghép báo cáo", "…%"),
        ("TV2 · [Họ tên]", "Kho dữ liệu, chất lượng", "clean/, business/ star schema, DuckDB; quy tắc chất lượng", "…%"),
        ("TV3 · [Họ tên]", "Mùa vụ, EDA, phân cụm", "Mốc mùa, độ nặng, phân cụm bang (RQ1–RQ3)", "…%"),
        ("TV4 · [Họ tên]", "Giả lập, yếu tố ảnh hưởng", "Tương quan trễ, Shaman, Negative Binomial (RQ4)", "…%"),
        ("TV5 · [Họ tên]", "Mô hình cảnh báo", "Logistic, ROC/AUC, calibration, backtest (RQ5)", "…%"),
        ("TV6 · [Họ tên]", "Dashboard, storytelling", "Streamlit 5 trang + Phương pháp; slide", "…%")]
tbl = s.shapes.add_table(len(rows), 4, M, Emu(1350000), W - 2 * M, Emu(4600000)).table
for j, w in enumerate([0.2, 0.25, 0.45, 0.1]):
    tbl.columns[j].width = int((W - 2 * M) * w)
for i, row in enumerate(rows):
    for j, val in enumerate(row):
        c = tbl.cell(i, j)
        c.text = val
        p = c.text_frame.paragraphs[0]
        p.runs[0].font.name, p.runs[0].font.size = FONT, Pt(14 if i else 15)
        p.runs[0].font.bold = i == 0
        p.runs[0].font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF) if i == 0 else INK
        c.fill.solid()
        c.fill.fore_color.rgb = BLUE if i == 0 else (LIGHT if i % 2 else RGBColor(0xFF, 0xFF, 0xFF))
footer(s, 1)
s.notes_slide.notes_text_frame.text = "Yeu cau mon hoc: slide dau tien ghi cong viec va % dong gop. Dien ho ten va %, tong 100%."

# 2. Bai toan va cau hoi nghien cuu
content("Cán bộ y tế cần biết sớm mùa cúm năm nay đến đâu",
        ["RQ1. Mùa cúm đã bắt đầu chưa, đang ở giai đoạn nào?",
         "RQ2. Sớm hay muộn, nhẹ hay nặng so với các mùa trước?",
         "RQ3. Bang nào lên trước, bang nào giống nhau?",
         "RQ4. Độ ẩm, PM2.5, vaccine, kỳ nghỉ lễ đi kèm mùa cúm thế nào?",
         "RQ5. 1–2 tuần tới có vượt ngưỡng báo động không?"], 2,
        "Tieu de slide la cau ket luan (khong phai ten chu de). Moi slide mot y chinh.")

# 3. Slide chuyen phan
s = prs.slides.add_slide(BLANK)
bg = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, W, H)
bg.fill.solid()
bg.fill.fore_color.rgb = BLUE
bg.line.fill.background()
text(s, M, Emu(2600000), W - 2 * M, Emu(1000000), "Phần 2 · Dữ liệu", size=36, bold=True,
     color=RGBColor(0xFF, 0xFF, 0xFF))
text(s, M, Emu(3500000), W - 2 * M, Emu(600000), "Thay bằng tên phần: Dữ liệu, Mùa vụ, Yếu tố, Cảnh báo, Dashboard",
     size=18, color=RGBColor(0xFF, 0xFF, 0xFF))

# 4. Slide hinh + thong diep
s = prs.slides.add_slide(BLANK)
bar(s)
text(s, M, Emu(300000), W - 2 * M, Emu(900000), "Tiêu đề là câu kết luận: mùa 2024-25 lên đỉnh sớm hơn trung bình 3 tuần",
     size=26, bold=True)
ph = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, M, Emu(1300000), int((W - 2 * M) * 0.66), Emu(4700000))
ph.fill.solid()
ph.fill.fore_color.rgb = LIGHT
ph.line.color.rgb = MUTED
ph.text_frame.text = "Chèn hình từ reports/figures/tvX_<ten>.png"
ph.text_frame.paragraphs[0].runs[0].font.color.rgb = MUTED
ph.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER
text(s, M + int((W - 2 * M) * 0.69), Emu(1300000), int((W - 2 * M) * 0.31), Emu(4700000),
     ["Điểm chính 1", "Điểm chính 2", "Nguồn: ..."], size=18)
footer(s, 4)

# 5. Ket luan
content("Kết luận và đề xuất",
        ["Trả lời từng RQ bằng một câu, kèm số liệu từ bản khóa v2026-11-19",
         "Hạn chế chính của dữ liệu và mô hình",
         "Liên hệ với Việt Nam"], 5, "")

# Chu thich mau
s = prs.slides.add_slide(BLANK)
bar(s)
text(s, M, Emu(300000), W - 2 * M, Emu(800000), "Bảng màu chung (Okabe-Ito) — xóa slide này trước khi trình bày",
     size=24, bold=True)
for i, (name, col) in enumerate([("Chính #0072B2", BLUE), ("Nhấn mạnh #E69F00", ORANGE), ("Cảnh báo #D55E00", VERMILION),
                                 ("Phụ #56B4E9", RGBColor(0x56, 0xB4, 0xE9)), ("Tốt #009E73", RGBColor(0x00, 0x9E, 0x73))]):
    sw = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, M + i * Emu(2250000), Emu(1600000), Emu(2000000), Emu(1200000))
    sw.fill.solid()
    sw.fill.fore_color.rgb = col
    sw.line.fill.background()
    text(s, M + i * Emu(2250000), Emu(2900000), Emu(2000000), Emu(500000), name, size=14)

prs.save(OUT)
print("Da tao", OUT)
