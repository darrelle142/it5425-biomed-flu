"""Pipeline cua TV1: thu thap du lieu moi, dung lai bang, kiem tra, roi (tuy chon) day len Hugging Face.

Cach chay (tu thu muc goc cua repo):
    python pipelines/01_ingest.py                     # tai Delphi + thoi tiet, dung bang, kiem tra (khong day)
    python pipelines/01_ingest.py --upload -m "..."   # nhu tren, dat thi day len HF
    python pipelines/01_ingest.py --steps build audit # chi chay mot so buoc

Cac buoc (theo thu tu):
    download  tai data/ tu Hugging Face (bo qua neu data/raw da co, tru khi chi dinh ro --steps download)
    verify    scripts/verify_integrity.py              du lieu tho tai ve phai khop manifest va Hugging Face;
              lech thi dung ngay (khong crawl, khong day gi len)
    delphi    scripts/crawl_sample.py delphi            ILINet, NHSN, NSSP, FluSurv, xet nghiem, NWSS
    weather   scripts/crawl_cities_weather.py --update  35 ngay gan nhat, 236 thanh pho (buoc mem: loi thi
              canh bao, dung so lieu thoi tiet cu, van chay tiep)
    build     profile_sample -> profile_dataset -> build_thresholds -> build_environment
    audit     scripts/audit_data.py --strict           cong chat luong: loi thi dung, khong day
    warehouse pipelines/02_warehouse.py --strict       kho clean/, business/ cua TV2 + 28 quy tac chat luong;
              quy tac muc loi khong dat thi dung, khong day (cong chat luong thu hai)
    analysis  pipelines/03_*.py, 04_*.py, 05_*.py      ket qua cua TV3-TV5 (chi chay file da co; buoc mem)
    merge     pipelines/02_warehouse.py --steps business olap quality --strict
              ghep ket qua vua chay cua TV3 (moc mua, cum) vao fact_season_summary, dim_state roi kiem tra lai;
              khong co buoc nay thi kho luon cham mot luot so voi file cua TV3
    --only-if-new: chi chay khi Delphi co so lieu moi hon ban da luu (lich tu chay dung)
    upload    scripts/upload_hf.py --tag [--derived]   chi khi co --upload; gan tag vYYYY-MM-DD; --derived khi kho
              vua duoc dung lai trong lan chay nay (day ca clean/, business/)
    backup    scripts/backup_hf.py                     sau upload: sao luu sang repo du phong rieng tu (buoc mem)

Moi lenh co gioi han thoi gian (TIMEOUT). Nguon CDC bi chan tu Viet Nam (WVAL, vaccine, trang nguong) do workflow crawl_cdc.yml tai rieng.
"""
import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
S = ROOT / "scripts"
P = ROOT / "pipelines"
STEPS = {
    "download": [[S / "download_data.py"]],
    "verify": [[S / "verify_integrity.py"]],
    "delphi": [[S / "crawl_sample.py", "delphi"]],
    "weather": [[S / "crawl_cities_weather.py", "--update"]],
    "build": [[S / "profile_sample.py"], [S / "profile_dataset.py"], [S / "build_thresholds.py"],
              [S / "build_environment.py"]],
    "audit": [[S / "audit_data.py", "--strict"]],
    "warehouse": [[P / "02_warehouse.py", "--strict"]],
    "analysis": [[f] for n in ("03", "04", "05") for f in sorted(P.glob(f"{n}_*.py"))],
    "merge": [[P / "02_warehouse.py", "--steps", "business", "olap", "quality", "--strict"]],
}
DEFAULT = ["download", "verify", "delphi", "weather", "build", "audit", "warehouse", "analysis", "merge"]
# Gioi han thoi gian moi lenh (phut): mot nguon bi treo khong keo ca job den het gio
TIMEOUT = {"download": 20, "verify": 10, "delphi": 25, "weather": 15, "build": 20, "audit": 5, "warehouse": 25, "analysis": 30, "merge": 10,
           "upload": 20, "backup": 30}
# Buoc "mem": that bai thi canh bao va chay tiep voi so lieu cu (thoi tiet chi phuc vu RQ4, khong can moi tuan)
# Phan tich cua TV3-TV5 cung la buoc mem: loi thi kho van duoc day len, file ket qua cu giu nguyen tren HF.
SOFT = {"weather", "analysis"}
# pipelines/02-05 import fluwatch.*: them src/ vao duong dan de chay duoc ca khi chua `pip install -e .`
# PYTHONIOENCODING: cac pipeline in tieng Viet; console Windows bang ma cu (cp1252...) se loi UnicodeEncodeError
ENV = {**os.environ, "PYTHONPATH": os.pathsep.join(filter(None, [str(ROOT / "src"), os.environ.get("PYTHONPATH")])),
       "PYTHONIOENCODING": "utf-8"}


def run(cmd, minutes):
    t = time.time()
    print(f"\n>>> {' '.join(str(c.relative_to(ROOT)) if isinstance(c, Path) else c for c in cmd)}", flush=True)
    try:
        code = subprocess.run([sys.executable, *map(str, cmd)], cwd=ROOT, timeout=minutes * 60, env=ENV).returncode
    except subprocess.TimeoutExpired:
        print(f"!!! qua {minutes} phut, dung lenh", flush=True)
        code = 124
    print(f"<<< ma thoat {code}, {time.time() - t:.0f} giay", flush=True)
    return code


def warn(msg):
    print(f"::warning::{msg}" if os.environ.get("GITHUB_ACTIONS") else f"CANH BAO: {msg}", flush=True)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as fh:
            fh.write(f"> ⚠️ {msg}\n\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--steps", nargs="+", choices=list(STEPS), help="chi chay cac buoc nay")
    ap.add_argument("--upload", action="store_true", help="day len Hugging Face sau khi audit dat")
    ap.add_argument("-m", "--message", default="Cap nhat hang tuan (pipelines/01_ingest.py)")
    ap.add_argument("--only-if-new", action="store_true",
                    help="chi chay khi Delphi co so lieu moi hon ban da luu (lich tu chay dung, tranh tai trung)")
    a = ap.parse_args()

    steps = a.steps or DEFAULT
    if not a.steps and (ROOT / "data" / "raw" / "manifest.jsonl").exists():
        steps = [s for s in steps if s != "download"]  # da co du lieu tren may
    if a.only_if_new:
        sys.path.insert(0, str(ROOT / "src"))
        from fluwatch.ingest import delphi
        from fluwatch.ingest.paths import Paths
        changed, note = delphi.new_updates(Paths(ROOT))
        if not changed:
            warn(f"Delphi chua co so lieu moi ({note}); bo qua lan chay nay.")
            return
        print(f"Delphi co so lieu moi: {note}", flush=True)
    for step in steps:
        for cmd in STEPS[step]:
            if run(cmd, TIMEOUT[step]) != 0:
                if step in SOFT:  # canh bao roi chay lenh tiep theo (vd. 04 loi thi 05 van chay)
                    name = cmd[0].name if isinstance(cmd[0], Path) else step
                    warn(f"Buoc '{step}' ({name}) that bai; chay tiep, giu ket qua cu tren Hugging Face.")
                    continue
                sys.exit(f"Buoc '{step}' that bai; dung lai, khong day len Hugging Face.")
    if a.upload:
        if "audit" not in steps:
            sys.exit("Chi day len khi da chay buoc audit trong cung lan chay.")
        derived = ["--derived"] if {"warehouse", "merge"} & set(steps) else []  # kho chi duoc day khi vua dung lai
        if run([S / "upload_hf.py", "-m", a.message, "--tag", *derived], TIMEOUT["upload"]) != 0:
            sys.exit("Day len Hugging Face that bai.")
        # Sao luu sang repo du phong: buoc mem, loi thi canh bao (ban chinh da len HF)
        if os.environ.get("GITHUB_ACTIONS") and not os.environ.get("HF_BACKUP_TOKEN"):
            warn("Chua co secret HF_BACKUP_TOKEN: bo qua sao luu sang repo du phong.")
        elif run([S / "backup_hf.py"], TIMEOUT["backup"]) != 0:
            warn("Sao luu sang repo du phong that bai; ban chinh van da cap nhat. Chay lai scripts/backup_hf.py.")
    print("\nXong:", ", ".join(steps + (["upload", "backup"] if a.upload else [])))


if __name__ == "__main__":
    main()
