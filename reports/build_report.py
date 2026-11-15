"""Ghep cac chuong trong reports/chapters/ thanh quyen bao cao Word va PDF.

Cach chay (tu thu muc goc cua repo, sau `pip install -r reports/requirements.txt`):
    python reports/build_report.py           # ca .docx va .pdf
    python reports/build_report.py --docx    # chi Word (nhanh, khong can LaTeX)
    python reports/build_report.py --pdf     # chi PDF (can xelatex: MiKTeX hoac TeX Live)

Ket qua: reports/build/bao_cao.docx, reports/build/bao_cao.pdf (khong commit).
- Cac chuong ghep theo thu tu ten file (00_, 01_, 02_1_, 02_2_, ..., 99_).
- Tieu de, tac gia, dinh dang PDF: reports/metadata.yaml. Dinh dang Word: reports/templates/reference.docx.
- Trich dan [@key] lay tu reports/references.bib, tu sinh muc Tai lieu tham khao.
- Hinh trong chuong viet duong dan tinh tu reports/ (vd. figures/tv3_season_overlay.png).
Neu khong co xelatex: mo file .docx bang Word -> File > Save As > PDF.
"""
import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pypandoc

R = Path(__file__).resolve().parent
OUT = R / "build"
COMMON = ["--from", "markdown", "--metadata-file", str(R / "metadata.yaml"), "--citeproc",
          "--bibliography", str(R / "references.bib"), "--resource-path", str(R), "--toc", "--toc-depth", "3",
          "--number-sections", "--standalone"]


def chapters():
    files = sorted((R / "chapters").glob("*.md"))
    if not files:
        sys.exit("Chua co chuong nao trong reports/chapters/.")
    return files


def check_figures(files):
    """Bao hinh duoc chen nhung khong co file."""
    missing = []
    for f in files:
        text = re.sub(r"<!--.*?-->", "", f.read_text(encoding="utf-8"), flags=re.S)  # bo phan huong dan
        for path in re.findall(r"!\[[^\]]*\]\(([^)\s]+)", text):
            if not (R / path).exists():
                missing.append(f"{f.name}: {path}")
    for m in missing:
        print("  THIEU HINH", m)
    return missing


def pandoc(args):
    r = subprocess.run([pypandoc.get_pandoc_path(), *args], cwd=R, capture_output=True, text=True, encoding="utf-8")
    for line in (r.stderr or "").splitlines():
        print("  pandoc:", line)
    return r.returncode


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docx", action="store_true")
    ap.add_argument("--pdf", action="store_true")
    a = ap.parse_args()
    want_docx = a.docx or not a.pdf
    want_pdf = a.pdf or not a.docx
    files = chapters()
    print("Chuong:", ", ".join(f.name for f in files))
    check_figures(files)
    OUT.mkdir(exist_ok=True)
    inputs = [str(f) for f in files]
    ok = True

    if want_docx:
        ref = R / "templates" / "reference.docx"
        args = [*COMMON, "--reference-doc", str(ref), "-o", str(OUT / "bao_cao.docx"), *inputs]
        ok &= pandoc(args) == 0
        print("Word:", OUT / "bao_cao.docx" if ok else "LOI")

    if want_pdf:
        engine = shutil.which("xelatex")
        if not engine:
            print("PDF: bo qua (khong thay xelatex). Mo bao_cao.docx bang Word va luu thanh PDF.")
        else:
            args = [*COMMON, "--pdf-engine", engine, "--top-level-division", "chapter",
                    "-o", str(OUT / "bao_cao.pdf"), *inputs]
            code = pandoc(args)
            ok &= code == 0
            print("PDF:", OUT / "bao_cao.pdf" if code == 0 else "LOI (xem thong bao pandoc o tren)")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
