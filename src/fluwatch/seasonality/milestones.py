import numpy as np
import pandas as pd


def prepare_signal(df: pd.DataFrame):
    df = df.copy()
    df['signal_value'] = df['ili_pct']
    df['signal_source'] = 'ILINet'

    missing_mask = df.groupby(['state', 'season'])['ili_pct'].transform(lambda s: s.isna().all())
    df.loc[missing_mask, 'signal_value'] = df.loc[missing_mask, 'ed_pct_flu']
    df.loc[missing_mask, 'signal_source'] = 'NSSP'

    return df

def compute_baselines(df: pd.DataFrame):
    df = df.sort_values(['state', 'season', 'season_week']).copy()
    seasons = sorted(df['season'].unique())
    off_mask = (df['season_week'] >= 34) | (df['season_week'] <= 3)

    records = []
    for (state, season), grp in df.groupby(['state', 'season'], sort=False):
        source = grp['signal_source'].iloc[0]

        if season == '2009-10':
            records.append({
                'state': state,
                'season': season,
                'baseline': np.nan
            })

        if source == 'NSSP':
            sub = df[(df['state'] == state) & (df['season'] != '2020-21') & off_mask]['ed_pct_flu'].dropna()
        else:
            prev_candidates = [s for s in seasons if s < season and s not in ('2009-10', '2020-21')]
            valid_prev_seasons = []
            for ps in reversed(prev_candidates):
                s_vals = df[(df['state'] == state) & (df['season'] == ps) & off_mask]['ili_pct'].dropna()
                if len(s_vals) > 5:
                    valid_prev_seasons.append(ps)
                if len(valid_prev_seasons) == 3:
                    break

            sub = df[(df['state'] == state) & (df['season'].isin(valid_prev_seasons) & off_mask)]['ili_pct'].dropna()
            if len(sub) < 10:
                sub = df[(df['state'] == state) & (~df['season'].isin(['2009-10', '2020-21', '2026-27'])) & off_mask]['ili_pct'].dropna()

        baseline = sub.mean() + 2 * sub.std(ddof=1) if len(sub) > 3 else np.nan
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

        onset_week = np.nan
        if not np.isnan(baseline):
            above = (values >= baseline).astype(int)
            for i in range(len(above) - 2):
                if above[i] == 1 and above[i + 1] == 1 and above[i + 2] == 1:
                    onset_week = weeks[i]
                    break

        if grp['signal_value'].notna().any():
            peak_idx = grp['signal_value'].idxmax()
            peak_value = grp.loc[peak_idx, 'signal_value']
            peak_week = grp.loc[peak_idx, 'season_week']
        else:
            peak_value = np.nan
            peak_week = np.nan

        phases = []
        for week in weeks:
            if np.isnan(onset_week) or week < onset_week:
                phases.append("Not started")
            elif not np.isnan(peak_week) and week == peak_week:
                phases.append("Peak")
            elif not np.isnan(peak_week) and week < peak_week:
                phases.append("Rising")
            else:
                phases.append("Declining")

        grp['season_phase'] = phases
        phase_frames.append(grp[['state', 'epiweek', 'season', 'season_week', 'baseline', 'season_phase']])

        summary_rows.append({
            'state': state,
            'season': season,
            'signal_source': grp['signal_source'].iloc[0],
            'baseline': round(baseline, 4) if not np.isnan(baseline) else np.nan,
            'onset_week': onset_week,
            'peak_value': round(peak_value, 4) if not np.isnan(peak_value) else np.nan,
            'peak_week': peak_week
        })

    season_milestones = pd.DataFrame(summary_rows)
    season_phase_df = pd.concat(phase_frames, ignore_index=True)

    return season_milestones, season_phase_df
