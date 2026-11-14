"""Luu du lieu tho nguyen trang va ghi nhat ky nguon goc (raw/manifest.jsonl)."""
import datetime as dt
import gzip
import hashlib
import json
from pathlib import Path

from .paths import today


def read_manifest(path):
    """Cac dong cua manifest (list dict); file chua co thi tra ve []."""
    p = Path(path)
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


class RawStore:
    """Kho raw/<nguon>/<ngay tai>/ cua mot Paths; moi lan luu them dung mot dong vao manifest."""

    def __init__(self, paths, day=None):
        self.paths = paths
        self.day = day or today()

    def save(self, source, name, url, status, body, gz=True):
        """Luu noi dung (chi khi HTTP 200) va ghi manifest (ca khi loi). Tra ve True neu da luu file.

        - Nen gzip neu gz=True; sha256 trong manifest la cua noi dung goc (truoc khi nen).
        - Khong bao gio ghi de: trong ngay da co file cung ten (tai lai, hoac ban vua tai tu Hugging Face)
          thi them gio phut giay UTC vao ten, vi du ili__state_113400.csv.gz.
        """
        folder = self.paths.raw / source / self.day
        folder.mkdir(parents=True, exist_ok=True)
        ok = status == 200
        path = folder / (name + (".gz" if gz else ""))
        if ok and path.exists():
            stem, dot, ext = path.name.partition(".")
            path = folder / f"{stem}_{dt.datetime.now(dt.timezone.utc):%H%M%S}{dot}{ext}"
        if ok:
            path.write_bytes(gzip.compress(body) if gz else body)
        with self.paths.manifest.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "source": source,
                "file": path.relative_to(self.paths.root).as_posix() if ok else None,
                "url": url,
                "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                "http_status": status,
                "bytes": len(body),
                "sha256": hashlib.sha256(body).hexdigest() if ok else None,
            }, ensure_ascii=False) + "\n")
        print(f"{status} {len(body):>11,} bytes  {source}/{name}", flush=True)
        return ok

    def have(self, source, filename):
        """Da co file nay o bat ky ngay tai nao chua (ten day du, vd. 'ak__juneau.json.gz')."""
        return any((self.paths.raw / source).glob(f"*/{filename}"))
