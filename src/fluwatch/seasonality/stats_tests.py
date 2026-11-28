import numpy as np
import pandas as pd
from itertools import combinations
from scipy.stats import kruskal, norm, rankdata, kendalltau, theilslopes, spearmanr, pearsonr


EXCLUDE_SEASONS = ['2009-10', '2020-21', '2026-27']
US_STATE_CENTROIDS = {
    'AL': (32.8067, -86.7911), 'AK': (61.3707, -152.4044), 'AZ': (33.7298, -111.4312),
    'AR': (34.9697, -92.3731), 'CA': (36.1162, -119.6816), 'CO': (39.0598, -105.3111),
    'CT': (41.5978, -72.7554), 'DE': (39.3185, -75.5071), 'DC': (38.8974, -77.0268),
    'FL': (27.7663, -81.6868), 'GA': (33.0406, -83.6431), 'HI': (21.0943, -157.4983),
    'ID': (44.2405, -114.4788), 'IL': (40.3495, -88.9861), 'IN': (39.8494, -86.2583),
    'IA': (42.0115, -93.2105), 'KS': (38.5266, -96.7265), 'KY': (37.6681, -84.6701),
    'LA': (31.1695, -91.8678), 'ME': (44.6939, -69.3819), 'MD': (39.0639, -76.8021),
    'MA': (42.2302, -71.5301), 'MI': (43.3266, -84.5361), 'MN': (45.6945, -93.9002),
    'MS': (32.7416, -89.6787), 'MO': (38.4561, -92.2884), 'MT': (46.9219, -110.4544),
    'NE': (41.1254, -98.2681), 'NV': (38.3135, -117.0554), 'NH': (43.4525, -71.5639),
    'NJ': (40.2989, -74.5210), 'NM': (34.8405, -106.2485), 'NY': (42.1657, -74.9481),
    'NC': (35.6301, -79.8064), 'ND': (47.5289, -99.7840), 'OH': (40.3888, -82.7649),
    'OK': (35.5653, -96.9289), 'OR': (44.5720, -122.0709), 'PA': (40.5908, -77.2098),
    'RI': (41.6809, -71.5118), 'SC': (33.8569, -80.9450), 'SD': (44.2998, -99.4388),
    'TN': (35.7478, -86.6923), 'TX': (31.0545, -97.5635), 'UT': (40.1500, -111.8624),
    'VT': (44.0459, -72.7107), 'VA': (37.7693, -78.1700), 'WA': (47.4009, -121.4905),
    'WV': (38.4912, -80.9545), 'WI': (44.2685, -89.6165), 'WY': (42.7560, -107.3025),
}

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

def mann_kendall_single(y, alpha=0.05):
    y = np.asarray(y, dtype=float)
    y = y[~np.isnan(y)]
    n = len(y)
    if n < 4 or np.std(y) == 0:
        return {
            'n_seasons': n,
            'tau': np.nan,
            'p_value': np.nan,
            'sens_slope': np.nan,
            'significant_005': False,
            'trend': 'insufficient_data'
        }

    t = np.arange(n)
    res_mk = kendalltau(t, y)
    tau, p_val = float(res_mk.statistic), float(res_mk.pvalue)
    slope = float(theilslopes(y, t).slope)
    is_sig = bool(p_val < alpha)

    if is_sig:
        trend = 'later_onset' if tau > 0 else 'earlier_onset'
    else:
        trend = 'no_significant_trend'

    return {
        'n_seasons': n,
        'tau': round(tau, 4),
        'p_value': round(p_val, 6),
        'sens_slope': round(slope, 4),
        'significant_005': is_sig,
        'trend': trend
    }

def run_onset_trend_mann_kendall(milestones_df: pd.DataFrame, alpha=0.05):
    sub = milestones_df[
        (~milestones_df['season'].isin(EXCLUDE_SEASONS)) &
        (milestones_df['onset_week'].notna())
    ].copy()
    sub['state_upper'] = sub['state'].str.upper()

    nat_season = (
        sub.groupby('season', as_index=False)
        .agg(
            median_onset=('onset_week', 'median'),
            mean_onset=('onset_week', 'mean'),
            n_states=('state_upper', 'nunique')
        )
        .sort_values('season')
    )

    nat_records = []
    for metric in ['median_onset', 'mean_onset']:
        res = mann_kendall_single(nat_season[metric].values, alpha=alpha)
        nat_records.append({
            'scope': 'National',
            'metric': metric,
            'first_season': nat_season['season'].iloc[0],
            'last_season': nat_season['season'].iloc[-1],
            **res
        })
    nat_mk_df = pd.DataFrame(nat_records)

    state_records = []
    for state, grp in sub.sort_values('season').groupby('state_upper'):
        res = mann_kendall_single(grp['onset_week'].values, alpha=alpha)
        state_records.append({
            'state': state,
            'median_onset_all': round(float(grp['onset_week'].median()), 2),
            **res
        })
    state_mk_df = pd.DataFrame(state_records).sort_values('p_value').reset_index(drop=True)

    return nat_mk_df, state_mk_df

def infer_spread_direction(r_lat, p_lat, r_lon, p_lon, alpha=0.05):
    ns_dir = ""
    if p_lat < alpha:
        ns_dir = "South -> North" if r_lat > 0 else "North -> South"

    ew_dir = ""
    if p_lon < alpha:
        ew_dir = "West -> East" if r_lon > 0 else "East -> West"

    if ns_dir and ew_dir:
        return f"Diagonal spread ({ns_dir} & {ew_dir})"
    if ns_dir:
        return f"Latitudinal spread ({ns_dir})"
    if ew_dir:
        return f"Longitudinal spread ({ew_dir})"
    
    return "No significant linear spread direction"

def run_spatial_onset_correlation(milestones_df: pd.DataFrame, dim_state: pd.DataFrame = None, alpha=0.05):
    sub = milestones_df[(~milestones_df['season'].isin(EXCLUDE_SEASONS)) &(milestones_df['onset_week'].notna())].copy()
    sub['state_upper'] = sub['state'].str.upper()

    if dim_state is not None and {'lat', 'lon'}.issubset(dim_state.columns):
        coord_df = dim_state[['state', 'lat', 'lon']].copy()
        coord_df['state_upper'] = coord_df['state'].str.upper()
        coord_df = coord_df[['state_upper', 'lat', 'lon']].drop_duplicates()
    else:
        coord_df = pd.DataFrame.from_dict(US_STATE_CENTROIDS, orient='index', columns=['lat', 'lon']).reset_index()
        coord_df.rename(columns={'index': 'state_upper'}, inplace=True)

    sub = sub.merge(coord_df, on='state_upper', how='inner')

    state_agg = (
        sub.groupby(['state_upper', 'lat', 'lon'], as_index=False)
        .agg(
            median_onset=('onset_week', 'median'),
            mean_onset=('onset_week', 'mean'),
            n_seasons=('season', 'count')
        )
    )

    overall_records = []
    subsets = {
        'All_51_Jurisdictions': state_agg,
        'CONUS_49_Excl_AK_HI': state_agg[~state_agg['state_upper'].isin(['AK', 'HI'])]
    }

    for scope_name, df_scope in subsets.items():
        for metric in ['median_onset', 'mean_onset']:
            r_lat_s, p_lat_s = spearmanr(df_scope['lat'], df_scope[metric])
            r_lon_s, p_lon_s = spearmanr(df_scope['lon'], df_scope[metric])
            r_lat_p, p_lat_p = pearsonr(df_scope['lat'], df_scope[metric])
            r_lon_p, p_lon_p = pearsonr(df_scope['lon'], df_scope[metric])

            overall_records.append({
                'scopre': scope_name,
                'metric': metric,
                'n_states': len(df_scope),
                'spearman_r_lat': round(float(r_lat_s), 4),
                'spearman_p_lat': round(float(p_lat_s), 6),
                'spearman_r_lon': round(float(r_lon_s), 4),
                'spearman_p_lon': round(float(p_lon_s), 6),
                'pearson_r_lat': round(float(r_lat_p), 4),
                'pearson_p_lat': round(float(p_lat_p), 6),
                'pearson_r_lon': round(float(r_lon_p), 4),
                'pearson_p_lon': round(float(p_lon_p), 6),
                'significant_lat_005': bool(p_lat_s < alpha),
                'significant_lon_005': bool(p_lon_s < alpha),
                'inferred_direction': infer_spread_direction(r_lat_s, p_lat_s, r_lon_s, p_lon_s, alpha=alpha)
            })
    overall_df = pd.DataFrame(overall_records)

    season_records = []
    conus_sub = sub[~sub['state_upper'].isin(['AK', 'HI'])]
    for season, grp in conus_sub.groupby('season'):
        if len(grp) < 10:
            continue

        r_lat, p_lat = spearmanr(grp['lat'], grp['onset_week'])
        r_lon, p_lon = spearmanr(grp['lon'], grp['onset_week'])
        season_records.append({
            'season': season,
            'n_states': len(grp),
            'spearman_r_lat': round(float(r_lat), 4),
            'spearman_p_lat': round(float(p_lat), 6),
            'spearman_r_lon': round(float(r_lon), 4),
            'spearman_p_lon': round(float(p_lon), 6),
            'significant_lat_005': bool(p_lat < alpha),
            'significant_lon_005': bool(p_lon < alpha),
            'inferred_direction': infer_spread_direction(r_lat, p_lat, r_lon, p_lon, alpha=alpha)
        })
    by_season_df = pd.DataFrame(season_records).sort_values('season').reset_index(drop=True)

    return overall_df, by_season_df
