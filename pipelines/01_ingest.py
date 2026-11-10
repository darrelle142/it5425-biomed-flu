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
    upload    scripts/upload_hf.py --tag               chi khi co --upload; gan tag vYYYY-MM-DD cho ban vua day

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
STEPS = {
    "download": [[S / "download_data.py"]],
    "verify": [[S / "verify_integrity.py"]],
    "delphi": [[S / "crawl_sample.py", "delphi"]],
    "weather": [[S / "crawl_cities_weather.py", "--update"]],
    "build": [[S / "profile_sample.py"], [S / "profile_dataset.py"], [S / "build_thresholds.py"],
              [S / "build_environment.py"]],
    "audit": [[S / "audit_data.py", "--strict"]],
}
DEFAULT = ["download", "verify", "delphi", "weather", "build", "audit"]
# Gioi han thoi gian moi lenh (phut): mot nguon bi treo khong keo ca job den het gio
TIMEOUT = {"download": 20, "verify": 10, "delphi": 25, "weather": 15, "build": 20, "audit": 5, "upload": 20}
# Buoc "mem": that bai thi canh bao va chay tiep voi so lieu cu (thoi tiet chi phuc vu RQ4, khong can moi tuan)
SOFT = {"weather"}


def run(cmd, minutes):
    t = time.time()
    print(f"\n>>> {' '.join(str(c.relative_to(ROOT)) if isinstance(c, Path) else c for c in cmd)}", flush=True)
    try:
        code = subprocess.run([sys.executable, *map(str, cmd)], cwd=ROOT, timeout=minutes * 60).returncode
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
    a = ap.parse_args()

    steps = a.steps or DEFAULT
    if not a.steps and (ROOT / "data" / "raw" / "manifest.jsonl").exists():
        steps = [s for s in steps if s != "download"]  # da co du lieu tren may
    for step in steps:
        for cmd in STEPS[step]:
            if run(cmd, TIMEOUT[step]) != 0:
                if step in SOFT:
                    warn(f"Buoc '{step}' that bai; chay tiep voi so lieu {step} cu (cac file da tai van duoc giu).")
                    break
                sys.exit(f"Buoc '{step}' that bai; dung lai, khong day len Hugging Face.")
    if a.upload:
        if "audit" not in steps:
            sys.exit("Chi day len khi da chay buoc audit trong cung lan chay.")
        if run([S / "upload_hf.py", "-m", a.message, "--tag"], TIMEOUT["upload"]) != 0:
            sys.exit("Day len Hugging Face that bai.")
    print("\nXong:", ", ".join(steps + (["upload"] if a.upload else [])))


if __name__ == "__main__":
    main()
