import numpy as np
import pandas as pd

# severity = dinh rate_flu (NHSN). NHSN du 51 bang tu 2020-21 (mua bi loai); 2019-20 chi 8 bang -> chi tinh tu mua nay
SEVERITY_FIRST_SEASON = '2021-22'


def mask_sparse_ili(df: pd.DataFrame, max_missing_ratio=0.3):
    df = df.copy()
    missing_ratio = df.groupby(['state', 'season'])['ili_pct'].transform(lambda s: s.isna().mean())
    df.loc[missing_ratio > max_missing_ratio, 'ili_pct'] = np.nan
    return df

def prepare_signal(df: pd.DataFrame, max_missing_ratio=0.3):
    df = mask_sparse_ili(df, max_missing_ratio=max_missing_ratio)
    df['signal_value'] = np.nan
    df['source'] = pd.Series(np.nan, index=df.index, dtype='object')

    has_ili = df.groupby(['state', 'season'])['ili_pct'].transform(lambda s: s.notna().any())
    df.loc[has_ili, 'signal_value'] = df.loc[has_ili, 'ili_pct']
    df.loc[has_ili, 'source'] = 'ili'

    has_nssp = (~has_ili) & df.groupby(['state', 'season'])['ed_pct_flu'].transform(lambda s: s.notna().any() and s.isna().mean() <= max_missing_ratio)
    df.loc[has_nssp, 'signal_value'] = df.loc[has_nssp, 'ed_pct_flu']
    df.loc[has_nssp, 'source'] = 'nssp'

    return df

def compute_baselines(df: pd.DataFrame):
    df = df.sort_values(['state', 'season', 'season_week']).copy()
    seasons = sorted(df['season'].unique())
    off_mask = (df['season_week'] >= 34) | (df['season_week'] <= 3)

    records = []
    for (state, season), grp in df.groupby(['state', 'season'], sort=False):
        source = grp['source'].iloc[0]

        if season in ('2009-10', '2020-21') or pd.isna(source):
            records.append({
                'state': state,
                'season': season,
                'baseline': np.nan
            })
            continue

        prev_candidates = [s for s in seasons if s < season and s not in ('2009-10', '2020-21')]
        val_col = 'ili_pct' if source == 'ili' else 'ed_pct_flu'

        valid_prev_seasons = []
        for ps in reversed(prev_candidates):
            s_vals = df[(df['state'] == state) & (df['season'] == ps) & off_mask][val_col].dropna()
            if len(s_vals) > 5:
                valid_prev_seasons.append(ps)
            if len(valid_prev_seasons) == 3:
                break

        sub = df[(df['state'] == state) & (df['season'].isin(valid_prev_seasons)) & off_mask][val_col].dropna()
        baseline = sub.mean() + 2 * sub.std(ddof=1) if len(valid_prev_seasons) > 0 else np.nan
        records.append({
            'state': state,
            'season': season,
            'baseline': baseline
        })

    return pd.DataFrame(records)

def detect_season_milestones(df: pd.DataFrame):
    df = prepare_signal(df)
    baselines = compute_baselines(df)
    df = df.merge(baselines, on=['state', 'season'], how='left')

    summary_rows = []
    phase_frames = []
    for (state, season), grp in df.groupby(['state', 'season'], sort=False):
        grp = grp.sort_values('season_week').copy()
        values = grp['signal_value'].values
        weeks = grp['season_week'].values
        baseline = grp['baseline'].iloc[0]
        source = grp['source'].iloc[0]

        onset_week = np.nan
        if not np.isnan(baseline):
            above = (values >= baseline).astype(int)
            for i in range(len(above) - 2):
                if above[i] == 1 and above[i + 1] == 1 and above[i + 2] == 1:
                    onset_week = weeks[i]
                    break

        is_completed = season not in ('2009-10', '2020-21', '2026-27')
        if is_completed and grp['signal_value'].notna().any():
            peak_idx = grp['signal_value'].idxmax()
            peak_value = grp.loc[peak_idx, 'signal_value']
            peak_week = grp.loc[peak_idx, 'season_week']
        else:
            peak_value = np.nan
            peak_week = np.nan

        has_nhsn = season >= SEVERITY_FIRST_SEASON and grp['rate_flu'].notna().any()
        severity = grp['rate_flu'].max() if is_completed and has_nhsn else np.nan

        phases = []
        for week in weeks:
            if np.isnan(baseline):
                phases.append(np.nan)
            elif np.isnan(onset_week) or week < onset_week:
                phases.append("chua_bat_dau")
            elif season == '2026-27':
                phases.append("dang_len")
            elif not np.isnan(peak_week) and week == peak_week:
                phases.append("dinh")
            elif not np.isnan(peak_week) and week < peak_week:
                phases.append("dang_len")
            else:
                phases.append("dang_giam")

        grp['season_phase'] = phases
        # ILI tru muc nen (khac ili_anomaly cua TV4 = ILI tru trung binh cung tuan qua cac nam)
        grp['ili_tren_muc_nen'] = (grp['ili_pct'] - grp['baseline']).round(4)

        phase_frames.append(grp[['state', 'week', 'epiweek', 'season', 'season_week', 'baseline', 'ili_tren_muc_nen', 'season_phase']])

        summary_rows.append({
            'state': state,
            'season': season,
            'source': source,
            'baseline': round(baseline, 4) if not np.isnan(baseline) else np.nan,
            'onset_week': onset_week,
            'peak_week': peak_week,
            'peak_value': round(peak_value, 4) if not np.isnan(peak_value) else np.nan,
            'severity': round(severity, 4) if not np.isnan(severity) else np.nan
        })

    season_milestones = pd.DataFrame(summary_rows)
    season_phase_df = pd.concat(phase_frames, ignore_index=True)

    return season_milestones, season_phase_df
