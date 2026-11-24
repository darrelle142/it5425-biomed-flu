<!-- Nguoi phu trach: TV5. Chi sua file nay. So lieu: python pipelines/05_alert_model.py -> data/business/model_eval.json -->

# Mô hình cảnh báo sớm và đánh giá

Chương này trả lời RQ5: *trong 1–2 tuần tới, một bang có vượt ngưỡng báo động không?* Toàn bộ kết quả được tạo lại bằng một lệnh: `python pipelines/05_alert_model.py`.

## Nhãn và dữ liệu huấn luyện

Dữ liệu là bảng bang × tuần đọc qua `load_flu_week()` (51 bang, 2010–2026).

- **Mức cảnh báo** (`alert_level`) gộp từ mức CDC dựa trên tỉ lệ nhập viện NHSN: mức 0–1 → *thấp*, 2 → *trung bình*, 3–4 → *cao*. Ngưỡng của từng bang lấy từ bảng ngưỡng CDC.
- **Vượt ngưỡng** `y_exceed_1w`, `y_exceed_2w` = 1 nếu 1 (2) tuần sau bang ở mức *cao*. Nhãn được ghép theo ngày của cùng bang, không theo vị trí dòng.
- **Khởi phát** `y_onset_next2w` = 1 nếu mùa cúm của bang khởi phát trong 2 tuần tới, theo tuần khởi phát chung của Chương 3 (xem đoạn *Nhãn khởi phát* bên dưới). Nhãn chỉ tính cho các tuần chưa khởi phát.
- Bỏ khỏi huấn luyện và đánh giá: 4 tuần gần nhất (số sơ bộ), mùa 2020-21, các tuần NHSN báo cáo ít (`low_reporting`), và các tuần mà tuần đích còn là số sơ bộ.

Chia theo **mùa**, không xáo trộn. Mô hình vượt ngưỡng huấn luyện trên 2022-23 đến 2024-25, vì trước đó gần như không có mức *cao* (mùa 2021-22 chỉ có 2 tuần–bang). Mô hình khởi phát huấn luyện trên mọi mùa ILINet đến 2024-25. Cả hai được kiểm tra trên mùa **2025-26**.

| Mùa | Dòng có nhãn vượt ngưỡng | Số dòng mức *cao* 1 tuần sau |
| --- | --- | --- |
| 2022-23 | 2652 | 109 |
| 2023-24 | 1933 | 45 |
| 2024-25 | 2481 | 378 |
| 2025-26 (test) | 2703 | 151 |

: Số dòng bang × tuần có nhãn theo mùa (sau khi bỏ tuần sơ bộ và tuần NHSN báo cáo ít)

Lịch sử nhập viện giả lập 2010–2023 (kế hoạch v2 mục 7) không dùng, vì NHSN thật đã có đủ 3 mùa có mức *cao* (532 dòng dương để huấn luyện). Quyết định này đã được người quản lý tiến độ đồng ý và ghi vào `docs/ke_hoach.md`. Các tuần NHSN báo cáo ít (5–10/2024, cột `low_reporting`) bị loại khỏi huấn luyện và đánh giá vì nhãn mức CDC ở các tuần này không đáng tin; tập huấn luyện vượt ngưỡng còn 7.066 dòng.

**Nhãn khởi phát** lấy từ mốc mùa của Chương 3 (`season_milestones.parquet`), để cả nhóm dùng một định nghĩa khởi phát: 3 tuần liên tiếp ≥ mức nền và, từ mùa 2016-17, tuần đầu có xét nghiệm dương tính ≥ 2%.

**Tầm dự báo tính từ đâu.** Mô hình dùng số liệu của tuần *t* để dự báo tuần *t* + 1 và *t* + 2. Số NHSN và ILINet của tuần *t* được công bố khoảng một tuần sau (backtest bên dưới giả định đúng như vậy). Vì thế, tính từ lúc có số liệu, dự báo "1 tuần" thực chất là ước lượng tuần đang diễn ra, còn dự báo "2 tuần" mới là báo trước khoảng 1 tuần. Dashboard ghi rõ tuần đích (`target_week`) thay vì chỉ ghi "1 tuần tới".

## Mô hình

Hồi quy logistic (chuẩn hóa biến, hệ số phạt L2 mặc định) với các biến đều đo **tại tuần phát hành dự báo**:

- tỉ lệ nhập viện chia ngưỡng *cao* của bang (thang log) và thay đổi so với tuần trước;
- ILI% và thay đổi so với tuần trước (mô hình khởi phát dùng tỉ số ILI / mức nền);
- độ ẩm tuyệt đối bất thường `ah_anomaly`; tuần trong mùa `season_week`.

Có ba biến thể lồng nhau: **chỉ nhập viện** (`nhsn`), **nhập viện + ILI** (`base`) và **thêm cấp cứu `ed_pct_flu` và nước thải `wval`** (`full`). Khi dự báo, mỗi bang dùng biến thể đầy đủ nhất mà nó có số liệu. So sánh với **hai mô hình nền**: (1) *persistence*: "tuần tới ở mức *cao* nếu tuần này ở mức *cao*" (0/1); (2) **hiện trạng**: dùng thẳng tỉ lệ nhập viện hiện tại chia ngưỡng *cao* làm điểm số, không cần học gì. Mô hình nền thứ hai mạnh hơn nhiều và là phép thử thật: mô hình chỉ có giá trị nếu hơn được việc nhìn số nhập viện tuần này. Riêng với khởi phát, mô hình nền là tỉ số ILI / mức nền hiện tại.

Ngưỡng phát cảnh báo chọn bằng **Youden's J** trên tập huấn luyện. Trong file dự báo, *cao* = xác suất ≥ ngưỡng và *trung bình* = xác suất ≥ một nửa ngưỡng. Đây là **mức của mô hình**, không phải mức CDC.

## Đánh giá (RQ5)

Mọi mô hình được so trên **cùng** tập dòng test (2205 dòng, 122 dương). Khoảng tin cậy 95% của AUC tính bằng bootstrap 1000 lần **theo bang**, vì các tuần cùng bang không độc lập. Hai đường ROC được so bằng kiểm định DeLong.

![Mô hình logistic hơn việc chỉ nhìn số nhập viện hiện tại, rõ nhất ở tầm 2 tuần](figures/tv5_roc_compare.png){width=95%}

| Mô hình | AUC 1 tuần [KTC 95%] | AUC 2 tuần [KTC 95%] | Brier 1 tuần | Brier 2 tuần |
| --- | --- | --- | --- | --- |
| Nền: đã ở mức Cao (0/1) | 0,818 [0,789–0,842] | 0,675 [0,637–0,708] | 0,038 | 0,068 |
| Nền: nhập viện hiện tại / ngưỡng | 0,974 [0,969–0,979] | 0,912 [0,900–0,924] | – | – |
| Chỉ nhập viện | 0,990 [0,986–0,993] | 0,960 [0,953–0,967] | 0,018 | 0,038 |
| Nhập viện + ILI | 0,993 [0,990–0,996] | 0,968 [0,961–0,974] | 0,014 | 0,033 |
| + cấp cứu, nước thải | 0,993 [0,990–0,996] | 0,968 [0,961–0,975] | 0,014 | 0,033 |

: Khả năng phân biệt và sai số xác suất, mùa test 2025-26

Kiểm định DeLong:

- So với mô hình nền 0/1, chênh AUC rất lớn (+0,175 và +0,293), nhưng phần lớn chỉ vì điểm số 0/1 không xếp hạng được. **So với mô hình nền hiện trạng**, mô hình vẫn hơn có ý nghĩa: +0,019 (1 tuần, p < 10⁻¹⁰) và +0,056 (2 tuần, p < 10⁻²⁸). Đây mới là giá trị thật của mô hình: nó dùng thêm xu hướng (thay đổi so với tuần trước), ILI, độ ẩm và thời điểm trong mùa, và lợi ích lớn dần khi tầm dự báo xa hơn.
- Thêm ILI vào số nhập viện giúp chút ít nhưng có ý nghĩa: +0,003 (p = 0,0006) và +0,008 (p < 10⁻¹⁰).
- Thêm **cấp cứu và nước thải không cải thiện**: chênh −0,0001 (p = 0,35) và +0,0005 (p = 0,26). Đây là kết quả âm tính, phù hợp với bằng chứng còn mâu thuẫn về tín hiệu dẫn trước của nước thải. Kết quả này khớp với Chương 3: tính đến lúc chạm nửa đỉnh, nước thải và cấp cứu chỉ đi trước nhập viện 0,3–0,6 tuần (khoảng một nửa số bang-mùa), trong khi ILI đi trước 2,5 tuần ở 87% số bang-mùa. Khi mô hình đã có ILI và số nhập viện tuần này, hai tín hiệu kia không còn mang thêm thông tin.

AUC chỉ cao một phần vì nhiều bang đã ở mức *cao* từ trước. Xét riêng các tuần bang **chưa** ở mức *cao*, tức lúc cần cảnh báo sớm, AUC vẫn là 0,990 [0,983–0,995] với 1 tuần (42 dương) và 0,971 [0,962–0,980] với 2 tuần (75 dương).

**Đường precision-recall.** Vì chỉ 5,5% dòng là dương, AUC có thể làm khác biệt giữa các mô hình trông nhỏ hơn thực tế. Đường PR trả lời câu hỏi thực tế hơn: trong các lần phát cảnh báo, bao nhiêu phần trăm là đúng. Theo diện tích dưới đường PR (AP), khoảng cách giữa mô hình và mô hình nền hiện trạng rộng hơn nhiều so với khi đo bằng AUC: 0,914 so với 0,746 ở tầm 1 tuần, và 0,638 so với 0,349 ở tầm 2 tuần (đoán bừa: 0,055). Ở ngưỡng đang dùng, khoảng một nửa số cảnh báo tầm 1 tuần là đúng (47%) trong khi gần như không bỏ sót ca nào (99%).

![Ở ngưỡng đang dùng, khoảng 1/2 cảnh báo là đúng, đổi lại gần như không bỏ sót](figures/tv5_pr_curve.png){width=95%}

![Xác suất dự báo 1 tuần khớp thực tế; dự báo 2 tuần lệch nhẹ nhưng vẫn xếp hạng tốt](figures/tv5_calibration_curve.png){width=95%}

**Hiệu chỉnh.** Kiểm định Hosmer-Lemeshow (10 nhóm, bậc tự do g − 2) không bác bỏ hiệu chỉnh tốt ở dự báo 1 tuần (p = 0,99). Ở dự báo 2 tuần thì có bác bỏ ở mức 5% (p = 0,037 với mô hình đầy đủ): mô hình đánh giá quá cao xác suất ở vùng 0,4–0,9. Vì vậy dashboard nên hiển thị mức cảnh báo hơn là con số phần trăm chính xác cho tầm 2 tuần.

**Ngưỡng.** Ngưỡng Youden của mô hình *nhập viện + ILI* là 0,047 (1 tuần). Trên mùa test, ngưỡng này cho độ nhạy 0,99, độ đặc hiệu 0,93, nhưng giá trị dự đoán dương chỉ 0,47: khoảng một nửa số báo động là báo giả. Với tầm 2 tuần, ngưỡng 0,055 cho độ nhạy 0,91, độ đặc hiệu 0,91 và giá trị dự đoán dương 0,36. Tỉ lệ dương thấp (5,5%) khiến ngưỡng Youden ưu tiên không bỏ sót. Với mục đích chuẩn bị giường bệnh, đó là lựa chọn chấp nhận được.

**Khởi phát.** Với nhãn khởi phát chung của Chương 3, mô hình khởi phát đạt AUC 0,820 [0,767–0,870] (bản đầy đủ) và 0,672 (bản base), **thua** mô hình nền chỉ dùng tỉ số ILI / mức nền (0,872 [0,830–0,910]; DeLong p = 0,010 với bản đầy đủ). Bản đầy đủ còn lệch xác suất (Hosmer-Lemeshow p = 0,002). Kết luận: để báo khởi phát, theo dõi ILI so với mức nền là đủ và tốt hơn mô hình logistic; dashboard dùng chính tỉ số này. Ở bản đầu, khi TV5 tự tính khởi phát không có điều kiện xét nghiệm, mô hình trông ngang mô hình nền (0,858 so với 0,869): một phần khả năng dự báo khi đó đến từ các khởi phát giả mà chính ILI tạo ra. Mẫu test nhỏ (412 dòng, 82 dương).

## Backtest mùa 2025-26 đúng như lúc công bố

Các số ở trên dùng số liệu **đã sửa**. Ngoài thực tế, mỗi tuần chỉ có số sơ bộ. Để mô phỏng việc dùng thật, với mỗi tuần *t* của mùa 2025-26 chúng tôi lấy giá trị ILINet và NHSN theo **bản công bố mới nhất có đến thứ Bảy tuần sau** (lịch sử sửa số Delphi `raw/*/archive__*`) [@delphi_epidata], rồi dự báo *t* + 1 và *t* + 2 bằng chính các mô hình đã huấn luyện.

| Mô hình | Tầm | AUC số sơ bộ [KTC 95%] | AUC số đã sửa | Nền 0/1 (số sơ bộ) | Nền hiện trạng (số sơ bộ) |
| --- | --- | --- | --- | --- | --- |
| Chỉ nhập viện | 1 tuần | 0,985 [0,979–0,990] | 0,989 | 0,786 | 0,969 |
| Nhập viện + ILI | 1 tuần | 0,988 [0,980–0,996] | 0,992 | 0,842 | 0,981 |
| Chỉ nhập viện | 2 tuần | 0,955 [0,948–0,962] | 0,958 | 0,652 | 0,902 |
| Nhập viện + ILI | 2 tuần | 0,949 [0,935–0,962] | 0,951 | 0,625 | 0,873 |

: Backtest: AUC khi dùng số liệu như lúc công bố so với số đã sửa

Số sơ bộ chỉ làm AUC giảm 0,002–0,004, và mô hình vẫn hơn mô hình nền hiện trạng trên số sơ bộ (DeLong p < 10⁻¹¹ ở tầm 2 tuần; ở tầm 1 tuần bản *nhập viện + ILI* chỉ hơn sát ngưỡng, p = 0,055). Khó khăn lớn hơn là **độ phủ**: lúc phát hành, ILI mới có cho 63% số bang–tuần, còn NHSN có cho 91%. Nếu chỉ dùng mô hình cần ILI, 11/45 bang lên mức *cao* sẽ không nhận được cảnh báo nào. Vì vậy hệ thống tự lùi về mô hình *chỉ nhập viện* khi thiếu ILI.

![Cảnh báo đến trước hoặc đúng tuần lên mức Cao ở 45/45 bang, trung vị sớm 1 tuần](figures/tv5_backtest_timeline.png){width=100%}

Với cơ chế lùi này, cả **45/45** bang lên mức *cao* trong mùa 2025-26 đều được cảnh báo trước hoặc đúng tuần lên *cao*: 7 bang báo đúng tuần, 28 bang trước 1 tuần, 8 bang trước 2 tuần, 2 bang trước 3 tuần trở lên. Có 4 bang có cảnh báo nhưng cả mùa không lên *cao*.

**Hạn chế.**

1. Chỉ một mùa test, và các bang cùng mùa chịu chung một đợt dịch, nên khoảng tin cậy có thể hơi hẹp. p của DeLong giả định các dòng độc lập.
2. Nước thải và độ ẩm không có lịch sử sửa số, nên backtest không đánh giá được bản đầy đủ.
3. Mô hình được huấn luyện trên số đã sửa, vì không có số sơ bộ trước 10/2024.
4. Tầm báo trước thực tế chủ yếu là 1 tuần. Muốn sớm hơn phải dùng tầm 2 tuần, chấp nhận AUC thấp hơn và xác suất kém chuẩn hơn.
5. Xác suất tầm 2 tuần chưa hiệu chỉnh tốt (Hosmer-Lemeshow p = 0,01–0,04). Chúng tôi đã thử hiệu chỉnh lại bằng Platt và isotonic, học trên dự báo chéo theo mùa của 3 mùa huấn luyện (để riêng từng mùa, huấn luyện trên 2 mùa còn lại), không dùng mùa test. Kết quả không tốt hơn: Hosmer-Lemeshow p giảm còn 0,006 (Platt) và 0,011 (isotonic), Brier gần như không đổi (0,0328 và 0,0326 so với 0,0328). Trên các mùa huấn luyện, mô hình không hề đánh giá quá cao xác suất, nên độ lệch ở mùa 2025-26 là đặc thù của mùa này, không sửa được bằng dữ liệu các mùa trước. Vì vậy chúng tôi giữ xác suất gốc và khuyên dùng mức cảnh báo thay vì con số phần trăm ở tầm 2 tuần.
