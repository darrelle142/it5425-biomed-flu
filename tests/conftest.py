"""Cho phep chay `python -m pytest tests` ma khong can `pip install -e .`."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
