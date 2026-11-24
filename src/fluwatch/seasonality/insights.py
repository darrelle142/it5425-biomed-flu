"""Cac phat hien them cua TV3 (RQ1-RQ3), dung lai moc mua cua milestones.py.

1. signal_lead: tin hieu nao bao som nhat. Voi moi bang-mua co du 5 tin hieu (2022-23 -> 2025-26), tuan moi tin hieu
   dat 50% dinh cua chinh no trong mua; so voi nhap vien (NHSN). Wilcoxon cho do lech tung bang-mua.
   Dung "nua dinh" thay vi muc nen vi moi tin hieu co thang do va muc nen khac nhau.
2. season_progress: mua dang dien ra som hay muon - so bang da khoi phat (da xac nhan) den cung tuan mua, so voi
   cac mua tu 2016-17 (cung dinh nghia khoi phat co xet nghiem).
3. spread_direction: huong lan - tuong quan Spearman giua thu hang khoi phat trong mua va vi do/kinh do
   (48 bang luc dia + DC, gop cac mua; kem tung mua).
4. onset_trend: xu huong tuan khoi phat qua cac mua (Mann-Kendall = Kendall tau voi thu tu mua).
"""
import numpy as np
import pandas as pd
from scipy.stats import kendalltau, spearmanr, wilcoxon

SIGNALS = {'ili_pct': 'ILI (khám ngoại trú)', 'lab_pct_pos': 'Xét nghiệm dương tính',
           'ed_pct_flu': 'Cấp cứu (NSSP)', 'wval_mean': 'Nước thải (WVAL)', 'rate_flu': 'Nhập viện (NHSN)'}
REFERENCE = 'rate_flu'
LEAD_SEASONS = ['2022-23', '2023-24', '2024-25', '2025-26']   # mua co du ca 5 tin hieu
HISTORY_FROM = '2016-17'                                       # dieu kien xet nghiem ap dung tu mua nay
EXCLUDED = ['2009-10', '2010-11', '2020-21']


def half_peak_weeks(df: pd.DataFrame, seasons=LEAD_SEASONS, max_missing=0.3) -> pd.DataFrame:
    rows = []
    for (state, season), g in df[df['season'].isin(seasons)].groupby(['state', 'season']):
        g = g.sort_values('season_week')
        r = {'state': state, 'season': season}
        for c in SIGNALS:
            x = pd.to_numeric(g[c], errors='coerce').to_numpy(float)
            if np.isnan(x).mean() > max_missing or np.nanmax(x) <= 0:
                r[c] = np.nan
                continue
            hit = np.flatnonzero(x >= 0.5 * np.nanmax(x))
            r[c] = g['season_week'].to_numpy()[hit[0]]
        rows.append(r)
    return pd.DataFrame(rows)


def signal_lead(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(bang tom tat theo tin hieu, bang tuan nua dinh tung bang-mua). lead > 0: tin hieu di truoc nhap vien."""
    h = half_peak_weeks(df)
    out = []
    for c, name in SIGNALS.items():
        if c == REFERENCE:
            continue
        d = (h[REFERENCE] - h[c]).dropna()
        nz = d[d != 0]
        out.append({'signal': c, 'ten': name, 'n': len(d), 'lead_median': float(d.median()),
                    'lead_mean': float(d.mean()), 'share_earlier': float((d > 0).mean()),
                    'share_same': float((d == 0).mean()),
                    'p_wilcoxon': float(wilcoxon(nz).pvalue) if len(nz) > 10 else np.nan})
    return pd.DataFrame(out).sort_values('lead_mean', ascending=False).reset_index(drop=True), h


def season_progress(milestones: pd.DataFrame, df: pd.DataFrame) -> dict:
    """So bang da khoi phat (da du 3 tuan xac nhan) den tuan mua hien tai, mua nay so voi cac mua truoc."""
    current = df['season'].max()
    last = int(df.loc[df['season'] == current, 'season_week'].max())
    confirmed_by = last - 2                       # khoi phat o tuan w can so lieu den w + 2
    hist = milestones[(milestones['season'] >= HISTORY_FROM) & ~milestones['season'].isin(EXCLUDED + [current])]
    per_season = hist.groupby('season')['onset_week'].apply(lambda s: int((s <= confirmed_by).sum()))
    now = int((milestones.loc[milestones['season'] == current, 'onset_week'] <= confirmed_by).sum())
    return {'season': current, 'last_season_week': last, 'onset_confirmed_by_week': confirmed_by,
            'states_onset_now': now, 'history': per_season.to_dict(),
            'history_median': float(per_season.median()),
            'rank_earliest': int((per_season > now).sum() + 1), 'n_seasons_compared': int(len(per_season) + 1)}


def spread_direction(milestones: pd.DataFrame, dim_state: pd.DataFrame) -> dict:
    x = milestones[~milestones['season'].isin(EXCLUDED) & (milestones['season'] < milestones['season'].max())]
    x = x.merge(dim_state[['state', 'lat', 'lon', 'contiguous']], on='state')
    x = x[x['contiguous'].astype(bool)].dropna(subset=['onset_week']).copy()
    x['onset_rank'] = x.groupby('season')['onset_week'].rank(pct=True)
    lat, lon = spearmanr(x['onset_rank'], x['lat']), spearmanr(x['onset_rank'], x['lon'])
    per = x.groupby('season').apply(lambda g: spearmanr(g['onset_week'], g['lat'])[0], include_groups=False)
    return {'n': int(len(x)), 'rho_lat': float(lat[0]), 'p_lat': float(lat[1]), 'rho_lon': float(lon[0]),
            'p_lon': float(lon[1]), 'seasons_rho_lat_positive': int((per > 0).sum()), 'n_seasons': int(len(per)),
            'rho_lat_by_season': {k: round(float(v), 3) for k, v in per.items()}}


def onset_trend(milestones: pd.DataFrame) -> dict:
    x = milestones[~milestones['season'].isin(EXCLUDED) & (milestones['season'] < milestones['season'].max())]
    nat = x.groupby('season')['onset_week'].median()
    tau = kendalltau(np.arange(len(nat)), nat.to_numpy())
    return {'tau': float(tau.statistic), 'p_value': float(tau.pvalue),
            'median_onset_by_season': {k: float(v) for k, v in nat.items()}}
