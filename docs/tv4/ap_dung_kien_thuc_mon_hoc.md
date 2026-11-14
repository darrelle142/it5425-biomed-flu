# TV4: Áp dụng kiến thức môn học theo từng việc

> 📍 [Mục lục tài liệu](../README.md) · Việc của TV4: [phan_cong.md](../phan_cong.md) · Lịch: [ke_hoach.md](../ke_hoach.md)

Thành viên 4 (Simulation & Risk Factor Modelling Lead) trả lời **RQ4: yếu tố nào (độ ẩm tuyệt đối, PM2.5, vaccine, nghỉ lễ) đi kèm mùa cúm sớm hoặc nặng hơn, và trễ bao nhiêu tuần?** Danh sách việc đầy đủ: [phan_cong.md](../phan_cong.md); lịch, hợp đồng dữ liệu và phạm vi đã cắt: [ke_hoach.md](../ke_hoach.md) (về đích 22/11/2026). Mục nào ghi "mở rộng" chỉ làm khi đã khóa số liệu (19/11).

Bảng dưới đây đối chiếu 5 việc của TV4 với slide môn Quản trị dữ liệu và trực quan hóa (SoICT). Số trang theo file PDF của slide. Cột "Sản phẩm" là thứ cần có trong code, hình hoặc Chương 4 để chứng minh đã áp dụng.

## Tổng quan

| Việc của TV4 | Bài áp dụng |
| --- | --- |
| 1. Bảng bằng chứng | 4 (phụ lục tương quan và nhân quả) |
| 2. Bảng phân tích, tạo biến | 4 (làm sạch, chuẩn hóa), 5.2 (feature engineering) |
| 3. Giả lập: cài hiệu ứng, chèn lỗi, what-if | 4 (phân loại lỗi chất lượng), 5.1 (so sánh phân phối) |
| 4. Tương quan trễ, kiểm chứng Shaman 2010 | 4 (tương quan), 5.1 (lag plot, scatter), 5.2 (time differences) |
| 5. Mô hình Negative Binomial | 5.1 (phân phối, phương sai, box plot), 5.2 (log, z-score, interaction, feature selection) |
| Hình của TV4 (mọi việc) | 7, 8, 10, 11 |
| Phần thống kê không có trong slide | Topic "Statistical modelling in biomedicine" (mục cuối) |

---

## Việc 1: Bảng bằng chứng

| Kiến thức | Bài (trang) | Áp dụng cụ thể | Sản phẩm |
| --- | --- | --- | --- |
| Tương quan không suy ra nhân quả; biến thứ ba (số bệnh viện và số vụ trộm xe cùng phụ thuộc dân số) | 4 (tr. 64) | Mỗi yếu tố trong bảng ghi rõ **cơ chế sinh học** từ bài báo (độ ẩm thấp → virus sống lâu hơn), không chỉ ghi "có tương quan". Chỉ ra biến thứ ba nguy hiểm nhất: mùa trong năm | Cột "cơ chế" trong bảng bằng chứng; đoạn mở đầu Chương 4 |

## Việc 2: Bảng phân tích và tạo biến

| Kiến thức | Bài (trang) | Áp dụng cụ thể | Sản phẩm |
| --- | --- | --- | --- |
| Time differences | 5.2 (tr. 62) | `ah_anomaly` = độ ẩm tuyệt đối tuần này − trung bình cùng tuần MMWR các năm của bang đó | Cột `ah_anomaly` |
| Biến trễ; cảnh báo rò rỉ dữ liệu (leakage) | 5.2 (tr. 31) | `ah_anomaly_lag1..3`, `pm25_lag1`; chỉ dùng số liệu quá khứ, không dùng tuần sau để giải thích tuần trước | Cột `*_lag1..3`; kiểm tra trong code |
| Closeness to major events (`date_X_days_before_holidays`) | 5.2 (tr. 61) | `weeks_to_holiday`: số tuần đến kỳ nghỉ gần nhất | Cột `weeks_to_holiday` |
| Binarization | 5.2 (tr. 10) | `holiday_week`, `winter_break` dạng 0/1 | Biến giả trong mô hình |
| Time binning | 5.2 (tr. 60) | `season` (từ tuần 40), `season_week`, tháng | Cột `season_week` để kiểm soát mùa vụ |
| Log transformation, Box-Cox | 5.2 (tr. 15–16) | log ILI khi đo tốc độ tăng; offset `log(num_patients)`; thử Box-Cox nếu cần | Biến tốc độ tăng log ILI |
| Z-score scaling | 5.2 (tr. 19); 4 (tr. 52) | Chuẩn hóa các yếu tố để rate ratio tính theo "mỗi 1 độ lệch chuẩn", so sánh được độ ẩm với PM2.5 | Bảng RR theo 1 SD |
| Interaction features | 5.2 (tr. 47–48) | Thử độ ẩm × nhiệt độ, vaccine × mùa | Mô hình mở rộng trong việc 5 |
| Correlation does not imply causality | 4 (tr. 64) | Lý do dùng `ah_anomaly` thay độ ẩm thô: độ ẩm và cúm cùng phụ thuộc mùa trong năm, đặt cạnh nhau sẽ tương quan giả | Một đoạn trong Chương 4 trích dẫn slide |
| Quản lý dữ liệu thiếu | 4 (tr. 46) | Thời tiết thiếu 1–2 tuần thì nội suy; số ca cúm thiếu thì **không** điền (tránh tạo đỉnh giả), gắn cờ `missing_*` | Bảng quy tắc xử lý thiếu |
| Quản lý dữ liệu nhiễu | 4 (tr. 47) | PM2.5 EPA âm (8 tuần, bang MT) → đặt thành thiếu, ghi log | Log làm sạch |

## Việc 3: Giả lập

| Kiến thức | Bài (trang) | Áp dụng cụ thể | Sản phẩm |
| --- | --- | --- | --- |
| Phân loại lỗi chất lượng: value level (missing, syntax, domain violation) | 4 (tr. 40–41) | Chèn: xóa ngẫu nhiên ô `ili_pct`; `ili_pct` = 120%; PM2.5 âm; tuần sai định dạng `YYYYWW` | Bộ dữ liệu chèn lỗi + file đáp án |
| Value-set và record level (uniqueness, integrity constraint) | 4 (tr. 42) | Chèn: `hosp_flu` > 0 nhưng `rate_flu` = 0 | Như trên |
| Relation level (approximate duplicates) | 4 (tr. 43) | Chèn: hai dòng cùng bang × tuần, khác nhau chút ít | Như trên |
| Multiple tables level (heterogeneous representation, different granularities) | 4 (tr. 44) | Chèn: "District of Columbia" lẫn "DC"; °F lẫn °C; số liệu ngày trộn vào bảng tuần | Như trên |
| Đo hiệu quả làm sạch trên mẫu | 4 (tr. 49) | TV2 chạy kiểm tra lên bộ chèn lỗi, TV4 so với đáp án, tính tỷ lệ bắt được | Bảng "loại lỗi / số chèn / số bắt được" |
| Histogram, box plot, lag plot để so phân phối | 5.1 (tr. 24, 26, 40–45) | Trước khi dùng dữ liệu giả lập: so phân phối độ cao đỉnh, tuần đỉnh, lag plot giữa giả lập và thật bằng biểu đồ, không chỉ so số trung bình | Hình `sim_vs_real.png` |

## Việc 4: Tương quan trễ và kiểm chứng Shaman 2010

| Kiến thức | Bài (trang) | Áp dụng cụ thể | Sản phẩm |
| --- | --- | --- | --- |
| Hệ số tương quan Pearson | 4 (tr. 63) | Tương quan giữa `ah_anomaly`, PM2.5 tuần t và mức tăng ILI tuần t+0…t+4, theo từng bang | Bảng tương quan theo độ trễ |
| Lag plot, tự tương quan | 5.1 (tr. 40–45) | ILI tuần này phụ thuộc mạnh tuần trước → p-value của tương quan thô bị lạc quan, cần kiểm định bằng permutation hoặc mô hình | Hình `ili_lag_plot.png` |
| Scatter plot: tuyến tính? phi tuyến? phương sai đổi theo X? ngoại lai? | 5.1 (tr. 32–38) | Vẽ `ah_anomaly` với mức tăng ILI, trả lời đủ 4 câu hỏi của slide trước khi chọn dạng mô hình | Hình `ah_vs_ili_growth.png` |
| Scatterplot matrix | 5.1 (tr. 39) | Kiểm tra tương quan giữa các yếu tố (nhiệt độ và độ ẩm tuyệt đối) → cảnh báo đa cộng tuyến | Hình `factor_matrix.png` |
| Run sequence plot: dịch chuyển vị trí | 5.1 (tr. 22) | Phát hiện mùa 2020-21 bất thường, loại khỏi phân tích | Hình chuỗi ILI theo thời gian |

## Việc 5: Mô hình Negative Binomial

| Kiến thức | Bài (trang) | Áp dụng cụ thể | Sản phẩm |
| --- | --- | --- | --- |
| Histogram, skewness, kurtosis | 5.1 (tr. 24, 28–30) | `num_ili` lệch phải mạnh → không dùng hồi quy tuyến tính, phải dùng mô hình số đếm | Hình phân phối `num_ili` |
| Phương sai, độ lệch chuẩn | 5.1 (tr. 21) | Texas mùa 2023-24: phương sai gấp 537 lần trung bình → bằng chứng trực quan cho overdispersion, chọn Negative Binomial thay Poisson | Bảng trung bình và phương sai theo bang |
| Box plot: "Is a factor significant? Does location differ between subgroups?" | 5.1 (tr. 26–27) | ILI tuần nghỉ lễ so với tuần thường; ILI theo nhóm `ah_anomaly` (khô, bình thường, ẩm) | Hình `ili_by_holiday.png` |
| Feature selection: wrapper methods | 5.2 (tr. 49–50) | Thêm hoặc bớt từng yếu tố, so bằng AIC và LR test | Bảng so sánh mô hình |
| PCA, giảm chiều | 5.1 (tr. 67–75) | Dự phòng: gộp nhiệt độ, độ ẩm, PM2.5 nếu đa cộng tuyến quá mạnh | Ghi chú trong Chương 4 nếu dùng |

## Hình của TV4

| Kiến thức | Bài (trang) | Áp dụng cụ thể | Hình |
| --- | --- | --- | --- |
| Kiểu dữ liệu: interval (Celsius, không có số 0 thật) và ratio (Kelvin) | 7 (tr. 10) | `ah_anomaly` là interval có điểm giữa 0 có nghĩa → màu diverging; rate ratio là tỷ số → trục log | Mọi hình có `ah_anomaly`, forest plot |
| Vị trí trên trục chung đọc chính xác nhất; diện tích bị đánh giá thấp | 8 (tr. 32–34) | Forest plot dùng chấm trên trục chung, không dùng cột hay bong bóng | `forest_rate_ratio.png` |
| Redundant encoding | 8 (tr. 54) | Có ý nghĩa thống kê: chấm đặc + nhãn chữ, không chỉ dựa vào màu | `forest_rate_ratio.png` |
| Dot plot, sắp xếp theo giá trị | 10 (tr. 39–41) | Sắp yếu tố trong forest plot theo độ lớn RR | `forest_rate_ratio.png` |
| Diverging color scale | 10 (tr. 22) | Tô `ah_anomaly` bằng dải xanh dương–cam, điểm giữa 0 | `ah_anomaly_heatmap.png` |
| Heatmap | 10 (tr. 42) | Bang × tuần của `ah_anomaly` trước tuần khởi phát | `ah_anomaly_heatmap.png` |
| Visualizing uncertainty, thanh sai số không rõ nghĩa là lỗi thường gặp | 10 (phần Visualizing uncertainty, tr. 60) | Ghi rõ "khoảng tin cậy 95%" trên mọi thanh sai số; vẽ khoảng tin cậy cho tương quan trễ | `forest_rate_ratio.png`, `lag_correlation.png` |
| Trục logarithmic: đặt chấm, không dùng cột | 11 (tr. 12) | Forest plot trục log, vạch dọc tại RR = 1 | `forest_rate_ratio.png` |
| Overplotting | 11 (tr. 18) | Hơn 40.000 điểm bang × tuần → làm trong suốt hoặc gộp theo bin | `ah_vs_ili_growth.png` |
| Direct labeling | 11 (tr. 30) | Ghi nhãn trực tiếp bên cạnh đường hoặc chấm thay cho chú giải | Mọi hình |
| Bảng màu Okabe-Ito cho người mù màu | 11 (tr. 37) | Màu phân loại trong mọi hình của TV4 | Mọi hình |
| Small multiples, dùng chung trục | 11 (tr. 53); 7 (tr. 43) | Độ ẩm và ILI theo từng bang, mỗi bang một ô, cùng thang | `small_multiples_ah_ili.png` |
| Principle of proportional ink | 11 | Cột (nếu có) bắt đầu từ 0; trục log thì không dùng cột | Kiểm tra mọi hình |

## Ngoài slide: topic thống kê y sinh được giao

Các phương pháp chính của TV4 không có trong slide. Chúng thuộc topic "Statistical modelling in biomedicine, models, methods and prediction; test statistics, goodness of fit test, model evaluation" (`docs/yeu_cau_mon_hoc.md`), là phần được chấm ở tiêu chí "mức độ triển khai xoay quanh topic".

| Phương pháp | Việc | Trả lời câu hỏi |
| --- | --- | --- |
| Negative Binomial với offset và hiệu ứng cố định | 5 | Tác động của từng yếu tố lên tỷ lệ ILI là bao nhiêu (rate ratio) |
| Kiểm định overdispersion (Poisson so với NB) | 5 | Chọn Negative Binomial có đúng không |
| Likelihood Ratio test | 5 | Thêm yếu tố X có làm mô hình tốt hơn có ý nghĩa không |
| AIC | 5 | Mô hình nào cân bằng tốt nhất giữa độ khớp và độ đơn giản |
| Goodness of fit: deviance, Pearson χ² (rootogram là mở rộng) | 5 | Mô hình có khớp dữ liệu không |
| Permutation test | 4 | Trước khởi phát có khô bất thường hơn ngẫu nhiên không (Shaman 2010) |
| Power analysis bằng giả lập (1 kịch bản; đường power đầy đủ là mở rộng) | 3 | Hiệu ứng nhỏ nhất mà 16 mùa dữ liệu phát hiện được |

## Đưa vào Chương 4

Kế hoạch v2 (mục 2) có bảng "chương môn học → áp dụng ở đâu". Chương 4 dùng lại bảng tổng quan ở đầu file này, kèm 1–2 câu cho mỗi dòng và tham chiếu hình tương ứng. Tiêu chí chấm có mục "sự sáng tạo trong quản trị dữ liệu và trực quan hóa", nên ghi rõ đã áp dụng bài nào, ở hình nào.
