"""Kiem tra toan ven du lieu tho: manifest <-> file tren may <-> file tren Hugging Face."""
import gzip
import json

from .hf import read_revision, same_as_remote, sha256
from .store import read_manifest


def verify(paths, remote=True, token=None):
    """Tra ve {"summary", "problems", "warnings"}; co problems nghia la khong dat.

    1. Moi dong manifest co file: file ton tai va sha256 khop (file .gz so ca noi dung da giai nen,
       vi manifest ghi sha cua noi dung goc; file tai tay .zip/.xlsx/.csv so nguyen trang).
    2. Moi file trong raw/ deu co trong manifest.
    3. (remote) ban tren may giong het ban tren HF o commit da tai: cung danh sach file raw/, cung noi dung.
    Canh bao (khong tinh loi) tai_lai_khong_luu: mot duong dan bi ghi nhieu dong; file khop mot dong
    (HF khong ghi de), cac lan tai sau khong duoc luu. Loi nay da sua ngay 10/11/2026.
    """
    lines = read_manifest(paths.manifest)
    logged = {}
    for m in lines:
        if m.get("file"):
            logged.setdefault(m["file"].removeprefix("data/"), []).append(m)
    problems = {"thieu_file": [], "sha_lech": [], "file_la": [], "khac_hf": [], "chi_co_tren_hf": [], "chi_co_tren_may": []}
    warnings = {"tai_lai_khong_luu": []}

    for rel, ms in logged.items():
        p = paths.data / rel
        if not p.exists():
            problems["thieu_file"].append(rel)
            continue
        shas = {m["sha256"] for m in ms if m.get("sha256")}
        if not shas:
            continue
        b = p.read_bytes()
        got = {sha256(b)} | ({sha256(gzip.decompress(b))} if p.suffix == ".gz" else set())
        if not got & shas:
            problems["sha_lech"].append(rel)
        elif len(shas) > 1:
            warnings["tai_lai_khong_luu"].append(rel)

    on_disk = sorted(p.relative_to(paths.data).as_posix() for p in paths.raw.glob("*/*/*") if p.is_file())
    problems["file_la"] = [rel for rel in on_disk if rel not in logged]

    revision = None
    if remote:
        from huggingface_hub import HfApi
        repo, revision = read_revision(paths)
        info = HfApi(token=token).dataset_info(repo, revision=revision, files_metadata=True)
        rem = {s.rfilename: s for s in info.siblings if s.rfilename.startswith("raw/")}
        local = set(on_disk) | {"raw/manifest.jsonl"} | {p.relative_to(paths.data).as_posix() for p in paths.raw.glob("*.json")}
        problems["chi_co_tren_hf"] = sorted(set(rem) - local)
        problems["chi_co_tren_may"] = sorted(local - set(rem))
        for rel in sorted(local & set(rem)):
            if not same_as_remote(rem[rel], (paths.data / rel).read_bytes()):
                problems["khac_hf"].append(rel)

    summary = {"revision": revision, "manifest_lines": len(lines), "files_logged": len(logged),
               "files_on_disk": len(on_disk), **{k: len(v) for k, v in problems.items()},
               **{f"canh_bao_{k}": len(v) for k, v in warnings.items()}}
    return {"summary": summary, "problems": problems, "warnings": warnings}


def write_report(paths, result):
    paths.samples.mkdir(parents=True, exist_ok=True)
    out = paths.samples / "integrity_results.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    return out
