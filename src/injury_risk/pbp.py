"""Per player-game load from the play-by-play: stints, late-game minutes, rim attacks, transition, early exits.

Every play in stats.nba.com's play-by-play lists the ten players on the floor, so time on court is the clock
time between plays credited to those ten (the clock is held monotone within a period, since a few plays are
logged out of order), and a stint is a run of consecutive plays with the player on the floor inside one
period. A transition chance is a field-goal attempt within 7 seconds of the shooting team winning the ball
on a defensive rebound or a steal; all ten players on the floor are credited. (The possessions table's own
start and end times are not usable: half its possessions last 0 seconds.) An early exit is a starter whose
last stint ends before the fourth quarter of a game decided by 12 points or fewer, without being ejected:
often a knock. Minutes rebuilt this way match the box score (2023-24: median difference 0.02 minutes).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import sources
from .paths import INTERIM

ON_COURT = [f"off_player_{i}" for i in range(1, 6)] + [f"def_player_{i}" for i in range(1, 6)]
GAME_PREFIXES = ("002", "004", "005", "006")     # regular season, playoffs, play-in, NBA Cup final
RIM_SHOT = r"Layup|Dunk|Tip|Alley Oop|Putback|Finger Roll"
TRANSITION_SECONDS = 7


def is_rim(sub_type: pd.Series, distance: pd.Series, shot_value: pd.Series, description: pd.Series) -> pd.Series:
    """Field-goal attempts at the rim: a rim shot type, or within 3 feet. A three-pointer never is: its distance
    is 0, not missing, when the description gives none (mostly corner threes)."""
    three = (pd.to_numeric(shot_value, errors="coerce") == 3) | description.fillna("").str.contains("3PT")
    near = sub_type.fillna("").str.contains(RIM_SHOT, case=False) | (distance.fillna(99) <= 3)
    return near & ~three
EARLY_EXIT_BEFORE = 3 * 720                       # end of the third quarter, in elapsed seconds
CLOSE_MARGIN = 12


def _transition_shots(game, team, t, atype, desc, is_fg) -> np.ndarray:
    """True for field-goal attempts within TRANSITION_SECONDS of the shooting team winning the ball."""
    out = np.zeros(len(game), dtype=bool)
    last_miss_team = gain_team = None
    gain_t = -1e9
    for i in range(len(game)):
        if i == 0 or game[i] != game[i - 1]:
            last_miss_team = gain_team = None
        a = atype[i]
        if a == "Missed Shot" or (a == "Free Throw" and desc[i].startswith("MISS")):
            last_miss_team = team[i]
        elif a == "Rebound":
            if last_miss_team is not None and team[i] not in (0, last_miss_team):
                gain_team, gain_t = team[i], t[i]
            last_miss_team = None
        elif a == "" and "STEAL" in desc[i]:
            gain_team, gain_t = team[i], t[i]
        if is_fg[i]:
            if team[i] == gain_team and t[i] - gain_t <= TRANSITION_SECONDS:
                out[i] = True
            gain_team = None
    return out


def _elapsed(period: np.ndarray, remaining: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(elapsed seconds at the play, elapsed seconds at the end of its period)."""
    start = np.where(period <= 4, (period - 1) * 720, 2880 + (period - 5) * 300)
    length = np.where(period <= 4, 720, 300)
    return start + (length - remaining), start + length


def season_load(season: int) -> pd.DataFrame:
    cols = ["game_id", "order_index", "period", "seconds_remaining", "score_home", "score_away", "action_type",
            "sub_type", "description", "team_id", "is_field_goal", "shot_distance", "shot_value", "person_id"] + ON_COURT
    p = pd.read_parquet(sources.season_path("pbp", season), columns=cols)
    p = p[p["game_id"].astype(str).str[:3].isin(GAME_PREFIXES)].sort_values(["game_id", "order_index"]).reset_index(drop=True)
    period = p["period"].to_numpy(dtype=int)
    t, period_end = _elapsed(period, p["seconds_remaining"].fillna(0).to_numpy(dtype=float))
    t = pd.Series(t).groupby([p["game_id"], p["period"]]).cummax().to_numpy()   # clock never runs backwards
    game = p["game_id"].to_numpy()
    same = np.concatenate([(game[1:] == game[:-1]) & (period[1:] == period[:-1]), [False]])
    nxt = np.concatenate([t[1:], [0.0]])
    p["dt"] = np.clip(np.where(same, nxt - t, period_end - t), 0, 300)
    p["t"] = t
    p["pos"] = p.groupby("game_id").cumcount()

    # time on court and stints
    long = p[["game_id", "pos", "period", "t", "dt"] + ON_COURT].melt(
        id_vars=["game_id", "pos", "period", "t", "dt"], value_vars=ON_COURT, value_name="player_id")
    long["player_id"] = pd.to_numeric(long["player_id"], errors="coerce")
    long = long[long["player_id"] > 0].astype({"player_id": "int64"})
    long = long.drop_duplicates(["game_id", "pos", "player_id"])   # a few plays list a player in two slots
    long = long.sort_values(["game_id", "player_id", "pos"]).reset_index(drop=True)
    g, pid, pos, per = (long[c].to_numpy() for c in ("game_id", "player_id", "pos", "period"))
    new = np.ones(len(long), dtype=bool)
    new[1:] = (g[1:] != g[:-1]) | (pid[1:] != pid[:-1]) | (pos[1:] - pos[:-1] > 1) | (per[1:] != per[:-1])
    long["stint"] = np.cumsum(new)
    stints = long.groupby(["game_id", "player_id", "stint"]).agg(sec=("dt", "sum"), end=("t", "max"))
    per_player = stints.groupby(["game_id", "player_id"]).agg(
        n_stints=("sec", "size"), longest_stint=("sec", "max"), mean_stint=("sec", "mean"), last_on=("end", "max"))
    late = long[long["period"] >= 4].groupby(["game_id", "player_id"])["dt"].sum().rename("q4ot_sec")
    ot = long[long["period"] >= 5].groupby(["game_id", "player_id"])["dt"].sum().rename("ot_sec")
    on = long.groupby(["game_id", "player_id"])["dt"].sum().rename("pbp_sec")
    out = per_player.join([on, late, ot]).fillna({"q4ot_sec": 0.0, "ot_sec": 0.0}).reset_index()

    # starters, final margin, ejections
    first = p.groupby("game_id").head(1)[["game_id"] + ON_COURT].melt(id_vars="game_id", value_name="player_id")
    first["player_id"] = pd.to_numeric(first["player_id"], errors="coerce")
    starters = set(zip(first["game_id"], first["player_id"]))
    scores = p[["game_id", "score_home", "score_away"]].replace("", np.nan)
    scores[["score_home", "score_away"]] = scores[["score_home", "score_away"]].apply(pd.to_numeric, errors="coerce")
    final = scores.groupby("game_id")[["score_home", "score_away"]].last()
    margin = (final["score_home"] - final["score_away"]).abs().rename("final_margin")
    ejected = set(zip(p.loc[p["action_type"] == "Ejection", "game_id"], p.loc[p["action_type"] == "Ejection", "person_id"]))
    out = out.merge(margin, on="game_id", how="left")
    out["starter_pbp"] = [(gid, pl) in starters for gid, pl in zip(out["game_id"], out["player_id"])]
    out["ejected"] = [(gid, pl) in ejected for gid, pl in zip(out["game_id"], out["player_id"])]

    # rim attacks and dunks, by the shooter
    shots = p[p["is_field_goal"] == 1]
    rim = is_rim(shots["sub_type"], shots["shot_distance"], shots["shot_value"], shots["description"])
    dunk = shots["sub_type"].fillna("").str.contains("Dunk", case=False)
    shooter = pd.DataFrame({"game_id": shots["game_id"], "player_id": pd.to_numeric(shots["person_id"], errors="coerce"),
                            "rim_fga": rim.astype(int), "dunk_fga": dunk.astype(int)})
    out = out.merge(shooter.groupby(["game_id", "player_id"]).sum().reset_index(), on=["game_id", "player_id"], how="left")

    # transition chances, credited to all ten players on the floor
    trans = _transition_shots(game, pd.to_numeric(p["team_id"], errors="coerce").fillna(0).astype("int64").to_numpy(), t,
                              p["action_type"].fillna("").to_numpy(), p["description"].fillna("").to_numpy(),
                              p["is_field_goal"].fillna(0).astype(bool).to_numpy())
    tl = p.loc[trans, ["game_id"] + ON_COURT].melt(id_vars="game_id", value_name="player_id")
    tl["player_id"] = pd.to_numeric(tl["player_id"], errors="coerce")
    tcount = tl[tl["player_id"] > 0].groupby(["game_id", "player_id"]).size().rename("trans_on")
    out = out.merge(tcount.reset_index(), on=["game_id", "player_id"], how="left")

    # possessions on the floor (the possession count is sound even though its clock times are not)
    q = pd.read_parquet(sources.season_path("possessions", season), columns=["game_id", "count_as_possession"] + ON_COURT)
    q = q[q["count_as_possession"].astype(bool)]
    ql = q[["game_id"] + ON_COURT].melt(id_vars="game_id", value_name="player_id")
    ql["player_id"] = pd.to_numeric(ql["player_id"], errors="coerce")
    poss = ql[ql["player_id"] > 0].groupby(["game_id", "player_id"]).size().rename("poss_on")
    out = out.merge(poss.reset_index(), on=["game_id", "player_id"], how="left")

    out = out.fillna({"rim_fga": 0, "dunk_fga": 0, "poss_on": 0, "trans_on": 0})
    out["early_exit"] = (out["starter_pbp"] & ~out["ejected"] & (out["last_on"] < EARLY_EXIT_BEFORE)
                         & (out["final_margin"] <= CLOSE_MARGIN)).astype(int)
    out["season"] = season
    return out


def build(seasons, log=print) -> pd.DataFrame:
    frames = []
    for season in seasons:
        frames.append(season_load(season))
        log(f"  play-by-play load {season}: {len(frames[-1]):,} player-games")
    df = pd.concat(frames, ignore_index=True)
    df["player_id"] = df["player_id"].astype("int64")
    INTERIM.mkdir(parents=True, exist_ok=True)
    df.to_parquet(INTERIM / "pbp_load.parquet", index=False)
    return df
