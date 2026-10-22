"""What an injury does to a college player's career: aftermath.py's study for Division I men's basketball, 2019-20 to
2025-26.

The injuries are the college profiles' Covers listings (outputs/profiles/college.json) that cost the team 4 or more
games, every torn ACL, Achilles and meniscus the notes name, and every concussion. Each player is followed in ESPN's box
scores, whose athlete ids hold across seasons and transfers (the NCAA's change every season); a listing is matched to its
player by season, team and name. The absence is the run of team games they missed around the listing, from their last
game before it to the next game they played.

Each injured player is set against the ten players most like them the day they were hurt: seasons already played in
Division I (counted from 2019-20), minutes, production per 36 minutes, the share of their team's games they played, and
how often their team won. The outcomes are aftermath.py's: time out, coming back the same (the year before against the
first and second years back), the year back (games played, listed hurt again), and what came after (still in Division I
the next season, at another school, and in the NBA).

Two limits. Covers' page was saved on 2 to 76 days a season, so injuries in thinly saved seasons are missing: some
matched players were hurt too, and "listed hurt again" counts only years in seasons saved on 30 or more days. And there
is no class year, so a senior who graduates looks like a player who stopped; matching on seasons played handles part of
that, and nothing handles the rest.

Associations in observational data: who gets hurt, and who comes back, isn't random.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from . import aftermath as A
from . import college, sources
from .paths import OUTPUTS

OUT = OUTPUTS / "college_aftermath"
PROFILES = OUTPUTS / "profiles"
LISTINGS = OUTPUTS / "college_moments" / "listings_matched.parquet"
TEAM_GAMES = 15                # a team with fewer games in a season in the box scores is outside Division I
INCLUDE_GAMES = 4              # games missed that make an injury worth following (10 of the NBA's 82 is about 4 of 32)
MIN_GAMES, MIN_PRE_MINUTES, MIN_POST_MINUTES = 8, 120, 100
SAME_GAME_GAP = 10             # days: a first missed game this soon after the last game played follows from that game
WELL_SAVED = 30                # days Covers' page was saved in a season for its listings to be fairly complete
NBA_SEASONS = 2                # seasons after the injury's season that a player needs to have had to reach the NBA
FIRST_ROOKIES, CAREER_GAP = 2021, 3   # the NBA debuts looked for, and how many seasons before them the college career may end
MATCH = ["seasons", "mpg", "production36", "played_share", "won"]
METRICS = [m for m in A.METRICS if m[0] not in ("rim36", "dunk36")]   # no play-by-play here
OUTCOMES = [
    ("played_share", "Share of the team’s games played in the year back"),
    ("listed_again", "Listed hurt again in the year back"),
    ("next_season", "Still in Division I the next season"),
    ("moved", "At another school the next season, of those still playing"),
    ("nba", "Reached the NBA"),
]
SERIOUS = {"acl", "achilles", "meniscus"}
# key, name, the notes' diagnoses, the profiles' kinds; a diagnosis decides first
GROUPS = [
    ("acl", "Torn ACL", {"Torn ACL", "ACL injury"}, {"acl"}),
    ("achilles", "Torn Achilles", {"Achilles tear"}, {"achilles"}),
    ("meniscus", "Torn meniscus", {"Torn meniscus"}, {"meniscus"}),
    ("fracture", "Broken bone", {"Fracture", "Stress fracture"}, {"hand_fracture", "foot_fracture"}),
    ("concussion", "Concussion", {"Concussion"}, {"concussion"}),
    ("knee", "Other knee injury", {"MCL injury", "Torn patellar tendon"}, {"mcl", "region:knee"}),
    ("ankle", "Ankle injury", {"High ankle sprain"}, {"ankle_sprain", "region:ankle"}),
    ("foot", "Foot injury", set(), {"region:foot"}),
    ("muscle", "Muscle strain", set(), {"hamstring", "calf", "groin", "region:hamstring", "region:calf", "region:groin",
                                        "region:thigh"}),
    ("back", "Back or hip injury", set(), {"region:back", "region:hip"}),
    ("upper", "Shoulder, arm or hand injury", set(), {"region:shoulder", "region:hand", "region:arm", "region:elbow"}),
]
CASES = {"acl", "achilles"}


def group_of(dx: str | None, kind: str | None) -> str | None:
    for key, _, labels, kinds in GROUPS:
        if dx in labels:
            return key
    return next((key for key, _, _, kinds in GROUPS if kind in kinds), None)


def season_of(day) -> int:
    day = pd.Timestamp(day)
    return day.year + 1 if day.month >= 7 else day.year


# --- the games ----------------------------------------------------------------------------------------------------------

def box() -> pd.DataFrame:
    """ESPN's box scores for every season with saved injury pages, Division I teams only."""
    cols = ["season", "season_type", "game_id", "game_date", "athlete_id", "athlete_display_name", "team_id", "minutes", "points",
            "rebounds", "assists", "steals", "blocks", "turnovers", "field_goals_attempted", "free_throws_attempted", "starter",
            "team_winner"]
    b = pd.concat([pd.read_parquet(sources.season_path("espn_mbb_player_box", s), columns=cols) for s in sources.COLLEGE_SEASONS],
                  ignore_index=True)
    b = b.dropna(subset=["athlete_id", "team_id", "game_id"]).astype({"athlete_id": "int64", "team_id": "int64", "game_id": "int64"})
    b["game_date"] = pd.to_datetime(b["game_date"])
    games = b.drop_duplicates(["season", "team_id", "game_id"]).groupby(["season", "team_id"]).size()
    d1 = games[games >= TEAM_GAMES].index
    b = b.set_index(["season", "team_id"]).loc[lambda x: x.index.isin(d1)].reset_index()
    b["key"] = b["athlete_display_name"].map(college._person)
    return b


def game_log(b: pd.DataFrame) -> pd.DataFrame:
    """The box scores as aftermath.Logs reads them: for each player's team each season (the one they played for most),
    a row for every game, played or not, with the line of the games they played."""
    played = b[b["minutes"].fillna(0) > 0]
    team = played.groupby(["athlete_id", "season"])["team_id"].agg(lambda s: s.mode().iloc[0]).reset_index()
    games = b.drop_duplicates(["season", "team_id", "game_id"])[["season", "team_id", "game_id", "game_date", "season_type"]]
    rows = team.merge(games, on=["season", "team_id"])
    line = played[["athlete_id", "game_id", "minutes", "points", "rebounds", "assists", "steals", "blocks", "turnovers",
                   "field_goals_attempted", "free_throws_attempted", "starter"]]
    rows = rows.merge(line, on=["athlete_id", "game_id"], how="left")
    return pd.DataFrame(dict(
        player_id=rows["athlete_id"], game_date=rows["game_date"], season=rows["season"], team=rows["team_id"],
        season_type=np.where(rows["season_type"] == 3, "playoffs", "regular-season"),
        status=np.where(rows["minutes"].notna(), "played", "dnp"), minutes=rows["minutes"], pts=rows["points"],
        reb=rows["rebounds"], ast=rows["assists"], stl=rows["steals"], blk=rows["blocks"], tov=rows["turnovers"],
        fga=rows["field_goals_attempted"], fta=rows["free_throws_attempted"], starter=rows["starter"], rim_fga=np.nan,
        dunk_fga=np.nan))


class Teams:
    """Each team's games and wins, for how often a player's team won before a day."""

    def __init__(self, b: pd.DataFrame):
        g = b.drop_duplicates(["team_id", "game_id"]).sort_values("game_date")
        self.games = {t: (x["game_date"].to_numpy(), np.r_[0, x["team_winner"].fillna(False).astype(float).cumsum().to_numpy()])
                      for t, x in g.groupby("team_id")}

    def won(self, team, start, end) -> float:
        dates, wins = self.games.get(team, (np.array([], dtype="datetime64[ns]"), np.zeros(1)))
        i, j = np.searchsorted(dates, np.datetime64(start)), np.searchsorted(dates, np.datetime64(end))
        return (wins[j] - wins[i]) / (j - i) if j > i else np.nan


# --- the injuries -------------------------------------------------------------------------------------------------------

def athletes(b: pd.DataFrame) -> dict:
    """(Covers id, season) -> ESPN athlete id: the listing's team that season, and the one player of that name on it."""
    lst = pd.read_parquet(LISTINGS, columns=["covers_id", "season", "team_id", "player_slug", "group"])
    lst = lst[lst["group"].notna() & lst["team_id"].notna()]
    roster = b.drop_duplicates(["season", "team_id", "athlete_id"])
    one = roster.groupby(["season", "team_id", "key"])["athlete_id"].agg(lambda s: s.iloc[0] if s.nunique() == 1 else -1).to_dict()
    lst = lst.assign(athlete=[one.get((s, int(t), college._person(p)), -1) for s, t, p in
                              zip(lst["season"], lst["team_id"], lst["player_slug"])])
    lst = lst[lst["athlete"] > 0]
    return lst.groupby(["covers_id", "season"])["athlete"].agg(lambda s: int(s.mode().iloc[0])).to_dict(), \
        lst.groupby(["covers_id", "season"])["team_id"].agg(lambda s: int(s.mode().iloc[0])).to_dict()


def episodes(logs: A.Logs, people: list, of: dict, team_of: dict, schedule: dict) -> pd.DataFrame:
    """One row per absence worth following: the player, their last game before it, when they were hurt, the next game
    they played, what it was and the team games it cost that season. ``of``/``team_of``: athletes(); ``schedule``:
    (season, team) -> the team's game days."""
    rows = []
    for p in people:
        absences = {}
        for e in p["inj"]:
            start, end, season = pd.Timestamp(e[0]), pd.Timestamp(e[1]), e[2]
            a, team = of.get((p["id"], season)), team_of.get((p["id"], season))
            if a is None or team is None:
                continue
            days = schedule.get((season, team), np.array([], dtype="datetime64[ns]"))
            mine = logs.played(a)[0]
            near = days[(days >= np.datetime64(start - pd.Timedelta(days=3))) & (days <= np.datetime64(end + pd.Timedelta(days=3)))]
            missed = near[~np.isin(near, mine)]
            if not len(missed):
                continue   # they played through the days it was listed
            first = missed[0]
            before, after = mine[mine < first], mine[mine > first]
            if not len(before):
                continue   # no game before it to start the clock from
            back = after[0] if len(after) else None
            gone = days[(days >= first) & ((days < back) if back is not None else True)]
            absences.setdefault((a, before[-1]), []).append(dict(
                e=e, first=first, games=len(gone), season_over=back is None or season_of(back) > season,
                group=group_of(e[10], e[13]), back=back))
        for (a, last), parts in absences.items():
            main = max(parts, key=lambda x: (x["group"] is not None, x["games"]))
            e, group = main["e"], main["group"]
            if not (main["games"] >= INCLUDE_GAMES or group in SERIOUS or group == "concussion"):
                continue
            last = pd.Timestamp(last)
            gap = (pd.Timestamp(main["first"]) - last).days
            rows.append(dict(player_id=a, covers_id=p["id"], player=p["n"], season=e[2], first_listed=parts[0]["e"][0], part=e[3],
                             coarse=e[4], dx=e[10], kind=e[13], group=group, games_missed=main["games"],
                             season_over=main["season_over"], last_game=last,
                             hurt=last if gap <= SAME_GAME_GAP else pd.NaT,
                             back=pd.Timestamp(main["back"]) if main["back"] is not None else pd.NaT,
                             two_injuries=len({x["e"][4] for x in parts if x["e"][4] != "other" and x["games"] >= INCLUDE_GAMES}) > 1))
    columns = ["player_id", "covers_id", "player", "season", "first_listed", "part", "coarse", "dx", "kind", "group", "games_missed",
               "season_over", "last_game", "hurt", "back", "two_injuries"]
    return pd.DataFrame(rows, columns=columns).sort_values(["first_listed", "player_id"]).reset_index(drop=True)


def nba_debuts(b: pd.DataFrame) -> dict:
    """ESPN athlete id -> their NBA debut season, by profiles.college_links' rules: a debut since 2020-21 under a name no
    other debut shares, and one college career of that name ending one to three seasons before it, with nobody of that
    name in college in that last season or after."""
    pro = json.loads((PROFILES / "nba.json").read_text(encoding="utf-8"))
    first = {p["id"]: min(s for s, _ in p["tm"]) for p in pro["players"]}
    key = {p["id"]: college._person(p["n"]) for p in pro["players"]}
    rookies = {pid: f for pid, f in first.items() if f >= FIRST_ROOKIES}
    taken = pd.Series([key[pid] for pid in rookies]).value_counts()
    played = b[b["minutes"].fillna(0) > 0]
    span = played.groupby(["key", "athlete_id"])["season"].agg(["min", "max"]).reset_index()
    by_key = {k: g for k, g in span.groupby("key")}
    out = {}
    for pid, f in rookies.items():
        g = by_key.get(key[pid])
        if g is None or taken[key[pid]] != 1:
            continue
        mine = g[g["max"].between(f - CAREER_GAP, f - 1)]
        if len(mine) != 1 or (g.drop(mine.index)["max"] >= mine["max"].iloc[0]).any():
            continue
        out[int(mine["athlete_id"].iloc[0])] = f
    return out


# --- following them -----------------------------------------------------------------------------------------------------

def everyone_at(logs: A.Logs, teams: Teams, seasons: dict, day) -> pd.DataFrame:
    """Every player playing around ``day`` with the games to judge by in the year before it, as they looked then.
    ``seasons``: athlete id -> the seasons they played, sorted."""
    start = day - A.YEAR
    games, totals = logs.totals(start, day)
    m = A.metrics(games, totals)
    m["player_id"], m["at"] = logs.ids, np.arange(len(logs.ids))
    m["played_share"] = games / np.maximum(logs.rostered(start, day), np.maximum(games, 1))
    keep = ((games >= MIN_GAMES) & (m["minutes"].to_numpy() >= MIN_PRE_MINUTES)
            & (logs.appeared(day - A.ACTIVE, day + pd.Timedelta(days=1)) > 0))
    m = m[keep].reset_index(drop=True)
    now = season_of(day)
    m["seasons"] = [int(np.searchsorted(seasons[a], now)) for a in m["player_id"]]
    m["won"] = [teams.won(logs.team_at(a, day), start, day) for a in m["player_id"]]
    return m[m["won"].notna()].reset_index(drop=True)


def follow(logs: A.Logs, teams: Teams, seasons: dict, teams_by_season: dict, ep: pd.DataFrame, listed: dict, saved: dict,
           debuts: dict, end: pd.Timestamp) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Each injury with the player before and after it, and the same for their matched players; and the placebo.
    ``teams_by_season``: (athlete, season) -> team; ``listed``: athlete -> the days a new injury of theirs was first
    listed; ``saved``: season -> days the page was saved; ``debuts``: nba_debuts()."""
    last_season = season_of(end) if 4 <= end.month <= 6 else season_of(end) - 1   # the last season played to its end
    rng = np.random.default_rng(A.SEED)
    out, placebo = [], []
    for e in ep.itertuples(index=False):
        L, R = e.last_game, e.back
        pool = everyone_at(logs, teams, seasons, L)
        me = pool[pool["player_id"] == e.player_id]
        if me.empty:
            continue
        me = me.iloc[0]
        pool = pool[pool["player_id"] != e.player_id].reset_index(drop=True)
        pick = A.nearest(me, pool, match=MATCH)
        matched = pool.iloc[pick]
        row = dict(e._asdict(), **{f"pre_{c}": me[c] for c in me.index if c not in ("player_id", "at")},
                   **{f"matched_{c}": matched[c].mean() for c in MATCH})
        row.update(A.came_back(logs, me, pool, R, end, match=MATCH, enough=(MIN_GAMES, MIN_POST_MINUTES)))
        stand_ins = []
        for i in rng.choice(len(pool), min(A.STAND_INS, len(pool)), replace=False):
            others = pool.drop(i).reset_index(drop=True)
            stand_ins.append((i, others, A.nearest(pool.iloc[i], others, match=MATCH), dict(
                player_id=pool.at[i, "player_id"], injury=len(out),
                **A.came_back(logs, pool.iloc[i], others, R, end, years=(1,), match=MATCH, enough=(MIN_GAMES, MIN_POST_MINUTES)))))
        ids, at = np.r_[e.player_id, pool["player_id"]], np.r_[me["at"], pool["at"]]
        outcomes = {}
        if pd.notna(R) and R + A.YEAR <= end:   # the full year back
            games, _ = logs.totals(R, R + A.YEAR, at)
            rostered = logs.rostered(R, R + A.YEAR, at)
            on = rostered > 0
            outcomes["played_share"] = (games / np.maximum(rostered, 1), on)
            if all(saved.get(s, 0) >= WELL_SAVED for s in {season_of(R), season_of(R + A.YEAR)}):
                again = np.array([float(((d >= np.datetime64(R)) & (d < np.datetime64(R + A.YEAR))).any()) for d in
                                  (listed.get(a, np.array([], dtype="datetime64[ns]")) for a in ids)])
                outcomes["listed_again"] = (again, on)
        if e.season + 1 <= last_season:   # the season after the injury's
            now = np.array([teams_by_season.get((a, e.season)) for a in ids], dtype=object)
            nxt = np.array([teams_by_season.get((a, e.season + 1)) for a in ids], dtype=object)
            playing = np.array([t is not None for t in nxt])
            outcomes["next_season"] = (playing.astype(float), np.ones(len(ids), dtype=bool))
            outcomes["moved"] = (np.array([float(n != c) if n is not None and c is not None else np.nan for n, c in zip(nxt, now)]), playing)
        if e.season + NBA_SEASONS <= last_season:
            outcomes["nba"] = (np.array([float(a in debuts) for a in ids]), np.ones(len(ids), dtype=bool))
        for k, (v, use) in outcomes.items():
            row[k], row[f"matched_{k}"] = (v[0] if use[0] else np.nan), A.corrected(me, pool, pick, v[1:], use[1:], match=MATCH)
            for i, others, near, t in stand_ins:
                if use[1 + i] and np.isfinite(v[1 + i]):
                    t[k] = v[1 + i]
                    t[f"matched_{k}"] = A.corrected(pool.iloc[i], others, near, np.delete(v[1:], i), np.delete(use[1:], i), match=MATCH)
        out.append(row)
        placebo += [t for *_, t in stand_ins]
    return pd.DataFrame(out), pd.DataFrame(placebo)


# --- summaries ----------------------------------------------------------------------------------------------------------

def summarize(f: pd.DataFrame, end: pd.Timestamp) -> list[dict]:
    out = []
    one = f[~f["two_injuries"]]
    for key, name, x in [("all", "Every injury followed", f)] + [(k, n, one[one["group"] == k]) for k, n, *_ in GROUPS]:
        if len(x) < A.MIN_SHOWN:
            continue
        days = np.where(x["back"].notna(), (x["back"] - x["hurt"]).dt.days, (end - x["hurt"]).dt.days)
        row = dict(key=key, name=name, injuries=len(x), players=x["player_id"].nunique(), not_back=int(x["back"].isna().sum()),
                   season_over=float(x["season_over"].mean()),
                   games_missed=dict(median=x["games_missed"].median(), quartiles=x["games_missed"].quantile([0.25, 0.75]).tolist()),
                   **A.time_to_return(days, x["back"].notna()))
        for n in (1, 2):
            row[f"year_{n}"] = A.effects(x, f"y{n}_", measures=METRICS)
        row["outcomes"] = A.differences(x, OUTCOMES)
        if key in CASES:
            row["cases"] = [dict(covers_id=c.covers_id, player=c.player, listed=c.first_listed, hurt=c.hurt, back=c.back,
                                 games_missed=c.games_missed, mpg_before=c.pre_mpg, mpg_after=getattr(c, "y1_mpg", None),
                                 production_before=c.pre_production36, production_after=getattr(c, "y1_production36", None),
                                 nba=getattr(c, "nba", None))
                            for c in x.sort_values("first_listed").itertuples()]
        out.append(row)
    return out


# --- run ----------------------------------------------------------------------------------------------------------------

def export(log=print) -> dict:
    b = box()
    logs = A.Logs(game_log(b))
    end = b["game_date"].max()
    teams = Teams(b)
    played = b[b["minutes"].fillna(0) > 0]
    seasons = {a: np.sort(g.unique()) for a, g in played.groupby("athlete_id")["season"]}
    teams_by_season = played.groupby(["athlete_id", "season"])["team_id"].agg(lambda s: s.mode().iloc[0]).to_dict()
    schedule = {k: np.sort(g["game_date"].unique()) for k, g in b.drop_duplicates(["game_id", "team_id"]).groupby(["season", "team_id"])}
    of, team_of = athletes(b)
    col = json.loads((PROFILES / "college.json").read_text(encoding="utf-8"))
    saved = {s["season"]: s["days"] for s in col["saved"]}
    listed = {}
    for p in col["people"]:
        for e in p["inj"]:
            a = of.get((p["id"], e[2]))
            if a:
                listed.setdefault(a, []).append(np.datetime64(e[0]))
    listed = {a: np.sort(np.array(d, dtype="datetime64[ns]")) for a, d in listed.items()}
    ep = episodes(logs, col["people"], of, team_of, schedule)
    debuts = nba_debuts(b)
    log(f"  {len(ep)} college injuries to follow; {len(debuts)} college careers found in the NBA")
    f, stand_ins = follow(logs, teams, seasons, teams_by_season, ep, listed, saved, debuts, end)
    log(f"  {len(f)} followed (the rest lacked the games before them), {int(f['two_injuries'].sum())} absences with two injuries")
    summary = dict(end_of_data=end, injuries=len(ep), followed=len(f), two_injuries=int(f["two_injuries"].sum()),
                   nba_links=len(debuts), saved=saved, balance=A.balance(f, MATCH),
                   placebo=dict(came_back=A.effects(stand_ins, "y1_", measures=METRICS), outcomes=A.differences(stand_ins, OUTCOMES)),
                   groups=summarize(f, end))
    for r in summary["balance"]:
        log(f"  matched on {r['measure']}: {r['injured']:.3f} against {r['matched']:.3f} "
            f"(standardized difference {r['standardized_difference']:+.3f})")
    for r in summary["placebo"]["came_back"] + summary["placebo"]["outcomes"]:
        log(f"  placebo, {r.get('metric') or r['outcome']}: {r.get('effect', r.get('difference')):+.3f} ({r['lo']:+.3f} to {r['hi']:+.3f})")
    OUT.mkdir(parents=True, exist_ok=True)
    f.to_parquet(OUT / "injuries.parquet")   # every injury followed, and the placebo's players, for checking by eye
    stand_ins.to_parquet(OUT / "placebo.parquet")
    (OUT / "summary.json").write_text(json.dumps(A.plain(summary), indent=1), encoding="utf-8")
    for g in summary["groups"]:
        y1 = {r["metric"]: r for r in g["year_1"]}
        line = f"  {g['name']}: {g['injuries']} injuries, median {g['games_missed']['median']:.0f} games out"
        if g["median_days"] is not None:
            line += f", half back in {g['median_days']:.0f} days"
        if "mpg" in y1:
            r = y1["mpg"]
            line += f"; minutes {r['effect']:+.2f} ({r['lo']:+.2f} to {r['hi']:+.2f}) in year one, n={r['injuries']}"
        log(line)
    return summary
