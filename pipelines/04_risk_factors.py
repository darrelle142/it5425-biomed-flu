"""TV4 (RQ4): yeu to anh huong - tuong quan tre, Negative Binomial, kiem chung Shaman 2010.

Chay: python pipelines/04_risk_factors.py
Doc: data/business/ (load_flu_week cua TV2), data/business/season_milestones.parquet (TV3, cho Shaman).
Ghi: data/business/risk_rate_ratios.csv (hop dong ke_hoach.md muc 4.2), reports/tv4/*.csv|json,
     reports/figures/tv4_*.png. Khong sua data/raw/.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd

from fluwatch.risk_factors import data, lag_corr, nb_model, plots, shaman

BUSINESS = ROOT / "data" / "business"
OUT = ROOT / "reports" / "tv4"
FIG = ROOT / "reports" / "figures"
OUT.mkdir(parents=True, exist_ok=True)
FIG.mkdir(parents=True, exist_ok=True)

print("1. Chuan bi du lieu (Q12)")
weekly = data.weekly_panel()
sample, steps = data.analysis_sample(weekly)
steps.to_csv(OUT / "sample_steps.csv", index=False)
print(steps.to_string(index=False))

print("2. Tuong quan tre 0-4 tuan (Q13)")
per_state = lag_corr.state_correlations(sample)
lc = lag_corr.summarize(per_state)
per_state.to_csv(OUT / "lag_correlation_by_state.csv", index=False)
lc.to_csv(OUT / "lag_correlation.csv", index=False)
print(lc.round(3).to_string(index=False))
plots.lag_correlation(lc, FIG / "tv4_lag_correlation.png")

print("3. Negative Binomial, LR test, AIC, overdispersion (Q14)")
rr, fits = nb_model.fit_all(sample)
rr.to_csv(BUSINESS / "risk_rate_ratios.csv", index=False)
rr.to_csv(OUT / "risk_rate_ratios.csv", index=False)
fits.to_csv(OUT / "nb_fit.csv", index=False)
print(rr.round(4).to_string(index=False))
print(fits.round(3).to_string(index=False))
# vaccine, nghi le khong tre: ve tu mo hinh do tre 0 (chot truoc, khong chon theo AIC sau khi xem ket qua)
plots.forest(rr, FIG / "tv4_forest_rate_ratio.png", lag_main=0)

print("4. Kiem chung Shaman 2010 (BAN TAM)")
ms_path = BUSINESS / "season_milestones.parquet"
if ms_path.exists():
    ms = pd.read_parquet(ms_path)
    if "source" not in ms.columns:
        print("   season_milestones chua dung hop dong (thieu cot source) -> bo qua")
    else:
        summ, t_null, obs = shaman.run(ms, weekly, data.contiguous_states(), data.EXCLUDED_SEASONS)
        (OUT / "shaman.json").write_text(json.dumps({k: (float(v) if not isinstance(v, str) else v)
                                                      for k, v in summ.items()}, indent=2, ensure_ascii=False))
        print(summ)
        plots.shaman(summ, t_null, FIG / "tv4_shaman_permutation.png")
else:
    print("   chua co season_milestones.parquet (TV3) -> bo qua")

print("Hoan tat pipeline 04_risk_factors")
