import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from injury_risk import college_cases as cc
from injury_risk import updates

DAYS = [f"2026-11-{d:02d}" for d in (4, 7, 10, 13, 16)]     # Toledo v Kent State
TEAMS = {2649: ("Toledo", "TOL"), 2309: ("Kent State", "KENT")}
PLAYERS = {1: ("Javan Simmons", 2649), 2: ("Sonny Wilson", 2649), 3: ("Tyler Cochran", 2649), 4: ("Jalen Sullinger", 2309)}
NOW = datetime.fromisoformat("2026-11-17T00:00:00+00:00")


def box(played, last_season=()):
    """ESPN box scores: every player listed in every game, with minutes in the days ``played`` maps them to (all, if not
    there); ``last_season``: (name, team id) on last season's box scores only."""
    rows = []
    for g, day in enumerate(DAYS):
        for pid, (name, team) in PLAYERS.items():
            on = day in played.get(pid, DAYS)
            rows.append(dict(season=2027, game_id=g, game_date=pd.Timestamp(day), athlete_id=pid, athlete_display_name=name,
                             team_id=team, team_location=TEAMS[team][0], team_short_display_name=TEAMS[team][0],
                             team_abbreviation=TEAMS[team][1], team_display_name=TEAMS[team][0], minutes=20.0 if on else np.nan))
    for i, (name, team) in enumerate(last_season):
        rows.append(dict(season=2026, game_id=100 + i, game_date=pd.Timestamp("2026-02-01"), athlete_id=50 + i,
                         athlete_display_name=name, team_id=team, team_location=TEAMS[team][0],
                         team_short_display_name=TEAMS[team][0], team_abbreviation=TEAMS[team][1],
                         team_display_name=TEAMS[team][0], minutes=10.0))
    b = pd.DataFrame(rows)
    b.attrs["division_one"] = set(TEAMS)
    return b


def snapshot(day, listed):
    """An archive file whose SCACCHoops snapshot was observed the evening of ``day``: (player, team, status, category, region)."""
    at = f"{day}T23:40:00+00:00"
    rows = [dict(id="0" * 24, league="ncaa_mbb", player=p, team=t, game_date=None, status=s, category=c, region=r, injury_type=None,
                 conference="MAC") for p, t, s, c, r in listed]
    return dict(schema_version=1, generated_at=at, sources={cc.SOURCE: dict(snapshot=dict(
        report_at=None, observed_at=at, sha256="a" * 64, rows=rows, not_submitted=[], pages_checked=31))})


def run(snapshots, played, last_season=()):
    with tempfile.TemporaryDirectory() as tmp:
        for i, s in enumerate(snapshots):
            path = Path(tmp) / f"{i:03d}.json"
            path.write_text(json.dumps(s), encoding="utf-8")
        rows, times = cc.snapshots(Path(tmp))
    return cc.build(rows, times, box(played, last_season), NOW)


def case(result, name):
    found = [c for c in result["cases"] if c["player"] == name]
    return found[0] if len(found) == 1 else found


class Matching(unittest.TestCase):
    def test_teams_by_name_or_alias_and_players_by_name_then_initial(self):
        b = box({}, last_season=[("Old Player", 2649)])
        self.assertEqual(cc.team_ids({"Toledo", "Kent State", "Connecticut", "Nowhere"}, b), {"Toledo": 2649, "Kent State": 2309, "Connecticut": 41})
        listings = pd.DataFrame(dict(team=["Toledo", "Toledo", "Toledo", "Toledo", "Nowhere"],
                                     player=["Javan Simmons", "S. Wilson", "Old Player", "Someone Else", "Javan Simmons"]))
        m = cc.match_players(listings, b)
        self.assertEqual(m["player_id"].tolist()[:2], [1, 2])
        self.assertEqual(m["match"].tolist(), ["name", "last_initial", "on the team's box scores last season only", "not found", "no team"])

    def test_covers_statuses(self):
        self.assertEqual([cc.covers_status(s) for s in ("Out indefinitely", "out for season", "Ques Sat", "Probable", "Day-to-day", "")],
                         ["out", "out_for_season", "questionable", "probable", "day_to_day", "unknown"])

    def test_listing_categories_read_body_parts_the_groups_miss(self):
        self.assertEqual(updates.scac_facts("Lower Body")[0], "injury")
        self.assertEqual(updates.scac_facts("Chest")[:2], ("injury", "trunk"))
        self.assertEqual(updates.scac_facts("Disciplinary")[0], "non_medical")
        self.assertEqual(updates.scac_facts("Undisclosed")[0], "unknown")


class Cases(unittest.TestCase):
    def test_a_listed_player_who_sits_out_has_a_case_until_they_play(self):
        listed = [("Javan Simmons", "Toledo", "out", "injury", "ankle")]
        result = run([snapshot(DAYS[0], listed), snapshot(DAYS[1], listed), snapshot(DAYS[2], listed)],
                     {1: [DAYS[0], DAYS[3], DAYS[4]]})
        c = case(result, "Javan Simmons")
        self.assertEqual((c["opened"], c["games_missed"], c["returned"], c["state"], c["region"]), (DAYS[1], 2, DAYS[3], "returned", "ankle"))
        self.assertEqual((c["team"], c["conference"], c["listings"], c["ended_with"]), ("Toledo", "MAC", 2, "played"))

    def test_a_missed_game_without_a_listing_extends_the_run(self):
        listed = [("Javan Simmons", "Toledo", "out", "injury", "knee")]
        result = run([snapshot(DAYS[0], listed), snapshot(DAYS[1], listed), snapshot(DAYS[2], []), snapshot(DAYS[3], [])],
                     {1: [DAYS[0], DAYS[4]]})
        c = case(result, "Javan Simmons")
        self.assertEqual((c["games_missed"], c["last_missed"], c["returned"]), (3, DAYS[3], DAYS[4]))

    def test_an_old_snapshot_says_nothing_about_a_later_game(self):
        result = run([snapshot(DAYS[0], [("Sonny Wilson", "Toledo", "out", "injury", "hand")])], {2: [DAYS[0], DAYS[1]]})
        self.assertEqual(result["cases"], [])   # the November 4 snapshot is more than 3 days before the games he missed

    def test_illness_and_rules_absences_open_no_case(self):
        listed = [("Sonny Wilson", "Toledo", "out", "illness", None), ("Tyler Cochran", "Toledo", "out", "non_medical", None)]
        result = run([snapshot(DAYS[0], listed), snapshot(DAYS[1], listed)], {2: [DAYS[0], DAYS[2]], 3: [DAYS[0], DAYS[2]]})
        self.assertEqual(result["cases"], [])

    def test_listed_out_without_a_missed_game_yet_waits(self):
        # listed the evening of the last game, which he played: hurt in it, perhaps
        result = run([snapshot(DAYS[4], [("Jalen Sullinger", "Kent State", "out", "injury", "foot")])], {})
        self.assertEqual(result["cases"], [])
        self.assertEqual([(u["player"], u["team"], u["region"]) for u in result["upcoming"]], [("Jalen Sullinger", "Kent State", "foot")])
        self.assertEqual(result["review"]["listed_out_but_playing"], [])

    def test_a_listing_the_games_contradict_is_reviewed_not_a_case(self):
        listed = [("Jalen Sullinger", "Kent State", "out", "injury", "foot"), ("Tyler Cochran", "Toledo", "out_for_season", "injury", "knee")]
        result = run([snapshot(DAYS[3], listed)], {4: DAYS[:3]})
        self.assertEqual(result["review"]["listed_out_but_playing"], ["Tyler Cochran (Toledo)"])
        self.assertEqual(result["upcoming"], [])
        self.assertEqual([(c["player"], c["state"]) for c in result["cases"]], [("Jalen Sullinger", "listed")])

    def test_an_open_case_off_the_latest_snapshot_is_off_report(self):
        listed = [("Javan Simmons", "Toledo", "out", "injury", "ankle")]
        result = run([snapshot(DAYS[0], listed), snapshot(DAYS[1], listed), snapshot(DAYS[4], [])], {1: [DAYS[0]]})
        c = case(result, "Javan Simmons")
        self.assertEqual((c["opened"], c["state"], c["returned"], c["review"]), (DAYS[1], "off_report", None, "weekly"))


if __name__ == "__main__":
    unittest.main()
