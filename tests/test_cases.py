import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from injury_risk import cases

DAYS = [f"2026-11-{d:02d}" for d in (2, 4, 6, 8, 10, 12)]   # one BOS-NYK game every other day
PLAYERS = {1: ("Jaylen", "Brown", "BOS"), 2: ("Jalen", "Brunson", "NYK"), 3: ("Derrick", "White", "BOS"),
           4: ("Josh", "Hart", "NYK"), 5: ("Al", "Horford", "BOS")}


AHEAD = ["2026-11-14"]                                       # scheduled, not yet played: no box score


def season(played, coach=None):
    """A schedule and player games: ``played`` maps player id -> the game days they played (the rest they sat out);
    ``coach``: player id -> the days they sat on the bench by the coach's decision."""
    sched = pd.DataFrame(dict(game_id=[f"g{i}" for i in range(len(DAYS + AHEAD))], season=2027, season_type="regular-season",
                              game_date=pd.to_datetime(DAYS + AHEAD), home="BOS", away="NYK"))
    rows = []
    for pid, (first, last, team) in PLAYERS.items():
        for gid, day in zip(sched["game_id"], DAYS):
            on, bench = day in played.get(pid, DAYS), day in (coach or {}).get(pid, [])
            rows.append(dict(game_id=gid, team=team, player_id=pid, first_name=first, last_name=last, season=2027,
                             game_date=pd.Timestamp(day), status="played" if on else ("dnp" if bench else "inactive"),
                             comment="DNP - Coach's Decision" if bench else ""))
    return sched, pd.DataFrame(rows)


def report(day, rows, observed=None, sha="a" * 64):
    """An archive file's NBA snapshot: the 5 PM ET report of ``day`` listing (player, team, game day, status, category, region)."""
    at = f"{day}T22:00:00+00:00"
    listed = [dict(id="0" * 24, league="nba", player=p, team=t, game_date=g, status=s, category=c, region=r, injury_type=None,
                   conference=None) for p, t, g, s, c, r in rows]
    return dict(generated_at=observed or at, schema_version=1, sources={"nba-official": dict(snapshot=dict(
        report_at=at, observed_at=observed or f"{day}T23:40:00+00:00", sha256=sha, rows=listed, not_submitted=[], pages_checked=1))})


def run(reports, played, now="2026-11-12T23:45:00+00:00", coach=None):
    with tempfile.TemporaryDirectory() as tmp:
        for i, r in enumerate(reports):
            path = Path(tmp) / "2026" / "11" / f"{i:03d}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(r), encoding="utf-8")
        observed, corrected = cases.observed_reports(Path(tmp))
    sched, pg = season(played, coach)
    return cases.build(observed, pg, sched, datetime.fromisoformat(now)), observed, corrected


def case(result, name):
    found = [c for c in result["cases"] if c["player"] == name]
    return found[0] if len(found) == 1 else found


class Archive(unittest.TestCase):
    def test_a_report_read_twice_counts_once_from_its_first_observation(self):
        r = ("Brown, Jaylen", "BOS", DAYS[1], "out", "injury", "ankle")
        _, observed, corrected = run([report(DAYS[1], [r], observed="2026-11-04T23:40:00+00:00"),
                                      report(DAYS[1], [r], observed="2026-11-05T23:40:00+00:00")], {})
        self.assertEqual(len(observed), 1)
        self.assertEqual(observed["first_observed"].iloc[0], "2026-11-04T23:40:00+00:00")
        self.assertEqual(corrected, 0)

    def test_a_corrected_report_replaces_the_rows_it_was_published_with(self):
        old = report(DAYS[1], [("Brown, Jaylen", "BOS", DAYS[1], "out", "injury", "ankle")], observed="2026-11-04T23:40:00+00:00")
        new = report(DAYS[1], [("Brown, Jaylen", "BOS", DAYS[1], "out", "injury", "knee")], observed="2026-11-05T23:40:00+00:00",
                     sha="b" * 64)
        _, observed, corrected = run([old, new], {})
        self.assertEqual(observed["region"].tolist(), ["knee"])
        self.assertEqual(corrected, 1)


class Cases(unittest.TestCase):
    def test_listings_across_games_are_one_case_that_ends_when_the_player_plays(self):
        reports = [report(DAYS[1], [("Brown, Jaylen", "BOS", DAYS[1], "out", "injury", "ankle")]),
                   report(DAYS[2], [("Brown, Jaylen", "BOS", DAYS[2], "out", "injury", "ankle")])]
        result, _, _ = run(reports, {1: [DAYS[0], DAYS[3], DAYS[4], DAYS[5]]})
        c = case(result, "Jaylen Brown")
        self.assertEqual((c["opened"], c["games_missed"], c["returned"], c["state"]), (DAYS[1], 2, DAYS[3], "returned"))
        self.assertEqual((c["listings"], c["review"], c["region"]), (2, None, "ankle"))
        self.assertEqual(c["first_observed"], f"{DAYS[1]}T23:40:00+00:00")
        self.assertTrue(c["new_injury"])

    def test_a_case_without_a_return_stays_open_listed_or_off_the_report(self):
        reports = [report(DAYS[3], [("Brunson, Jalen", "NYK", DAYS[3], "out", "injury", "knee"),
                                    ("Hart, Josh", "NYK", DAYS[3], "out", "injury", "back")]),
                   report(DAYS[5], [("Brunson, Jalen", "NYK", DAYS[5], "out", "injury", "knee")])]
        result, _, _ = run(reports, {2: DAYS[:3], 4: DAYS[:3]})
        listed, off = case(result, "Jalen Brunson"), case(result, "Josh Hart")
        self.assertEqual((listed["state"], listed["returned"], listed["latest_listing"]), ("listed", None, dict(status="Out", game_date=DAYS[5])))
        self.assertEqual(off["state"], "off_report")   # gone from the latest report, and no game played since: not a return
        self.assertEqual(listed["review"], "daily")

    def test_review_is_daily_for_a_week_then_weekly(self):
        reports = [report(DAYS[3], [("Brunson, Jalen", "NYK", DAYS[3], "out", "injury", "knee")])]
        early, _, _ = run(reports, {2: DAYS[:3]}, now="2026-11-09T12:00:00+00:00")
        later, _, _ = run(reports, {2: DAYS[:3]}, now="2026-11-20T12:00:00+00:00")
        self.assertEqual(case(early, "Jalen Brunson")["review"], "daily")
        self.assertEqual(case(later, "Jalen Brunson")["review"], "weekly")

    def test_illness_and_other_absences_open_no_case(self):
        reports = [report(DAYS[1], [("White, Derrick", "BOS", DAYS[1], "out", "illness", None),
                                    ("Horford, Al", "BOS", DAYS[1], "out", "management", None)])]
        result, _, _ = run(reports, {3: [DAYS[0]] + DAYS[2:], 5: [DAYS[0]] + DAYS[2:]})
        self.assertEqual(result["cases"], [])

    def test_a_case_under_way_before_the_first_report_says_so(self):
        reports = [report(DAYS[2], [("Brown, Jaylen", "BOS", DAYS[2], "out", "injury", "foot")])]
        result, _, _ = run(reports, {1: []})   # sat out from the first game, before any report was observed
        c = case(result, "Jaylen Brown")
        self.assertTrue(c["began_before_observations"])
        self.assertFalse(c["new_injury"])
        self.assertEqual((c["state"], c["review"]), ("listed", "weekly"))

    def test_a_case_closes_on_a_return_even_when_it_began_before_the_reports(self):
        reports = [report(DAYS[2], [("Brown, Jaylen", "BOS", DAYS[2], "out", "injury", "foot")])]
        result, _, _ = run(reports, {1: DAYS[4:]})
        c = case(result, "Jaylen Brown")
        self.assertEqual((c["began_before_observations"], c["returned"], c["review"]), (True, DAYS[4], None))

    def test_a_listing_for_a_game_not_yet_played_waits_as_upcoming(self):
        later = AHEAD[0]
        reports = [report(DAYS[5], [("Brown, Jaylen", "BOS", later, "out", "injury", "hamstring"),
                                    ("White, Derrick", "BOS", later, "questionable", "injury", "ankle")])]
        result, _, _ = run(reports, {})
        self.assertEqual(result["cases"], [])
        self.assertEqual([(u["player"], u["game_date"], u["status"]) for u in result["upcoming"]], [("Jaylen Brown", later, "Out")])

    def test_names_that_match_no_player_go_to_review(self):
        reports = [report(DAYS[1], [("Nobody, Someone", "BOS", DAYS[1], "out", "injury", "ankle")])]
        result, _, _ = run(reports, {})
        self.assertEqual(result["review"]["unmatched"], ["Nobody, Someone (BOS)"])
        self.assertEqual(result["cases"], [])

    def test_a_coaches_decision_ends_the_case_and_the_return_is_the_next_game_played(self):
        reports = [report(DAYS[1], [("Brown, Jaylen", "BOS", DAYS[1], "out", "injury", "ankle")])]
        result, _, _ = run(reports, {1: [DAYS[0], DAYS[3], DAYS[4], DAYS[5]]}, coach={1: [DAYS[2]]})
        c = case(result, "Jaylen Brown")
        self.assertEqual((c["games_missed"], c["last_missed"], c["returned"], c["state"], c["ended_with"], c["review"]),
                         (1, DAYS[1], DAYS[3], "returned", "coach", None))

    def test_a_case_ended_by_another_absence_without_a_game_played_is_ended(self):
        reports = [report(DAYS[1], [("Brown, Jaylen", "BOS", DAYS[1], "out", "injury", "ankle")]),
                   report(DAYS[2], [("Brown, Jaylen", "BOS", DAYS[2], "out", "non_medical", None)])]
        result, _, _ = run(reports, {1: [DAYS[0]]})
        c = case(result, "Jaylen Brown")
        self.assertEqual((c["state"], c["returned"], c["ended_with"], c["review"]), ("ended", None, "non_medical", None))

    def test_a_team_is_judged_by_the_latest_report_that_covered_its_games(self):
        sched = pd.DataFrame(dict(game_date=pd.to_datetime(["2026-11-04", "2026-11-05"]), home=["BOS", "LAL"], away=["NYK", "GSW"]))
        first, second = "2026-11-04T22:00:00+00:00", "2026-11-05T22:00:00+00:00"
        reports = pd.DataFrame(dict(report_at=[first, first, second], game_date=["2026-11-04", "2026-11-05", "2026-11-05"]))
        # the second report lists only the next day's game, and Golden State hadn't submitted to it
        got = cases.latest_reports(reports, sched, skip={(second, "2026-11-05", "GSW")})
        self.assertEqual(got, {"BOS": first, "NYK": first, "LAL": second, "GSW": first})

    def test_game_days_without_a_report_are_found_within_the_window(self):
        sched, _ = season({})
        now = datetime.fromisoformat("2026-11-11T02:00:00+00:00")   # the evening of November 10, Eastern
        self.assertEqual([d.isoformat() for d in cases.missing_days({DAYS[0], DAYS[2]}, sched, now)], [DAYS[1], DAYS[3]])
        self.assertEqual([d.isoformat() for d in cases.missing_days({DAYS[0], DAYS[2]}, sched, now, back=5)], [DAYS[3]])


class Leagues(unittest.TestCase):
    def test_the_wnba_between_seasons_has_no_cases_and_no_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            got = cases.league_part("wnba", Path(tmp), datetime.fromisoformat("2026-11-20T12:00:00+00:00"), refresh=False)
        self.assertEqual((got["season"], got["source"], got["cases"]), (None, "wnba-official", []))

    def test_only_the_seasons_reports_are_used(self):
        sched, _ = season({})
        inside = f"{DAYS[1]}T22:00:00+00:00"
        self.assertEqual(list(cases.in_season({"2026-06-01T21:00:00+00:00": {}, inside: {}}, sched)), [inside])

    def test_each_league_is_built_on_its_own_and_a_failure_is_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "cases.json"
            with self.assertRaises(RuntimeError):   # no reports or snapshots to build from: flagged, after saving the rest
                cases.export(Path(tmp) / "archive", out, now=datetime.fromisoformat("2026-11-20T12:00:00+00:00"), refresh=False,
                             log=lambda *a, **k: None)
            saved = json.loads(out.read_text(encoding="utf-8"))["leagues"]
        self.assertEqual(sorted(saved), ["nba", "ncaa_mbb", "wnba"])
        self.assertIn("note", saved["wnba"])
        for league in ("nba", "ncaa_mbb"):
            self.assertIn("error", saved[league])
            self.assertNotIn("NameError", saved[league]["error"])

    def test_case_ids_carry_the_league(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.json"
            path.write_text(json.dumps(report(DAYS[1], [("Brown, Jaylen", "BOS", DAYS[1], "out", "injury", "ankle")])), encoding="utf-8")
            observed, _ = cases.observed_reports(Path(tmp))
        sched, pg = season({1: [DAYS[0], DAYS[2]]})
        result = cases.build(observed, pg, sched, datetime.fromisoformat("2026-11-12T23:45:00+00:00"), league="wnba")
        self.assertEqual([c["id"] for c in result["cases"]], [f"wnba-1-{DAYS[1].replace('-', '')}"])


if __name__ == "__main__":
    unittest.main()
