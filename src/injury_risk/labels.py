"""Injury labels: why each missed game was missed, when each injury began, and the training target.

An injury *onset* is the first game of a run of missed games that the official report attributes to an
injury, counted only if the player had played in the previous 14 days (a long absence that continues is
not a new injury). A missed game with no report entry and no informative box comment can extend a run,
and the one directly before a reported injury absence becomes the onset (a late scratch, or a day whose
report is missing). The target for a game a player played is whether an onset falls in the next
``horizon`` days.
"""
from __future__ import annotations

import difflib
import json
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

from . import injury_reports, report_download
from .games import name_key
from .paths import INTERIM, REPORTS_RAW
from .reasons import classify

ELIGIBLE_GAP_DAYS = 14
LOWER_BODY = {"ankle", "knee", "foot", "calf", "hamstring", "groin", "hip", "thigh", "achilles", "leg"}
ONSET_COLUMNS = ["player_id", "onset_date", "onset_game_id", "team", "season", "reason", "region", "injury_type",
                 "games_missed", "end_date", "return_date", "days_since_played", "new_injury"]


# --- reports ------------------------------------------------------------------------------------------------------

def _parse_one(job):
    file, day = job
    try:
        res = injury_reports.parse_pdf(REPORTS_RAW / file)
    except Exception as error:  # a damaged PDF is reported, not fatal
        return [], [dict(file=file, problem=f"{type(error).__name__}: {error}")]
    rows = [dict(r, report_day=day, report_stamp=res["stamp"], file=file) for r in res["rows"]]
    return rows, [dict(file=file, problem=p) for p in res["problems"]]


def parse_all(workers: int = 6) -> pd.DataFrame:
    manifest = report_download.load_manifest()
    jobs = sorted((r["file"], r["day"]) for r in manifest.values() if r["status"] == "ok")
    rows, problems = [], []
    with ProcessPoolExecutor(workers) as pool:
        for got, issues in pool.map(_parse_one, jobs, chunksize=8):
            rows += got
            problems += issues
    df = pd.DataFrame(rows)
    INTERIM.mkdir(parents=True, exist_ok=True)
    df.to_parquet(INTERIM / "report_rows.parquet", index=False)
    (INTERIM / "report_parse_problems.json").write_text(json.dumps(problems, indent=1), encoding="utf-8")
    return df


def match_players(report: pd.DataFrame, player_games: pd.DataFrame, schedule: pd.DataFrame) -> pd.DataFrame:
    """Add ``player_id`` and ``season`` to report rows by name, within the team and season where possible."""
    sides = pd.concat([schedule[["game_date", "home", "season"]].rename(columns={"home": "team"}),
                       schedule[["game_date", "away", "season"]].rename(columns={"away": "team"})])
    sides["game_date"] = sides["game_date"].dt.date.astype(str)
    report = report.merge(sides.drop_duplicates(["game_date", "team"]), on=["game_date", "team"], how="left")

    people = player_games[["season", "team", "player_id", "first_name", "last_name"]].drop_duplicates(["season", "team", "player_id"])
    people = people.assign(key=[name_key(l, f) for l, f in zip(people["last_name"], people["first_name"])])
    by_team = {(s, t, k): pid for s, t, k, pid in zip(people["season"], people["team"], people["key"], people["player_id"])}
    season_keys = people.groupby(["season", "key"])["player_id"].nunique()
    by_season = {(s, k): pid for (s, t, k, pid) in zip(people["season"], people["team"], people["key"], people["player_id"])
                 if season_keys.get((s, k), 0) == 1}
    roster = people.groupby(["season", "team"])
    names = {g: list(zip(d["key"], d["player_id"])) for g, d in roster}

    ids, methods = [], []
    for season, team, raw in zip(report["season"], report["team"], report["player"]):
        last, _, first = str(raw).partition(",")
        key = name_key(last, first)
        pid, how = None, None
        if (season, team, key) in by_team:
            pid, how = by_team[(season, team, key)], "team"
        elif (season, key) in by_season:
            pid, how = by_season[(season, key)], "season"
        else:
            pool = names.get((season, team), [])
            same_last = [p for k, p in pool if k[0] == key[0] and k[1][:1] == key[1][:1]]
            if len(set(same_last)) == 1:
                pid, how = same_last[0], "last_initial"
            elif pool:
                target = f"{key[0]} {key[1]}"
                scored = max(((difflib.SequenceMatcher(None, target, f"{k[0]} {k[1]}").ratio(), p) for k, p in pool), key=lambda x: x[0])
                if scored[0] >= 0.85:
                    pid, how = scored[1], "fuzzy"
        ids.append(pid)
        methods.append(how)
    report = report.assign(player_id=pd.array(ids, dtype="Int64"), match=methods)
    return report


def best_entries(report: pd.DataFrame) -> pd.DataFrame:
    """One report entry per (game date, team, player): the same day's report, else the latest earlier one."""
    r = report.dropna(subset=["player_id", "game_date", "team"]).astype({"player_id": "int64"})
    r = r[r["report_day"] <= r["game_date"]]
    r = r.sort_values(["game_date", "team", "player_id", "report_day"])
    r = r.drop_duplicates(["game_date", "team", "player_id"], keep="last")
    cls = r["reason"].map(classify)
    r["reason_class"] = [c["reason_class"] for c in cls]
    r["region"] = [c["region"] for c in cls]
    r["injury_type"] = [c["injury_type"] for c in cls]
    r["same_day"] = r["report_day"] == r["game_date"]
    return r[["game_date", "team", "player_id", "status", "reason", "reason_class", "region", "injury_type", "same_day"]]


# --- absences and onsets ------------------------------------------------------------------------------------------

def _comment_class(comment: str) -> str:
    c = (comment or "").lower()
    if not c:
        return "unknown"
    if "coach" in c:
        return "coach"
    if "concussion" in c:
        return "injury"
    if "injury" in c or "illness" in c:
        return "unknown_medical"
    if "rest" in c or "reconditioning" in c:
        return "management"
    return "non_medical"


def classify_absences(player_games: pd.DataFrame, entries: pd.DataFrame) -> pd.DataFrame:
    pg = player_games.copy()
    pg["date_key"] = pg["game_date"].dt.date.astype(str)
    e = entries.rename(columns={"game_date": "date_key", "status": "report_status"})
    pg = pg.merge(e, on=["date_key", "team", "player_id"], how="left")
    reported = pg["reason_class"].notna()
    serious = pg["report_status"].isin(["Out", "Doubtful", "Questionable"])
    from_comment = pg["comment"].map(_comment_class)
    absence = np.where(pg["status"] == "played", "played",
              np.where(reported & (serious | (from_comment != "coach")), pg["reason_class"].fillna("unknown"),
                       from_comment))
    pg["absence"] = absence
    return pg.drop(columns="date_key")


def find_onsets(pg: pd.DataFrame) -> pd.DataFrame:
    """One row per injury run, with its onset date, the games it cost and whether it counts as a new injury."""
    out = []
    pg = pg.sort_values(["player_id", "game_date"])
    for pid, d in pg.groupby("player_id", sort=False):
        kind = d["absence"].to_numpy()
        dates = d["game_date"].to_numpy()
        played = kind == "played"
        n, i = len(d), 0
        while i < n:
            if kind[i] not in ("injury", "unknown", "unknown_medical"):
                i += 1
                continue
            j = i
            while j < n and kind[j] in ("injury", "unknown", "unknown_medical"):
                j += 1
            injured = [k for k in range(i, j) if kind[k] == "injury"]
            if injured:
                first = injured[0]
                onset = first - 1 if first - 1 >= i else first
                prior = np.nonzero(played[:onset])[0]
                last_played = dates[prior[-1]] if len(prior) else None
                gap = (dates[onset] - last_played) / np.timedelta64(1, "D") if last_played is not None else None
                row = d.iloc[first]
                out.append(dict(
                    player_id=pid, onset_date=dates[onset], onset_game_id=d["game_id"].iloc[onset],
                    team=d["team"].iloc[onset], season=d["season"].iloc[onset],
                    reason=row["reason"], region=row["region"], injury_type=row["injury_type"],
                    games_missed=j - onset, end_date=dates[j - 1],
                    return_date=dates[j] if j < n and played[j] else pd.NaT,
                    days_since_played=gap, new_injury=gap is not None and gap <= ELIGIBLE_GAP_DAYS))
            i = j
    return pd.DataFrame(out, columns=ONSET_COLUMNS).astype({"new_injury": bool})


def targets(rows: pd.DataFrame, onsets: pd.DataFrame, all_games: pd.DataFrame, horizon: int, where=None) -> pd.Series:
    """1 if an eligible onset (optionally filtered by ``where``) falls in (game date, game date + horizon]."""
    o = onsets[onsets["new_injury"]]
    if where is not None:
        o = o[where(o)]
    o = o[["player_id", "onset_date"]].astype({"player_id": "int64"}).sort_values("onset_date")
    r = rows[["player_id", "game_date"]].astype({"player_id": "int64"}).reset_index().sort_values("game_date")
    m = pd.merge_asof(r, o, left_on="game_date", right_on="onset_date", by="player_id",
                      direction="forward", allow_exact_matches=False)
    hit = (m["onset_date"] - m["game_date"]).dt.days <= horizon
    return pd.Series(hit.to_numpy(), index=m["index"]).reindex(rows.index).fillna(False).astype(int)


def targets_in_games(rows: pd.DataFrame, onsets: pd.DataFrame, all_games: pd.DataFrame, n_games: int,
                     where=None) -> tuple[pd.Series, pd.Series]:
    """(target, observable) in team games rather than days: does a new injury make the player miss one of the
    team's next ``n_games`` games? Observable when the player has ``n_games`` later team games that season."""
    o = onsets[onsets["new_injury"]]
    if where is not None:
        o = o[where(o)]
    onset_games = set(zip(o["player_id"].astype("int64"), o["onset_game_id"]))
    y = pd.Series(0, index=rows.index)
    seen = pd.Series(False, index=rows.index)
    g = all_games[["player_id", "game_id", "game_date", "season"]].sort_values(["player_id", "game_date"])
    wanted = rows.groupby("player_id").groups
    for pid, d in g.groupby("player_id", sort=False):
        if pid not in wanted:
            continue
        ids, seasons = d["game_id"].to_numpy(), d["season"].to_numpy()
        is_onset = np.array([(pid, gid) in onset_games for gid in ids])
        pos = {gid: i for i, gid in enumerate(ids)}
        cum = np.concatenate([[0], np.cumsum(is_onset)])
        for idx in wanted[pid]:
            i = pos.get(rows.at[idx, "game_id"])
            if i is None:
                continue
            j = min(i + n_games, len(ids) - 1)
            y.at[idx] = int(cum[j + 1] - cum[i + 1] > 0)
            seen.at[idx] = i + n_games < len(ids) and seasons[i + n_games] == seasons[i]
    return y, seen


def observable(rows: pd.DataFrame, all_games: pd.DataFrame, horizon: int) -> pd.Series:
    """True when the player has any later team game within the horizon (the window can show a missed game)."""
    nxt = all_games[["player_id", "game_date"]].astype({"player_id": "int64"}).rename(columns={"game_date": "next_date"}).sort_values("next_date")
    r = rows[["player_id", "game_date"]].astype({"player_id": "int64"}).reset_index().sort_values("game_date")
    m = pd.merge_asof(r, nxt, left_on="game_date", right_on="next_date", by="player_id",
                      direction="forward", allow_exact_matches=False)
    ok = (m["next_date"] - m["game_date"]).dt.days <= horizon
    return pd.Series(ok.to_numpy(), index=m["index"]).reindex(rows.index).fillna(False)
