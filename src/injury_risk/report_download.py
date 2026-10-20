"""Download the NBA's official injury report, one snapshot per game day (2018-19 onward).

The league posts the PDFs at a fixed address. Until 2024-25 the files are named by the hour
(``Injury-Report_2024-01-15_05PM.pdf``); from 2025-26 by the quarter hour (``..._05_00PM.pdf``). The
5 PM ET report comes first: it is before most tip-offs and still lists the day's early games.
A day whose report cannot be found is recorded as missing, never invented.
"""
from __future__ import annotations

import hashlib
import json
import time
from datetime import date

import pandas as pd

from . import net, sources
from .paths import REPORTS_RAW

URL = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_{day}_{slot}.pdf"
HOURLY = ["05PM", "06PM", "04PM", "07PM", "03PM", "08PM", "02PM", "01PM", "12PM", "11AM", "09PM", "10AM"]
QUARTER = ["05_00PM", "05_30PM", "05_15PM", "05_45PM", "04_30PM", "06_00PM", "04_00PM", "06_30PM",
           "07_00PM", "03_00PM", "02_00PM", "01_00PM", "12_00PM", "11_00AM"]
QUARTER_NAMING_FROM = date(2025, 7, 1)
FIRST_REPORT_SEASON = 2019            # 2018-19; the 2017-18 addresses answer 403
FIRST_REPORT_DAY = date(2018, 12, 17)  # the archive starts here; Oct 16 - Dec 16, 2018 answer 403 at every slot
GAME_TYPES = ("regular-season", "play-in", "playoffs", "nba-cup")
MANIFEST = REPORTS_RAW / "manifest.jsonl"


def slots(day: date) -> list[str]:
    first, second = (QUARTER, HOURLY) if day >= QUARTER_NAMING_FROM else (HOURLY, QUARTER)
    return first + second


def game_days(seasons) -> list[tuple[int, date]]:
    days = []
    for season in seasons:
        sched = pd.read_parquet(sources.season_path("schedule", season), columns=["game_date", "season_type"])
        sched = sched[sched["season_type"].isin(GAME_TYPES)]
        days += [(season, d) for d in sorted(pd.to_datetime(sched["game_date"]).dt.date.unique()) if d >= FIRST_REPORT_DAY]
    return days


def load_manifest() -> dict[str, dict]:
    if not MANIFEST.exists():
        return {}
    records = [json.loads(line) for line in MANIFEST.read_text(encoding="utf-8").splitlines() if line.strip()]
    return {r["day"]: r for r in records}          # the latest record for a day wins


def fetch(seasons, retry_missing: bool = False, pause: float = 0.15, log=print) -> dict[str, int]:
    REPORTS_RAW.mkdir(parents=True, exist_ok=True)
    done = load_manifest()
    counts = {"ok": 0, "missing": 0, "skipped": 0}
    all_days = game_days(seasons)
    todo = [(s, d) for s, d in all_days
            if not (d.isoformat() in done and (done[d.isoformat()]["status"] == "ok" or not retry_missing))]
    counts["skipped"] = len(all_days) - len(todo)
    with MANIFEST.open("a", encoding="utf-8") as manifest:
        for i, (season, day) in enumerate(todo, 1):
            record = dict(day=day.isoformat(), season=season, status="missing", tried=0)
            for slot in slots(day):
                url = URL.format(day=day.isoformat(), slot=slot)
                record["tried"] += 1
                try:
                    status, body = net.get(url, timeout=60)
                except OSError:
                    time.sleep(2)
                    continue
                time.sleep(pause)
                if status == 200 and body[:4] == b"%PDF":
                    dest = REPORTS_RAW / str(season) / f"Injury-Report_{day.isoformat()}_{slot}.pdf"
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(body)
                    record.update(status="ok", slot=slot, file=str(dest.relative_to(REPORTS_RAW)).replace("\\", "/"),
                                  bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
                    break
            manifest.write(json.dumps(record) + "\n")
            manifest.flush()
            counts[record["status"]] += 1
            if i % 50 == 0 or i == len(todo):
                log(f"{i}/{len(todo)} days: {counts}")
    return counts
