"""Phan cum bang theo hinh dang duong cong mua cum (TV3, RQ3).

Cach lam:
- Moi bang-mua (bo 2009-10, 2020-21, mua dang dien ra) co du >= 45 tuan ILI: chuan hoa z-score theo chinh mua do
  (bo khac biet muc ILI giua cac bang va giua cac mua, chi giu hinh dang: len som/muon, nhon/bet).
- Duong cong dai dien cua bang = trung binh cac mua; bang co < MIN_SEASONS mua bi bo (FL chi co 5 mua ILINet).
- Ward tren duong cong dai dien; chon k bang silhouette (k = 2..6); doi chieu k-means (chi so Rand hieu chinh).
- Kiem tra dia ly: phan cum KHONG dung toa do, nen neu cac cum gan nhau ve dia ly hon ngau nhien thi do la dau hieu
  hinh dang mua cum co tinh vung (permutation test: bang va 3 bang gan nhat co cung cum khong; 48 bang luc dia + DC).
"""
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import fcluster, linkage
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score, silhouette_score

EXCLUDE_SEASONS = ['2009-10', '2020-21']
MIN_WEEKS = 45
MIN_SEASONS = 6
N_PERM = 5000


def state_curves(df: pd.DataFrame) -> pd.DataFrame:
    current = df['season'].max()
    v = df[~df['season'].isin(EXCLUDE_SEASONS + [current]) & (df['season_week'] <= 52)].dropna(subset=['ili_pct'])
    v = v[v.groupby(['state', 'season'])['ili_pct'].transform('size') >= MIN_WEEKS].copy()
    g = v.groupby(['state', 'season'])['ili_pct']
    v['z'] = (v['ili_pct'] - g.transform('mean')) / g.transform('std')
    n_seasons = v.groupby('state')['season'].nunique()
    v = v[v['state'].isin(n_seasons[n_seasons >= MIN_SEASONS].index)]
    curves = v.pivot_table(index='state', columns='season_week', values='z', aggfunc='mean')
    return curves.interpolate(axis=1, limit_direction='both')


def _haversine_km(lat, lon):
    la, lo = np.radians(lat)[:, None], np.radians(lon)[:, None]
    a = np.sin((la - la.T) / 2) ** 2 + np.cos(la) * np.cos(la.T) * np.sin((lo - lo.T) / 2) ** 2
    return 2 * 6371 * np.arcsin(np.sqrt(a))


def geographic_coherence(labels: np.ndarray, lat: np.ndarray, lon: np.ndarray, k_nn=3, seed=2026) -> dict:
    """Ty le cap (bang, 1 trong k_nn bang gan nhat) cung cum, so voi gan nhan ngau nhien giu nguyen kich thuoc cum.

    Giong kiem dinh join-count cho tu tuong quan khong gian: cao hon ngau nhien = cum co tinh vung.
    """
    d = _haversine_km(lat, lon)
    np.fill_diagonal(d, np.inf)
    nn = np.argsort(d, axis=1)[:, :k_nn]

    def agree(lab):
        return float((lab[nn] == lab[:, None]).mean())

    obs = agree(labels)
    rng = np.random.default_rng(seed)
    null = np.array([agree(rng.permutation(labels)) for _ in range(N_PERM)])
    return {'k_nn': k_nn, 'same_cluster_share': obs, 'null_share': float(null.mean()),
            'p_value': float((np.sum(null >= obs) + 1) / (N_PERM + 1))}


def cluster_states(df: pd.DataFrame, k_range: range = range(2, 7), dim_state: pd.DataFrame | None = None):
    curves = state_curves(df)
    X = curves.values
    Z = linkage(X, method='ward')

    scores = {k: round(float(silhouette_score(X, fcluster(Z, t=k, criterion='maxclust'))), 4) for k in k_range}
    best_k = max(scores, key=scores.get)
    labels = fcluster(Z, t=best_k, criterion='maxclust')
    km = KMeans(n_clusters=best_k, random_state=42, n_init=10).fit_predict(X) + 1

    cluster_df = pd.DataFrame({'state': curves.index, 'cluster_id': labels, 'kmeans_cluster_id': km,
                               'peak_season_week': curves.idxmax(axis=1).to_numpy()})
    meta = {'best_k': best_k, 'silhouette_scores': scores, 'states': list(curves.index),
            'ari_ward_kmeans': round(float(adjusted_rand_score(labels, km)), 3),
            'excluded_states': sorted(set(df['state']) - set(curves.index))}
    if dim_state is not None:
        # chi 48 bang luc dia + DC: AK, HI o xa nen lam khoang cach trung binh mat y nghia
        ds = dim_state.set_index('state').reindex(curves.index)
        cont = ds['contiguous'].astype(bool).to_numpy()
        meta['geography'] = geographic_coherence(labels[cont], ds['lat'].to_numpy(float)[cont],
                                                 ds['lon'].to_numpy(float)[cont])
    return cluster_df, Z, meta
