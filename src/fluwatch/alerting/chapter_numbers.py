"""In mọi con số Chương 5 dùng, theo thứ tự các đoạn trong chương, định dạng kiểu Việt Nam.

Chạy cuối pipelines/05_alert_model.py -> data/business/tv5_chapter_numbers.md.
Sau khi chạy lại trên bản khóa số liệu, mở file này và chép số vào reports/chapters/05_canh_bao.md.
"""
from __future__ import annotations

import pandas as pd


def _n(x, d=3):
    return f"{x:.{d}f}".replace(".", ",")


def _p(p):
    if p is None:
        return "–"
    if p < 1e-4:
        e = int(f"{p:.0e}".split("e")[1]) + 1  # p < 10^e
        return f"p < 10^{e}"
    return "p = " + _n(p, 3 if p >= 0.001 else 4)


def _auc(m):
    return f"{_n(m['auc'])} [{_n(m['auc_ci_low'])}–{_n(m['auc_ci_high'])}]"


def _delong(r, a, b):
    for d in r["delong"]:
        if d["a"] == a and d["b"] == b:
            return f"{d['diff']:+.4f}".replace(".", ",") + f" ({_p(d['p'])})"
    return "–"


def build(ev: dict, df: pd.DataFrame, lead: pd.DataFrame | None) -> str:
    T = ev["targets"]
    e1, e2, on = T["y_exceed_1w"], T["y_exceed_2w"], T["y_onset_next2w"]
    L = [f"# Số liệu cho Chương 5 (mùa test {ev['test_season']})", "",
         "Tự sinh bởi `python pipelines/05_alert_model.py`. Không sửa tay.", ""]

    L += ["## Nhãn và dữ liệu huấn luyện", "", "| Mùa | Dòng có nhãn vượt ngưỡng | Dòng mức cao 1 tuần sau |", "| --- | --- | --- |"]
    t = df[df["train_ok"] & df["y_exceed_1w"].notna() & (df["season"] >= "2022-23")]
    for s, g in t.groupby("season"):
        L.append(f"| {s} | {len(g)} | {int(g['y_exceed_1w'].sum())} |")
    L += [""]

    L += ["## Bảng đánh giá", "", f"Tập test chung: {e1['n']} dòng, {e1['n_pos']} dương (tỉ lệ {_n(e1['base_rate'] * 100, 1)}%).", "",
          "| Mô hình | AUC 1 tuần | AUC 2 tuần | Brier 1 tuần | Brier 2 tuần | AP 1 tuần | AP 2 tuần |", "| --- | --- | --- | --- | --- | --- | --- |"]
    for m in ["persistence", "hien_trang", "nhsn", "base", "full"]:
        a, b = e1["models"][m], e2["models"][m]
        br = lambda x: _n(x["brier"]) if "brier" in x else "–"  # noqa: E731
        L.append(f"| {m} | {_auc(a)} | {_auc(b)} | {br(a)} | {br(b)} | {_n(a['average_precision'])} | {_n(b['average_precision'])} |")
    L += [""]

    L += ["## DeLong (chênh AUC, p)", "", "| So sánh | 1 tuần | 2 tuần |", "| --- | --- | --- |"]
    for a, b in [("base", "persistence"), ("base", "hien_trang"), ("full", "hien_trang"), ("base", "nhsn"), ("full", "base")]:
        L.append(f"| {a} vs {b} | {_delong(e1, a, b)} | {_delong(e2, a, b)} |")
    L += [""]

    L += ["## Chưa ở mức cao (cảnh báo sớm)", ""]
    for h, r in (("1 tuần", e1), ("2 tuần", e2)):
        ew = r.get("early_warning_not_yet_high")
        if ew:
            L.append(f"- {h}: {ew['n_pos']} dương; base AUC {_auc(ew['models']['base'])}")
    L += [""]

    L += ["## Hiệu chỉnh và ngưỡng", ""]
    for h, r in (("1 tuần", e1), ("2 tuần", e2)):
        f, b = r["models"]["full"], r["models"]["base"]
        a = b["at_train_threshold"]
        L.append(f"- {h}: Hosmer-Lemeshow full {_p(f['hosmer_lemeshow']['p_df_g_minus_2'])}, base {_p(b['hosmer_lemeshow']['p_df_g_minus_2'])}; "
                 f"ngưỡng Youden (base) {_n(a['threshold'])}: độ nhạy {_n(a['sensitivity'], 2)}, đặc hiệu {_n(a['specificity'], 2)}, "
                 f"giá trị dự đoán dương {_n(a['ppv'], 2)}")
    L += [""]

    L += ["## Khởi phát", "", f"- {on['n']} dòng test, {on['n_pos']} dương",
          f"- full AUC {_auc(on['models']['full'])}; base AUC {_n(on['models']['base']['auc'])}; nền ILI/mức nền AUC {_auc(on['models']['hien_trang'])}",
          f"- DeLong full vs nền: {_delong(on, 'full', 'hien_trang')}; Hosmer-Lemeshow full {_p(on['models']['full']['hosmer_lemeshow']['p_df_g_minus_2'])}", ""]

    bt = ev.get("backtest", {})
    if "targets" in bt:
        L += ["## Backtest như lúc công bố", "", "| Mô hình | Tầm | AUC số sơ bộ [KTC] | AUC số đã sửa | Nền 0/1 | Nền hiện trạng | DeLong vs hiện trạng |",
              "| --- | --- | --- | --- | --- | --- | --- |"]
        for h in (1, 2):
            for v, m in bt["targets"][f"y_exceed_{h}w"].items():
                ci = m["auc_asof_ci"]
                dl = m.get("delong_asof_vs_hien_trang", {}).get("p")
                L.append(f"| {v} | {h} tuần | {_n(m['auc_asof'])} [{_n(ci[0])}–{_n(ci[1])}] | {_n(m['auc_retro'])} | "
                         f"{_n(m['auc_persistence_asof'])} | {_n(m['auc_hien_trang_asof']) if 'auc_hien_trang_asof' in m else '–'} | {_p(dl)} |")
        at = bt["alert_timing"]
        L += ["", f"- {at['states_alerted_by_first_high']}/{at['states_reached_high']} bang lên mức cao được cảnh báo trước hoặc đúng tuần; "
                  f"trung vị báo trước {_n(at['lead_weeks_median'], 0)} tuần; {at['states_alerted_but_never_high']} bang báo giả cả mùa"]
        if lead is not None and len(lead):
            vc = lead.loc[lead["first_high"].notna(), "lead_weeks"].dropna().round().astype(int).value_counts().sort_index()
            L.append("- Số bang theo số tuần báo trước: " + ", ".join(f"{k} tuần: {v}" for k, v in vc.items()))
    return "\n".join(L) + "\n"
