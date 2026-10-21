import unittest

import numpy as np
import pandas as pd

from injury_risk import profiles as P


def onsets(rows):
    cols = ["player_id", "onset_date", "season", "reason", "region", "injury_type", "games_missed", "return_date", "new_injury",
            "days_since_played"]
    o = pd.DataFrame(rows, columns=cols)
    for c in ("onset_date", "return_date"):
        o[c] = pd.to_datetime(o[c])
    return o


def games(dates, played, listed=None):
    d = np.array(pd.to_datetime(dates), dtype="datetime64[ns]")
    p = np.array(played, dtype=bool)
    why = np.array(listed or [None] * len(dates), dtype=object)
    return d, p, ~p, why


class WordsTest(unittest.TestCase):
    def test_covers_shorthand_in_plain_words(self):
        self.assertEqual(P.plain_status("Ques Sat"), "Questionable")
        self.assertEqual(P.plain_status("Doub Mon"), "Doubtful")
        self.assertEqual(P.plain_status("out for season"), "Out for the season")
        self.assertEqual(P.plain_status("Out indefinitely"), "Out indefinitely")
        self.assertEqual(P.plain_status("Early March"), "Expected back early March")
        self.assertEqual(P.plain_status("whatever"), "Listed")

    def test_named_kinds_before_body_regions(self):
        self.assertEqual(P.kind_of("Injury/Illness - Left Knee; Sprain/ACL tear", "knee", "ligament"), "acl")
        self.assertEqual(P.kind_of("Injury/Illness - Torn right anterior cruciate ligament", "other", "ligament"), "acl")
        self.assertEqual(P.kind_of("Injury/Illness - Right Achilles Tendon; Tear", "achilles", "muscle_tendon"), "achilles")
        self.assertEqual(P.kind_of("Injury/Illness - Left Achilles Tendon; Soreness", "achilles", "soreness"), "region:achilles")
        self.assertEqual(P.kind_of("Injury/Illness - Left Ankle; Sprain", "ankle", "ligament"), "ankle_sprain")

    def test_names_from_covers_addresses(self):
        self.assertEqual(P.name_from_slug("bryan-trimble-jr."), "Bryan Trimble Jr.")
        self.assertEqual(P.name_from_slug("james-wiseman-iii"), "James Wiseman III")


class GamesMissedTest(unittest.TestCase):
    def test_counts_until_the_next_game_played_and_skips_other_absences(self):
        d = np.array(pd.to_datetime(["2025-01-01", "2025-01-03", "2025-01-05", "2025-01-07", "2025-01-09"]), dtype="datetime64[ns]")
        played = np.array([False, False, False, True, False])
        hurt = np.array([True, False, True, False, True])     # the second game was a coach's decision
        self.assertEqual(P.box_missed(d, played, hurt, pd.Timestamp("2025-01-01")), 2)
        self.assertEqual(P.box_missed(d, played, hurt, pd.Timestamp("2025-01-01"), pd.Timestamp("2025-01-04")), 1)   # next injury
        self.assertIsNone(P.box_missed(d, played, hurt, pd.Timestamp("2025-02-01")))                                # no roster


class CollegeLinkTest(unittest.TestCase):
    def test_a_namesake_at_another_school_is_someone_else(self):
        pro = dict(players=[dict(id=1, n="Test Williams", tm=[[2023, "TST"]], gp=[[2023, 60]])])
        # the box scores give a player a new id each season; in 2020 two players have the name, and theirs is the one at
        # the school they played for next
        careers = pd.DataFrame([dict(season=2020, player_id=500, name="Test Williams", team="Far State", games=20),
                                dict(season=2020, player_id=501, name="Test Williams", team="Near College", games=25),
                                dict(season=2021, player_id=601, name="Test Williams", team="Near College", games=30),
                                dict(season=2022, player_id=602, name="Test Williams", team="Near College", games=31)])
        careers["key"] = careers["name"].map(P.college._person)
        far, near = dict(id=10, ncaa={2020: 500}, inj=[]), dict(id=11, ncaa={2020: 501}, inj=[])
        link = P.college_links(pro, dict(people=[far, near]), careers)[1]
        self.assertEqual(link["person"]["id"], 11)
        self.assertEqual((link["school"], link["seasons"], link["games"]), ("Near College", 3, 86))

    def test_a_transfer_keeps_every_season(self):
        pro = dict(players=[dict(id=2, n="Sample Transfer", tm=[[2023, "TST"]], gp=[[2023, 60]])])
        careers = pd.DataFrame([dict(season=2020, player_id=700, name="Sample Transfer", team="First College", games=28),
                                dict(season=2022, player_id=702, name="Sample Transfer", team="Second College", games=33)])
        careers["key"] = careers["name"].map(P.college._person)
        person = dict(id=12, ncaa={2020: 700}, inj=[])
        link = P.college_links(pro, dict(people=[person]), careers)[2]
        self.assertEqual((link["person"]["id"], link["school"], link["seasons"], link["games"]), (12, "Second College", 2, 61))


class InjuriesTest(unittest.TestCase):
    def test_care_and_listings_before_a_return_join_the_injury(self):
        o = onsets([
            [1, "2025-01-01", 2025, "Injury/Illness - Left Knee; Torn ACL", "knee", "ligament", 2, None, True, 2],
            [1, "2025-01-20", 2025, "Injury/Illness - Left Knee; Injury Recovery", "knee", "surgery", 3, None, False, 20],
        ])
        g = {1: games(["2025-01-01", "2025-01-03", "2025-01-20", "2025-01-22", "2025-01-24", "2025-01-26"],
                      [False, False, False, False, False, True])}
        out = P.nba_injuries(o, g)
        self.assertEqual(len(out), 1)
        self.assertEqual(out.loc[0, "kind"], "acl")
        self.assertEqual(out.loc[0, "listings"], 2)
        self.assertEqual(out.loc[0, "games_missed"], 5)
        self.assertEqual(out.loc[0, "return_date"], pd.Timestamp("2025-01-26"))

    def test_a_new_injury_after_a_return_is_its_own(self):
        o = onsets([
            [1, "2025-01-01", 2025, "Injury/Illness - Left Knee; Contusion", "knee", "impact", 1, "2025-01-03", True, 2],
            [1, "2025-02-01", 2025, "Injury/Illness - Right Knee; ACL repair", "knee", "surgery", 1, None, False, 20],
        ])
        g = {1: games(["2025-01-01", "2025-01-03", "2025-02-01"], [False, True, False])}
        out = P.nba_injuries(o, g)
        self.assertEqual(list(out["kind"]), ["region:knee", "acl"])

    def test_a_long_absence_listed_for_another_region_is_two_injuries(self):
        listed = [("Injury/Illness - Left Knee; ACL rehabilitation", "knee", "surgery")] * 3 + \
                 [("Injury/Illness - Right Achilles; Tear", "achilles", "muscle_tendon")] * 6
        dates = pd.date_range("2025-01-01", periods=9, freq="2D").strftime("%Y-%m-%d").tolist() + ["2025-02-01"]
        o = onsets([[1, dates[0], 2025, listed[0][0], "knee", "surgery", 9, dates[-1], True, 2]])
        g = {1: games(dates, [False] * 9 + [True], listed + [None])}
        out = P.nba_injuries(o, g)
        self.assertEqual(list(out["region"]), ["knee", "achilles"])
        self.assertEqual(list(out["games_missed"]), [3, 6])
        self.assertTrue(pd.isna(out.loc[0, "return_date"]))           # still out when the second injury took over
        self.assertEqual(out.loc[1, "return_date"], pd.Timestamp("2025-02-01"))


if __name__ == "__main__":
    unittest.main()
