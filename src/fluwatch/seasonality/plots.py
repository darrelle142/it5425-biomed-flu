import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from pathlib import Path
from scipy.stats import gaussian_kde
from scipy.cluster.hierarchy import dendrogram
from statsmodels.graphics.tsaplots import plot_acf


EXCLUDE_SEASON = ['2009-10', '2020-21']

def setup_style():
    plt.rcParams.update({
        'figure.dpi': 300,
        'savefig.dpi': 300,
        'font.size': 10,
        'axes.titlesize': 12,
        'axes.titleweight': 'bold',
        'axes.spines.top': False,
        'axes.spines.right': False
    })

def plot_season_overlay(df: pd.DataFrame, output_dir: Path, current_season: str = '2026-27', recent_season: str = '2025-26'):
    setup_style()

    fig, ax = plt.subplots(figsize=(10, 5))
    agg_dict = {
        'ili_pct': ('ili_pct', 'mean'),
        'is_preliminary': ('is_preliminary', 'any')
    }
    nat = df[~df['season'].isin(EXCLUDE_SEASON)].groupby(['season', 'season_week'], as_index=False).agg(**agg_dict).sort_values(['season', 'season_week'])
    for season, grp in nat.groupby('season'):
        if grp.empty:
            continue

        if season == current_season:
            if grp['is_preliminary'].any():
                prelim_start_idx = grp[grp['is_preliminary']].index[0]
                confirmed = grp.loc[:prelim_start_idx]
                prelim = grp.loc[prelim_start_idx:]

                ax.plot(confirmed['season_week'], confirmed['ili_pct'], color='#D55E00', linewidth=2.5)
                ax.plot(prelim['season_week'], prelim['ili_pct'], color='#D55E00', linestyle='--', alpha=0.65)

            else:
                ax.plot(grp['season_week'], grp['ili_pct'], color='#D55E00', linewidth=2.5)

            last = grp.iloc[-1]
            ax.text(last['season_week'], last['ili_pct'], f" {season}", color='#D55E00', fontweight='bold', va='center')

        elif season == recent_season:
            ax.plot(grp['season_week'], grp['ili_pct'], color='#0072B2', linewidth=1.8, alpha=0.85)
            last = grp.iloc[-1]
            ax.text(last['season_week'] + 0.5, last['ili_pct'], f" {season}", color='#0072B2', fontweight='bold', va='center')

        else:
            ax.plot(grp['season_week'], grp['ili_pct'], color='#BDBDBD', alpha=0.6, linewidth=1.2)

    ax.set_title(f"ILI trung bình toàn quốc: mùa {current_season} so với các mùa trước")
    ax.set_xlabel("Tuần trong mùa (1 = tuần MMWR 40)")
    ax.set_ylabel("ILI trung bình các bang (%)")
    ax.set_xlim(1, 55)
    ax.grid(axis='y', linestyle='--', alpha=0.3)

    plt.tight_layout()
    fig.savefig(output_dir / 'tv3_season_overlay.png')
    plt.close(fig)

def plot_severity_boxplot(milestones: pd.DataFrame, output_dir: Path):
    setup_style()

    fig, ax = plt.subplots(figsize=(11, 5))
    sub = milestones[~milestones['season'].isin(EXCLUDE_SEASON + ['2026-27'])].copy()
    sub = sub[sub['source'] == 'ili'].sort_values('season')

    sns.boxplot(data=sub, x='season', y='peak_value', color='#56B4E9', ax=ax, fliersize=3)
    ax.set_title("Đỉnh ILI của các bang theo mùa")
    ax.set_xlabel("Mùa cúm")
    ax.set_ylabel("Đỉnh ILI trong mùa (%)")
    plt.xticks(rotation=30)
    ax.grid(axis='y', linestyle='--', alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_dir / 'tv3_severity_boxplot.png')
    plt.close(fig)

def plot_onset_distribution(milestones: pd.DataFrame, output_dir: Path):
    setup_style()

    fig, ax = plt.subplots(figsize=(12, 5))
    sub = milestones[(~milestones['season'].isin(EXCLUDE_SEASON + ['2026-27'])) & (milestones['onset_week'].notna())]

    ax.hist(sub['onset_week'], bins=20, color='#0072B2', edgecolor='white', alpha=0.85)
    median_w = sub['onset_week'].median()
    ax.axvline(median_w, color='#D55E00', linestyle='--', linewidth=2)
    ax.text(median_w + 0.3, ax.get_ylim()[1] * 0.9, f"Trung vị: tuần {int(median_w)}", color='#D55E00', fontweight='bold')
    ax.set_title("Phân bố tuần khởi phát của các bang-mùa")
    ax.set_xlabel("Tuần khởi phát (tuần trong mùa)")
    ax.set_ylabel("Số bang-mùa")

    plt.tight_layout()
    fig.savefig(output_dir / 'tv3_onset_histogram.png')
    plt.close(fig)

def plot_onset_ridgeline(milstones: pd.DataFrame, output_dir: Path):
    setup_style()

    fig, ax = plt.subplots(figsize=(10, 7))
    sub = milstones[(~milstones['season'].isin(EXCLUDE_SEASON + ['2026-27'])) & (milstones['onset_week'].notna())]

    x_grid = np.linspace(1, 35, 300)
    overlap = 0.65

    for idx, season in enumerate(sorted(sub['season'].unique(), reverse=True)):
        vals = sub[sub['season'] == season]['onset_week'].values
        if len(vals) < 3 or np.std(vals) == 0:
            continue

        kde = gaussian_kde(vals, bw_method=0.45)
        y_vals = kde(x_grid)
        y_vals = y_vals / y_vals.max() * overlap
        baseline_y = idx * 0.55

        ax.fill_between(x_grid, baseline_y, baseline_y + y_vals, color='#0072B2', alpha=0.65, zorder=idx+1)
        ax.plot(x_grid, baseline_y + y_vals, color='white', linewidth=1.2, zorder=idx+2)
        ax.axhline(baseline_y, color='#BDBDBD', linewidth=0.6, zorder=idx)

        med = np.median(vals)
        ax.plot([med, med], [baseline_y, baseline_y + overlap * 0.65], color='#D55E00', linestyle='--', linewidth=1.5, zorder=idx+3)
        ax.text(0.5, baseline_y + 0.08, season, fontweight='bold', fontsize=9, va='bottom', ha='right')

    ax.set_yticks([])
    ax.spines['left'].set_visible(False)
    ax.set_xlim(1, 35)
    ax.set_xlabel("Tuần khởi phát (tuần trong mùa)")
    ax.set_title("Phân bố tuần khởi phát theo từng mùa (vạch đỏ: trung vị)")

    plt.tight_layout()
    fig.savefig(output_dir / 'tv3_onset_ridgeline.png')
    plt.close(fig)

def plot_lag_and_acf(df: pd.DataFrame, output_dir: Path):
    setup_style()

    fig, ax = plt.subplots(1, 2, figsize=(16, 5))
    nat = df.groupby('epiweek')['ili_pct'].mean().dropna().sort_index()

    ax[0].scatter(nat.shift(1), nat, alpha=0.5, color='#0072B2', s=18)
    ax[0].set_title("ILI tuần này so với tuần trước")
    ax[0].set_xlabel("ILI tuần t − 1 (%)")
    ax[0].set_ylabel("ILI tuần t (%)")

    plot_acf(nat, lags=20, ax=ax[1], color='#009E73')
    ax[1].set_title("Hàm tự tương quan (ACF) của ILI toàn quốc")
    ax[1].set_xlabel("Độ trễ (tuần)")
    ax[1].set_ylabel("Tự tương quan")

    plt.tight_layout()
    fig.savefig(output_dir / 'tv3_lag_acf_ili.png')
    plt.close(fig)

def plot_state_week_heatmap(df: pd.DataFrame, milestones: pd.DataFrame, output_dir: Path, target_season: str = '2024-25'):
    setup_style()

    sub = df[df['season'] == target_season].copy()
    sub['state_upper'] = sub['state'].str.upper()

    m_sub = milestones[milestones['season'] == target_season][['state', 'onset_week', 'peak_week']].copy()
    m_sub['state_upper'] = m_sub['state'].str.upper()

    order = m_sub.sort_values(['onset_week', 'peak_week'])['state_upper'].tolist()
    piv = sub.pivot(index='state_upper', columns='season_week', values='ili_pct').reindex(order)

    fig, ax = plt.subplots(figsize=(12, 10))
    sns.heatmap(piv, cmap='YlOrRd', ax=ax, cbar_kws={'label': "ILI (%)"})
    ax.set_title(f"ILI theo bang và tuần, mùa {target_season} (bang sắp theo tuần khởi phát)")
    ax.set_xlabel("Tuần trong mùa (1 = tuần MMWR 40)")
    ax.set_ylabel("Bang (khởi phát sớm → muộn)")

    plt.tight_layout()
    fig.savefig(output_dir / 'tv3_heatmap_state_week.png')
    plt.close(fig)

def plot_cluster_dendrogram(Z: np.ndarray, state_labels: list, output_dir: Path):
    setup_style()

    fig, ax = plt.subplots(figsize=(12, 5))
    upper_labels = [s.upper() for s in state_labels]
    dendrogram(
        Z,
        labels=upper_labels,
        leaf_rotation=90,
        leaf_font_size=8,
        ax=ax,
        color_threshold=0.7 * max(Z[:, 2])
    )

    ax.set_title(f"Phân cụm Ward {len(state_labels)} bang theo hình dạng đường cong mùa cúm")
    ax.set_xlabel("Bang")
    ax.set_ylabel("Khoảng cách Ward (đường cong z-score)")

    plt.tight_layout()
    fig.savefig(output_dir / 'tv3_dendrogram.png')
    plt.close(fig)


# ---------------- Hinh cho cac phat hien them (insights.py) ----------------

def plot_signal_lead(lead: pd.DataFrame, output_dir: Path):
    """Moi tin hieu dat nua dinh truoc nhap vien bao nhieu tuan (trung binh, ty le bang-mua di truoc)."""
    setup_style()
    d = lead.sort_values('lead_mean')
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.barh(d['ten'], d['lead_mean'], color='#0072B2')
    for y, (m, s) in enumerate(zip(d['lead_mean'], d['share_earlier'])):
        ax.text(m + 0.05, y, f"{m:.1f} tuần, {s:.0%} bang-mùa đi trước", va='center', fontsize=9)
    ax.axvline(0, color='#555555', linewidth=0.8)
    ax.set_xlabel("Đạt nửa đỉnh trước nhập viện (tuần, trung bình)")
    ax.set_title("Tín hiệu nào báo sớm nhất (mùa 2022-23 đến 2025-26)")
    ax.set_xlim(0, max(3.5, d['lead_mean'].max() + 1.8))
    plt.tight_layout()
    fig.savefig(output_dir / 'tv3_signal_lead.png')
    plt.close(fig)


def plot_season_progress(progress: dict, output_dir: Path):
    """So bang da khoi phat den cung tuan mua: mua hien tai so voi cac mua truoc."""
    setup_style()
    hist = progress['history']
    names = list(hist) + [progress['season']]
    vals = list(hist.values()) + [progress['states_onset_now']]
    colors = ['#BDBDBD'] * len(hist) + ['#D55E00']
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.bar(names, vals, color=colors)
    ax.axhline(progress['history_median'], color='#0072B2', linestyle='--', linewidth=1.2)
    ax.text(len(names) - 0.5, progress['history_median'] + 0.8, f"trung vị {progress['history_median']:.0f}",
            color='#0072B2', ha='right', fontsize=9)
    ax.set_ylabel("Số bang đã khởi phát")
    ax.set_title(f"Số bang đã khởi phát đến tuần {progress['onset_confirmed_by_week']} của mùa")
    plt.xticks(rotation=30)
    plt.tight_layout()
    fig.savefig(output_dir / 'tv3_season_progress.png')
    plt.close(fig)


def plot_onset_latitude(milestones: pd.DataFrame, dim_state: pd.DataFrame, spread: dict, output_dir: Path):
    """Thu hang khoi phat trung binh cua moi bang theo vi do (48 bang luc dia + DC)."""
    setup_style()
    x = milestones[~milestones['season'].isin(['2009-10', '2010-11', '2020-21'])
                   & (milestones['season'] < milestones['season'].max())].dropna(subset=['onset_week']).copy()
    x['rk'] = x.groupby('season')['onset_week'].rank(pct=True)
    s = x.groupby('state')['rk'].mean().rename('rk').reset_index().merge(dim_state, on='state')
    s = s[s['contiguous'].astype(bool)]
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.scatter(s['lat'], s['rk'], color='#009E73', s=22)
    for r in s.itertuples():
        ax.annotate(r.state.upper(), (r.lat, r.rk), fontsize=7, xytext=(2, 2), textcoords='offset points')
    b = np.polyfit(s['lat'], s['rk'], 1)
    xs = np.linspace(s['lat'].min(), s['lat'].max(), 50)
    ax.plot(xs, np.polyval(b, xs), color='#D55E00', linewidth=1.5)
    ax.set_xlabel("Vĩ độ (°B)")
    ax.set_ylabel("Thứ hạng khởi phát trung bình (0 = sớm nhất)")
    ax.set_title(f"Bang phía Nam khởi phát sớm hơn (Spearman ρ = {spread['rho_lat']:.2f}, p = {spread['p_lat']:.1e})")
    plt.tight_layout()
    fig.savefig(output_dir / 'tv3_onset_latitude.png')
    plt.close(fig)
