<!-- Nguoi phu trach: TV3. Chi sua file nay. -->
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
- So lieu trong phan ket qua lay tu ban da khoa (tag v2026-11-26 tren Hugging Face).
- Xem thu ca quyen: python reports/build_report.py
- BAN NHAP do TV1 soan 24/11/2026 tu ket qua python pipelines/03_season_eda.py (business/ tag v2026-11-22).
  TV3 doc lai, sua van phong, bo sung; sau khi khoa so lieu 26/11 chay lai pipeline va cap nhat cac con so.
  So lieu goc: data/business/season_insights.json, season_signal_lead.csv, hhs_kruskal_results.csv, hhs_dunn_posthoc.csv.
-->

# Mô tả mùa vụ, khám phá dữ liệu và phân cụm

Chương này trả lời ba câu hỏi: mùa cúm đang ở giai đoạn nào (RQ1), năm nay sớm hay muộn, nặng hay nhẹ so với các năm trước (RQ2), và bang nào lên trước, những bang nào có mùa cúm giống nhau (RQ3). Mọi số liệu lấy từ kho `business/` qua `load_flu_week()` và được tính bằng `python pipelines/03_season_eda.py`. Kết quả xuất ra `season_milestones`, `season_phase`, `state_cluster` để Chương 4, Chương 5 và dashboard dùng chung một định nghĩa.

## Định nghĩa mốc mùa

Một mùa cúm bắt đầu từ tuần MMWR 40 (`season_week` = 1). Với mỗi bang và mỗi mùa:

- **Mức nền**: trung bình cộng 2 độ lệch chuẩn của ILI ở các tuần ngoài mùa (cuối mùa trước và 3 tuần đầu mùa) trong 3 mùa gần nhất có đủ số liệu, bỏ mùa 2020-21 (gần như không có cúm) [@cdc_fluview].
- **Tuần khởi phát**: tuần đầu của chuỗi 3 tuần liên tiếp ILI ≥ mức nền, **và** từ mùa 2016-17, tuần đó phải có tỷ lệ xét nghiệm cúm dương tính ≥ 2%. Bang thiếu số xét nghiệm tuần đó thì lấy trung vị các bang cùng vùng HHS.
- **Tuần đỉnh, giá trị đỉnh**: tuần ILI cao nhất của mùa (chỉ tính mùa đã kết thúc). **Độ nặng**: tỷ lệ nhập viện vì cúm cao nhất mùa theo NHSN [@cdc_nhsn_hrd], chỉ từ mùa 2021-22 (trước đó NHSN chưa đủ 51 bang).
- **Giai đoạn mùa** (`season_phase`): chưa bắt đầu, đang lên, đỉnh, đang giảm.
- 8 bang thiếu ILINet mùa 2025-26 (AK, CT, HI, NY, OK, OR, SD, UT) dùng tỷ lệ khám cấp cứu vì cúm của NSSP thay cho ILI (`source = nssp`).

**Vì sao thêm điều kiện xét nghiệm.** Sau COVID-19, ILI ngoài mùa cúm tăng hẳn lên vì COVID và RSV cũng gây triệu chứng giống cúm. Nếu chỉ dùng ILI, mùa 2021-22 có 22 bang "khởi phát" ngay tuần 40 trong khi xét nghiệm cúm dương tính gần 0%. Thêm điều kiện xét nghiệm, con số này còn 2 bang. Định nghĩa này được cả nhóm dùng chung: Chương 4 kiểm chứng giả thuyết độ ẩm của @shaman2010 trên các mốc khởi phát này, Chương 5 dùng làm nhãn cảnh báo khởi phát. Trước mùa 2016-17 chưa có số xét nghiệm cấp bang, nên các mùa đó vẫn dùng định nghĩa chỉ theo ILI; một số bang có mức nền thấp có thể "khởi phát" sớm giả ở các mùa này.

Trên 14 mùa đã kết thúc (2011-12 đến 2025-26, trừ 2020-21), 670/714 bang-mùa có tuần khởi phát. Trung vị tuần khởi phát là tuần 9 của mùa (khoảng đầu tháng 12; khoảng tứ phân vị: tuần 6–11), trung vị tuần đỉnh là tuần 16 (giữa tháng 1).

## Mùa năm nay so với các mùa trước (RQ1, RQ2)

![ILI toàn quốc mùa 2026-27 so với các mùa trước](figures/tv3_season_overlay.png){width=95%}

![Mùa 2026-27 có 27 bang khởi phát đến tuần 4, sớm thứ 2 trong 10 mùa từ 2016-17](figures/tv3_season_progress.png){width=85%}

**Năm nay đến sớm.** Tính đến tuần kết thúc 14/11/2026 (tuần 6 của mùa), 27 bang đã khởi phát và được xác nhận (khởi phát ở tuần 4 trở về trước, đủ 3 tuần liên tiếp). Ở cùng thời điểm, các mùa từ 2016-17 có trung vị 4 bang; chỉ mùa 2022-23 sớm hơn (31 bang). Xét nghiệm dương tính ở các bang khởi phát sớm năm nay là 8–18% (CA, TX, WA, NV...), nên đây là cúm thật chứ không phải ILI tăng vì bệnh khác. Theo `season_phase`, tuần này 27 bang ở giai đoạn đang lên, 24 bang chưa bắt đầu.

![Thời điểm khởi phát dao động mạnh giữa các mùa](figures/tv3_onset_ridgeline.png){width=85%}

| Mùa | Tuần khởi phát | Tuần đỉnh | Đỉnh ILI (%) | Độ nặng (nhập viện / 100.000) |
| --- | --- | --- | --- | --- |
| 2021-22 | 9 | 13 | 4,3 | 1,9 |
| 2022-23 | 4 | 9 | 8,1 | 9,9 |
| 2023-24 | 7 | 13 | 6,0 | 6,7 |
| 2024-25 | 11 | 19 | 7,8 | 17,9 |
| 2025-26 | 10 | 13 | 8,2 | 13,2 |

: Mốc mùa trung vị của 51 bang, các mùa sau COVID-19

![Đỉnh ILI theo bang qua các mùa](figures/tv3_severity_boxplot.png){width=95%}

**Sớm không có nghĩa là nặng.** Mùa 2022-23 đến sớm nhất nhưng độ nặng (9,9) thấp hơn hai mùa muộn hơn là 2024-25 (17,9, nặng nhất từ khi NHSN đủ 51 bang) và 2025-26 (13,2). Vì vậy việc năm nay đến sớm chưa nói được năm nay sẽ nặng. Đỉnh ILI các mùa sau COVID cao hơn trước COVID một phần vì ILI có nền cao hơn, nên khi so độ nặng giữa các năm nên dùng số nhập viện, không dùng đỉnh ILI.

**Không có xu hướng sớm dần hay muộn dần.** Trung vị tuần khởi phát qua 14 mùa không có xu hướng (Mann-Kendall, Kendall τ = −0,03, p = 0,87): mỗi năm sớm hay muộn là do chính năm đó, không do một thay đổi lâu dài.

![ILI có tự tương quan rất cao ở độ trễ 1 tuần và giảm dần theo độ trễ](figures/tv3_lag_acf_ili.png){width=95%}

ILI tuần này gần như quyết định ILI tuần sau (biểu đồ trễ gần thẳng hàng, ACF giảm chậm). Đây là lý do Chương 5 phải so mô hình cảnh báo với một mô hình nền dùng chính giá trị hiện tại, và Chương 4 dùng sai số chuẩn theo cụm bang.

## Tín hiệu nào báo sớm nhất

Ngoài ILI, kho dữ liệu có thêm tỷ lệ xét nghiệm dương tính, khám cấp cứu (NSSP), nước thải (WVAL) và nhập viện (NHSN). Với 4 mùa có đủ cả 5 tín hiệu (2022-23 đến 2025-26), chúng tôi xác định tuần mỗi tín hiệu đạt **một nửa đỉnh của chính nó** trong mùa, rồi so với nhập viện. Dùng "nửa đỉnh" thay cho mức nền vì mỗi tín hiệu có thang đo khác nhau.

![ILI đạt nửa đỉnh trước nhập viện 2,5 tuần ở 87% bang-mùa; nước thải và cấp cứu gần như cùng lúc](figures/tv3_signal_lead.png){width=85%}

| Tín hiệu | Số bang-mùa | Đi trước nhập viện (tuần, trung bình) | Tỷ lệ bang-mùa đi trước | p (Wilcoxon) |
| --- | --- | --- | --- | --- |
| ILI (khám ngoại trú) | 195 | 2,5 | 87% | < 0,001 |
| Xét nghiệm dương tính | 153 | 1,3 | 76% | < 0,001 |
| Cấp cứu (NSSP) | 203 | 0,6 | 54% | < 0,001 |
| Nước thải (WVAL) | 173 | 0,3 | 53% | < 0,001 |

: Thời điểm đạt nửa đỉnh của từng tín hiệu so với nhập viện, mùa 2022-23 đến 2025-26

Kết quả trái với kỳ vọng phổ biến rằng nước thải là tín hiệu sớm nhất: ở cấp bang × tuần, nước thải chỉ đi trước nhập viện chưa đến nửa tuần và chỉ ở khoảng một nửa số bang-mùa. ILI mới là tín hiệu sớm và nhất quán nhất. Chương 5 cho kết quả cùng chiều: thêm nước thải và cấp cứu vào mô hình cảnh báo không cải thiện AUC.

## Bang nào lên trước, bang nào giống nhau (RQ3)

![Bang phía Nam khởi phát sớm hơn bang phía Bắc](figures/tv3_onset_latitude.png){width=85%}

**Cúm lan từ Nam lên Bắc.** Trong mỗi mùa, xếp hạng các bang theo tuần khởi phát; thứ hạng này tương quan thuận với vĩ độ (Spearman ρ = 0,28, p < 10⁻¹², 48 bang lục địa + DC, 14 mùa), tức bang càng ở phía Nam càng khởi phát sớm. Hướng này lặp lại ở 12/14 mùa. Theo kinh độ (Đông – Tây) không có liên hệ (ρ = −0,04, p = 0,27).

![ILI theo bang và tuần mùa 2024-25, bang sắp theo tuần khởi phát](figures/tv3_heatmap_state_week.png){width=95%}

**So sánh giữa các vùng HHS.** Kiểm định Kruskal-Wallis cho thấy tuần khởi phát khác nhau giữa 10 vùng HHS (H = 34,9, p < 0,001); hậu kiểm Dunn (hiệu chỉnh Holm) có 5 cặp vùng khác nhau. Vùng 2 (New York, New Jersey) khởi phát sớm nhất (trung vị tuần 5), vùng 8 (miền núi) và vùng 10 (Tây Bắc) muộn nhất (tuần 10). Đỉnh ILI cũng khác giữa các vùng (p < 0,001, 18 cặp khác nhau), nhưng phần lớn do mỗi vùng có mức ILI nền khác nhau, nên không đọc thành "vùng này nặng hơn".

![Phân cụm Ward theo hình dạng đường cong mùa cúm](figures/tv3_dendrogram.png){width=95%}

**Phân cụm theo hình dạng đường cong.** Mỗi đường cong bang-mùa được chuẩn hóa z-score theo chính mùa đó (bỏ khác biệt về mức ILI, chỉ giữ hình dạng: lên sớm hay muộn, nhọn hay bẹt), rồi lấy trung bình các mùa thành đường cong đại diện của bang. FL bị loại vì chỉ có 5 mùa ILINet đầy đủ. Phân cụm Ward chọn k = 2 theo hệ số silhouette:

- **Cụm 1 (11 bang):** AL, GA, MS, SC, TN, NC, LA, TX, MD, DC và AK, phần lớn ở Đông Nam. Đỉnh sớm hơn: trung vị tuần đỉnh 13 so với 17 của cụm 2 (Mann-Whitney p = 0,007); khởi phát cũng sớm hơn 1 tuần (p = 0,006).
- **Cụm 2 (39 bang):** các bang còn lại.

Silhouette chỉ 0,23 và k-means khớp vừa phải với Ward (chỉ số Rand hiệu chỉnh 0,39), nên ranh giới giữa hai cụm không sắc nét. Nhưng phân cụm **không dùng tọa độ**, vậy mà các cụm lại liền nhau về địa lý: 88% số cặp (bang, 1 trong 3 bang gần nhất) cùng cụm, so với 66% nếu gán cụm ngẫu nhiên (permutation test, p < 0,001). Hình dạng mùa cúm vì vậy mang tính vùng, khớp với hướng lan từ Nam lên Bắc ở trên.

## Nhận xét

Các điểm chính cho cán bộ y tế:

1. **Mùa 2026-27 đến sớm**: 27 bang đã khởi phát đến giữa tháng 11, sớm thứ 2 trong 10 mùa gần đây và được xét nghiệm xác nhận. Đến sớm chưa có nghĩa là nặng, nên cần theo dõi số nhập viện (Chương 5).
2. **Bang phía Nam, đặc biệt Đông Nam, lên trước**: khởi phát sớm hơn khoảng 1 tuần và đạt đỉnh sớm hơn khoảng 4 tuần; các bang phía Bắc và miền núi có thể dùng diễn biến ở phía Nam làm tín hiệu chuẩn bị.
3. **ILI là tín hiệu sớm nhất** ở cấp bang, đi trước nhập viện khoảng 2 tuần; nước thải và cấp cứu không sớm hơn nhập viện bao nhiêu.
4. **Định nghĩa khởi phát quan trọng**: sau COVID-19, khởi phát chỉ dựa trên ILI cho nhiều kết quả giả; cần xét nghiệm xác nhận.

**Hạn chế.** Trước mùa 2016-17 chưa có số xét nghiệm cấp bang nên khởi phát các mùa này kém chắc chắn hơn. FL thiếu ILINet nhiều năm nên không vào phân cụm. ILINet là triệu chứng giống cúm, không phải ca xác nhận; mức ILI giữa các bang khác nhau một phần do cách lấy mẫu phòng khám, nên chương này so sánh thời điểm và hình dạng, không so trực tiếp mức ILI giữa các bang.
