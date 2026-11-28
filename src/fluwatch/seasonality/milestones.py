import numpy as np
import pandas as pd


SEVERITY_FIRST_SEASON = '2021-22'
EXCLUDED_HIST_SEASONS = ('2009-10', '2020-21')
MIN_COMPLETED_SEASON_WEEK = 34  # het mua cum CDC (MMWR tuan 21 tro di)
COVID_1920_MAX_SEASON_WEEK = 24  # tuan ket thuc 2020-03-14, truoc song COVID-19 dau tien lam nhieu ILI
NON_FLU_LAB_THRESHOLD = 2.0
CDC_LEVEL_NAMES = ['rat_thap', 'thap', 'trung_binh', 'cao', 'rat_cao']


def get_completed_seasons(df: pd.DataFrame) -> set:
    """Xac dinh dong cac mua da hoan tat dua tren du lieu khong so bo."""
    work = df[~df['is_preliminary'].fillna(False)] if 'is_preliminary' in df.columns else df
    max_sw = work.groupby('season')['season_week'].max()
    return {
        s for s, sw in max_sw.items()
        if s not in EXCLUDED_HIST_SEASONS and pd.notna(sw) and sw >= MIN_COMPLETED_SEASON_WEEK
    }


def mask_sparse_ili(df: pd.DataFrame, max_missing_ratio=0.3):
    df = df.copy()
    missing_ratio = df.groupby(['state', 'season'])['ili_pct'].transform(lambda s: s.isna().mean())
    df.loc[missing_ratio > max_missing_ratio, 'ili_pct'] = np.nan
    return df


def prepare_signal(df: pd.DataFrame, max_missing_ratio=0.3):
    df = mask_sparse_ili(df, max_missing_ratio=max_missing_ratio)
    df['signal_value'] = np.nan
    df['source'] = pd.Series(pd.NA, index=df.index, dtype='string')

    has_ili = df.groupby(['state', 'season'])['ili_pct'].transform(lambda s: s.notna().any())
    df.loc[has_ili, 'signal_value'] = df.loc[has_ili, 'ili_pct']
    df.loc[has_ili, 'source'] = 'ili'

    has_nssp = (~has_ili) & df.groupby(['state', 'season'])['ed_pct_flu'].transform(
        lambda s: s.notna().any() and s.isna().mean() <= max_missing_ratio
    )
    df.loc[has_nssp, 'signal_value'] = df.loc[has_nssp, 'ed_pct_flu']
    df.loc[has_nssp, 'source'] = 'nssp'

    if 'rate_flu' in df.columns:
        has_nhsn = (~has_ili) & (~has_nssp) & df.groupby(['state', 'season'])['rate_flu'].transform(
            lambda s: s.notna().any() and s.isna().mean() <= max_missing_ratio
        ) & (df['season'] >= SEVERITY_FIRST_SEASON)
        df.loc[has_nhsn, 'signal_value'] = df.loc[has_nhsn, 'rate_flu']
        df.loc[has_nhsn, 'source'] = 'nhsn'

    return df


def get_non_flu_mask(df: pd.DataFrame, lab_threshold=2, min_consec=3, smooth_window=3):
    smooth_lab = df['lab_pct_pos'].rolling(window=smooth_window, center=True, min_periods=1).median()
    below = (smooth_lab < lab_threshold).fillna(False)

    run_id = (~below).cumsum()
    run_lengths = below.groupby(run_id).transform('sum')

    return below & (run_lengths >= min_consec)


def compute_baselines(df: pd.DataFrame, lab_threshold=2, min_consec=3, smooth_window=3):
    work = df[~df['is_preliminary'].fillna(False)] if 'is_preliminary' in df.columns else df
    work = work.sort_values(['state', 'season', 'season_week']).copy()
    seasons = sorted(work['season'].unique())

    col_by_source = {'ili': 'ili_pct', 'nssp': 'ed_pct_flu', 'nhsn': 'rate_flu'}
    records = []
    for (state, season), grp in work.groupby(['state', 'season'], sort=False):
        source = grp['source'].iloc[0]

        if season in EXCLUDED_HIST_SEASONS or pd.isna(source):
            records.append({
                'state': state,
                'season': season,
                'baseline': np.nan
            })
            continue

        prev_candidates = [s for s in seasons if s < season and s not in EXCLUDED_HIST_SEASONS]
        val_col = col_by_source.get(source, 'ili_pct')

        valid_samples = []
        for ps in reversed(prev_candidates):
            s_grp = work[(work['state'] == state) & (work['season'] == ps)]

            lab_mask = get_non_flu_mask(s_grp, lab_threshold, min_consec, smooth_window)
            s_vals = s_grp.loc[lab_mask, val_col].dropna()

            if len(s_vals) <= 5:
                cal_mask = s_grp['season_week'] >= 34
                s_vals = s_grp.loc[cal_mask, val_col].dropna()

            if len(s_vals) > 5:
                valid_samples.append(s_vals)

            if len(valid_samples) == 3:
                break

        if valid_samples:
            sub = pd.concat(valid_samples)
            baseline = sub.mean() + 2 * sub.std(ddof=1)
        else:
            baseline = np.nan

        records.append({
            'state': state,
            'season': season,
            'baseline': baseline
        })

    return pd.DataFrame(records)


def _severity_label(grp: pd.DataFrame):
    valid_rate = grp['rate_flu'].dropna()
    if valid_rate.empty:
        return pd.NA
    peak_idx = valid_rate.idxmax()
    if 'cdc_level_name' in grp.columns and pd.notna(grp.loc[peak_idx, 'cdc_level_name']):
        return str(grp.loc[peak_idx, 'cdc_level_name'])
    if 'cdc_level' in grp.columns and pd.notna(grp.loc[peak_idx, 'cdc_level']):
        lvl = int(grp.loc[peak_idx, 'cdc_level'])
        if 0 <= lvl < len(CDC_LEVEL_NAMES):
            return CDC_LEVEL_NAMES[lvl]
    return pd.NA


def detect_season_milestones(df: pd.DataFrame):
    df_full = prepare_signal(df)
    df_full['week'] = pd.to_datetime(df_full['week'])
    df_conf = df_full[~df_full['is_preliminary'].fillna(False)].copy() if 'is_preliminary' in df_full.columns else df_full.copy()

    completed_seasons = get_completed_seasons(df_conf)
    baselines = compute_baselines(df_conf)
    df_conf = df_conf.merge(baselines, on=['state', 'season'], how='left')
    nat_lab = (
        df_conf.groupby(['season', 'season_week'])['lab_pct_pos']
        .median()
        .rename('_nat_lab_pct_pos')
    )
    df_conf = df_conf.merge(nat_lab, on=['season', 'season_week'], how='left')

    summary_rows = []
    for (state, season), grp in df_conf.groupby(['state', 'season'], sort=False):
        grp = grp.sort_values('season_week').copy()
        baseline = grp['baseline'].iloc[0]
        source = grp['source'].iloc[0]

        milestone_grp = grp[grp['season_week'] <= COVID_1920_MAX_SEASON_WEEK] if season == '2019-20' else grp
        values = milestone_grp['signal_value'].values
        season_weeks = milestone_grp['season_week'].values
        week_dates = milestone_grp['week'].values

        if pd.notna(source) and source == 'ili':
            st_lab = milestone_grp['lab_pct_pos'].to_numpy(dtype=float)
            na_lab = milestone_grp['_nat_lab_pct_pos'].to_numpy(dtype=float)
            both_na = np.isnan(st_lab) & np.isnan(na_lab)
            flu_ok = (
                both_na
                | (np.nan_to_num(st_lab, nan=-1.0) >= NON_FLU_LAB_THRESHOLD)
                | (np.nan_to_num(na_lab, nan=-1.0) >= NON_FLU_LAB_THRESHOLD)
            )
        else:
            flu_ok = np.ones(len(milestone_grp), dtype=bool)

        onset_season_week = pd.NA
        onset_week = pd.NaT
        if not np.isnan(baseline):
            above = (values >= baseline).astype(int)
            for i in range(len(above) - 2):
                if above[i] == 1 and above[i + 1] == 1 and above[i + 2] == 1 and np.any(flu_ok[i:i + 3]):
                    onset_season_week = int(season_weeks[i])
                    onset_week = pd.Timestamp(week_dates[i])
                    break

        is_completed = season in completed_seasons
        valid_peak = milestone_grp[milestone_grp['signal_value'].notna() & flu_ok]
        if valid_peak.empty:
            valid_peak = milestone_grp[milestone_grp['signal_value'].notna()]
        if is_completed and not valid_peak.empty:
            peak_idx = valid_peak['signal_value'].idxmax()
            peak_value = round(float(valid_peak.loc[peak_idx, 'signal_value']), 4)
            peak_season_week = int(valid_peak.loc[peak_idx, 'season_week'])
            peak_week = pd.Timestamp(valid_peak.loc[peak_idx, 'week'])
        else:
            peak_value = np.nan
            peak_season_week = pd.NA
            peak_week = pd.NaT

        has_nhsn = season >= SEVERITY_FIRST_SEASON and grp['rate_flu'].notna().any()
        if is_completed and has_nhsn:
            peak_rate_flu = round(float(grp['rate_flu'].max()), 4)
            severity = _severity_label(grp)
        else:
            peak_rate_flu = np.nan
            severity = pd.NA

        summary_rows.append({
            'state': state,
            'season': season,
            'source': source if pd.notna(source) else pd.NA,
            'baseline': round(float(baseline), 4) if not np.isnan(baseline) else np.nan,
            'onset_week': onset_week,
            'peak_week': peak_week,
            'peak_value': peak_value,
            'severity': severity,
            'onset_season_week': onset_season_week,
            'peak_season_week': peak_season_week,
            'peak_rate_flu': peak_rate_flu,
        })

    all_pairs = df_full[['state', 'season']].drop_duplicates()
    season_milestones = all_pairs.merge(pd.DataFrame(summary_rows), on=['state', 'season'], how='left')
    season_milestones['state'] = season_milestones['state'].astype('string')
    season_milestones['season'] = season_milestones['season'].astype('string')
    season_milestones['source'] = season_milestones['source'].astype('string')
    season_milestones['severity'] = season_milestones['severity'].astype('string')
    season_milestones['onset_week'] = pd.to_datetime(season_milestones['onset_week'])
    season_milestones['peak_week'] = pd.to_datetime(season_milestones['peak_week'])
    season_milestones['onset_season_week'] = pd.to_numeric(season_milestones['onset_season_week'], errors='coerce').astype('Int64')
    season_milestones['peak_season_week'] = pd.to_numeric(season_milestones['peak_season_week'], errors='coerce').astype('Int64')
    season_milestones = season_milestones.sort_values(['state', 'season']).reset_index(drop=True)

    phase_input = df_full.merge(
        season_milestones[['state', 'season', 'baseline', 'onset_season_week', 'peak_season_week']],
        on=['state', 'season'],
        how='left'
    )
    phase_frames = []
    for (state, season), grp in phase_input.groupby(['state', 'season'], sort=False):
        grp = grp.sort_values('season_week').copy()
        baseline = grp['baseline'].iloc[0]
        onset_sw = grp['onset_season_week'].iloc[0]
        peak_sw = grp['peak_season_week'].iloc[0]
        is_completed = season in completed_seasons

        phases = []
        for sw in grp['season_week'].values:
            if pd.isna(baseline):
                phases.append(pd.NA)
            elif pd.isna(onset_sw) or sw < onset_sw:
                phases.append("chua_bat_dau")
            elif not is_completed:
                phases.append("dang_len")
            elif pd.notna(peak_sw) and sw == peak_sw:
                phases.append("dinh")
            elif pd.notna(peak_sw) and sw < peak_sw:
                phases.append("dang_len")
            else:
                phases.append("dang_giam")

        grp['season_phase'] = pd.Series(phases, index=grp.index, dtype='string')
        grp['ili_tren_muc_nen'] = np.where(
            (grp['source'] == 'ili').fillna(False),
            (grp['ili_pct'] - grp['baseline']).round(4),
            np.nan
        )
        phase_frames.append(
            grp[['state', 'week', 'epiweek', 'season', 'season_week', 'baseline', 'ili_tren_muc_nen', 'season_phase']]
        )

    season_phase_df = pd.concat(phase_frames, ignore_index=True).sort_values(['state', 'week']).reset_index(drop=True)
    return season_milestones, season_phase_df
