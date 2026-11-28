import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from pathlib import Path
from scipy.stats import gaussian_kde, spearmanr
from scipy.cluster.hierarchy import dendrogram
from statsmodels.graphics.tsaplots import plot_acf


EXCLUDE_SEASONS = ['2009-10', '2020-21']

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
    nat = df[~df['season'].isin(EXCLUDE_SEASONS)].groupby(['season', 'season_week'], as_index=False).agg(**agg_dict).sort_values(['season', 'season_week'])
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

    ax.set_title(f"National % ILI trajectory of {current_season} compared against historical seasonal patterns")
    ax.set_xlabel("Season week (Starting from MMWR week 40)")
    ax.set_ylabel("Mean outpatient visits for ILI (%)")
    ax.set_xlim(1, 55)
    ax.grid(axis='y', linestyle='--', alpha=0.3)

    plt.tight_layout()
    fig.savefig(output_dir / 'season_overlay.png')
    plt.close(fig)

def plot_severity_boxplot(milestones: pd.DataFrame, output_dir: Path):
    setup_style()

    fig, ax = plt.subplots(figsize=(11, 5))
    sub = milestones[~milestones['season'].isin(EXCLUDE_SEASONS + ['2026-27'])].copy()
    sub = sub[sub['source'] == 'ili'].sort_values('season')

    sns.boxplot(data=sub, x='season', y='peak_value', color='#56B4E9', ax=ax, fliersize=3)
    ax.set_title("Seasonal peak % ILI varies substantially across years with higher medians in recent seasons")
    ax.set_xlabel("Flu season")
    ax.set_ylabel("Seasonal peak outpatient ILI (%)")
    plt.xticks(rotation=30)
    ax.grid(axis='y', linestyle='--', alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_dir / 'severity_boxplot.png')
    plt.close(fig)

def plot_onset_distribution(milestones: pd.DataFrame, output_dir: Path):
    setup_style()

    fig, ax = plt.subplots(figsize=(12, 5))
    sub = milestones[(~milestones['season'].isin(EXCLUDE_SEASONS + ['2026-27'])) & (milestones['onset_week'].notna())]

    ax.hist(sub['onset_week'], bins=20, color='#0072B2', edgecolor='white', alpha=0.85)
    median_w = sub['onset_week'].median()
    ax.axvline(median_w, color='#D55E00', linestyle='--', linewidth=2)
    ax.text(median_w + 0.3, ax.get_ylim()[1] * 0.9, f"Median: Week {int(median_w)}", color='#D55E00', fontweight='bold')
    ax.set_title("State-season epidemic onset timing is right-skewed and concentrated in the first half of the season")
    ax.set_xlabel("Onset week (Weeks since MMWR week 40)")
    ax.set_ylabel("State-Season count")

    plt.tight_layout()
    fig.savefig(output_dir / 'onset_histogram.png')
    plt.close(fig)

def plot_onset_ridgeline(milstones: pd.DataFrame, output_dir: Path):
    setup_style()

    fig, ax = plt.subplots(figsize=(10, 7))
    sub = milstones[(~milstones['season'].isin(EXCLUDE_SEASONS + ['2026-27'])) & (milstones['onset_week'].notna())]
    seasons = sorted(sub['season'].unique(), reverse=True)

    x_grid = np.linspace(1, 35, 300)
    max_height = 0.72
    row_step = 0.5

    for idx, season in enumerate(sorted(sub['season'].unique(), reverse=True)):
        vals = sub[sub['season'] == season]['onset_week'].values
        if len(vals) < 3 or np.std(vals) == 0:
            continue

        kde = gaussian_kde(vals, bw_method=0.45)
        raw_y = kde(x_grid)
        y_vals = raw_y / raw_y.max() * max_height
        baseline_y = idx * row_step

        z_base = (len(seasons) - idx) * 10

        ax.fill_between(x_grid, baseline_y, baseline_y + y_vals, color='white', alpha=1, zorder=z_base)
        ax.fill_between(x_grid, baseline_y, baseline_y + y_vals, color='#0072B2', alpha=0.78, zorder=z_base + 1)
        ax.plot(x_grid, baseline_y + y_vals, color='white', linewidth=1.2, zorder=z_base + 2)
        ax.axhline(baseline_y, color='#BDBDBD', linewidth=0.6, zorder=z_base - 1)

        med = np.median(vals)
        med_height = kde([med])[0] / raw_y.max() * max_height
        ax.plot([med, med], [baseline_y, baseline_y + med_height], color='#D55E00', linestyle='--', linewidth=1.5, zorder=z_base + 3)
        ax.text(0.4, baseline_y + 0.06, season, fontweight='bold', fontsize=9, va='bottom', ha='right')

    ax.set_yticks([])
    ax.spines['left'].set_visible(False)
    ax.set_xlim(1, 35)
    ax.set_ylim(-0.05, (len(seasons) - 1) * row_step + max_height + 0.1)
    ax.set_xlabel("Onset week (Weeks since MMWR week 40)")
    ax.set_title("Seasonal distribution of epidemic onset weeks shifts notably across influenza seasons")

    plt.tight_layout()
    fig.savefig(output_dir / 'onset_ridgeline.png')
    plt.close(fig)

def plot_lag_and_acf(df: pd.DataFrame, output_dir: Path):
    setup_style()

    fig, ax = plt.subplots(1, 2, figsize=(16, 5))
    nat = df.groupby('epiweek')['ili_pct'].mean().dropna().sort_index()

    ax[0].scatter(nat.shift(1), nat, alpha=0.5, color='#0072B2', s=18)
    ax[0].set_title("Weekly % ILI exhibits strong first-order autocorrelation")
    ax[0].set_xlabel("Prior week % ILI (t - 1)")
    ax[0].set_ylabel("Current week % ILI (t)")

    plot_acf(nat, lags=20, ax=ax[1], color='#009E73')
    ax[1].set_title("Autocorrelation function (ACF) decays gradually across multi-week lags")
    ax[1].set_xlabel("Lag (Weeks)")
    ax[1].set_ylabel("Autocorrelation")

    plt.tight_layout()
    fig.savefig(output_dir / 'lag_acf_ili.png')
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
    sns.heatmap(piv, cmap='YlOrRd', ax=ax, cbar_kws={'label': "Outpatient ILI (%)"})
    ax.set_title(f"Ordering states by onset week in {target_season} reveals geographic spread patterns")
    ax.set_xlabel("Season week (Starting from MMWR week 40)")
    ax.set_ylabel("State (Ordered from earliest to latest onset)")

    plt.tight_layout()
    fig.savefig(output_dir / 'heatmap_state_week.png')
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

    ax.set_title(f"Hierarchical clustering groups {len(state_labels)} jurisdictions by normalized seasonal curve shape")
    ax.set_xlabel("State")
    ax.set_ylabel("Ward linkage distance (Z-score normalized curves)")

    plt.tight_layout()
    fig.savefig(output_dir / 'dendrogram.png')
    plt.close(fig)

def plot_spatial_onset_spread(milestones: pd.DataFrame, state_centroids: dict, output_dir: Path):
    setup_style()

    sub = milestones[(~milestones['season'].isin(EXCLUDE_SEASONS + ['2026-27'])) & (milestones['onset_week'].notna())].copy()
    sub['state_upper'] = sub['state'].str.upper()

    coord_df = pd.DataFrame.from_dict(state_centroids, orient='index', columns=['lat', 'lon']).reset_index()
    coord_df.rename(columns={'index': 'state_upper'}, inplace=True)

    agg = sub.groupby('state_upper', as_index=False)['onset_week'].median().merge(coord_df, on='state_upper')
    conus = agg[~agg['state_upper'].isin(['AK', 'HI'])].copy()

    fig, axes = plt.subplots(1, 2, figsize=(14, 5.2), sharey=True)
    configs = [
        ('lat', 'Latitude (°N, South → North)', '#0072B2'),
        ('lon', 'Longitude (°W, West → East)', '#009E73')
    ]

    for ax, (col, xlabel, color) in zip(axes, configs):
        r_s, p_s = spearmanr(conus[col], conus['onset_week'])
        sns.regplot(
            data=conus, x=col, y='onset_week', ax=ax,
            scatter_kws={'alpha': 0.75, 's': 45, 'color': color},
            line_kws={'color': '#D55E00', 'linewidth': 1.8}
        )

        conus_sorted = conus.sort_values(['onset_week', col]).reset_index(drop=True)
        prev_x, prev_y, toggle = -999.0, -999.0, 1
        for _, row in conus_sorted.iterrows():
            x_val, y_val = row[col], row['onset_week']
            if abs(y_val - prev_y) < 0.35 and abs(x_val - prev_x) < 2.2:
                y_offset = -0.34 if toggle > 0 else 0.16
                toggle *= -1
            else:
                y_offset = 0.14
                toggle = 1
            ax.text(x_val, y_val + y_offset, row['state_upper'], fontsize=7, ha='center', alpha=0.85)
            prev_x, prev_y = x_val, y_val

        ax.set_xlabel(xlabel)
        ax.set_title(f"Spearman = {r_s:.3f} (p = {p_s:.4f})")

    axes[0].set_ylabel("Median epidemic onset week across seasons")
    axes[1].set_ylabel("")
    fig.suptitle("Geographic gradient of influenza epidemic onset across contiguous US jurisdictions", fontweight='bold', y=1.02)

    plt.tight_layout()
    fig.savefig(output_dir / 'spatial_onset_correlation.png', bbox_inches='tight')
    plt.close(fig)
