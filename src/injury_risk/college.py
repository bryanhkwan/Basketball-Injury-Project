"""The play-by-play injury-moment test for Division I men's basketball, run to the plan fixed in advance
(docs/ncaa_moments_plan.md).

The NBA version (moments.py) has official injury reports; college has none, so injuries come from saved
copies of Covers' injury page (covers.py) matched to missed-game runs in the NCAA's box scores: a run is a
new injury of a body part when a Covers listing for that player with a named body part was saved during the
run or carries a note dated from 3 days before the game before the run to 14 days after its first missed
game. Everything after that follows the NBA test: the last exit of the game before the run, if it came early
in a competitive game the player finished well under his usual minutes, is an injury exit; the plays he was
part of in the 30 seconds before it are compared with those before his ordinary exits that season.

The NCAA's own play-by-play (sportsdataverse ncaa_mbb_pbp) logs substitutions as "Enters Game" / "Leaves
Game" with player ids, the fouled player as "Draw Foul", shot descriptors (driving layup, tip-in, floater,
dunk) and both teams' five players on the floor. Who is on the floor comes from the first lineup of the game
and the substitution log, checked against each period's first lineup; minutes rebuilt this way are compared
with the box score. A player who does not start the second half leaves at halftime.
"""
from __future__ import annotations

import json
import re
import unicodedata

import numpy as np
import pandas as pd

from . import causes, covers, moments, sources
from .moments import (FDR, LAST_PLAY_ORDER, MAX_MARGIN, MIN_EXPOSED, MIN_LEFT, MIN_USUAL, RANDOM_PER_GAME, SHORT_GAME,
                      SHORT_VARIANTS, WINDOW, WINDOWS, Timeline, benjamini_hochberg, flag, flag_moments, p_value)
from .paths import OUTPUTS

OUT = OUTPUTS / "college_moments"
SEASONS = sources.COLLEGE_SEASONS
SPLIT_SEASON = causes.SPLIT_SEASON
FOUL_OUT = 5
GOOD_MINUTES, GOOD_GAME = 2.0, 0.9   # a game is kept when 90% of its player-games' rebuilt minutes are within 2 of the box
LABEL_BEFORE = 3       # days before the game before a run that a listing's note may be dated...
LABEL_AFTER = 14       # ...and days after its first missed game
HOME = [f"home_{i}_player_id" for i in range(1, 6)]
AWAY = [f"away_{i}_player_id" for i in range(1, 6)]
LINEUP = HOME + AWAY
SHOTS = {"Layup", "Dunk", "Hook", "Two Point Jumper", "Three Point Jumper"}
DEAD_BALL = {"Commits Foul", "Draw Foul", "Timeout", "Enters Game", "Leaves Game", "Deadball Rebound", "Free Throw",
             "Jumpball (held ball)", "Jumpball (lodged ball)", "Jumpball (out of bounds)"}
HANDLING = {"lostball", "travel", "dribbling"}

GROUPS = [   # id, plain name (the plan's groups)
    ("ankle", "Ankle"),
    ("ankle_sprain", "Ankle sprain"),
    ("knee", "Knee"),
    ("foot", "Foot and toe"),
    ("muscle", "Pulled muscles (hamstring, calf, groin, Achilles, thigh)"),
    ("back_hip", "Back and hip"),
    ("hand", "Hand, wrist, finger and arm"),
    ("head", "Head, face and concussions"),
    ("shoulder", "Shoulder"),
    ("other", "Everything else"),
]
ALL = ("any", "Any new injury")
PRIMARY = [("H1", "ankle", "fouled"), ("H2", "any", "steal"), ("H3", "hand", "opp_rim"), ("H4", "muscle", "drive")]
SECONDARY = [("H5", "ankle", "rebound")]

# Covers team names ESPN writes differently, matched by hand (October 19, 2026)
ALIASES = {
    "brigham-young-cougars": 252, "connecticut-huskies": 41, "florida-international-golden-panthers": 2229,
    "grand-canyon-antelopes": 2253, "illinois-chicago-flames": 82, "liu-sharks": 112358, "louisiana-monroe-warhawks": 2433,
    "louisiana-state-tigers": 99, "massachusetts-minutemen": 113, "md-baltimore-county-retrievers": 2378,
    "miami-florida-hurricanes": 2390, "michigan-st-spartans": 127, "middle-tennessee-st.-blue-raiders": 2393,
    "mississippi-rebels": 145, "monmouth-nj-hawks": 2405, "nc-wilmington-seahawks": 350, "ohio-st-buckeyes": 194,
    "southern-methodist-mustangs": 2567, "st.-john-s-red-storm": 2599, "st.-joseph-s-pa-hawks": 2603, "st.-mary-s-gaels": 2608,
    "texas-christian-horned-frogs": 2628, "texas-el-paso-miners": 2638, "ul-lafayette-ragin-cajuns": 309,
    "unlv-runnin-rebels": 2439, "valparaiso-crusaders": 2674, "miami-oh-red-hawks": 193, "southern-california-trojans": 30,
    "central-florida-knights": 2116, "massachusetts-lowell-river-hawks": 2349, "prairie-view-a-m-panthers": 2504,
    "saint-mary-s-gaels": 2608, "southeastern-louisiana-lions": 2545, "texas-rio-grande-valley-vaqueros": 292,
    "texas-san-antonio-roadrunners": 2636, "se-missouri-st.-redhawks": 2546, "texas-a-m-aggies": 245,
    "saint-joseph-s-hawks": 2603, "nebraska-omaha-mavericks": 2437, "valparaiso-basketball-team": 2674,
    "mount-st.-mary-s-mountaineers": 116, "american-eagles": 44, "mcneese-st.-cowboys": 2377, "north-carolina-a-t-aggies": 2448,
    "texas-a-m-cc-islanders": 357, "csu-bakersfield-roadrunners": 2934, "texas-arlington-mavericks": 250,
    "queens-university-of-charlotte-royals": 2511, "sam-houston-st.-bearkats": 2534, "saint-peter-s-peacocks": 2612,
    "george-washington-revolutionaries": 45, "elon-university-phoenix": 2210, "cal-poly-slo-mustangs": 13,
    "nicholls-state-colonels": 2447, "seattle-redhawks": 2547, "csu-fullerton-titans": 2239, "texas-a-m-commerce-lions": 2837,
    "miami-fl-hurricanes": 2390, "north-carolina-state-wolfpack": 152, "delaware-fightin-blue-hens": 48,
    "hawai-i-rainbow-warriors": 62, "utah-runnin-utes": 254, "tarleton-state-texans": 2627, "penn-quakers": 219,
}
LEFT_GAME = re.compile(r"forced (from|out)|(removed|lifted) from|left (the |his |saturday|sunday|monday|tuesday|wednesday|thursday|"
                       r"friday|last)|exited|went down|helped off|did ?n.t return|did not return|in the (first|second) half|"
                       r"during (the|his|a|last)|injured in|got hurt|suffered .{0,40}\bin (the|a|his|last|[a-z]+day)\b", re.I)
SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}


def _slug(s) -> str:
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower().replace("'", "").replace("&", "and")
    s = re.sub(r"\bst\.", "state", s)
    s = re.sub(r"\bst\b(?=-|$)", "state", s.replace("-", " ")).replace(" ", "-")
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def _person(s) -> str:
    """A name with accents, punctuation, spaces and a trailing Jr./III removed, so 'N'Faly Dante', 'n-faly-dante'
    and 'J.J. Starling', 'j-j-starling' meet."""
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    words = [w for w in re.split(r"[^a-z0-9]+", s) if w]
    while len(words) > 1 and words[-1] in SUFFIXES:
        words.pop()
    return "".join(words)


# --- injuries: Covers listings matched to missed-game runs -------------------------------------------------

def espn_teams() -> pd.DataFrame:
    cols = ["team_id", "team_slug", "team_display_name"]
    return pd.concat([pd.read_parquet(sources.season_path("espn_mbb_player_box", s), columns=cols) for s in SEASONS]).drop_duplicates("team_id")


def team_ids(listings: pd.DataFrame) -> dict:
    """Covers team slug -> ESPN team id: normalized names, then the hand-checked aliases."""
    teams = espn_teams()
    exact = {}
    for col in ("team_slug", "team_display_name"):
        for v, tid in zip(teams[col], teams["team_id"]):
            exact.setdefault(_slug(v), int(tid))
    out = {}
    for slug in listings["team_slug"].unique():
        tid = ALIASES.get(slug, exact.get(_slug(slug)))
        if tid is not None:
            out[slug] = int(tid)
    return out


def box(season: int) -> pd.DataFrame:
    b = pd.read_parquet(sources.season_path("ncaa_player_box", season),
                        columns=["contest_id", "game_date", "player_id", "clean_name", "team", "team_espn_team_id", "mins", "pf"])
    b["player_id"] = pd.to_numeric(b["player_id"], errors="coerce")
    b["team_id"] = pd.to_numeric(b["team_espn_team_id"], errors="coerce")
    b["contest_id"] = pd.to_numeric(b["contest_id"], errors="coerce")
    b["game_date"] = pd.to_datetime(b["game_date"])
    b = b.dropna(subset=["player_id", "team_id", "contest_id"]).astype({"player_id": "int64", "team_id": "int64", "contest_id": "int64"})
    b["season"] = season
    return b[b["mins"] > 0]


def match_players(listings: pd.DataFrame, boxes: pd.DataFrame) -> pd.DataFrame:
    """Each listing with the NCAA player id of the player it names: same team, same season, same name (a looser
    initial-and-surname match picked teammates of players who did not play, so there is none)."""
    tid = team_ids(listings)
    lst = listings.assign(team_id=listings["team_slug"].map(tid))
    names = boxes.drop_duplicates(["season", "team_id", "player_id"])[["season", "team_id", "player_id", "clean_name"]].copy()
    names["key"] = names["clean_name"].map(_person)
    unique = names.groupby(["season", "team_id", "key"])["player_id"].agg(lambda x: x.iloc[0] if x.nunique() == 1 else -1).to_dict()
    lst["slug_key"] = lst["player_slug"].map(_person)
    pid, how = [], []
    for s, t, k in zip(lst["season"], lst["team_id"], lst["slug_key"]):
        p = unique.get((s, int(t), k)) if pd.notna(t) else None
        if pd.isna(t):
            pid.append(np.nan); how.append("no team")
        elif p is not None and p >= 0:
            pid.append(p); how.append("name")
        else:
            pid.append(np.nan); how.append("not found" if p is None else "two players of that name")
    lst["player_id"], lst["match"] = pid, how
    return lst


def runs(boxes: pd.DataFrame) -> pd.DataFrame:
    """Missed-game runs: consecutive team games a player did not play, after a game he played."""
    out = []
    sched = boxes.drop_duplicates(["season", "team_id", "contest_id"])[["season", "team_id", "contest_id", "game_date"]]
    sched = sched.sort_values(["season", "team_id", "game_date", "contest_id"])
    games = {k: g.reset_index(drop=True) for k, g in sched.groupby(["season", "team_id"])}
    played = boxes.groupby(["season", "team_id", "player_id"])["contest_id"].agg(set)
    for (season, team, pid), mine in played.items():
        g = games[(season, team)]
        flags = g["contest_id"].isin(mine).to_numpy()
        idx = np.flatnonzero(flags)
        if not len(idx):
            continue
        i = idx[0]
        while i < len(g):
            if flags[i]:
                i += 1
                continue
            j = i
            while j < len(g) and not flags[j]:
                j += 1
            out.append(dict(season=season, team_id=team, player_id=pid, prev_game=int(g["contest_id"][i - 1]),
                            prev_date=g["game_date"][i - 1], first_missed=int(g["contest_id"][i]), first_date=g["game_date"][i],
                            last_date=g["game_date"][j - 1], games_missed=j - i, back=j < len(g)))
            i = j
    return pd.DataFrame(out)


def label_runs(r: pd.DataFrame, lst: pd.DataFrame, strict: bool = False) -> pd.DataFrame:
    """The plan's rule: a run is a new injury of a body part when a listing for him with a named body part was saved
    during it or carries a note dated from 3 days before the game before it to 14 days after its first missed game
    (the earliest-dated named listing wins). ``strict`` is the sensitivity check the review asked for: each listing
    labels one run (the one it was saved during, else the latest run whose window holds its note date and that had
    not ended before it), a non-injury listing saved during a run outranks named listings from outside it, and the
    most recent named listing saved during the run wins."""
    lst = lst[lst["player_id"].notna()].astype({"player_id": "int64"})
    by_player = {k: g for k, g in lst.groupby(["season", "player_id"])}
    r = r.reset_index(drop=True)
    day = pd.Timedelta(days=1)
    picks = [None] * len(r)   # (chosen listing, every candidate note)
    if not strict:
        for i, (season, pid, prev_date, first, last) in enumerate(zip(r["season"], r["player_id"], r["prev_date"], r["first_date"],
                                                                      r["last_date"])):
            g = by_player.get((season, pid))
            if g is None:
                continue
            during = (g["captured"] >= first) & (g["captured"] <= last + day)
            near = (g["note_date"] >= prev_date - LABEL_BEFORE * day) & (g["note_date"] <= first + LABEL_AFTER * day)
            cand = g[during | near].sort_values(["note_date", "captured"])
            if len(cand):
                named = cand[cand["group"].notna()]
                picks[i] = (named.iloc[0] if len(named) else cand.iloc[0], list(cand["note"]))
    else:
        assigned: dict[int, list] = {}
        runs_of = {k: g for k, g in r.groupby(["season", "player_id"])}
        for key, g in by_player.items():
            rr = runs_of.get(key)
            if rr is None:
                continue
            for _, listing in g.iterrows():
                during = rr[(rr["first_date"] <= listing["captured"]) & (listing["captured"] <= rr["last_date"] + day)]
                if len(during):
                    assigned.setdefault(during.index[-1], []).append((listing, True))
                    continue
                near = rr[(listing["note_date"] >= rr["prev_date"] - LABEL_BEFORE * day) & (listing["note_date"] <= rr["first_date"] + LABEL_AFTER * day)
                          & (rr["last_date"] >= listing["note_date"] - day)]
                if len(near):
                    assigned.setdefault(near.index[-1], []).append((listing, False))
        for i, cands in assigned.items():
            during_named = [x for x, d in cands if d and pd.notna(x["group"])]
            during_other = [x for x, d in cands if d and pd.isna(x["group"])]
            near_named = [x for x, d in cands if not d and pd.notna(x["group"])]
            hit = (max(during_named, key=lambda x: x["captured"]) if during_named else during_other[0] if during_other
                   else max(near_named, key=lambda x: x["note_date"]) if near_named else cands[0][0])
            picks[i] = (hit, [x["note"] for x, _ in cands])
    labels = []
    for pick in picks:
        if pick is None:
            labels.append(dict(label="none"))
            continue
        hit, notes = pick
        labels.append(dict(label="injury" if pd.notna(hit["group"]) else "not injury", part=hit["part"], group=hit["group"],
                           kind=hit["kind"], status=hit["status"], note=hit["note"], note_date=hit["note_date"], covers_id=hit["covers_id"],
                           left_game_note=any(bool(LEFT_GAME.search(n or "")) for n in notes)))
    return pd.concat([r, pd.DataFrame(labels)], axis=1)


# --- play-by-play ----------------------------------------------------------------------------------------

def season_plays(season: int) -> pd.DataFrame:
    cols = ["contest_id", "game_date", "period", "game_seconds", "home_score", "away_score", "event_type", "event_result",
            "event_description", "player_1_id", "event_team_espn_team_id", "home_espn_team_id", "away_espn_team_id",
            "is_paint", "is_fastbreak", "foul_class", "is_flagrant", "turnover_type"] + LINEUP
    p = pd.read_parquet(sources.season_path("ncaa_pbp", season), columns=cols)
    p["order_index"] = np.arange(len(p))   # the file keeps each game's plays in order
    return prepare(p)


def prepare(p: pd.DataFrame) -> pd.DataFrame:
    for c in ["contest_id", "player_1_id", "event_team_espn_team_id", "home_espn_team_id", "away_espn_team_id"] + LINEUP:
        p[c] = pd.to_numeric(p[c], errors="coerce")
    p = p.dropna(subset=["contest_id"]).copy()
    p["contest_id"] = p["contest_id"].astype("int64")
    p = p.sort_values(["contest_id", "order_index"]).reset_index(drop=True)
    p["game_id"] = p["contest_id"]
    period = p["period"].to_numpy(dtype=int)
    p["period_start"] = np.where(period <= 2, (period - 1) * 1200, 2400 + (period - 3) * 300)
    p["period_end"] = np.where(period <= 2, period * 1200, 2400 + (period - 2) * 300)
    p["t"] = pd.Series(np.clip(p["game_seconds"].to_numpy(dtype=float), p["period_start"], p["period_end"])).groupby(
        [p["game_id"], p["period"]]).cummax().to_numpy()
    p["person_id"] = p["player_1_id"].fillna(0).astype("int64")
    p["team"] = p["event_team_espn_team_id"].fillna(0).astype("int64")
    for c in ("home_score", "away_score"):
        p[c] = pd.to_numeric(p[c], errors="coerce")
        p[c] = p.groupby("game_id")[c].ffill().fillna(0)
    for c in ("event_type", "event_description", "foul_class", "turnover_type"):
        p[c] = p[c].fillna("").astype(str)
    for c in ("is_paint", "is_fastbreak", "is_flagrant"):
        p[c] = p[c].fillna(False).astype(bool)
    p["row"] = np.arange(len(p))
    return p


def _descriptor(p: pd.DataFrame) -> pd.Series:
    return p["event_description"].str.extract(r",\s*(?:2pt|3pt)\s+([a-z]+)", expand=False).fillna("")


def player_plays(p: pd.DataFrame) -> pd.DataFrame:
    """One row per play a player was credited with: game_id, player_id, period, t, order_index, play."""
    e = p["event_type"]
    person = p["person_id"] > 0
    shot = e.isin(SHOTS) & person
    rim = shot & e.isin({"Layup", "Dunk"})
    kind = _descriptor(p)
    turnover = (e == "Turnover") & person
    masks = {
        "rebound": e.isin({"Offensive Rebound", "Defensive Rebound"}) & person,
        "off_rebound": (e == "Offensive Rebound") & person,
        "def_rebound": (e == "Defensive Rebound") & person,
        "rim": rim,
        "drive": shot & (kind.isin({"drivinglayup", "floatingjumpshot"}) | (rim & p["is_fastbreak"])),
        "dunk": (e == "Dunk") & person,
        "putback": shot & kind.isin({"tipinlayup", "tipindunk"}),
        "jumper": shot & ~rim,
        "fouled": (e == "Draw Foul") & person,
        "foul_def": (e == "Commits Foul") & person & (p["foul_class"] == "personal"),
        "foul_off": (e == "Commits Foul") & person & (p["foul_class"] == "offensive"),
        "block": (e == "Blocked Shot") & person,
        "steal": (e == "Steal") & person,
        "tov_handle": turnover & p["turnover_type"].isin(HANDLING),
        "tov_pass": turnover & ~p["turnover_type"].isin(HANDLING),
    }
    cols = ["game_id", "person_id", "period", "t", "order_index"]
    return pd.concat([p.loc[m, cols].assign(play=k) for k, m in masks.items()], ignore_index=True).rename(columns={"person_id": "player_id"})


def context_plays(p: pd.DataFrame) -> pd.DataFrame:
    """Plays a player was on the floor for: any rebound, a rebound of a miss in the paint, or the other team's
    shot at the rim while he was defending."""
    e = p["event_type"]
    rebound = e.isin({"Offensive Rebound", "Defensive Rebound"}) & (p["person_id"] > 0)
    missed = e.isin(SHOTS) & (p["event_result"] == "missed")
    paint = p["is_paint"].astype(float).where(missed | (e == "Free Throw")).groupby(p["game_id"]).ffill().fillna(0).astype(bool)
    rim = e.isin({"Layup", "Dunk"})
    home_shoots = rim & (p["team"] == p["home_espn_team_id"])
    away_shoots = rim & (p["team"] == p["away_espn_team_id"])
    frames = []
    for name, mask, cols in (("scramble", rebound, LINEUP), ("scramble_close", rebound & paint, LINEUP),
                             ("opp_rim", home_shoots, AWAY), ("opp_rim", away_shoots, HOME)):
        part = p.loc[mask, ["game_id", "period", "t", "order_index"] + cols].melt(
            id_vars=["game_id", "period", "t", "order_index"], value_vars=cols, value_name="player_id")
        part = part[part["player_id"] > 0].astype({"player_id": "int64"})
        frames.append(part[["game_id", "player_id", "period", "t", "order_index"]].assign(play=name))
    return pd.concat(frames, ignore_index=True)


# --- who was on the floor ----------------------------------------------------------------------------------

def presence(p: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """(exits, stretches, counts): from the game's first lineup and the substitution log, checked against each
    period's first lineup (a mismatch resets to it). A player taken out at the very start of a period left at the
    end of the one before."""
    exits, stretches = [], []
    resets = 0
    own = p[(p["person_id"] > 0) & ~p["event_type"].isin({"Enters Game", "Leaves Game"})]
    own_t = {k: np.sort(v.to_numpy()) for k, v in own.groupby(["game_id", "person_id"])["t"]}
    for gid, g in p.groupby("game_id", sort=False):
        on, since, by_sub = set(), {}, set()
        game_exits, game_stretches = [], []
        team_of = {}
        for side, cols in (("home_espn_team_id", HOME), ("away_espn_team_id", AWAY)):
            tid = g[side].dropna()
            tid = int(tid.iloc[0]) if len(tid) else 0
            for c in cols:
                for v in g[c].dropna().unique():
                    team_of.setdefault(int(v), tid)
        for pid, team in zip(g["person_id"], g["team"]):
            if pid > 0 and team > 0:
                team_of.setdefault(pid, team)
        prev_end, prev_period = None, None
        for period, gp in g.groupby("period", sort=True):
            start, end = gp["period_start"].iloc[0], gp["period_end"].iloc[0]
            subs_mask = gp["event_type"].isin({"Enters Game", "Leaves Game"})
            plays = gp[~subs_mask]
            first_play = plays["order_index"].min() if len(plays) else np.inf
            full = plays[plays[LINEUP].notna().all(axis=1)]
            first_lineup = set(full.iloc[0][LINEUP].astype("int64")) if len(full) else None
            subs = gp[subs_mask]
            opening = subs[(subs["t"] == start) & (subs["order_index"] < first_play)]   # changes before the period's first play
            rest = subs.drop(opening.index)
            if prev_period is None:
                on = set(first_lineup) if first_lineup else set()
                for s in opening.itertuples():   # the first lineup is after the opening changes: undo them for the starters
                    if s.event_type == "Enters Game":
                        on.discard(s.person_id)
                    else:
                        on.add(s.person_id)
                since = {pid: start for pid in on}
            by_sub, entered_at_start, opening_break = set(), set(), {}
            for batch, at_start in ((opening, prev_period is not None), (rest, False)):
                if batch is rest and first_lineup and len(first_lineup) == 10 and first_lineup != on:
                    # check against the period's first lineup once its opening changes are through
                    resets += 1
                    for pid in on - first_lineup:   # a change we did not see: he did not start this period
                        since.pop(pid, None)
                        if prev_period is not None:
                            game_exits.append(dict(game_id=gid, player_id=pid, period=prev_period, t=prev_end, how="break",
                                                   row=-1, order=-1, team=team_of.get(pid, 0)))
                    for pid in first_lineup - on:
                        since[pid] = start
                    on = set(first_lineup)
                for s in batch.itertuples():
                    pid, t = s.person_id, s.t
                    if pid <= 0:
                        continue
                    if s.event_type == "Leaves Game":
                        if pid not in on:
                            continue
                        on.discard(pid)
                        if at_start and pid in entered_at_start:
                            since.pop(pid, None)  # logged in and straight back out before the period began: never played
                        elif at_start:   # did not start the period: left at the end of the one before
                            since.pop(pid, None)
                            opening_break[pid] = dict(game_id=gid, player_id=pid, period=prev_period, t=prev_end, how="break",
                                                      row=-1, order=-1, team=team_of.get(pid, 0))
                            game_exits.append(opening_break[pid])
                        elif since.get(pid) == t:
                            since.pop(pid)       # in and straight back out at one stoppage (or before any play): never played
                        else:
                            game_stretches.append((gid, pid, period, since.pop(pid, start), t))
                            game_exits.append(dict(game_id=gid, player_id=pid, period=period, t=t, how="substitution",
                                                   row=s.row, order=s.order_index, team=team_of.get(pid, 0)))
                    else:
                        if pid in on:
                            continue
                        if at_start and pid in opening_break:   # out and straight back in before the period began: never left
                            game_exits.remove(opening_break.pop(pid))
                            since[pid] = start
                            on.add(pid)
                            continue
                        if at_start:
                            entered_at_start.add(pid)
                        same = [e for e in game_exits if e["player_id"] == pid and e["t"] == t and e["how"] == "substitution"]
                        if same:   # out and straight back in at one stoppage: he never left
                            game_exits.remove(same[-1])
                            last = [x for x in game_stretches if x[1] == pid and x[4] == t]
                            if last:
                                game_stretches.remove(last[-1])
                            since[pid] = last[-1][3] if last else t
                        else:
                            since[pid] = start if at_start else t
                            by_sub.add(pid)
                        on.add(pid)
            for pid in on:   # close the period's stretches; carry the floor into the next period
                game_stretches.append((gid, pid, period, since.get(pid, start), end))
                since[pid] = end
            prev_end, prev_period = end, period
            since = {pid: end for pid in on}
        exits += game_exits
        stretches += game_stretches
    e = pd.DataFrame(exits, columns=["game_id", "player_id", "period", "t", "how", "row", "order", "team"])
    st = pd.DataFrame(stretches, columns=["game_id", "player_id", "period", "start_t", "end_t"])
    st = st[st["end_t"] > st["start_t"]]
    later_start = st.groupby(["game_id", "player_id"])["start_t"].max()
    last_out = e.groupby(["game_id", "player_id"])["t"].max()
    key = pd.MultiIndex.from_frame(e[["game_id", "player_id"]])
    came_back = later_start.reindex(key).to_numpy() > e["t"].to_numpy()
    came_back |= last_out.reindex(key).to_numpy() > e["t"].to_numpy()
    plays_after = np.array([(own_t.get((g, pid)) is not None) and bool((own_t[(g, pid)] > t).any())
                            for g, pid, t in zip(e["game_id"], e["player_id"], e["t"])], dtype=bool)
    e["returned"] = came_back.astype(bool) | plays_after
    return e, st, dict(lineup_resets=resets)


STOPPAGE_RANK = ["own timeout", "opponent timeout", "media timeout", "foul", "free throws", "turnover or violation", "jump ball",
                 "team rebound"]


def stoppage(p: pd.DataFrame, e: pd.DataFrame) -> np.ndarray:
    """What stopped play when he went out, from every play logged at that second on either side of the substitution
    rows (a timeout of either team or the media first, then a foul, free throws, a turnover or violation, a held
    ball, a dead-ball rebound; a dead-ball rebound after a missed free throw is part of the free throws). For a null
    exit the dead-ball play itself counts. Nothing at that second means the stoppage was not logged: often
    officials stopping play for a hurt player, sometimes a TV timeout."""
    event, team, game, t = p["event_type"].to_numpy(), p["team"].to_numpy(), p["game_id"].to_numpy(), p["t"].to_numpy()
    result = p["event_result"].to_numpy()
    code = pd.factorize(p["game_id"])[0].astype(np.int64)
    keys = code * 100_000 + np.round(t * 10).astype(np.int64)
    subs = {"Enters Game", "Leaves Game"}

    def label(j, own_team):
        a = event[j]
        if "Timeout" in a:
            if "Media" in a or team[j] == 0:
                return "media timeout"
            return "own timeout" if team[j] == own_team else "opponent timeout"
        if a in ("Commits Foul", "Draw Foul"):
            return "foul"
        if a == "Free Throw":
            return "free throws"
        if a in ("Turnover",) or "Violation" in a:
            return "turnover or violation"
        if a.startswith("Jumpball"):
            return "jump ball"
        if a == "Deadball Rebound":
            k = j - 1
            while k >= 0 and game[k] == game[j] and event[k] in subs:
                k -= 1
            return "free throws" if k >= 0 and event[k] == "Free Throw" and result[k] == "missed" else "team rebound"
        return None

    out = []
    for row, how, own_team in zip(e["row"], e["how"], e["team"]):
        if how == "break":
            out.append("break")
            continue
        i = int(row)
        own = label(i, own_team) if event[i] not in subs else None   # a null exit's dead ball labels itself
        lo, hi = np.searchsorted(keys, keys[i], side="left"), np.searchsorted(keys, keys[i], side="right")
        found = [label(j, own_team) for j in range(lo, hi) if event[j] not in subs]
        found = [x for x in found + [own] if x]
        out.append(min(found, key=STOPPAGE_RANK.index) if found else "no logged stoppage")
    return np.array(out, dtype=object)


def exits(p: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    e, st, counts = presence(p)
    e["game_end"] = p.groupby("game_id")["period_end"].max().reindex(e["game_id"]).to_numpy()
    e["margin"] = margin_at(p, e)
    fouls = p[(p["event_type"] == "Commits Foul") & p["foul_class"].isin({"personal", "offensive"})]
    times = {k: np.sort(v.to_numpy()) for k, v in fouls.groupby(["game_id", "person_id"])["t"]}
    e["fouls"] = [np.searchsorted(times[(g, pid)], t, side="right") if (g, pid) in times else 0
                  for g, pid, t in zip(e["game_id"], e["player_id"], e["t"])]
    flagrant = set(zip(p.loc[p["is_flagrant"] & (p["event_type"] == "Commits Foul"), "game_id"],
                       p.loc[p["is_flagrant"] & (p["event_type"] == "Commits Foul"), "person_id"],
                       p.loc[p["is_flagrant"] & (p["event_type"] == "Commits Foul"), "t"]))
    e["ejected"] = [(g, pid, t) in flagrant for g, pid, t in zip(e["game_id"], e["player_id"], e["t"])]   # out at his own flagrant
    e["stoppage"] = stoppage(p, e)
    e["replaced_shooter"] = False   # the NCAA log names the fouled player directly ("Draw Foul")
    # markers of how he left: alone, and whether a teammate shot the free throws of a foul he drew at that second
    leaves = p[p["event_type"] == "Leaves Game"].groupby(["game_id", "team", "t"]).size()
    e["lone_sub"] = [(how == "substitution") and leaves.get((g, team, t), 0) == 1
                     for g, team, t, how in zip(e["game_id"], e["team"], e["t"], e["how"])]
    drew = set(zip(p.loc[p["event_type"] == "Draw Foul", "game_id"], p.loc[p["event_type"] == "Draw Foul", "person_id"],
                   p.loc[p["event_type"] == "Draw Foul", "t"]))
    ft = p[p["event_type"] == "Free Throw"]
    shooters = ft.groupby(["game_id", "team", "t"])["person_id"].agg(set).to_dict()
    e["replaced_at_line"] = [(g, pid, t) in drew and bool(shooters.get((g, team, t))) and pid not in shooters[(g, team, t)]
                             for g, pid, team, t in zip(e["game_id"], e["player_id"], e["team"], e["t"])]
    return e, st, counts


def foul_kinds(p: pd.DataFrame) -> pd.DataFrame:
    """Each foul a player drew, by what followed at that second: he shot his own free throws, a teammate shot them
    (he was replaced at the line), or no free throws."""
    drew = p[(p["event_type"] == "Draw Foul") & (p["person_id"] > 0)]
    ft = p[p["event_type"] == "Free Throw"].groupby(["game_id", "team", "t"])["person_id"].agg(set).to_dict()
    kind = []
    for g, pid, team, t in zip(drew["game_id"], drew["person_id"], drew["team"], drew["t"]):
        shooters = ft.get((g, team, t), set())
        kind.append("fouled_shot" if pid in shooters else "fouled_replaced" if shooters else "fouled_no_ft")
    return drew[["game_id", "person_id", "period", "t", "order_index"]].rename(columns={"person_id": "player_id"}).assign(play=kind)


EXTRA_PLAYS = [("fouled_shot", "Drew a foul and shot his own free throws"), ("fouled_replaced", "Drew a foul, a teammate shot his free throws"),
               ("fouled_no_ft", "Drew a foul with no free throws")]
MARKERS = [("unlogged", "Left at a stoppage the log does not record"), ("lone_sub", "The only player his team took out"),
           ("replaced_at_line", "A teammate shot the free throws of a foul he drew")]


def extra_flags(m: pd.DataFrame, p: pd.DataFrame) -> pd.DataFrame:
    """Flags the shared statistics do not cover: the three kinds of drawn foul, and the exit markers (the same at every
    window, so a marker compares like a play)."""
    fk = foul_kinds(p)
    cols = {}
    for name, _ in EXTRA_PLAYS:
        line = Timeline(fk[fk["play"] == name])
        for w in WINDOWS:
            cols[f"{name}_{w}"] = line.count(m, w) > 0
    for name, _ in MARKERS:
        v = (m["stoppage"] == "no logged stoppage") if name == "unlogged" else m[name].fillna(False).astype(bool)
        v = v & m["role"].isin(["case", "case_strict_only", "pseudo", "exit"])
        for w in WINDOWS:
            cols[f"{name}_{w}"] = v.to_numpy()
    return pd.concat([m.reset_index(drop=True), pd.DataFrame(cols)], axis=1)


def margin_at(p: pd.DataFrame, m: pd.DataFrame) -> np.ndarray:
    code = pd.factorize(p["game_id"])[0].astype(np.int64)
    keys = code * 100_000 + np.round(p["t"].to_numpy() * 10).astype(np.int64)
    lookup = pd.Series(np.arange(code.max() + 1), index=pd.unique(p["game_id"]))
    mc = lookup.reindex(m["game_id"]).to_numpy()
    ok = np.isfinite(mc)
    k = np.searchsorted(keys, np.where(ok, mc, 0).astype(np.int64) * 100_000 + np.round(m["t"].to_numpy(dtype=float) * 10).astype(np.int64),
                        side="right") - 1
    k = np.clip(k, 0, len(p) - 1)
    return np.where(ok, np.abs(p["home_score"].to_numpy()[k] - p["away_score"].to_numpy()[k]), np.nan)


def null_exits(p: pd.DataFrame, m: pd.DataFrame) -> pd.DataFrame:
    """For each random moment on the floor, the first dead ball at or after it in that period (or its end)."""
    e = p["event_type"]
    steal_next = (p["event_type"].shift(-1) == "Steal") & (p["game_id"].shift(-1) == p["game_id"])
    dead = e.isin(DEAD_BALL) | e.str.contains("Timeout") | e.str.startswith("Jumpball") | ((e == "Turnover") & ~steal_next)
    d = p.loc[dead, ["game_id", "period", "t", "row"]]
    times = {k: (v["t"].to_numpy(), v["row"].to_numpy()) for k, v in d.groupby(["game_id", "period"])}
    period_end = p.groupby(["game_id", "period"])["period_end"].first().to_dict()
    rows = []
    for gid, pid, period, t, season, team in zip(m["game_id"], m["player_id"], m["period"], m["t"], m["season"], m["team"]):
        tt, rr = times.get((gid, period), (np.array([]), np.array([])))
        k = np.searchsorted(tt, t, side="left")
        if k < len(tt):
            rows.append((gid, pid, period, float(tt[k]), int(rr[k]), season, team, "substitution"))
        else:
            rows.append((gid, pid, period, float(period_end.get((gid, period), t)), -1, season, team, "break"))
    n = pd.DataFrame(rows, columns=["game_id", "player_id", "period", "t", "row", "season", "team", "how"])
    n["stoppage"] = stoppage(p, n)
    n["how"] = np.where(n["how"] == "break", "break", "dead ball")
    return n


# --- cases, comparisons and the test ----------------------------------------------------------------------

def usual_minutes(boxes: pd.DataFrame) -> pd.DataFrame:
    b = boxes.sort_values(["player_id", "game_date", "contest_id"]).copy()
    b["usual"] = b.groupby(["season", "player_id"])["mins"].transform(lambda s: s.shift(1).rolling(10, min_periods=3).mean())
    return b[["season", "player_id", "contest_id", "mins", "usual"]].rename(columns={"contest_id": "game_id", "mins": "minutes"})


def early_exit_rules(c: pd.DataFrame, short: float | None = SHORT_GAME) -> pd.Series:
    ok = (c["t"].notna() & (c["t"] <= c["game_end"] - MIN_LEFT) & (c["margin"] <= MAX_MARGIN)
          & ~c["ejected"].fillna(False).astype(bool) & (c["fouls"] < FOUL_OUT) & (c["usual"] >= MIN_USUAL))
    if short is not None:
        ok &= c["minutes"] < short * c["usual"]
    return ok


def case_info(inj: pd.DataFrame) -> pd.DataFrame:
    """Group columns the comparisons read: region, injury_type (ankle sprains from the note), coarse."""
    info = inj[["group", "kind", "note", "part"]].copy()
    info["region"] = info["group"]
    info["injury_type"] = np.where((info["group"] == "ankle") & info["note"].fillna("").str.contains(r"sprain|rolled", case=False),
                                   "sprain", info["kind"])
    info["coarse"] = info["group"]
    return info


def failed_returns(inj: pd.DataFrame, lst: pd.DataFrame) -> np.ndarray:
    """He was already listed with that body part in the 30 days before the game before the run: a return from an
    injury he had, not a new one in that game."""
    named = lst[lst["group"].notna() & lst["player_id"].notna()].astype({"player_id": "int64"})
    by = {k: g["captured"].to_numpy() for k, g in named.groupby(["season", "player_id", "group"])}
    month = np.timedelta64(30, "D")
    return np.array([(k := by.get((s, pid, grp))) is not None and bool(((k < d) & (k >= d - month)).any())
                     for s, pid, grp, d in zip(inj["season"], inj["player_id"], inj["group"], inj["prev_date"].to_numpy())], dtype=bool)


def old_format_games(p: pd.DataFrame) -> set:
    """Games logged in the NCAA's old format: no "Draw Foul" events and under half the shots with a descriptor, so
    drawn fouls, drives, tip-ins and foul kinds cannot show."""
    drew = p.groupby("game_id")["event_type"].agg(lambda s: (s == "Draw Foul").any())
    shots = p[p["event_type"].isin(SHOTS)]
    described = _descriptor(shots).ne("").groupby(shots["game_id"]).mean().reindex(drew.index).fillna(0)
    return set(drew.index[~drew & (described < 0.5)])


def build(log=print) -> dict:
    lst_all = covers.listings()
    boxes = pd.concat([box(s) for s in SEASONS], ignore_index=True)
    lst = match_players(lst_all, boxes)
    all_runs = runs(boxes)
    usual = usual_minutes(boxes)
    labelled = {}
    for name, strict in (("primary", False), ("strict", True)):
        r = label_runs(all_runs, lst, strict=strict)
        labelled[name] = r.merge(usual.rename(columns={"game_id": "prev_game"}), on=["season", "player_id", "prev_game"], how="left")
    r = labelled["primary"]
    any_run = set(zip(r["player_id"], r["prev_game"]))                                     # games right before any missed game
    inj = r[r["label"] == "injury"].reset_index(drop=True)
    inj_s = labelled["strict"][labelled["strict"]["label"] == "injury"].reset_index(drop=True)
    inj["failed_return"], inj_s["failed_return"] = failed_returns(inj, lst), failed_returns(inj_s, lst)
    rng = np.random.default_rng(0)
    frames, background, quality = [], [], []
    for season in SEASONS:
        p = season_plays(season)
        ex, st, counts = exits(p)
        ex["season"] = season
        old = old_format_games(p)

        # quality: minutes rebuilt from the floor against the box score; keep games where 90% are within 2 minutes
        rebuilt = (st.assign(sec=st["end_t"] - st["start_t"]).groupby(["game_id", "player_id"])["sec"].sum() / 60).rename("rebuilt")
        mins = usual[usual["season"] == season].set_index(["game_id", "player_id"])["minutes"]
        j = pd.concat([rebuilt, mins], axis=1).reset_index()
        j["err"] = (j["rebuilt"].fillna(0) - j["minutes"].fillna(0)).abs()
        per_game = j.groupby("game_id")["err"].agg(lambda e: (e <= GOOD_MINUTES).mean())
        good = set(per_game.index[per_game >= GOOD_GAME])
        kept = j[j["game_id"].isin(good)]
        quality.append(dict(season=season, games=int(p["game_id"].nunique()), games_kept=len(good), old_format_games=len(old),
                            old_format_kept=len(old & good), player_games_kept=int(len(kept)),
                            within_1_kept=float((kept["err"] <= 1).mean()), median_minutes_error_kept=float(kept["err"].median()),
                            within_1_all=float((j["err"] <= 1).mean()), lineup_resets=counts["lineup_resets"]))
        ex, st = ex[ex["game_id"].isin(good)], st[st["game_id"].isin(good)]
        ex = ex.merge(usual[usual["season"] == season].drop(columns="season"), on=["player_id", "game_id"], how="left")
        ex["old_format"] = ex["game_id"].isin(old)
        last = ex[~ex["returned"]].sort_values("t").drop_duplicates(["game_id", "player_id"], keep="last")
        for frame in (inj, inj_s):
            here = frame["season"] == season
            frame.loc[here, "evaluable"] = frame.loc[here, "prev_game"].isin(good).to_numpy()

        # the pattern in every eligible game, by what came next
        played = usual[(usual["season"] == season) & (usual["usual"] >= MIN_USUAL) & usual["game_id"].isin(good)]
        bg = played.merge(last.drop(columns=["minutes", "usual", "season"]), on=["player_id", "game_id"], how="left")
        bg["pattern"] = early_exit_rules(bg).to_numpy()
        si = inj[inj["season"] == season]
        injured = set(zip(si["player_id"], si["prev_game"]))
        bg["next"] = np.select([[(a, b) in injured for a, b in zip(bg["player_id"], bg["game_id"])],
                                [(a, b) in any_run for a, b in zip(bg["player_id"], bg["game_id"])]],
                               ["new injury", "missed next game, other or unknown reason"], "played next game")
        background.append(bg[["player_id", "game_id", "next", "pattern"]].assign(season=season))

        # cases under the plan's labels and under the strict ones (any minutes; the main definition adds the rule later)
        found = []
        for frame, col in ((inj, "injury"), (inj_s, "injury_strict")):
            sf = frame[frame["season"] == season]
            c = sf[["player_id", "prev_game", "minutes", "usual"]].reset_index().merge(
                last.drop(columns=["minutes", "usual"]).rename(columns={"game_id": "prev_game"}), on=["player_id", "prev_game"], how="left")
            frame.loc[c["index"], "pinned"] = early_exit_rules(c).to_numpy()
            frame.loc[c["index"], "exit_how"] = c["how"].to_numpy()
            frame.loc[c["index"], "exit_stoppage"] = c["stoppage"].to_numpy()
            found.append(c[early_exit_rules(c, None)].rename(columns={"prev_game": "game_id", "index": col}))
        found[0]["injury_strict"], found[1]["injury"] = -1, -1
        both = pd.concat(found, ignore_index=True)
        agg = {k: "first" for k in both.columns if k not in ("player_id", "game_id", "injury", "injury_strict")}
        cases = both.groupby(["player_id", "game_id"], as_index=False).agg({**agg, "injury": "max", "injury_strict": "max"})
        cases["role"] = np.where(cases["injury"] >= 0, "case", "case_strict_only")

        pseudo = bg[bg["pattern"] & (bg["next"] == "played next game")][["player_id", "game_id"]]
        pseudo = last.merge(pseudo, on=["player_id", "game_id"]).assign(role="pseudo", injury=-1, injury_strict=-1)
        players = set(cases["player_id"]) | set(pseudo["player_id"])
        fair = (ex["t"] <= ex["game_end"] - MIN_LEFT) & (ex["margin"] <= MAX_MARGIN)
        ctrl = ex[ex["returned"] & fair & ex["player_id"].isin(players)]
        ctrl = ctrl[[(a, b) not in any_run for a, b in zip(ctrl["player_id"], ctrl["game_id"])]].assign(role="exit", injury=-1,
                                                                                                         injury_strict=-1)

        case_players = set(cases["player_id"])
        sts = st[st["player_id"].isin(case_players)]
        sts = sts[[(a, b) not in any_run for a, b in zip(sts["player_id"], sts["game_id"])]]
        team_of = dict(zip(zip(ex["game_id"], ex["player_id"]), ex["team"]))
        rand = []
        for (pid, gid), grp in sts.groupby(["player_id", "game_id"]):
            lengths = (grp["end_t"] - grp["start_t"]).to_numpy()
            pick = rng.choice(len(grp), size=RANDOM_PER_GAME, p=lengths / lengths.sum())
            for i, u in zip(pick, rng.random(RANDOM_PER_GAME)):
                rand.append((gid, pid, int(grp["period"].iloc[i]), grp["start_t"].iloc[i] + u * lengths[i], team_of.get((gid, pid), 0)))
        rand = pd.DataFrame(rand, columns=["game_id", "player_id", "period", "t", "team"]).assign(role="random", injury=-1, injury_strict=-1,
                                                                                              season=season, how="random")
        rand["game_end"] = p.groupby("game_id")["period_end"].max().reindex(rand["game_id"]).to_numpy()
        rand["margin"] = margin_at(p, rand)
        rand = rand[(rand["t"] <= rand["game_end"] - MIN_LEFT) & (rand["margin"] <= MAX_MARGIN)]
        null = null_exits(p, rand).assign(role="null", injury=-1, injury_strict=-1)
        null["game_end"] = p.groupby("game_id")["period_end"].max().reindex(null["game_id"]).to_numpy()
        null["margin"] = margin_at(p, null)
        null = null[(null["t"] <= null["game_end"] - MIN_LEFT) & (null["margin"] <= MAX_MARGIN)]

        plays = pd.concat([player_plays(p), context_plays(p)], ignore_index=True)
        keep = ["game_id", "player_id", "season", "period", "t", "how", "role", "injury", "injury_strict", "margin", "stoppage",
                "minutes", "usual", "replaced_shooter", "lone_sub", "replaced_at_line"]
        mm = pd.concat([f.reindex(columns=keep) for f in (cases, pseudo, ctrl, rand, null)], ignore_index=True)
        mm["season"] = season
        for col in ("replaced_shooter", "lone_sub", "replaced_at_line"):
            mm[col] = mm[col].fillna(False).astype(bool)
        mm["stoppage"] = mm["stoppage"].fillna("none")
        mm["old_format"] = mm["game_id"].isin(old)
        frames.append(extra_flags(flag_moments(mm, plays), p))
        log(f"  {season}: {p['game_id'].nunique()} games, {int((cases['role'] == 'case').sum())} injury exits under the plan's labels "
            f"({int((cases['injury_strict'] >= 0).sum())} under the strict ones; any minutes), {len(pseudo)} early exits with no injury, "
            f"{len(ctrl)} ordinary exits; {quality[-1]['games_kept']} of {quality[-1]['games']} games kept")
    m = pd.concat(frames, ignore_index=True)
    m["ratio"] = m["minutes"] / m["usual"]
    for frame in (inj, inj_s):
        frame["pinned"] = frame["pinned"].fillna(False).astype(bool)
        frame["evaluable"] = frame["evaluable"].fillna(False).astype(bool)
    info = case_info(inj).assign(failed_return=inj["failed_return"])
    m = m.merge(info[["region", "injury_type", "coarse", "part", "note", "failed_return"]], left_on="injury", right_index=True, how="left")
    info_s = case_info(inj_s).assign(failed_return=inj_s["failed_return"])
    info_s.columns = [f"{c}_s" for c in info_s.columns]
    m = m.merge(info_s[["region_s", "injury_type_s", "coarse_s", "failed_return_s"]], left_on="injury_strict", right_index=True, how="left")
    return dict(moments=m, injuries=inj, injuries_strict=inj_s, runs=r, listings=lst, background=pd.concat(background, ignore_index=True),
                quality=quality)


def view(m: pd.DataFrame, labels: str = "primary", drop_failed: bool = False, drop_old: bool = False) -> pd.DataFrame:
    """The moments as one analysis sees them: the plan's labels (main) or the strict ones; optionally without returns
    from an injury he already had, or without old-format games."""
    if labels == "strict":
        v = m.copy()
        is_case = v["role"].isin(["case", "case_strict_only"])
        v.loc[is_case, "role"] = np.where(v.loc[is_case, "injury_strict"] >= 0, "case", "dropped")
        for c in ("region", "injury_type", "coarse", "failed_return"):
            v[c] = v[f"{c}_s"]
    else:
        v = m[m["role"] != "case_strict_only"]
    if drop_failed:
        v = v[~((v["role"] == "case") & v["failed_return"].fillna(False).astype(bool))]
    if drop_old:
        v = v[~v["old_format"]]
    return v


def in_group(group: str, frame: pd.DataFrame) -> pd.Series:
    if group == "any":
        return pd.Series(True, index=frame.index)
    if group == "ankle_sprain":
        return (frame["region"] == "ankle") & (frame["injury_type"] == "sprain")
    return frame["coarse"] == group


def compare(m: pd.DataFrame, group: str, play: str, width: int = WINDOW, against: str = "exit", case_role: str = "case",
            short: float | None = SHORT_GAME, by_stoppage: bool = False) -> dict:
    """As moments.compare, with the college groups."""
    sel = (m["role"] == case_role) & ((m["ratio"] < short) if short is not None else True)
    cases = m[sel & (in_group(group, m) if case_role == "case" else True)]
    if against == "other injuries":
        pool = m[(m["role"] == "case") & ((m["ratio"] < short) if short is not None else True) & ~in_group(group, m)]
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
    halves = [causes.mantel_haenszel(stratum[part], x[part], y[part])[0]
              for part in ((d["season"] <= SPLIT_SEASON).to_numpy(), (d["season"] > SPLIT_SEASON).to_numpy())]
    return dict(group=group, play=play, window=width, against=against, case_role=case_role, short=short, by_stoppage=by_stoppage,
                cases=int(y.sum()), comparisons=int((~y).sum()), exposed=int(x[y].sum()),
                case_share=float(x[y].mean()) if y.any() else np.nan, comparison_share=float(x[~y].mean()) if (~y).any() else np.nan,
                odds_ratio=odds, lo=lo, hi=hi, p=p_value(odds, lo, hi), first_half=halves[0], second_half=halves[1],
                same_way=all(np.isfinite(h) and np.isfinite(odds) and ((h > 1) == (odds > 1)) for h in halves))


def holm(ps: list[float]) -> list[float]:
    order = np.argsort(ps)
    adj = np.empty(len(ps))
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (len(ps) - rank) * ps[i]))
        adj[i] = running
    return adj.tolist()


# --- the same comparison from per-stratum counts: exact test, power, pooling ------------------------------

def strata_table(m: pd.DataFrame, group: str, play: str, width: int = WINDOW, against: str = "exit") -> pd.DataFrame:
    """Per player-season stratum: a = exposed injury exits, b = unexposed, c = exposed comparisons, d = unexposed."""
    cases = m[(m["role"] == "case") & (m["ratio"] < SHORT_GAME) & in_group(group, m)]
    kc = cases["player_id"].astype(str) + "_" + cases["season"].astype(str)
    pool = m[m["role"] == against]
    kp = pool["player_id"].astype(str) + "_" + pool["season"].astype(str)
    keep = kp.isin(set(kc))
    t = pd.DataFrame({"s": np.concatenate([kc.to_numpy(), kp[keep].to_numpy()]),
                      "case": np.r_[np.ones(len(cases), int), np.zeros(int(keep.sum()), int)],
                      "x": np.r_[flag(cases, play, width), flag(pool[keep], play, width)].astype(int)})
    c = t.groupby(["s", "case", "x"]).size().unstack(["case", "x"], fill_value=0)
    out = pd.DataFrame(index=c.index)
    for name, col in (("a", (1, 1)), ("b", (1, 0)), ("c", (0, 1)), ("d", (0, 0))):
        out[name] = c[col] if col in c.columns else 0
    return out.astype(float)


def mh_counts(a, b, c, d) -> tuple[float, float, float, float]:
    """Mantel-Haenszel odds ratio, RBG 95% interval and Wald p from per-stratum counts (arrays, or reps x strata)."""
    n = a + b + c + d
    with np.errstate(divide="ignore", invalid="ignore"):
        R, S = np.where(n > 1, a * d / n, 0), np.where(n > 1, b * c / n, 0)
        P, Q = np.where(n > 1, (a + d) / n, 0), np.where(n > 1, (b + c) / n, 0)
        sR, sS = R.sum(axis=-1), S.sum(axis=-1)
        odds = sR / sS
        var = (P * R).sum(axis=-1) / (2 * sR ** 2) + (P * S + Q * R).sum(axis=-1) / (2 * sR * sS) + (Q * S).sum(axis=-1) / (2 * sS ** 2)
        se = np.sqrt(var)
        z = np.abs(np.log(odds)) / se
    from scipy.stats import norm
    return odds, odds * np.exp(-1.96 * se), odds * np.exp(1.96 * se), 2 * norm.sf(z)


def exact_test(t: pd.DataFrame) -> dict:
    """Exact conditional test (stratified hypergeometric) of the number of exposed injury exits: one-sided (more than
    expected) and two-sided by minimum likelihood."""
    from scipy.stats import hypergeom
    dist = np.array([1.0])
    for a, b, c, d in t[["a", "b", "c", "d"]].to_numpy().astype(int):
        N, K, n = a + b + c + d, a + c, a + b
        lo, hi = max(0, n - (N - K)), min(n, K)
        pmf = np.zeros(hi + 1)
        pmf[lo:hi + 1] = hypergeom.pmf(np.arange(lo, hi + 1), N, K, n)
        dist = np.convolve(dist, pmf)
    obs = int(t["a"].sum())
    p_obs = dist[obs] if obs < len(dist) else 0.0
    expected = float((np.arange(len(dist)) * dist).sum())
    return dict(observed=obs, expected=expected, p_one_sided=float(dist[obs:].sum()), p_two_sided=float(dist[dist <= p_obs * (1 + 1e-7)].sum()))


def power(t: pd.DataFrame, true_or: float, reps: int = 4000, alphas=(0.05, 0.0125), seed: int = 0) -> dict:
    """How often this test, on these strata and their comparisons, finds OR > 1 at each alpha if the true odds ratio
    is ``true_or``: case exposures simulated from each stratum's comparison rate (shrunk toward the pooled rate)."""
    rng = np.random.default_rng(seed)
    a, b, c, d = (t[k].to_numpy() for k in "abcd")
    cases, ctrl = a + b, c + d
    pooled = c.sum() / max(ctrl.sum(), 1)
    p0 = (c + 10 * pooled) / (ctrl + 10)
    p1 = p0 * true_or / (1 - p0 + p0 * true_or)
    sim_a = rng.binomial(cases.astype(int), p1, size=(reps, len(a))).astype(float)
    odds, lo, hi, p = mh_counts(sim_a, cases - sim_a, np.broadcast_to(c, sim_a.shape), np.broadcast_to(d, sim_a.shape))
    ok = np.isfinite(p) & (odds > 1)
    return {f"at_{alpha}": float((ok & (p < alpha)).mean()) for alpha in alphas}


def pooled(m: pd.DataFrame, hyps: list[tuple[str, str]]) -> dict:
    """Fixed-effect pool of several log odds ratios that share cases (GLS with a delete-one-stratum jackknife
    covariance), and the same pool treating them as independent. Exploratory: not in the plan."""
    tables = [strata_table(m, g, pl) for g, pl in hyps]
    theta, var = [], []
    for t in tables:
        o, lo, hi, _ = mh_counts(*(t[k].to_numpy() for k in "abcd"))
        theta.append(np.log(o))
        var.append(((np.log(hi) - np.log(lo)) / 3.92) ** 2)
    theta, var = np.array(theta), np.array(var)
    strata = sorted(set().union(*[set(t.index) for t in tables]))
    jack = np.empty((len(strata), len(hyps)))
    sums = []
    for t in tables:
        a, b, c, d = (t[k].to_numpy() for k in "abcd")
        n = a + b + c + d
        R, S = np.where(n > 1, a * d / n, 0), np.where(n > 1, b * c / n, 0)
        sums.append((pd.Series(R, index=t.index), pd.Series(S, index=t.index), R.sum(), S.sum()))
    for i, s in enumerate(strata):
        for j, (R, S, sR, sS) in enumerate(sums):
            jack[i, j] = np.log((sR - R.get(s, 0.0)) / (sS - S.get(s, 0.0)))
    n = len(strata)
    ones = np.ones(len(hyps))
    from scipy.stats import norm, chi2
    if np.isfinite(jack).all() and np.isfinite(theta).all():
        dev = jack - jack.mean(axis=0)
        cov = (n - 1) / n * dev.T @ dev
        inv = np.linalg.pinv(cov)
        w = inv @ ones / (ones @ inv @ ones)
        est, se = float(w @ theta), float(np.sqrt(1 / (ones @ inv @ ones)))
        correlated = dict(odds_ratio=float(np.exp(est)), lo=float(np.exp(est - 1.96 * se)), hi=float(np.exp(est + 1.96 * se)),
                          p=float(2 * norm.sf(abs(est / se))))
    else:   # a stratum holds every exposed case of some hypothesis: the jackknife is not defined
        correlated = dict(odds_ratio=np.nan, lo=np.nan, hi=np.nan, p=np.nan)
    ok = np.isfinite(theta) & np.isfinite(var) & (var > 0)
    wi = (1 / var[ok]) / (1 / var[ok]).sum()
    est_i, se_i = float(wi @ theta[ok]), float(np.sqrt(1 / (1 / var[ok]).sum()))
    q = float(((theta[ok] - est_i) ** 2 / var[ok]).sum())
    return dict(hypotheses=[f"{g}:{pl}" for g, pl in hyps], odds_ratios=np.exp(theta).tolist(),
                correlated=correlated,
                independent=dict(odds_ratio=float(np.exp(est_i)), lo=float(np.exp(est_i - 1.96 * se_i)), hi=float(np.exp(est_i + 1.96 * se_i)),
                                 p=float(2 * norm.sf(abs(est_i / se_i)))),
                heterogeneity_p=float(chi2.sf(q, max(int(ok.sum()) - 1, 1))))


NBA_ROWS = {"H1": ("ankle", "fouled"), "H2": ("any", "steal"), "H3": ("hand", "opp_rim"), "H4": ("muscle", "drive"), "H5": ("ankle", "rebound")}


def nba_reference() -> dict:
    """The NBA test's odds ratio and interval for each hypothesis (outputs/moments/summary.json)."""
    path = OUTPUTS / "moments" / "summary.json"
    if not path.exists():
        return {}
    table = json.loads(path.read_text(encoding="utf-8"))["table"]
    out = {}
    for hid, (g, pl) in NBA_ROWS.items():
        x = next((r for r in table if r["group"] == g and r["play"] == pl), None)
        if x:
            out[hid] = dict(odds_ratio=x["odds_ratio"], lo=x["lo"], hi=x["hi"])
    return out


def built(log=print, reuse: bool = False) -> dict:
    """The build, saved to outputs/college_moments (``reuse`` reads the saved one instead of rebuilding)."""
    names = ("moments", "injuries", "injuries_strict", "runs", "listings", "background")
    if reuse and all((OUT / f"{n}.parquet").exists() for n in names) and (OUT / "quality.json").exists():
        b = {n: pd.read_parquet(OUT / f"{n}.parquet") for n in names}
        b["quality"] = json.loads((OUT / "quality.json").read_text(encoding="utf-8"))
        return b
    b = build(log=log)
    OUT.mkdir(parents=True, exist_ok=True)
    for n in names:
        b[n].to_parquet(OUT / f"{n}.parquet", index=False)
    (OUT / "quality.json").write_text(json.dumps(b["quality"], indent=1, default=float), encoding="utf-8")
    return b


def analyse(log=print, reuse: bool = False) -> dict:
    b = built(log=log, reuse=reuse)
    m, inj, inj_s, r, lst, bg = b["moments"], b["injuries"], b["injuries_strict"], b["runs"], b["listings"], b["background"]
    mp = view(m, "primary")
    groups = [ALL] + GROUPS
    plays = [k for k, _ in moments.PLAYS if k != "take_foul"] + [k for k, _ in moments.CONTEXT] + [k for k, _ in moments.SUMMARY]
    labels = dict(moments.PLAYS + moments.CONTEXT + moments.SUMMARY + EXTRA_PLAYS + MARKERS)
    labels["fouled"] = "Drew a foul"

    # matching, labelling and counts
    teams = lst.drop_duplicates("team_slug")
    named = lst[lst["group"].notna()].drop_duplicates(["season", "covers_id", "part"])
    rates = bg.groupby("next")["pattern"].agg(["mean", "sum", "size"]).rename(columns={"mean": "rate", "sum": "with_pattern", "size": "games"})
    chance = float(rates.loc["played next game", "rate"]) if "played next game" in rates.index else np.nan
    cases_main = mp[(mp["role"] == "case") & (mp["ratio"] < SHORT_GAME)]
    group_view = inj.assign(region=inj["group"], coarse=inj["group"], injury_type=np.where(
        (inj["group"] == "ankle") & inj["note"].fillna("").str.contains(r"sprain|rolled", case=False), "sprain", inj["kind"]))
    found = []
    for gid, name in groups:
        member = in_group(gid, group_view)
        ok = member & inj["evaluable"]
        rate_inj = float(inj.loc[ok & inj["usual"].ge(MIN_USUAL), "pinned"].mean()) if ok.any() else np.nan
        pinned = member & inj["pinned"]
        found.append(dict(group=gid, name=name, injuries=int(member.sum()), evaluable=int(ok.sum()), pinned=int(pinned.sum()),
                          pinned_share=float(inj.loc[ok, "pinned"].mean()) if ok.any() else np.nan,
                          beyond_chance=float(max(0.0, 1 - chance / rate_inj)) if rate_inj else np.nan,
                          note_says_left_game=float(inj.loc[pinned, "left_game_note"].mean()) if pinned.any() else np.nan,
                          note_says_left_game_not_pinned=float(inj.loc[member & ~inj["pinned"], "left_game_note"].mean())
                          if (member & ~inj["pinned"]).any() else np.nan,
                          failed_returns=int((pinned & inj["failed_return"]).sum())))
    quality = dict(
        seasons=b["quality"],
        teams=dict(covers_teams=int(len(teams)), matched=int(teams["team_id"].notna().sum())),
        listings=dict(named_injury_listings=int(len(named)), matched_to_a_player=float(named["player_id"].notna().mean()),
                      by_method=named["match"].value_counts().to_dict()),
        runs=dict(missed_game_runs=int(len(r)), labelled=r["label"].value_counts().to_dict(),
                  strict_injury_runs=int(len(inj_s)), strict_pinned=int(inj_s["pinned"].sum())),
        cases=dict(main=int(len(cases_main)), old_format=int(cases_main["old_format"].sum()),
                   failed_returns=int(cases_main["failed_return"].fillna(False).astype(bool).sum())),
        background=rates.reset_index().to_dict("records"), chance_rate=chance)

    # the plan's tests
    table = [compare(mp, g, play) for g, _ in groups for play in plays]
    q = benjamini_hochberg([x["p"] if x["play"] != "no_play" else np.nan for x in table])
    for x, qq in zip(table, q):
        x.update(q=qq, thin=x["exposed"] < MIN_EXPOSED, label=labels[x["play"]],
                 headline=bool(np.isfinite(qq) and qq < FDR and x["exposed"] >= MIN_EXPOSED and x["same_way"]))
    lookup = {(x["group"], x["play"]): x for x in table}
    nba = nba_reference()
    primary = []
    adj = holm([lookup[(g, pl)]["p"] if np.isfinite(lookup[(g, pl)]["p"]) else 1.0 for _, g, pl in PRIMARY])
    exact = {hid: exact_test(strata_table(mp, g, pl)) for hid, g, pl in PRIMARY + SECONDARY}
    adj_exact = holm([exact[hid]["p_two_sided"] for hid, _, _ in PRIMARY])
    for (hid, g, pl), a, ae in zip(PRIMARY, adj, adj_exact):
        x = lookup[(g, pl)]
        verdict = ("Replicates" if a < 0.05 and x["odds_ratio"] > 1 else
                   "Same direction, not shown" if np.isfinite(x["odds_ratio"]) and x["odds_ratio"] > 1 else
                   "Does not replicate" if np.isfinite(x["odds_ratio"]) else "Too few to test")
        primary.append(dict(hypothesis=hid, group=g, play=pl, holm_p=a, verdict=verdict, exact=exact[hid], holm_exact_p=ae,
                            **{k: x[k] for k in ("cases", "exposed", "case_share", "comparison_share", "odds_ratio", "lo", "hi", "p",
                                                 "first_half", "second_half")}))
    secondary = [dict(hypothesis=hid, exact=exact[hid], **lookup[(g, pl)]) for hid, g, pl in SECONDARY]

    # added after the results, at the review's request (labelled as such)
    hyps = PRIMARY + SECONDARY
    power_rows = []
    for hid, g, pl in hyps:
        if hid in nba:
            power_rows.append(dict(hypothesis=hid, nba_odds_ratio=nba[hid]["odds_ratio"], **power(strata_table(mp, g, pl), nba[hid]["odds_ratio"])))
    versus_nba = []
    for hid, g, pl in hyps:
        if hid not in nba:
            continue
        x = lookup[(g, pl)]
        vc = ((np.log(x["hi"]) - np.log(x["lo"])) / 3.92) ** 2
        vn = ((np.log(nba[hid]["hi"]) - np.log(nba[hid]["lo"])) / 3.92) ** 2
        z = (np.log(x["odds_ratio"]) - np.log(nba[hid]["odds_ratio"])) / np.sqrt(vc + vn)
        from scipy.stats import norm
        versus_nba.append(dict(hypothesis=hid, college=x["odds_ratio"], nba=nba[hid]["odds_ratio"], difference_p=float(2 * norm.sf(abs(z)))))
    sensitivity = {}
    for name, v in (("strict labels", view(m, "strict")), ("without returns from an injury he already had", view(m, drop_failed=True)),
                    ("without old-format games", view(m, drop_old=True)), ("all three", view(m, "strict", True, True))):
        sensitivity[name] = [dict(hypothesis=hid, **compare(v, g, pl), exact=exact_test(strata_table(v, g, pl))) for hid, g, pl in hyps]
    markers = [dict(compare(mp, g, mk), label=labels[mk]) for mk, _ in MARKERS for g in ("any", "ankle", "muscle", "hand", "knee", "head")]
    markers += [dict(compare(mp, "any", mk, case_role="pseudo"), label=labels[mk] + " (early exits with no injury)") for mk, _ in MARKERS]
    foul_split = [dict(compare(mp, g, k), label=labels[k]) for k, _ in EXTRA_PLAYS for g in ("ankle", "any")]
    combined = pooled(mp, [(g, pl) for _, g, pl in hyps])
    combined_no_h4 = pooled(mp, [(g, pl) for hid, g, pl in hyps if hid != "H4"])

    checks = {
        "null": [compare(mp, g, pl, against="null") for g, _ in groups for pl in plays],
        "stoppage": [compare(mp, g, pl, by_stoppage=True) for g, _ in groups for pl in plays],
        "other_injuries": [compare(mp, g, pl, against="other injuries") for g, _ in GROUPS for pl in plays],
        "no_injury_early_exits": [compare(mp, "any", pl, case_role="pseudo") for pl in plays],
        "windows": [compare(mp, g, pl, width=w) for g, _ in groups for pl in plays for w in WINDOWS],
        "case_definitions": [compare(mp, g, pl, short=s) for g in ("any", "ankle", "muscle", "hand") for pl in plays for s in SHORT_VARIANTS],
    }
    for rows in checks.values():
        for x in rows:
            x["label"] = labels[x["play"]]
    stoppages = {"injury exits": cases_main["stoppage"].value_counts(normalize=True).round(4).to_dict(),
                 "ordinary exits": mp.loc[mp["role"] == "exit", "stoppage"].value_counts(normalize=True).round(4).to_dict()}
    result = dict(quality=quality, groups=found, primary=primary, secondary=secondary, table=table, stoppages=stoppages, **checks,
                  added_after_results=dict(note="Not in the plan; added after the results at the review's request.", power=power_rows,
                                           versus_nba=versus_nba, sensitivity=sensitivity, markers=markers, foul_split=foul_split,
                                           pooled=combined, pooled_without_h4=combined_no_h4),
                  settings=dict(window=WINDOW, windows=list(WINDOWS), min_left=MIN_LEFT, max_margin=MAX_MARGIN, short_game=SHORT_GAME,
                                min_usual=MIN_USUAL, foul_out=FOUL_OUT, label_before=LABEL_BEFORE, label_after=LABEL_AFTER,
                                good_game=[GOOD_MINUTES, GOOD_GAME], seasons=list(SEASONS), split=SPLIT_SEASON, plan="docs/ncaa_moments_plan.md"))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "summary.json").write_text(json.dumps(result, indent=1, default=lambda v: float(v) if isinstance(v, (np.floating, np.integer)) else str(v)),
                                      encoding="utf-8")
    return result


def report(result: dict, log=print) -> None:
    q = result["quality"]
    log("Quality:")
    for s in q["seasons"]:
        log(f"  {s['season']}: {s['games_kept']} of {s['games']} games kept ({s['old_format_kept']} kept in the old format); their minutes "
            f"within 1 of the box {s['within_1_kept']:.1%} (median error {s['median_minutes_error_kept']:.2f}; all games {s['within_1_all']:.1%})")
    log(f"  Covers teams matched: {q['teams']['matched']} of {q['teams']['covers_teams']}; named-injury listings matched to a player: "
        f"{q['listings']['matched_to_a_player']:.1%} {q['listings']['by_method']}")
    log(f"  missed-game runs: {q['runs']['missed_game_runs']:,} {q['runs']['labelled']}; strict labels: {q['runs']['strict_injury_runs']} "
        f"injury runs, {q['runs']['strict_pinned']} pinned")
    log(f"  main injury exits: {q['cases']['main']} ({q['cases']['old_format']} in old-format games, {q['cases']['failed_returns']} returns "
        f"from an injury he already had)")
    for b in q["background"]:
        log(f"  pattern before: {b['next']:42s} {b['rate']:6.1%} of {b['games']:,} games")
    log("\nInjuries pinned to an injury exit:")
    for g in result["groups"]:
        log(f"  {g['name']:58s} {g['pinned']:4d} of {g['evaluable']:5d} evaluable ({g['pinned_share']:.0%}; {g['injuries']} in all), "
            f"beyond chance {g['beyond_chance']:.0%}; note says he left a game: pinned {g['note_says_left_game']:.0%} vs not "
            f"{g['note_says_left_game_not_pinned']:.0%}")
    log("\nPrimary hypotheses (plan fixed in advance), 30 s, injury exits vs the same players' ordinary exits:")
    for x in result["primary"]:
        e = x["exact"]
        log(f"  {x['hypothesis']} {x['group']:7s} {x['play']:8s} {x['case_share']:6.1%} vs {x['comparison_share']:6.1%}  OR {x['odds_ratio']:.2f} "
            f"({x['lo']:.2f}-{x['hi']:.2f}) p {x['p']:.4f} Holm {x['holm_p']:.4f}  exposed {x['exposed']}/{x['cases']} (expected "
            f"{e['expected']:.1f}; exact p {e['p_two_sided']:.4f}, Holm {x['holm_exact_p']:.4f})  halves {x['first_half']:.2f}/"
            f"{x['second_half']:.2f}  -> {x['verdict']}")
    for x in result["secondary"]:
        log(f"  {x['hypothesis']} {x['group']:7s} {x['play']:8s} {x['case_share']:6.1%} vs {x['comparison_share']:6.1%}  OR {x['odds_ratio']:.2f} "
            f"({x['lo']:.2f}-{x['hi']:.2f}) p {x['p']:.4f}  exposed {x['exposed']}/{x['cases']}")
    a = result["added_after_results"]
    log("\nAdded after the results (not in the plan):")
    for x in a["power"]:
        log(f"  power of {x['hypothesis']} at the NBA odds ratio {x['nba_odds_ratio']:.2f}: {x['at_0.05']:.0%} at 0.05, {x['at_0.0125']:.0%} at 0.0125")
    for x in a["versus_nba"]:
        log(f"  {x['hypothesis']}: college {x['college']:.2f} vs NBA {x['nba']:.2f}, difference p {x['difference_p']:.3f}")
    for name, rows in a["sensitivity"].items():
        log(f"  {name}: " + "; ".join(f"{x['hypothesis']} {x['odds_ratio']:.2f} ({x['lo']:.2f}-{x['hi']:.2f}) {x['exposed']}/{x['cases']}"
                                     for x in rows))
    for x in a["markers"] + a["foul_split"]:
        log(f"  {x['label']:70s} {x['group']:6s} {x['case_share']:6.1%} vs {x['comparison_share']:6.1%}  OR {x['odds_ratio']:.2f} "
            f"({x['lo']:.2f}-{x['hi']:.2f})")
    for key in ("pooled", "pooled_without_h4"):
        c = a[key]["correlated"]
        log(f"  {key}: OR {c['odds_ratio']:.2f} ({c['lo']:.2f}-{c['hi']:.2f}) p {c['p']:.4f}; independent {a[key]['independent']['odds_ratio']:.2f}; "
            f"heterogeneity p {a[key]['heterogeneity_p']:.2f}")


def export(log=print) -> dict:
    result = analyse(log=log)
    report(result, log=log)
    return {x["hypothesis"]: x["verdict"] for x in result["primary"]}
