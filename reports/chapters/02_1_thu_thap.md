<!-- Nguoi phu trach: TV1. Chi sua file nay. -->
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

# Thu thập và quản trị dữ liệu

## Thu thập, tự động hóa và bảo toàn dữ liệu thô

<!-- Muc 2.1 (TV1). Muc 2.2-2.4 do TV2 viet trong 02_2_kho_du_lieu.md. Mo dau bang hinh so do pipeline. -->

*(Đang viết, TV1.)*

### Thu thập từ 9 nguồn

<!-- Delphi V5 (ban chup + lich su sua so), Open-Meteo 236 thanh pho, EPA, CDC bi chan tu Viet Nam qua GitHub Actions. -->

*(Đang viết, TV1.)*

### Lưu trữ nguyên trạng và nhật ký nguồn gốc

<!-- raw/<nguon>/<ngay tai>/, manifest.jsonl (URL, thoi diem, sha256), khong ghi de. -->

*(Đang viết, TV1.)*

### Tự động hóa hằng tuần

<!-- crawl_cdc.yml, weekly_update.yml, pipelines/01_ingest.py; lich sang som, --only-if-new, gioi han thoi gian, buoc mem; anh chup lan chay. -->

*(Đang viết, TV1.)*

### Bảo toàn dữ liệu thô

<!-- docs/bao_toan_du_lieu.md: kiem tra toan ven 3 chieu, cong chat luong, tag phien ban, ban sao rieng tu, chay thu khoi phuc; su co 10/11 va cach sua. -->

*(Đang viết, TV1.)*
