# Phân công công việc 6 thành viên

> 📍 [Mục lục tài liệu](README.md) · Lịch và hợp đồng dữ liệu: [ke_hoach.md](ke_hoach.md)

Cập nhật 14/11/2026. Về đích 22/11/2026. Khung `src/fluwatch/` và `pipelines/` đã có sẵn trên `main` (TV1 dựng). Mỗi người một mảng, có code riêng, lệnh chạy riêng, hình riêng và phần báo cáo riêng. Phần thu thập dữ liệu đã làm xong được tính là mảng của Thành viên 1; phần còn lại của kế hoạch chia cho Thành viên 2–6, Thành viên 1 hoàn thiện nốt mảng của mình.

**Lịch, hợp đồng dữ liệu (tên file, tên cột), hạn bàn giao và phạm vi đã cắt: xem [ke_hoach.md](ke_hoach.md).** Các việc dưới đây đã được cắt cho vừa 2 tuần; việc nào ghi *(mở rộng)* chỉ làm khi đã khóa số liệu (19/11) mà còn thời gian.

## Quy ước chung

```
src/fluwatch/
  ingest/        TV1: thu thập, tự động hóa, bảo toàn dữ liệu thô
  warehouse/     TV2: clean/, business/, chất lượng
  seasonality/   TV3: mốc mùa, EDA, phân cụm
  risk_factors/  TV4: giả lập, yếu tố ảnh hưởng
  alerting/      TV5: mô hình cảnh báo, đánh giá
  dashboard/     TV6: ứng dụng Streamlit
pipelines/01_ingest.py ... 06_dashboard.py   mỗi người một lệnh chạy toàn bộ phần của mình
data/clean/  data/business/  data/sandbox/      (lưu trên Hugging Face `DragonBornRay/FluDataset`, không commit)
reports/figures/  reports/chapters/              hình và chương báo cáo (Markdown hoặc LaTeX)
```

- Mỗi người làm trên nhánh riêng, gộp vào `main` qua Pull Request, có ít nhất 1 người khác xem.
- **Mọi phân tích đọc dữ liệu qua hàm chung của TV2** (`from fluwatch.warehouse.load import load_flu_week, ...`; tên cột ở [ke_hoach.md](ke_hoach.md) mục 4.1). Đến 16/11 hàm đọc từ `data/samples/` (dữ liệu thật, đến 07/11); từ 17/11 tự đọc `data/business/` v1. Không ai phải sửa code khi đổi nguồn.
- Dữ liệu giả lập chỉ nằm trong `data/sandbox/`, luôn có cột `is_synthetic`, `sim_scenario`, `sim_seed`.
- Hình lưu PNG 300 dpi, tiêu đề là câu kết luận, bảng màu Okabe-Ito (kế hoạch v2, mục 9.3).

---

#### 📌 Gửi Thành viên 1 (Data Acquisition & Data Preservation Lead)

"Chào bạn, bạn phụ trách **thu thập toàn bộ dữ liệu thô**, biến việc thu thập thành **server tự động** và **bảo toàn dữ liệu thô** theo góp ý của thầy. Phần kỹ thuật đã xong và chạy thật; việc còn lại là cho lịch tự chạy hoạt động, ghép quyển báo cáo và viết chương của mình.

• Đã hoàn thành (kiểm chứng trên `main` và Hugging Face ngày 14/11/2026):
1. Thu thập đủ 9 nguồn của kế hoạch v2: ILINet, NHSN, NSSP, xét nghiệm, FluSurv, NWSS qua Delphi API (cả lịch sử sửa số để backtest); thời tiết và PM2.5 của 236 thành phố (Open-Meteo); EPA PM2.5 2010–2026; nước thải WVAL, vaccine, NHSN, Census. **Số liệu trên Hugging Face đến tuần kết thúc 07/11/2026.**
2. Lưu trữ: `data/raw/<nguồn>/<ngày tải>/` nguyên trạng, `raw/manifest.jsonl` ghi URL, thời điểm, sha256, máy tải; repo chung `DragonBornRay/FluDataset`, tải bằng `scripts/download_data.py`.
3. Bảng tra cứu `data/reference/` và bảng thử `data/samples/`; `scripts/audit_data.py` (kèm `--strict` làm cổng chất lượng).
4. Server tự động: workflow `crawl_cdc.yml` (nước thải `atcp-73re`, vaccine `vh55-3he6`, trang ngưỡng CDC; chạy thật 10/11 và 14/11) và `weekly_update.yml` → `pipelines/01_ingest.py` (tải → kiểm tra toàn vẹn → Delphi → thời tiết 35 ngày gần nhất → dựng bảng → audit → đẩy lên → tag → sao lưu; chạy thật 10/11 và 14/11).
5. Bảo toàn dữ liệu (`docs/bao_toan_du_lieu.md`): kiểm tra toàn vẹn manifest ↔ file ↔ Hugging Face (`verify_integrity.py`, đã bắt được 1 sự cố thật ngày 10/11); manifest chỉ thêm dòng, không ghi đè (`upload_hf.py`); tag phiên bản (`v2026-11-14` đã có); bản sao riêng tư `DragonBornRay/FluDataset-backup` (`backup_hf.py`); chạy thử khôi phục 10/11 đạt 6/6 bảng (`restore.py`).
6. Khung code `src/fluwatch/` cho cả 6 người và `pyproject.toml`; tách code thu thập thành module trong `src/fluwatch/ingest/`.

• Việc còn lại:
1. **Lịch tự chạy chưa kích hoạt lần nào** (đến 14/11 chưa có lần chạy nào với sự kiện `schedule`; các lần chạy đều bấm tay). Vào tab Actions kiểm tra workflow có bị tắt không; đổi phút trong `cron` sang số lẻ (ví dụ `17 3 * * 6`, `17 6 * * 6`) vì GitHub hay bỏ lịch đặt đúng phút :00; theo dõi lần chạy thứ Bảy 21/11.
2. Ghép quyển báo cáo tổng: dựng khuôn (LaTeX hoặc Word) trong `reports/`, gộp các chương, mục lục, tài liệu tham khảo. Hạn: có khuôn trước tối 15/11 để mọi người viết vào.
3. Chạy thử toàn bộ pipeline từ máy trống theo README để chắc người khác dựng lại được.
4. *(Khi TV2–TV5 bàn giao)* Gọi thêm `pipelines/02`–`05` trong workflow hằng tuần.

• Sản phẩm nộp: code trong `scripts/`, `src/fluwatch/ingest/`, `pipelines/01_ingest.py` và `.github/workflows/`; ảnh chụp các lần chạy tự động làm minh chứng; quyển báo cáo PDF tổng; viết **Chương 1 (bài toán, người dùng, câu hỏi nghiên cứu, nguồn dữ liệu) và Chương 2.1 (thu thập, tự động hóa, bảo toàn dữ liệu)** của báo cáo."

---

#### 📌 Gửi Thành viên 2 (Data Warehouse & Data Quality Lead)

"Chào bạn, bạn phụ trách dựng **data lake và star schema** mà cả nhóm sẽ đọc, cùng hệ thống kiểm tra chất lượng dữ liệu.

• Đầu vào: `data/raw/` và `data/reference/` (tải bằng `python scripts/download_data.py`); kế hoạch v2 mục 5–6.

• Việc cần làm:
1. Vùng `data/clean/`: mỗi nguồn một bảng Parquet đã chuẩn hóa (mã bang 2 chữ, tuần MMWR, `season`, `season_week`, đơn vị), lọc GU/VI/PR, PM2.5 âm đặt thành thiếu và ghi log, lấy thời tiết từ bản 3–5 thành phố, vaccine lấy tháng cuối có số.
2. Vùng `data/business/` theo star schema: `dim_state` (vùng HHS, dân số, cờ 48 bang lục địa, `cluster_id` để TV3 điền), `dim_time`, `dim_source`, `fact_flu_week` (đủ cột trong từ điển dữ liệu: `ah_anomaly`, biến trễ, `wow_pct`, `yoy_pct`, `is_preliminary`, `missing_*`), `fact_season_summary` (vaccine + chỗ trống cho mốc mùa của TV3); một file DuckDB để truy vấn roll-up, drill-down, slice, dice, pivot.
3. Bảng quy tắc chất lượng 4 mức (giá trị, bản ghi, quan hệ, nhiều bảng) chạy tự động, xuất báo cáo dạng Markdown (HTML là mở rộng); báo cáo độ phủ bang × năm (cờ thiếu > 30%), kiểm tra khóa, kiểm tra tổng các bang so với toàn quốc.
4. Chạy kiểm tra ở bước 3 trên bộ dữ liệu bị chèn lỗi do TV4 sinh ra (thiếu ngẫu nhiên, mất khối nhiều tuần, trùng dòng, số liệu sơ bộ bị sửa) và chứng minh bắt được 100% lỗi.
5. Tài liệu quản trị dữ liệu: người phụ trách từng nguồn (điền vào `dim_source`), lineage từng cột (cột nào đến từ nguồn nào, qua phép biến đổi nào), quy tắc cập nhật 4 tuần gần nhất.

• Mốc gấp: **`load.py` đọc `samples/` đúng tên cột (CN 15/11, trưa)**, **`business/` v1 lên Hugging Face và `load.py` chuyển sang đọc `business/` (T3 17/11)**. TV1 hỗ trợ phần `clean/` của thời tiết, EPA, vaccine (chia file, không sửa chung).

• Sản phẩm nộp: code trong `src/fluwatch/warehouse/`, chạy bằng `python pipelines/02_warehouse.py`; `data/business/*.parquet`; báo cáo chất lượng `reports/data_quality/README.md`; `docs/tu_dien_du_lieu.md`, `docs/quan_tri_du_lieu.md`; viết **Chương 2.2–2.4 (kiến trúc data lake, star schema, quản trị và chất lượng dữ liệu)**."

---

#### 📌 Gửi Thành viên 3 (Seasonality, EDA & Clustering Lead — RQ1, RQ2, RQ3)

"Chào bạn, bạn phụ trách trả lời **mùa cúm đang ở đâu, năm nay sớm hay muộn, nhẹ hay nặng, bang nào lên trước**.

• Đầu vào: `load_flu_week()`, `load_dim_state()`, `load_dim_time()` của TV2 (đọc `samples/` đến 16/11, `business/` từ 17/11). Giao: stub 3 file 15/11, `season_milestones` + `season_phase` thật 17/11, `state_cluster` thật 18/11 (tên cột: [ke_hoach.md](ke_hoach.md) mục 4.2).

• Việc cần làm:
1. Mốc mùa theo định nghĩa thống nhất: mức nền kiểu CDC (tuần không có cúm của 3 mùa trước, + 2 độ lệch chuẩn, bỏ mùa 2020-21), tuần khởi phát (3 tuần liên tiếp ≥ mức nền), tuần đỉnh, giá trị đỉnh, `season_phase`. 8 bang thiếu ILINet mùa 2025-26 dùng NSSP. Ghi vào `fact_season_summary`.
2. EDA: chồng các mùa theo `season_week`, boxplot độ nặng theo mùa, ridgeline tuần khởi phát, lag plot và ACF chuỗi ILI, heatmap bang × tuần sắp theo tuần khởi phát.
3. Phân cụm bang theo hình dạng đường cong (z-score theo `season_week`): hierarchical (Ward) và k-means, chọn k bằng silhouette, vẽ dendrogram; ghi `cluster_id` vào `dim_state`.
4. Kiểm định: so sánh tuần khởi phát và độ nặng giữa các vùng HHS (Kruskal-Wallis, hậu kiểm Dunn), *(mở rộng)* xu hướng khởi phát qua các năm (Mann-Kendall), tương quan tuần khởi phát với kinh độ/vĩ độ để mô tả hướng lan.

• Sản phẩm nộp: code trong `src/fluwatch/seasonality/`, chạy bằng `python pipelines/03_season_eda.py`; hình trong `reports/figures/` (`season_overlay.png`, `onset_ridgeline.png`, `heatmap_state_week.png`, `dendrogram.png`…); viết **Chương 3 (mô tả mùa vụ, EDA, phân cụm)**."

---

#### 📌 Gửi Thành viên 4 (Simulation & Risk Factor Modelling Lead — RQ4)

"Chào bạn, bạn phụ trách **dữ liệu giả lập** và trả lời **yếu tố nào (độ ẩm, PM2.5, vaccine, nghỉ lễ) đi kèm mùa cúm sớm hoặc nặng hơn, trễ bao nhiêu tuần**.

• Đầu vào: `load_flu_week()` (có sẵn cột `ah_anomaly`), `load_season_summary()`, mốc mùa của TV3 (stub 15/11, thật 17/11); 6 bài báo ở kế hoạch v2 mục 8. Giao: stub `risk_rate_ratios.csv`, `whatif.parquet` 15/11, bản thật 18/11 (tên cột: [ke_hoach.md](ke_hoach.md) mục 4.2).

• Việc cần làm:
1. Bảng bằng chứng tầng 2: với mỗi yếu tố ghi chiều tác động, độ trễ, độ lớn hiệu ứng từ bài báo (Shaman 2009/2010, Croft 2019, medRxiv 2025, nghiên cứu nước thải, Úc 2019).
2. Dữ liệu giả lập trong `data/sandbox/`, chỉ dùng cho những việc dữ liệu thật không làm được (dữ liệu thật đã crawl đủ nên không cần giả lập để dựng dashboard): (a) các kịch bản cài sẵn hiệu ứng có độ lớn lấy từ bài báo để kiểm tra phương pháp có tìm lại được hiệu ứng không, và phân tích cỡ mẫu (làm 1 kịch bản; đường power đầy đủ là mở rộng); (b) bộ dữ liệu bị chèn lỗi có đáp án (thiếu ngẫu nhiên, mất khối, trùng dòng, số sơ bộ bị sửa) để TV2 kiểm tra pipeline. (c) kịch bản what-if cho trang Cảnh báo của dashboard: độ phủ vaccine tăng 10 điểm phần trăm (kịch bản "mùa đông khô bất thường" là mở rộng). Kiểm chứng phân phối giả lập so với thật bằng biểu đồ.
3. Tương quan chéo theo độ trễ 0–4 tuần giữa từng yếu tố (đã loại mùa vụ, dùng `ah_anomaly`) và ILI; kiểm chứng Shaman 2010 bằng permutation test trên 48 bang lục địa + DC.
4. Hồi quy Negative Binomial trên ILINet (offset số bệnh nhân, hiệu ứng cố định bang và mùa, `season_week`): Likelihood Ratio test cho từng yếu tố, AIC, kiểm định overdispersion (Poisson vs NB), độ phù hợp (deviance, Pearson χ²; rootogram là mở rộng); forest plot rate ratio trên trục log.

• Sản phẩm nộp: code trong `src/fluwatch/risk_factors/`, chạy bằng `python pipelines/04_risk_factors.py`; `data/sandbox/`; hình `forest_rate_ratio.png`, `lag_correlation.png`, `shaman_permutation.png`; bảng bằng chứng; viết **Chương 4 (yếu tố ảnh hưởng, giả lập và kiểm tra phương pháp)**."

---

#### 📌 Gửi Thành viên 5 (Early Warning Model & ROC Evaluation Lead — RQ5)

"Chào bạn, bạn phụ trách **mô hình cảnh báo 1–4 tuần tới** và đánh giá độ tin cậy của nó, đúng trọng tâm môn học (test statistics, goodness of fit, model evaluation, ROC).

• Đầu vào: `load_flu_week()` (nhãn mức CDC `cdc_level`, ILI, NSSP, nước thải), mốc mùa của TV3 (stub 15/11, thật 17/11), các file lịch sử sửa số `raw/*/archive__*` để backtest đúng như lúc công bố; dữ liệu giả lập của TV4. Giao: stub `alert_forecast.parquet`, `model_eval.json` + `roc_points.csv` 15/11, bản thật 18/11 (tên cột: [ke_hoach.md](ke_hoach.md) mục 4.2).

• Việc cần làm:
1. Nhãn và dữ liệu huấn luyện: `alert_level`, `y_exceed_1w`, `y_exceed_2w`, `y_onset_next2w`. Sinh lịch sử nhập viện giả lập 2010–2023 (Negative Binomial ILI → nhập viện theo bang trên 2 mùa NHSN, bỏ 2020-21, kèm khoảng bất định), lưu trong `data/sandbox/`.
2. Mô hình: logistic dự đoán khởi phát (ILINet nhiều mùa) và vượt ngưỡng (huấn luyện trên giả lập + 2024-25, test trên mùa thật 2025-26); so với mô hình nền (persistence); xuất `prob_exceed` (xác suất vượt ngưỡng 1 và 2 tuần tới) và xác suất khởi phát; *(mở rộng)* dự báo dạng quạt `pred_1w`…`pred_4w`, `pred_lo`, `pred_hi`.
3. Đánh giá: ROC và AUC (khoảng tin cậy bootstrap), PR curve, DeLong test so mô hình có/không có nước thải và cấp cứu, calibration curve + Brier score + Hosmer-Lemeshow, chọn ngưỡng bằng Youden's J; backtest theo từng tuần mùa 2025-26 dùng số liệu đúng như lúc công bố.
4. Xuất kết quả dự báo thành file Parquet để TV2 ghép vào `data/business/`; *(mở rộng)* đưa vào chạy hằng tuần trong workflow của TV1.

• Sản phẩm nộp: code trong `src/fluwatch/alerting/`, chạy bằng `python pipelines/05_alert_model.py`; mô hình trong `models/*.joblib`; hình `roc_compare.png`, `calibration_curve.png`, `backtest_timeline.png`; viết **Chương 5 (mô hình cảnh báo và đánh giá)**."

---

#### 📌 Gửi Thành viên 6 (Dashboard & Storytelling Lead)

"Chào bạn, bạn phụ trách **dashboard cho cán bộ y tế** và slide thuyết trình.

• Đầu vào: `load_flu_week()`, `load_dim_state()` của TV2; file kết quả của TV3, TV4, TV5 (stub từ 15/11, thật từ 17–18/11, tên cột: [ke_hoach.md](ke_hoach.md) mục 4.2); kế hoạch v2 mục 9.2–9.3.

• Việc cần làm:
1. Ứng dụng Streamlit `src/fluwatch/dashboard/app.py` đọc thẳng Parquet từ Hugging Face (tự cập nhật khi server của TV1 chạy). 15/11: khung 5 trang + Phương pháp trên `load_flu_week()` và file stub; 18/11 thay stub bằng file thật (cùng tên, không phải sửa code).
2. Năm trang và trang Phương pháp:
   - Tình hình hiện tại: thẻ KPI, nhãn giai đoạn mùa, đèn cảnh báo (màu + biểu tượng + chữ), tile map 51 bang.
   - Mùa vụ: chồng các mùa, dải mức nền, bảng tuần khởi phát và đỉnh (TV3).
   - Địa lý: tile map có thanh trượt tuần, heatmap bang × tuần, top 10 bang tăng nhanh nhất.
   - Yếu tố ảnh hưởng: small multiples độ ẩm và ILI, forest plot (TV4).
   - Cảnh báo và đối ứng: xác suất vượt ngưỡng 1–2 tuần tới (dự báo dạng quạt là mở rộng), bảng hành động theo mức cảnh báo, what-if vaccine (TV5).
   - Phương pháp: ROC, calibration, backtest (TV5); sức khỏe dữ liệu (TV1, TV2).
   - Bộ lọc chung bang, vùng HHS, mùa; roll-up và drill-down toàn quốc → vùng → bang.
3. Theo đúng quy tắc thiết kế: tile map thay choropleth, Okabe-Ito, số liệu sơ bộ và giả lập vẽ nét đứt có nhãn, tiêu đề là câu kết luận. *(Mở rộng)* tile map có chuyển động, kiểm tra bằng công cụ giả lập mù màu.
4. Làm slide (slide đầu ghi công việc và % đóng góp từng người; mỗi thành viên gửi 1–2 slide nội dung của mình); dựng câu chuyện quanh mùa 2024-25. Quyển báo cáo tổng do TV1 ghép.

• Sản phẩm nộp: chạy được bằng `python pipelines/06_dashboard.py` (gọi `streamlit run`), triển khai bản online trên Streamlit Community Cloud; slide PDF; viết **Chương 6 (dashboard và storytelling) và Kết luận (liên hệ Việt Nam)**."

---

## Lịch và bàn giao

Xem [ke_hoach.md](ke_hoach.md) mục 5 (lịch 6 luồng) và mục 4.2 (file mỗi người giao, hạn stub và bản thật).
