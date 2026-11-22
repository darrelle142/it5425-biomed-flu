import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage, fcluster
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score


def cluster_states(df: pd.DataFrame, k_range: range = range(2, 6)):
    exclude_seasons = ['2009-10', '2020-21', '2026-27']
    valid_df = df[(~df['season'].isin(exclude_seasons)) & (df['season_week'] <= 52)].copy()

    pivot_curve = valid_df.pivot_table(index='state', columns='season_week', values='ili_pct', aggfunc='mean')
    pivot_curve = pivot_curve.interpolate(axis=1, limit_direction='both').dropna(how='all')

    row_means = pivot_curve.mean(axis=1)
    row_stds = pivot_curve.std(axis=1).replace(0, 1)
    z_curves = pivot_curve.sub(row_means, axis=0).div(row_stds, axis=0).fillna(0)

    X = z_curves.values
    Z = linkage(X, method='ward')

    best_k = 3
    best_score = -1
    scores = {}
    for k in k_range:
        labels_hier = fcluster(Z, t=k, criterion='maxclust')
        score = silhouette_score(X, labels_hier)
        scores[k] = round(score, 4)
        if score > best_score:
            best_score = score
            best_k = k

    final_hier_labels = fcluster(Z, t=best_k, criterion='maxclust')
    kmeans = KMeans(n_clusters=best_k, random_state=42, n_init=10)
    kmeans_labels = kmeans.fit_predict(X) + 1

    cluster_df = pd.DataFrame({
        'state': z_curves.index,
        'cluster_id': final_hier_labels,
        'kmeans_cluster_id': kmeans_labels
    })

    meta = {'best_k': best_k, 'silhouette_scores': scores, 'states': list(z_curves.index)}

    return cluster_df, Z, meta
