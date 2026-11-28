import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage, fcluster
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from fluwatch.seasonality.milestones import *


def cluster_states(df: pd.DataFrame, k_range: range = range(2, 6)):
    completed = get_completed_seasons(df)
    work = mask_sparse_ili(df)
    if 'is_preliminary' in work.columns:
        work = work[~work['is_preliminary'].fillna(False)]
    work.loc[(work['season'] == '2019-20') & (work['season_week'] > COVID_1920_MAX_SEASON_WEEK), 'ili_pct'] = np.nan
    valid_df = work[(work['season'].isin(completed)) & (work['season_week'] <= 52)].copy()

    def _zscore(s: pd.Series) -> pd.Series:
        std = s.std()
        if pd.isna(std) or std == 0:
            return s - s.mean()
        return (s - s.mean()) / std

    valid_df['ili_z'] = valid_df.groupby(['state', 'season'])['ili_pct'].transform(_zscore)

    pivot_curve = valid_df.pivot_table(index='state', columns='season_week', values='ili_z', aggfunc='mean')
    pivot_curve = pivot_curve.interpolate(axis=1, limit_direction='both').dropna(how='all')

    row_means = pivot_curve.mean(axis=1)
    row_stds = pivot_curve.std(axis=1).replace(0, 1)
    z_curves = pivot_curve.sub(row_means, axis=0).div(row_stds, axis=0).fillna(0)

    X = z_curves.values
    Z = linkage(X, method='ward')

    best_k = min(k_range)
    best_score = -1.0
    scores = {}
    for k in k_range:
        labels_hier = fcluster(Z, t=k, criterion='maxclust')
        score = silhouette_score(X, labels_hier)
        scores[k] = round(float(score), 4)
        if score > best_score:
            best_score = score
            best_k = k

    final_hier_labels = fcluster(Z, t=best_k, criterion='maxclust')
    kmeans = KMeans(n_clusters=best_k, random_state=42, n_init=10)
    kmeans_labels = kmeans.fit_predict(X) + 1

    cluster_df = pd.DataFrame({
        'state': pd.Series(z_curves.index, dtype='string'),
        'cluster_id': pd.Series(final_hier_labels, dtype='Int64'),
        'kmeans_cluster_id': pd.Series(kmeans_labels, dtype='Int64'),
    })

    meta = {'best_k': best_k, 'silhouette_scores': scores, 'states': list(z_curves.index)}

    return cluster_df, Z, meta
