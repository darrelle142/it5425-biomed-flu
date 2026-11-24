"""Bo du lieu chen loi cua TV4 de TV2 kiem tra bo quy tac chat luong (ke_hoach.md muc 2, viec cua TV4).

Doc lap voi bo tu sinh cua TV2 (warehouse/inject.py): loi duoc dung theo cac TINH HUONG THAT co the xay ra voi
nguon CDC, khong rai deu ngau nhien, va dung seed khac. Hop dong file (inject.py):
    data/sandbox/corrupted/fact_flu_week.parquet   fact_flu_week da bi chen loi
    data/sandbox/corrupted/answer_key.csv          error_id, error_type, state, week, column, scenario
    error_type in {missing_random, missing_block, duplicate, preliminary_revised}; column = "*" neu ca dong.

Tinh huong:
  A. missing_random      1 bang khong nop 1 tin hieu trong 1 tuan (ILINet, NHSN, NSSP, xet nghiem), ngoai 4 tuan so bo
  B. missing_block       tram nuoc thai cua bang ngung 8 tuan (cot wval); bang ngung gui ILINet 6 tuan (ili_pct);
                         mat ca khoi dong 5 tuan cua 1 bang (loi ghep bang)
  C. duplicate           chay lai buoc nap 1 tuan cho 6 bang (nhan doi ca tuan) + 20 dong trung rai rac
  D. preliminary_revised so so bo NHSN 4 tuan cuoi THAP hon so sau sua 15-40% (bao cao tre: chi sua xuong)
Moi (bang, tuan) toi da 1 loi de cham diem ro rang.
"""
import numpy as np
import pandas as pd

SEED = 4040
OUT = ("sandbox", "corrupted")
RANDOM_COLS = ["ili_pct", "num_ili", "hosp_flu", "rate_flu", "ed_pct_flu", "lab_pct_pos"]
INT_COLS = {"num_ili", "num_patients", "hosp_flu"}


def _na(dtype):
    return pd.NA if str(dtype) in ("Int64", "boolean", "string") else np.nan


def build(fact: pd.DataFrame, seed=SEED, n_random=200):
    rng = np.random.default_rng(seed)
    f = fact.copy().reset_index(drop=True)
    f["week"] = pd.to_datetime(f["week"])
    used, key = set(), []
    prelim = f["is_preliminary"].astype(bool).to_numpy()
    weeks = np.sort(f["week"].unique())
    safe_weeks = weeks[:-8]                                   # khong cham 4 tuan so bo va vung dem
    states = sorted(f["state"].unique())

    def add(t, s, w, c, sc):
        key.append(dict(error_type=t, state=s, week=pd.Timestamp(w), column=c, scenario=sc))
        used.add((s, pd.Timestamp(w)))

    def free(s, ws):
        return all((s, pd.Timestamp(w)) not in used for w in ws)

    # B. mat khoi (lam truoc de chon duoc doan lien tuc)
    def block(col, length, scenario, need_col=True):
        for _ in range(500):
            s = states[rng.integers(len(states))]
            i = int(rng.integers(0, len(safe_weeks) - length))
            ws = [pd.Timestamp(w) for w in safe_weeks[i:i + length]]
            rows = f.index[(f["state"] == s) & f["week"].isin(ws)]
            if len(rows) != length or not free(s, ws):
                continue
            if need_col and not f.loc[rows, col].notna().all():
                continue
            return s, ws, rows
        raise RuntimeError(f"khong tim duoc doan cho {scenario}")

    s, ws, rows = block("wval", 8, "tram nuoc thai ngung 8 tuan")
    f.loc[rows, "wval"] = _na(f["wval"].dtype)
    for w in ws:
        add("missing_block", s, w, "wval", "tram nuoc thai ngung 8 tuan")
    s, ws, rows = block("ili_pct", 6, "bang ngung gui ILINet 6 tuan")
    f.loc[rows, "ili_pct"] = _na(f["ili_pct"].dtype)
    for w in ws:
        add("missing_block", s, w, "ili_pct", "bang ngung gui ILINet 6 tuan")
    s, ws, drop_rows = block(None, 5, "mat ca dong 5 tuan (loi ghep bang)", need_col=False)
    for w in ws:
        add("missing_block", s, w, "*", "mat ca dong 5 tuan (loi ghep bang)")

    # A. thieu rai rac theo tin hieu
    cand = [(i, c) for c in RANDOM_COLS for i in np.flatnonzero(f[c].notna().to_numpy() & ~prelim)]
    n = 0
    for j in rng.permutation(len(cand)):
        if n >= n_random:
            break
        i, c = cand[j]
        s, w = f.at[i, "state"], f.at[i, "week"]
        if (s, w) in used:
            continue
        f.loc[i, c] = _na(f[c].dtype)
        add("missing_random", s, w, c, "bang khong nop 1 tin hieu trong 1 tuan")
        n += 1

    # D. so so bo NHSN bi bao thieu (chi sua xuong)
    pre = f.index[prelim & (pd.to_numeric(f["hosp_flu"], errors="coerce") > 5).to_numpy()]
    for i in rng.permutation(pre)[:40]:
        s, w = f.at[i, "state"], f.at[i, "week"]
        if (s, w) in used:
            continue
        k = 1 - rng.uniform(0.15, 0.40)
        c = "hosp_flu" if rng.random() < 0.5 else "rate_flu"
        old = float(f.at[i, c])
        new = round(old * k) if c in INT_COLS else round(old * k, 4)
        if new == old:
            continue
        f.loc[i, c] = new
        add("preliminary_revised", s, w, c, "so so bo NHSN bao thieu 15-40%")

    f = f.drop(index=drop_rows)

    # C. trung dong: nap lai ca 1 tuan cho 6 bang + 20 dong rai rac
    w = pd.Timestamp(safe_weeks[int(rng.integers(len(safe_weeks)))])
    dup = [i for i in f.index[f["week"] == w] if (f.at[i, "state"], w) not in used]
    dup = list(rng.choice(dup, size=min(6, len(dup)), replace=False))
    for i in dup:
        add("duplicate", f.at[i, "state"], w, "*", "nap lai 1 tuan cho 6 bang")
    pool = [i for i in f.index if (f.at[i, "state"], f.at[i, "week"]) not in used]
    extra = list(rng.choice(pool, size=20, replace=False))
    for i in extra:
        add("duplicate", f.at[i, "state"], f.at[i, "week"], "*", "dong trung rai rac")
    f = pd.concat([f, f.loc[dup + extra]], ignore_index=True)

    f = f.sample(frac=1, random_state=seed).reset_index(drop=True)
    k = pd.DataFrame(key)
    k.insert(0, "error_id", range(1, len(k) + 1))
    k["week"] = k["week"].dt.strftime("%Y-%m-%d")
    return f, k


def write(root, fact=None, seed=SEED):
    # doc thang file cua kho (giu nguyen kieu cot) - giong ban TV2 cham trong inject.py
    fact = pd.read_parquet(root / "data" / "business" / "fact_flu_week.parquet") if fact is None else fact
    f, k = build(fact, seed=seed)
    d = root.joinpath("data", *OUT)
    d.mkdir(parents=True, exist_ok=True)
    f.to_parquet(d / "fact_flu_week.parquet", index=False)
    k.to_csv(d / "answer_key.csv", index=False)
    return d, k
