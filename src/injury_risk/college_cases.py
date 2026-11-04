"""College men's injury cases from the daily SCACCHoops snapshots, with cases.py's rules on ESPN's Division I box scores.

SCACCHoops lists players by conference with a status and a body part but no dates, so a listing's time is when the daily
job saw it. Each listing is matched to its ESPN team (by name, with hand-checked aliases) and to the one player of that
name on the team's box scores this season. ESPN lists the whole roster in a college box score, so a player who sits out
still has a row. At each of the team's games, the listing in effect is the player's on the latest snapshot from that day
or the three before it. Then the NBA's rules apply (labels.classify_absences, labels.find_onsets): a case opens at the
first game missed in a run of injury absences and ends with the run; the return is the next game played.

One difference: a college box score doesn't say why a player sat out, so a missed game without a listing is unknown and
can extend a run, where in the NBA a coach's decision ends it. A player healthy again but kept on the bench keeps their
case open until they play.
"""
from __future__ import annotations

import difflib
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from . import cases, college, labels, sources
from .paths import OUTPUTS

SOURCE = "ncaa-men-scac"
LISTINGS = OUTPUTS / "college_moments" / "listings_matched.parquet"   # the saved Covers pages, for the historical check
STUDY = OUTPUTS / "college_aftermath" / "injuries.parquet"
SEASON = 2027                 # 2026-27
STALE_DAYS = 3                # a snapshot more days than this before a game says nothing about it
TEAM_GAMES = 15               # fewer games in a season's box scores: a visitor from outside Division I (college_aftermath)
STATUS = {"out": "Out", "out_for_season": "Out", "questionable": "Questionable", "day_to_day": "Questionable",
          "probable": "Probable", "available": "Available", "unknown": "Unknown"}
MISSING = ("out", "out_for_season")
# SCACCHoops team names ESPN writes differently, checked by hand against every name SCACCHoops has shown (November 4, 2026)
ALIASES = {"Appalachian State": 2026, "CS-Bakersfield": 2934, "Central Florida": 2116, "Citadel": 2643,
           "College of Charleston": 232, "Connecticut": 41, "Miami (Ohio)": 193, "Southeastern Louisiana": 2545,
           "Tarleton": 2627, "Texas-Arlington": 250, "USC Upstate": 2908}
BOX = ["season", "game_id", "game_date", "athlete_id", "athlete_display_name", "team_id", "team_location",
       "team_short_display_name", "team_abbreviation", "team_display_name", "minutes"]


def _norm(text) -> str:
    text = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", text.replace("&", "and").replace("'", "")).strip()


def _words(name) -> list[str]:
    words = _norm(name).replace(".", "").split()
    while len(words) > 1 and words[-1] in college.SUFFIXES:
        words.pop()
    return words


def snapshots(archive: Path, source: str = SOURCE) -> tuple[pd.DataFrame, list[str]]:
    """Every distinct snapshot in the archive as one row per listing, and the times of all of them (one can list no one).
    A failed collection keeps the last good snapshot, so a snapshot is known by when it was observed."""
    seen = {}
    for path in sorted(archive.rglob("*.json")):
        snap = json.loads(path.read_text(encoding="utf-8"))["sources"].get(source, {}).get("snapshot")
        if snap:
            seen.setdefault(snap["observed_at"], snap)
    cols = ["observed_at", "conference", "team", "player", "status", "category", "region", "injury_type"]
    rows = pd.DataFrame([dict(observed_at=k, **{c: r[c] for c in cols[1:]}) for k, s in seen.items() for r in s["rows"]], columns=cols)
    return rows, sorted(seen)


def season_box(season: int = SEASON, refresh: bool = True) -> pd.DataFrame:
    """ESPN's box scores for this season (refreshed) and the last (for telling Division I teams from their visitors)."""
    if refresh:
        got = sources.fetch(seasons=(season,), kinds=["espn_mbb_player_box"], force=True)
        got += sources.fetch(seasons=(season - 1,), kinds=["espn_mbb_player_box"])
        for r in got:
            if r["status"] not in ("downloaded", "cached"):
                raise RuntimeError(f"could not download {r['kind']} for {r['season']}: {r['status']}")
    b = pd.concat([pd.read_parquet(sources.season_path("espn_mbb_player_box", s), columns=BOX) for s in (season - 1, season)],
                  ignore_index=True)
    b = b.dropna(subset=["athlete_id", "team_id", "game_id"]).astype({"athlete_id": "int64", "team_id": "int64", "game_id": "int64"})
    b["game_date"] = pd.to_datetime(b["game_date"])
    games = b.drop_duplicates(["season", "team_id", "game_id"]).groupby(["season", "team_id"]).size()
    b.attrs["division_one"] = {int(t) for (_, t), n in games.items() if n >= TEAM_GAMES}
    return b


def team_ids(names, b: pd.DataFrame) -> dict:
    """SCACCHoops team name -> ESPN team id: the hand-checked aliases, else the one Division I team with that name."""
    teams = b[b["team_id"].isin(b.attrs["division_one"])].drop_duplicates("team_id")
    index = {}
    for col in ("team_location", "team_short_display_name", "team_abbreviation", "team_display_name"):
        for v, t in zip(teams[col], teams["team_id"]):
            index.setdefault(_norm(v), set()).add(int(t))
    out = {}
    for n in names:
        hit = index.get(_norm(n), set())
        tid = ALIASES.get(n, next(iter(hit)) if len(hit) == 1 else None)
        if tid is not None:
            out[n] = tid
    return out


def match_players(listings: pd.DataFrame, b: pd.DataFrame, season: int = SEASON) -> pd.DataFrame:
    """Add team_id (unless the listings carry it), player_id (ESPN's athlete id) and how they were matched: the one player
    of that name on the team's box scores this season, else the one with that last name and first initial, else a close
    spelling (both reviewed)."""
    if "team_id" in listings:
        lst = listings.astype({"team_id": "Int64"})
    else:
        lst = listings.assign(team_id=listings["team"].map(team_ids(set(listings["team"]), b)).astype("Int64"))
    roster = b[b["season"] == season].drop_duplicates(["team_id", "athlete_id"])
    roster = roster.assign(key=roster["athlete_display_name"].map(college._person))
    by_key = roster.groupby(["team_id", "key"])["athlete_id"].agg(lambda s: s.iloc[0] if s.nunique() == 1 else -1).to_dict()
    pool = {t: list(zip(d["athlete_display_name"].map(_words), d["athlete_id"], d["key"])) for t, d in roster.groupby("team_id")}
    before = b[b["season"] == season - 1]
    last_year = set(zip(before["team_id"], before["athlete_display_name"].map(college._person)))
    ids, how = [], []
    for t, name in zip(lst["team_id"], lst["player"]):
        pid, m = None, "no team"
        if not pd.isna(t) and int(t) not in pool:
            m = "team has no game yet"
        elif not pd.isna(t):
            # not in this season's box scores: on the team's last season (an old listing, or a player not dressing), or not
            m = "on the team's box scores last season only" if (int(t), college._person(name)) in last_year else "not found"
            p = by_key.get((int(t), college._person(name)))
            words = _words(name)
            same = {a for w, a, _ in pool.get(int(t), []) if w and words and w[-1] == words[-1] and w[0][:1] == words[0][:1]}
            if p == -1:
                m = "two players of that name"
            elif p is not None:
                pid, m = p, "name"
            elif len(same) == 1:
                pid, m = same.pop(), "last_initial"
            elif pool.get(int(t)):
                score, a = max((difflib.SequenceMatcher(None, college._person(name), k).ratio(), a) for _, a, k in pool[int(t)])
                if score >= 0.85:
                    pid, m = a, "fuzzy"
        ids.append(pid)
        how.append(m)
    return lst.assign(player_id=pd.array(ids, dtype="Int64"), match=how)


def player_games(b: pd.DataFrame, season: int = SEASON) -> pd.DataFrame:
    """labels' player games: a row for every game of each Division I player's team this season (the team they were in
    the box scores of most), played or not."""
    s = b[(b["season"] == season) & b["team_id"].isin(b.attrs["division_one"])]
    team = s.groupby("athlete_id")["team_id"].agg(lambda x: x.mode().iloc[0]).rename("team_id").reset_index()
    rows = team.merge(s.drop_duplicates(["team_id", "game_id"])[["team_id", "game_id", "game_date"]], on="team_id")
    played = s.loc[s["minutes"].fillna(0) > 0, ["athlete_id", "game_id"]].drop_duplicates().assign(on=True)
    rows = rows.merge(played, on=["athlete_id", "game_id"], how="left")
    name = s.drop_duplicates("athlete_id", keep="last").set_index("athlete_id")["athlete_display_name"]
    pg = pd.DataFrame(dict(game_id=rows["game_id"], game_date=rows["game_date"], season=season, team=rows["team_id"],
                           player_id=rows["athlete_id"], status=np.where(rows["on"].notna(), "played", "dnp"), comment="",
                           name=rows["athlete_id"].map(name)))
    return pg.sort_values(["player_id", "game_date", "game_id"]).reset_index(drop=True)


def game_entries(matched: pd.DataFrame, times: list[str], pg: pd.DataFrame) -> pd.DataFrame:
    """labels' report entries: at each team game, the player's listing on the latest snapshot from the game's day or
    the STALE_DAYS before it. A game with no snapshot that recent has no entries."""
    if not times:
        return pd.DataFrame(columns=["game_date", "team", "player_id", "status", "reason", "reason_class", "region",
                                     "injury_type", "same_day", "observed_at"])
    snaps = pd.DataFrame(dict(observed_at=times, day=pd.to_datetime([cases.eastern_day(t) for t in times]).astype("datetime64[ns]")))
    snaps = snaps.sort_values("observed_at").drop_duplicates("day", keep="last").sort_values("day")
    g = pg[["team", "game_date"]].drop_duplicates().astype({"game_date": "datetime64[ns]"}).sort_values("game_date")
    g = pd.merge_asof(g, snaps, left_on="game_date", right_on="day", direction="backward",
                      tolerance=pd.Timedelta(days=STALE_DAYS)).dropna(subset=["observed_at"])
    m = matched.dropna(subset=["player_id"]).astype({"player_id": "int64", "team_id": "int64"})
    e = g.merge(m.drop(columns="team"), left_on=["team", "observed_at"], right_on=["team_id", "observed_at"])
    e = e.drop_duplicates(["game_date", "team", "player_id"])
    return pd.DataFrame(dict(game_date=e["game_date"].dt.strftime("%Y-%m-%d"), team=e["team"], player_id=e["player_id"],
                             status=e["status"].map(STATUS).fillna("Unknown"), reason=None, reason_class=e["category"],
                             region=e["region"], injury_type=e["injury_type"], same_day=e["day"] == e["game_date"],
                             observed_at=e["observed_at"]))


def build(listing_rows: pd.DataFrame, times: list[str], b: pd.DataFrame, now: datetime, season: int = SEASON) -> dict:
    """The season's college cases, the players listed out who haven't missed a game yet, and what needs review."""
    matched = match_players(listing_rows, b, season)
    pg = player_games(b, season)
    entries = game_entries(matched, times, pg)
    pg = labels.classify_absences(pg, entries.drop(columns="observed_at"))
    onsets = labels.find_onsets(pg)
    coverage = pd.Timestamp(cases.eastern_day(times[0])) if times else None
    box_through = pg.loc[pg["status"] == "played", "game_date"].max()
    names = pg.drop_duplicates("player_id", keep="last").set_index("player_id")["name"]
    team_name = b.drop_duplicates("team_id", keep="last").set_index("team_id")["team_location"]
    latest = matched[matched["observed_at"] == times[-1]] if times else matched.iloc[:0]
    listed = {int(p): x.iloc[0] for p, x in latest.dropna(subset=["player_id"]).groupby("player_id")}
    seen = matched.dropna(subset=["player_id"]).astype({"player_id": "int64"})
    seen = seen.assign(day=pd.to_datetime([cases.eastern_day(t) for t in seen["observed_at"]]))
    by_player = {pid: (d["game_date"].to_numpy(), d["absence"].to_numpy()) for pid, d in pg.groupby("player_id")}
    conference = matched.dropna(subset=["team_id"]).drop_duplicates("team_id", keep="last").set_index("team_id")["conference"]

    out, open_players = [], set()
    for o in onsets.itertuples(index=False):
        dates, absence = by_player[o.player_id]
        start = pd.Timestamp(cases.run_start(dates, absence, o.onset_date))
        after = dates > np.datetime64(o.end_date)
        over = bool(after.any())
        played = dates[after & (absence == "played")]
        back = pd.Timestamp(played[0]) if len(played) else None
        games = entries[(entries["player_id"] == o.player_id) & (entries["game_date"] >= cases._day(start))]
        mine = seen[(seen["player_id"] == o.player_id) & (seen["day"] >= start - pd.Timedelta(days=STALE_DAYS))]
        if over:
            games = games[games["game_date"] <= cases._day(o.end_date)]
            mine = mine[mine["day"] <= pd.Timestamp(o.end_date)]
        now_listed = listed.get(int(o.player_id))
        state = ("returned" if back is not None else "ended") if over else ("listed" if now_listed is not None else "off_report")
        opened = pd.Timestamp(o.onset_date)
        age = None if over else (now - opened.tz_localize(cases.ET).astimezone(timezone.utc)).days
        before = coverage is not None and (start < coverage or start == pd.Timestamp(dates[0]))
        if not over:
            open_players.add(int(o.player_id))
        out.append(dict(
            id=f"ncaa-mbb-{o.player_id}-{opened:%Y%m%d}", player_id=int(o.player_id), player=names.get(o.player_id),
            team=team_name.get(o.team), conference=conference.get(o.team), opened=cases._day(opened),
            began_before_observations=bool(before), region=o.region, injury_type=o.injury_type,
            games_missed=int(o.games_missed), last_missed=cases._day(o.end_date), returned=cases._day(back), state=state,
            ended_with=str(absence[after][0]) if over else None,
            latest_listing=None if now_listed is None else dict(status=now_listed["status"], observed=cases.eastern_day(times[-1])),
            first_observed=mine["observed_at"].min() if len(mine) else None, listings=int(games["game_date"].nunique()),
            new_injury=bool(o.new_injury) and not before,
            review=None if over else ("daily" if age <= cases.DAILY_REVIEW_DAYS and not before else "weekly")))

    # listed out with an injury and not playing since, with no case yet: a case once their team plays without them
    upcoming, playing = [], []
    for pid, x in listed.items():
        if pid in open_players or x["status"] not in MISSING or x["category"] != "injury" or pid not in by_player:
            continue
        since = pd.Timestamp(seen.loc[seen["player_id"] == pid, "day"].min())
        dates, absence = by_player[pid]
        # a game the day it was first seen may have come before it (a listing after an injury in that game)
        if ((dates > np.datetime64(since)) & (absence == "played")).any():
            playing.append(f"{x['player']} ({x['team']})")   # the listing is older than their latest games
            continue
        upcoming.append(dict(player_id=pid, player=names.get(pid), team=team_name.get(int(x["team_id"])), status=x["status"],
                             region=x["region"], injury_type=x["injury_type"], first_observed=seen.loc[seen["player_id"] == pid, "observed_at"].min()))

    people = latest.drop_duplicates(["team", "player"])
    unmatched = {}
    for p, t, pid, how in zip(people["player"], people["team"], people["player_id"], people["match"]):
        if pd.isna(pid) and how != "no team":
            unmatched.setdefault(how, []).append(f"{p} ({t})")
    review = dict(
        teams_not_matched=sorted(set(people.loc[people["team_id"].isna(), "team"])),
        unmatched={how: sorted(v) for how, v in sorted(unmatched.items())},
        uncertain=sorted({f"{p} ({t}) -> {names.get(int(pid))}, by {how}"
                          for p, t, pid, how in zip(people["player"], people["team"], people["player_id"], people["match"])
                          if how in ("last_initial", "fuzzy")}),
        listed_out_but_playing=sorted(playing))
    return dict(cases=sorted(out, key=lambda c: (c["state"] in ("returned", "ended"), c["opened"])), upcoming=upcoming, review=review,
                observations_from=cases._day(coverage), box_scores_through=cases._day(box_through), snapshots=len(times),
                listings_now=len(latest), matched_now=int(latest["player_id"].notna().sum()))


def section(archive: Path, now: datetime, refresh: bool = True) -> dict:
    """cases.json's college men's part."""
    rows, times = snapshots(archive)
    if not times:
        raise ValueError(f"no {SOURCE} snapshots in {archive}")
    return dict(season="2026-27", source=SOURCE, **build(rows, times, season_box(refresh=refresh), now))


# --- the historical check -----------------------------------------------------------------------------------------

def covers_status(text) -> str:
    s = str(text or "").lower()
    if "season" in s:
        return "out_for_season"
    if s.startswith("out"):
        return "out"
    if s.startswith(("ques", "doubt", "gtd")) or "game time" in s:
        return "questionable"
    if s.startswith("prob"):
        return "probable"
    return "day_to_day" if "day" in s else "unknown"


def covers_rows(season: int) -> tuple[pd.DataFrame, list[str]]:
    """A past season's saved Covers pages as the daily job saves SCACCHoops: one snapshot per day saved, with the
    collector's categories (updates.scac_facts) and the ESPN team ids the college study matched."""
    from . import updates
    p = pd.read_parquet(LISTINGS, columns=["captured", "school", "team_id", "player", "status", "part", "season"])
    p = p[(p["season"] == season) & p["team_id"].notna()]
    facts = [updates.scac_facts(str(part or "Unknown")) for part in p["part"]]
    at = [datetime(d.year, d.month, d.day, 17, tzinfo=cases.ET).astimezone(timezone.utc).isoformat(timespec="seconds") for d in p["captured"]]
    rows = pd.DataFrame(dict(observed_at=at, conference=None, team=p["school"].to_numpy(), team_id=p["team_id"].to_numpy(),
                             player=p["player"].to_numpy(), status=p["status"].map(covers_status).to_numpy(),
                             category=[f[0] for f in facts], region=[f[1] for f in facts], injury_type=[f[2] for f in facts]))
    return rows, sorted(set(at))


def replay(season: int = 2022, log=print) -> dict:
    """Rebuild a past season's college cases from its saved Covers pages, and compare them with the college study's
    absences that began that season (outputs/college_aftermath/injuries.parquet: 4 or more games missed, or a serious
    injury). A case is the study's absence when it is the same player's and opened inside it. The study starts an absence
    from a listing's note date when Covers gave one; the cases have only when a listing was seen, so a start can be later."""
    rows, times = covers_rows(season)
    b = season_box(season, refresh=False)
    result = build(rows, times, b, datetime.now(timezone.utc), season=season)
    live = pd.DataFrame(result["cases"]).assign(opened=lambda d: pd.to_datetime(d["opened"]))
    pg = player_games(b, season)
    dates = {pid: d["game_date"].to_numpy() for pid, d in pg[pg["status"] != "played"].groupby("player_id")}
    games = b[b["season"] == season]["game_date"]
    hist = pd.read_parquet(STUDY, columns=["player_id", "player", "first_listed", "last_game", "back", "games_missed", "season_over"])
    hist = hist[(hist["last_game"] >= games.min()) & (hist["last_game"] <= games.max())].drop_duplicates(["player_id", "last_game"])
    # an absence after the player's team's last game of the season is the next season's, which one season can't show
    team_end = pg.groupby("player_id")["game_date"].max()
    later = hist[[team_end.get(p, pd.Timestamp.min) > g for p, g in zip(hist["player_id"], hist["last_game"])]]
    found, late, same_back, same_games = [], [], 0, 0
    for h in hist.itertuples(index=False):
        end = h.back if not h.season_over and not pd.isna(h.back) else games.max() + pd.Timedelta(days=1)
        mine = live[(live["player_id"] == h.player_id) & (live["opened"] > h.last_game) & (live["opened"] < end)]
        if not len(mine):
            continue
        c = mine.iloc[0]
        found.append((int(h.player_id), c["opened"]))
        # the study's first missed game: its player's first after their last game, from 3 days before the listing
        missed = dates.get(h.player_id, np.array([], dtype="datetime64[ns]"))
        missed = missed[(missed > np.datetime64(h.last_game)) & (missed >= np.datetime64(pd.Timestamp(h.first_listed) - pd.Timedelta(days=3)))]
        late.append(int(np.sum(missed < np.datetime64(c["opened"]))) if len(missed) else None)
        same_back += (cases._day(h.back) if not h.season_over else None) == (None if pd.isna(c["returned"]) else c["returned"])
        same_games += int(h.games_missed) == c["games_missed"]
    long = live[(live["games_missed"] >= 4) & ~live["began_before_observations"]]
    people = match_players(rows.drop_duplicates(["team_id", "player"]), b, season)
    out = dict(season=season, snapshots=len(times), cases=len(live), study_absences=len(hist), in_this_season=len(later), found=len(found),
               same_start=sum(x == 0 for x in late), games_later={str(k): v for k, v in sorted(pd.Series([x for x in late if x]).value_counts().items())},
               same_return=int(same_back), same_games_missed=int(same_games), cases_4_plus_games=len(long),
               of_those_in_study=int(sum((p, o) in set(found) for p, o in zip(long["player_id"], long["opened"]))),
               players_matched=float(round(people["player_id"].notna().mean(), 3)))
    log(out)
    return out
