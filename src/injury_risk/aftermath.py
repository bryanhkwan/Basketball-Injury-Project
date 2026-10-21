"""What an injury does to a career: how long it keeps a player out, whether they come back the same, how durable they
are after it, and whether they stay in the league.

The injuries are the NBA profiles' (outputs/profiles/nba.json) from 2018-19 on that cost 10 or more games, ACL, Achilles
and meniscus injuries the listing names, and concussions. Listings that follow each other before the player plays again
are one absence; one with two injuries in different parts of the body that each cost 10 or more games (Klay Thompson's
torn ACL, then torn Achilles) counts in the totals but not by diagnosis. The diagnosis is the news's where the research
named it (confirmed or reported), else the listing's. Time out runs from the game the news says they were hurt in, else
their last game before the listing when it came within ten days, to the next game they played; an injury with no return
yet counts as still out (Kaplan-Meier).

Came back the same: the year before the injury against the first and second years back, in regular-season games, each
with 15 games and the minutes to judge by. Each change is set against the change over the same dates for the ten players
most like them the day they were hurt (age, minutes, production per 36 and the share of their team's games they played,
standardized) who played those dates too, so aging and the league's drift drop out. Durability and career compare the
year back and the seasons after with ten players matched the same way, whether or not they played on. Intervals resample
players.

Associations in observational data: who gets hurt, and who comes back, isn't random.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from . import features, news, news_research
from .paths import OUTPUTS, PROCESSED
from .profiles import FOLLOW_UP_CARE

OUT = OUTPUTS / "aftermath"
PROFILES = OUTPUTS / "profiles" / "nba.json"
FIRST_DAY = "2018-10-01"       # the reports begin in 2018-19
YEAR = pd.Timedelta(days=365)
SAME_GAME_GAP = 10             # days: a listing this soon after the player's last game follows from that game
ACTIVE = pd.Timedelta(days=10) # matched players played within this long before the injured player's last game
MIN_GAMES, MIN_PRE_MINUTES, MIN_POST_MINUTES = 15, 300, 200
K = 10                         # matched players per injury
STAND_INS = 5                  # players who weren't hurt put through the same steps for each injury (the placebo)
MIN_SHOWN = 5                  # injuries a result needs to be shown
WEEKS = 104                    # the recovery curve: the share still out each week for two years
BREAK = 14                     # days without an NBA game that make a break in the season (the offseason, the 2020 pause)
REPS = 1000
SEED = 0
SERIOUS = {"acl", "achilles", "meniscus"}                     # followed whatever they cost
NAMED = {"acl", "achilles", "meniscus", "mcl", "concussion"}   # kinds the listing names in words, not by region and type
# key, name, the news's labels, the profiles' kinds, and the body regions a label must be filed under (None: any)
GROUPS = [
    ("acl", "Torn ACL", {"Torn ACL"}, {"acl"}, None),
    ("achilles", "Torn Achilles", {"Achilles tear"}, {"achilles"}, None),
    ("meniscus", "Torn meniscus", {"Torn meniscus"}, {"meniscus"}, None),
    ("knee_sprain", "Knee sprain or bone bruise", {"MCL sprain", "Torn MCL", "PCL sprain", "ACL sprain", "Knee sprain",
                                                   "Knee bone bruise", "Knee hyperextension"}, {"mcl"}, None),
    ("foot_fracture", "Broken foot", {"Foot fracture"}, {"foot_fracture"}, None),
    ("bone_stress", "Stress fracture or reaction", {"Stress fracture", "Stress reaction"}, set(), None),
    ("leg_fracture", "Broken leg, knee or ankle", {"Leg fracture", "Knee fracture", "Ankle fracture"}, set(), None),
    ("hand_fracture", "Broken hand, finger or wrist", {"Hand or finger fracture", "Wrist fracture"}, {"hand_fracture"}, None),
    ("ankle", "Ankle sprain", {"Ankle sprain", "High ankle sprain"}, {"ankle_sprain"}, None),
    ("muscle", "Muscle strain", {"Hamstring strain", "Calf strain", "Groin strain", "Quad strain", "Torn quadriceps",
                                 "Hip flexor strain", "Abdominal or oblique strain"}, {"hamstring", "calf", "groin"}, None),
    ("back", "Back injury", {"Back strain or spasms", "Herniated disc"}, {"region:back"}, None),
    ("shoulder", "Shoulder injury", {"Shoulder dislocation", "Shoulder subluxation", "AC joint sprain", "Rotator cuff injury",
                                     "Torn labrum"}, {"region:shoulder"}, {"shoulder"}),
    ("concussion", "Concussion", {"Concussion"}, {"concussion"}, None),
]
CASES = {"acl", "achilles", "meniscus", "foot_fracture"}   # groups whose injuries are listed one by one
# parts of the body: listings of one absence in the same part are one injury named more than one way ("right lower leg",
# then "right Achilles surgery"); two parts that each cost 10 or more games are two injuries
PART = {"knee": "knee", "thigh": "hip and thigh", "hamstring": "hip and thigh", "groin": "hip and thigh", "hip": "hip and thigh",
        "calf": "lower leg and foot", "leg": "lower leg and foot", "achilles": "lower leg and foot", "ankle": "lower leg and foot",
        "foot": "lower leg and foot", "back": "back and trunk", "trunk": "back and trunk", "hand": "arm", "arm": "arm",
        "elbow": "arm", "shoulder": "arm", "head_neck": "head", "concussion": "head"}
STATS = ["minutes", "pts", "reb", "ast", "stl", "blk", "tov", "fga", "fta", "starter", "rim_fga", "dunk_fga", "pbp_minutes"]
METRICS = [   # key, name
    ("mpg", "Minutes a game"), ("starter", "Share of games started"),
    ("production36", "Points, rebounds, assists, steals and blocks less turnovers, per 36 minutes"),
    ("pts36", "Points per 36"), ("reb36", "Rebounds per 36"), ("ast36", "Assists per 36"),
    ("stocks36", "Steals and blocks per 36"), ("ts", "True shooting"), ("usage36", "Shots, free throws and turnovers per 36"),
    ("rim36", "Shots at the rim per 36"), ("dunk36", "Dunks per 36"),
]
MATCH = ["age", "mpg", "production36", "played_share"]
OUTCOMES = [   # key, name: each against the matched players' average
    ("played_share", "Share of the team's games played in the year back"),
    ("new_injuries", "New injuries in the year back"),
    ("same_region", "Hurt again in the same body region in the year back"),
    ("other_regions", "New injuries elsewhere in the body in the year back"),
    ("new_team", "On a new team in the year back"),
    ("playing_2", "Playing two seasons on"), ("playing_3", "Playing three seasons on"),
]
SPAN = 100_000                 # days per player in the game keys below
DAY0 = np.datetime64("2000-01-01", "D")


def group_of(label: str | None, kind: str, region: str) -> str | None:
    """The diagnosis group: by the news's label, else by the listing's kind when the news named nothing more (no label,
    one that only repeats the body region, or "Other" for an injury the listing names in words)."""
    for key, _, labels, _, regions in GROUPS:
        if label in labels and (regions is None or region in regions):
            return key
    if label is None or label in news.GENERIC or (label == "Other" and kind in NAMED):
        return next((key for key, _, _, kinds, _ in GROUPS if kind in kinds), None)
    return None


# --- the games --------------------------------------------------------------------------------------------------------

def day_number(d) -> np.ndarray:
    d = d.to_numpy() if isinstance(d, pd.Series) else np.datetime64(d)
    return (d.astype("datetime64[D]") - DAY0).astype(np.int64)


class Logs:
    """Every player's regular-season games, for totals over any stretch of days for one player or all of them at once,
    and every game they played (with their team and season) for the clock and the career."""

    def __init__(self, pg: pd.DataFrame):
        self.ids = np.sort(pg["player_id"].unique())
        self.index = {pid: i for i, pid in enumerate(self.ids)}
        regular = pg[pg["season_type"] == "regular-season"]
        played = regular[regular["status"] == "played"].copy()
        played["starter"] = played["starter"].eq(True).astype(float)
        played["pbp_minutes"] = np.where(played["rim_fga"].notna(), played["minutes"], 0.0)   # games with play-by-play
        played[STATS] = played[STATS].fillna(0.0).astype(float)
        played = played.assign(key=self.keys(played)).sort_values("key")
        self.played_keys = played["key"].to_numpy()
        self.cum = np.vstack([np.zeros(len(STATS)), played[STATS].to_numpy().cumsum(axis=0)])
        self.rostered_keys = np.sort(self.keys(regular))
        anyplay = pg[pg["status"] == "played"].sort_values("game_date")
        self.appeared_keys = np.sort(self.keys(anyplay))
        self.games = {pid: (g["game_date"].to_numpy(), g["team"].to_numpy(), g["season"].to_numpy())
                      for pid, g in anyplay.groupby("player_id")}
        self.seasons = {pid: set(g[2]) for pid, g in self.games.items()}

    def keys(self, df: pd.DataFrame) -> np.ndarray:
        return df["player_id"].map(self.index).to_numpy() * SPAN + day_number(df["game_date"])

    def bounds(self, keys, start, end, at) -> tuple[np.ndarray, np.ndarray]:
        at = np.arange(len(self.ids)) if at is None else np.asarray(at)
        return np.searchsorted(keys, at * SPAN + day_number(start)), np.searchsorted(keys, at * SPAN + day_number(end))

    def totals(self, start, end, at=None) -> tuple[np.ndarray, np.ndarray]:
        """(regular-season games played, their totals in STATS order) with start <= date < end, for the players at
        positions ``at`` in ``ids`` (all of them by default)."""
        i, j = self.bounds(self.played_keys, start, end, at)
        return j - i, self.cum[j] - self.cum[i]

    def rostered(self, start, end, at=None) -> np.ndarray:
        """Regular-season games on a roster (played, inactive or not used) with start <= date < end."""
        i, j = self.bounds(self.rostered_keys, start, end, at)
        return j - i

    def appeared(self, start, end, at=None) -> np.ndarray:
        """Games of any kind played with start <= date < end."""
        i, j = self.bounds(self.appeared_keys, start, end, at)
        return j - i

    def played(self, pid) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """(dates, teams, seasons) of every game the player played."""
        none = np.array([], dtype=object)
        return self.games.get(pid, (np.array([], dtype="datetime64[ns]"), none, none))

    def plays_in(self, pid, season) -> float:
        return float(season in self.seasons.get(pid, ()))

    def season_of(self, pid, day) -> int:
        dates, _, seasons = self.played(pid)
        return int(seasons[np.searchsorted(dates, np.datetime64(day), side="right") - 1])

    def new_team(self, pid, last, back) -> float:
        """1 if they played for a team other than their team at ``last`` in the year from ``back``."""
        dates, teams, _ = self.played(pid)
        at = teams[dates <= np.datetime64(last)]
        after = teams[(dates >= np.datetime64(back)) & (dates < np.datetime64(back + YEAR))]
        return float((after != at[-1]).any()) if len(at) and len(after) else np.nan


def metrics(games, totals) -> pd.DataFrame:
    """Rates from stretches of games: games played and their totals in STATS order, one row each."""
    s = np.atleast_2d(totals)
    games = np.atleast_1d(games).astype(float)
    v = dict(zip(STATS, s.T))
    with np.errstate(divide="ignore", invalid="ignore"):
        def per36(x, minutes=v["minutes"]):
            return np.where(minutes > 0, 36 * x / minutes, np.nan)
        shots = 2 * (v["fga"] + 0.44 * v["fta"])
        out = pd.DataFrame(dict(
            games=games, minutes=v["minutes"], mpg=np.where(games > 0, v["minutes"] / games, np.nan),
            starter=np.where(games > 0, v["starter"] / games, np.nan), pts36=per36(v["pts"]), reb36=per36(v["reb"]),
            ast36=per36(v["ast"]), stocks36=per36(v["stl"] + v["blk"]), ts=np.where(shots > 0, v["pts"] / shots, np.nan),
            usage36=per36(v["fga"] + 0.44 * v["fta"] + v["tov"]), rim36=per36(v["rim_fga"], v["pbp_minutes"]),
            dunk36=per36(v["dunk_fga"], v["pbp_minutes"])))
        out["production36"] = out["pts36"] + out["reb36"] + out["ast36"] + out["stocks36"] - per36(v["tov"])
    return out


def everyone_at(logs: Logs, birth: np.ndarray, day) -> pd.DataFrame:
    """Every player playing around ``day`` (a game in the ACTIVE days up to it, as an injured player played their last
    game that day) with the games to judge by in the year before it, as they looked then. ``birth``: birth dates lined
    up with ``logs.ids``, NaT where unknown."""
    start = day - YEAR
    games, totals = logs.totals(start, day)
    m = metrics(games, totals)
    m["player_id"], m["at"] = logs.ids, np.arange(len(logs.ids))
    m["age"] = (np.datetime64(day) - birth) / np.timedelta64(1, "D") / 365.25
    m["played_share"] = games / np.maximum(logs.rostered(start, day), np.maximum(games, 1))
    keep = ((games >= MIN_GAMES) & (m["minutes"].to_numpy() >= MIN_PRE_MINUTES) & m["age"].notna().to_numpy()
            & (logs.appeared(day - ACTIVE, day + pd.Timedelta(days=1)) > 0))
    return m[keep].reset_index(drop=True)


def nearest(target, pool: pd.DataFrame, k: int = K) -> np.ndarray:
    """Positions in ``pool`` of the k players closest to ``target`` on MATCH, each standardized over the pool."""
    x = pool[MATCH].to_numpy(dtype=float)
    sd = x.std(axis=0)
    sd[sd == 0] = 1
    d = np.sqrt((((x - np.array([target[c] for c in MATCH], dtype=float)) / sd) ** 2).sum(axis=1))
    return np.argsort(d, kind="stable")[:k]


def corrected(me, pool: pd.DataFrame, pick: np.ndarray, values, use=None) -> float:
    """The mean of ``values`` (lined up with ``pool``) over the matched players at positions ``pick``, less what a
    straight line on MATCH, fitted over the pool, puts down to the ways they still differ from ``me`` (bias-corrected
    matching). ``use``: the pool players the outcome counts for (all of them by default)."""
    v = np.asarray(values, dtype=float)
    ok = np.isfinite(v) if use is None else np.isfinite(v) & use
    chosen = pick[ok[pick]]
    if not len(chosen):
        return np.nan
    x = pool[MATCH].to_numpy(dtype=float)
    gap = np.array([me[c] for c in MATCH], dtype=float) - x[chosen].mean(axis=0)
    if ok.sum() <= 2 * len(MATCH):
        return float(v[chosen].mean())
    slope = np.linalg.lstsq(np.c_[np.ones(ok.sum()), x[ok]], v[ok], rcond=None)[0][1:]
    return float(v[chosen].mean() + gap @ slope)


# --- the injuries -------------------------------------------------------------------------------------------------------

def from_news() -> dict:
    """NBA target id -> (the diagnosis the research confirmed or reported, the date of the game they were hurt in, the
    team's first return timeline as [fewest, most] weeks)."""
    out = {}
    for f in news_research.read_jsonl(news.FACTS):
        if f["target"].startswith("nba:") and f["status"] != "not_found":
            label = news._get(f, "diagnosis.label") if f["status"] in ("confirmed", "reported") else None
            out[f["target"]] = (label, news._get(f, "game.date"), news._get(f, "expected.weeks"))
    return out


def episodes(logs: Logs, profiles: dict, said: dict) -> pd.DataFrame:
    """One row per absence worth following: the player, the last game before it, when they were hurt, the next game
    they played, what it was and the games it cost. The injury that names it is the one with a diagnosis that cost the
    most games. ``said``: from_news()."""
    rows = []
    for p in profiles["players"]:
        dates = logs.played(p["id"])[0]
        absences = {}
        for first, text, kind, region, games, *_ in p["inj"]:
            if first < FIRST_DAY or (games < 10 and FOLLOW_UP_CARE.search(text)):
                continue   # a listing for care of an injury that came before
            day = np.datetime64(first)
            last, after = np.searchsorted(dates, day) - 1, np.searchsorted(dates, day, side="right")
            if last < 0:
                continue
            label, hurt, weeks = said.get(f"nba:{p['id']}:{first}:{region}", (None, None, None))
            absences.setdefault(dates[last], []).append(dict(
                first=first, text=text, kind=kind, region=region, games=games, label=label, hurt=hurt, weeks=weeks,
                group=group_of(label, kind, region), back=dates[after] if after < len(dates) else None))
        for last, parts in absences.items():
            main = max(parts, key=lambda x: (x["group"] is not None, x["games"]))
            games = sum(x["games"] for x in parts)
            if not (games >= 10 or main["kind"] in SERIOUS or main["group"] == "concussion"):
                continue
            last = pd.Timestamp(last)
            part = PART.get(main["region"], main["region"])
            same = [x for x in parts if PART.get(x["region"], x["region"]) == part]
            # when they were hurt: the news's game, else the last game before a listing that soon followed it, unless
            # the absence began with an injury somewhere else
            told = [pd.Timestamp(x["hurt"]) for x in same if x["hurt"] and x["hurt"] <= x["first"]]
            gap = (pd.Timestamp(parts[0]["first"]) - last).days
            weeks = next((x["weeks"] for x in [main, *parts] if x["weeks"]), [None, None])
            rows.append(dict(player_id=p["id"], player=p["n"], first_listed=parts[0]["first"], listed_as=main["text"],
                             kind=main["kind"], region=main["region"], label=main["label"], group=main["group"],
                             games_missed=games, last_game=last,
                             two_injuries=len({PART.get(x["region"], x["region"]) for x in parts if x["games"] >= 10}) > 1,
                             hurt=min(told) if told else (last if gap <= SAME_GAME_GAP and parts[0] in same else pd.NaT),
                             back=pd.Timestamp(parts[0]["back"]) if parts[0]["back"] is not None else pd.NaT,
                             forecast_lo=weeks[0], forecast_hi=weeks[1]))
    columns = ["player_id", "player", "first_listed", "listed_as", "kind", "region", "label", "group", "games_missed", "last_game",
               "two_injuries", "hurt", "back", "forecast_lo", "forecast_hi"]
    return pd.DataFrame(rows, columns=columns).sort_values(["first_listed", "player_id"]).reset_index(drop=True)


# --- following them -----------------------------------------------------------------------------------------------------

def came_back(logs: Logs, me: pd.Series, pool: pd.DataFrame, back, end: pd.Timestamp, years=(1, 2)) -> dict:
    """``me`` (a row of everyone_at) in each year from ``back`` against the year before, set against the same change for
    the K players in ``pool`` most like them who played that year too: y<n>_<metric>, y<n>_matched_change_<metric> and
    y<n>_effect_<metric>, the one less the other."""
    row = {}
    for n in years:
        a = back + (n - 1) * YEAR
        if pd.isna(back) or a >= end:
            break
        b = min(a + YEAR, end)
        games, totals = logs.totals(a, b, [me["at"]])
        if games[0] < MIN_GAMES or totals[0, 0] < MIN_POST_MINUTES:
            continue
        g2, t2 = logs.totals(a, b, pool["at"])
        ok = (g2 >= MIN_GAMES) & (t2[:, 0] >= MIN_POST_MINUTES)
        if ok.sum() < K:
            continue
        others = pool[ok].reset_index(drop=True)
        pick, after = nearest(me, others), metrics(g2[ok], t2[ok])
        mine = metrics(games, totals).iloc[0]
        for k, _ in METRICS:
            matched = corrected(me, others, pick, after[k].to_numpy() - others[k].to_numpy())
            row[f"y{n}_{k}"], row[f"y{n}_matched_change_{k}"] = mine[k], matched
            row[f"y{n}_effect_{k}"] = mine[k] - me[k] - matched
    return row


def follow(logs: Logs, birth: np.ndarray, ep: pd.DataFrame, onsets: pd.DataFrame,
           end: pd.Timestamp) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Each injury with the player before and after it, and the same for their matched players; and the placebo: for
    each injury, STAND_INS of the others that day put through the same comparison over the same dates. With no injury
    there is nothing to find, so what the comparison finds for them is its own bias."""
    long = onsets[onsets["games_missed"] >= 10]
    fresh = onsets[onsets["new_injury"] & ~onsets["reason"].fillna("").str.contains(FOLLOW_UP_CARE)]
    last_season = end.year if end >= pd.Timestamp(f"{end.year}-04-30") else end.year - 1
    rng = np.random.default_rng(SEED)
    out, placebo = [], []
    for e in ep.itertuples(index=False):
        L, R = e.last_game, e.back
        pool = everyone_at(logs, birth, L)
        me = pool[pool["player_id"] == e.player_id]
        if me.empty:
            continue
        me = me.iloc[0]
        # the others, less anyone out with a long injury that day
        out_then = set(long.loc[(long["onset_date"] <= L) & (long["end_date"] >= L), "player_id"])
        pool = pool[(pool["player_id"] != e.player_id) & ~pool["player_id"].isin(out_then)].reset_index(drop=True)
        pick = nearest(me, pool)
        matched = pool.iloc[pick]
        row = dict(e._asdict(), season=logs.season_of(e.player_id, L),
                   **{f"pre_{c}": me[c] for c in me.index if c not in ("player_id", "at")},
                   **{f"matched_{c}": matched[c].mean() for c in MATCH})
        # came back the same: the first and second years back; and the year back for the stand-ins
        row.update(came_back(logs, me, pool, R, end))
        stand_ins = []
        for i in rng.choice(len(pool), min(STAND_INS, len(pool)), replace=False):
            others = pool.drop(i).reset_index(drop=True)
            stand_ins.append((i, others, nearest(pool.iloc[i], others), dict(
                player_id=pool.at[i, "player_id"], injury=len(out), **came_back(logs, pool.iloc[i], others, R, end, years=(1,)))))
        # durability and career, for the player and then everyone else that day: (values, whether each one counts)
        ids, at = np.r_[e.player_id, pool["player_id"]], np.r_[me["at"], pool["at"]]
        outcomes = {}
        if pd.notna(R) and R + YEAR <= end:   # the full year back, for those on a roster in it
            games, _ = logs.totals(R, R + YEAR, at)
            rostered = logs.rostered(R, R + YEAR, at)
            on = rostered > 0
            new = fresh[(fresh["onset_date"] >= R) & (fresh["onset_date"] < R + YEAR)]
            same = new["region"] == e.region
            outcomes.update(played_share=(games / np.maximum(rostered, 1), on), new_injuries=(count_of(new, ids), on),
                            same_region=(np.isin(ids, new.loc[same, "player_id"]).astype(float), on),
                            other_regions=(count_of(new[~same], ids), on),
                            new_team=(np.array([logs.new_team(pid, L, R) for pid in ids]), on))
        for n in (2, 3):   # still playing the seasons after
            if row["season"] + n <= last_season:
                outcomes[f"playing_{n}"] = (np.array([logs.plays_in(pid, row["season"] + n) for pid in ids]),
                                            np.ones(len(ids), dtype=bool))
        for k, (v, use) in outcomes.items():
            row[k], row[f"matched_{k}"] = v[0], corrected(me, pool, pick, v[1:], use[1:])
            for i, others, near, t in stand_ins:
                if use[1 + i] and np.isfinite(v[1 + i]):
                    t[k] = v[1 + i]
                    t[f"matched_{k}"] = corrected(pool.iloc[i], others, near, np.delete(v[1:], i), np.delete(use[1:], i))
        out.append(row)
        placebo += [t for *_, t in stand_ins]
    return pd.DataFrame(out), pd.DataFrame(placebo)


def count_of(onsets: pd.DataFrame, ids: np.ndarray) -> np.ndarray:
    return onsets["player_id"].value_counts().reindex(ids).fillna(0).to_numpy()


# --- summaries ----------------------------------------------------------------------------------------------------------

def interval(values, players, reps: int = REPS, seed: int = SEED) -> tuple[float, float]:
    """95% interval of the mean, resampling players with all their injuries."""
    v = np.asarray(values, dtype=float)
    keep = ~np.isnan(v)
    v, players = v[keep], np.asarray(players)[keep]
    if len(v) < 3:
        return np.nan, np.nan
    codes, _ = pd.factorize(players)
    sums, counts = np.bincount(codes, v), np.bincount(codes)
    pick = np.random.default_rng(seed).integers(0, len(sums), (reps, len(sums)))
    means = sums[pick].sum(axis=1) / counts[pick].sum(axis=1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def time_to_return(days, back) -> dict:
    """Kaplan-Meier: the days by which half are back, the shares back within one and two years, and the share still out
    each week for WEEKS weeks. ``days``: to the return, or to the end of the data for those not back."""
    t, back = np.asarray(days, dtype=float), np.asarray(back, dtype=bool)
    keep = ~np.isnan(t)
    t, back = t[keep], back[keep]
    still_out, curve = 1.0, []
    for day in np.unique(t[back]):
        still_out *= 1 - (back & (t == day)).sum() / (t >= day).sum()
        curve.append((day, still_out))

    def still(limit):
        return min([s for d, s in curve if d <= limit], default=1.0)
    return dict(timed=int(len(t)), median_days=next((float(d) for d, s in curve if s <= 0.5), None),
                back_within_a_year=1 - still(365), back_within_two_years=1 - still(730),
                still_out=[still(7 * w) for w in range(WEEKS + 1)])


def timelines(x: pd.DataFrame) -> dict | None:
    """Teams' first return timelines against when the player came back, counted from the first listing (about when a
    timeline is given): sooner than the fewest weeks, within the range, or later than the most, half a week either way.
    Only a range or a single figure ("four to six weeks", "two weeks"), not "at least", and only returns that didn't
    wait out a break in the season."""
    have = x[x["forecast_hi"].notna() & x["back"].notna() & ~x["crosses_break"]]
    if len(have) < MIN_SHOWN:
        return None
    weeks = ((have["back"] - pd.to_datetime(have["first_listed"])).dt.days / 7).to_numpy()
    lo, hi = have["forecast_lo"].to_numpy(dtype=float), have["forecast_hi"].to_numpy(dtype=float)
    sooner, later = weeks < lo - 0.5, weeks > hi + 0.5
    return dict(injuries=len(have), sooner=int(sooner.sum()), within=int((~sooner & ~later).sum()), later=int(later.sum()),
                late_by=float(np.median((weeks - hi)[later])) if later.any() else None)


def crosses_break(start, back, days: np.ndarray) -> bool:
    """Whether the days from ``start`` to ``back`` took in BREAK or more days with no NBA game. ``days``: every game day,
    sorted."""
    if pd.isna(back):
        return False
    inside = days[(days > np.datetime64(start)) & (days < np.datetime64(back))]
    gaps = np.diff(np.r_[np.datetime64(start, "D"), inside.astype("datetime64[D]"), np.datetime64(back, "D")])
    return bool(len(gaps) and gaps.max() >= np.timedelta64(BREAK, "D"))


def summarize(f: pd.DataFrame, end: pd.Timestamp) -> list[dict]:
    out = []
    one = f[~f["two_injuries"]]
    for key, name, x in [("all", "Every injury followed", f)] + [(k, n, one[one["group"] == k]) for k, n, *_ in GROUPS]:
        if len(x) < MIN_SHOWN:
            continue
        days = np.where(x["back"].notna(), (x["back"] - x["hurt"]).dt.days, (end - x["hurt"]).dt.days)
        row = dict(key=key, name=name, injuries=len(x), players=x["player_id"].nunique(), not_back=int(x["back"].isna().sum()),
                   games_missed=dict(median=x["games_missed"].median(), quartiles=x["games_missed"].quantile([0.25, 0.75]).tolist()),
                   **time_to_return(days, x["back"].notna()))
        for n in (1, 2):
            row[f"year_{n}"] = effects(x, f"y{n}_")
        row["outcomes"] = differences(x)
        row["timelines"] = timelines(x)
        if key in CASES:
            row["cases"] = [dict(player_id=c.player_id, player=c.player, listed=c.first_listed, hurt=c.hurt, back=c.back,
                                 games_missed=c.games_missed,
                                 mpg_before=c.pre_mpg, mpg_after=getattr(c, "y1_mpg", None),
                                 production_before=c.pre_production36, production_after=getattr(c, "y1_production36", None))
                            for c in x.sort_values("first_listed").itertuples()]
        out.append(row)
    return out


def effects(x: pd.DataFrame, prefix: str, players: str = "player_id") -> list[dict]:
    """Each measure's mean before, after and change for the matched players, and the effect with its interval, from
    the columns came_back() wrote under ``prefix``."""
    out = []
    for k, label in METRICS:
        col = f"{prefix}effect_{k}"
        have = x.dropna(subset=[col]) if col in x else x.iloc[:0]
        if len(have) < MIN_SHOWN:
            continue
        after, matched = have[f"{prefix}{k}"], have[f"{prefix}matched_change_{k}"]
        lo, hi = interval(have[col], have[players])
        out.append(dict(metric=k, name=label, injuries=len(have), before=(after - matched - have[col]).mean(), after=after.mean(),
                        matched_change=matched.mean(), effect=have[col].mean(), lo=lo, hi=hi))
    return out


def differences(x: pd.DataFrame) -> list[dict]:
    """Each durability and career outcome: the mean for the injured, for their matched players, and the difference
    with its interval."""
    out = []
    for k, label in OUTCOMES:
        have = x.dropna(subset=[k, f"matched_{k}"]) if k in x else x.iloc[:0]
        if len(have) < MIN_SHOWN:
            continue
        diff = have[k] - have[f"matched_{k}"]
        lo, hi = interval(diff, have["player_id"])
        out.append(dict(outcome=k, name=label, injuries=len(have), them=have[k].mean(), matched=have[f"matched_{k}"].mean(),
                        difference=diff.mean(), lo=lo, hi=hi))
    return out


def by_injury(ep: pd.DataFrame, f: pd.DataFrame) -> dict:
    """'<player id>:<first listed>' -> when they were hurt and back, the days between (and whether they took in the
    offseason), the diagnosis group, and their first year back against the year before: [before, after, the matched
    players' change] for minutes a game and production per 36."""
    followed = f.set_index(["player_id", "first_listed"])
    out = {}
    for e in ep.itertuples(index=False):
        row = dict(group=e.group, two_injuries=e.two_injuries, hurt=e.hurt, back=e.back,
                   days=(e.back - e.hurt).days if pd.notna(e.back) and pd.notna(e.hurt) else None, offseason=e.crosses_break)
        if (e.player_id, e.first_listed) in followed.index:
            r = followed.loc[(e.player_id, e.first_listed)]
            if pd.notna(r.get("y1_mpg")):
                row["year_1"] = {k: [r[f"pre_{k}"], r[f"y1_{k}"], r[f"y1_matched_change_{k}"]] for k in ("mpg", "production36")}
        out[f"{e.player_id}:{e.first_listed}"] = row
    return out


def balance(f: pd.DataFrame) -> list[dict]:
    """How alike the injured and their matched players were the day they were hurt: the means, and the difference in
    the injured players' standard deviations."""
    return [dict(measure=c, injured=f[f"pre_{c}"].mean(), matched=f[f"matched_{c}"].mean(),
                 standardized_difference=(f[f"pre_{c}"] - f[f"matched_{c}"]).mean() / f[f"pre_{c}"].std()) for c in MATCH]


def plain(v):
    """JSON-ready: rounded numbers, dates as text, and None for what is missing."""
    if isinstance(v, dict):
        return {k: plain(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [plain(x) for x in v]
    if v is pd.NaT or isinstance(v, (pd.Timestamp, np.datetime64)):
        return None if pd.isna(v) else pd.Timestamp(v).strftime("%Y-%m-%d")
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    if isinstance(v, (int, np.integer)):
        return int(v)
    if isinstance(v, (float, np.floating)):
        return None if np.isnan(v) else round(float(v), 4)
    return v


# --- run ----------------------------------------------------------------------------------------------------------------

def export(log=print) -> dict:
    pg = pd.read_parquet(PROCESSED / "player_games.parquet", columns=["player_id", "game_date", "season", "season_type", "status",
                                                                      "team", *STATS[:-1]])
    logs = Logs(pg)
    end = pg["game_date"].max()
    bio, _ = features.bios(sorted(pg["season"].unique()))
    birth = (bio.assign(player_id=bio["player_id"].astype("int64")).set_index("player_id")["birth"]
             .reindex(logs.ids).to_numpy(dtype="datetime64[ns]"))
    ep = episodes(logs, json.loads(PROFILES.read_text(encoding="utf-8")), from_news())
    days = np.unique(pg["game_date"].to_numpy())
    ep["crosses_break"] = [crosses_break(h, b, days) for h, b in zip(ep["first_listed"].map(pd.Timestamp), ep["back"])]
    f, stand_ins = follow(logs, birth, ep, pd.read_parquet(PROCESSED / "onsets.parquet"), end)
    log(f"  {len(ep)} injuries; {len(f)} followed (the rest lacked a year of games before them), "
        f"{int(f['two_injuries'].sum())} of them absences with two injuries")
    summary = dict(end_of_data=end, injuries=len(ep), followed=len(f), two_injuries=int(f["two_injuries"].sum()),
                   balance=balance(f), placebo=dict(came_back=effects(stand_ins, "y1_"), outcomes=differences(stand_ins)),
                   groups=summarize(f, end))
    for r in summary["balance"]:
        log(f"  matched on {r['measure']}: {r['injured']:.3f} against {r['matched']:.3f} "
            f"(standardized difference {r['standardized_difference']:+.3f})")
    for r in summary["placebo"]["came_back"] + summary["placebo"]["outcomes"]:
        log(f"  placebo, {r.get('metric') or r['outcome']}: {r.get('effect', r.get('difference')):+.3f} "
            f"({r['lo']:+.3f} to {r['hi']:+.3f})")
    OUT.mkdir(parents=True, exist_ok=True)
    f.to_parquet(OUT / "injuries.parquet")   # every injury followed, for checking by eye (not on the site)
    (OUT / "summary.json").write_text(json.dumps(plain(summary), indent=1), encoding="utf-8")
    # each injury as its player's profile shows it (kept local, like the profiles; the site publishes a copy)
    (OUT / "players.json").write_text(json.dumps(plain(by_injury(ep, f)), separators=(",", ":")), encoding="utf-8")
    for g in summary["groups"]:
        y1 = {r["metric"]: r for r in g["year_1"]}
        line = f"  {g['name']}: {g['injuries']} injuries, median {g['games_missed']['median']:.0f} games out"
        if g["median_days"] is not None:
            line += f", half back in {g['median_days']:.0f} days"
        if "production36" in y1:
            r = y1["production36"]
            line += f"; production per 36 {r['effect']:+.2f} ({r['lo']:+.2f} to {r['hi']:+.2f}) in year one, n={r['injuries']}"
        log(line)
    return summary
