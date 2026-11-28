import numpy as np
import pandas as pd
from itertools import combinations
from scipy.stats import kruskal, norm, rankdata, kendalltau, theilslopes, spearmanr, pearsonr
from fluwatch.seasonality.milestones import *


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


def get_onset_week_col(milestones_df: pd.DataFrame) -> str:
    if 'onset_season_week' in milestones_df.columns:
        return 'onset_season_week'
    return 'onset_week'


def filter_completed_milestones(milestones_df: pd.DataFrame) -> pd.DataFrame:
    completed_mask = ~milestones_df['season'].isin(EXCLUDED_HIST_SEASONS)
    if 'peak_week' in milestones_df.columns:
        season_has_peak = milestones_df.groupby('season')['peak_week'].transform(lambda s: s.notna().any())
        completed_mask = completed_mask & season_has_peak
    return milestones_df[completed_mask].copy()


def resolve_state_coords(dim_state: pd.DataFrame = None) -> pd.DataFrame:
    if dim_state is not None and {'lat', 'lon'}.issubset(dim_state.columns):
        coord_df = dim_state[['state', 'lat', 'lon']].copy()
        coord_df['state_upper'] = coord_df['state'].str.upper()
        return coord_df[['state_upper', 'lat', 'lon']].drop_duplicates()

    coord_df = pd.DataFrame.from_dict(US_STATE_CENTROIDS, orient='index', columns=['lat', 'lon']).reset_index()
    coord_df.rename(columns={'index': 'state_upper'}, inplace=True)
    return coord_df


def _holm_adjust(p_raw: np.ndarray) -> np.ndarray:
    m = len(p_raw)
    if m == 0:
        return p_raw
    order = np.argsort(p_raw)
    sorted_p = p_raw[order]
    adj_sorted = np.minimum(1.0, np.maximum.accumulate(sorted_p * (m - np.arange(m))))
    adj = np.empty_like(adj_sorted)
    adj[order] = adj_sorted
    return adj


def run_dunn_posthoc(sub: pd.DataFrame, metric, group_col='hhs_region'):
    df = sub[[group_col, metric]].dropna().copy()
    df[metric] = pd.to_numeric(df[metric], errors='coerce')
    df = df.dropna(subset=[metric])
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
    res['p_adj_holm'] = np.round(_holm_adjust(res['p_raw'].to_numpy(dtype=float)), 6)
    res['p_raw'] = res['p_raw'].round(6)
    res['significant_005'] = res['p_adj_holm'] < 0.05

    return res


def run_hhs_comparisons(milestones_df: pd.DataFrame, dim_state: pd.DataFrame):
    onset_col = get_onset_week_col(milestones_df)
    merged = filter_completed_milestones(milestones_df).merge(
        dim_state[['state', 'hhs_region']], on='state', how='left'
    )

    metrics = [onset_col, 'peak_value']
    if 'peak_rate_flu' in merged.columns:
        metrics.append('peak_rate_flu')

    kw_results = []
    dunn_frames = []
    for metric in metrics:
        sub = merged.dropna(subset=[metric, 'hhs_region']).copy()
        sub[metric] = pd.to_numeric(sub[metric], errors='coerce')
        sub = sub.dropna(subset=[metric])

        if metric == 'peak_value':
            sub = sub[sub['source'] == 'ili']

        groups = [grp[metric].values for _, grp in sub.groupby('hhs_region') if len(grp) >= 3]
        if len(groups) > 2:
            stat, p_val = kruskal(*groups)
            is_sig = bool(p_val < 0.05)
            kw_results.append({
                'metric': metric,
                'n_obs': int(len(sub)),
                'test': "Kruskal-Wallis across HHS Regions",
                'statistic': round(float(stat), 4),
                'p_value': round(float(p_val), 6),
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
            'trend': 'Không đủ dữ liệu'
        }

    t = np.arange(n)
    res_mk = kendalltau(t, y)
    tau, p_val = float(res_mk.statistic), float(res_mk.pvalue)
    slope = float(theilslopes(y, t).slope)
    is_sig = bool(p_val < alpha)

    if is_sig:
        trend = 'Khởi phát muộn hơn' if tau > 0 else 'Khởi phát sớm hơn'
    else:
        trend = 'Không có xu hướng rõ rệt'

    return {
        'n_seasons': n,
        'tau': round(tau, 4),
        'p_value': round(p_val, 6),
        'sens_slope': round(slope, 4),
        'significant_005': is_sig,
        'trend': trend
    }


def run_onset_trend_mann_kendall(milestones_df: pd.DataFrame, alpha=0.05):
    onset_col = get_onset_week_col(milestones_df)
    sub = filter_completed_milestones(milestones_df)
    sub = sub[sub[onset_col].notna()].copy()
    sub[onset_col] = pd.to_numeric(sub[onset_col], errors='coerce')
    sub = sub[sub[onset_col].notna()].copy()
    sub['state_upper'] = sub['state'].str.upper()

    nat_season = (
        sub.groupby('season', as_index=False)
        .agg(
            median_onset=(onset_col, 'median'),
            mean_onset=(onset_col, 'mean'),
            n_states=('state_upper', 'nunique')
        )
        .sort_values('season')
    )

    nat_records = []
    for metric in ['median_onset', 'mean_onset']:
        res = mann_kendall_single(nat_season[metric].values, alpha=alpha)
        nat_records.append({
            'scope': 'Toàn quốc',
            'metric': metric,
            'first_season': nat_season['season'].iloc[0],
            'last_season': nat_season['season'].iloc[-1],
            **res
        })
    nat_mk_df = pd.DataFrame(nat_records)

    state_records = []
    for state, grp in sub.sort_values('season').groupby('state_upper'):
        res = mann_kendall_single(grp[onset_col].values, alpha=alpha)
        state_records.append({
            'state': state,
            'median_onset_all': round(float(grp[onset_col].median()), 2),
            **res
        })
    state_mk_df = pd.DataFrame(state_records)
    valid_p = state_mk_df['p_value'].notna()
    state_mk_df['p_adj_holm'] = np.nan
    if valid_p.any():
        state_mk_df.loc[valid_p, 'p_adj_holm'] = np.round(
            _holm_adjust(state_mk_df.loc[valid_p, 'p_value'].to_numpy(dtype=float)), 6
        )
    state_mk_df['significant_holm_005'] = (state_mk_df['p_adj_holm'] < alpha).fillna(False)
    state_mk_df['trend'] = np.where(
        state_mk_df['p_value'].isna(),
        'Không đủ dữ liệu',
        np.where(
            ~state_mk_df['significant_holm_005'],
            'Không có xu hướng rõ rệt',
            np.where(state_mk_df['tau'] > 0, 'Khởi phát muộn hơn', 'Khởi phát sớm hơn'),
        ),
    )
    state_mk_df = state_mk_df.sort_values('p_value').reset_index(drop=True)

    return nat_mk_df, state_mk_df


def infer_spread_direction(r_lat, p_lat, r_lon, p_lon, alpha=0.05):
    ns_dir = ""
    if p_lat < alpha:
        ns_dir = "Nam -> Bắc" if r_lat > 0 else "Bắc -> Nam"

    ew_dir = ""
    if p_lon < alpha:
        ew_dir = "Tây -> Đông" if r_lon > 0 else "Đông -> Tây"

    if ns_dir and ew_dir:
        return f"Lan chéo ({ns_dir} & {ew_dir})"
    if ns_dir:
        return f"Lan theo vĩ độ ({ns_dir})"
    if ew_dir:
        return f"Lan theo kinh độ ({ew_dir})"

    return "Không có hướng lan tuyến tính rõ rệt"


def run_spatial_onset_correlation(milestones_df: pd.DataFrame, dim_state: pd.DataFrame = None, alpha=0.05):
    onset_col = get_onset_week_col(milestones_df)
    sub = filter_completed_milestones(milestones_df)
    sub = sub[sub[onset_col].notna()].copy()
    sub[onset_col] = pd.to_numeric(sub[onset_col], errors='coerce')
    sub = sub[sub[onset_col].notna()].copy()
    sub['state_upper'] = sub['state'].str.upper()

    coord_df = resolve_state_coords(dim_state)
    sub = sub.merge(coord_df, on='state_upper', how='inner')

    state_agg = (
        sub.groupby(['state_upper', 'lat', 'lon'], as_index=False)
        .agg(
            median_onset=(onset_col, 'median'),
            mean_onset=(onset_col, 'mean'),
            n_seasons=('season', 'count')
        )
    )

    overall_records = []
    subsets = {
        'Toàn bộ 51 bang/đặc khu': state_agg,
        '49 bang lục địa (bỏ AK, HI)': state_agg[~state_agg['state_upper'].isin(['AK', 'HI'])]
    }

    for scope_name, df_scope in subsets.items():
        for metric in ['median_onset', 'mean_onset']:
            r_lat_s, p_lat_s = spearmanr(df_scope['lat'], df_scope[metric])
            r_lon_s, p_lon_s = spearmanr(df_scope['lon'], df_scope[metric])
            r_lat_p, p_lat_p = pearsonr(df_scope['lat'], df_scope[metric])
            r_lon_p, p_lon_p = pearsonr(df_scope['lon'], df_scope[metric])

            overall_records.append({
                'scope': scope_name,
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
        if len(grp) < 10 or grp[onset_col].nunique() < 2:
            continue

        r_lat, p_lat = spearmanr(grp['lat'], grp[onset_col])
        r_lon, p_lon = spearmanr(grp['lon'], grp[onset_col])
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
