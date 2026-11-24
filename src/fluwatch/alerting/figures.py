"""Hình cho chương 5 (TV5): PNG 300 dpi, tiêu đề là câu kết luận, bảng màu Okabe-Ito.

Màu theo thực thể (không đổi giữa các hình): nền = xám, nhsn = cam, base = xanh dương, full = xanh lục.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import BoundaryNorm, ListedColormap  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

from fluwatch.alerting.models import EXCEED_FEATS, TEST_SEASON  # noqa: E402

OI = {"grey": "#8C8C8C", "orange": "#E69F00", "blue": "#0072B2", "green": "#009E73", "verm": "#D55E00", "sky": "#56B4E9"}
MODEL_COLOR = {"persistence": OI["grey"], "hien_trang": "#000000", "nhsn": OI["orange"], "base": OI["blue"], "full": OI["green"]}
MODEL_LABEL = {"persistence": "Nền: đã ở mức Cao (0/1)", "hien_trang": "Nền: nhập viện hiện tại / ngưỡng", "nhsn": "Chỉ nhập viện", "base": "Nhập viện + ILI", "full": "+ cấp cứu, nước thải"}
INK, MUTED, GRID = "#222222", "#666666", "#E6E6E6"


def _style():
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": MUTED, "axes.labelcolor": INK,
        "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True,
        "figure.dpi": 100, "savefig.dpi": 300, "savefig.bbox": "tight", "savefig.facecolor": "white",
    })


def _title(fig, text, sub=None):
    fig.text(0.0, 1.02, text, ha="left", va="bottom", fontsize=12.5, fontweight="bold", color=INK)
    if sub:
        fig.text(0.0, 0.985, sub, ha="left", va="bottom", fontsize=8.5, color=MUTED)


def _vn(x, d=3):
    return f"{x:.{d}f}".replace(".", ",")


def fig_roc(ev, roc, out):
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 4.4), sharey=True)
    for ax, (lab, name) in zip(axes, [("y_exceed_1w", "1 tuần tới"), ("y_exceed_2w", "2 tuần tới")]):
        t = ev["targets"][lab]
        ax.plot([0, 1], [0, 1], color=GRID, lw=1, ls=(0, (4, 3)), zorder=1)
        for m in ["persistence", "hien_trang", "nhsn", "base", "full"]:
            r = roc[(roc["target"] == lab) & (roc["model"] == m)]
            a = t["models"][m]
            ls = (0, (5, 2)) if m == "full" else "-"
            ls = (0, (1, 1.5)) if m == "hien_trang" else ls
            ax.plot(r["fpr"], r["tpr"], color=MODEL_COLOR[m], lw=1.8 if m not in ("persistence", "hien_trang") else 1.3, ls=ls,
                    label=f"{MODEL_LABEL[m]}: AUC {_vn(a['auc'])} [{_vn(a['auc_ci_low'])}–{_vn(a['auc_ci_high'])}]")
        b = t["models"]["base"]["at_train_threshold"]
        ax.scatter([1 - b["specificity"]], [b["sensitivity"]], s=46, color=OI["verm"], zorder=5, edgecolor="white", linewidth=1.2)
        ax.annotate(f"ngưỡng Youden (mô hình ILI)\nnhạy {_vn(b['sensitivity'], 2)}, đặc hiệu {_vn(b['specificity'], 2)}",
                    (1 - b["specificity"], b["sensitivity"]), xytext=(0.36, 0.34), fontsize=8, color=OI["verm"],
                    arrowprops=dict(arrowstyle="-", color=OI["verm"], lw=0.8))
        ax.set_title(f"Dự báo {name} (mùa {ev['test_season']}, {t['n_pos']} ca dương / {t['n']} dòng)", fontsize=9.5, loc="left", color=INK)
        ax.set_xlabel("Tỉ lệ báo động giả (1 − độ đặc hiệu)")
        ax.set_xlim(0, 1); ax.set_ylim(0, 1.01); ax.set_aspect("equal", adjustable="box")
        ax.legend(loc="lower right", fontsize=7.4, frameon=False, handlelength=2.2)
    axes[0].set_ylabel("Tỉ lệ phát hiện đúng (độ nhạy)")
    m1, m2 = ev["targets"]["y_exceed_1w"]["models"], ev["targets"]["y_exceed_2w"]["models"]
    _title(fig, f"Logistic hơn việc chỉ nhìn số nhập viện hiện tại: AUC {_vn(m1['base']['auc'], 3)} so với "
                f"{_vn(m1['hien_trang']['auc'], 3)} (1 tuần), {_vn(m2['base']['auc'], 3)} so với {_vn(m2['hien_trang']['auc'], 3)} (2 tuần)",
           "Thêm cấp cứu và nước thải không cải thiện thêm: đường xanh lục chồng lên đường xanh dương")
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    fig.savefig(out); plt.close(fig)


def _wilson(k, n, z=1.96):
    if n == 0:
        return np.nan, np.nan
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(c - h, 0.0), min(c + h, 1.0)  # lam tron so hoc co the ra -1e-17 khi k = 0


def fig_calibration(df, fitted, ev, out):
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 4.6))
    edges = np.array([0, 0.005, 0.02, 0.05, 0.15, 0.4, 0.7, 0.9, 1.0001])
    for ax, h in zip(axes, (1, 2)):
        lab = f"y_exceed_{h}w"
        f = fitted[(lab, "full")]
        te = df[df["train_ok"] & (df["season"] == TEST_SEASON) & df[lab].notna() & df[EXCEED_FEATS["full"]].notna().all(axis=1)]
        p, y = f["model"].predict_proba(te[f["feats"]])[:, 1], te[lab].astype(int).to_numpy()
        g = np.digitize(p, edges) - 1
        rows = []
        for k in range(len(edges) - 1):
            m = g == k
            if m.sum() >= 5:
                lo, hi = _wilson(y[m].sum(), m.sum())
                rows.append((p[m].mean(), y[m].mean(), lo, hi, int(m.sum())))
        r = np.array(rows)
        sq = lambda v: np.sqrt(np.clip(v, 0, None))  # noqa: E731
        ax.plot([0, 1], [0, 1], color=MUTED, lw=1, ls=(0, (4, 3)))
        ax.errorbar(r[:, 0], r[:, 1], yerr=np.clip([r[:, 1] - r[:, 2], r[:, 3] - r[:, 1]], 0, None), fmt="none", ecolor=OI["green"], elinewidth=1.1, capsize=2.5)
        ax.plot(r[:, 0], r[:, 1], color=OI["green"], lw=1.6)
        ax.scatter(r[:, 0], r[:, 1], s=np.clip(r[:, 4] / 14, 14, 150), color=OI["green"], edgecolor="white", linewidth=1.0, zorder=4)
        ax.set_xscale("function", functions=(sq, np.square)); ax.set_yscale("function", functions=(sq, np.square))
        ticks = [0, 0.01, 0.05, 0.1, 0.25, 0.5, 1]
        for axis in (ax.xaxis, ax.yaxis):
            axis.set_ticks(ticks); axis.set_ticklabels([str(t).replace(".", ",") for t in ticks])
        ax.set_xlim(0, 1); ax.set_ylim(0, 1.0)
        hl = ev["targets"][lab]["models"]["full"]["hosmer_lemeshow"]
        ax.set_title(f"Dự báo {h} tuần tới: Brier {_vn(ev['targets'][lab]['models']['full']['brier'], 4)}, Hosmer-Lemeshow p = {_vn(hl['p_df_g_minus_2'], 3)}",
                     fontsize=9.2, loc="left", color=INK)
        ax.set_xlabel("Xác suất mô hình dự báo (trục căn bậc hai)")
        ax.set_aspect("equal", adjustable="box")
        ax.annotate("điểm càng lớn = càng nhiều dòng", (0.02, 0.9), xycoords="axes fraction", fontsize=7.5, color=MUTED)
    axes[0].set_ylabel("Tần suất thực tế, khoảng tin cậy 95% (trục căn bậc hai)")
    _title(fig, "Xác suất dự báo 1 tuần khớp thực tế; dự báo 2 tuần lệch nhẹ nhưng vẫn xếp hạng tốt",
           "Mô hình đầy đủ, mùa test 2025-26. Đường chéo nét đứt = hiệu chỉnh hoàn hảo")
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    fig.savefig(out); plt.close(fig)


def fig_backtest(ev, bt, lead, out):
    at = ev["backtest"]["alert_timing"]
    lead = lead.copy()
    for c in ("first_high", "first_alert"):
        lead[c] = pd.to_datetime(lead[c])
    order = lead.sort_values(["first_high", "state"], na_position="last")["state"].tolist()
    bt = bt[bt["week"] <= pd.Timestamp("2026-06-30")]  # sau tháng 6 chỉ còn mức thấp, bỏ cho gọn
    weeks = sorted(bt["week"].unique())
    grid = bt.pivot(index="state", columns="week", values="cdc_level").reindex(index=order, columns=weeks)
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(10.6, 8.2), gridspec_kw={"width_ratios": [3.2, 1], "wspace": 0.16,
                                                                          "top": 0.91, "bottom": 0.08, "left": 0.05, "right": 0.99})
    cmap = ListedColormap(["#F2F2F2", "#CFE3F2", "#8FBBE0", "#3F8CC7", "#0B4F8A"])
    ax.pcolormesh(np.arange(len(weeks) + 1), np.arange(len(order) + 1), np.ma.masked_invalid(grid.to_numpy(float)),
                  cmap=cmap, norm=BoundaryNorm(np.arange(-0.5, 5), 5), edgecolor="white", linewidth=0.3)
    xi = {w: i for i, w in enumerate(weeks)}
    for j, s in enumerate(order):
        r = lead.set_index("state").loc[s]
        if pd.notna(r["first_alert"]):
            ax.scatter([xi[r["first_alert"]] + 0.5], [j + 0.5], marker="v", s=24, color=OI["verm"], edgecolor="white", linewidth=0.6, zorder=5)
    ax.set_ylim(len(order), 0); ax.set_xlim(0, len(weeks))
    ax.set_yticks(np.arange(len(order)) + 0.5); ax.set_yticklabels([s.upper() for s in order], fontsize=6.4)
    tk = [i for i, w in enumerate(weeks) if pd.Timestamp(w).day <= 7 and pd.Timestamp(w).month % 2 == 1]
    ax.set_xticks([i + 0.5 for i in tk]); ax.set_xticklabels([pd.Timestamp(weeks[i]).strftime("%m/%Y") for i in tk], fontsize=8)
    ax.grid(False); [s.set_visible(False) for s in ax.spines.values()]
    ax.tick_params(length=0)
    ax.set_title("Mức CDC thực tế theo tuần (bang xếp theo tuần lên mức Cao)", fontsize=9.2, loc="left", color=INK)
    handles = [Patch(color=c, label=l) for c, l in zip(cmap.colors, ["0 rất thấp", "1 thấp", "2 trung bình", "3 cao", "4 rất cao"])]
    handles.append(Patch(facecolor="white", edgecolor=MUTED, linewidth=0.6, label="chưa có số liệu"))
    handles.append(Line2D([], [], marker="v", ls="", color=OI["verm"], markeredgecolor="white", label="tuần cảnh báo đầu tiên của mô hình"))
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.035), ncol=4, fontsize=7.6, frameon=False, columnspacing=1.2)

    reached = lead[lead["first_high"].notna() & lead["first_alert"].notna()]
    vc = reached["lead_weeks"].round().astype(int).value_counts().sort_index()
    xs = np.arange(0, int(vc.index.max()) + 1)
    ys = [int(vc.get(x, 0)) for x in xs]
    bx.bar(xs, ys, color=OI["blue"], width=0.62)
    for x, y in zip(xs, ys):
        if y:
            bx.text(x, y + 0.5, str(y), ha="center", fontsize=8.5, color=INK)
    bx.set_xticks(xs); bx.set_xlabel("Số tuần báo trước")
    bx.set_ylabel("Số bang"); bx.set_title("Báo trước bao lâu?", fontsize=9.2, loc="left", color=INK)
    bx.grid(axis="x", visible=False)
    n_reach, n_by = at["states_reached_high"], at["states_alerted_by_first_high"]
    _title(fig, f"Cảnh báo đến trước hoặc đúng tuần lên mức Cao ở {n_by}/{n_reach} bang, trung vị sớm {at['lead_weeks_median']:.0f} tuần",
           f"Backtest {ev['test_season']} với số liệu đúng như lúc công bố, hiển thị đến 06/2026; "
           f"{at['states_alerted_but_never_high']} bang có báo động nhưng không lên mức Cao (xếp cuối bảng)")
    fig.savefig(out); plt.close(fig)


def make_figures(df, fitted, ev, roc, bt, lead, outdir: Path):
    outdir.mkdir(parents=True, exist_ok=True)
    _style()
    fig_roc(ev, roc, outdir / "tv5_roc_compare.png")
    fig_calibration(df, fitted, ev, outdir / "tv5_calibration_curve.png")
    if len(bt):
        fig_backtest(ev, bt, lead, outdir / "tv5_backtest_timeline.png")
