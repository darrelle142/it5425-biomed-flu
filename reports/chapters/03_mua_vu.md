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
- So lieu trong phan ket qua lay tu ban da khoa (tag v2026-11-19 tren Hugging Face).
- Xem thu ca quyen: python reports/build_report.py
-->

# Mô tả mùa vụ, khám phá dữ liệu và phân cụm

Chương này triển khai mô-đun phân tích mùa vụ (`src/fluwatch/seasonality/` và `pipelines/03_season_eda.py`) trên dữ liệu chuẩn hóa từ tầng `data/business/` (`44.931` dòng × `90` cột trong `fact_flu_week`, phạm vi từ tuần kết thúc `2010-01-02` đến `2026-11-14`, tương ứng các mùa từ `2009-10` đến tuần thứ 6 của mùa `2026-27`) [@fludataset]. Toàn bộ mã nguồn nhằm trả lời ba câu hỏi nghiên cứu đầu tiên: xác định trạng thái pha dịch hiện tại (**RQ1**), so sánh mức độ sớm/muộn và nhẹ/nặng của các mùa (**RQ2**), và nhận diện trình tự lan dịch, nhóm bang tương đồng cũng như hướng lan theo không gian (**RQ3**).

## Định nghĩa mốc mùa

Để đo lường đồng nhất trên 50 bang và Đặc khu Columbia (51 đơn vị) qua hơn 16 năm giám sát, hệ thống quy chuẩn tuần dịch theo lịch MMWR, trong đó mỗi mùa cúm bắt đầu từ tuần MMWR 40 (`season_week = 1`) và sử dụng cơ chế tính mốc mùa trong `milestones.py`.

### Xử lý dữ liệu thưa, số liệu sơ bộ và nguồn thay thế

Trước khi tính mốc mùa, hai quy tắc làm sạch nghiệp vụ được áp dụng nhất quán:

1. **Loại trừ mùa bất thường, sóng COVID-19 và dữ liệu thưa**: Hai mùa `2009-10` (dư âm đại dịch H1N1, không đủ tuần đầu mùa trong chuỗi bắt đầu từ tháng 1/2010) và `2020-21` (hoạt động cúm gần bằng 0 với `lab_pct_pos` trung bình `0,21%`, nhưng `% ILI` vẫn trung bình `1,15%` do COVID-19) được loại khỏi tập tính mức nền lịch sử, phân cụm, kiểm định và biểu đồ tự tương quan. Riêng mùa `2019-20`, do làn sóng COVID-19 đầu tiên từ nửa cuối tháng 3/2020 gây ra các đỉnh ILI giả (như `IA` tăng lên `10,82%` ở tuần `48` với `lab_pct_pos = 0%`, hay `NJ` và `NY` đạt đỉnh ở tuần `26`), việc xác định mốc mùa và trích xuất đường cong phân cụm của mùa `2019-20` được giới hạn tới hết tuần `24` (`2020-03-14`). Ngoài ra, hàm `mask_sparse_ili` kiểm tra tỷ lệ thiếu theo từng cặp `(bang, mùa)` và đặt toàn bộ chuỗi `ili_pct` thành thiếu nếu tỷ lệ thiếu vượt quá `30%`: bang Florida (`FL`) thiếu dữ liệu ILINet từ `2010-11` đến `2019-20`, Louisiana (`LA`) thiếu từ `2010-11` đến `2015-16`, và Delaware (`DE`) thiếu ở mùa `2010-11` [@delphi_epidata].
2. **Xác nhận lưu hành virus cúm chống bùng nổ giả cho nguồn `ILINet`**: Vì `% ILI` đo hội chứng giống cúm nên dễ bị các đợt dịch COVID-19 hoặc virus hô hấp khác làm vượt mức nền trước khi cúm thật sự lưu hành (điển hình như sóng Delta tháng 10–11/2021). Đối với các bang–mùa dùng nguồn `ili`, một tuần chỉ được tính là có cúm lưu hành khi tỷ lệ xét nghiệm dương tính cúm ở cấp bang **hoặc** trung vị toàn quốc đạt `lab_pct_pos >= 2,0%` (tự động bỏ qua ràng buộc nếu cả bang lẫn toàn quốc chưa có dữ liệu `lab_clinical` như giai đoạn trước `2016-17`). Cách kết hợp mức bang và mức toàn quốc vừa chặn được các đỉnh giả khi cả nước chưa có cúm, vừa bảo toàn các bang thiếu `lab_clinical` (`NY`, `NJ`, `DC`) hoặc bị pha loãng mẫu xét nghiệm trong sóng Omicron cuối năm 2021.
3. **Cách ly số liệu sơ bộ**: 4 tuần công bố gần nhất được gắn cờ `is_preliminary = True` do mạng lưới báo cáo của CDC thường xuyên hiệu chỉnh hồi cứu [@cdc_fluview]. Việc xác định mùa đã hoàn tất (`get_completed_seasons`: có dữ liệu xác nhận đến tối thiểu `season_week >= 34`), tính mức nền, phát hiện tuần khởi phát và xác định tuần đỉnh chỉ sử dụng các tuần đã xác nhận (`~is_preliminary`), tránh tình trạng chốt nhầm đỉnh hoặc khởi phát giả từ số liệu chưa ổn định.
4. **Thứ tự ưu tiên nguồn khi thiếu ILINet**: Trong mùa `2025-26`, có 8 bang thiếu dữ liệu ILINet (`AK`, `CT`, `HI`, `NY`, `OK`, `OR`, `SD`, `UT`). Hàm `prepare_signal` gán tín hiệu chính (`signal_value`) theo thứ tự ưu tiên `ILINet (ili_pct)` → `NSSP cấp cứu (ed_pct_flu)` → `NHSN nhập viện (rate_flu)`, đồng thời lưu tên nguồn vào cột `source` (`ili`, `nssp` hoặc `nhsn`). Mức nền của từng bang–mùa luôn được tính trên **cùng cột và cùng đơn vị** tương ứng với `source` của bang–mùa đó, đảm bảo không trộn lẫn thang đo giữa % khám ngoại trú (ILI), % lượt cấp cứu (NSSP) và ca/100.000 dân (NHSN).

### Mức nền, tuần khởi phát, tuần đỉnh, độ nặng và pha mùa

Các mốc dịch tễ học được chuẩn hóa theo phương pháp của CDC Hoa Kỳ [@cdc_fluview; @cdc_nhsn_hrd]:

| Chỉ tiêu / Cột | Định nghĩa và quy tắc tính | Kiểu / Giá trị |
| --- | --- | --- |
| `baseline` | Trung bình cộng 2 lần độ lệch chuẩn ($\bar{x} + 2s$) trên tập tuần không có cúm của tối đa 3 mùa hợp lệ gần nhất trước đó. Tuần không có cúm ưu tiên xác định khi trung vị trượt 3 tuần của `lab_pct_pos < 2%` trong ít nhất 3 tuần liên tiếp; nếu số mẫu $\le 5$ tuần thì lùi về các tuần cuối mùa (`season_week >= 34`). Mùa `2010-11` không có mùa trước hợp lệ nên `baseline` để trống (`NaN`). | `float64` (theo đơn vị của `source`) |
| `onset_week`, `onset_season_week` | Tuần đầu tiên của chuỗi **3 tuần xác nhận liên tiếp** có `signal_value >= baseline`, đồng thời có ít nhất 1 tuần trong chuỗi đạt xác nhận lưu hành cúm (`lab_pct_pos >= 2,0%` cấp bang hoặc toàn quốc với nguồn `ili`). | `datetime64[us]`, `Int64` |
| `peak_week`, `peak_season_week`, `peak_value` | Tuần đạt giá trị cực đại của `signal_value` trong các tuần có lưu hành cúm (giới hạn `season_week <= 24` với mùa `2019-20`), chỉ chốt với các mùa đã hoàn tất (`season_week >= 34`). | `datetime64[us]`, `Int64`, `float64` |
| `severity`, `peak_rate_flu` | Mức độ nặng dựa trên ngưỡng nhập viện CDC tại tuần có `rate_flu` (NHSN) cao nhất trong mùa đã hoàn tất, áp dụng từ mùa `2021-22` trở đi. | `rat_thap`, `thap`, `trung_binh`, `cao`, `rat_cao` (`string`) |
| `season_phase` | Nhãn pha theo từng tuần: trước tuần khởi phát là `chua_bat_dau`; từ tuần khởi phát đến trước tuần đỉnh (hoặc mùa đang diễn ra chưa chốt đỉnh) là `dang_len`; đúng tuần đỉnh là `dinh`; sau tuần đỉnh là `dang_giam` (để `NA` nếu chưa tính được `baseline`). | `string` (`4` nhãn pha) |

: Định nghĩa các cột mốc mùa và nhãn pha dịch trong `season_milestones.parquet` và `season_phase.parquet`

Toàn bộ kết quả mốc mùa được xuất ra `season_milestones.parquet` (`918` dòng = `51` đơn vị × `18` mùa, gồm `11` cột tương thích hoàn toàn với lược đồ `fact_season_summary` của Thành viên 2) và `season_phase.parquet` (`44.931` dòng × `8` cột, bổ sung `ili_tren_muc_nen`).

## Mùa năm nay so với các mùa trước (RQ1, RQ2)

### Trạng thái mùa hiện tại 2026-27 (RQ1)

Tính đến tuần dữ liệu mới nhất trong kho (`2026-11-14`, tức `season_week = 6` của mùa `2026-27`), chuỗi `% ILI` toàn quốc đạt `3,57%` (`99.430` lượt ILI trên `2.781.895` lượt khám ngoại trú), cao gấp gần đôi trung vị lịch sử tại cùng tuần thứ 6 (`1,86%`). Đường biểu diễn của mùa `2026-27` tăng nhanh ngay từ các tuần đầu mùa (từ tuần 3 đến tuần 6 là số liệu sơ bộ, vẽ bằng nét đứt).

![Mùa 2026-27 có tỷ lệ % ILI đầu mùa cao hơn rõ rệt trung vị lịch sử cùng thời điểm](figures/season_overlay.png){width=90%}

Tuy nhiên, do 4 tuần gần nhất (tuần 3–6) đang mang cờ `is_preliminary = True`, tập dữ liệu xác nhận của mùa `2026-27` mới dừng ở 2 tuần đầu mùa (`season_week` 1–2), chưa đủ điều kiện tối thiểu 3 tuần liên tiếp để xác nhận `onset_week`. Do đó, toàn bộ `51/51` bang và đặc khu tại mốc `2026-11-14` vẫn được gắn nhãn thận trọng là `chua_bat_dau`, đồng thời đường nét đứt trên biểu đồ đóng vai trò cảnh báo sớm về đà tăng nhanh đầu mùa cho cán bộ y tế.

### Độ nặng và tiến độ qua các mùa lịch sử (RQ2)

Xét `15` mùa hoàn tất hợp lệ từ `2010-11` đến `2025-26` (loại `2020-21`), độ lớn đỉnh dịch và thời điểm bùng phát có sự phân hóa đáng kể giữa giai đoạn trước và sau đại dịch COVID-19.

| Mùa | Nguồn (`ili` / `nssp`) | Số bang có `baseline` | Số bang có `onset` | Tuần khởi phát trung vị [IQR] | Tuần đỉnh trung vị | Đỉnh ILI trung vị (%) [IQR] | Đỉnh ILI cao nhất (%) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2010-11 | 48 / 0 | 0 | 0 | – | 20 | 4,58 [3,22–6,45] | 14,74 |
| 2011-12 | 49 / 0 | 48 | 46 | 4,5 [1,0–11,0] | 23 | 2,53 [1,47–3,66] | 8,18 |
| 2012-13 | 49 / 0 | 49 | 48 | 6,0 [3,0–10,0] | 13 | 5,62 [4,36–7,18] | 13,25 |
| 2013-14 | 49 / 0 | 49 | 47 | 8,0 [4,0–11,0] | 14 | 4,12 [2,89–5,72] | 16,35 |
| 2014-15 | 49 / 0 | 49 | 47 | 7,0 [3,0–10,0] | 14 | 6,44 [4,02–8,03] | 19,42 |
| 2015-16 | 49 / 0 | 49 | 45 | 4,0 [2,0–12,0] | 23 | 3,47 [2,58–4,42] | 9,66 |
| 2016-17 | 50 / 0 | 49 | 46 | 9,0 [7,0–12,0] | 19 | 4,86 [3,59–6,73] | 15,50 |
| 2017-18 | 50 / 0 | 50 | 49 | 7,0 [4,0–10,0] | 18 | 7,17 [5,32–10,76] | 15,45 |
| 2018-19 | 50 / 0 | 50 | 49 | 8,0 [8,0–11,0] | 20 | 5,22 [3,78–7,40] | 11,74 |
| 2019-20 | 50 / 0 | 50 | 49 | 6,0 [5,0–8,0] | 19 | 7,52 [5,32–9,80] | 15,27 |
| 2021-22 | 51 / 0 | 50 | 45 | 9,0 [7,0–12,0] | 13 | 4,24 [3,24–5,80] | 9,61 |
| 2022-23 | 51 / 0 | 51 | 50 | 4,0 [2,0–6,0] | 9 | 8,09 [5,81–9,82] | 16,95 |
| 2023-24 | 51 / 0 | 51 | 50 | 8,0 [6,0–10,75] | 13 | 6,00 [4,22–8,60] | 19,33 |
| 2024-25 | 51 / 0 | 51 | 51 | 10,0 [8,0–12,0] | 19 | 7,75 [5,52–10,08] | 17,01 |
| 2025-26 | 43 / 8 | 51 | 50 | 10,0 [8,25–11,0] | 13 | 8,06 [5,56–10,43] | 16,03 |

: Tổng hợp các mốc mùa qua 15 mùa hoàn tất từ `2010-11` đến `2025-26` (không tính mùa `2020-21`)

Trong nhóm 5 mùa hậu đại dịch có dữ liệu nhập viện NHSN (`2021-22` đến `2025-26`), hai mùa gần nhất là `2024-25` và `2025-26` nổi bật về cường độ:

- **Đỉnh % ILI ngoại trú**: Trung vị đỉnh ILI cấp bang mùa `2025-26` (trên 43 bang có ILINet) đạt `8,06%` (IQR: `5,56%–10,43%`) và mùa `2024-25` đạt `7,75%` (IQR: `5,52%–10,08%`), thuộc nhóm cao nhất chuỗi lịch sử cùng `2022-23` (`8,09%`) và `2019-20` (`7,52%` sau khi loại sóng COVID-19 từ tuần `25`), vượt xa các mùa nhẹ như `2011-12` (`2,53%`) hay `2015-16` (`3,47%`). Ở quy mô toàn quốc, mùa `2025-26` đạt đỉnh sớm ở tuần `13` (`8,02%`), còn mùa `2024-25` đạt đỉnh muộn hơn ở tuần `19` (`7,71%`).
- **Mức độ nặng nhập viện (NHSN)**: Mùa `2024-25` là mùa nặng nhất trong 5 mùa gần đây với toàn bộ `51/51` bang/đặc khu rơi vào hai mức cao nhất (`37` `rat_cao`, `14` `cao`, không có bang nào ở mức `trung_binh` trở xuống). Mùa `2025-26` ghi nhận `23` bang `rat_cao`, `22` bang `cao` và `6` bang `trung_binh` (trong đó 8 bang dùng nguồn thay thế NSSP đều có đầy đủ mốc khởi phát, đỉnh và mức nặng NHSN; riêng bang `ND` dù đạt đỉnh ILI `5,40%` ở tuần `13` và mức `rat_cao` nhưng chỉ vượt nền `2,996%` trong 2 tuần liên tiếp 13–14 nên không kích hoạt `onset_week`). Trái lại, mùa `2021-22` nhẹ nhất (`18` `rat_thap`, `27` `thap`, `5` `trung_binh`, `1` `cao`).

![Đỉnh % ILI giữa các mùa biến động mạnh, các mùa sau đại dịch có trung vị cao hơn](figures/severity_boxplot.png){width=90%}

Về tiến độ khởi phát và lên đỉnh qua `672` quan sát `(bang, mùa)` có tuần khởi phát hợp lệ (`14` mùa từ `2011-12` đến `2025-26`), phân bố tuần khởi phát lệch phải rõ rệt với trung vị toàn bộ là **tuần thứ `8`** (IQR: tuần `5` đến tuần `11`, trung bình `7,92`), trong khi trung vị tuần đỉnh trên `748` quan sát đạt **tuần thứ `17`** (IQR: tuần `13` đến tuần `20`). Quan sát biểu đồ ridgeline cho thấy sự dịch chuyển đáng chú ý giữa các mùa gần đây: mùa `2022-23` bùng phát rất sớm (trung vị khởi phát tuần `4`, đỉnh tuần `9`), trong khi hai mùa `2024-25` và `2025-26` đều khởi phát muộn hơn (trung vị tuần `10`), nhưng mùa `2025-26` tăng tốc lên đỉnh rất nhanh chỉ sau 3 tuần (trung vị đỉnh tuần `13` so với tuần `19` ở `2024-25`).

![Tuần khởi phát dịch giữa các bang lệch phải và tập trung ở nửa đầu mùa](figures/onset_histogram.png){width=90%}

![Phân bố tuần khởi phát dịch dịch chuyển rõ rệt qua các mùa cúm](figures/onset_ridgeline.png){width=90%}

Ngoài ra, phân tích tự tương quan trên `788` tuần ILI toàn quốc (sau khi loại hai mùa bất thường `2009-10` và `2020-21`, đồng thời tính độ trễ trong nội bộ từng mùa) cho thấy chuỗi `% ILI` có quán tính ngắn hạn rất cao: hệ số tương quan bậc 1 đạt `r = 0,9650`, tiếp tục duy trì cao ở độ trễ 2 tuần (`0,8944`), 3 tuần (`0,8189`) và 4 tuần (`0,7450`), rồi giảm dần về `0` quanh độ trễ 13–14 tuần. Đặc tính tự tương quan mạnh ở các độ trễ 1–4 tuần là cơ sở quan trọng giải thích vì sao biến trễ `ili_pct` giữ vai trò chủ lực trong bài toán dự báo vượt ngưỡng ngắn hạn (RQ5).

![Chuỗi % ILI theo tuần có tự tương quan bậc 1 rất mạnh (r = 0,965) và giảm đều qua nhiều tuần trễ](figures/lag_acf_ili.png){width=90%}

## Bang nào lên trước, bang nào giống nhau (RQ3)

### Trình tự lan dịch giữa các bang qua biểu đồ nhiệt

Khi sắp xếp `51` bang/đặc khu mùa `2024-25` theo thứ tự tuần khởi phát từ sớm nhất đến muộn nhất, biểu đồ nhiệt (`heatmap_state_week.png`) cho thấy sự chênh lệch thời gian khởi phát lên tới `15` tuần giữa nhóm bang đầu và cuối:

- **Nhóm khởi phát sớm nhất (tuần 3–7)**: `NJ` khởi phát sớm nhất ở tuần `3` (đạt đỉnh `10,53%` ở tuần `18`), tiếp theo là `LA` ở tuần `4` (đỉnh sớm `13,66%` ở tuần `13`), `AZ` và `FL` ở tuần `6`, và `GA` ở tuần `7`.
- **Nhóm khởi phát muộn nhất (tuần 16–18)**: `ND` (tuần `16`), `MT` và `WV` (tuần `18`) bắt đầu muộn hơn khoảng 3–3,5 tháng nhưng lên đỉnh gần như đồng thời với phần còn lại của cả nước quanh tuần `17–20`.

![Sắp xếp các bang theo tuần khởi phát mùa 2024-25 cho thấy rõ trình tự lan dịch](figures/heatmap_state_week.png){width=90%}

### Phân cụm hình dạng đường cong mùa vụ (Ward và K-Means)

Để nhận diện các bang có nhịp điệu dịch giống nhau mà không bị chi phối bởi độ lớn tuyệt đối của từng mùa, `cluster_states()` chuẩn hóa Z-score chuỗi `ili_pct` trong từng `(bang, mùa)` rồi tính trung bình đường cong theo `season_week` (`1..52`) trên `15` mùa hoàn tất (đồng thời loại phần sau tuần `24` của mùa `2019-20`). Thuật toán phân cụm thứ bậc (liên kết Ward) được đánh giá cho `k = 2..5`: chỉ số Silhouette đạt đỉnh rõ rệt tại **`k = 2`** với giá trị **`0,3872`**, cao hơn hẳn so với `k = 3` (`0,1599`), `k = 4` (`0,1615`) và `k = 5` (`0,1705`).

Kết quả phân cụm thứ bậc (ghi vào `dim_state.cluster_id`) tách `51` đơn vị thành hai nhóm rõ rệt:

- **Cụm 1 (`5` đơn vị)**: `DC`, `FL`, `GA`, `LA`, `MS` — tập trung ở khu vực Đông Nam và Duyên hải Vịnh (3 bang thuộc vùng HHS 4, 1 bang vùng HHS 6 và DC thuộc vùng HHS 3). Nhóm này có đường cong kéo dài, nền cao sớm từ đầu mùa hoặc đỉnh phụ sớm đặc trưng cho các bang khí hậu ấm hơn. Toàn bộ 5/5 đơn vị này cũng đều rơi vào Cụm 2 của K-Means (`n = 14`), khẳng định tính ổn định của nhóm tách biệt sớm này.
- **Cụm 2 (`46` đơn vị còn lại)**: Trải rộng trên tất cả 10 vùng HHS, mang dạng đường cong mùa đông điển hình (tăng dốc từ cuối thu và đạt đỉnh tập trung quanh tuần 12–20). Trong đó, K-Means chia tiếp nhóm đa số thành một lõi `37` bang có đường cong mùa đông thuần túy và `9` bang chuyển tiếp (`AL`, `CA`, `MD`, `NC`, `NV`, `NY`, `SC`, `TN`, `TX`) có biên độ dao động đầu–giữa mùa gần với nhóm 5 bang trên.

![Phân cụm thứ bậc chia 51 đơn vị thành 2 nhóm theo hình dạng đường cong mùa vụ](figures/dendrogram.png){width=90%}

### Khác biệt giữa 10 vùng HHS (Kruskal–Wallis và hậu kiểm Dunn)

Kiểm định phi tham số Kruskal–Wallis qua 10 vùng HHS khẳng định có sự khác biệt có ý nghĩa thống kê giữa các vùng về **thời điểm khởi phát** và **độ cao đỉnh ILI**, nhưng **không có khác biệt có ý nghĩa về đỉnh tỷ lệ nhập viện NHSN (`peak_rate_flu`)**:

| Chỉ tiêu kiểm định | Số quan sát (`n`) | Thống kê $H$ (Kruskal–Wallis) | Giá trị $p$ | Kết luận ($\alpha = 0,05$) | Số cặp khác biệt (Dunn Holm $p_{\text{adj}} < 0,05$) |
| --- | --- | --- | --- | --- | --- |
| `onset_season_week` | 672 | 25,9064 | 0,002116 | Có khác biệt | 1 cặp: Vùng 4 vs Vùng 10 ($p_{\text{adj}} = 0,0147$) |
| `peak_value` (chỉ nguồn `ili`) | 740 | 147,5974 | < 0,000001 | Có khác biệt rất mạnh | 19 cặp (cao nhất ở Vùng 6 trung vị `8,80%` và Vùng 4 `7,76%`; thấp nhất ở Vùng 1 `4,16%` và Vùng 8 `4,23%`) |
| `peak_rate_flu` (NHSN) | 255 | 5,8466 | 0,755169 | Không khác biệt có ý nghĩa | – |

: Kết quả kiểm định Kruskal–Wallis và hậu kiểm Dunn (hiệu chỉnh Holm) giữa 10 vùng HHS

Về thời điểm khởi phát, **Vùng 4** (Đông Nam, trung vị tuần `6,0`, IQR `4,0–9,0`) cùng **Vùng 2** và **Vùng 6** (trung vị `7,0`) khởi phát sớm hơn so với **Vùng 3**, **Vùng 9** và **Vùng 10** (cùng có trung vị `9,0`), trong đó cặp chênh lệch mạnh nhất là Vùng 4 so với Vùng 10 ($p_{\text{adj}} = 0,0147$). Về cường độ đỉnh ngoại trú, Vùng 6 (`8,80%`) và Vùng 4 (`7,76%`) ghi nhận tỷ lệ `% ILI` đỉnh cao gấp gần đôi Vùng 1 (`4,16%`) và Vùng 8 (`4,23%`). Ngược lại, `peak_rate_flu` không khác biệt theo vùng ($p = 0,7552$), hàm ý tỷ lệ nhập viện nặng trên 100.000 dân chịu chi phối nhiều hơn bởi đặc thù từng mùa dịch (chủng virus, miễn dịch cộng đồng) hơn là yếu tố vùng địa lý cố định, đồng thời phản ánh sự khác biệt trong thói quen khám ngoại trú ILI giữa các vùng.

### Xu hướng khởi phát dài hạn (Mann–Kendall) và hướng lan không gian

Ở phần kiểm định mở rộng bằng kiểm định xu hướng phi tham số **Mann–Kendall** kèm độ dốc Sen qua `14` mùa (`2011-12` đến `2025-26`):

- **Cấp toàn quốc**: Chưa đủ bằng chứng kết luận xu hướng dịch chuyển thời điểm khởi phát toàn quốc ở mức $\alpha = 0,05$, dù hệ số $\tau$ dương gợi ý xu hướng hơi muộn dần nhẹ (`median_onset`: $\tau = 0,4027$, $p = 0,0522$, độ dốc Sen `+0,3182` tuần/mùa; `mean_onset`: $\tau = 0,2967$, $p = 0,1572$, độ dốc `+0,1947` tuần/mùa).
- **Cấp từng bang (sau hiệu chỉnh đa kiểm định Holm)**: Trong `51` bang/đặc khu, có `12` bang đạt $p < 0,05$ thô, nhưng sau khi hiệu chỉnh Holm cho toàn bộ `51` phép thử đồng thời, có **`3` bang** giữ được xu hướng có ý nghĩa thống kê với **`Khởi phát muộn hơn`**: **Virginia (`VA`)** ($\tau = 0,7640$, $p_{\text{adj}} = 0,0120$, độ dốc Sen `+0,83` tuần/mùa), **Missouri (`MO`)** ($\tau = 0,6959$, $p_{\text{adj}} = 0,0443$, Sen `+0,89` tuần/mùa) và **Ohio (`OH`)** ($\tau = 0,6782$, $p_{\text{adj}} = 0,0452$, Sen `+0,80` tuần/mùa). `48` bang còn lại đều được phân loại nhất quán là `Không có xu hướng rõ rệt`.

Về **tương quan không gian theo tọa độ trọng tâm dân số** (`dim_state.lat`, `dim_state.lon`) trên `49` bang lục địa (loại `AK` và `HI` vì vị trí địa lý tách biệt):

- **Tổng hợp nhiều mùa**: Sau khi loại bỏ các đợt vượt nền giả ngoài mùa cúm, tín hiệu hướng lan theo vĩ độ trở nên rõ nét hơn hẳn. Trung vị tuần khởi phát của `49` bang lục địa tương quan thuận mạnh có ý nghĩa với vĩ độ (Spearman $r = 0,4223$, $p = 0,0025$; Pearson $r = 0,4648$, $p = 0,0008$), trong khi không có tương quan có ý nghĩa với kinh độ (Spearman $r = -0,1306$, $p = 0,3711$). Xu hướng này vẫn nhất quán khi xét cả `51` bang/đặc khu (Spearman $r_{\text{lat}} = 0,3606$, $p = 0,0093$; $r_{\text{lon}} = -0,2158$, $p = 0,1282$). Điều này khẳng định **các bang vĩ độ thấp (phía Nam) có xu hướng khởi phát sớm hơn các bang phía Bắc** (hướng lan **Nam → Bắc**), phù hợp với y văn về vai trò kích hoạt sớm của điều kiện độ ẩm tuyệt đối thấp và mật độ di chuyển ở vùng Vịnh–Đông Nam [@shaman2010].
- **Biến thiên theo từng mùa**: Phân tích từng mùa riêng lẻ ghi nhận hướng lan **Nam → Bắc** có ý nghĩa thống kê ở **`6` mùa** (`2013-14`, `2015-16`, `2016-17`, `2018-19`, `2022-23` với $r = 0,4650$, $p = 0,0009$, và `2023-24` với $r = 0,4449$, $p = 0,0015$), còn các mùa còn lại (bao gồm `2024-25` và `2025-26`) không có hướng lan tuyến tính rõ rệt theo trục vĩ độ hay kinh độ.

![Các bang phía Nam có xu hướng khởi phát mùa cúm sớm hơn các bang phía Bắc](figures/spatial_onset_correlation.png){width=90%}

## Nhận xét

Tổng hợp các phát hiện từ mô-đun mùa vụ mang lại bốn hàm ý thực hành trực tiếp cho cán bộ y tế và cho các mô-đun dự báo tiếp theo:

1. **Giám sát sớm tuần sơ bộ nhưng thận trọng khi chốt mốc chính thức**: Với tốc độ tự tương quan bậc 1 rất cao ($r = 0,965$), đà tăng bất thường của `2026-27` ngay ở tuần thứ 6 (`3,57%` so với trung vị lịch sử `1,86%`, kèm `lab_pct_pos` đạt `11,20%`) là tín hiệu cúm thật cần kích hoạt chuẩn bị nguồn lực sớm dù tuần khởi phát chính thức chưa chốt do còn nằm trong cửa sổ 4 tuần sơ bộ.
2. **Không dùng một ngưỡng chung toàn quốc hay chỉ nhìn đơn thuần vào `% ILI`**: Chênh lệch trung vị đỉnh `% ILI` gần gấp đôi giữa Vùng 6/Vùng 4 và Vùng 1/Vùng 8 chứng minh việc xây dựng `baseline` riêng theo từng `(bang, nguồn dữ liệu)` là bắt buộc; đồng thời, ràng buộc `lab_pct_pos >= 2%` khi chốt mốc `ILINet` giúp loại bỏ hiệu quả các đợt bùng nổ giả do COVID-19 (như sóng Delta tháng 10/2021 hoặc đỉnh COVID mùa xuân–hè `2019-20`), trong khi cơ chế chuyển sang `NSSP` ở 8 bang thiếu `ILINet` năm `2025-26` vẫn giữ trọn độ phủ `51/51` bang.
3. **Trọng tâm cảnh báo theo không gian và nhóm đường cong**: Nhóm `5` bang Cụm 1 (`DC`, `FL`, `GA`, `LA`, `MS`) cùng vùng Đông Nam (Vùng 4) thường có tín hiệu khởi phát sớm hoặc đường cong kéo dài; kết hợp hướng lan chủ đạo Nam → Bắc giúp ưu tiên giám sát sớm các bang vĩ độ thấp làm chỉ báo dẫn đường.
4. **Liên kết sang các chương tiếp theo**: Các bảng `season_milestones.parquet`, `season_phase.parquet` và `state_cluster.parquet` đã hợp nhất đầy đủ vào `fact_season_summary` và `dim_state` của kho dữ liệu, cung cấp trực tiếp biến mục tiêu tuần khởi phát/vượt ngưỡng cho mô hình yếu tố ảnh hưởng (Chương 4), mô hình cảnh báo sớm 1–4 tuần (Chương 5) và các trang hiển thị trên Dashboard (Chương 6).

