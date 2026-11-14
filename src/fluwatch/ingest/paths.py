"""Duong dan chuan cua kho du lieu, tinh tu thu muc goc cua lenh chay."""
import datetime as dt
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Paths:
    """Moi duong dan suy ra tu root (thu muc goc repo, hoac restore_test/ khi chay thu khoi phuc)."""
    root: Path

    @classmethod
    def from_script(cls, script_file):
        """Paths cho mot lenh chay nam o <root>/scripts/ hoac <root>/pipelines/."""
        return cls(Path(script_file).resolve().parents[1])

    @property
    def data(self):
        return self.root / "data"

    @property
    def raw(self):
        return self.data / "raw"

    @property
    def reference(self):
        return self.data / "reference"

    @property
    def samples(self):
        return self.data / "samples"

    @property
    def manifest(self):
        return self.raw / "manifest.jsonl"

    @property
    def hf_revision(self):
        return self.data / ".hf_revision"


def today():
    """Ngay tai theo gio may (ten thu muc raw/<nguon>/<ngay>/)."""
    return dt.date.today().isoformat()
