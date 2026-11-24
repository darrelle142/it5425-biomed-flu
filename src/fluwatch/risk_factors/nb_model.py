"""Hoi quy Negative Binomial tren ILINet (nhat ky Q14).

num_ili ~ yeu to + offset log(num_patients) + C(state) + C(season) + C(season_week)

- Moi do tre k = 0-4 mot mo hinh: AH va PM2.5 cung do tre k; vaccine (muc mua) va nghi le (tuan hien tai) khong tre.
- Rate ratio theo 1 g/m3 (AH), 10 ug/m3 (PM2.5), 10 diem % (vaccine), co/khong (nghi le).
- Khoang tin cay 95% chinh: sai so chuan cum theo bang (chuoi tuan cung bang tu tuong quan nen sai so mac dinh qua nho).
- LR test bo tung bien (gia dinh doc lap giua cac tuan nen p_lr nho hon thuc te; doc cung khoang tin cay cum).
- AIC; overdispersion: Pearson chi2/df cua Poisson va LR test alpha = 0 (nua chi2 vi alpha o bien).
"""
import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from scipy import stats

from .data import LAGS

SCALE = {"ah": 1.0, "pm25": 10.0, "vax": 10.0, "holiday": 1.0}
LABELS = {"ah": "Độ ẩm tuyệt đối, độ chênh (+1 g/m³)", "pm25": "PM2.5 EPA, độ chênh (+10 µg/m³)",
          "vax": "Độ phủ vaccine mùa trước (+10 điểm %)", "holiday": "Tuần nghỉ lễ (có/không)"}
FE = "C(state) + C(season) + C(season_week)"


def model_frame(f, k):
    d = pd.DataFrame({
        "y": f["num_ili"], "off": np.log(f["num_patients"]),
        "ah": f[f"ah_anomaly_l{k}"], "pm25": f[f"pm25_epa_anomaly_l{k}"],
        "vax": f["flu_vax_pct_prev"], "holiday": f["holiday_week"],
        "state": f["state"], "season": f["season"], "season_week": f["season_week"].astype(int),
    }).dropna().reset_index(drop=True)
    return d


def _fit_nb(formula, d, start=None, cluster=False):
    mod = smf.negativebinomial(formula, d, offset=d["off"])
    kw = dict(cov_type="cluster", cov_kwds={"groups": pd.factorize(d["state"])[0]}) if cluster else {}
    return mod.fit(disp=0, maxiter=300, start_params=start, **kw)


def _poisson_start(formula, d):
    p = smf.glm(formula, d, offset=d["off"], family=sm.families.Poisson()).fit()
    return p, np.append(p.params.to_numpy(), 0.1)


def fit_lag(f, k):
    d = model_frame(f, k)
    terms = list(SCALE)
    full_formula = "y ~ " + " + ".join(terms) + " + " + FE
    pois, start = _poisson_start(full_formula, d)
    full = _fit_nb(full_formula, d, start=start, cluster=True)
    rows = []
    for t in terms:
        red_formula = "y ~ " + " + ".join(x for x in terms if x != t) + " + " + FE
        _, s0 = _poisson_start(red_formula, d)
        red = _fit_nb(red_formula, d, start=s0)
        lr = 2 * (full.llf - red.llf)
        b, se = full.params[t], full.bse[t]
        c = SCALE[t]
        rows.append(dict(factor=t, lag_weeks=k if t in ("ah", "pm25") else 0, rr=np.exp(c * b),
                         ci_low=np.exp(c * (b - 1.96 * se)), ci_high=np.exp(c * (b + 1.96 * se)),
                         p_lr=stats.chi2.sf(lr, 1), p_wald_cluster=2 * stats.norm.sf(abs(b / se)),
                         model=f"nb_lag{k}"))
    lr_alpha = 2 * (full.llf - pois.llf)
    fit = dict(model=f"nb_lag{k}", lag_weeks=k, n=len(d), n_states=d["state"].nunique(),
               n_seasons=d["season"].nunique(), aic_nb=full.aic, aic_poisson=pois.aic,
               alpha=full.params["alpha"], poisson_pearson_df=pois.pearson_chi2 / pois.df_resid,
               p_overdispersion=0.5 * stats.chi2.sf(lr_alpha, 1), nb_pearson_df=_nb_pearson_df(full, d))
    return pd.DataFrame(rows), fit


def _nb_pearson_df(res, d):
    mu = res.predict(d, offset=d["off"])
    a = res.params["alpha"]
    pearson = (((d["y"] - mu) ** 2) / (mu + a * mu ** 2)).sum()
    return pearson / (len(d) - len(res.params))


def common_rows(f):
    """Chi giu dong co du moi do tre 0-4 cua AH, PM2.5 va vaccine: 5 mo hinh cung tap dong nen AIC so duoc."""
    cols = [f"{p}_l{k}" for p in ("ah_anomaly", "pm25_epa_anomaly") for k in LAGS] + ["flu_vax_pct_prev", "holiday_week"]
    return f.dropna(subset=cols).reset_index(drop=True)


def fit_all(f):
    f = common_rows(f)
    rr, fits = [], []
    for k in LAGS:
        r, m = fit_lag(f, k)
        rr.append(r)
        fits.append(m)
    return pd.concat(rr, ignore_index=True), pd.DataFrame(fits)
