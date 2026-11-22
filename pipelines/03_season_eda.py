from pathlib import Path
from fluwatch.warehouse.load import *
from fluwatch.seasonality.milestones import *
from fluwatch.seasonality.clustering import *
from fluwatch.seasonality.stats_tests import *
from fluwatch.seasonality.plots import *


ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / 'data' / 'business'
FIG_DIR = ROOT / 'reports' / 'figures'
FIG_DIR.mkdir(parents=True, exist_ok=True)

print("1. Đang tải dữ liệu từ tầng warehouse")
df_week = mask_sparse_ili(load_flu_week())
dim_state = load_dim_state()

print("2. Tính toán baseline, tuần khởi phát, tuần đỉnh và giai đoạn mùa")
season_milestones, season_phase = detect_season_milestones(df_week)
season_milestones.to_parquet(DATA_DIR / 'season_milestones.parquet', index=False)
season_phase.to_parquet(DATA_DIR / 'season_phase.parquet', index=False)

print("3. Phân cụm các bang theo hình dạng đường cong mùa vụ")
state_cluster, Z, meta = cluster_states(df_week)
state_cluster.to_parquet(DATA_DIR / 'state_cluster.parquet', index=False)
print(f"-> Số cụm tối ưu k = {meta['best_k']}, Silhouette = {meta['silhouette_scores']}")

print("4. Chạy kiểm định thống kê giữa các vùng HHS")
stats_df = run_hhs_comparisons(season_milestones, dim_state)
stats_df.to_csv(DATA_DIR / 'hhs_kruskal_results.csv', index=False)
print(stats_df)

print("5. Xuất các biểu đồ EDA")
plot_season_overlay(df_week, FIG_DIR)
plot_severity_boxplot(season_milestones, FIG_DIR)
plot_onset_distribution(season_milestones, FIG_DIR)
plot_lag_and_acf(df_week, FIG_DIR)
plot_state_week_heatmap(df_week, season_milestones, FIG_DIR)
plot_cluster_dendrogram(Z, meta['states'], FIG_DIR)

print("Hoàn tất pipeline 03_season_eda")
