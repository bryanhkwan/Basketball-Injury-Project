"""Season files from the sportsdataverse data releases on GitHub, which mirror stats.nba.com and ESPN.

stats.nba.com itself refuses scripted requests from this machine, so these releases are the source of box
scores, inactive lists, schedules and rosters. Seasons are named by the year they end: 2024 is 2023-24.
"""
from __future__ import annotations

import hashlib
import time

from . import net
from .paths import SDV

BASE = "https://github.com/sportsdataverse/sportsdataverse-data/releases/download"

# kind -> (release tag, file name pattern)
SEASON_FILES = {
    "player_box": ("nba_stats_player_boxscores", "player_boxscores_{season}.parquet"),   # minutes, stats, DNP comment
    "inactive": ("nba_stats_game_rosters", "game_rosters_{season}.parquet"),            # inactive players per game
    "schedule": ("nba_stats_schedules", "nba_schedule_{season}.parquet"),
    "rosters": ("nba_stats_rosters", "rosters_{season}.parquet"),                       # birth date, height, weight
    "espn_schedule": ("espn_nba_schedules", "nba_schedule_{season}.parquet"),           # venue, neutral site
    "schedule_xwalk": ("nba_crosswalk", "nba_schedule_crosswalk_{season}.parquet"),     # ESPN <-> NBA game ids
    "pbp": ("nba_stats_pbp", "nba_play_by_play_{season}.parquet"),                       # every play, all 10 on court
    "possessions": ("nba_stats_possessions", "nba_possessions_{season}.parquet"),        # start type, duration, on court
}

DEFAULT_SEASONS = tuple(range(2017, 2027))   # 2016-17 through 2025-26

# Division I men's college basketball: the NCAA's own play-by-play and box scores, and ESPN's team list
COLLEGE_FILES = {
    "ncaa_pbp": ("ncaa_mbb_pbp", "ncaa_mbb_pbp_{season}.parquet"),                     # substitutions, lineups
    "ncaa_player_box": ("ncaa_mbb_player_box", "ncaa_mbb_player_box_{season}.parquet"),  # minutes per player-game
    "espn_mbb_player_box": ("espn_mens_college_basketball_player_boxscores", "player_box_{season}.parquet"),   # team slugs
}
COLLEGE_SEASONS = tuple(range(2020, 2027))   # 2019-20 through 2025-26, the seasons with saved injury pages


def season_path(kind: str, season: int):
    return SDV / kind / f"{kind}_{season}.parquet"


def fetch(seasons=DEFAULT_SEASONS, kinds=None, force: bool = False) -> list[dict]:
    """Download each (kind, season) file once; a cached file is kept unless ``force``."""
    results = []
    for kind in kinds or SEASON_FILES:
        tag, pattern = SEASON_FILES[kind] if kind in SEASON_FILES else COLLEGE_FILES[kind]
        for season in seasons:
            dest = season_path(kind, season)
            if dest.exists() and not force:
                results.append(dict(kind=kind, season=season, status="cached", bytes=dest.stat().st_size))
                continue
            url = f"{BASE}/{tag}/{pattern.format(season=season)}"
            status, body = net.get(url, timeout=120)
            if status != 200 or not body.startswith(b"PAR1"):
                results.append(dict(kind=kind, season=season, status=f"http {status}", url=url))
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            part = dest.with_suffix(".part")
            part.write_bytes(body)
            part.replace(dest)
            results.append(dict(kind=kind, season=season, status="downloaded", bytes=len(body),
                                sha256=hashlib.sha256(body).hexdigest()))
            time.sleep(0.2)
    return results
