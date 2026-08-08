"""Test setup: make the repo root importable so `firstboot` resolves."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # hermes-os/
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
