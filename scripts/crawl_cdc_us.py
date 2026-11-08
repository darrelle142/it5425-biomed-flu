"""Tai cac nguon CDC bi chan tu Viet Nam (403): nuoc thai WVAL, do phu vaccine, trang nguong HRD.

Chay tren GitHub Actions (may o My) theo lich, hoac tren may ca nhan dang bat VPN My.
Ke hoach: docs/ke_hoach_tu_dong_crawl_cdc.md

Cach chay (tu thu muc goc cua repo):
    python scripts/crawl_cdc_us.py --dry-run     # tai va kiem tra, khong ghi file, khong day len HF
    python scripts/crawl_cdc_us.py               # luu vao data/raw/ va manifest tren may
    python scripts/crawl_cdc_us.py --upload      # luu va day file moi + manifest len Hugging Face
                                                 # (can bien moi truong HF_TOKEN co quyen write)

Quy tac:
- Tra id bo du lieu tren data.cdc.gov theo ten (Socrata catalog); ep id bang --id-wval / --id-vax.
- Kiem tra cot so voi file nhom tai ngay 01/11/2026; thieu cot thi khong luu.
- sha256 giong ban moi nhat trong manifest thi khong luu lai, chi ghi mot dong "unchanged".
- Bi 403 hoac loi thi ghi vao manifest va thoat voi ma 1; khong thu vuot chan.
"""
import argparse
import csv
import datetime as dt
import gzip
import hashlib
import io
import json
import os
import shutil
import socket
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW = DATA / "raw"
MANIFEST_IN_REPO = "raw/manifest.jsonl"  # duong dan trong repo Hugging Face (= data/ tren may)
HF_REPO = os.environ.get("HF_REPO") or "tdu175/FluDataset"  # doi repo: bien moi truong HF_REPO
NOW = dt.datetime.now(dt.timezone.utc)
TODAY = NOW.date().isoformat()
UA = "it5425-biomed-flu-crawler/1.0 (+https://github.com/darrelle142/it5425-biomed-flu)"

SOCRATA = [
    {"key": "wval", "source": "cdc_wastewater_wval",
     "name": "CDC Wastewater Viral Activity Level for SARS-CoV-2, Influenza A and RSV",
     "columns": ["State/Territory", "Counties_Served", "Site", "Population_Served", "Source", "Site_WVAL",
                 "Site_WVAL_Category", "Date_Included_In_WVAL", "Week_End", "Pathogen_Target", "date_updated"]},
    {"key": "vax", "source": "cdc_fluvax_coverage",
     "name": "Influenza Vaccination Coverage for All Ages (6+ Months)",
     "columns": ["Vaccine", "Geography Type", "Geography", "FIPS", "Season/Survey Year", "Month",
                 "Dimension Type", "Dimension", "Estimate (%)", "95% CI (%)", "Sample Size"]},
]
METHODS = {"key": "methods", "source": "cdc_methods", "file": "hrd_data_methods.html.gz",
           "url": "https://www.cdc.gov/nhsn/psc/hospital-respiratory-reporting/data-methods.html",
           "must_contain": ["Very High", "threshold"]}


def fetch(url, timeout=900):
    """GET mot URL. Tra ve (ma HTTP, noi dung byte); khong thu lai khi bi tu choi."""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as err:
        return err.code, err.read()
    except Exception as err:  # loi mang
        return 0, str(err).encode()


def find_dataset_id(name):
    """Tim id tren data.cdc.gov theo ten chinh xac. Tra ve (id, thoi diem cap nhat du lieu) hoac (None, loi)."""
    q = urllib.parse.urlencode({"domains": "data.cdc.gov", "search_context": "data.cdc.gov",
                                "q": name, "only": "dataset", "limit": 50})
    status, body = fetch(f"https://api.us.socrata.com/api/catalog/v1?{q}", timeout=60)
    if status != 200:
        return None, f"catalog HTTP {status}"
    try:
        results = json.loads(body)["results"]
    except Exception as err:
        return None, f"catalog tra ve khong phai JSON: {err}"
    hits = [r["resource"] for r in results if r["resource"]["name"].strip().lower() == name.lower()]
    if len(hits) != 1:
        found = [r["resource"]["name"] for r in results[:5]]
        return None, f"{len(hits)} bo trung ten; 5 ket qua dau: {found}"
    return hits[0]["id"], hits[0].get("data_updated_at")


def rows_updated_at(ds_id):
    status, body = fetch(f"https://data.cdc.gov/api/views/{ds_id}.json", timeout=60)
    if status != 200:
        return None
    try:
        ts = json.loads(body).get("rowsUpdatedAt")
        return dt.datetime.fromtimestamp(ts, dt.timezone.utc).isoformat(timespec="seconds") if ts else None
    except Exception:
        return None


def check_columns(body, expected):
    header = next(csv.reader(io.StringIO(body[:20000].decode("utf-8-sig", "replace").splitlines()[0])))
    missing = [c for c in expected if c not in header]
    return missing, header


def latest_sha(manifest_lines, source):
    for m in reversed(manifest_lines):
        if m.get("source") == source and m.get("sha256") and (m.get("file") or m.get("unchanged")):
            return m["sha256"]
    return None


def read_manifest(path):
    if not path or not Path(path).exists():
        return []
    return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()]


def hf_manifest(repo, token):
    """Tai manifest moi nhat tu Hugging Face. Tra ve (duong dan tam, commit sha)."""
    from huggingface_hub import HfApi, hf_hub_download
    sha = HfApi(token=token).dataset_info(repo).sha
    p = hf_hub_download(repo, MANIFEST_IN_REPO, repo_type="dataset", revision=sha, token=token)
    tmp = Path(tempfile.mkdtemp()) / "manifest.jsonl"
    shutil.copy(p, tmp)
    return tmp, sha


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="tai va kiem tra, khong ghi gi")
    ap.add_argument("--upload", action="store_true", help="day file moi va manifest len Hugging Face")
    ap.add_argument("--repo", default=HF_REPO, help="repo dataset tren Hugging Face (mac dinh: bien HF_REPO)")
    ap.add_argument("--id-wval", help="ep id Socrata cho WVAL (bo qua tra cuu theo ten)")
    ap.add_argument("--id-vax", help="ep id Socrata cho vaccine")
    ap.add_argument("--only", nargs="+", choices=["wval", "vax", "methods"], help="chi chay cac nguon nay")
    a = ap.parse_args()
    if a.dry_run and a.upload:
        ap.error("--dry-run va --upload khong dung cung nhau")
    token = os.environ.get("HF_TOKEN")
    if a.upload and not token:
        sys.exit("Thieu bien moi truong HF_TOKEN (token Hugging Face co quyen write).")
    runner = "github-actions" if os.environ.get("GITHUB_ACTIONS") == "true" else socket.gethostname()

    # Manifest goc: ban tren HF khi upload (tranh ghi de dong cua nguoi khac), nguoc lai dung ban tren may
    parent = None
    if a.upload or not (RAW / "manifest.jsonl").exists():
        base_path, parent = hf_manifest(a.repo, token)
        print(f"Manifest lay tu Hugging Face, commit {parent[:8]}")
    else:
        base_path = RAW / "manifest.jsonl"
        print(f"Manifest tren may: {base_path.relative_to(ROOT)}")
    base = read_manifest(base_path)

    new_lines, new_files, report, failed = [], [], [], False
    overrides = {"wval": a.id_wval, "vax": a.id_vax}

    def record(src, url, status, body, file_rel=None, unchanged=False, **extra):
        line = {"source": src, "file": file_rel, "url": url, "fetched_at": NOW.isoformat(timespec="seconds"),
                "http_status": status, "bytes": len(body),
                "sha256": hashlib.sha256(body).hexdigest() if status == 200 else None, "runner": runner}
        if unchanged:
            line["unchanged"] = True
        line.update({k: v for k, v in extra.items() if v is not None})
        new_lines.append(line)

    def save(src, filename, body, gz=False):
        folder = RAW / src / TODAY
        path = folder / filename
        if path.exists():  # chay 2 lan trong ngay va du lieu doi: them gio de khong ghi de
            stem, dot, ext = filename.partition(".")
            path = folder / f"{stem}_{NOW:%H%M%S}{dot}{ext}"
        if not a.dry_run:
            folder.mkdir(parents=True, exist_ok=True)
            path.write_bytes(gzip.compress(body) if gz else body)
            new_files.append(path)
        return str(path.relative_to(ROOT)).replace("\\", "/")

    for ds in SOCRATA:
        if a.only and ds["key"] not in a.only:
            continue
        print(f"\n== {ds['source']}")
        ds_id, info = (overrides[ds["key"]], "id ep tu tham so") if overrides[ds["key"]] else find_dataset_id(ds["name"])
        if not ds_id:
            print(f"  LOI tra id: {info}")
            record(ds["source"], None, 0, info.encode(), note="khong tra duoc id")
            report.append((ds["source"], "LOI", f"khong tra duoc id: {info}"))
            failed = True
            continue
        url = f"https://data.cdc.gov/api/views/{ds_id}/rows.csv?accessType=DOWNLOAD"
        print(f"  id {ds_id} ({info}); tai {url}")
        status, body = fetch(url)
        upd = rows_updated_at(ds_id) if status == 200 else None
        if status != 200:
            print(f"  LOI HTTP {status}: {body[:200]!r}")
            record(ds["source"], url, status, body, dataset_id=ds_id)
            report.append((ds["source"], "LOI", f"HTTP {status}"))
            failed = True
            continue
        missing, header = check_columns(body, ds["columns"])
        if missing:
            print(f"  LOI cot: thieu {missing}; header nhan duoc {header}")
            record(ds["source"], url, "bad_schema", body, dataset_id=ds_id, note=f"thieu cot {missing}")
            report.append((ds["source"], "LOI", f"thieu cot {missing}"))
            failed = True
            continue
        sha = hashlib.sha256(body).hexdigest()
        n_rows = body.count(b"\n") - 1
        if sha == latest_sha(base + new_lines, ds["source"]):
            print(f"  khong doi so voi ban moi nhat ({len(body):,} bytes)")
            record(ds["source"], url, 200, body, unchanged=True, dataset_id=ds_id, rows_updated_at=upd)
            report.append((ds["source"], "khong doi", f"{n_rows:,} dong, CDC cap nhat {upd}"))
            continue
        fname = f"{ds['name'].replace(' ', '_')}_{NOW:%Y%m%d}.csv"
        rel = save(ds["source"], fname, body)
        print(f"  {'(dry-run) se luu' if a.dry_run else 'da luu'} {rel} ({len(body):,} bytes, {n_rows:,} dong)")
        record(ds["source"], url, 200, body, file_rel=rel, dataset_id=ds_id, rows_updated_at=upd)
        report.append((ds["source"], "MOI", f"{n_rows:,} dong, CDC cap nhat {upd}"))

    if not a.only or "methods" in a.only:
        m = METHODS
        print(f"\n== {m['source']}")
        status, body = fetch(m["url"], timeout=120)
        text = body.decode("utf-8", "replace")
        if status != 200 or not all(s.lower() in text.lower() for s in m["must_contain"]):
            why = f"HTTP {status}" if status != 200 else "trang khong con bang nguong"
            print(f"  LOI: {why}")
            record(m["source"], m["url"], status if status != 200 else "bad_content", body)
            report.append((m["source"], "LOI", why))
            failed = True
        elif hashlib.sha256(body).hexdigest() == latest_sha(base + new_lines, m["source"]):
            print("  khong doi")
            record(m["source"], m["url"], 200, body, unchanged=True)
            report.append((m["source"], "khong doi", ""))
        else:
            rel = save(m["source"], m["file"], body, gz=True)
            print(f"  {'(dry-run) se luu' if a.dry_run else 'da luu'} {rel}; nho chay lai build_thresholds.py")
            record(m["source"], m["url"], 200, body, file_rel=rel)
            report.append((m["source"], "MOI", "trang thay doi: kiem tra bang nguong (build_thresholds.py)"))

    # Ghi manifest va day len HF
    if a.dry_run:
        print("\n(dry-run) khong ghi manifest, khong day len Hugging Face")
    else:
        merged = base_path if a.upload else RAW / "manifest.jsonl"
        if not a.upload and Path(base_path).resolve() != merged.resolve():  # may chua co manifest: chep ban HF
            merged.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(base_path, merged)
        with open(merged, "a", encoding="utf-8") as fh:
            for line in new_lines:
                fh.write(json.dumps(line, ensure_ascii=False) + "\n")
        if a.upload:
            from huggingface_hub import CommitOperationAdd, HfApi
            ops = [CommitOperationAdd(path_in_repo=MANIFEST_IN_REPO, path_or_fileobj=str(merged))]
            ops += [CommitOperationAdd(path_in_repo=str(p.relative_to(DATA)).replace("\\", "/"), path_or_fileobj=str(p))
                    for p in new_files]
            msg = f"Tu dong tai CDC {TODAY} ({runner}): " + ", ".join(f"{s} {k}" for s, k, _ in report)
            info = HfApi(token=token).create_commit(a.repo, ops, commit_message=msg, repo_type="dataset",
                                                    parent_commit=parent)
            print(f"\nDa day len Hugging Face: {info.commit_url}")
            local = RAW / "manifest.jsonl"
            if local.exists() and local.resolve() != Path(merged).resolve():
                with local.open("a", encoding="utf-8") as fh:  # dong bo dong moi vao manifest tren may
                    for line in new_lines:
                        fh.write(json.dumps(line, ensure_ascii=False) + "\n")

    table = "| Nguon | Ket qua | Ghi chu |\n| --- | --- | --- |\n" + "\n".join(f"| {s} | {k} | {n} |" for s, k, n in report)
    print("\n" + table)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as fh:
            fh.write(f"## Tai nguon CDC {TODAY}{' (dry-run)' if a.dry_run else ''}\n\n{table}\n")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
