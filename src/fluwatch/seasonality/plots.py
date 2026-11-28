import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from pathlib import Path
from scipy.stats import gaussian_kde, spearmanr
from scipy.cluster.hierarchy import dendrogram
from statsmodels.graphics.tsaplots import plot_acf
from fluwatch.seasonality.milestones import *
from fluwatch.seasonality.stats_tests import *


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


def _national_ili_by_week(df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    sub = df.copy()
    if {'num_ili', 'num_patients'}.issubset(sub.columns):
        sub = sub[sub['ili_pct'].notna()].copy()
        agg = sub.groupby(group_cols, as_index=False).agg(
            num_ili=('num_ili', 'sum'),
            num_patients=('num_patients', 'sum'),
            ili_mean=('ili_pct', 'mean'),
            is_preliminary=('is_preliminary', 'any') if 'is_preliminary' in sub.columns else ('ili_pct', lambda _: False),
        )
        agg['ili_pct'] = np.where(
            agg['num_patients'] > 0,
            agg['num_ili'] / agg['num_patients'] * 100.0,
            agg['ili_mean'],
        )
        return agg

    return sub.groupby(group_cols, as_index=False).agg(
        ili_pct=('ili_pct', 'mean'),
        is_preliminary=('is_preliminary', 'any') if 'is_preliminary' in sub.columns else ('ili_pct', lambda _: False),
    )


def plot_season_overlay(df: pd.DataFrame, output_dir: Path, current_season: str = None, recent_season: str = None):
    setup_style()

    sub = df[~df['season'].isin(EXCLUDED_HIST_SEASONS)].copy()
    nat = _national_ili_by_week(sub, ['season', 'season_week']).sort_values(['season', 'season_week'])

    seasons = sorted(nat['season'].unique())
    if current_season is None and seasons:
        current_season = seasons[-1]
    if recent_season is None and len(seasons) >= 2:
        recent_season = seasons[-2]

    fig, ax = plt.subplots(figsize=(10, 5))
    for season, grp in nat.groupby('season'):
        if grp.empty:
            continue

        if season == current_season:
            if grp['is_preliminary'].any():
                prelim_start_idx = grp[grp['is_preliminary']].index[0]
                confirmed = grp.loc[:prelim_start_idx]
                prelim = grp.loc[prelim_start_idx:]

                ax.plot(confirmed['season_week'], confirmed['ili_pct'], color='#D55E00', linewidth=2.5)
                ax.plot(prelim['season_week'], prelim['ili_pct'], color='#D55E00', linestyle='--', alpha=0.7, linewidth=2.2)
            else:
                ax.plot(grp['season_week'], grp['ili_pct'], color='#D55E00', linewidth=2.5)

            last = grp.iloc[-1]
            suffix = " (sơ bộ)" if bool(last['is_preliminary']) else ""
            ax.text(last['season_week'] + 0.4, last['ili_pct'], f"{season}{suffix}", color='#D55E00', fontweight='bold', va='center')

        elif season == recent_season:
            ax.plot(grp['season_week'], grp['ili_pct'], color='#0072B2', linewidth=1.8, alpha=0.85)
            last = grp.iloc[-1]
            ax.text(last['season_week'] + 0.5, last['ili_pct'], f"{season}", color='#0072B2', fontweight='bold', va='center')

        else:
            ax.plot(grp['season_week'], grp['ili_pct'], color='#BDBDBD', alpha=0.6, linewidth=1.2)

    cur_grp = nat[nat['season'] == current_season]
    title = f"Diễn biến % ILI toàn quốc mùa {current_season} so với các mùa trước"
    if not cur_grp.empty:
        last_row = cur_grp.iloc[-1]
        hist_at_wk = nat[(nat['season'] != current_season) & (nat['season_week'] == last_row['season_week'])]['ili_pct']
        if not hist_at_wk.empty:
            med_hist = hist_at_wk.median()
            comp = "cao hơn" if last_row['ili_pct'] >= med_hist else "thấp hơn"
            title = (
                f"Mùa {current_season} có % ILI đầu mùa {comp} trung vị lịch sử "
                f"({last_row['ili_pct']:.2f}% so với {med_hist:.2f}% ở tuần {int(last_row['season_week'])})"
            )

    ax.set_title(title)
    ax.set_xlabel("Tuần trong mùa (Bắt đầu từ tuần MMWR 40)")
    ax.set_ylabel("Tỷ lệ lượt khám ngoại trú do ILI (%)")
    ax.set_xlim(1, 56)
    ax.grid(axis='y', linestyle='--', alpha=0.3)

    plt.tight_layout()
    fig.savefig(output_dir / 'season_overlay.png')
    plt.close(fig)


def plot_severity_boxplot(milestones: pd.DataFrame, output_dir: Path):
    setup_style()

    fig, ax = plt.subplots(figsize=(11, 5))
    sub = filter_completed_milestones(milestones)
    sub = sub[sub['source'] == 'ili'].dropna(subset=['peak_value']).sort_values('season')

    sns.boxplot(data=sub, x='season', y='peak_value', color='#56B4E9', ax=ax, fliersize=3)
    ax.set_title("Đỉnh % ILI giữa các mùa biến động mạnh, các mùa sau đại dịch có trung vị cao hơn")
    ax.set_xlabel("Mùa cúm")
    ax.set_ylabel("Đỉnh tỷ lệ khám ngoại trú do ILI (%)")
    plt.xticks(rotation=30)
    ax.grid(axis='y', linestyle='--', alpha=0.3)

    plt.tight_layout()
    fig.savefig(output_dir / 'severity_boxplot.png')
    plt.close(fig)


def plot_onset_distribution(milestones: pd.DataFrame, output_dir: Path):
    setup_style()

    onset_col = get_onset_week_col(milestones)
    fig, ax = plt.subplots(figsize=(12, 5))
    sub = filter_completed_milestones(milestones)
    sub = sub[sub[onset_col].notna()].copy()
    vals = pd.to_numeric(sub[onset_col], errors='coerce').dropna()

    ax.hist(vals, bins=20, color='#0072B2', edgecolor='white', alpha=0.85)
    median_w = vals.median()
    ax.axvline(median_w, color='#D55E00', linestyle='--', linewidth=2)
    ax.text(median_w + 0.4, ax.get_ylim()[1] * 0.9, f"Trung vị: Tuần {int(round(median_w))}", color='#D55E00', fontweight='bold')
    ax.set_title("Tuần khởi phát dịch giữa các bang lệch phải và tập trung ở nửa đầu mùa")
    ax.set_xlabel("Tuần khởi phát (Số tuần kể từ tuần MMWR 40)")
    ax.set_ylabel("Số cặp bang × mùa")

    plt.tight_layout()
    fig.savefig(output_dir / 'onset_histogram.png')
    plt.close(fig)


def plot_onset_ridgeline(milestones: pd.DataFrame, output_dir: Path):
    setup_style()

    onset_col = get_onset_week_col(milestones)
    fig, ax = plt.subplots(figsize=(10, 7))
    sub = filter_completed_milestones(milestones)
    sub = sub[sub[onset_col].notna()].copy()
    sub[onset_col] = pd.to_numeric(sub[onset_col], errors='coerce')
    sub = sub[sub[onset_col].notna()]

    seasons = sorted(sub['season'].unique(), reverse=True)
    x_grid = np.linspace(1, 35, 300)
    max_height = 0.72
    row_step = 0.5

    for idx, season in enumerate(seasons):
        vals = sub[sub['season'] == season][onset_col].to_numpy(dtype=float)
        if len(vals) < 3 or np.std(vals) == 0:
            continue

        reflected = np.concatenate([vals, 2.0 - vals])
        kde = gaussian_kde(reflected, bw_method=0.45)
        raw_y = 2.0 * kde(x_grid)
        y_vals = raw_y / raw_y.max() * max_height
        baseline_y = idx * row_step

        z_base = (len(seasons) - idx) * 10

        ax.fill_between(x_grid, baseline_y, baseline_y + y_vals, color='white', alpha=1, zorder=z_base)
        ax.fill_between(x_grid, baseline_y, baseline_y + y_vals, color='#0072B2', alpha=0.78, zorder=z_base + 1)
        ax.plot(x_grid, baseline_y + y_vals, color='white', linewidth=1.2, zorder=z_base + 2)
        ax.axhline(baseline_y, color='#BDBDBD', linewidth=0.6, zorder=z_base - 1)

        med = float(np.median(vals))
        med_height = 2.0 * kde([med])[0] / raw_y.max() * max_height
        ax.plot([med, med], [baseline_y, baseline_y + med_height], color='#D55E00', linestyle='--', linewidth=1.5, zorder=z_base + 3)
        ax.text(0.4, baseline_y + 0.06, season, fontweight='bold', fontsize=9, va='bottom', ha='right')

    ax.set_yticks([])
    ax.spines['left'].set_visible(False)
    ax.set_xlim(1, 35)
    ax.set_ylim(-0.05, (len(seasons) - 1) * row_step + max_height + 0.28)
    ax.set_xlabel("Tuần khởi phát (Số tuần kể từ tuần MMWR 40)")
    ax.set_title("Phân bố tuần khởi phát dịch dịch chuyển rõ rệt qua các mùa cúm")

    plt.tight_layout()
    fig.savefig(output_dir / 'onset_ridgeline.png')
    plt.close(fig)


def plot_lag_and_acf(df: pd.DataFrame, output_dir: Path):
    setup_style()

    fig, ax = plt.subplots(1, 2, figsize=(16, 5))
    sub = df[~df['season'].isin(EXCLUDED_HIST_SEASONS)].copy()
    nat_season = _national_ili_by_week(sub, ['season', 'season_week', 'epiweek']).sort_values(['season', 'season_week'])
    nat_season['ili_lag1'] = nat_season.groupby('season')['ili_pct'].shift(1)
    lag_pairs = nat_season[['ili_lag1', 'ili_pct']].dropna()
    r_lag1 = lag_pairs['ili_lag1'].corr(lag_pairs['ili_pct'])

    ax[0].scatter(lag_pairs['ili_lag1'], lag_pairs['ili_pct'], alpha=0.5, color='#0072B2', s=18)
    ax[0].set_title(f"Tỷ lệ % ILI theo tuần tự tương quan bậc 1 rất mạnh (r = {r_lag1:.3f})")
    ax[0].set_xlabel("Tỷ lệ % ILI tuần trước (t - 1)")
    ax[0].set_ylabel("Tỷ lệ % ILI tuần hiện tại (t)")

    nat = _national_ili_by_week(sub, ['epiweek']).sort_values('epiweek')['ili_pct'].dropna()
    plot_acf(nat, lags=20, ax=ax[1], color='#009E73')
    ax[1].set_title("Hàm tự tương quan (ACF) duy trì dương và giảm dần qua nhiều tuần trễ")
    ax[1].set_xlabel("Độ trễ (Tuần)")
    ax[1].set_ylabel("Hệ số tự tương quan")

    plt.tight_layout()
    fig.savefig(output_dir / 'lag_acf_ili.png')
    plt.close(fig)


def plot_state_week_heatmap(df: pd.DataFrame, milestones: pd.DataFrame, output_dir: Path, target_season: str = '2024-25'):
    setup_style()

    onset_col = get_onset_week_col(milestones)
    peak_col = 'peak_season_week' if 'peak_season_week' in milestones.columns else 'peak_week'

    sub = df[df['season'] == target_season].copy()
    sub['state_upper'] = sub['state'].str.upper()

    m_sub = milestones[milestones['season'] == target_season][['state', onset_col, peak_col]].copy()
    m_sub['state_upper'] = m_sub['state'].str.upper()

    order = m_sub.sort_values([onset_col, peak_col])['state_upper'].tolist()
    piv = sub.pivot(index='state_upper', columns='season_week', values='ili_pct').reindex(order)

    fig, ax = plt.subplots(figsize=(12, 10))
    sns.heatmap(piv, cmap='YlOrRd', ax=ax, cbar_kws={'label': "Tỷ lệ khám ngoại trú do ILI (%)"})
    ax.set_title(f"Sắp xếp các bang theo tuần khởi phát mùa {target_season} cho thấy rõ trình tự lan dịch")
    ax.set_xlabel("Tuần trong mùa (Bắt đầu từ tuần MMWR 40)")
    ax.set_ylabel("Bang (Xếp từ khởi phát sớm nhất đến muộn nhất)")

    plt.tight_layout()
    fig.savefig(output_dir / 'heatmap_state_week.png')
    plt.close(fig)


def plot_cluster_dendrogram(Z: np.ndarray, state_labels: list, best_k: int, output_dir: Path):
    setup_style()

    fig, ax = plt.subplots(figsize=(12, 5))
    upper_labels = [s.upper() for s in state_labels]
    if best_k >= 2 and len(Z) >= best_k:
        color_threshold = 0.5 * (Z[-best_k, 2] + Z[-(best_k - 1), 2])
    else:
        color_threshold = 0.7 * max(Z[:, 2])

    dendrogram(
        Z,
        labels=upper_labels,
        leaf_rotation=90,
        leaf_font_size=8,
        ax=ax,
        color_threshold=color_threshold,
    )

    ax.set_title(f"Phân cụm thứ bậc chia {len(state_labels)} đơn vị thành {best_k} nhóm theo hình dạng đường cong mùa vụ")
    ax.set_xlabel("Bang / Đặc khu")
    ax.set_ylabel("Khoảng cách liên kết Ward (Đường cong chuẩn hóa Z-score)")

    plt.tight_layout()
    fig.savefig(output_dir / 'dendrogram.png')
    plt.close(fig)


def plot_spatial_onset_spread(milestones: pd.DataFrame, dim_state_or_centroids=None, output_dir: Path = None):
    setup_style()

    onset_col = get_onset_week_col(milestones)
    sub = filter_completed_milestones(milestones)
    sub = sub[sub[onset_col].notna()].copy()
    sub[onset_col] = pd.to_numeric(sub[onset_col], errors='coerce')
    sub = sub[sub[onset_col].notna()]
    sub['state_upper'] = sub['state'].str.upper()

    if isinstance(dim_state_or_centroids, dict):
        coord_df = pd.DataFrame.from_dict(dim_state_or_centroids, orient='index', columns=['lat', 'lon']).reset_index()
        coord_df.rename(columns={'index': 'state_upper'}, inplace=True)
    else:
        coord_df = resolve_state_coords(dim_state_or_centroids)

    agg = sub.groupby('state_upper', as_index=False)[onset_col].median().merge(coord_df, on='state_upper')
    agg.rename(columns={onset_col: 'median_onset'}, inplace=True)
    conus = agg[~agg['state_upper'].isin(['AK', 'HI'])].copy()

    fig, axes = plt.subplots(1, 2, figsize=(14, 5.2), sharey=True)
    configs = [
        ('lat', 'Vĩ độ (°N, Nam → Bắc)', '#0072B2'),
        ('lon', 'Kinh độ (°E, Tây → Đông)', '#009E73')
    ]

    stats_by_col = {}
    for ax, (col, xlabel, color) in zip(axes, configs):
        r_s, p_s = spearmanr(conus[col], conus['median_onset'])
        stats_by_col[col] = (float(r_s), float(p_s))
        sns.regplot(
            data=conus, x=col, y='median_onset', ax=ax,
            scatter_kws={'alpha': 0.75, 's': 45, 'color': color},
            line_kws={'color': '#D55E00', 'linewidth': 1.8}
        )

        conus_sorted = conus.sort_values(['median_onset', col]).reset_index(drop=True)
        x_span = float(conus[col].max() - conus[col].min())
        x_tol = 0.08 * x_span
        placed = []
        for _, row in conus_sorted.iterrows():
            x_val, y_val = float(row[col]), float(row['median_onset'])
            chosen_dy = 0.18
            for cand_dy in (0.18, -0.36, 0.42, -0.58, 0.62):
                if not any(abs(x_val - px) < x_tol and abs((y_val + cand_dy) - py) < 0.42 for px, py in placed):
                    chosen_dy = cand_dy
                    break
            ax.text(x_val, y_val + chosen_dy, row['state_upper'], fontsize=7, ha='center', alpha=0.85)
            placed.append((x_val, y_val + chosen_dy))

        ax.set_xlabel(xlabel)
        ax.set_title(f"Spearman r = {r_s:.3f} (p = {p_s:.4f})")

    r_lat, p_lat = stats_by_col['lat']
    r_lon, p_lon = stats_by_col['lon']
    if p_lat < 0.05 and p_lon < 0.05:
        ns_txt = "Nam → Bắc" if r_lat > 0 else "Bắc → Nam"
        ew_txt = "Tây → Đông" if r_lon > 0 else "Đông → Tây"
        suptitle = f"Tuần khởi phát mùa cúm có xu hướng lan chéo ({ns_txt} và {ew_txt}) qua {len(conus)} bang lục địa"
    elif p_lat < 0.05:
        suptitle = (
            "Các bang phía Nam có xu hướng khởi phát mùa cúm sớm hơn các bang phía Bắc"
            if r_lat > 0
            else "Các bang phía Bắc có xu hướng khởi phát mùa cúm sớm hơn các bang phía Nam"
        )
    elif p_lon < 0.05:
        ew_txt = "Tây → Đông" if r_lon > 0 else "Đông → Tây"
        suptitle = f"Tuần khởi phát mùa cúm có xu hướng lan theo kinh độ ({ew_txt})"
    else:
        suptitle = f"Chưa ghi nhận xu hướng lan tuyến tính có ý nghĩa theo tọa độ địa lý qua {len(conus)} bang lục địa"

    axes[0].set_ylabel("Trung vị tuần khởi phát qua các mùa")
    axes[1].set_ylabel("")
    fig.suptitle(suptitle, fontweight='bold', y=1.02)

    plt.tight_layout()
    fig.savefig(output_dir / 'spatial_onset_correlation.png', bbox_inches='tight')
    plt.close(fig)
