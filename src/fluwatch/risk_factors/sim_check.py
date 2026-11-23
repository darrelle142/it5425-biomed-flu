"""Kiem tra phuong phap bang du lieu gia lap biet truoc dap an (ke hoach v2 muc 7.1 muc dich 1-2; nhat ky Q15).

Khong dung de chung minh lien he (muc 7.3): chi hoi "neu hieu ung that co co nay, phuong phap cua nhom co tim lai
duoc khong, va khoang tin cay co dung muc 95% khong".

Sinh du lieu:
- Giu nguyen bien giai thich, hieu ung co dinh va so benh nhan that (mo hinh NB tre 2 tren du lieu that).
- eta = log(mu_that) - b_ah_that * ah + log(RR_cai) * ah   (thay hieu ung do am bang gia tri cai san)
- Nhieu u theo AR(1) trong tung bang-mua: he so rho = tu tuong quan tre 1 cua phan du that; phuong sai bien
  sigma^2 = log(1 + alpha_that) de do phan tan bang NB that; y ~ Poisson(exp(eta + u - sigma^2/2)).
  (Poisson-lognormal: giong NB ve do phan tan nhung giu duoc tu tuong quan giua cac tuan nhu du lieu that.)
Uoc luong lai bang dung mo hinh NB cua nhom; so KTC 95% sai so chuan cum theo bang voi KTC thuong.
"""
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

from .nb_model import FE, SCALE, common_rows

LAG = 2
SCENARIOS = {"cai_hieu_ung": 0.975, "doi_chung": 1.0}
N_REP = 100
SEED = 2026
TERMS = list(SCALE)
FORMULA = "y ~ " + " + ".join(TERMS) + " + " + FE


def frame(sample):
    f = common_rows(sample)
    d = pd.DataFrame({
        "y": f["num_ili"], "off": np.log(f["num_patients"]), "ah": f[f"ah_anomaly_l{LAG}"],
        "pm25": f[f"pm25_epa_anomaly_l{LAG}"], "vax": f["flu_vax_pct_prev"], "holiday": f["holiday_week"],
        "state": f["state"], "season": f["season"], "season_week": f["season_week"].astype(int), "week": f["week"],
        "num_patients": f["num_patients"],
    }).sort_values(["state", "week"]).reset_index(drop=True)
    return d


def _fit(d, start=None, cluster=False):
    mod = smf.negativebinomial(FORMULA, d, offset=d["off"])
    kw = dict(cov_type="cluster", cov_kwds={"groups": pd.factorize(d["state"])[0]}) if cluster else {}
    return mod.fit(disp=0, maxiter=300, start_params=start, **kw)


def calibrate(d):
    res = _fit(d)
    mu = np.asarray(res.predict(d, offset=d["off"]))
    r = np.log((d["y"] + 0.5) / mu)
    g = d.groupby(["state", "season"]).ngroup()
    lag1 = pd.Series(r).groupby(g).shift(1)
    rho = float(pd.concat([pd.Series(r), lag1], axis=1).dropna().corr().iloc[0, 1])
    alpha = float(res.params["alpha"])
    return dict(res=res, mu=mu, rho=rho, alpha=alpha, sigma2=np.log1p(alpha), b_ah=float(res.params["ah"]))


def _ar1(groups, rho, sigma, rng):
    e = rng.normal(0, sigma * np.sqrt(1 - rho ** 2), len(groups))
    u = np.empty(len(groups))
    first = np.r_[True, groups[1:] != groups[:-1]]
    for i in range(len(groups)):
        u[i] = rng.normal(0, sigma) if first[i] else rho * u[i - 1] + e[i]
    return u


def simulate(d, cal, rr_planted, rng):
    eta = np.log(cal["mu"]) + (np.log(rr_planted) - cal["b_ah"]) * d["ah"].to_numpy()
    g = d.groupby(["state", "season"]).ngroup().to_numpy()
    u = _ar1(g, cal["rho"], np.sqrt(cal["sigma2"]), rng)
    return rng.poisson(np.exp(eta + u - cal["sigma2"] / 2))


def run(sample, n_rep=N_REP, seed=SEED, progress=None):
    d = frame(sample)
    cal = calibrate(d)
    start = cal["res"].params.to_numpy()
    rng = np.random.default_rng(seed)
    rows, example = [], None
    for name, rr in SCENARIOS.items():
        for i in range(n_rep):
            ds = d.copy()
            ds["y"] = simulate(d, cal, rr, rng)
            if example is None and name == "cai_hieu_ung":
                example = ds.assign(is_synthetic=1, sim_scenario=name, sim_seed=seed, rep=i)
            plain = _fit(ds, start=start)
            clus = _fit(ds, start=plain.params.to_numpy(), cluster=True)
            b = clus.params["ah"]
            for kind, res in (("cum_theo_bang", clus), ("thuong", plain)):
                se = res.bse["ah"]
                lo, hi = np.exp(b - 1.96 * se), np.exp(b + 1.96 * se)
                rows.append(dict(scenario=name, rr_true=rr, rep=i, ci_type=kind, rr_hat=np.exp(b), ci_low=lo,
                                 ci_high=hi, covers=lo <= rr <= hi, significant=(hi < 1) or (lo > 1)))
            if progress:
                progress(name, i)
    reps = pd.DataFrame(rows)
    summ = reps.groupby(["scenario", "rr_true", "ci_type"]).agg(
        n=("rep", "size"), rr_hat_mean=("rr_hat", "mean"), rr_hat_sd=("rr_hat", "std"),
        coverage=("covers", "mean"), share_significant=("significant", "mean")).reset_index()
    params = dict(lag=LAG, scenarios=SCENARIOS, n_rep=n_rep, seed=seed, rho=cal["rho"], alpha=cal["alpha"],
                  sigma2=cal["sigma2"], b_ah_real=cal["b_ah"], n_rows=len(d))
    return summ, reps, params, example, d, cal
