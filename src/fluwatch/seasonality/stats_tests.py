import numpy as np
import pandas as pd
from itertools import combinations
from scipy.stats import kruskal, norm, rankdata


def run_dunn_posthoc(sub: pd.DataFrame, metric, group_col='hhs_region'):
    df = sub[[group_col, metric]].dropna().copy()
    n = len(df)
    df['rank'] = rankdata(df[metric])

    _, counts = np.unique(df[metric].values, return_counts=True)
    tie_correction = np.sum(counts ** 3 - counts) / (12 * (n - 1)) if n > 1 else 0
    var_base = (n * (n + 1) / 12) - tie_correction

    group_stats = df.groupby(group_col)['rank'].agg(['count', 'mean'])
    groups = group_stats.index.tolist()

    rows = []
    for g1, g2 in combinations(groups, 2):
        n1, r1 = group_stats.loc[g1, 'count'], group_stats.loc[g1, 'mean']
        n2, r2 = group_stats.loc[g2, 'count'], group_stats.loc[g2, 'mean']
        se = np.sqrt(var_base * (1.0 / n1 + 1.0 / n2))
        z_stat = (r1 - r2) / se if se > 0 else 0
        p_raw = 2 * (1 - norm.cdf(abs(z_stat)))
        rows.append({
            'metric': metric,
            'group_1': g1,
            'group_2': g2,
            'z_stat': round(z_stat, 4),
            'p_raw': p_raw
        })

    res = pd.DataFrame(rows).sort_values('p_raw').reset_index(drop=True)
    m = len(res)
    res['p_adj_holm'] = np.minimum(1, np.maximum.accumulate(res['p_raw'] * (m - np.arange(m)))).round(6)
    res['p_raw'] = res['p_raw'].round(6)
    res['significant_005'] = res['p_adj_holm'] < 0.05

    return res

def run_hhs_comparisons(milestones_df: pd.DataFrame, dim_state: pd.DataFrame):
    exclude_seasons = ['2009-10', '2020-21', '2026-27']
    merged = milestones_df.merge(dim_state[['state', 'hhs_region']], on='state', how='left')
    merged = merged[~merged['season'].isin(exclude_seasons)]

    kw_results = []
    dunn_frames = []
    for metric in ['onset_week', 'peak_value']:
        sub = merged.dropna(subset=[metric, 'hhs_region'])

        if metric == 'peak_value':
            sub = sub[sub['source'] == 'ili']

        groups = [grp[metric].values for _, grp in sub.groupby('hhs_region') if len(grp) >= 3]
        if len(groups) > 2:
            stat, p_val = kruskal(*groups)
            is_sig = p_val < 0.05
            kw_results.append({
                'metric': metric,
                'test': "Kruskal-Wallis across HHS Regions",
                'statistic': round(stat, 4),
                'p_value': round(p_val, 6),
                'significant_005': is_sig
            })

            if is_sig:
                dunn_df = run_dunn_posthoc(sub, metric, 'hhs_region')
                dunn_frames.append(dunn_df)

    kw_df = pd.DataFrame(kw_results)
    dunn_all = pd.concat(dunn_frames, ignore_index=True) if dunn_frames else pd.DataFrame()

    return kw_df, dunn_all
