"""Hugging Face: dinh danh file, ban da tai (data/.hf_revision), ke hoach day len va sao luu, tag phien ban.

Nguyen tac bao toan: raw/ chi duoc them (khong ghi de, khong xoa); manifest chi duoc them dong;
moi commit dua tren commit da tai (parent_commit) de khong ghi de khi co nguoi day chen giua.
"""
import datetime as dt
import hashlib
import json
from pathlib import Path

MAIN_REPO = "DragonBornRay/FluDataset"
BACKUP_REPO = "DragonBornRay/FluDataset-backup"
MANIFEST = "raw/manifest.jsonl"  # duong dan trong repo HF (= data/ tren may)
SKIP_UPLOAD = ("samples/preview_",)


class Refused(Exception):
    """Thao tac vi pham nguyen tac bao toan; khong lam gi ca."""


def sha256(b):
    return hashlib.sha256(b).hexdigest()


def git_blob_sha1(b):
    """File nho (khong qua LFS) duoc HF dinh danh bang sha1 kieu git."""
    return hashlib.sha1(b"blob %d\0" % len(b) + b).hexdigest()


def same_as_remote(sibling, b):
    """Noi dung b giong file tren HF (sibling lay voi files_metadata=True)?"""
    return sibling.lfs.sha256 == sha256(b) if sibling.lfs else sibling.blob_id == git_blob_sha1(b)


def read_revision(paths):
    """(repo, commit) cua ban data/ dang co tren may, do download_data.py ghi."""
    if not paths.hf_revision.exists():
        raise Refused("Thieu data/.hf_revision: chay scripts/download_data.py truoc de biet ban HF goc.")
    repo, sha = paths.hf_revision.read_text(encoding="utf-8").split()
    return repo, sha


def write_revision(paths, repo, sha):
    paths.hf_revision.write_text(f"{repo} {sha}\n", encoding="utf-8")


def plan_upload(api, paths, repo, parent, token=None):
    """Nhung file can day len repo chinh so voi commit `parent`. Tra ve (so dong manifest moi, danh sach file).

    - Manifest tren may phai bat dau bang dung manifest tren HF (chi them dong).
    - File raw/ moi: duoc ghi trong cac dong manifest moi, chua co tren HF; da co thi tu choi (khong ghi de).
    - samples/*.csv*, reference/*.csv, README.md: day khi noi dung khac HF.
    """
    from huggingface_hub import hf_hub_download
    rem = Path(hf_hub_download(repo, MANIFEST, repo_type="dataset", revision=parent, token=token)
               ).read_text(encoding="utf-8").splitlines()
    loc = paths.manifest.read_text(encoding="utf-8").splitlines()
    if loc[:len(rem)] != rem:
        raise Refused("manifest tren may khong bat dau bang manifest tren HF (co dong bi sua hoac xoa).")
    new_lines = [json.loads(x) for x in loc[len(rem):] if x.strip()]

    remote = {s.rfilename: s for s in api.dataset_info(repo, revision=parent, files_metadata=True).siblings}
    listed = []
    for m in new_lines:
        rel = (m.get("file") or "").removeprefix("data/")
        if not rel or rel in listed:
            continue
        if rel in remote:
            raise Refused(f"Dong manifest moi tro toi {rel} nhung file nay da co tren HF; khong ghi de.")
        if not (paths.data / rel).exists():
            raise Refused(f"manifest ghi {rel} nhung file khong co tren may.")
        listed.append(rel)
    for p in [*sorted(paths.samples.glob("*.csv*")), *sorted(paths.reference.glob("*.csv")), paths.data / "README.md"]:
        rel = p.relative_to(paths.data).as_posix()
        if rel.startswith(SKIP_UPLOAD):
            continue
        r = remote.get(rel)
        if r is None or not same_as_remote(r, p.read_bytes()):
            listed.append(rel)
    if new_lines:
        listed.append(MANIFEST)
    return len(new_lines), listed


def plan_backup(src_api, dst_api, paths, repo, revision, backup_repo):
    """Nhung file cua repo chinh (o `revision`) ma repo du phong chua co hoac khac. Tra ve (moi file, can chep).

    File raw/ (tru manifest) da co tren repo du phong ma khac noi dung thi tu choi (khong ghi de).
    """
    main_files = [s.rfilename for s in src_api.dataset_info(repo, revision=revision).siblings]
    backup = {s.rfilename: s for s in dst_api.dataset_info(backup_repo, files_metadata=True).siblings}
    todo, conflicts = [], []
    for rel in main_files:
        p = paths.data / rel
        if not p.exists():
            raise Refused(f"Thieu {rel} tren may: chay download_data.py (ban day du) truoc khi sao luu.")
        s = backup.get(rel)
        if s is None:
            todo.append(rel)
        elif not same_as_remote(s, p.read_bytes()):
            (conflicts if rel.startswith("raw/") and rel != MANIFEST else todo).append(rel)
    if conflicts:
        raise Refused(f"Repo du phong co {len(conflicts)} file raw/ khac ban chinh (vd. {conflicts[:3]}); khong ghi de.")
    todo.sort(key=lambda r: r == MANIFEST)  # manifest sau cung: repo luon co du file ma manifest cua no ghi
    return main_files, todo


def tag_version(api, repo, oid, message):
    """Gan tag vYYYY-MM-DD (UTC; trung ngay thi -2, -3...) cho commit. Tra ve ten tag."""
    have = {t.name for t in api.list_repo_refs(repo, repo_type="dataset").tags}
    base = f"v{dt.datetime.now(dt.timezone.utc):%Y-%m-%d}"
    name = base if base not in have else next(f"{base}-{i}" for i in range(2, 100) if f"{base}-{i}" not in have)
    api.create_tag(repo, tag=name, revision=oid, tag_message=message, repo_type="dataset")
    return name
