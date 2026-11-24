"""TV5: mô hình cảnh báo sớm. Một lệnh chạy toàn bộ phần của TV5.

    python pipelines/05_alert_model.py

Đọc dữ liệu qua load_flu_week() + season_milestones.parquet (TV3) -> nhãn -> huấn luyện -> models/*.joblib
-> data/business/alert_forecast.parquet. Chạy từ thư mục gốc repo.
"""
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import json  # noqa: E402

import joblib  # noqa: E402

from fluwatch.alerting.backtest import run_backtest  # noqa: E402
from fluwatch.alerting.evaluate import evaluate  # noqa: E402
from fluwatch.alerting.figures import make_figures  # noqa: E402
from fluwatch.alerting.labels import build_labels  # noqa: E402
from fluwatch.alerting.models import (  # noqa: E402
    TEST_SEASON, TRAIN_LAST, add_features, build_alert_forecast, fit_all, quick_auc,
)
from fluwatch.warehouse.load import load_flu_week  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("05")

import pandas as pd  # noqa: E402

ms_path = ROOT / "data" / "business" / "season_milestones.parquet"
milestones = pd.read_parquet(ms_path) if ms_path.exists() else None
if milestones is None or "onset_date" not in milestones:
    log.info("CẢNH BÁO: chưa có season_milestones.parquet (TV3, có onset_date): tự tính tuần khởi phát")
    milestones = None
df = add_features(build_labels(load_flu_week(), milestones))
log.info("Nhãn khởi phát lấy từ: %s", df["onset_source"].iloc[0])
log.info("Bảng: %d dòng, %d bang", len(df), df["state"].nunique())

fitted = fit_all(df)
(ROOT / "models").mkdir(exist_ok=True)
for (label, variant), f in fitted.items():
    joblib.dump(f, ROOT / "models" / f"{label}__{variant}.joblib")
    auc, n = quick_auc(df, fitted, label, variant, df["season"] == TEST_SEASON)
    log.info("%-16s %-5s train n=%-6d dương=%-5d | test %s AUC=%.3f (n=%d)",
             label, variant, f["n_train"], f["n_pos"], TEST_SEASON, auc, n)

ev, roc = evaluate(df, fitted)
bt_summary, bt, lead = run_backtest(df, fitted)
ev["backtest"] = bt_summary
if len(bt):
    bt.to_parquet(ROOT / "data" / "business" / "backtest_2025_26.parquet", index=False)
    lead.to_csv(ROOT / "data" / "business" / "backtest_alert_lead.csv", index=False)
    log.info("Backtest as-published: %s", {k: v for k, v in bt_summary["alert_timing"].items() if k.startswith(("states_alerted_by", "lead_weeks_median"))})
else:
    log.info("Bỏ qua backtest: %s", bt_summary["skipped"])
(ROOT / "data" / "business" / "model_eval.json").write_text(json.dumps(ev, ensure_ascii=False, indent=2), encoding="utf-8")
roc.to_csv(ROOT / "data" / "business" / "roc_points.csv", index=False)
log.info("Ghi model_eval.json, roc_points.csv (mô hình chính: AUC=%.3f, CI %s)", ev["auc"], [round(x, 3) for x in ev["auc_ci"]])

make_figures(df, fitted, ev, roc, bt, lead, ROOT / "reports" / "figures")
log.info("Ghi hình reports/figures/tv5_*.png")

fc = build_alert_forecast(df, fitted)
out = ROOT / "data" / "business" / "alert_forecast.parquet"
fc.to_parquet(out, index=False)
log.info("Ghi %s (%d dòng). Train<=%s, test=%s", out.relative_to(ROOT), len(fc), TRAIN_LAST, TEST_SEASON)
