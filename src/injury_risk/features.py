"""Features for each game a player played, using only what was known before tip-off.

Workload, style and injury history come from the player's earlier games; schedule features describe the
game itself (rest, back-to-back, travel, altitude), which is fixed before it starts. The pre-game injury
report for the game itself is kept apart (``PREGAME``) so its effect can be measured on its own.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import sources, teams
from .labels import LOWER_BODY

WORKLOAD = ["min_prev1", "min_avg3", "min_avg10", "min_std10", "min_7d", "min_14d", "min_28d", "games_7d",
            "games_14d", "acwr", "min_spike", "season_min", "season_games", "season_min_avg", "prev_season_min",
            "prev_season_games", "days_since_played", "starter_rate10", "heavy_14d", "min_last2"]
STYLE = ["usage36", "reb36", "oreb36", "fta36", "pf36", "blk36", "stl36", "ast36"]
SCHEDULE = ["rest_days", "b2b", "games_4d", "games_7d_team", "travel_km", "travel_7d", "tz_shift",
            "alt_ft", "prev_alt_ft", "is_home", "game_no", "playoffs", "month",
            "games_next14", "b2b_next14"]   # the schedule ahead is published in advance
BODY = ["age", "height_in", "weight_lb", "bmi", "exp", "pos_g", "pos_f", "pos_c"]
HISTORY = ["inj_365", "inj_per100", "muscle_365", "lower_365", "missed_inj_365", "days_since_onset",   # no raw career count: it grows with the data window
           "games_since_return", "days_since_return", "last_games_missed", "mgmt_60", "ill_60",
           "listed_played_21", "team_inj_rate_365",
           "prone_shrunk", "inj_decay", "missed_decay", "inj_60", "inj_120", "soreness_365"]
HISTORY_START = np.datetime64("2018-12-17", "D").astype(np.int64)   # first official report in the archive
LEAGUE_INJURIES_PER_GAME = 0.039   # about 1,100 new injuries per season over 28,000 player-games
DECAY_DAYS = 180                   # weight of an old injury falls by e every 180 days
PREGAME = ["pregame_listed", "pregame_questionable"]
PBP = ["stint_long_prev1", "stint_long_avg5", "stints_avg5", "q4ot_avg5", "ot_min_14d", "rim36_10", "dunk36_10",
       "trans36_10", "pace48_10", "early_exit_prev1", "early_exit_10", "early_exit_30d", "close_10"]
# What happened in the game itself. Only for the after-game question (will the player miss the next game?);
# never part of a before-the-game score, where it would be information from the future.
CURRENT = ["cur_minutes", "cur_min_drop", "cur_early_exit", "cur_last_on_min", "cur_longest_stint", "cur_q4ot_min",
           "cur_n_stints", "cur_margin"]
ALL = WORKLOAD + STYLE + SCHEDULE + BODY + HISTORY


def team_schedule(schedule: pd.DataFrame) -> pd.DataFrame:
    cols = ["game_id", "season", "season_type", "game_date", "lat", "lon", "utc", "alt_ft"]
    sides = pd.concat([schedule[cols].assign(team=schedule["home"], is_home=True),
                       schedule[cols].assign(team=schedule["away"], is_home=False)], ignore_index=True)
    sides = sides.sort_values(["team", "game_date", "game_id"]).reset_index(drop=True)
    out = []
    for team, d in sides.groupby("team", sort=False):
        day = d["game_date"].to_numpy().astype("datetime64[D]").astype(np.int64)
        lat, lon = d["lat"].to_numpy(), d["lon"].to_numpy()
        travel = np.zeros(len(d))
        for k in range(1, len(d)):
            travel[k] = teams.haversine_km((lat[k - 1], lon[k - 1]), (lat[k], lon[k]))
        cum_travel = np.concatenate([[0.0], np.cumsum(travel)])
        idx = np.arange(len(d))
        start4 = np.searchsorted(day, day - 3, "left")
        start7 = np.searchsorted(day, day - 6, "left")
        rest = np.concatenate([[np.nan], np.diff(day).astype(float)])
        b2b_cum = np.concatenate([[0], np.cumsum(rest == 1)])
        ahead = np.searchsorted(day, day + 14, "right")
        regular = (d["season_type"] == "regular-season").to_numpy()
        game_no = d.assign(r=regular.astype(int)).groupby("season")["r"].cumsum().to_numpy()
        utc, alt = d["utc"].to_numpy(dtype=float), d["alt_ft"].to_numpy(dtype=float)
        out.append(pd.DataFrame(dict(
            game_id=d["game_id"].to_numpy(), team=team,
            rest_days=np.minimum(rest, 10), b2b=(rest == 1).astype(int),
            games_4d=idx - start4 + 1, games_7d_team=idx - start7 + 1,
            travel_km=travel, travel_7d=cum_travel[idx + 1] - cum_travel[start7],
            tz_shift=np.abs(np.concatenate([[0.0], np.diff(utc)])),
            alt_ft=alt, prev_alt_ft=np.concatenate([[np.nan], alt[:-1]]),
            game_no=game_no, playoffs=d["season_type"].isin(["playoffs", "play-in"]).astype(int).to_numpy(),
            month=d["game_date"].dt.month.to_numpy(),
            games_next14=ahead - idx - 1, b2b_next14=b2b_cum[ahead] - b2b_cum[idx + 1])))
    return pd.concat(out, ignore_index=True)


def bios(seasons) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(player bio, per-season experience) from the season rosters."""
    frames = [pd.read_parquet(sources.season_path("rosters", s)).assign(season=s) for s in seasons]
    r = pd.concat(frames, ignore_index=True)
    r["player_id"] = pd.to_numeric(r["player_id"], errors="coerce").astype("Int64")
    r = r.dropna(subset=["player_id"])
    r["birth"] = pd.to_datetime(r["birth_date"], format="%b %d, %Y", errors="coerce")
    hw = r["height"].astype(str).str.extract(r"^(\d+)-(\d+)$").astype(float)
    r["height_in"] = hw[0] * 12 + hw[1]
    r["weight_lb"] = pd.to_numeric(r["weight"], errors="coerce")
    pos = r["position"].fillna("").astype(str)
    r["pos_g"], r["pos_f"], r["pos_c"] = (pos.str.contains("G").astype(int), pos.str.contains("F").astype(int),
                                          pos.str.contains("C").astype(int))
    bio = (r.sort_values("season").groupby("player_id")
             .agg(birth=("birth", "last"), height_in=("height_in", "last"), weight_lb=("weight_lb", "median"),
                  pos_g=("pos_g", "last"), pos_f=("pos_f", "last"), pos_c=("pos_c", "last")).reset_index())
    exp = r.assign(exp=pd.to_numeric(r["exp"].astype(str).replace({"R": "0"}), errors="coerce"))
    exp = exp.groupby(["player_id", "season"])["exp"].max().reset_index()
    return bio, exp


def _window_count(dates, ref, lo_days):
    """Number of ``dates`` (sorted day numbers) in [ref - lo_days, ref) for each ref."""
    return np.searchsorted(dates, ref, "left") - np.searchsorted(dates, ref - lo_days, "left")


def player_features(pg: pd.DataFrame, onsets: pd.DataFrame) -> pd.DataFrame:
    """Workload, style and history features for every played row of ``pg`` (classified player games)."""
    pg = pg.sort_values(["player_id", "game_date", "game_id"])
    eligible = onsets[onsets["new_injury"]]
    on_by_player = {pid: d.sort_values("onset_date") for pid, d in eligible.groupby("player_id")}
    spells_by_player = {pid: d.sort_values("end_date") for pid, d in onsets.groupby("player_id")}
    out = []
    for pid, a in pg.groupby("player_id", sort=False):
        a_day = a["game_date"].to_numpy().astype("datetime64[D]").astype(np.int64)
        kind = a["absence"].to_numpy()
        played = kind == "played"
        p = a[played]
        if p.empty:
            continue
        day = a_day[played]
        mins = p["minutes"].to_numpy(dtype=float)
        n = len(p)
        k = np.arange(n)
        cum = np.concatenate([[0.0], np.cumsum(mins)])

        def last_n_mean(values, n_last):
            c = np.concatenate([[0.0], np.cumsum(values)])
            lo = np.maximum(k - n_last, 0)
            cnt = k - lo
            with np.errstate(invalid="ignore", divide="ignore"):
                return np.where(cnt > 0, (c[k] - c[lo]) / np.maximum(cnt, 1), np.nan)

        def window_sum(values_cum, w):
            lo = np.searchsorted(day, day - w, "left")
            return values_cum[k] - values_cum[lo], k - lo

        min7, g7 = window_sum(cum, 7)
        min14, g14 = window_sum(cum, 14)
        min28, _ = window_sum(cum, 28)
        seasons = p["season"].to_numpy()
        season_start = np.searchsorted(seasons, seasons, "left")
        season_min = cum[k] - cum[season_start]
        season_games = k - season_start
        totals = p.groupby("season")["minutes"].agg(["sum", "count"])
        prev = totals.reindex(seasons - 1)
        sq = np.concatenate([[0.0], np.cumsum(mins ** 2)])
        lo10 = np.maximum(k - 10, 0)
        cnt10 = k - lo10
        with np.errstate(invalid="ignore", divide="ignore"):
            mean10 = (cum[k] - cum[lo10]) / cnt10
            std10 = np.sqrt(np.maximum((sq[k] - sq[lo10]) / cnt10 - mean10 ** 2, 0))
            acwr = np.where(min28 > 0, min7 / (min28 / 4), np.nan)
            season_avg = np.where(season_games > 0, season_min / np.maximum(season_games, 1), np.nan)
        prev1 = np.concatenate([[np.nan], mins[:-1]])
        heavy_cum = np.concatenate([[0.0], np.cumsum(mins >= 36)])
        lo14 = np.searchsorted(day, day - 14, "left")
        lo2 = np.maximum(k - 2, 0)
        f = dict(row_index=p.index.to_numpy(),
                 heavy_14d=heavy_cum[k] - heavy_cum[lo14], min_last2=cum[k] - cum[lo2],
                 min_prev1=prev1, min_avg3=last_n_mean(mins, 3), min_avg10=np.where(cnt10 > 0, mean10, np.nan),
                 min_std10=np.where(cnt10 > 1, std10, np.nan), min_7d=min7, min_14d=min14, min_28d=min28,
                 games_7d=g7, games_14d=g14, acwr=acwr, min_spike=prev1 - season_avg,
                 season_min=season_min, season_games=season_games, season_min_avg=season_avg,
                 prev_season_min=prev["sum"].to_numpy(), prev_season_games=prev["count"].to_numpy(),
                 days_since_played=np.concatenate([[np.nan], np.diff(day).astype(float)]),
                 starter_rate10=last_n_mean(p["starter"].to_numpy(dtype=float), 10))
        stat_cum = {c: np.concatenate([[0.0], np.cumsum(p[c].to_numpy(dtype=float))]) for c in
                    ("fga", "fta", "tov", "reb", "oreb", "pf", "blk", "stl", "ast")}
        m10 = cum[k] - cum[lo10]
        with np.errstate(invalid="ignore", divide="ignore"):
            per36 = lambda c: np.where(m10 > 30, (stat_cum[c][k] - stat_cum[c][lo10]) * 36 / m10, np.nan)
            f.update(usage36=np.where(m10 > 30, (stat_cum["fga"][k] - stat_cum["fga"][lo10] + 0.44 * (stat_cum["fta"][k] - stat_cum["fta"][lo10])
                                                 + stat_cum["tov"][k] - stat_cum["tov"][lo10]) * 36 / m10, np.nan),
                     reb36=per36("reb"), oreb36=per36("oreb"), fta36=per36("fta"), pf36=per36("pf"),
                     blk36=per36("blk"), stl36=per36("stl"), ast36=per36("ast"))

        if "longest_stint" in p.columns:   # play-by-play load, from earlier games only
            def col(name):
                return np.nan_to_num(p[name].to_numpy(dtype=float))

            def last10_per(name, per):
                c = np.concatenate([[0.0], np.cumsum(col(name))])
                with np.errstate(invalid="ignore", divide="ignore"):
                    return np.where(m10 > 30, (c[k] - c[lo10]) * per / m10, np.nan)
            m10 = cum[k] - cum[lo10]
            longest = col("longest_stint") / 60
            exits = col("early_exit")
            exit_cum = np.concatenate([[0.0], np.cumsum(exits)])
            ot_cum = np.concatenate([[0.0], np.cumsum(col("ot_sec") / 60)])
            close = (p["final_margin"].to_numpy(dtype=float) <= 5).astype(float)
            f.update(stint_long_prev1=np.concatenate([[np.nan], longest[:-1]]), stint_long_avg5=last_n_mean(longest, 5),
                     stints_avg5=last_n_mean(col("n_stints"), 5), q4ot_avg5=last_n_mean(col("q4ot_sec") / 60, 5),
                     ot_min_14d=ot_cum[k] - ot_cum[lo14],
                     rim36_10=last10_per("rim_fga", 36), dunk36_10=last10_per("dunk_fga", 36),
                     trans36_10=last10_per("trans_on", 36), pace48_10=last10_per("poss_on", 48),
                     early_exit_prev1=np.concatenate([[np.nan], exits[:-1]]),
                     early_exit_10=exit_cum[k] - exit_cum[lo10],
                     early_exit_30d=exit_cum[k] - exit_cum[np.searchsorted(day, day - 30, "left")],
                     close_10=last_n_mean(close, 10))

        # absences and listings (all rows, strictly before the game)
        def count_kind(mask, w):
            return _window_count(a_day[mask], day, w)

        def decayed(event_days):
            """Sum of exp(-age / DECAY_DAYS) over events strictly before each game."""
            if len(event_days) == 0:
                return np.zeros(n)
            ev = np.sort(event_days)
            # running sum of exp(t / tau) over events, read just before each game, rescaled to the game's date
            w = np.exp((ev - ev[-1]) / DECAY_DAYS)
            c = np.concatenate([[0.0], np.cumsum(w)])
            upto = np.searchsorted(ev, day, "left")
            return c[upto] * np.exp((ev[-1] - day) / DECAY_DAYS)
        f["missed_inj_365"] = count_kind(kind == "injury", 365)
        f["missed_decay"] = decayed(a_day[kind == "injury"])
        f["mgmt_60"] = count_kind(kind == "management", 60)
        f["ill_60"] = count_kind(kind == "illness", 60)
        listed_played = played & (a["reason_class"].to_numpy() == "injury")
        f["listed_played_21"] = count_kind(listed_played, 21)
        here = a.loc[played]
        f["pregame_listed"] = (here["reason_class"] == "injury").astype(int).to_numpy()
        f["pregame_questionable"] = here["report_status"].isin(["Questionable", "Doubtful"]).astype(int).to_numpy()

        # injury history from onsets (new injuries) and spells (any run)
        o = on_by_player.get(pid)
        if o is not None:
            od = o["onset_date"].to_numpy().astype("datetime64[D]").astype(np.int64)
            f["inj_365"] = _window_count(od, day, 365)
            f["inj_all"] = np.searchsorted(od, day, "left")
            f["muscle_365"] = _window_count(od[(o["injury_type"] == "muscle_tendon").to_numpy()], day, 365)
            f["lower_365"] = _window_count(od[o["region"].isin(LOWER_BODY).to_numpy()], day, 365)
            last = np.searchsorted(od, day, "left") - 1
            f["days_since_onset"] = np.where(last >= 0, day - od[np.maximum(last, 0)], np.nan)
            f["inj_60"] = _window_count(od, day, 60)
            f["inj_120"] = _window_count(od, day, 120)
            f["soreness_365"] = _window_count(od[(o["injury_type"] == "soreness").to_numpy()], day, 365)
            f["inj_decay"] = decayed(od)
        else:
            zeros = np.zeros(n)
            f.update(inj_365=zeros, inj_all=zeros, muscle_365=zeros, lower_365=zeros, days_since_onset=np.full(n, np.nan),
                     inj_60=zeros, inj_120=zeros, soreness_365=zeros, inj_decay=zeros)
        observed = np.maximum(k - np.searchsorted(day, HISTORY_START, "left"), 0)   # games played since the reports begin
        with np.errstate(invalid="ignore", divide="ignore"):
            f["inj_per100"] = np.where(observed >= 20, 100 * f["inj_all"] / np.maximum(observed, 1), np.nan)
        # the same rate pulled toward the league average when there are few games to judge by
        prior_games = 1 / LEAGUE_INJURIES_PER_GAME
        f["prone_shrunk"] = 100 * (f["inj_all"] + 1) / (observed + prior_games)
        s = spells_by_player.get(pid)
        if s is not None:
            end = s["end_date"].to_numpy().astype("datetime64[D]").astype(np.int64)
            ret = s["return_date"].to_numpy().astype("datetime64[D]")
            ret = np.where(np.isnat(ret), np.datetime64("NaT"), ret).astype("datetime64[D]")
            missed = s["games_missed"].to_numpy(dtype=float)
            last = np.searchsorted(end, day, "left") - 1
            has = last >= 0
            li = np.maximum(last, 0)
            f["games_since_return"] = np.where(has, k - np.searchsorted(day, end[li], "right"), np.nan)
            ret_day = ret[li].astype(np.int64).astype(float)
            ret_day[np.isnat(ret[li])] = np.nan
            f["days_since_return"] = np.where(has, day - ret_day, np.nan)
            f["last_games_missed"] = np.where(has, missed[li], np.nan)
        else:
            f.update(games_since_return=np.full(n, np.nan), days_since_return=np.full(n, np.nan),
                     last_games_missed=np.full(n, np.nan))
        out.append(pd.DataFrame(f))
    return pd.concat(out, ignore_index=True).set_index("row_index")


def team_injury_rate(rows: pd.DataFrame, onsets: pd.DataFrame, team_games: pd.DataFrame) -> np.ndarray:
    """New injuries per team game for the player's team over the previous 365 days."""
    eligible = onsets[onsets["new_injury"]]
    rate = np.full(len(rows), np.nan)
    on = {t: np.sort(d["onset_date"].to_numpy().astype("datetime64[D]").astype(np.int64)) for t, d in eligible.groupby("team")}
    games = {t: np.sort(d["game_date"].to_numpy().astype("datetime64[D]").astype(np.int64)) for t, d in team_games.groupby("team")}
    day = rows["game_date"].to_numpy().astype("datetime64[D]").astype(np.int64)
    for team in rows["team"].unique():
        mask = (rows["team"] == team).to_numpy()
        g = games.get(team)
        if g is None:
            continue
        n_games = _window_count(g, day[mask], 365)
        n_on = _window_count(on.get(team, np.array([], dtype=np.int64)), day[mask], 365)
        with np.errstate(invalid="ignore", divide="ignore"):
            rate[mask] = np.where(n_games >= 20, n_on / np.maximum(n_games, 1), np.nan)
    return rate


def build(pg: pd.DataFrame, onsets: pd.DataFrame, schedule: pd.DataFrame, seasons) -> pd.DataFrame:
    """Played rows with every feature attached (labels are added by the caller)."""
    rows = pg[pg["absence"] == "played"].copy()
    pf = player_features(pg, onsets)
    rows = rows.join(pf, how="left")
    ts = team_schedule(schedule)
    rows = rows.merge(ts, on=["game_id", "team"], how="left", suffixes=("", "_sched"))
    if "is_home_sched" in rows:
        rows = rows.drop(columns="is_home_sched")
    rows["is_home"] = rows["is_home"].astype(int)
    bio, exp = bios(seasons)
    rows = rows.merge(bio, on="player_id", how="left").merge(exp, on=["player_id", "season"], how="left")
    rows["age"] = (rows["game_date"] - rows["birth"]).dt.days / 365.25
    rows["bmi"] = 703 * rows["weight_lb"] / rows["height_in"] ** 2
    team_games = pg[["team", "game_id", "game_date"]].drop_duplicates(["team", "game_id"])
    rows["team_inj_rate_365"] = team_injury_rate(rows, onsets, team_games)
    if "longest_stint" in rows:
        rows = rows.assign(cur_minutes=rows["minutes"], cur_min_drop=rows["minutes"] - rows["min_avg10"],
                           cur_early_exit=rows["early_exit"], cur_last_on_min=rows["last_on"] / 60,
                           cur_longest_stint=rows["longest_stint"] / 60, cur_q4ot_min=rows["q4ot_sec"] / 60,
                           cur_n_stints=rows["n_stints"], cur_margin=rows["final_margin"])
    return rows
