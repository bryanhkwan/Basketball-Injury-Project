"""Schedule and player-game tables built from the season files.

``schedule``: one row per game (regular season, play-in, playoffs, NBA Cup final) with its date, the two
teams and where it was played. ``player_games``: one row per player per team game, from the box score
(played, or listed with a DNP/DND/NWT comment) and the inactive list (not dressed).
"""
from __future__ import annotations

import re
import unicodedata

import numpy as np
import pandas as pd

from . import sources, teams

GAME_TYPES = ("regular-season", "play-in", "playoffs", "nba-cup")
BOX_STATS = {"field_goals_attempted": "fga", "free_throws_attempted": "fta", "turnovers": "tov",
             "rebounds_offensive": "oreb", "rebounds_total": "reb", "assists": "ast", "steals": "stl",
             "blocks": "blk", "fouls_personal": "pf", "points": "pts"}


def build_schedule(seasons) -> pd.DataFrame:
    frames = []
    for season in seasons:
        s = pd.read_parquet(sources.season_path("schedule", season))
        s = s[s["season_type"].isin(GAME_TYPES)]
        s = s.rename(columns={"home_team_abbreviation": "home", "away_team_abbreviation": "away"})
        s = s[["game_id", "season", "season_type", "game_date", "home", "away"]].copy()
        x = pd.read_parquet(sources.season_path("schedule_xwalk", season), columns=["nba_game_id", "espn_game_id"])
        e = pd.read_parquet(sources.season_path("espn_schedule", season), columns=["game_id", "venue_address_city"])
        e = e.rename(columns={"game_id": "espn_game_id", "venue_address_city": "venue_city"})
        x["espn_game_id"] = x["espn_game_id"].astype(str)
        e["espn_game_id"] = e["espn_game_id"].astype(str)
        venue = x.merge(e, on="espn_game_id", how="left").drop_duplicates("nba_game_id")
        s = s.merge(venue[["nba_game_id", "venue_city"]], left_on="game_id", right_on="nba_game_id", how="left")
        frames.append(s.drop(columns="nba_game_id"))
    sched = pd.concat(frames, ignore_index=True).drop_duplicates("game_id")
    sched["game_date"] = pd.to_datetime(sched["game_date"])
    unknown = sorted((set(sched["home"]) | set(sched["away"])) - set(teams.TEAMS))
    if unknown:
        raise ValueError(f"unknown team codes in schedule: {unknown}")
    loc = [teams.NEUTRAL_CITIES.get(city) if isinstance(city, str) else None for city in sched["venue_city"]]
    home_loc = [teams.location(code) for code in sched["home"]]
    chosen = [n if n is not None else h for n, h in zip(loc, home_loc)]
    sched["neutral"] = [n is not None and not (abs(n[0] - h[0]) < 0.5 and abs(n[1] - h[1]) < 0.5) for n, h in zip(loc, home_loc)]
    sched[["lat", "lon", "utc", "alt_ft"]] = pd.DataFrame(chosen, index=sched.index)
    return sched.sort_values(["game_date", "game_id"]).reset_index(drop=True)


def _minutes(value) -> float:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return 0.0
    text = str(value).strip()
    if not text:
        return 0.0
    m = re.match(r"^(\d+):(\d+)", text)
    if m:
        return int(m.group(1)) + int(m.group(2)) / 60
    try:
        return float(text)
    except ValueError:
        return 0.0


def build_player_games(seasons, schedule: pd.DataFrame) -> pd.DataFrame:
    frames = []
    for season in seasons:
        b = pd.read_parquet(sources.season_path("player_box", season))
        b = b.rename(columns={"person_id": "player_id", "team_tricode": "team", "family_name": "last_name"})
        b["minutes"] = [_minutes(v) for v in b["minutes"]]
        b["starter"] = b["position"].fillna("").str.len() > 0
        b["comment"] = b["comment"].fillna("").astype(str).str.strip()
        b["status"] = np.where(b["minutes"] > 0, "played", "dnp")
        keep = ["game_id", "team", "player_id", "first_name", "last_name", "minutes", "starter", "comment", "status"]
        b = b[keep + list(BOX_STATS)].rename(columns=BOX_STATS)
        i = pd.read_parquet(sources.season_path("inactive", season))
        i = i.rename(columns={"team_abbreviation": "team"})[["game_id", "team", "player_id", "first_name", "last_name"]]
        i = i.assign(minutes=0.0, starter=False, comment="", status="inactive")
        both = pd.concat([b, i], ignore_index=True)
        both["player_id"] = pd.to_numeric(both["player_id"], errors="coerce")
        both = both.dropna(subset=["player_id"]).astype({"player_id": "int64"})
        both = both.drop_duplicates(["game_id", "team", "player_id"], keep="first")
        frames.append(both)
    pg = pd.concat(frames, ignore_index=True)
    pg = pg.merge(schedule[["game_id", "season", "season_type", "game_date", "home", "away"]], on="game_id", how="inner")
    pg["is_home"] = pg["team"] == pg["home"]
    pg["opponent"] = np.where(pg["is_home"], pg["away"], pg["home"])
    for col in BOX_STATS.values():
        pg[col] = pd.to_numeric(pg[col], errors="coerce").fillna(0.0)
    return pg.drop(columns=["home", "away"]).sort_values(["player_id", "game_date", "game_id"]).reset_index(drop=True)


RENAMED = {   # players whose surname changed; box scores carry the later name retroactively
    ("kanter", "enes"): ("freedom", "enes"),
    ("kanter freedom", "enes"): ("freedom", "enes"),
    ("waller prince", "taurean"): ("prince", "taurean"),
    ("carrington", "carlton"): ("carrington", "bub"),          # reports use the legal name, box scores the nickname
    ("louzada silva", "marcos"): ("louzada", "didi"),
}


def name_key(last: str, first: str) -> tuple[str, str]:
    def norm(text: str) -> str:
        text = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode()
        text = re.sub(r"[^a-z ]", " ", text.lower().replace("'", "").replace(".", ""))
        return " ".join(t for t in text.split() if t not in {"jr", "sr", "ii", "iii", "iv", "v"})
    key = norm(last), norm(first)
    return RENAMED.get(key, key)
