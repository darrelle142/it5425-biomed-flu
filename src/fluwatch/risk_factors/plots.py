"""Hinh cua TV4. Quy tac ve (ke hoach v2 muc 9.3): tieu de la cau ket luan sinh tu ket qua; ty so dung truc log;
ghi ro khoang tin cay 95%; bang mau Okabe-Ito kem chu (khong chi dung mau); mot truc."""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .lag_corr import FACTORS
from .nb_model import LABELS

OKABE = {"blue": "#0072B2", "orange": "#E69F00", "vermillion": "#D55E00", "grey": "#7F7F7F"}
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.titleweight": "bold", "savefig.dpi": 300, "savefig.bbox": "tight"})


def _ci_excludes(lo, hi, ref):
    return lo > ref or hi < ref


def lag_correlation(summary, path):
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.8), sharey=True)
    colors = [OKABE["blue"], OKABE["orange"]]
    notes = {}
    for ax, (fac, label), col in zip(axes, FACTORS.items(), colors):
        s = summary[summary["factor"] == fac].sort_values("lag_weeks")
        ax.axhline(0, color=OKABE["grey"], lw=1)
        ax.errorbar(s["lag_weeks"], s["rho_median"], yerr=[s["rho_median"] - s["ci_low"], s["ci_high"] - s["rho_median"]],
                    fmt="o", color=col, ms=7, lw=2, capsize=3)
        for r in s.itertuples():
            ax.annotate(f"{r.rho_median:+.2f}", (r.lag_weeks, r.ci_high), textcoords="offset points", xytext=(0, 4),
                        ha="center", fontsize=8)
        ax.set_title(label, fontsize=10, fontweight="normal")
        ax.set_xlabel("Độ trễ (tuần, yếu tố đi trước ILI)")
        ax.set_xticks(range(0, 5))
        neg = s[s["ci_high"] < 0]
        pos = s[s["ci_low"] > 0]
        notes[fac] = (neg, pos)
    axes[0].set_ylabel("Tương quan Spearman (trung vị các bang)")
    name = {"ah_anomaly": "độ ẩm", "pm25_epa_anomaly": "PM2.5"}
    parts = []
    for fac, (neg, pos) in notes.items():
        if len(neg):
            lags = f"{int(neg.lag_weeks.min())}–{int(neg.lag_weeks.max())}" if len(neg) > 1 else f"{int(neg.lag_weeks.iloc[0])}"
            parts.append(f"{name[fac]} thấp bất thường đi trước ILI cao {lags} tuần "
                         f"(ρ từ {neg.rho_median.max():+.2f} đến {neg.rho_median.min():+.2f})")
        elif not len(pos):
            parts.append(f"{name[fac]} không có tương quan rõ")
    title = ("; ".join(parts) + ". Tương quan rất yếu") if parts else \
        "Không yếu tố nào có tương quan rõ với ILI ở độ trễ 0–4 tuần"
    title = title[0].upper() + title[1:]
    fig.suptitle(title, fontsize=11, fontweight="bold", x=0.01, ha="left")
    fig.text(0.01, -0.04, "Thanh sai số: KTC 95% bootstrap theo bang. Cả hai biến đã trừ trung bình cùng tuần qua các năm "
             "và trung bình bang × mùa. Tuần mùa 1–33, mùa 2010-11 đến 2025-26 trừ 2020-21.", fontsize=8,
             color=OKABE["grey"])
    fig.savefig(path)
    plt.close(fig)


def forest(rr, path, lag_main=None):
    order = ["ah", "pm25", "vax", "holiday"]
    rows = []
    for fac in order:
        g = rr[rr["factor"] == fac]
        if fac in ("vax", "holiday"):
            g = g[g["model"] == (f"nb_lag{lag_main}" if lag_main is not None else g["model"].iloc[0])]
        for r in g.sort_values("lag_weeks").itertuples():
            lab = LABELS[fac] + (f", trễ {r.lag_weeks} tuần" if fac in ("ah", "pm25") else "")
            rows.append((lab, r.rr, r.ci_low, r.ci_high, fac))
    fig, ax = plt.subplots(figsize=(8, 0.42 * len(rows) + 1.6))
    y = np.arange(len(rows))[::-1]
    col = {"ah": OKABE["blue"], "pm25": OKABE["orange"], "vax": OKABE["vermillion"], "holiday": OKABE["grey"]}
    for yi, (lab, est, lo, hi, fac) in zip(y, rows):
        ax.plot([lo, hi], [yi, yi], color=col[fac], lw=2)
        ax.plot(est, yi, "o", color=col[fac], ms=7)
        ax.text(hi * 1.004, yi, f" {est:.3f} ({lo:.3f}–{hi:.3f})", va="center", fontsize=8)
    ax.axvline(1, color="black", lw=1)
    ax.set_xscale("log")
    ticks = [0.85, 0.9, 0.95, 1.0, 1.05, 1.1, 1.2]
    ax.set_xticks(ticks, [f"{t:g}" for t in ticks])
    ax.minorticks_off()
    ax.set_yticks(y, [r[0] for r in rows], fontsize=8)
    ax.set_xlabel("Rate ratio của ILI (trục log; 1 = không có liên hệ)")
    short = {"ah": "độ ẩm cao hơn", "pm25": "PM2.5 cao hơn", "vax": "độ phủ vaccine cao hơn", "holiday": "tuần nghỉ lễ"}
    sig = {}
    for r in rows:
        if _ci_excludes(r[2], r[3], 1):
            sig.setdefault(r[4], "ILI thấp hơn" if r[1] < 1 else "ILI cao hơn")
    if sig:
        title = "Sau khi kiểm soát bang, mùa, tuần mùa: " + "; ".join(f"{short[k]} → {v}" for k, v in sig.items()) + \
            " (KTC 95% không chứa 1)"
    else:
        title = "Không yếu tố nào có liên hệ rõ với ILI sau khi kiểm soát bang, mùa và tuần mùa"
    ax.set_title(title, fontsize=10, loc="left")
    fig.text(0.01, -0.02, "Negative Binomial, offset log(số bệnh nhân), hiệu ứng cố định bang, mùa, tuần mùa; mỗi độ trễ "
             "một mô hình, cùng tập dòng. Vaccine, nghỉ lễ lấy từ mô hình trễ 0. Thanh: KTC 95% từ sai số chuẩn cụm theo bang.\n"
             "Tuần nghỉ lễ: ILI% tăng một phần do ít lượt khám bệnh khác (mẫu số giảm), không hẳn là lây nhiều hơn.",
             fontsize=8, color=OKABE["grey"])
    fig.savefig(path)
    plt.close(fig)


def sim_check(summ, reps, real_pct, sim_pct, ac_real, ac_sim, path):
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.9))
    q = np.linspace(0.01, 0.99, 99)
    ax = axes[0]
    ax.plot(np.quantile(real_pct, q), np.quantile(sim_pct, q), "o", ms=3, color=OKABE["blue"])
    m = np.quantile(real_pct, 0.99)
    ax.plot([0, m], [0, m], color=OKABE["grey"], lw=1)
    ax.set_xlabel("ILI% thật (phân vị)")
    ax.set_ylabel("ILI% giả lập (phân vị)")
    ax.set_title(f"Kiểm chứng bộ giả lập: phân phối khớp;\ntự tương quan trễ 1 thật {ac_real:.2f}, giả lập {ac_sim:.2f}",
                 fontsize=9, fontweight="normal", loc="left")

    ax = axes[1]
    cols = {"cai_hieu_ung": OKABE["blue"], "doi_chung": OKABE["orange"]}
    names = {"cai_hieu_ung": "Cài RR 0,975", "doi_chung": "Đối chứng RR 1"}
    r = reps[reps["ci_type"] == "cum_theo_bang"]
    for sc, g in r.groupby("scenario"):
        ax.hist(g["rr_hat"], bins=25, color=cols[sc], alpha=0.6, label=f"{names[sc]} (ước lượng)")
        ax.axvline(g["rr_true"].iloc[0], color=cols[sc], lw=2, ls="--")
    ax.set_xlabel("RR độ ẩm ước lượng lại (đường nét đứt: giá trị cài)")
    ax.set_ylabel("Số lần mô phỏng")
    ax.legend(frameon=False, fontsize=8)
    ax.set_title("Ước lượng quanh đúng giá trị cài", fontsize=9, fontweight="normal", loc="left")

    ax = axes[2]
    s = summ.copy()
    labels, vals, colors = [], [], []
    for sc in ("cai_hieu_ung", "doi_chung"):
        for ct, nm in (("cum_theo_bang", "KTC cụm"), ("thuong", "KTC thường")):
            row = s[(s["scenario"] == sc) & (s["ci_type"] == ct)].iloc[0]
            labels.append(f"{names[sc]}\n{nm}")
            vals.append(row["coverage"] * 100)
            colors.append(cols[sc] if ct == "cum_theo_bang" else OKABE["grey"])
    x = np.arange(len(vals))
    ax.bar(x, vals, color=colors, width=0.6)
    for xi, v in zip(x, vals):
        ax.text(xi, v + 1, f"{v:.0f}%", ha="center", fontsize=8)
    ax.axhline(95, color="black", lw=1, ls=":")
    ax.set_ylim(0, 105)
    ax.set_xticks(x, labels, fontsize=7)
    ax.set_ylabel("% lần KTC 95% chứa giá trị cài")
    ax.set_title("Độ phủ khoảng tin cậy (mục tiêu 95%)", fontsize=9, fontweight="normal", loc="left")

    pc = s[(s.scenario == "cai_hieu_ung") & (s.ci_type == "cum_theo_bang")].iloc[0]
    nc_c = s[(s.scenario == "doi_chung") & (s.ci_type == "cum_theo_bang")].iloc[0]
    nc_t = s[(s.scenario == "doi_chung") & (s.ci_type == "thuong")].iloc[0]
    fig.suptitle(f"Phương pháp tìm lại hiệu ứng cài sẵn ở {pc.share_significant:.0%} số lần; khi không có hiệu ứng, "
                 f"KTC cụm báo nhầm {nc_c.share_significant:.0%}, KTC thường {nc_t.share_significant:.0%}",
                 fontsize=11, fontweight="bold", x=0.01, ha="left", y=1.04)
    fig.text(0.01, -0.06, "DỮ LIỆU GIẢ LẬP, chỉ để kiểm tra phương pháp, không dùng làm bằng chứng. Biến giải thích, hiệu ứng "
             "cố định và số bệnh nhân thật; số ca ILI sinh từ Poisson-lognormal có tự tương quan AR(1) theo bang-mùa.",
             fontsize=8, color=OKABE["grey"])
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def shaman(summary, t_null, path):
    fig, ax = plt.subplots(figsize=(8, 3.6))
    ax.hist(t_null, bins=60, color=OKABE["grey"], alpha=0.7, label="Khởi phát ngẫu nhiên (giả thuyết 0)")
    ax.axvline(summary["t_obs"], color=OKABE["blue"], lw=2, label="Khởi phát thật")
    ax.axvline(0, color="black", lw=0.8, ls=":")
    ax.set_xlabel("Độ chênh độ ẩm tuyệt đối trung bình 2–4 tuần trước khởi phát (g/m³)")
    ax.set_ylabel("Số lần hoán vị")
    ax.legend(frameon=False, fontsize=8)
    p = summary["p_one_sided"]
    verdict = "thấp hơn có ý nghĩa" if p < 0.05 else "không thấp hơn có ý nghĩa"
    ax.set_title(f"Trước khởi phát, độ ẩm {verdict} so với ngẫu nhiên "
                 f"({summary['t_obs']:+.2f} g/m³, p = {p:.4f})", fontsize=10, loc="left")
    fig.text(0.01, -0.06, f"{summary['n_pairs']} bang-mùa, {summary['n_states']} bang lục địa + DC; "
             f"{len(t_null)} hoán vị. BẢN TẠM: bỏ mùa {summary['skipped_seasons']}, mốc khởi phát chưa áp dụng định nghĩa mới.",
             fontsize=8, color=OKABE["grey"])
    fig.savefig(path)
    plt.close(fig)
