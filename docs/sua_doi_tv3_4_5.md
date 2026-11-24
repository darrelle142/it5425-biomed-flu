# Hoàn thiện phần TV3, TV4, TV5 (24/11/2026)

> 📍 [Mục lục tài liệu](README.md) · Kế hoạch: [ke_hoach.md](ke_hoach.md) (mục 1b: lịch mới, mục 10: các điểm đã chốt)

**Người thực hiện:** TV1 (Hiếu), được người quản lý tiến độ (Dũng) đồng ý ngày 24/11/2026.
**Nhánh:** `ql/hoan-thien-tv3-4-5`, gộp vào `main` qua Pull Request.

File này ghi lại TV1 đã sửa gì trong phần của TV3, TV4, TV5, vì sao sửa, và mỗi người cần làm gì tiếp. Không ai bị mất công: mọi commit của các bạn được giữ nguyên tên tác giả, phần sửa của TV1 là các commit riêng phía sau.

## 1. Vì sao phải sửa

Khi xem 3 nhánh `tv3/eda`, `tv4/yeu-to-anh-huong`, `tv5/alert-model` (23/11), mỗi phần chạy được và làm tốt, nhưng **ba phần không khớp nhau**:

| Vấn đề | Hậu quả nếu để nguyên |
| --- | --- |
| TV3 và TV5 tính tuần khởi phát theo hai cách khác nhau, cả hai đều chưa có điều kiện xét nghiệm mà TV4 đề xuất | Chương 3 và Chương 5 nói khác nhau về cùng một mùa (chỉ 59% bang-mùa trùng tuần khởi phát); Shaman của TV4 phải bỏ mùa 2021-22 và chỉ đạt p = 0,041 |
| File của TV3 sai hợp đồng ở một số chỗ (kiểu `onset_week`, tên hình) | TV2 ghép kho, TV6 vẽ dashboard sai cột |
| TV5 so mô hình với mô hình nền quá yếu (0/1) | Chương 5 báo cải thiện +0,18 AUC, trong khi so với mô hình nền hợp lý chỉ +0,02; thầy hỏi là lộ |
| Bộ dữ liệu chèn lỗi của TV4 chưa có | TV2 chỉ kiểm tra được trên bộ lỗi do chính mình sinh |
| Phân cụm của TV3 cho 2 cụm 46/5 bang, khó giải thích | RQ3 thiếu kết luận |

Cách làm: dùng **một định nghĩa khởi phát chung** (của TV3, có điều kiện xét nghiệm), rồi cho TV4 và TV5 đọc chung file `season_milestones.parquet`.

## 2. Những gì đã sửa

### TV3: mùa vụ, EDA, phân cụm (`src/fluwatch/seasonality/`, `pipelines/03_season_eda.py`)

| Commit | Thay đổi |
| --- | --- |
| `TV3 moc mua: ...` | `milestones.py`: tuần khởi phát phải có `lab_pct_pos` ≥ 2% từ mùa 2016-17 (thiếu thì lấy trung vị vùng HHS); thêm cột `onset_date`, `peak_date`, `onset_lab_pct_pos`; mùa hiện tại tự lấy theo dữ liệu, không ghi cứng `2026-27`. `onset_week`, `peak_week` giữ là **số tuần trong mùa** |
| `TV3 phan cum: ...` | `clustering.py` viết lại: chuẩn hóa z-score theo **từng bang-mùa** rồi lấy trung bình (trước đây lấy trung bình ILI thô rồi mới chuẩn hóa, nên bang có mức ILI cao bị kéo riêng ra); bỏ FL (chỉ 5 mùa ILINet); thêm chỉ số Rand hiệu chỉnh Ward/k-means và **kiểm định tính vùng** (permutation test với 3 bang gần nhất) |
| `TV3 phat hien them: ...` | File mới `insights.py`: tín hiệu nào báo sớm nhất, mùa hiện tại sớm hay muộn, hướng lan theo vĩ độ, xu hướng khởi phát qua các mùa (Mann-Kendall); 3 hình mới; mọi hình đổi tên `tv3_*.png` (đúng quy ước báo cáo) và chú thích tiếng Việt; `03_season_eda.py` viết lại gọn, ghi thêm `season_insights.json`, `season_signal_lead.csv` |
| `Chuong 3 ban nhap ...` | **Bản nháp** Chương 3 từ kết quả trên. TV3 đọc lại và sửa |

### TV4: yếu tố ảnh hưởng (`src/fluwatch/risk_factors/`, `pipelines/04_risk_factors.py`)

| Commit | Thay đổi |
| --- | --- |
| `TV4 bo du lieu chen loi ...` | File mới `corrupt.py`, chạy bằng `python pipelines/04_risk_factors.py --corrupt`: 285 lỗi theo 7 tình huống thật (trạm nước thải ngừng 8 tuần, bang ngừng gửi ILINet, mất dòng do ghép bảng, nạp lại trùng một tuần, số sơ bộ NHSN báo thiếu...), ghi `data/sandbox/corrupted/` đúng hợp đồng của TV2. Chạy bộ chấm của TV2 và commit kết quả `reports/data_quality/injection_test.md` |
| `TV4 Shaman ...` | Bỏ việc loại mùa 2021-22 (không cần nữa khi khởi phát có xét nghiệm); chạy lại; cập nhật Chương 4 (mục Shaman, đoạn dữ liệu chèn lỗi, hạn chế). Các kết quả khác của TV4 **không đổi** (chạy lại chỉ lệch ở chữ số thứ 9) |

### TV5: mô hình cảnh báo (`src/fluwatch/alerting/`, `pipelines/05_alert_model.py`)

| Commit | Thay đổi |
| --- | --- |
| `TV5: nhan khoi phat ...` | `labels.py`: nhãn khởi phát lấy từ `season_milestones.parquet` của TV3 (không có file thì tự tính như cũ); bỏ các tuần `low_reporting` khỏi huấn luyện. `evaluate.py`: thêm **mô hình nền "hiện trạng"** (tỉ lệ nhập viện hiện tại / ngưỡng Cao) và DeLong so với nó. `backtest.py`: thêm mô hình nền này cho số sơ bộ. `figures.py`: vẽ thêm đường nền mới; sửa lỗi vẽ thanh sai số khi khoảng Wilson ra số âm rất nhỏ. Thêm `tests/conftest.py` (chạy `pytest` không cần `pip install -e .`) và 1 test cho nhãn khởi phát |
| `TV5 chay lai va cap nhat Chuong 5` | Chạy lại, cập nhật số và câu kết luận trong Chương 5; thêm đoạn **tầm dự báo tính từ lúc công bố số liệu**; ghi quyết định không dùng lịch sử nhập viện giả lập |

### Tài liệu chung

| Commit | Thay đổi |
| --- | --- |
| `Tu dien du lieu: ...` | `catalog.py` (TV2) chỉ sửa mô tả các cột của TV3: `onset_week`, `peak_week` là số tuần trong mùa, `severity` là nhập viện NHSN; sinh lại `docs/tu_dien_du_lieu.md`. Đã chạy thử `02_warehouse.py --steps business quality --strict` với file mới của TV3: kho ghép đủ 6 cột mốc mùa và `cluster_id`, **28/28 quy tắc đạt** |
| `ke_hoach: lui han 1 tuan ...` | Lịch mới (mục 1b), khóa số liệu 26/11, nộp 29/11; mục 10 ghi các điểm đã chốt |

## 3. Kết quả nổi bật để trình bày với thầy

| # | Phát hiện | Con số | Ở đâu |
| --- | --- | --- | --- |
| 1 | **Định nghĩa khởi phát quyết định kết quả.** Sau COVID, ILI tăng vì COVID và RSV; chỉ dùng ILI thì mùa 2021-22 có 22 bang "khởi phát" ở tuần 40. Thêm xét nghiệm ≥ 2% còn 2 bang | Shaman: p 0,041 → **0,0009**; tín hiệu độ ẩm trước khởi phát mạnh gấp 3 (−0,021 → −0,075 g/m³) | Chương 3, 4 |
| 2 | **Mùa 2026-27 đến sớm**, được xét nghiệm xác nhận | 27 bang khởi phát đến tuần 4 (trung vị các mùa trước: 4); sớm thứ 2 trong 10 mùa, sau 2022-23 | Chương 3 |
| 3 | **Cúm lan từ Nam lên Bắc**, không theo Đông – Tây | Spearman ρ = 0,28 với vĩ độ, p < 10⁻¹²; lặp lại ở 12/14 mùa; kinh độ p = 0,27 | Chương 3 |
| 4 | **Phân cụm không dùng tọa độ nhưng ra các cụm liền nhau về địa lý**: cụm Đông Nam (11 bang) đạt đỉnh sớm hơn 4 tuần | 88% bang cùng cụm với láng giềng, so với 66% ngẫu nhiên, p = 0,0002; đỉnh tuần 13 so với 17, p = 0,007 | Chương 3 |
| 5 | **ILI là tín hiệu báo sớm nhất, không phải nước thải** | ILI đạt nửa đỉnh trước nhập viện 2,5 tuần (87% bang-mùa); nước thải 0,3 tuần (53%) | Chương 3 |
| 6 | Kết quả 5 khớp với Chương 5: **thêm nước thải và cấp cứu không cải thiện mô hình cảnh báo** | DeLong p = 0,35 và 0,26 | Chương 5 |
| 7 | **Mô hình cảnh báo hơn được mô hình nền mạnh**, lợi ích tăng theo tầm dự báo, và vẫn đúng với số sơ bộ lúc công bố | AUC 0,993 so với 0,974 (1 tuần), 0,968 so với 0,912 (2 tuần), p < 10⁻¹⁰; 45/45 bang được cảnh báo trước hoặc đúng tuần lên mức Cao | Chương 5 |
| 8 | **Kết quả âm tính trung thực**: để báo khởi phát, tỉ số ILI / mức nền tốt hơn mô hình logistic | AUC 0,872 so với 0,820, p = 0,010 | Chương 5 |
| 9 | **Kiểm tra độc lập tìm ra lỗ hổng thật trong bộ quy tắc chất lượng**: bộ lỗi do TV4 dựng (khác người viết quy tắc) phát hiện bộ quy tắc không đối chiếu `num_ili` với `ili_pct` | Bắt 233/285 lỗi, 0 báo động giả; cả 52 lỗi bị lọt đều là ô `num_ili`; bộ tự sinh của TV2 không phát hiện được | Chương 2, 4 |
| 10 | **Sai số chuẩn thường quá lạc quan** với dữ liệu bang × tuần | Giả lập: KTC thường báo nhầm 18% khi không có hiệu ứng, KTC theo cụm bang 8% | Chương 4 |

## 4. Mỗi người cần làm gì tiếp

**Mọi người, sau khi PR được gộp:**

```
git fetch origin
git checkout main
git reset --hard origin/main
python scripts/download_data.py --samples
```

Nhánh cũ `tv3/eda`, `tv4/yeu-to-anh-huong`, `tv5/alert-model` không dùng nữa (nội dung đã nằm trong `main`). Việc mới thì tạo nhánh mới từ `main`. Lời nhắn commit **không** thêm dòng `Co-Authored-By`.

| Người | Việc | Hạn |
| --- | --- | --- |
| **TV2** | Thêm quy tắc đối chiếu `num_ili` thiếu khi `ili_pct` có (phát hiện số 9), chạy lại `--steps inject`, viết vào Chương 2.2–2.4 | 25/11 |
| **TV3** | Đọc bản nháp Chương 3, sửa văn phong, bổ sung nhận xét riêng; kiểm tra lại các hình `tv3_*.png`. Sau khóa số liệu, chạy lại `03_season_eda.py` và cập nhật số | 26/11 tối |
| **TV4** | Đọc lại mục Shaman và đoạn dữ liệu chèn lỗi trong Chương 4. Sau khóa số liệu, chạy `04_risk_factors.py --sim` và cập nhật số. What-if vaccine (RR 1,007, KTC 0,85–1,20) nhắc TV6 luôn vẽ kèm dải bất định | 26/11 tối |
| **TV5** | Đọc lại Chương 5 (các đoạn đã sửa: mô hình nền hiện trạng, khởi phát, tầm dự báo). Tùy chọn: hiệu chỉnh xác suất tầm 2 tuần (Hosmer-Lemeshow p = 0,01–0,04). Sau khóa số liệu, chạy lại `05_alert_model.py` | 26/11 tối |
| **TV6** | Dùng file mới (bảng dưới); thay stub bằng file thật | 25/11 |

**File và cột mới cho dashboard (TV6):**

| File | Dùng cho |
| --- | --- |
| `season_milestones.parquet`: thêm `onset_date`, `peak_date` (ngày, để hiển thị); `onset_week`, `peak_week` là số tuần trong mùa | Trang Mùa vụ |
| `season_phase.parquet`: nhãn `chua_bat_dau`, `dang_len`, `dinh`, `dang_giam` | Trang Hiện tại, tile map |
| `state_cluster.parquet`: `cluster_id` 1 = Đông Nam (11 bang), 2 = còn lại; FL trống | Trang Địa lý |
| `season_insights.json`: mùa hiện tại sớm thứ mấy, hướng lan, thành viên cụm | Thẻ số liệu, trang Phương pháp |
| `season_signal_lead.csv` | Hình "tín hiệu nào báo sớm nhất" |
| `alert_forecast.parquet`: **chỉ lấy `split == "live"`** cho tuần hiện tại; hiển thị `target_week` (tuần đích) thay vì chỉ ghi "1 tuần tới" | Trang Cảnh báo |
| `whatif.parquet`: vẽ cả `value_scenario_lo`, `value_scenario_hi`, nhãn "Giả lập" | Trang Yếu tố |

## 5. Cách kiểm tra lại

```
python pipelines/03_season_eda.py          # ~1 phút
python pipelines/04_risk_factors.py        # ~6 phút (thêm --sim: ~10 phút nữa; --corrupt: bộ chèn lỗi)
python pipelines/05_alert_model.py         # ~20 giây (backtest cần data/raw/, tải bằng download_data.py không có --samples)
python -m pytest -q tests                  # 6 test của TV5
python pipelines/02_warehouse.py --steps inject    # TV2 chấm bộ chèn lỗi của TV4 (~1,5 phút)
```

Trên GitHub Actions, workflow hằng tuần tự chạy `03`, `04`, `05` sau bước dựng kho (bước `analysis`), rồi đẩy file kết quả lên Hugging Face.
