"""Plays a player was credited with just before he left a game he got hurt in.

Most injuries leave no trace in the play-by-play: the player finishes the game, gets hurt in practice, or
the problem builds up. Some show as an injury exit: the player leaves a competitive game early, never comes
back, ends well under his usual minutes, and the team's next game is the first he misses with a new
injury. These are injuries that ended a player's night early, mostly in the first half, and the severe end
(each cost at least a game). The plays he was credited with in the seconds before he left (rebounds,
shots, fouls drawn, steals...) are the closest the play-by-play gets to "what he was doing". It cannot see
the mechanisms injury research finds most often: landing on another player's foot, elbows, a cut or
landing with no contact, or a contested rebound someone else secured.

Design (case-crossover inside each player): each injury exit is compared with the same player's ordinary
exits that season, times he left the floor and came back. Players only leave at dead balls, so the plays
before any exit look alike; what is left over is what sets an injury exit apart. Mantel-Haenszel odds
ratios over player-season strata, RBG intervals, Benjamini-Hochberg q-values across the main table. A
finding needs q < 0.05, at least 10 exposed injury exits and the same direction in 2019-20 to 2021-22 and
2022-23 to 2025-26. Checks beside each one:
- within the same kind of stoppage (own-team timeout, opponent timeout, foul, free throws, turnover...);
- against "null exits": a random moment on the floor followed by leaving at the first dead ball, which
  copies how a hurt player gets off the floor (a fouled player shoots his own free throws first);
- against early exits with no injury after them (the player played the next game), which shows what any
  early exit looks like (benching after a turnover, foul trouble);
- each kind of injury against all other injury exits, which cancels anything shared by every injury exit.

Who is on the floor comes from each period's starters (the lineup columns at its first play with a full
lineup) and the substitution log ("SUB: <in> FOR <out>", person_id = the player going out; the incoming
name is matched within the team, accents ignored, against the log's own names, the play-by-play's and the
box score's; the lineup columns settle the few left). Minutes rebuilt this way match the box score to a
median of 0.00 (2024-25: 164 player-games more than a minute off). The lineup columns follow possessions
and lag a substitution by a few plays, so they never time an exit. The stoppage at an exit is a timeout,
foul or violation logged at that second, or else the play before the substitution; a team rebound after a
missed free throw counts as the free throws, and a live-ball play there means no stoppage was logged. Conventions needed to reproduce the numbers: usual minutes is the mean
of the previous 10 games played (at least 3); the margin at a moment is the last posted score at or before
its second; a window is (t - W, t] in game seconds inside the moment's period; a player who goes out and
comes back in at the same second never left.
"""
from __future__ import annotations

import json
import re
import unicodedata

import numpy as np
import pandas as pd

from . import causes, sources
from .paths import OUTPUTS, PROCESSED
from .pbp import GAME_PREFIXES, ON_COURT, _elapsed, is_rim

OUT = OUTPUTS / "moments"
SEASONS = causes.SEASONS
SPLIT_SEASON = causes.SPLIT_SEASON
WINDOW = 30                # seconds of game clock before an exit that count as "just before" (fixed in advance)
WINDOWS = (15, 30, 60, 120)
LAST_PLAY_WINDOW = 120     # how far back to look for the player's last play
MIN_LEFT = 6 * 60          # an exit counts only with at least this much of the game left...
MAX_MARGIN = 15            # ...in a game within this many points at the time...
SHORT_GAME = 0.6           # ...for an injury exit, a game under this share of his usual minutes...
MIN_USUAL = 12             # ...when he usually plays at least this many minutes (previous 10 games)
SHORT_VARIANTS = (0.5, 0.75, 0.8, None)   # case definitions tried as a sensitivity check (None: no minutes rule)
CHECKED = ("any", "ankle", "muscle", "hand")   # groups with a finding, run under those definitions and substitutions only
RANDOM_PER_GAME = 2        # random moments on the floor per comparison game
FDR = 0.05
MIN_EXPOSED = 10           # fewer exposed injury exits than this: too few to say
FIRST_TEAM_ID = 1_610_612_700   # person ids at or above this are teams, not players
TICKS = 10                 # times are packed in tenths of a second...
SCALE = 100_000            # ...inside one block per (game, player, period); a game lasts under 4,100 s
SUB_TEXT = re.compile(r"^SUB:\s*(.+?)\s+FOR\s+(.+?)\s*$")
NOT_INJURY = re.compile(r"personal|family|influenza|congestion|infection|throat|dental|appendectom|neuropathy|"
                        r"illness|virus|injury recovery|maintenance|management|reconditioning", re.I)   # no new injury moment
SUFFIX = re.compile(r"\s+(jr\.?|sr\.?|ii|iii|iv)$")
PLAYER_ACTIONS = {"Made Shot", "Missed Shot", "Free Throw", "Rebound", "Foul", "Turnover", "", "Jump Ball", "Violation"}

GROUPS = [   # id, plain name
    ("ankle", "Ankle"),
    ("ankle_sprain", "Ankle sprain"),
    ("knee", "Knee"),
    ("foot", "Foot and toe"),
    ("muscle", "Pulled muscles (hamstring, calf, groin, thigh, Achilles, hip flexor, oblique)"),
    ("back_hip", "Back and hip"),
    ("hand", "Hand, wrist, finger and arm"),
    ("head", "Head, face and concussions"),
    ("shoulder", "Shoulder"),
    ("contusion", "Knocks and bruises (contusions, any body part)"),
    ("other", "Everything else"),
]
ALL = ("any", "Any new injury")
CROSS_CUTTING = {"ankle_sprain", "contusion"}

PLAYS = [   # id, plain label: plays the player himself was credited with
    ("rebound", "Rebound"),
    ("off_rebound", "Offensive rebound"),
    ("def_rebound", "Defensive rebound"),
    ("rim", "Shot at the rim (layup, dunk, tip-in)"),
    ("drive", "Drove or cut to the basket"),
    ("dunk", "Dunk"),
    ("putback", "Tip-in or putback"),
    ("jumper", "Jump shot"),
    ("fouled", "Fouled: went to the line, or was replaced at the line"),
    ("foul_def", "Committed a defensive foul (not a take foul)"),
    ("take_foul", "Fouled on purpose to stop play (take foul)"),
    ("foul_off", "Offensive foul or charge"),
    ("block", "Blocked a shot"),
    ("steal", "Steal"),
    ("tov_handle", "Lost the ball or traveled"),
    ("tov_pass", "Bad pass or other turnover"),
]
CONTEXT = [   # id, plain label: what happened on the floor while he was out there
    ("scramble", "On the floor for a rebound"),
    ("scramble_close", "On the floor for a rebound of a miss near the basket"),
    ("opp_rim", "Defending while the other team attacked the rim"),
]
SUMMARY = [("any_play", "Any play of his own"), ("no_play", "No play of his own")]
LAST_PLAY_ORDER = ["rebound", "rim", "jumper", "fouled", "foul_def", "foul_off", "block", "steal", "tov_handle", "tov_pass"]
LAST_PLAY_LABEL = {"rebound": "Rebound", "rim": "Shot at the rim", "jumper": "Jump shot", "fouled": "Fouled",
                   "foul_def": "Defensive foul", "foul_off": "Offensive foul", "block": "Block", "steal": "Steal",
                   "tov_handle": "Lost the ball", "tov_pass": "Bad pass", "none": "No play in the last 2 minutes"}
HANDLING = r"Lost Ball|Traveling|Step Out of Bounds|Discontinue Dribble|Double Dribble|Backcourt|Palming"
FOUL_NOT_PERSONAL = r"Technical|Defense 3 Second|Delay|Flopping"


def group_of(region: str | None, kind: str | None, reason: str | None = None) -> str:
    # a few body parts the report parser files elsewhere
    if reason and re.search(r"tibial? plateau", reason, re.I):
        return "knee"
    if region in {"other", "back"} and reason and re.search(r"radius|ulna|\bhand\b", reason, re.I):
        return "hand"
    if region == "other" and reason and re.search(r"ac joint|acromioclavicular", reason, re.I):
        return "shoulder"
    if region == "other" and reason and re.search(r"mtp|toe|cuboid|retrocalcaneal|heel", reason, re.I):
        return "foot"
    if region in {"ankle", "knee", "foot", "shoulder"}:
        return region
    if causes.group_of(region, kind) == "muscle":
        return "muscle"
    if region in {"back", "hip", "trunk"}:
        return "back_hip"
    if region in {"hand", "arm"}:
        return "hand"
    if region in {"concussion", "head_neck"} or kind == "concussion":
        return "head"
    return "other"


def in_group(group: str, frame: pd.DataFrame) -> pd.Series:
    if group == "any":
        return pd.Series(True, index=frame.index)
    if group == "ankle_sprain":
        return (frame["region"] == "ankle") & (frame["injury_type"] == "ligament")
    if group == "contusion":
        return frame["injury_type"] == "impact"
    return frame["coarse"] == group


# --- play-by-play -------------------------------------------------------------------------------------

def season_plays(season: int) -> pd.DataFrame:
    cols = ["game_id", "order_index", "period", "seconds_remaining", "score_home", "score_away", "action_type",
            "sub_type", "description", "team_id", "team_tricode", "is_field_goal", "shot_distance", "shot_value",
            "person_id", "player_name", "player_name_i"] + ON_COURT
    p = pd.read_parquet(sources.season_path("pbp", season), columns=cols)
    p = p[p["game_id"].astype(str).str[:3].isin(GAME_PREFIXES)].sort_values(["game_id", "order_index"]).reset_index(drop=True)
    return prepare(p)


def prepare(p: pd.DataFrame) -> pd.DataFrame:
    """Elapsed game time, numeric ids and scores carried forward, for plays already sorted within each game."""
    period = p["period"].to_numpy(dtype=int)
    t, period_end = _elapsed(period, p["seconds_remaining"].fillna(0).to_numpy(dtype=float))
    p["t"] = pd.Series(t).groupby([p["game_id"], p["period"]]).cummax().to_numpy()   # clock never runs backwards
    p["period_start"] = np.where(period <= 4, (period - 1) * 720, 2880 + (period - 5) * 300)
    p["period_end"] = period_end
    p["person_id"] = pd.to_numeric(p["person_id"], errors="coerce").fillna(0).astype("int64")
    p["team_id"] = pd.to_numeric(p["team_id"], errors="coerce").fillna(0).astype("int64")
    for c in ("score_home", "score_away"):
        p[c] = pd.to_numeric(p[c].replace("", np.nan), errors="coerce")
        p[c] = p.groupby("game_id")[c].ffill().fillna(0)
    for c in ("action_type", "sub_type", "description", "player_name", "player_name_i", "team_tricode"):
        if c not in p:
            p[c] = ""
        p[c] = p[c].fillna("").astype(str)
    if "shot_value" not in p:
        p["shot_value"] = np.nan
    for c in ON_COURT:
        p[c] = pd.to_numeric(p[c], errors="coerce")
    p["row"] = np.arange(len(p))
    return p


def player_plays(p: pd.DataFrame) -> pd.DataFrame:
    """One row per play a player was credited with: game_id, player_id, period, t, order_index, play."""
    a, sub, desc = p["action_type"], p["sub_type"], p["description"]
    person = (p["person_id"] > 0) & (p["person_id"] < FIRST_TEAM_ID)
    missed = (a == "Missed Shot") | ((a == "Free Throw") & desc.str.startswith("MISS"))
    miss_team = p["team_id"].where(missed).groupby(p["game_id"]).ffill()
    rebound = (a == "Rebound") & person
    fga = (p["is_field_goal"] == 1) & person
    rim = fga & is_rim(sub, p["shot_distance"], p["shot_value"], desc)
    foul = (a == "Foul") & person & ~sub.str.contains(FOUL_NOT_PERSONAL, case=False)
    take = foul & sub.str.contains("Take", case=False)
    foul_off = foul & sub.str.contains("Offensive", case=False)
    turnover = (a == "Turnover") & person
    masks = {
        "rebound": rebound,
        "off_rebound": rebound & (p["team_id"] == miss_team),
        "def_rebound": rebound & (p["team_id"] != miss_team),
        "rim": rim,
        "drive": fga & (sub.str.contains("Driving|Cutting", case=False) | (rim & sub.str.contains("Running", case=False))),
        "dunk": fga & sub.str.contains("Dunk", case=False),
        "putback": fga & sub.str.contains("Putback|Tip", case=False),
        "jumper": fga & ~rim,
        "fouled": (a == "Free Throw") & person & sub.str.contains(r"1 of [123]") & ~sub.str.contains("Technical", case=False),
        "foul_def": foul & ~foul_off & ~take,
        "take_foul": take,
        "foul_off": foul_off,
        "block": (a == "") & person & desc.str.contains("BLOCK"),
        "steal": (a == "") & person & desc.str.contains("STEAL"),
        "tov_handle": turnover & sub.str.contains(HANDLING, case=False),
        "tov_pass": turnover & ~sub.str.contains(HANDLING, case=False),
    }
    cols = ["game_id", "person_id", "period", "t", "order_index"]
    frames = [p.loc[m, cols].assign(play=k) for k, m in masks.items()]
    return pd.concat(frames, ignore_index=True).rename(columns={"person_id": "player_id"})


def context_plays(p: pd.DataFrame) -> pd.DataFrame:
    """Plays a player was on the floor for: a player's rebound (of any miss, or of a two-point miss within 10
    feet), or the other team's shot at the rim. Lineup columns are fine here: they decide who was out there."""
    a, sub, desc = p["action_type"], p["sub_type"], p["description"]
    person = (p["person_id"] > 0) & (p["person_id"] < FIRST_TEAM_ID)
    rebound = (a == "Rebound") & person
    # the miss each rebound belongs to: the latest miss before it (a block row can sit in between)
    missed = (a == "Missed Shot") | ((a == "Free Throw") & desc.str.startswith("MISS"))
    close = ((a == "Missed Shot") & (p["shot_distance"] <= 10) & ~is_three(p)).astype(float)
    after_close = close.where(missed).groupby(p["game_id"]).ffill().fillna(0).astype(bool)
    rim = (p["is_field_goal"] == 1) & is_rim(sub, p["shot_distance"], p["shot_value"], desc)
    offense = [f"off_player_{i}" for i in range(1, 6)]
    defense = [f"def_player_{i}" for i in range(1, 6)]
    rim = rim & p[offense].eq(p["person_id"], axis=0).any(axis=1)   # only where the lineup columns agree with the shooter
    frames = []
    for name, mask, cols in (("scramble", rebound, offense + defense), ("scramble_close", rebound & after_close, offense + defense),
                             ("opp_rim", rim, defense)):
        part = p.loc[mask, ["game_id", "period", "t", "order_index"] + cols].melt(
            id_vars=["game_id", "period", "t", "order_index"], value_vars=cols, value_name="player_id")
        part = part[part["player_id"] > 0].astype({"player_id": "int64"})
        frames.append(part[["game_id", "player_id", "period", "t", "order_index"]].assign(play=name))
    return pd.concat(frames, ignore_index=True)


def is_three(p: pd.DataFrame) -> pd.Series:
    return (pd.to_numeric(p["shot_value"], errors="coerce") == 3) | p["description"].str.contains("3PT")


# --- who was on the floor ----------------------------------------------------------------------------------

def _norm(name: str) -> str:
    """A name as the substitution log and the box score can both write it: no accents, lower case."""
    name = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode()
    return " ".join(name.lower().split())


def _names(g: pd.DataFrame, roster: pd.DataFrame | None = None) -> dict:
    """(team_id, name) -> person_id, from substitution rows, the player's own plays and the box-score roster."""
    names = {}
    subs = g[g["action_type"] == "Substitution"]
    for team, pid, desc in zip(subs["team_id"], subs["person_id"], subs["description"]):
        m = SUB_TEXT.match(desc)
        if m and pid:
            names[(team, _norm(m.group(2)))] = pid
    own = g[(g["person_id"] > 0) & (g["person_id"] < FIRST_TEAM_ID) & (g["team_id"] > 0)]
    for col in ("player_name", "player_name_i"):
        for team, pid, name in zip(own["team_id"], own["person_id"], own[col]):
            if name:
                names.setdefault((team, _norm(name)), pid)
    if roster is not None:
        for team, pid, first, last in zip(roster["team_id"], roster["player_id"], roster["first_name"], roster["last_name"]):
            first, last = _norm(first), _norm(last)
            if not last:
                continue
            bare = SUFFIX.sub("", last)
            for form in {last, bare, f"{first[:1]}. {last}", f"{first[:1]}. {bare}", f"{first[:2]}. {last}",
                         f"{first[:3]}. {last}", f"{first} {last}"}:
                names.setdefault((team, form), pid)
    return names


def presence(p: pd.DataFrame, roster: pd.DataFrame | None = None, log=None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(exits, stretches): every time a player left the floor, and each stretch he spent on it, per game.
    ``roster`` (game_id, team_id, player_id, first_name, last_name) adds box-score name forms for matching."""
    exits, stretches = [], []
    fallback = unresolved = 0
    # a player's own plays (officials appear on replay and other rows; a technical can come from the bench)
    own = p[(p["person_id"] > 0) & (p["person_id"] < FIRST_TEAM_ID) & (p["team_id"] > 0) & p["action_type"].isin(PLAYER_ACTIONS)
            & ~p["sub_type"].str.contains("Technical", case=False)]
    own_t = {k: np.sort(v.to_numpy()) for k, v in own.groupby(["game_id", "person_id"])["t"]}
    players_in = {}
    for g_, pid_ in own_t:
        players_in.setdefault(g_, set()).add(pid_)
    rosters = {k: v for k, v in roster.groupby("game_id")} if roster is not None else {}
    for gid, g in p.groupby("game_id", sort=False):
        names = _names(g, rosters.get(gid))
        team_of = {}
        for pid, team in zip(g["person_id"], g["team_id"]):
            if 0 < pid < FIRST_TEAM_ID and team > 0:
                team_of.setdefault(pid, team)
        if gid in rosters:
            for pid, team in zip(rosters[gid]["player_id"], rosters[gid]["team_id"]):
                team_of.setdefault(pid, team)
        on, since, by_sub = set(), {}, set()
        game_exits, game_stretches = [], []
        prev_end, prev_period = None, None
        full = g[g[ON_COURT].notna().all(axis=1)]
        first_full = full.groupby("period").head(1).set_index("period")
        for period, gp in g.groupby("period", sort=True):
            start, end = gp["period_start"].iloc[0], gp["period_end"].iloc[0]
            starters = set(first_full.loc[period, ON_COURT].astype("int64")) if period in first_full.index else set(on)
            for pid in on:   # the period that just ended: close his stretch; leaving at the break if he does not start
                game_stretches.append((gid, pid, prev_period, since[pid], prev_end))
                if pid not in starters:
                    game_exits.append(dict(game_id=gid, player_id=pid, period=prev_period, t=prev_end, how="break",
                                           row=-1, order=-1, team=team_of.get(pid, 0), in_player=-1))
            on, by_sub = set(starters), set()
            since = {pid: start for pid in on}
            claimed = set()
            for s in gp[gp["action_type"] == "Substitution"].itertuples(index=False):
                out, team, t = s.person_id, s.team_id, s.t
                m = SUB_TEXT.match(s.description)
                name_in = _norm(m.group(1)) if m else ""
                pin = names.get((team, name_in))
                if pin is None and name_in:
                    fallback += 1
                    left_now = {e["player_id"] for e in game_exits if e["t"] == t} | {out}   # gone at this stoppage
                    pin = _from_lineups(gp, s.order_index, left_now, on, team, team_of, claimed)
                    unresolved += pin is None
                if pin is not None:
                    claimed.add(pin)
                record = True
                if out in on:
                    on.discard(out)
                    if since.get(out) == t and (out in by_sub or t == start):
                        since.pop(out)       # in and straight back out at one stoppage: he never played
                        record = False
                    else:
                        game_stretches.append((gid, out, period, since.pop(out, start), t))
                if record:   # (a player the log takes out whom we did not have on came on unseen: still an exit)
                    game_exits.append(dict(game_id=gid, player_id=out, period=period, t=t, how="substitution", row=s.row,
                                           order=s.order_index, team=team, in_player=-1 if pin is None else int(pin)))
                if pin is not None and pin not in on:
                    same = [e for e in game_exits if e["player_id"] == pin and e["t"] == t and e["how"] == "substitution"]
                    if same:   # out and straight back in at one stoppage: he never left
                        game_exits.remove(same[-1])
                        last = [x for x in game_stretches if x[1] == pin and x[4] == t]
                        if last:
                            game_stretches.remove(last[-1])
                        since[pin] = last[-1][3] if last else t
                    else:
                        since[pin] = t
                        by_sub.add(pin)
                    on.add(pin)
            # back on without a matched substitution: he made a play in this period after his last exit
            for pid in players_in.get(gid, set()) - on:
                plays = own_t[(gid, pid)]
                plays = plays[(plays >= start) & (plays <= end)]
                if not len(plays):
                    continue
                left = [e["t"] for e in game_exits if e["player_id"] == pid]
                after = plays[plays > (max(left) if left else -1.0)]
                if len(after):
                    on.add(pid)
                    since[pid] = float(after[0])
            prev_end, prev_period = end, period
        for pid in on:
            game_stretches.append((gid, pid, prev_period, since.get(pid, prev_end), prev_end))
        exits += game_exits
        stretches += game_stretches
    if log:
        log(f"    {fallback} substitutions matched from the lineup columns, {unresolved} incoming players not identified")
    e = pd.DataFrame(exits, columns=["game_id", "player_id", "period", "t", "how", "row", "order", "team", "in_player"])
    st = pd.DataFrame(stretches, columns=["game_id", "player_id", "period", "start_t", "end_t"])
    # did he come back? a later stretch, a later exit, or a later play of his
    later_start = st.groupby(["game_id", "player_id"])["start_t"].max()
    last_out = e.groupby(["game_id", "player_id"])["t"].max()
    key = pd.MultiIndex.from_frame(e[["game_id", "player_id"]])
    came_back = later_start.reindex(key).to_numpy() > e["t"].to_numpy()
    came_back |= last_out.reindex(key).to_numpy() > e["t"].to_numpy()
    plays_after = np.array([(own_t.get((g, pid)) is not None) and (own_t[(g, pid)] > t).any()
                            for g, pid, t in zip(e["game_id"], e["player_id"], e["t"])])
    e["returned"] = came_back | plays_after
    return e, st


def _from_lineups(gp: pd.DataFrame, order: int, left: set, on: set, team: int, team_of: dict, claimed: set) -> int | None:
    """The incoming player of a substitution whose name did not match: wait for the first full lineup that no
    longer lists the players going out at this stoppage (the lineup columns lag), then take that team's new face."""
    after = gp[gp["order_index"] > order].head(80)
    for row in after[ON_COURT].itertuples(index=False):
        if any(pd.isna(v) for v in row):
            continue
        ids = [int(v) for v in row]
        if any(pid in left for pid in ids):
            continue
        for pid in ids:
            if pid not in on and pid not in left and pid not in claimed and team_of.get(pid) == team:
                return pid
        return None
    return None


def exits(p: pd.DataFrame, roster: pd.DataFrame | None = None, log=None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Every exit with what it needs to be judged: the score, his fouls, ejection, the stoppage it came at, and
    whether he was hurt on a foul he could not shoot (his replacement shot the free throws)."""
    e, st = presence(p, roster, log=log)
    e["game_end"] = p.groupby("game_id")["period_end"].max().reindex(e["game_id"]).to_numpy()
    e["margin"] = margin_at(p, e)
    fouls = p[(p["action_type"] == "Foul") & ~p["sub_type"].str.contains(FOUL_NOT_PERSONAL, case=False)]
    e["fouls"] = _count_up_to(fouls, e)
    ejected = set(zip(p.loc[p["action_type"] == "Ejection", "game_id"], p.loc[p["action_type"] == "Ejection", "person_id"]))
    e["ejected"] = [(g, pl) in ejected for g, pl in zip(e["game_id"], e["player_id"])]
    e["stoppage"] = stoppage(p, e)
    e["replaced_shooter"] = replaced_shooter(p, e)
    # an opponent's flagrant foul at that second: kept for reference, not counted as "fouled" (often a bystander)
    flag = p[(p["action_type"] == "Foul") & p["sub_type"].str.contains("Flagrant", case=False)]
    flag_at = {(g, t): team for g, t, team in zip(flag["game_id"], flag["t"], flag["team_id"])}
    e["opp_flagrant"] = [flag_at.get((g, t), team) != team for g, t, team in zip(e["game_id"], e["t"], e["team"])]
    return e, st


SHOOTER_PICKED = r"Take|Away|Technical|Flagrant|Clear Path|Transition"   # fouls where someone else may be picked to shoot


def replaced_shooter(p: pd.DataFrame, e: pd.DataFrame) -> np.ndarray:
    """He went out at a foul on him that he could not shoot: a foul at that second logged before his substitution
    (not one where a team picks the shooter), then the player who replaced him shoots the first free throw, and
    that player is not straight back out."""
    action, person, game, t = p["action_type"].to_numpy(), p["person_id"].to_numpy(), p["game_id"].to_numpy(), p["t"].to_numpy()
    picked = p["sub_type"].str.contains(SHOOTER_PICKED, case=False).to_numpy()
    first_ft = (p["action_type"] == "Free Throw").to_numpy() & p["sub_type"].str.contains(r"1 of [123]").to_numpy() & ~picked
    out = np.zeros(len(e), dtype=bool)
    for k, (row, how, pin) in enumerate(zip(e["row"], e["how"], e["in_player"])):
        if how != "substitution" or pin is None or pin <= 0:
            continue
        i = int(row)
        here = t[i]
        j, foul = i - 1, False
        while j >= 0 and game[j] == game[i] and t[j] == here:
            if action[j] == "Foul":
                foul = not picked[j]
                break
            j -= 1
        if not foul:
            continue
        j = i + 1
        while j < len(p) and game[j] == game[i] and t[j] == here:
            if action[j] == "Substitution" and person[j] == pin:
                break                      # in and straight back out
            if first_ft[j] and person[j] == pin:
                out[k] = True
                break
            j += 1
    return out


def stoppage(p: pd.DataFrame, e: pd.DataFrame) -> np.ndarray:
    """What stopped play when he went out: a timeout, foul or violation logged at that second after the
    substitution rows, or else the last play before them (technicals and replays skipped). A team rebound after a
    missed free throw belongs to the free throws; a live-ball play, or a play at an earlier second, means the
    stoppage itself was not logged."""
    action, sub = p["action_type"].to_numpy(), p["sub_type"].to_numpy()
    team, person, game, t = p["team_id"].to_numpy(), p["person_id"].to_numpy(), p["game_id"].to_numpy(), p["t"].to_numpy()
    desc = p["description"].to_numpy()
    technical = p["sub_type"].str.contains("Technical", case=False).to_numpy()

    def timeout(i, own_team):
        caller = person[i] if person[i] >= FIRST_TEAM_ID else team[i]   # a timeout row names the calling team in person_id
        return "own timeout" if caller == own_team else "opponent timeout"

    out = []
    for row, how, own_team in zip(e["row"], e["how"], e["team"]):
        if how == "break":
            out.append("break")
            continue
        i = int(row)
        here = t[i]
        if action[i] == "Substitution":
            j, label = i + 1, None
            while j < len(p) and game[j] == game[i] and t[j] == here:
                if action[j] == "Timeout":
                    label = timeout(j, own_team)
                elif action[j] == "Foul" and not technical[j]:
                    label = "foul"
                elif action[j] == "Violation":
                    label = "turnover or violation"
                if label or action[j] not in ("Substitution", "Instant Replay"):
                    break
                j += 1
            if label:
                out.append(label)
                continue
        j = i
        while j >= 0 and game[j] == game[i] and (action[j] in ("Substitution", "Instant Replay") or technical[j]):
            j -= 1
        if j < 0 or game[j] != game[i] or t[j] < here:
            out.append("no logged stoppage")
            continue
        a = action[j]
        if a == "Timeout":
            out.append(timeout(j, own_team))
        elif a == "Foul":
            out.append("foul")
        elif a == "Free Throw":
            out.append("free throws")
        elif a == "Rebound" and person[j] >= FIRST_TEAM_ID:
            k = j - 1
            while k >= 0 and game[k] == game[j] and action[k] in ("Substitution", "Instant Replay"):
                k -= 1
            after_ft = k >= 0 and action[k] == "Free Throw" and str(desc[k]).startswith("MISS")
            out.append("free throws" if after_ft or sub[j] == "Normal Rebound" else "team rebound")
        elif a in ("Turnover", "Violation"):
            out.append("turnover or violation")
        else:
            out.append("no logged stoppage")
    return np.array(out, dtype=object)


DEAD_BALL = {"Foul", "Timeout", "Substitution", "Violation", "Jump Ball", "Instant Replay", "Ejection", "Free Throw"}


def null_exits(p: pd.DataFrame, moments: pd.DataFrame) -> pd.DataFrame:
    """For each random moment on the floor, the first dead ball at or after it in that period (or the period's end):
    when a player hurt at that moment would get off the floor. A fouled player shoots his own free throws first,
    and the window (t - W, t] includes them because they come at the same second."""
    a = p["action_type"]
    steal_next = (p["description"].shift(-1).fillna("").str.contains("STEAL")) & (p["game_id"].shift(-1) == p["game_id"])
    dead = a.isin(DEAD_BALL) | ((a == "Turnover") & ~steal_next) | ((a == "Rebound") & (p["person_id"] >= FIRST_TEAM_ID))
    d = p.loc[dead & ~p["sub_type"].str.contains("Technical", case=False), ["game_id", "period", "t", "row"]]
    times = {k: (v["t"].to_numpy(), v["row"].to_numpy()) for k, v in d.groupby(["game_id", "period"])}
    period_end = p.groupby(["game_id", "period"])["period_end"].first().to_dict()
    rows = []
    for gid, pid, period, t, season, team in zip(moments["game_id"], moments["player_id"], moments["period"], moments["t"],
                                                 moments["season"], moments["team"]):
        tt, rr = times.get((gid, period), (np.array([]), np.array([])))
        k = np.searchsorted(tt, t, side="left")
        if k < len(tt):
            rows.append((gid, pid, period, float(tt[k]), int(rr[k]), season, team, "dead ball"))
        else:
            rows.append((gid, pid, period, float(period_end.get((gid, period), t)), -1, season, team, "break"))
    n = pd.DataFrame(rows, columns=["game_id", "player_id", "period", "t", "row", "season", "team", "how"])
    n["stoppage"] = stoppage(p, n.assign(how=np.where(n["how"] == "break", "break", "substitution")))
    return n


def margin_at(p: pd.DataFrame, moments: pd.DataFrame) -> np.ndarray:
    """Absolute score margin at the last play at or before each moment (game_id, t)."""
    code = pd.factorize(p["game_id"])[0].astype(np.int64)
    keys = code * SCALE + np.round(p["t"].to_numpy() * TICKS).astype(np.int64)   # sorted: plays are in game and time order
    lookup = pd.Series(np.arange(code.max() + 1), index=pd.unique(p["game_id"]))
    mcode = lookup.reindex(moments["game_id"]).to_numpy().astype(np.int64)
    k = np.searchsorted(keys, mcode * SCALE + np.round(moments["t"].to_numpy(dtype=float) * TICKS).astype(np.int64), side="right") - 1
    k = np.clip(k, 0, len(p) - 1)
    return np.abs(p["score_home"].to_numpy()[k] - p["score_away"].to_numpy()[k])


def _count_up_to(events: pd.DataFrame, moments: pd.DataFrame) -> np.ndarray:
    """How many of a player's events in the game came at or before each moment."""
    times = {k: np.sort(v.to_numpy()) for k, v in events.groupby(["game_id", "person_id"])["t"]}
    return np.array([np.searchsorted(times[(g, pid)], t, side="right") if (g, pid) in times else 0
                     for g, pid, t in zip(moments["game_id"], moments["player_id"], moments["t"])])


class Timeline:
    """One kind of play for every (game, player, period), packed into sorted integers (tenths of a second) so a
    window before any moment is two binary searches. Ties at one second are ordered by the play's position in
    the log."""

    def __init__(self, events: pd.DataFrame):
        cols = ["game_id", "player_id", "period"]
        pairs = events[cols].drop_duplicates()
        self.codes = pd.Series(np.arange(len(pairs), dtype=np.int64), index=pd.MultiIndex.from_frame(pairs))
        code = self.codes.reindex(pd.MultiIndex.from_frame(events[cols])).to_numpy().astype(np.int64)
        keys = code * SCALE + np.round(events["t"].to_numpy(dtype=float) * TICKS).astype(np.int64)
        order = events["order_index"].to_numpy(dtype=np.int64)
        idx = np.lexsort((order, keys))
        self.keys, self.order = keys[idx], order[idx]

    def _base(self, moments: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        cols = ["game_id", "player_id", "period"]
        if not len(self.codes):
            return np.zeros(len(moments), dtype=np.int64), np.zeros(len(moments), dtype=bool)
        code = self.codes.reindex(pd.MultiIndex.from_frame(moments[cols])).to_numpy()
        known = np.isfinite(code)
        return np.where(known, code, 0).astype(np.int64) * SCALE, known

    def count(self, moments: pd.DataFrame, width: float) -> np.ndarray:
        """Plays in (t - width, t] inside the moment's period."""
        b, known = self._base(moments)
        tt = np.floor(moments["t"].to_numpy(dtype=float) * TICKS + 1e-6).astype(np.int64)   # (t - W, t] for any t
        hi = np.searchsorted(self.keys, b + tt, side="right")
        lo = np.searchsorted(self.keys, b + tt - int(round(width * TICKS)), side="right")
        return np.where(known, hi - lo, 0)

    def last(self, moments: pd.DataFrame, width: float) -> tuple[np.ndarray, np.ndarray]:
        """(time in ticks, log position) of the most recent play in (t - width, t], or (-1, -1)."""
        b, known = self._base(moments)
        tt = np.floor(moments["t"].to_numpy(dtype=float) * TICKS + 1e-6).astype(np.int64)   # (t - W, t] for any t
        if not len(self.keys):
            return np.full(len(tt), -1), np.full(len(tt), -1)
        k = np.searchsorted(self.keys, b + tt, side="right") - 1
        kk = np.clip(k, 0, len(self.keys) - 1)
        prev = self.keys[kk]
        ok = known & (k >= 0) & (prev >= b) & (prev > b + tt - int(round(width * TICKS)))
        return np.where(ok, prev - b, -1), np.where(ok, self.order[kk], -1)


def flag_moments(moments: pd.DataFrame, plays: pd.DataFrame) -> pd.DataFrame:
    """Add, for each kind of play and window, whether it came in that window before the moment, and his last play."""
    lines = {name: Timeline(plays[plays["play"] == name]) for name in [k for k, _ in PLAYS] + [k for k, _ in CONTEXT]}
    cols = {}
    hurt_at_line = (moments["replaced_shooter"].fillna(False).to_numpy(dtype=bool) if "replaced_shooter" in moments
                    else np.zeros(len(moments), dtype=bool))
    for name, line in lines.items():
        for w in WINDOWS:
            hit = line.count(moments, w) > 0
            cols[f"{name}_{w}"] = hit | hurt_at_line if name == "fouled" else hit
    best_t = np.full(len(moments), -1, dtype=np.int64)
    best_o = np.full(len(moments), -1, dtype=np.int64)
    best = np.array(["none"] * len(moments), dtype=object)
    for name in LAST_PLAY_ORDER:
        when, order = lines[name].last(moments, LAST_PLAY_WINDOW)
        newer = (when > best_t) | ((when == best_t) & (order > best_o) & (when >= 0))
        best_t, best_o, best = np.where(newer, when, best_t), np.where(newer, order, best_o), np.where(newer, name, best)
    cols["last_play"] = best
    return pd.concat([moments.reset_index(drop=True), pd.DataFrame(cols)], axis=1)


# --- injuries, exits and comparisons ---------------------------------------------------------------------

def usual_minutes(pg: pd.DataFrame) -> pd.DataFrame:
    played = pg[(pg["status"] == "played") & (pg["minutes"] > 0)].sort_values(["player_id", "game_date"]).copy()
    played["usual"] = played.groupby("player_id")["minutes"].transform(lambda s: s.shift(1).rolling(10, min_periods=3).mean())
    return played[["player_id", "game_id", "season", "minutes", "usual"]]


def next_games(pg: pd.DataFrame) -> pd.DataFrame:
    """For each player-game: the team's next game and whether he played in it."""
    games = pg[["team", "game_id", "game_date"]].drop_duplicates().sort_values(["team", "game_date", "game_id"])
    games["next_game"] = games.groupby("team")["game_id"].shift(-1)
    out = pg[["player_id", "team", "game_id"]].merge(games[["team", "game_id", "next_game"]], on=["team", "game_id"], how="left")
    played = set(zip(pg.loc[(pg["status"] == "played") & (pg["minutes"] > 0), "player_id"],
                     pg.loc[(pg["status"] == "played") & (pg["minutes"] > 0), "game_id"]))
    out["played_next"] = [(pid, g) in played for pid, g in zip(out["player_id"], out["next_game"])]
    return out[["player_id", "game_id", "next_game", "played_next"]]


def injury_games(pg: pd.DataFrame, onsets: pd.DataFrame) -> pd.DataFrame:
    """Each new injury with the team game before its first missed game and the player's minutes in it."""
    o = onsets[onsets["new_injury"] & onsets["season"].between(*SEASONS)].copy()
    text = o["reason"].fillna("").str.replace(r"^Injury/Illness\s*-\s*", "", regex=True)
    o = o[~text.str.contains(NOT_INJURY)].reset_index(drop=True)
    games = pg[["team", "game_id", "game_date"]].drop_duplicates().sort_values(["team", "game_date", "game_id"])
    games["prev_game"] = games.groupby("team")["game_id"].shift(1)
    o = o.merge(games[["team", "game_id", "prev_game"]].rename(columns={"game_id": "onset_game_id"}),
                on=["team", "onset_game_id"], how="left")
    o = o.merge(usual_minutes(pg).drop(columns="season").rename(columns={"game_id": "prev_game"}),
                on=["player_id", "prev_game"], how="left")
    o["coarse"] = [group_of(r, k, why) for r, k, why in zip(o["region"], o["injury_type"], o["reason"])]
    return o


def early_exit_rules(c: pd.DataFrame, short: float | None = SHORT_GAME) -> pd.Series:
    """His last exit of the game came early, in a competitive game; with ``short``, he also finished under that
    share of his usual minutes."""
    ok = (c["t"].notna() & (c["t"] <= c["game_end"] - MIN_LEFT) & (c["margin"] <= MAX_MARGIN)
          & ~c["ejected"].fillna(False).astype(bool) & (c["fouls"] < 6) & (c["usual"] >= MIN_USUAL))
    if short is not None:
        ok &= c["minutes"] < short * c["usual"]
    return ok


def is_injury_exit(c: pd.DataFrame) -> pd.Series:
    return early_exit_rules(c, SHORT_GAME)


def build(log=print) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """(injuries with whether each was pinned to an injury exit, every moment with its flags, the background
    rate of the injury-exit pattern by what came next)."""
    pg = pd.read_parquet(PROCESSED / "player_games.parquet")
    inj = injury_games(pg, pd.read_parquet(PROCESSED / "onsets.parquet"))
    inj["pinned"], inj["exit_how"] = False, None
    usual = usual_minutes(pg)
    nxt = next_games(pg)
    all_onsets = pd.read_parquet(PROCESSED / "onsets.parquet")
    before_injury = set(zip(inj["player_id"], inj["prev_game"]))   # games right before a new injury
    missed_next = set(zip(all_onsets["player_id"], all_onsets["onset_game_id"]))
    rng = np.random.default_rng(0)
    frames, background = [], []
    for season in range(SEASONS[0], SEASONS[1] + 1):
        p = season_plays(season)
        teams = p.loc[p["team_id"] > 0, ["team_tricode", "team_id"]].drop_duplicates("team_tricode")
        roster = pg[pg["season"] == season][["game_id", "team", "player_id", "first_name", "last_name"]].merge(
            teams.rename(columns={"team_tricode": "team"}), on="team")
        ex, st = exits(p, roster, log=log)
        ex = ex.merge(usual[usual["season"] == season].drop(columns="season"), on=["player_id", "game_id"], how="left")
        ex["season"] = season
        last = ex[~ex["returned"]].sort_values("t").drop_duplicates(["game_id", "player_id"], keep="last")

        # the pattern in every eligible game, by what came next: the background rate
        games_played = usual[(usual["season"] == season) & (usual["usual"] >= MIN_USUAL)]
        bg = games_played.merge(last.drop(columns=["minutes", "usual"]), on=["player_id", "game_id"], how="left")
        bg = bg.merge(nxt, on=["player_id", "game_id"], how="left")
        bg["played_next"] = bg["played_next"].fillna(False).astype(bool)
        bg["pattern"] = early_exit_rules(bg).to_numpy()
        bg["next"] = np.select([[(pid, g) in before_injury for pid, g in zip(bg["player_id"], bg["game_id"])],
                                bg["next_game"].isna(), bg["played_next"]],
                               ["new injury", "season over", "played next game"], "missed next game, other reason")
        background.append(bg[["player_id", "game_id", "next", "pattern"]].assign(season=season))

        # cases: the last exit in the game before a new injury, early in a competitive game (any minutes; the
        # main definition adds the minutes rule, the others are sensitivity checks)
        si = inj[(inj["season"] == season) & inj["prev_game"].notna()]
        c = si[["player_id", "prev_game"]].reset_index().merge(
            last.drop(columns=["minutes", "usual"]).rename(columns={"game_id": "prev_game"}), on=["player_id", "prev_game"], how="left")
        c = c.merge(si[["minutes", "usual"]], left_on="index", right_index=True)
        main = is_injury_exit(c)
        inj.loc[c["index"], "pinned"] = main.to_numpy()
        inj.loc[c["index"], "exit_how"] = c["how"].to_numpy()
        cases = c[early_exit_rules(c, None)].rename(columns={"prev_game": "game_id", "index": "injury"}).assign(role="case")

        # non-injury early exits: the same pattern in games where he played the team's next game
        pseudo = bg[bg["pattern"] & (bg["next"] == "played next game")][["player_id", "game_id"]]
        pseudo = last.merge(pseudo, on=["player_id", "game_id"]).assign(role="pseudo", injury=-1)
        players = set(cases["player_id"]) | set(pseudo["player_id"])

        # comparisons: these players' exits they came back from, in competitive games not followed by a new injury
        fair = (ex["t"] <= ex["game_end"] - MIN_LEFT) & (ex["margin"] <= MAX_MARGIN)
        ctrl = ex[ex["returned"] & fair & ex["player_id"].isin(players)]
        ctrl = ctrl[[(pid, gid) not in before_injury for pid, gid in zip(ctrl["player_id"], ctrl["game_id"])]]
        ctrl = ctrl.assign(role="exit", injury=-1)

        # random moments on the floor in the case players' other games, and when each would have led off the floor
        case_players = set(cases["player_id"])
        sts = st[st["player_id"].isin(case_players) & (st["end_t"] > st["start_t"])]
        sts = sts[[(pid, gid) not in before_injury for pid, gid in zip(sts["player_id"], sts["game_id"])]]
        rand = []
        team_of = dict(zip(zip(ex["game_id"], ex["player_id"]), ex["team"]))
        for (pid, gid), grp in sts.groupby(["player_id", "game_id"]):
            lengths = (grp["end_t"] - grp["start_t"]).to_numpy()
            pick = rng.choice(len(grp), size=RANDOM_PER_GAME, p=lengths / lengths.sum())
            for i, u in zip(pick, rng.random(RANDOM_PER_GAME)):
                rand.append((gid, pid, int(grp["period"].iloc[i]), grp["start_t"].iloc[i] + u * lengths[i], team_of.get((gid, pid), 0)))
        rand = pd.DataFrame(rand, columns=["game_id", "player_id", "period", "t", "team"]).assign(role="random", injury=-1,
                                                                                              season=season, how="random")
        rand["game_end"] = p.groupby("game_id")["period_end"].max().reindex(rand["game_id"]).to_numpy()
        rand["margin"] = margin_at(p, rand)
        rand = rand[(rand["t"] <= rand["game_end"] - MIN_LEFT) & (rand["margin"] <= MAX_MARGIN)]
        null = null_exits(p, rand).assign(role="null", injury=-1)
        null["game_end"] = p.groupby("game_id")["period_end"].max().reindex(null["game_id"]).to_numpy()
        null["margin"] = margin_at(p, null)
        null = null[(null["t"] <= null["game_end"] - MIN_LEFT) & (null["margin"] <= MAX_MARGIN)]

        plays = pd.concat([player_plays(p), context_plays(p)], ignore_index=True)
        keep = ["game_id", "player_id", "season", "period", "t", "how", "role", "injury", "margin", "stoppage", "minutes",
                "usual", "replaced_shooter", "opp_flagrant"]
        parts = [f.reindex(columns=keep) for f in (cases, pseudo, ctrl, rand, null)]
        moments = pd.concat(parts, ignore_index=True)
        moments["season"] = season
        for col in ("replaced_shooter", "opp_flagrant"):
            moments[col] = moments[col].fillna(False).astype(bool)
        moments["stoppage"] = moments["stoppage"].fillna("none")
        frames.append(flag_moments(moments, plays))
        log(f"  {season}: {int(main.sum())} injury exits ({len(cases)} before the minutes rule), {len(pseudo)} early exits "
            f"with no injury, {len(ctrl)} ordinary exits, {len(rand)} random moments, {len(null)} null exits")
    m = pd.concat(frames, ignore_index=True)
    m["ratio"] = m["minutes"] / m["usual"]
    m = m.merge(inj[["region", "injury_type", "coarse", "reason"]], left_on="injury", right_index=True, how="left")
    return inj, m, pd.concat(background, ignore_index=True)


# --- comparisons -------------------------------------------------------------------------------------------

def flag(d: pd.DataFrame, play: str, width: int) -> np.ndarray:
    own = [f"{k}_{width}" for k, _ in PLAYS if k != "take_foul"]
    if play == "any_play":
        return d[own].any(axis=1).to_numpy()
    if play == "no_play":
        return ~d[own].any(axis=1).to_numpy()
    return d[f"{play}_{width}"].to_numpy(dtype=bool)


def main_cases(m: pd.DataFrame, role: str = "case", short: float | None = SHORT_GAME) -> pd.Series:
    sel = m["role"] == role
    if short is not None:
        sel &= m["ratio"] < short
    return sel


def p_value(odds: float, lo: float, hi: float) -> float:
    """Two-sided p from the RBG interval."""
    from math import erf, log, sqrt
    if not all(np.isfinite([odds, lo, hi])) or lo <= 0 or hi <= lo:
        return np.nan
    z = abs(log(odds)) / ((log(hi) - log(lo)) / 3.92)
    return 1 - erf(z / sqrt(2))


def compare(m: pd.DataFrame, group: str, play: str, width: int = WINDOW, against: str = "exit", case_role: str = "case",
            short: float | None = SHORT_GAME, by_stoppage: bool = False) -> dict:
    """Injury exits of one group against comparison moments of one kind (same players and seasons), for one play.
    ``against`` is "exit", "null", "random", or "other injuries" (every other injury exit, strata = season)."""
    cases = m[main_cases(m, case_role, short) & (in_group(group, m) if case_role == "case" else True)]
    if against == "other injuries":
        pool = m[main_cases(m, "case", short) & ~in_group(group, m)]
        d = pd.concat([cases, pool])
        stratum = d["season"].astype(str).to_numpy()
    else:
        strata = set(cases["player_id"].astype(str) + "_" + cases["season"].astype(str))
        pool = m[m["role"] == against]
        pool = pool[(pool["player_id"].astype(str) + "_" + pool["season"].astype(str)).isin(strata)]
        d = pd.concat([cases, pool])
        key = d["player_id"].astype(str) + "_" + d["season"].astype(str)
        stratum = (key + "|" + d["stoppage"].astype(str) if by_stoppage else key).to_numpy()
    x = flag(d, play, width)
    y = np.concatenate([np.ones(len(cases), bool), np.zeros(len(pool), bool)])
    odds, lo, hi = causes.mantel_haenszel(stratum, x, y)
    halves = []
    for part in ((d["season"] <= SPLIT_SEASON).to_numpy(), (d["season"] > SPLIT_SEASON).to_numpy()):
        halves.append(causes.mantel_haenszel(stratum[part], x[part], y[part])[0])
    exposed = int(x[y].sum())
    return dict(group=group, play=play, window=width, against=against, case_role=case_role, short=short,
                by_stoppage=by_stoppage, cases=int(y.sum()), comparisons=int((~y).sum()), exposed=exposed,
                case_share=float(x[y].mean()) if y.any() else np.nan,
                comparison_share=float(x[~y].mean()) if (~y).any() else np.nan,
                odds_ratio=odds, lo=lo, hi=hi, p=p_value(odds, lo, hi), first_half=halves[0], second_half=halves[1],
                same_way=all(np.isfinite(h) and np.isfinite(odds) and ((h > 1) == (odds > 1)) for h in halves))


def benjamini_hochberg(p: list[float]) -> np.ndarray:
    p = np.asarray(p, dtype=float)
    q = np.full(len(p), np.nan)
    ok = np.isfinite(p)
    if not ok.any():
        return q
    pv = p[ok]
    order = np.argsort(pv)
    ranked = pv[order] * len(pv) / np.arange(1, len(pv) + 1)
    ranked = np.minimum.accumulate(ranked[::-1])[::-1]
    out = np.empty(len(pv))
    out[order] = np.minimum(ranked, 1)
    q[ok] = out
    return q


def analyse(log=print, reuse: bool = False) -> dict:
    """The statistics in summary.json. ``reuse`` recomputes them from the saved moments instead of rebuilding those
    from the play-by-play."""
    saved = [OUT / f for f in ("injuries.parquet", "moments.parquet", "background.parquet")]
    if reuse and all(f.exists() for f in saved):
        inj, m, bg = (pd.read_parquet(f) for f in saved)
    else:
        inj, m, bg = build(log=log)
        OUT.mkdir(parents=True, exist_ok=True)
        m.to_parquet(OUT / "moments.parquet", index=False)
        bg.to_parquet(OUT / "background.parquet", index=False)
        inj[["player_id", "onset_date", "onset_game_id", "team", "season", "reason", "region", "injury_type", "coarse",
             "prev_game", "minutes", "usual", "pinned", "exit_how"]].to_parquet(OUT / "injuries.parquet", index=False)
    groups = [ALL] + GROUPS
    plays = [k for k, _ in PLAYS] + [k for k, _ in CONTEXT] + [k for k, _ in SUMMARY]
    labels = dict(PLAYS + CONTEXT + SUMMARY)

    # how often the injury-exit pattern turns up by what came next, and how many pins are beyond chance
    rates = bg.groupby("next")["pattern"].agg(["mean", "sum", "size"]).rename(columns={"mean": "rate", "sum": "games_with_pattern",
                                                                                      "size": "games"})
    chance = float(rates.loc["played next game", "rate"])
    cases_main = m[main_cases(m)]
    exits_ = m[m["role"] == "exit"]
    quarter = lambda d: (np.minimum(d["period"], 5).map({1: "Q1", 2: "Q2", 3: "Q3", 4: "Q4", 5: "OT"})  # noqa: E731
                         .value_counts(normalize=True).reindex(["Q1", "Q2", "Q3", "Q4", "OT"]).fillna(0).round(3).to_dict())
    found = []
    for gid, name in groups:
        member = in_group(gid, inj)
        cases = cases_main[in_group(gid, cases_main)]
        prev_played = member & inj["minutes"].notna()
        rate_injured = float(inj.loc[member & inj["usual"].ge(MIN_USUAL), "pinned"].mean()) if member.any() else np.nan
        last = cases["last_play"].value_counts(normalize=True)
        strata = set(cases["player_id"].astype(str) + "_" + cases["season"].astype(str))
        ctrl = exits_[(exits_["player_id"].astype(str) + "_" + exits_["season"].astype(str)).isin(strata)]
        last_ctrl = ctrl["last_play"].value_counts(normalize=True)
        found.append(dict(group=gid, name=name, injuries=int(member.sum()), played_previous=int(prev_played.sum()),
                          pinned=int(inj.loc[member, "pinned"].sum()), pinned_share=float(inj.loc[member, "pinned"].mean()),
                          beyond_chance=float(max(0.0, 1 - chance / rate_injured)) if rate_injured else np.nan,
                          at_break=float((cases["how"] == "break").mean()) if len(cases) else np.nan,
                          quarters=quarter(cases) if len(cases) else {},
                          last_play={LAST_PLAY_LABEL[k]: [float(v), float(last_ctrl.get(k, 0.0))] for k, v in last.items()}))

    table = [compare(m, g, play) for g, _ in groups for play in plays]
    q = benjamini_hochberg([r["p"] if r["play"] != "no_play" else np.nan for r in table])
    for r, qq in zip(table, q):
        r["q"] = qq
        r["thin"] = r["exposed"] < MIN_EXPOSED
        r["headline"] = bool(np.isfinite(qq) and qq < FDR and r["exposed"] >= MIN_EXPOSED and r["same_way"])
        r["label"] = labels[r["play"]]
    checks = {
        "null": [compare(m, g, play, against="null") for g, _ in groups for play in plays],
        "stoppage": [compare(m, g, play, by_stoppage=True) for g, _ in groups for play in plays],
        "random": [compare(m, g, play, against="random") for g, _ in groups for play in plays],
        "other_injuries": [compare(m, g, play, against="other injuries") for g, _ in GROUPS for play in plays],
        "no_injury_early_exits": [compare(m, "any", play, case_role="pseudo") for play in plays],
        "windows": [compare(m, g, play, width=w) for g, _ in groups for play in plays for w in WINDOWS],
        "case_definitions": [compare(m, g, play, short=s) for g in CHECKED for play in plays for s in SHORT_VARIANTS],
        "substitutions_only": [compare(m[(m["how"] == "substitution") | ~m["role"].isin(["case", "exit"])], g, play)
                               for g in CHECKED for play in plays],
    }
    for rows in checks.values():
        for r in rows:
            r["label"] = labels[r["play"]]
    stoppages = {
        "injury exits": cases_main["stoppage"].value_counts(normalize=True).round(4).to_dict(),
        "ordinary exits": exits_["stoppage"].value_counts(normalize=True).round(4).to_dict(),
        "null exits": m.loc[m["role"] == "null", "stoppage"].value_counts(normalize=True).round(4).to_dict(),
    }
    result = dict(
        groups=found, background=rates.reset_index().to_dict("records"), chance_rate=chance,
        quarters={"injury exits": quarter(cases_main), "ordinary exits": quarter(exits_)},
        stoppages=stoppages, table=table, **checks,
        settings=dict(window=WINDOW, windows=list(WINDOWS), min_left=MIN_LEFT, max_margin=MAX_MARGIN, short_game=SHORT_GAME,
                      min_usual=MIN_USUAL, seasons=list(SEASONS), split=SPLIT_SEASON, random_per_game=RANDOM_PER_GAME,
                      fdr=FDR, min_exposed=MIN_EXPOSED, short_variants=[s for s in SHORT_VARIANTS]))
    (OUT / "summary.json").write_text(json.dumps(result, indent=1, default=float), encoding="utf-8")
    return result


def _row(result: dict, key: str, group: str, play: str, **match) -> dict | None:
    for r in result[key]:
        if r["group"] == group and r["play"] == play and all(r.get(k) == v for k, v in match.items()):
            return r
    return None


def report(result: dict, log=print) -> None:
    bg = {r["next"]: r for r in result["background"]}
    log("How often a player leaves a competitive game early for good, under 60% of his usual minutes:")
    for k in ("new injury", "played next game", "missed next game, other reason", "season over"):
        if k in bg:
            log(f"  next game {k:32s} {bg[k]['rate']:6.1%} of {bg[k]['games']:,} games")
    log("\nInjuries pinned to an injury exit (beyond chance = share not explained by the rate in games followed by a normal game):")
    for g in result["groups"]:
        log(f"  {g['name']:60s} {g['pinned']:4d} of {g['injuries']:5d} ({g['pinned_share']:.0%}), beyond chance {g['beyond_chance']:.0%}")
    log(f"\nQuarter of the exit: injury exits {result['quarters']['injury exits']}, ordinary exits {result['quarters']['ordinary exits']}")
    log(f"Stoppage at the exit: injury exits {result['stoppages']['injury exits']}")
    log(f"                      ordinary exits {result['stoppages']['ordinary exits']}")
    log(f"\nIn the {WINDOW} seconds before leaving, injury exits vs the same players' ordinary exits "
        f"(OR, 95% CI, BH q); then the same within stoppage type, against null exits, and against other injuries:")
    for gid, name in [ALL] + GROUPS:
        rows = [r for r in result["table"] if r["group"] == gid]
        if not rows or rows[0]["cases"] < 40:
            continue
        log(f"  {name} ({rows[0]['cases']} injury exits)")
        for r in rows:
            if r["play"] == "no_play":
                continue
            s = _row(result, "stoppage", gid, r["play"])
            n = _row(result, "null", gid, r["play"])
            o = _row(result, "other_injuries", gid, r["play"]) if gid != "any" else _row(result, "no_injury_early_exits", "any", r["play"])
            tag = "  <- finding" if r["headline"] else ("  (too few)" if r["thin"] else "")
            other = f"{'pseudo' if gid == 'any' else 'vs other'} {o['odds_ratio']:5.2f}" if o else ""
            log(f"    {r['label']:58s} {r['case_share']:6.1%} vs {r['comparison_share']:6.1%}  OR {r['odds_ratio']:5.2f} "
                f"({r['lo']:.2f}-{r['hi']:.2f}) q {r['q']:.3f} | stop {s['odds_ratio']:5.2f} | null {n['odds_ratio']:5.2f} "
                f"| {other}{tag}")


def export(log=print, reuse: bool = False) -> dict:
    result = analyse(log=log, reuse=reuse)
    report(result, log=log)
    return {"injuries_pinned": result["groups"][0]["pinned"], "injuries": result["groups"][0]["injuries"],
            "findings": [f"{r['group']}:{r['play']}" for r in result["table"] if r["headline"]]}
