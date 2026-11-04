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


def season(played):
    """A schedule and player games: ``played`` maps player id -> the game days they played (the rest they sat out)."""
    sched = pd.DataFrame(dict(game_id=[f"g{i}" for i in range(len(DAYS + AHEAD))], season=2027, season_type="regular-season",
                              game_date=pd.to_datetime(DAYS + AHEAD), home="BOS", away="NYK"))
    rows = []
    for pid, (first, last, team) in PLAYERS.items():
        for gid, day in zip(sched["game_id"], DAYS):
            on = day in played.get(pid, DAYS)
            rows.append(dict(game_id=gid, team=team, player_id=pid, first_name=first, last_name=last, season=2027,
                             game_date=pd.Timestamp(day), status="played" if on else "inactive", comment=""))
    return sched, pd.DataFrame(rows)


def report(day, rows, observed=None, sha="a" * 64):
    """An archive file's NBA snapshot: the 5 PM ET report of ``day`` listing (player, team, game day, status, category, region)."""
    at = f"{day}T22:00:00+00:00"
    listed = [dict(id="0" * 24, league="nba", player=p, team=t, game_date=g, status=s, category=c, region=r, injury_type=None,
                   conference=None) for p, t, g, s, c, r in rows]
    return dict(generated_at=observed or at, schema_version=1, sources={"nba-official": dict(snapshot=dict(
        report_at=at, observed_at=observed or f"{day}T23:40:00+00:00", sha256=sha, rows=listed, not_submitted=[], pages_checked=1))})


def run(reports, played, now="2026-11-12T23:45:00+00:00"):
    with tempfile.TemporaryDirectory() as tmp:
        for i, r in enumerate(reports):
            path = Path(tmp) / "2026" / "11" / f"{i:03d}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(r), encoding="utf-8")
        observed, corrected = cases.observed_reports(Path(tmp))
    sched, pg = season(played)
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


if __name__ == "__main__":
    unittest.main()
