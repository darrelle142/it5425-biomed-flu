"""Tao reports/templates/reference.docx: khuon dinh dang Word cho quyen bao cao.

Chay lai khi muon doi phong chu, co chu, le trang:
    python reports/templates/make_reference_docx.py
Lay khuon mac dinh cua pandoc roi chinh: Times New Roman 13, gian dong 1,3, can deu hai ben,
le trang tren/duoi 2 cm, trai 3 cm, phai 2 cm (quy cach bao cao thuong dung o Viet Nam).
"""
import subprocess
from pathlib import Path

import pypandoc
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

HERE = Path(__file__).resolve().parent
OUT = HERE / "reference.docx"
FONT = "Times New Roman"


def set_font(style, size=None, bold=None, color=RGBColor(0, 0, 0)):
    style.font.name = FONT
    rpr = style.element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = rpr.makeelement(qn("w:rFonts"), {})
        rpr.append(rfonts)
    for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rfonts.set(qn(attr), FONT)
    for attr in ("w:asciiTheme", "w:hAnsiTheme", "w:cstheme", "w:eastAsiaTheme"):
        rfonts.attrib.pop(qn(attr), None)
    if size:
        style.font.size = Pt(size)
    if bold is not None:
        style.font.bold = bold
    if color is not None:
        style.font.color.rgb = color


def main():
    raw = subprocess.run([pypandoc.get_pandoc_path(), "--print-default-data-file", "reference.docx"],
                         capture_output=True, check=True).stdout
    OUT.write_bytes(raw)
    doc = Document(OUT)
    st = {s.name: s for s in doc.styles}  # tra theo ten hien thi
    for name in ("Normal", "Body Text", "First Paragraph", "Compact", "Block Text", "Footnote Text",
                 "Bibliography", "Caption", "Table Caption", "Image Caption", "TOC Heading"):
        if name in st:
            set_font(st[name], 13 if name in ("Normal", "Body Text", "First Paragraph", "Bibliography") else None)
    for name in ("Body Text", "First Paragraph"):
        pf = st[name].paragraph_format
        pf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        pf.line_spacing = 1.3
        pf.space_after = Pt(6)
    sizes = {"Title": 20, "Subtitle": 15, "Heading 1": 16, "Heading 2": 14, "Heading 3": 13, "Heading 4": 13}
    for name, size in sizes.items():
        set_font(st[name], size, bold=True)
        st[name].paragraph_format.space_before = Pt(12 if name.startswith("Heading") else 0)
    st["Heading 1"].paragraph_format.page_break_before = True  # moi chuong sang trang moi
    for name in ("Title", "Subtitle", "Author", "Date"):
        if name in st:
            set_font(st[name], sizes.get(name))
            st[name].paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for name in ("Caption", "Table Caption", "Image Caption"):
        if name in st:
            st[name].font.italic = True
            st[name].font.size = Pt(12)
            st[name].paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for section in doc.sections:
        section.page_height, section.page_width = Cm(29.7), Cm(21.0)  # A4
        section.top_margin = section.bottom_margin = Cm(2)
        section.left_margin, section.right_margin = Cm(3), Cm(2)
    doc.save(OUT)
    print("Da tao", OUT)


if __name__ == "__main__":
    main()
