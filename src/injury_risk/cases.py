"""Injury cases from the daily availability observations: local, and not published until they have been reviewed.

The daily job's archive keeps every NBA report it read. Here each listing is matched to a player, and the season's box
scores say game by game whether they played. The rules are the historical onsets' (labels.classify_absences,
labels.find_onsets): a case opens at the first game missed in a run of injury absences and ends with the run, at a game
the player played or missed for another reason (a coach's decision, rest); the return is the next game they played.
Dropping off the report is not a return, and a case the archive caught already under way says so rather than guessing
when it began. Cases are rebuilt from the archive every time, so a corrected report or box score changes the case it
belongs to, while the archive keeps what was observed when.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from . import games, labels, reasons, sources
from .paths import DATA, INTERIM, PROCESSED

SEASON = 2027                 # 2026-27, the season the daily job follows
SEASON_KINDS = ["player_box", "inactive", "schedule", "schedule_xwalk", "espn_schedule"]
LOCAL = DATA / "updates"
DAILY_REVIEW_DAYS = 7         # a new case is checked every day for its first week, then weekly until the player returns
FILL_DAYS = 30                # how far back a game day with no archived report is read from the league's site
RUN = ("injury", "unknown", "unknown_medical")   # absences a run of injury absences is made of (labels.find_onsets)
STATUS = {"out": "Out", "doubtful": "Doubtful", "questionable": "Questionable", "probable": "Probable", "available": "Available"}
MISSING = ("Out", "Doubtful")  # listings that expect the player to miss the game
CLASSES = {"injury", "illness", "management", "non_medical", "unknown"}   # the daily job's categories (updates.CLASSES)
ET = ZoneInfo("America/New_York")


def _day(t) -> str | None:
    return None if t is None or pd.isna(t) else pd.Timestamp(t).strftime("%Y-%m-%d")


def archived_reports(archive: Path, source: str = "nba-official") -> tuple[dict, int]:
    """report_at -> the report as first observed, and how many reports were corrected. The same report read again is one
    report. A report republished under the same time with other rows replaces it from the moment it was observed."""
    kept, corrected = {}, 0
    for path in sorted(archive.rglob("*.json")):
        snap = json.loads(path.read_text(encoding="utf-8"))["sources"].get(source, {}).get("snapshot")
        if not snap or not snap["report_at"]:
            continue
        was = kept.get(snap["report_at"])
        if was is None:
            kept[snap["report_at"]] = dict(snap, first_observed=snap["observed_at"])
        elif was["sha256"] != snap["sha256"] and snap["observed_at"] > was["first_observed"]:
            kept[snap["report_at"]] = dict(snap, first_observed=snap["observed_at"])
            corrected += 1
    return kept, corrected


def eastern_day(stamp: str) -> str:
    return datetime.fromisoformat(stamp).astimezone(ET).date().isoformat()


def missing_days(have: set, sched: pd.DataFrame, now: datetime, back: int = FILL_DAYS) -> list[date]:
    """The season's game days before today (Eastern), at most ``back`` days ago, with no report in the archive."""
    today = now.astimezone(ET).date()
    return [d for d in sorted(set(sched["game_date"].dt.date)) if today - timedelta(days=back) <= d < today and d.isoformat() not in have]


def fill(days: list[date], archive: Path, log=print) -> tuple[list, list]:
    """Read the missing days' 5 PM reports from the league's site, as the daily job reads them, into the archive."""
    from . import updates
    from .update_http import Client
    spec = next(s for s in updates.load_config() if s["id"] == "nba-official")
    if not spec["enabled"]:
        return [], [dict(day=d.isoformat(), problem="source not enabled") for d in days]
    client = Client(spec["hosts"], LOCAL / "raw", budget=2 * len(days) + 5)
    return updates.fill_reports(spec, client, days, archive, log=log)


def listings(kept: dict) -> pd.DataFrame:
    """The archived reports (archived_reports) as one row per listing, with when each report was first observed."""
    rows = [dict(report_at=k, first_observed=s["first_observed"], game_date=r["game_date"], team=r["team"], player=r["player"],
                 status=r["status"], category=r["category"], region=r["region"], injury_type=r["injury_type"])
            for k, s in kept.items() for r in s["rows"] if r["game_date"]]
    out = pd.DataFrame(rows, columns=["report_at", "first_observed", "game_date", "team", "player", "status", "category", "region",
                                      "injury_type"])
    out["report_day"] = [eastern_day(t) for t in out["report_at"]]
    return out.sort_values(["report_at", "team", "player"], ignore_index=True)


def unsubmitted(kept: dict) -> set:
    """(report, game day, team) for each team a report says hadn't submitted its listings yet."""
    return {(k, n["game_date"], n["team"]) for k, s in kept.items() for n in s["not_submitted"]}


def observed_reports(archive: Path, source: str = "nba-official") -> tuple[pd.DataFrame, int]:
    """Every distinct report in the archive, one row per listing, and how many reports were corrected."""
    kept, corrected = archived_reports(archive, source)
    return listings(kept), corrected


def latest_reports(reports: pd.DataFrame, sched: pd.DataFrame, skip=()) -> dict:
    """team -> the latest report that covered one of its games. A report lists the day's games and often the next day's,
    and covers each team playing then that had submitted (``skip``: unsubmitted), even one with nobody listed. So a player
    missing from it is off their team's report, not just absent from a report about other teams' games."""
    sides = pd.concat([sched[["game_date", side]].rename(columns={side: "team"}) for side in ("home", "away")])
    sides = sides.assign(game_date=sides["game_date"].dt.strftime("%Y-%m-%d")).drop_duplicates()
    covered = reports[["report_at", "game_date"]].drop_duplicates().merge(sides, on="game_date")
    skip = set(skip)
    covered = covered[np.array([(r, d, t) not in skip for r, d, t in zip(covered["report_at"], covered["game_date"], covered["team"])],
                               dtype=bool)]
    return covered.groupby("team")["report_at"].max().to_dict()


def game_entries(matched: pd.DataFrame) -> pd.DataFrame:
    """One listing per (game, team, player), as labels.best_entries picks it: the game day's report, else the latest
    earlier one. The saved category stands in for the classified reason, which the archive doesn't keep."""
    r = matched.dropna(subset=["player_id"]).astype({"player_id": "int64"})
    r = r[r["report_day"] <= r["game_date"]]
    r = r.sort_values(["game_date", "team", "player_id", "report_at"]).drop_duplicates(["game_date", "team", "player_id"], keep="last")
    r = r.assign(status=r["status"].map(STATUS).fillna("Unknown"), reason=None, reason_class=r["category"],
                 same_day=r["report_day"] == r["game_date"])
    return r[["game_date", "team", "player_id", "status", "reason", "reason_class", "region", "injury_type", "same_day"]]


def run_start(dates: np.ndarray, absence: np.ndarray, onset) -> np.datetime64:
    """The first game of the run of injury absences an onset belongs to (labels.find_onsets starts a case at most one
    game before its first injury listing, so a run the observations joined late reaches further back)."""
    i = int(np.searchsorted(dates, np.datetime64(onset)))
    while i > 0 and absence[i - 1] in RUN:
        i -= 1
    return dates[i]


def build(reports: pd.DataFrame, pg: pd.DataFrame, sched: pd.DataFrame, now: datetime, season: int = SEASON,
          skip=()) -> dict:
    """The season's cases, the listings awaiting a game, and what needs a person to look at it. ``skip``: the
    (report, game day, team) of teams that hadn't submitted to a report (unsubmitted)."""
    matched = labels.match_players(reports, pg, sched)
    entries = game_entries(matched)
    pg = labels.classify_absences(pg[pg["season"] == season], entries)
    onsets = labels.find_onsets(pg)
    coverage = pd.Timestamp(reports["game_date"].min()) if len(reports) else None
    box_through = pg.loc[pg["status"] == "played", "game_date"].max()
    seen = matched.dropna(subset=["player_id"]).astype({"player_id": "int64"})
    team_latest = latest_reports(reports, sched, skip)
    on_latest = seen[np.array([team_latest.get(t) == r for t, r in zip(seen["team"], seen["report_at"])], dtype=bool)]
    listed = {int(p): x for p, x in on_latest.groupby("player_id")}
    names = pg.drop_duplicates("player_id", keep="last").set_index("player_id")
    by_player = {pid: (d["game_date"].to_numpy(), d["absence"].to_numpy()) for pid, d in pg.sort_values("game_date").groupby("player_id")}

    cases, open_players = [], set()
    for o in onsets.itertuples(index=False):
        dates, absence = by_player[o.player_id]
        start = pd.Timestamp(run_start(dates, absence, o.onset_date))
        # a later game that wasn't an injury absence ends the case, a coach's decision included; the return is the next
        # game they played (the historical onsets only record one when it is the very next game)
        after = dates > np.datetime64(o.end_date)
        over = bool(after.any())
        played = dates[after & (absence == "played")]
        back = pd.Timestamp(played[0]) if len(played) else None
        mine = seen[(seen["player_id"] == o.player_id) & (seen["game_date"] >= _day(start))]
        if over:
            mine = mine[mine["game_date"] <= _day(o.end_date)]
        now_listed = listed.get(int(o.player_id))
        state = ("returned" if back is not None else "ended") if over else ("listed" if now_listed is not None else "off_report")
        opened = pd.Timestamp(o.onset_date)
        age = None if over else (now - opened.tz_localize(ET).astimezone(timezone.utc)).days
        # under way before the first observed report, or at the player's first game, with nothing before it to say when
        before = coverage is not None and (start < coverage or start == pd.Timestamp(dates[0]))
        if not over:
            open_players.add(int(o.player_id))
        last = now_listed.sort_values("game_date").iloc[-1] if now_listed is not None else None
        cases.append(dict(
            id=f"nba-{o.player_id}-{opened:%Y%m%d}", player_id=int(o.player_id),
            player=f"{names.at[o.player_id, 'first_name']} {names.at[o.player_id, 'last_name']}", team=o.team,
            opened=_day(opened), began_before_observations=bool(before), region=o.region, injury_type=o.injury_type,
            games_missed=int(o.games_missed), last_missed=_day(o.end_date), returned=_day(back), state=state,
            ended_with=str(absence[after][0]) if over else None,   # the next game: played, or a coach's decision, rest, ...
            latest_listing=None if last is None else dict(status=STATUS.get(last["status"], "Unknown"), game_date=last["game_date"]),
            first_observed=mine["first_observed"].min() if len(mine) else None, listings=int(mine["game_date"].nunique()),
            new_injury=bool(o.new_injury) and not before,
            review=None if over else ("daily" if age <= DAILY_REVIEW_DAYS and not before else "weekly")))

    # listed to miss a game that has no box score yet, with no case open: a case once they miss it
    upcoming = []
    after = _day(box_through) if not pd.isna(box_through) else ""
    for pid, x in listed.items():
        x = x[(x["game_date"] > after) & x["status"].map(STATUS).isin(MISSING) & (x["category"] == "injury")]
        if pid in open_players or not len(x):
            continue
        first = x.sort_values("game_date").iloc[0]
        name = f"{names.at[pid, 'first_name']} {names.at[pid, 'last_name']}" if pid in names.index else first["player"]
        upcoming.append(dict(player_id=pid, player=name, team=first["team"], game_date=first["game_date"],
                             status=STATUS[first["status"]], region=first["region"], injury_type=first["injury_type"],
                             first_observed=first["first_observed"]))

    people = matched.drop_duplicates(["team", "player"])
    review = dict(
        unmatched=sorted({f"{p} ({t})" for p, t, pid in zip(people["player"], people["team"], people["player_id"]) if pd.isna(pid)}),
        uncertain=sorted({f"{p} ({t}) -> {names.at[int(pid), 'first_name']} {names.at[int(pid), 'last_name']}, by {how}"
                          for p, t, pid, how in zip(people["player"], people["team"], people["player_id"], people["match"])
                          if how in ("last_initial", "fuzzy") and int(pid) in names.index}))
    return dict(cases=sorted(cases, key=lambda c: (c["state"] in ("returned", "ended"), c["opened"])), upcoming=upcoming,
                review=review, observations_from=_day(coverage), box_scores_through=_day(box_through), reports=int(reports["report_at"].nunique()))


def season_data(season: int = SEASON, refresh: bool = True) -> tuple[pd.DataFrame, pd.DataFrame]:
    """The season's schedule and player games, from the same data releases the history uses (refreshed daily)."""
    if refresh:
        for r in sources.fetch(seasons=(season,), kinds=SEASON_KINDS, force=True):
            if r["status"] not in ("downloaded", "cached"):
                raise RuntimeError(f"could not download {r['kind']} for {season}: {r['status']}")
    sched = games.build_schedule((season,))
    return sched, games.build_player_games((season,), sched)


def export(archive: Path = LOCAL / "archive", output: Path = LOCAL / "cases.json", *, now: datetime | None = None,
           refresh: bool = True, fill_missing: bool = False, log=print) -> dict:
    now = now or datetime.now(timezone.utc)
    sched, pg = season_data(refresh=refresh)
    filled = []
    if fill_missing:
        kept, _ = archived_reports(archive)
        days = missing_days({eastern_day(k) for k in kept}, sched, now)
        if days:
            filled, _ = fill(days, archive, log=log)
    kept, corrected = archived_reports(archive)
    reports = listings(kept)
    if not len(reports):
        raise ValueError(f"no NBA reports in {archive}")
    result = build(reports, pg, sched, now, skip=unsubmitted(kept))
    lacking = missing_days({eastern_day(k) for k in kept}, sched, now, back=366)
    out = dict(schema_version=1, generated_at=now.isoformat(timespec="seconds"), season="2026-27", corrected_reports=corrected,
               rules=("A case opens at the first game missed in a run of injury absences (box scores and the reports) and ends "
                      "with the run, at a game played or missed for another reason; the return is the next game played. Off the "
                      "team's latest report is not a return. Reviewed daily for 7 days, then weekly, until the case ends."),
               reports_filled=filled, game_days_without_report=[d.isoformat() for d in lacking], **result)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    states = pd.Series([c["state"] for c in result["cases"]]).value_counts().to_dict()
    log({"cases": len(result["cases"]), "states": states, "upcoming": len(result["upcoming"]), "unmatched": len(result["review"]["unmatched"]),
         "uncertain": len(result["review"]["uncertain"]), "reports": result["reports"], "reports_filled": len(filled),
         "game_days_without_report": len(lacking), "observations_from": result["observations_from"],
         "box_scores_through": result["box_scores_through"], "output": str(output)})
    return out


# --- the historical check -----------------------------------------------------------------------------------------

def as_observed(report_rows: pd.DataFrame) -> pd.DataFrame:
    """Historical report rows as the daily job saves them: the 5 PM report, its time, and only the normalized facts
    (updates.read_nba_pdf), so the case rules can be checked on whole past seasons."""
    r = report_rows.copy()
    stamp = pd.to_datetime(r["report_stamp"])
    r["report_at"] = [t.replace(tzinfo=ET).astimezone(timezone.utc).isoformat(timespec="seconds") for t in stamp]
    facts = [reasons.classify(x) for x in r["reason"]]
    r["category"] = [f["reason_class"] if f["reason_class"] in CLASSES else "unknown" for f in facts]
    r["region"] = [f["region"] for f in facts]
    r["injury_type"] = [f["injury_type"] for f in facts]
    r["status"] = r["status"].str.lower()
    r["first_observed"] = r["report_at"]
    r["report_day"] = r["report_day"].astype(str)
    r["game_date"] = r["game_date"].astype(str)
    return r[["report_at", "first_observed", "game_date", "team", "player", "status", "category", "region", "injury_type", "report_day"]]


def replay(season: int = 2026, log=print) -> dict:
    """Rebuild a past season's cases from its 5 PM reports the way the daily job would have seen them, and compare them
    with that season's historical onsets (data/processed/onsets.parquet)."""
    rows = pd.read_parquet(INTERIM / "report_rows.parquet")
    sched, pg = season_data(season, refresh=False)
    days = set(sched["game_date"].dt.date.astype(str))
    rows = rows[rows["game_date"].astype(str).isin(days)]
    result = build(as_observed(rows), pg, sched, datetime.now(timezone.utc), season=season)
    live = pd.DataFrame(result["cases"])
    hist = pd.read_parquet(PROCESSED / "onsets.parquet")
    hist = hist[hist["season"] == season].assign(opened=lambda d: d["onset_date"].dt.strftime("%Y-%m-%d"))
    # a case already under way at a player's first game of the season may have started the season before, where the
    # history (built across seasons) puts it, so it is left out of the comparison
    inside = live[~live["began_before_observations"]]
    later = hist[~hist.set_index(["player_id", "opened"]).index.isin(
        list(zip(live.loc[live["began_before_observations"], "player_id"], live.loc[live["began_before_observations"], "opened"])))]
    key = lambda d: set(zip(d["player_id"].astype(int), d["opened"]))   # noqa: E731
    both = key(inside) & key(later)
    ids = list(zip(later["player_id"].astype(int), later["opened"]))
    games_missed = dict(zip(ids, later["games_missed"]))
    last_missed = {k: _day(t) for k, t in zip(ids, later["end_date"])}
    returned = {k: _day(t) for k, t in zip(ids, later["return_date"])}
    pairs = [(c, (int(c["player_id"]), c["opened"])) for _, c in inside.iterrows()]
    pairs = [(c, k) for c, k in pairs if k in both]
    # the history records a return only when it is the very next game; the cases also find a later one, after a coach's
    # decision or rest, so those are counted apart
    out = dict(season=season, cases=len(live), already_under_way=int(live["began_before_observations"].sum()),
               historical_onsets=len(hist), compared_here=len(inside), compared_in_history=len(later), matched=len(both),
               missing_here=sorted(key(later) - key(inside)), extra_here=sorted(key(inside) - key(later)),
               same_games_missed=sum(int(games_missed[k]) == c["games_missed"] for c, k in pairs),
               same_last_missed=sum(last_missed[k] == c["last_missed"] for c, k in pairs),
               historical_returns=sum(returned[k] is not None for c, k in pairs),
               same_return=sum(returned[k] is not None and returned[k] == c["returned"] for c, k in pairs),
               return_after_another_absence=sum(returned[k] is None and c["returned"] is not None for c, k in pairs),
               unmatched_names=len(result["review"]["unmatched"]))
    log({k: (len(v) if isinstance(v, list) else v) for k, v in out.items()})
    return out
