"""Kiem chung Shaman et al. 2010 bang permutation test (ke hoach v2 muc 8; nhat ky Q14).

Voi moi bang (48 bang luc dia + DC) va moi mua co tuan khoi phat w (tu season_milestones cua TV3):
  quan sat = trung binh ah_anomaly cac tuan mua w-4 .. w-2 (2-4 tuan truoc khoi phat).
Gia thuyet 0: tuan khoi phat khong lien quan do am -> thay w bang tuan ngau nhien trong khoang tuan mua 5-30 cua
cung bang-mua. Thong ke T = trung binh quan sat tren moi bang-mua; p mot phia = P(T_null <= T_obs).

Luu y: Shaman 2010 xac dinh khoi phat tu tu vong do viem phoi va cum, nhom dung ILI, nen day la kiem chung gia thuyet
voi dinh nghia khoi phat khac. Mua 2021-22 bi bo cho den khi TV3 ap dung dinh nghia khoi phat moi (nhat ky Q11).
"""
import numpy as np
import pandas as pd

WINDOW = (2, 4)          # 2-4 tuan truoc khoi phat
NULL_WEEKS = (5, 30)     # tuan mua co the la khoi phat
N_PERM = 10000
SKIP_SEASONS = ("2021-22",)


def onset_pairs(milestones, weekly, states, excluded_seasons):
    m = milestones.copy()
    m["state"] = m["state"].astype(str)
    m["season"] = m["season"].astype(str)
    m = m[m["state"].isin(states) & ~m["season"].isin(tuple(excluded_seasons) + SKIP_SEASONS)]
    m = m[m["source"] == "ili"].dropna(subset=["onset_week"])
    m = m[m["onset_week"].between(NULL_WEEKS[0], NULL_WEEKS[1])]
    w = weekly[["state", "season", "season_week", "ah_anomaly"]].dropna()
    ah = {key: g.set_index("season_week")["ah_anomaly"] for key, g in w.groupby(["state", "season"])}
    return m[["state", "season", "onset_week"]].reset_index(drop=True), ah


def _window_mean(series, wk):
    idx = np.arange(wk - WINDOW[1], wk - WINDOW[0] + 1)
    v = series.reindex(idx)
    return v.mean() if v.notna().sum() == len(idx) else np.nan


def run(milestones, weekly, states, excluded_seasons, seed=2026):
    pairs, ah = onset_pairs(milestones, weekly, states, excluded_seasons)
    cand = np.arange(NULL_WEEKS[0], NULL_WEEKS[1] + 1)
    obs, table = [], []
    for r in pairs.itertuples():
        s = ah.get((r.state, r.season))
        if s is None:
            continue
        o = _window_mean(s, int(r.onset_week))
        null = np.array([_window_mean(s, c) for c in cand])
        if np.isnan(o) or np.isnan(null).any():
            continue
        obs.append(o)
        table.append(null)
    obs = np.array(obs)
    table = np.vstack(table)
    rng = np.random.default_rng(seed)
    pick = rng.integers(0, table.shape[1], size=(N_PERM, table.shape[0]))
    t_null = table[np.arange(table.shape[0]), pick].mean(axis=1)
    t_obs = obs.mean()
    p = (np.sum(t_null <= t_obs) + 1) / (N_PERM + 1)
    summary = dict(n_pairs=len(obs), n_states=pairs["state"].nunique(), t_obs=t_obs,
                   t_null_mean=t_null.mean(), t_null_q025=np.quantile(t_null, 0.025),
                   t_null_q975=np.quantile(t_null, 0.975), p_one_sided=p, share_obs_negative=(obs < 0).mean(),
                   skipped_seasons=",".join(SKIP_SEASONS))
    return summary, t_null, obs
