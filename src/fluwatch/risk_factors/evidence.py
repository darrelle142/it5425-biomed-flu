"""Bang bang chung tang 2 (ke hoach v2 muc 8) dat canh ket qua tang 3 cua nhom.

Cot bang_chung, chieu_du_kien, do_tre_thu chep tu ke hoach v2 muc 8 (khong them so lieu ngoai tai lieu do).
Cot ket_qua_nhom sinh tu ket qua chay that (tuong quan tre, NB) de khong lech so voi file ket qua.
"""
import pandas as pd

EVIDENCE = [
    dict(yeu_to="Độ ẩm tuyệt đối", loai="Yếu tố nguy cơ", nguon="Shaman & Kohn 2009 (PNAS); Shaman et al. 2010",
         bang_chung="Độ ẩm tuyệt đối chi phối khả năng sống và lây truyền của virus cúm mạnh hơn độ ẩm tương đối; "
                    "khởi phát mùa cúm ở Mỹ gắn với độ ẩm tuyệt đối thấp bất thường những tuần trước (48 bang + DC, 30 mùa đông)",
         chieu_du_kien="Thấp bất thường → khởi phát sớm, tăng", do_tre_thu="1–3 tuần", key="ah"),
    dict(yeu_to="PM2.5", loai="Yếu tố nguy cơ", nguon="Croft et al. 2019",
         bang_chung="498.118 người lớn ở New York; nhập viện và cấp cứu vì cúm tăng theo PM2.5 trong 1–7 ngày trước",
         chieu_du_kien="Tăng → tăng", do_tre_thu="0–1 tuần", key="pm25"),
    dict(yeu_to="Vaccine cúm", loai="Yếu tố bảo vệ", nguon="Nghiên cứu cấp bang (medRxiv 2025)",
         bang_chung="Nhập viện vì cúm tương quan có ý nghĩa với tỷ lệ tiêm nhóm 18–49 tuổi (p < 0,0107), "
                    "không có ý nghĩa với tỷ lệ chung",
         chieu_du_kien="Tăng → giảm", do_tre_thu="Theo mùa", key="vax"),
    dict(yeu_to="Kỳ nghỉ lễ, nghỉ học", loai="Yếu tố bảo vệ", nguon="Úc 2019",
         bang_chung="Kỳ nghỉ học gắn với mức giảm 41–65% số ca cúm ở 3 bang và 1 vùng lãnh thổ",
         chieu_du_kien="Nghỉ học → giảm trong kỳ nghỉ", do_tre_thu="0–1 tuần", key="holiday"),
    dict(yeu_to="Nước thải cúm A", loai="Chỉ báo sớm", nguon="Nghiên cứu 50 bang 2021–2025; nghiên cứu California",
         bang_chung="Nước thải dự báo nhập viện cúm trước 2 tuần, r = 0,93; nghiên cứu California không thấy nước thải "
                    "luôn đi trước (cúm A từ −16 đến 22 ngày)",
         chieu_du_kien="Đi trước, cùng chiều (chưa thống nhất)", do_tre_thu="0–2 tuần", key=None),
    dict(yeu_to="Khám cấp cứu", loai="Chỉ báo sớm", nguon="Kế hoạch v2 mục 8",
         bang_chung="Dữ liệu cấp cứu thời gian thực đạt đỉnh trước ILI và tử vong do cúm",
         chieu_du_kien="Đi trước, cùng chiều", do_tre_thu="0–1 tuần", key=None),
]
LC_KEY = {"ah": "ah_anomaly", "pm25": "pm25_epa_anomaly"}


def _nb_text(rr, key):
    g = rr[rr["factor"] == key]
    if key in ("vax", "holiday"):
        g = g[g["model"] == "nb_lag0"]
    sig = g[(g["ci_low"] > 1) | (g["ci_high"] < 1)]
    if sig.empty:
        r = g.iloc[0]
        return f"NB: không rõ (RR {r.rr:.3f}, KTC {r.ci_low:.2f}–{r.ci_high:.2f})"
    lags = sorted(sig["lag_weeks"].unique())
    lag_txt = f", trễ {lags[0]}–{lags[-1]} tuần" if key in ("ah", "pm25") else ""
    rr_txt = f"{sig.rr.min():.3f}" if len(sig) == 1 else f"{sig.rr.min():.3f}–{sig.rr.max():.3f}"
    note = ""
    if key == "holiday" and sig.rr.min() > 1:
        note = ("; ngược chiều bài báo: tuần lễ Tạ ơn, Giáng sinh, Năm mới có ít lượt khám bệnh khác nên ILI% tăng "
                "một phần do mẫu số, và biến này không phải kỳ nghỉ học")
    return f"NB: RR {rr_txt}{lag_txt} (KTC cụm không chứa 1){note}"


def _lc_text(lc, key):
    if key not in LC_KEY:
        return ""
    g = lc[lc["factor"] == LC_KEY[key]]
    neg, pos = g[g["ci_high"] < 0], g[g["ci_low"] > 0]
    if len(neg):
        return f"; tương quan trễ: âm ở trễ {int(neg.lag_weeks.min())}–{int(neg.lag_weeks.max())} tuần (ρ đến {neg.rho_median.min():+.2f})"
    if len(pos):
        return f"; tương quan trễ: dương ở trễ {', '.join(str(int(x)) for x in pos.lag_weeks)}"
    return "; tương quan trễ: không rõ"


def table(rr, lc):
    rows = []
    for e in EVIDENCE:
        k = e["key"]
        res = (_nb_text(rr, k) + _lc_text(lc, k)) if k else "Không thuộc RQ4 (TV5 đánh giá trong mô hình cảnh báo)"
        rows.append({**{c: v for c, v in e.items() if c != "key"}, "ket_qua_nhom": res})
    return pd.DataFrame(rows)
