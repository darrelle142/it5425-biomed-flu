"""Khoi phuc du lieu tu repo du phong va chay thu: tai ve -> kiem tra toan ven -> dung lai bang -> so sanh.

Cach chay (tu thu muc goc cua repo):
    python scripts/restore.py                          # ban moi nhat cua repo du phong, vao thu muc restore_test/
    python scripts/restore.py --revision v2026-11-14   # dung mot phien ban da gan tag
    python scripts/restore.py --repo DragonBornRay/FluDataset   # khoi phuc tu repo chinh

Khong dung toi data/ cua repo: moi thu nam trong --out (mac dinh restore_test/, da nam trong .gitignore).
Khi can khoi phuc that (repo chinh hong hoac mat): chay lenh nay, kiem tra ket qua "DAT", roi
    hf upload DragonBornRay/FluDataset restore_test/data . --repo-type dataset --exclude ".cache/*" --exclude ".hf_revision"
Bien moi truong HF_BACKUP_TOKEN (doc repo du phong rieng tu); khong dat thi dung tai khoan da `hf auth login`.
Ket qua ghi vao <out>/restore_results.json.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd
from huggingface_hub import HfApi, snapshot_download

ROOT = Path(__file__).resolve().parents[1]
BUILD = ["profile_sample.py", "profile_dataset.py", "build_thresholds.py", "build_environment.py"]
TABLES = ["state_week_sample.csv.gz", "cdc_level_state_week.csv.gz", "wval_state_week.csv.gz",
          "vaccine_state_season.csv", "weather_state_week.csv.gz", "epa_pm25_state_week.csv.gz"]


def fresh_dir(out):
    """Thu muc trong cho lan chay thu. Xoa ban cu; neu bi khoa (vd. OneDrive dang dong bo) thi dung ten moi."""
    for _ in range(3):
        if not out.exists():
            return out
        shutil.rmtree(out, ignore_errors=True)
        time.sleep(2)
    alt = out.with_name(f"{out.name}_{time.strftime('%Y%m%d_%H%M%S')}")
    print(f"Khong xoa duoc {out} (file dang bi khoa); dung {alt}", flush=True)
    return alt


def compare(a, b):
    """Hai bang giong nhau (so thuc sai lech toi 1e-9 tuong doi)? Tra ve (dat, ghi chu)."""
    x, y = pd.read_csv(a), pd.read_csv(b)
    if list(x.columns) != list(y.columns) or len(x) != len(y):
        return False, f"cot/dong khac: {x.shape} vs {y.shape}"
    try:
        pd.testing.assert_frame_equal(x, y, check_exact=False, rtol=1e-9, check_dtype=False)
        return True, f"{len(x):,} dong khop"
    except AssertionError as err:
        return False, str(err).splitlines()[0][:200]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=os.environ.get("HF_BACKUP_REPO") or "DragonBornRay/FluDataset-backup")
    ap.add_argument("--revision", default=None, help="tag hoac ma commit; mac dinh ban moi nhat")
    ap.add_argument("--out", default=str(ROOT / "restore_test"))
    a = ap.parse_args()
    token = os.environ.get("HF_BACKUP_TOKEN") or None
    out = Path(a.out)
    t0 = time.time()
    report = {"repo": a.repo, "revision_requested": a.revision, "steps": []}

    def step(name, ok, note=""):
        report["steps"].append({"step": name, "ok": ok, "note": note, "seconds": round(time.time() - t0)})
        print(f"[{'DAT' if ok else 'LOI'}] {name} {note}", flush=True)
        return ok

    # 1. Tai ve thu muc rieng, kem ban sao scripts/ va src/ de cac script doc dung data/ moi
    out = fresh_dir(out)
    for d in ("scripts", "src"):  # ban sao lenh chay + thu vien: moi duong dan tinh tu out/
        shutil.copytree(ROOT / d, out / d, ignore=shutil.ignore_patterns("__pycache__"))
    sha = HfApi(token=token).dataset_info(a.repo, revision=a.revision).sha
    snapshot_download(a.repo, repo_type="dataset", revision=sha, local_dir=out / "data", token=token)
    (out / "data" / ".hf_revision").write_text(f"{a.repo} {sha}\n", encoding="utf-8")
    report["revision"] = sha
    n = sum(1 for p in (out / "data").rglob("*") if p.is_file() and ".cache" not in p.parts)
    step("tai_ve", True, f"{n} file tu {a.repo}@{sha[:8]}")

    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    if token:
        env["HF_TOKEN"] = token  # verify_integrity doc repo du phong bang token nay

    def run(script, *args):
        r = subprocess.run([sys.executable, str(out / "scripts" / script), *args], cwd=out, env=env,
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        return r.returncode, (r.stdout + r.stderr).strip().splitlines()[-1:] or [""]

    # 2. Kiem tra toan ven ban vua khoi phuc (manifest <-> file <-> repo du phong)
    code, last = run("verify_integrity.py")
    ok = step("kiem_tra_toan_ven", code == 0, last[0])

    # 3. Dung lai cac bang tu raw/ va so voi bang da luu trong ban sao luu
    if ok:
        saved = out / "samples_da_luu"
        shutil.copytree(out / "data" / "samples", saved)
        for s in BUILD:
            code, last = run(s)
            ok = step(f"dung_lai {s}", code == 0, last[0] if code else "") and ok
        report["tables"] = {}
        for t in TABLES:
            same, note = compare(saved / t, out / "data" / "samples" / t)
            report["tables"][t] = {"ok": same, "note": note}
            ok = step(f"so_sanh {t}", same, note) and ok

    report["ok"] = ok
    report["seconds"] = round(time.time() - t0)
    (out / "restore_results.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n{'DAT' if ok else 'KHONG DAT'}: khoi phuc {a.repo}@{sha[:8]} trong {report['seconds']} giay; "
          f"chi tiet {out / 'restore_results.json'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
