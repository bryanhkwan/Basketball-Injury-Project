"""Where the project keeps its files. Everything under data/ can be rebuilt from the sources."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
RAW = DATA / "raw"
SDV = RAW / "sportsdataverse"          # season parquet files mirrored from stats.nba.com and ESPN
REPORTS_RAW = RAW / "injury_reports"   # official NBA injury report PDFs, one per game day
INTERIM = DATA / "interim"
PROCESSED = DATA / "processed"
OUTPUTS = ROOT / "outputs"


def ensure_dirs() -> None:
    for path in (SDV, REPORTS_RAW, INTERIM, PROCESSED, OUTPUTS):
        path.mkdir(parents=True, exist_ok=True)
