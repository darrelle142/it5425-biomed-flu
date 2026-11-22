import pandas as pd
from scipy.stats import kruskal


def run_hhs_comparisons(milestones_df: pd.DataFrame, dim_state: pd.DataFrame):
    exclude_seasons = ['2009-10', '2020-21', '2026-27']
    merged = milestones_df.merge(dim_state[['state', 'hhs_region']], on='state', how='left')
    merged = merged[~merged['season'].isin(exclude_seasons)]

    results = []
    for metric in ['onset_week', 'peak_value']:
        sub = merged.dropna(subset=[metric, 'hhs_region'])

        if metric == 'peak_value':
            sub = sub[sub['signal_source'] == 'ILINet']

        groups = [grp[metric].values for _, grp in sub.groupby('hhs_region') if len(grp) >= 3]
        if len(groups) > 2:
            stat, p_val = kruskal(*groups)
            results.append({
                'metric': metric,
                'test': "Kruskal-Wallis across HHS Regions",
                'statistic': round(stat, 4),
                'p_value': round(p_val, 6),
                'significant_005': p_val < 0.05
            })

    return pd.DataFrame(results)
