<!-- Nguoi phu trach: TV4. Chi sua file nay. -->
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
- So lieu chuong nay: chay python pipelines/04_risk_factors.py --sim tren business/ tag v2026-11-22 (TV4, 23/11/2026).
-->

# Yếu tố ảnh hưởng, giả lập và kiểm tra phương pháp

Chương này trả lời RQ4: yếu tố môi trường và xã hội nào (độ ẩm tuyệt đối, bụi mịn PM2.5, độ phủ vaccine, kỳ nghỉ lễ) đi kèm hoạt động cúm cao hơn, và đi trước bao nhiêu tuần. Mọi phân tích theo khung ba tầng của kế hoạch: một yếu tố chỉ được coi là có liên hệ khi ghép được về mặt kỹ thuật (tầng 1, Chương 2), có bằng chứng đã công bố (tầng 2) và mối liên hệ xuất hiện lại trên chính dữ liệu thật của nhóm (tầng 3).

Toàn bộ số liệu trong chương lấy từ kho `business/` phiên bản `v2026-11-22` trên Hugging Face, chạy bằng `python pipelines/04_risk_factors.py --sim`. Đặc tả phân tích (mẫu, biến, mô hình, cách tính khoảng tin cậy) được chốt và ghi lại trước khi xem kết quả, để tránh chọn cách làm theo kết quả đẹp.

## Bảng bằng chứng từ các nghiên cứu

Bảng dưới tóm tắt bằng chứng đã công bố cho từng yếu tố (tầng 2) và đặt cạnh kết quả của nhóm (tầng 3, trình bày chi tiết ở các mục sau). Cột kết quả được sinh tự động từ file kết quả (`reports/tv4/bang_bang_chung.csv`), nên luôn khớp với số trong chương.

| Yếu tố | Bằng chứng đã công bố | Chiều dự kiến, độ trễ | Kết quả của nhóm |
| --- | --- | --- | --- |
| Độ ẩm tuyệt đối | Độ ẩm tuyệt đối chi phối khả năng sống và lây truyền của virus cúm [@shaman2009]; khởi phát mùa cúm ở Mỹ gắn với độ ẩm thấp bất thường những tuần trước, 48 bang + DC [@shaman2010] | Thấp bất thường → tăng; 1–3 tuần | Cùng chiều: trễ 1–4 tuần, hiệu ứng nhỏ |
| PM2.5 | Croft và cộng sự (2019): 498.118 người lớn ở New York, nhập viện và cấp cứu vì cúm tăng theo PM2.5 của 1–7 ngày trước | Tăng → tăng; 0–1 tuần | Cùng chiều trong mô hình Negative Binomial; tương quan trễ không rõ |
| Vaccine cúm | Nghiên cứu cấp bang (medRxiv 2025): nhập viện tương quan với tỷ lệ tiêm nhóm 18–49 tuổi (p < 0,0107), không với tỷ lệ chung | Tăng → giảm; theo mùa | Không phát hiện liên hệ |
| Kỳ nghỉ | Nghiên cứu ở Úc (2019): kỳ nghỉ học gắn với mức giảm 41–65% số ca cúm | Nghỉ → giảm; 0–1 tuần | Ngược chiều (xem giải thích ở mục Hồi quy) |
| Nước thải, cấp cứu | Chỉ báo đi trước nhập viện 0–2 tuần (chưa thống nhất giữa các nghiên cứu) | Đi trước, cùng chiều | Thuộc mô hình cảnh báo (Chương 5) |

: Bằng chứng đã công bố và kết quả kiểm chứng trên dữ liệu của nhóm

Bài của Shaman và cộng sự xác định khởi phát mùa cúm từ số tử vong do viêm phổi và cúm, còn nhóm dùng ILI. Vì vậy phần tái hiện ở chương này là kiểm chứng cùng giả thuyết với một định nghĩa khởi phát khác, không phải lặp lại nguyên bài.

## Dữ liệu và cách loại trừ

**Mẫu phân tích.** Đơn vị là bang × tuần MMWR, 51 bang (gồm DC). Các bước loại trừ và số dòng còn lại:

| Bước | Số dòng còn lại |
| --- | --- |
| Toàn bộ bang × tuần trong kho | 44.931 |
| Bỏ mùa 2009-10 (chưa có ILINet), 2020-21 (gần như không có cúm do biện pháp phòng COVID-19), 2026-27 (mới bắt đầu) | 39.882 |
| Chỉ giữ tuần mùa 1–33 (tuần MMWR 40 đến 20, giai đoạn giả thuyết áp dụng) | 25.245 |
| Bỏ bang-mùa thiếu ILINet trên 30% (FL 2010–2021, LA 2010–2016, DE 2010-11, 8 bang mùa 2025-26) | 24.453 |
| Có số ILINet trong tuần | 24.451 |

: Các bước chọn mẫu cho phân tích RQ4 (15 mùa, 51 bang)

**Loại bỏ mùa vụ trước khi so sánh.** Cúm, độ ẩm và PM2.5 đều có chu kỳ năm, nên đặt hai chuỗi cạnh nhau sẽ "tương quan" dù không liên quan. Mọi biến môi trường vì thế dùng dạng độ chênh: giá trị tuần đó trừ trung bình của cùng bang, cùng tuần MMWR qua các năm 2010–2025. Cột `ah_anomaly` có sẵn trong kho; `ili_anomaly` và `pm25_epa_anomaly` được tính theo đúng công thức đó. Biến trễ 0–4 tuần lấy giá trị của các tuần trước trong cùng bang, không bao giờ dùng số liệu của tuần sau.

**Chọn đúng biến.** Ba lựa chọn dưới đây đều xuất phát từ kiểm tra dữ liệu ở Chương 2:

- **PM2.5 chỉ dùng số đo của trạm EPA** (`pm25_epa`). Cột `pm25_mean` của kho ghép số trạm EPA với số mô hình Open-Meteo khi thiếu EPA. Ở các bang × tuần có cả hai nguồn, chúng chỉ tương quan Spearman 0,51. Ở các đợt khói cháy rừng (06–07/2023), Open-Meteo chỉ bằng khoảng nửa số EPA. Ghép hai nguồn vào một biến sẽ đưa chênh lệch giữa hai nguồn vào hệ số.
- **Vaccine dùng độ phủ cuối mùa trước** (`flu_vax_pct_prev`). Cột `flu_vax_pct` là số cuối mùa (tháng 5) gán cho mọi tuần của mùa. Dùng nó để giải thích các tuần tháng 10 là dùng thông tin chưa có ở thời điểm đó.
- **Kỳ nghỉ chỉ dùng một biến** (`holiday_week`, gồm tuần lễ Tạ ơn, Giáng sinh, Năm mới). Hai biến nghỉ lễ của kho trùng nhau ở 96% số dòng.

## Tương quan trễ

Với mỗi bang, tính tương quan Spearman giữa độ chênh của yếu tố ở tuần t−k và độ chênh ILI ở tuần t, k = 0–4. Cả hai biến trừ thêm trung bình theo bang × mùa, vì ILI sau COVID tăng mức nền ngay cả khi không có cúm. Kết quả gộp bằng trung vị của 51 bang; khoảng tin cậy 95% bằng bootstrap theo bang. Báo đủ cả 5 độ trễ, không chỉ độ trễ mạnh nhất.

![Độ ẩm thấp bất thường đi trước ILI cao 1–4 tuần nhưng tương quan rất yếu; PM2.5 không có tương quan rõ](figures/tv4_lag_correlation.png){width=95%}

- **Độ ẩm:** tương quan âm ở trễ 1–4 tuần, khoảng tin cậy không chứa 0, mạnh dần theo độ trễ: ρ = −0,02 (trễ 1), −0,04 (trễ 2 và 3), −0,05 (trễ 4). Ở trễ 2–4 tuần, 82–90% số bang có ρ âm. Đúng chiều và gần đúng độ trễ (1–3 tuần) mà @shaman2010 báo cáo. Trễ 0 tuần cho tương quan dương nhỏ (+0,03), nhóm chưa có giải thích chắc chắn; điều đáng chú ý là liên hệ chỉ xuất hiện khi độ ẩm đi trước ILI, đúng với giả thuyết độ ẩm tác động qua quá trình lây truyền.
- **PM2.5:** khoảng tin cậy chứa 0 ở mọi độ trễ.
- **Độ lớn:** |ρ| không quá 0,05, tức độ ẩm giải thích một phần rất nhỏ biến thiên tuần của ILI. Kết luận đúng là "có liên hệ nhất quán về chiều nhưng yếu", không phải "độ ẩm quyết định mùa cúm".

## Kiểm chứng Shaman 2010 (bản tạm)

Với mỗi bang trong 48 bang lục địa + DC và mỗi mùa có tuần khởi phát (mốc của TV3, Chương 3), lấy độ chênh độ ẩm trung bình của 2–4 tuần trước khởi phát. Giả thuyết 0 là tuần khởi phát không liên quan đến độ ẩm: thay tuần khởi phát bằng một tuần ngẫu nhiên trong tuần mùa 5–30 của cùng bang-mùa, lặp 10.000 lần (permutation test, một phía).

![Trước khởi phát, độ ẩm thấp hơn so với khởi phát ngẫu nhiên (−0,02 so với +0,05 g/m³, p = 0,041)](figures/tv4_shaman_permutation.png){width=85%}

Trên 416 bang-mùa của 49 bang, độ chênh độ ẩm trước khởi phát thật là −0,02 g/m³. Khi chọn tuần khởi phát ngẫu nhiên, giá trị này trung bình là +0,05 g/m³ (khoảng 95%: −0,03 đến +0,13). p một phía = 0,041.

**Đây là kết quả tạm.** Mốc khởi phát dùng ở đây chưa áp dụng định nghĩa mới (khởi phát phải có xét nghiệm dương tính ≥ 2%, xem Chương 3). Với định nghĩa cũ, mùa 2021-22 có 22 bang "khởi phát" ngay tuần 40 khi chưa có cúm, nên mùa này bị bỏ khỏi phép kiểm. p = 0,041 nằm gần ngưỡng 0,05, nên kết luận chỉ được chốt sau khi chạy lại trên mốc khởi phát chính thức.

## Hồi quy Negative Binomial

**Mô hình.** Số ca ILI mỗi tuần của mỗi bang (`num_ili`) được mô hình hóa bằng hồi quy Negative Binomial, offset là log số bệnh nhân khám (`num_patients`), kèm hiệu ứng cố định theo bang, mùa và tuần mùa:

`num_ili ~ độ ẩm(t−k) + PM2.5(t−k) + vaccine mùa trước + tuần nghỉ lễ + bang + mùa + tuần mùa`

- Mỗi độ trễ k = 0–4 là một mô hình. Cả 5 mô hình dùng chung 23.843 dòng (dòng có đủ mọi biến trễ), nên AIC so được với nhau.
- Hiệu ứng cố định theo mùa hấp thụ việc ILI tăng mức nền theo thời gian; theo tuần mùa hấp thụ chu kỳ năm còn lại; theo bang hấp thụ khác biệt cố định giữa các bang.
- Rate ratio (RR) tính theo +1 g/m³ độ ẩm, +10 µg/m³ PM2.5, +10 điểm phần trăm độ phủ vaccine.

**Chọn Negative Binomial thay Poisson.** Với Poisson, thống kê Pearson χ²/bậc tự do = 160, xa mức 1 mà Poisson giả định. Kiểm định tỷ số hợp lý cho tham số phân tán α = 0 có p < 0,001. AIC giảm từ khoảng 3,6 triệu (Poisson) xuống 302 nghìn (NB). Với NB, α ≈ 0,28, Pearson χ²/bậc tự do = 1,10, tức mô hình khớp tốt.

**Khoảng tin cậy.** Các tuần liên tiếp của cùng một bang không độc lập (tự tương quan phần dư khoảng 0,87). Khoảng tin cậy và Likelihood Ratio test thông thường đều giả định độc lập, nên quá hẹp. Khoảng tin cậy chính trong chương vì vậy là khoảng 95% từ sai số chuẩn cụm theo bang. LR test vẫn được báo cáo nhưng cho p nhỏ hơn thực tế (ví dụ PM2.5 trễ 0: p LR = 0,0001 so với p cụm = 0,009). Mục kiểm tra phương pháp bên dưới cho thấy lựa chọn này đúng.

![Sau khi kiểm soát bang, mùa, tuần mùa: độ ẩm cao hơn → ILI thấp hơn; PM2.5 cao hơn → ILI cao hơn; tuần nghỉ lễ → ILI cao hơn](figures/tv4_forest_rate_ratio.png){width=100%}

| Yếu tố | Độ trễ | RR | KTC 95% (cụm) | p (Wald cụm) | p (LR) |
| --- | --- | --- | --- | --- | --- |
| Độ ẩm tuyệt đối, +1 g/m³ | 0 tuần | 0,999 | 0,994–1,005 | 0,85 | 0,83 |
| | 1 tuần | 0,981 | 0,975–0,986 | < 0,001 | < 0,001 |
| | 2 tuần | 0,975 | 0,970–0,981 | < 0,001 | < 0,001 |
| | 3 tuần | 0,977 | 0,971–0,982 | < 0,001 | < 0,001 |
| | 4 tuần | 0,977 | 0,972–0,981 | < 0,001 | < 0,001 |
| PM2.5 EPA, +10 µg/m³ | 0 tuần | 1,061 | 1,015–1,109 | 0,009 | < 0,001 |
| | 1 tuần | 1,081 | 1,031–1,134 | 0,001 | < 0,001 |
| | 2 tuần | 1,075 | 1,021–1,133 | 0,006 | < 0,001 |
| | 3 tuần | 1,084 | 1,033–1,138 | 0,001 | < 0,001 |
| | 4 tuần | 1,083 | 1,037–1,131 | < 0,001 | < 0,001 |
| Vaccine mùa trước, +10 điểm % | – | 1,007 | 0,848–1,196 | 0,93 | 0,58 |
| Tuần nghỉ lễ | – | 1,107 | 1,087–1,128 | < 0,001 | < 0,001 |

: Rate ratio của ILI theo từng yếu tố (vaccine và nghỉ lễ lấy từ mô hình trễ 0; trong 4 mô hình còn lại hai hệ số này gần như không đổi)

**Đọc kết quả:**

- **Độ ẩm:** độ ẩm cao hơn bình thường 1 g/m³ đi kèm số ca ILI thấp hơn khoảng 2–2,5% sau 1–4 tuần. Trong cùng tuần thì không thấy liên hệ. Kết quả thống nhất với phần tương quan trễ: cùng chiều, cùng khoảng độ trễ.
- **PM2.5:** PM2.5 cao hơn bình thường 10 µg/m³ đi kèm ILI cao hơn khoảng 6–8%, cùng chiều với nghiên cứu của Croft và cộng sự (2019). Tuy nhiên phần tương quan trễ không thấy liên hệ rõ. Khác biệt có thể do mô hình NB đo theo số ca và kiểm soát tuần mùa, còn tương quan trễ đo theo thứ hạng; mô hình cũng chưa kiểm soát nhiệt độ. Vì hai phép đo không thống nhất, nhóm chỉ kết luận "có dấu hiệu liên hệ", không kết luận PM2.5 gây tăng cúm.
- **Vaccine:** không phát hiện liên hệ. Khoảng tin cậy rất rộng (−15% đến +20%) vì độ phủ vaccine chỉ thay đổi theo mùa, và sau khi kiểm soát bang và mùa thì còn rất ít biến thiên để ước lượng. Đây là kết quả "không đủ dữ liệu để thấy", không phải "vaccine không có tác dụng". Kết quả cũng nhất quán với nghiên cứu medRxiv 2025: liên hệ chỉ thấy ở nhóm 18–49 tuổi, không thấy với tỷ lệ tiêm chung mà nhóm có.
- **Tuần nghỉ lễ:** ngược chiều nghiên cứu ở Úc. Biến của nhóm là tuần lễ Tạ ơn, Giáng sinh, Năm mới, không phải kỳ nghỉ học. Trong những tuần này, số lượt khám vì bệnh khác giảm, nên tỷ lệ ILI tăng một phần chỉ vì mẫu số nhỏ lại. Theo quy tắc của kế hoạch, đây vẫn được báo cáo như một kết quả âm tính kèm giải thích.

## Dữ liệu giả lập và kiểm tra phương pháp

Dữ liệu giả lập trong đề tài chỉ dùng để kiểm tra phương pháp, không bao giờ dùng để chứng minh một mối liên hệ: nếu sinh số ca từ độ ẩm rồi "tìm thấy" độ ẩm ảnh hưởng đến cúm thì đó là lập luận vòng tròn. Mọi kết luận ở các mục trên chỉ dựa trên dữ liệu thật.

**Câu hỏi:** nếu độ ẩm thật sự có hiệu ứng cỡ RR = 0,975, thì phương pháp của nhóm có tìm lại được không, và khoảng tin cậy 95% có thật sự chứa giá trị đúng 95% số lần không?

**Cách sinh dữ liệu.** Giữ nguyên biến giải thích, hiệu ứng cố định và số bệnh nhân thật. Chỉ thay số ca ILI bằng số sinh ngẫu nhiên, trong đó hiệu ứng độ ẩm trễ 2 tuần được cài sẵn. Để giữ đặc điểm quan trọng nhất của dữ liệu thật là các tuần liên tiếp phụ thuộc nhau, số ca được sinh theo phân phối Poisson-lognormal với nhiễu tự tương quan AR(1) trong từng bang-mùa. Hai tham số lấy từ dữ liệu thật: hệ số tự tương quan 0,87 và độ phân tán tương ứng α = 0,28. Chạy hai kịch bản, mỗi kịch bản 100 lần: cài RR = 0,975, và đối chứng không có hiệu ứng (RR = 1).

**Kiểm chứng bộ giả lập trước khi dùng.** So bằng hình (bảng con bên trái), không chỉ bằng con số trung bình: phân vị ILI% giả lập gần trùng phân vị thật (trung vị 1,88% so với 1,96%; phân vị 95%: 6,85% so với 6,82%); tự tương quan trễ 1 tuần là 0,92 so với 0,93.

![Phương pháp tìm lại hiệu ứng cài sẵn ở 100% số lần; khi không có hiệu ứng, khoảng tin cậy cụm báo nhầm 8%, khoảng tin cậy thường 18%](figures/tv4_kiem_tra_phuong_phap.png){width=100%}

| Kịch bản | Khoảng tin cậy | RR ước lượng (trung bình) | KTC chứa giá trị thật | Báo "có ý nghĩa" |
| --- | --- | --- | --- | --- |
| Cài RR = 0,975 | Cụm theo bang | 0,9756 | 95% | 100% |
| Cài RR = 0,975 | Thường | 0,9756 | 86% | 100% |
| Đối chứng RR = 1 | Cụm theo bang | 0,9998 | 92% | 8% |
| Đối chứng RR = 1 | Thường | 0,9998 | 82% | 18% |

: Kết quả kiểm tra phương pháp trên dữ liệu giả lập (2 kịch bản × 100 lần)

Ba kết luận:

- Ước lượng không chệch, và hiệu ứng cỡ 0,975 được phát hiện ở mọi lần chạy. Với dữ liệu 15 mùa × 51 bang, cỡ mẫu đủ để thấy hiệu ứng nhỏ như nhóm quan sát được.
- Nếu dùng khoảng tin cậy thường, khi không có hiệu ứng thì 18% số lần vẫn báo "có ý nghĩa", gần gấp bốn mức 5% danh nghĩa. Đây là căn cứ để chọn khoảng tin cậy cụm theo bang.
- Khoảng tin cậy cụm vẫn hơi lỏng (báo nhầm 8%), nên kết quả có p gần 0,05 phải đọc thận trọng. Các kết quả độ ẩm và PM2.5 ở trên có p cụm dưới 0,01, không thuộc vùng này. Kiểm chứng Shaman (p = 0,041) thì có.

**Dữ liệu chèn lỗi.** Bộ dữ liệu chèn lỗi để kiểm tra pipeline (thiếu ngẫu nhiên, mất khối nhiều tuần, trùng dòng, số sơ bộ bị sửa) do TV2 sinh và chạy trực tiếp trong bộ kiểm tra chất lượng: khoảng 510 lỗi bị bắt 100%, không báo động giả (Chương 2).

## Kịch bản what-if

Câu hỏi cho dashboard: nếu độ phủ vaccine mùa trước cao hơn 10 điểm phần trăm, ILI mùa 2025-26 sẽ thay đổi thế nào?

Nghiên cứu medRxiv 2025 trong bảng bằng chứng chỉ báo p-value, không báo độ lớn hiệu ứng, nên nhóm không có độ lớn từ tài liệu và không tự đặt ra con số. Kịch bản dùng rate ratio ước lượng từ chính dữ liệu của nhóm (RR = 1,007, khoảng tin cậy 0,85–1,20) và giữ cả hai đầu khoảng tin cậy: ILI kịch bản = ILI thật × RR.

Kết quả trên 1.419 bang × tuần của 43 bang: ILI trung bình gần như không đổi (3,00% → 3,02%), nhưng dải bất định rộng, từ 2,55% đến 3,59%. Thông điệp cho cán bộ y tế: dữ liệu giám sát cấp bang không đủ để định lượng tác dụng của việc tăng độ phủ vaccine lên ILI; điều này không có nghĩa vaccine không có tác dụng. File `whatif.parquet` có cột `is_synthetic = 1`, và dashboard vẽ đường kịch bản bằng nét đứt, có nhãn "Giả lập".

## Hạn chế

- Đây là nghiên cứu quan sát ở cấp bang × tuần: các rate ratio là liên hệ, không phải quan hệ nhân quả. Mô hình chưa kiểm soát nhiệt độ, vốn tương quan với cả độ ẩm và PM2.5.
- ILI là triệu chứng giống cúm, không phải ca cúm xác nhận. Sau COVID, ILI tăng mức nền cả khi không có cúm; hiệu ứng cố định theo mùa chỉ hấp thụ được phần thay đổi giữa các mùa.
- Độ ẩm và PM2.5 là trung bình của 3–5 thành phố lớn nhất (thời tiết) hoặc các trạm EPA trong bang, không đại diện cho mọi vùng của bang.
- Kiểm chứng Shaman là bản tạm, sẽ chạy lại khi có mốc khởi phát theo định nghĩa mới.
- Số liệu PM2.5 của EPA mới có đến tuần 30/05/2026, nên mô hình chính không có đầu mùa 2026-27.
