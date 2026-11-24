"""Moc mua cua TV3: muc nen, tuan khoi phat, tuan dinh, do nang, giai doan mua.

Dinh nghia (ke_hoach.md muc 10):
- Muc nen = trung binh + 2 do lech chuan cua cac tuan ngoai mua (season_week >= 34 hoac <= 3) trong 3 mua truoc
  co du so lieu, bo 2009-10 va 2020-21.
- Tuan khoi phat = tuan dau cua chuoi 3 tuan lien tiep tin hieu >= muc nen, VA (tu mua 2016-17) tuan do co xet
  nghiem duong tinh cum lab_pct_pos >= 2%. Bang thieu so xet nghiem tuan do thi lay trung vi cac bang cung vung HHS.
  Ly do: sau COVID, ILI ngoai mua tang (COVID, RSV) du khong co cum, nen chi dung ILI se ra khoi phat gia o tuan 40.
- onset_week, peak_week la so tuan trong mua (season_week, 1 = tuan MMWR 40); onset_date, peak_date la ngay thu Bay
  ket thuc tuan do (de hien thi).
"""
import numpy as np
import pandas as pd

# Dieu kien xet nghiem: so lieu xet nghiem cap bang day du tu mua 2016-17
LAB_MIN_PCT = 2.0
LAB_FIRST_SEASON = '2016-17'

# severity = dinh rate_flu (NHSN). NHSN du 51 bang tu 2020-21 (mua bi loai); 2019-20 chi 8 bang -> chi tinh tu mua nay
SEVERITY_FIRST_SEASON = '2021-22'


def mask_sparse_ili(df: pd.DataFrame, max_missing_ratio=0.3):
    df = df.copy()
    missing_ratio = df.groupby(['state', 'season'])['ili_pct'].transform(lambda s: s.isna().mean())
    df.loc[missing_ratio > max_missing_ratio, 'ili_pct'] = np.nan
    return df

def lab_with_region_fill(df: pd.DataFrame, dim_state: pd.DataFrame | None = None) -> pd.Series:
    """lab_pct_pos; o thieu lay trung vi cac bang cung vung HHS trong cung tuan."""
    if dim_state is None:
        from fluwatch.warehouse.load import load_dim_state
        dim_state = load_dim_state()
    region = df['state'].map(dim_state.set_index('state')['hhs_region'])
    lab = pd.to_numeric(df['lab_pct_pos'], errors='coerce')
    med = lab.groupby([region, df['week']]).transform('median')
    return lab.fillna(med)


def prepare_signal(df: pd.DataFrame, max_missing_ratio=0.3, dim_state: pd.DataFrame | None = None):
    df = mask_sparse_ili(df, max_missing_ratio=max_missing_ratio)
    df['lab_eff'] = lab_with_region_fill(df, dim_state)
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

def first_onset(values, lab, need_lab):
    """Chi so tuan dau cua 3 tuan lien tiep >= muc nen (values da la bool); need_lab: tuan do phai co xet nghiem >= 2%."""
    for i in range(len(values) - 2):
        if values[i] and values[i + 1] and values[i + 2]:
            if need_lab and not (np.isnan(lab[i]) or lab[i] >= LAB_MIN_PCT):
                continue
            return i
    return None


def detect_season_milestones(df: pd.DataFrame, dim_state: pd.DataFrame | None = None):
    df = prepare_signal(df, dim_state=dim_state)
    baselines = compute_baselines(df)
    df = df.merge(baselines, on=['state', 'season'], how='left')

    current = df['season'].max()  # mua dang dien ra: chua co dinh, giai doan sau khoi phat la dang_len
    summary_rows = []
    phase_frames = []
    for (state, season), grp in df.groupby(['state', 'season'], sort=False):
        grp = grp.sort_values('season_week').copy()
        values = grp['signal_value'].values
        weeks = grp['season_week'].values
        baseline = grp['baseline'].iloc[0]
        source = grp['source'].iloc[0]

        onset_week, onset_date, onset_lab = np.nan, pd.NaT, np.nan
        if not np.isnan(baseline):
            i = first_onset(values >= baseline, grp['lab_eff'].to_numpy(dtype=float), season >= LAB_FIRST_SEASON)
            if i is not None:
                onset_week, onset_date = weeks[i], grp['week'].iloc[i]
                onset_lab = grp['lab_eff'].iloc[i]

        is_completed = season not in ('2009-10', '2020-21', current)
        if is_completed and grp['signal_value'].notna().any():
            peak_idx = grp['signal_value'].idxmax()
            peak_value = grp.loc[peak_idx, 'signal_value']
            peak_week = grp.loc[peak_idx, 'season_week']
            peak_date = grp.loc[peak_idx, 'week']
        else:
            peak_date = pd.NaT
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
            elif season == current:
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
            'onset_date': onset_date,
            'onset_lab_pct_pos': round(onset_lab, 2) if not np.isnan(onset_lab) else np.nan,
            'peak_week': peak_week,
            'peak_date': peak_date,
            'peak_value': round(peak_value, 4) if not np.isnan(peak_value) else np.nan,
            'severity': round(severity, 4) if not np.isnan(severity) else np.nan
        })

    season_milestones = pd.DataFrame(summary_rows)
    season_phase_df = pd.concat(phase_frames, ignore_index=True)

    return season_milestones, season_phase_df
