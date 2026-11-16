"""Chung minh bo kiem tra chat luong bat duoc loi: chen loi co dap an vao fact_flu_week roi cham (TV2 viec 4).

Nguon bo du lieu loi:
1. Cua TV4 (uu tien) neu da co:  data/sandbox/corrupted/fact_flu_week.parquet  +  data/sandbox/corrupted/answer_key.csv
2. Neu chua co: tu sinh bang inject_errors() (cung 4 loai loi, co seed) - chi trong bo nho, khong ghi vao sandbox/.

Hop dong answer_key.csv (gui TV4):
    error_id, error_type, state, week, column
    error_type in {missing_random, missing_block, duplicate, preliminary_revised}
    column = ten cot bi sua, hoac "*" neu ca dong (dong bi xoa trong missing_block, dong bi nhan doi trong duplicate)
    week = thu Bay ket thuc tuan MMWR (YYYY-MM-DD)

Cach cham: chay run_checks() tren du lieu goc (baseline) va du lieu loi; vi pham MOI (khong co o baseline) tro
dung o (bang, tuan, cot) - hoac dung dong (bang, tuan) voi loi ca dong - thi loi do "bi bat". Recall = bat / chen.
Vi pham moi khong giai thich duoc bang dap an = bao dong gia.

Hai che do chen:
    raw        : chi sua o du lieu, cac cot phai sinh (bien tre, wow, missing_*, cdc_level) giu nguyen nhu ban goc.
    consistent : sua xong tinh lai moi cot phai sinh cho khop -> cac quy tac noi bo khong thay, chi con doi chieu
                 nguon (M01-M03) - kiem tra "phong thu nhieu lop".

Chay: python pipelines/02_warehouse.py --steps inject   -> reports/data_quality/injection_test.md
"""
import datetime as dt
import logging

import numpy as np
import pandas as pd

from .common import season_of
from .business import LAG_COLS, LEVEL_NAMES, MISSING_FLAGS, _cdc_level, _pct_change
from .quality import _hrd, _md, load_business, load_clean, run_checks

log = logging.getLogger("fluwatch.warehouse")

ERROR_TYPES = {
    "missing_random": "Thiếu ngẫu nhiên (ô bị xóa rải rác)",
    "missing_block": "Mất khối nhiều tuần liên tiếp (mất dòng hoặc mất cả đoạn một tín hiệu)",
    "duplicate": "Trùng dòng",
    "preliminary_revised": "Số sơ bộ (4 tuần cuối) bị sửa ±10–50%",
}
CORE = ["ili_pct", "num_ili", "num_patients", "hosp_flu", "rate_flu", "ed_pct_flu", "lab_pct_pos", "wval",
        "temp_mean", "abs_humidity", "pm25_mean"]
PRELIM_COLS = ["hosp_flu", "rate_flu", "ili_pct", "ed_pct_flu", "num_ili"]
INT_COLS = {"num_ili", "num_patients", "hosp_flu"}


# ============================== Chen loi ==============================

def inject_errors(fact, seed=2026, n_random=300, n_blocks=8, n_dup=80, n_prelim=60, mode="raw", paths=None):
    """Tra ve (fact bi loi, answer_key). Cac loi khong chong len nhau (moi (bang, tuan) toi da 1 loi)."""
    rng = np.random.default_rng(seed)
    f = fact.copy().reset_index(drop=True)
    used = set()                                  # (state, week) da co loi
    key = []

    def add(t, s, w, c):
        key.append(dict(error_type=t, state=s, week=pd.Timestamp(w), column=c))
        used.add((s, pd.Timestamp(w)))

    prelim = f.is_preliminary.astype(bool).to_numpy()

    # 1. Thieu ngau nhien: o dang co so -> NaN (ngoai 4 tuan so bo)
    cand = [(i, c) for c in CORE for i in np.flatnonzero(f[c].notna().to_numpy() & ~prelim)]
    for j in rng.permutation(len(cand)):
        if sum(k["error_type"] == "missing_random" for k in key) >= n_random:
            break
        i, c = cand[j]
        s, w = f.at[i, "state"], f.at[i, "week"]
        if (s, w) in used:
            continue
        f.loc[i, c] = pd.NA if str(f[c].dtype) in ("Int64", "boolean") else np.nan
        add("missing_random", s, w, c)

    # 2. Mat khoi: nua so khoi xoa ca dong, nua so khoi xoa mot tin hieu (6-12 tuan lien tiep)
    drop_idx = []
    weeks = np.sort(f.week.unique())
    states = sorted(f.state.unique())
    made = 0
    while made < n_blocks:
        s = states[rng.integers(len(states))]
        L = int(rng.integers(6, 13))
        start = int(rng.integers(0, len(weeks) - L - 8))        # khong cham 4 tuan so bo
        blk = [pd.Timestamp(w) for w in weeks[start:start + L]]
        if any((s, w) in used for w in blk):
            continue
        rows = f.index[(f.state == s) & f.week.isin(blk)]
        if made % 2 == 0:
            drop_idx.extend(rows)
            for w in blk:
                add("missing_block", s, w, "*")
        else:
            cols = [c for c in ["ili_pct", "rate_flu", "lab_pct_pos", "ed_pct_flu", "wval", "abs_humidity"]
                    if f.loc[rows, c].notna().all()]
            if not cols:
                continue
            c = cols[rng.integers(len(cols))]
            f.loc[rows, c] = pd.NA if str(f[c].dtype) == "Int64" else np.nan
            for w in blk:
                add("missing_block", s, w, c)
        made += 1

    # 3. So so bo bi sua: o 4 tuan cuoi nhan he so 1 +- U(0.1, 0.5)
    cand = [(i, c) for c in PRELIM_COLS for i in np.flatnonzero(prelim & (pd.to_numeric(f[c], errors="coerce") > 0)
                                                                .to_numpy())]
    n = 0
    for j in rng.permutation(len(cand)):
        if n >= n_prelim:
            break
        i, c = cand[j]
        s, w = f.at[i, "state"], f.at[i, "week"]
        if (s, w) in used:
            continue
        old = float(f.at[i, c])
        new = old * (1 + rng.choice([-1, 1]) * rng.uniform(0.1, 0.5))
        if c in INT_COLS:
            new = round(new)
            if new == old:
                new = old + 1
        else:
            new = round(new, 4)
        f.loc[i, c] = new
        add("preliminary_revised", s, w, c)
        n += 1

    f = f.drop(index=drop_idx)

    # 4. Trung dong: chep nguyen dong (sau cung de khong trung voi dong da xoa)
    free = [i for i in f.index if (f.at[i, "state"], f.at[i, "week"]) not in used]
    dup = rng.choice(free, size=n_dup, replace=False)
    for i in dup:
        add("duplicate", f.at[i, "state"], f.at[i, "week"], "*")
    f = pd.concat([f, f.loc[dup]], ignore_index=True)

    if mode == "consistent":
        f = recompute_derived(f, paths)
    f = f.sample(frac=1, random_state=seed).reset_index(drop=True)          # xao thu tu dong
    k = pd.DataFrame(key)
    k.insert(0, "error_id", range(1, len(k) + 1))
    return f, k


def recompute_derived(f, paths):
    """Tinh lai bien tre (theo tuan that, khong theo vi tri dong), wow, missing_*, cdc_level cho khop du lieu da sua."""
    f = f.copy()
    base = f.drop_duplicates(["state", "week"])
    for col, k in LAG_COLS.items():
        for i in range(1, k + 1):
            prev = base[["state", "week", col]].assign(week=lambda d: d.week + pd.Timedelta(weeks=i))
            prev = prev.rename(columns={col: "_p"})
            f = f.drop(columns=f"{col}_lag{i}").merge(prev, on=["state", "week"], how="left") \
                 .rename(columns={"_p": f"{col}_lag{i}"})
    f["wow_pct"] = _pct_change(pd.to_numeric(f.rate_flu), pd.to_numeric(f.rate_flu_lag1))
    f["ili_wow_pct"] = _pct_change(f.ili_pct, f.ili_pct_lag1)
    for flag, c in MISSING_FLAGS.items():
        f[flag] = f[c].isna()
    f["cdc_level"] = _cdc_level(paths, f.assign(rate_flu=pd.to_numeric(f.rate_flu)).reset_index(drop=True)) \
        .to_numpy()
    f["cdc_level_name"] = f["cdc_level"].map(lambda v: LEVEL_NAMES[int(v)] if pd.notna(v) else pd.NA).astype("string")
    return f


# ============================== Cham diem ==============================

def _vkey(v):
    return set(zip(v.rule, v.table, v.state.astype(object).fillna(""), v.week.astype(str), v.season.astype(object)
                   .fillna(""), v.column.astype(str)))


def score(viol_base, viol_bad, key):
    """Ghep vi pham moi voi dap an. Tra ve (key co cot caught/rules, bang vi pham moi co cot explained)."""
    base = _vkey(viol_base)
    v = viol_bad.copy()
    v["week"] = pd.to_datetime(v.week)
    tup = list(zip(v.rule, v.table, v.state.astype(object).fillna(""), v.week.astype(str),
                   v.season.astype(object).fillna(""), v.column.astype(str)))
    new = v[[t not in base for t in tup]].copy()

    cell = new[new.state.notna() & new.week.notna()]
    by_cell = cell.groupby(["state", "week", "column"]).rule.agg(lambda r: sorted(set(r)))
    by_row = cell.groupby(["state", "week"]).rule.agg(lambda r: sorted(set(r)))

    k = key.copy()
    k["week"] = pd.to_datetime(k.week)
    rules = []
    for r in k.itertuples():
        if r.column == "*":
            hit = by_row.get((r.state, r.week), [])
        else:
            hit = by_cell.get((r.state, r.week, r.column), [])
        rules.append(hit)
    k["rules"] = [", ".join(h) for h in rules]
    k["caught"] = [len(h) > 0 for h in rules]
    k["caught_internal"] = [any(x not in ("M01", "M02", "M03") for x in h) for h in rules]

    # vi pham moi co duoc dap an giai thich khong
    krow = set(zip(k.state, k.week))
    kweek = set(k.week)
    ks, _ = season_of(k.week)                                   # tinh tu tuan: dong bi xoa khong con trong fact_bad
    kseason = set(zip(k.state, ks))

    def explained(r):
        if pd.notna(r.state) and pd.notna(r.week):
            return (r.state, r.week) in krow
        if pd.notna(r.week):                                   # tong toan quoc / vung theo tuan
            return r.week in kweek
        if pd.notna(r.state) and pd.notna(r.season):           # roll-up mua
            return (r.state, r.season) in kseason
        return False

    new["explained"] = [explained(r) for r in new.itertuples()]
    return k, new


def load_tv4(paths):
    d = paths.data / "sandbox" / "corrupted"
    fp, kp = d / "fact_flu_week.parquet", d / "answer_key.csv"
    if fp.exists() and kp.exists():
        f = pd.read_parquet(fp)
        k = pd.read_csv(kp, parse_dates=["week"])
        k["column"] = k["column"].fillna("*").astype(str)
        return f, k, f"TV4 (`{fp.relative_to(paths.root).as_posix()}`)"
    return None, None, None


def run_injection_test(paths, out_md=None, seed=2026, extra_seeds=(1, 2, 3)):
    tables = load_business(paths)
    clean = load_clean(paths)
    hrd, _ = _hrd(paths)
    _, vb, _ = run_checks(paths, tables, clean, hrd)
    runs = []
    f4, k4, src = load_tv4(paths)
    if f4 is not None:
        runs.append(("tv4", src, f4, k4))
    for mode in ("raw", "consistent"):
        fb, kb = inject_errors(tables["fact_flu_week"], seed=seed, mode=mode, paths=paths)
        runs.append((mode, f"tự sinh, seed {seed}, chế độ `{mode}`", fb, kb))

    results = []
    for mode, src, fb, kb in runs:
        t = dict(tables, fact_flu_week=fb)
        summ, v, _ = run_checks(paths, t, clean, hrd)
        k, new = score(vb, v, kb)
        results.append(dict(mode=mode, source=src, key=k, new=new, summary=summ, rows=len(fb)))
        log.info("Chen loi [%s]: bat %d/%d loi, %d vi pham moi khong giai thich duoc",
                 mode, k.caught.sum(), len(k), (~new.explained).sum())
    # do on dinh: them vai seed, chi ghi so tong
    stab = []
    for sd in extra_seeds:
        for mode in ("raw", "consistent"):
            fb, kb = inject_errors(tables["fact_flu_week"], seed=sd, mode=mode, paths=paths)
            _, v, _ = run_checks(paths, dict(tables, fact_flu_week=fb), clean, hrd)
            k, new = score(vb, v, kb)
            fa = new[~new.explained]
            stab.append(dict(seed=sd, mode=mode, injected=len(k), caught=int(k.caught.sum()),
                             false_alarms=len(fa), fa_rules=", ".join(sorted(set(fa.rule)))))
    if out_md:
        _write(paths, results, vb, out_md, pd.DataFrame(stab))
    return results


def _write(paths, results, vb, out_md, stab=None):
    p = ["# Kiểm tra bộ kiểm tra chất lượng trên dữ liệu chèn lỗi", "",
         f"Sinh tự động bởi `python pipelines/02_warehouse.py --steps inject` lúc {dt.datetime.now():%Y-%m-%d %H:%M}. "
         "Code: `src/fluwatch/warehouse/inject.py` (chèn lỗi, chấm điểm), `quality.py` (các quy tắc).", "",
         "**Cách chấm.** Chạy toàn bộ quy tắc trên dữ liệu gốc (baseline: "
         f"{len(vb)} vi phạm có sẵn, là vấn đề thật của dữ liệu, xem `README.md`) và trên dữ liệu bị chèn lỗi. "
         "Chỉ tính vi phạm **mới**. Một lỗi trong đáp án là *bị bắt* khi có vi phạm mới trỏ đúng ô "
         "(bang, tuần, cột); lỗi cả dòng (dòng bị xóa, dòng trùng) cần vi phạm mới ở đúng (bang, tuần). "
         "Vi phạm mới không khớp đáp án nào là *báo động giả*.", ""]
    if not any(r["mode"] == "tv4" for r in results):
        p += ["> Chưa có bộ dữ liệu lỗi của TV4 (`data/sandbox/corrupted/fact_flu_week.parquet` + `answer_key.csv`). "
              "Bảng dưới dùng bộ tự sinh cùng 4 loại lỗi; khi TV4 giao file, chạy lại lệnh trên, "
              "kết quả của TV4 sẽ đứng đầu.", ""]
    p += ["## Tổng hợp", "",
          "| Bộ dữ liệu | Số lỗi chèn | Bắt được | Recall | Bắt chỉ bằng quy tắc nội bộ (không cần M01–M03) | "
          "Vi phạm mới | Báo động giả |", "| --- | --- | --- | --- | --- | --- | --- |"]
    for r in results:
        k, new = r["key"], r["new"]
        p.append(f"| {r['source']} | {len(k)} | {int(k.caught.sum())} | **{k.caught.mean() * 100:.1f}%** | "
                 f"{int(k.caught_internal.sum())} ({k.caught_internal.mean() * 100:.1f}%) | {len(new)} | "
                 f"{int((~new.explained).sum())} |")
    p += ["", "Chế độ `raw`: chỉ sửa ô dữ liệu, cột phái sinh giữ như cũ (lỗi xảy ra sau khi dựng bảng). "
          "Chế độ `consistent`: kẻ sửa tính lại mọi cột phái sinh cho khớp (biến trễ, `wow_pct`, `missing_*`, "
          "`cdc_level`), nên quy tắc nội bộ khó thấy hơn; lớp đối chiếu nguồn (M01–M03) vẫn phải bắt được.", ""]
    if stab is not None and len(stab):
        p += ["**Độ ổn định qua các seed khác** (mỗi seed chèn lỗi ở vị trí khác):", "",
              "| Seed | Chế độ | Lỗi chèn | Bắt được | Báo động giả | Quy tắc báo giả |", "| --- | --- | --- | --- | --- | --- |"]
        p += [f"| {r.seed} | `{r.mode}` | {r.injected} | {r.caught} ({r.caught / r.injected * 100:.1f}%) | "
              f"{r.false_alarms} | {r.fa_rules or '–'} |" for r in stab.itertuples()]
        if stab.false_alarms.sum():
            p += ["", "Báo động giả đến từ " + ", ".join(sorted(set(", ".join(stab.fa_rules).replace(" ", "").split(",")) - {""}))
                  + "; R09 là quy tắc mức *cảnh báo* suy dân số từ trung vị theo bang × mùa: "
                  "khi một khối tuần bị xóa, trung vị dịch nhẹ và một tuần vốn sát ngưỡng 5% bị gắn cờ.", ""]
        p += ["", "Không quy tắc mức *lỗi* nào báo giả." if stab.false_alarms.sum() else "Không có báo động giả ở mọi seed.", ""]
    for r in results:
        k, new = r["key"], r["new"]
        p += [f"## {r['source']}", "", f"Bảng lỗi: {r['rows']} dòng.", "",
              "| Loại lỗi | Ô/dòng chèn | Bắt được | Recall | Quy tắc bắt (số lỗi) |", "| --- | --- | --- | --- | --- |"]
        for et, d in k.groupby("error_type", sort=False):
            cnt = d.rules.str.split(", ").explode()
            cnt = cnt[cnt != ""].value_counts()
            p.append(f"| {ERROR_TYPES.get(et, et)} (`{et}`) | {len(d)} | {int(d.caught.sum())} | "
                     f"{d.caught.mean() * 100:.1f}% | " + ", ".join(f"{a} ({b})" for a, b in cnt.items()) + " |")
        miss = k[~k.caught]
        if len(miss):
            p += ["", "Lỗi **không** bắt được:", "", _md(miss[["error_id", "error_type", "state", "week", "column"]]
                                                       .head(30))]
        fa = new[~new.explained]
        if len(fa):
            p += ["", "Báo động giả:", "", _md(fa[["rule", "table", "state", "week", "season", "column", "detail"]]
                                               .head(20))]
        p.append("")
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(p), encoding="utf-8")
    # dap an cua bo tu sinh, de TV4 doi chieu dinh dang
    for r in results:
        if r["mode"] != "tv4":
            r["key"].to_csv(out_md.parent / f"injection_key_{r['mode']}.csv", index=False)
