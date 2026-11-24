"""TV3 (RQ1-RQ3): moc mua, giai doan mua, phan cum bang, kiem dinh vung HHS, cac phat hien them va hinh EDA.

Chay: python pipelines/03_season_eda.py   (tu thu muc goc repo; khoang 1 phut)
Doc:  load_flu_week(), load_dim_state() cua TV2 (data/business/)
Ghi:  data/business/season_milestones.parquet, season_phase.parquet, state_cluster.parquet (hop dong ke_hoach.md 4.2)
      data/business/hhs_kruskal_results.csv, hhs_dunn_posthoc.csv, season_signal_lead.csv, season_insights.json
      reports/figures/tv3_*.png
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fluwatch.seasonality import insights  # noqa: E402
from fluwatch.seasonality.clustering import cluster_states  # noqa: E402
from fluwatch.seasonality.milestones import detect_season_milestones, mask_sparse_ili  # noqa: E402
from fluwatch.seasonality.plots import (  # noqa: E402
    plot_cluster_dendrogram, plot_lag_and_acf, plot_onset_distribution, plot_onset_latitude, plot_onset_ridgeline,
    plot_season_overlay, plot_season_progress, plot_severity_boxplot, plot_signal_lead, plot_state_week_heatmap,
)
from fluwatch.seasonality.stats_tests import run_hhs_comparisons  # noqa: E402
from fluwatch.warehouse.load import load_dim_state, load_flu_week  # noqa: E402

DATA_DIR = ROOT / 'data' / 'business'
FIG_DIR = ROOT / 'reports' / 'figures'
FIG_DIR.mkdir(parents=True, exist_ok=True)

print("1. Đang tải dữ liệu từ tầng warehouse")
df_week = mask_sparse_ili(load_flu_week())
dim_state = load_dim_state()
current = df_week['season'].max()

print("2. Tính toán baseline, tuần khởi phát (có điều kiện xét nghiệm), tuần đỉnh và giai đoạn mùa")
season_milestones, season_phase = detect_season_milestones(df_week, dim_state)
season_milestones.to_parquet(DATA_DIR / 'season_milestones.parquet', index=False)
season_phase.to_parquet(DATA_DIR / 'season_phase.parquet', index=False)

print("3. Phân cụm các bang theo hình dạng đường cong mùa vụ")
state_cluster, Z, meta = cluster_states(df_week, dim_state=dim_state)
state_cluster.to_parquet(DATA_DIR / 'state_cluster.parquet', index=False)
print(f"-> Số cụm tối ưu k = {meta['best_k']}, Silhouette = {meta['silhouette_scores']}")
print(f"-> Ward so với k-means: ARI = {meta['ari_ward_kmeans']}; tính vùng: {meta['geography']}")

print("4. Chạy kiểm định thống kê giữa các vùng HHS")
stats_df, dunn_df = run_hhs_comparisons(season_milestones, dim_state)
stats_df.to_csv(DATA_DIR / 'hhs_kruskal_results.csv', index=False)
print(stats_df.to_string(index=False))
if not dunn_df.empty:
    dunn_df.to_csv(DATA_DIR / 'hhs_dunn_posthoc.csv', index=False)
    print(f"-> {int(dunn_df['significant_005'].sum())} cặp vùng HHS khác biệt có ý nghĩa (Dunn, Holm p < 0,05)")

print("5. Các phát hiện thêm: tín hiệu báo sớm, mùa hiện tại, hướng lan, xu hướng")
lead, _ = insights.signal_lead(df_week)
lead.to_csv(DATA_DIR / 'season_signal_lead.csv', index=False)
print(lead.round(3).to_string(index=False))
progress = insights.season_progress(season_milestones, df_week)
spread = insights.spread_direction(season_milestones, dim_state)
trend = insights.onset_trend(season_milestones)
print(f"-> Mùa {progress['season']}: {progress['states_onset_now']} bang đã khởi phát đến tuần "
      f"{progress['onset_confirmed_by_week']} (trung vị các mùa trước {progress['history_median']:.0f}; "
      f"sớm thứ {progress['rank_earliest']}/{progress['n_seasons_compared']})")
print(f"-> Hướng lan: ρ(vĩ độ) = {spread['rho_lat']:.3f} (p = {spread['p_lat']:.1e}), "
      f"ρ(kinh độ) = {spread['rho_lon']:.3f} (p = {spread['p_lon']:.2f})")
print(f"-> Xu hướng khởi phát qua các mùa: Kendall τ = {trend['tau']:.3f}, p = {trend['p_value']:.2f}")

summary = {
    'current_season': current,
    'onset_rule': 'ILI (hoặc NSSP) >= mức nền 3 tuần liên tiếp; từ 2016-17 tuần đầu phải có xét nghiệm dương tính >= 2%',
    'cluster': {k: v for k, v in meta.items() if k != 'states'},
    'cluster_members': state_cluster.groupby('cluster_id')['state'].apply(lambda s: sorted(s)).to_dict(),
    'hhs_kruskal': stats_df.to_dict('records'),
    'season_progress': progress, 'spread_direction': spread, 'onset_trend': trend,
}
(DATA_DIR / 'season_insights.json').write_text(
    json.dumps(summary, ensure_ascii=False, indent=2, default=lambda o: o.item() if hasattr(o, 'item') else str(o)),
    encoding='utf-8')

print("6. Xuất các biểu đồ EDA (reports/figures/tv3_*.png)")
plot_season_overlay(df_week, FIG_DIR, current_season=current)
plot_severity_boxplot(season_milestones, FIG_DIR)
plot_onset_distribution(season_milestones, FIG_DIR)
plot_onset_ridgeline(season_milestones, FIG_DIR)
plot_lag_and_acf(df_week, FIG_DIR)
plot_state_week_heatmap(df_week, season_milestones, FIG_DIR)
plot_cluster_dendrogram(Z, meta['states'], FIG_DIR)
plot_signal_lead(lead, FIG_DIR)
plot_season_progress(progress, FIG_DIR)
plot_onset_latitude(season_milestones, dim_state, spread, FIG_DIR)

print("Hoàn tất pipeline 03_season_eda")
