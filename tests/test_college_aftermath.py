import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from injury_risk import aftermath as A
from injury_risk import college_aftermath as C

DAYS = pd.date_range("2021-11-10", periods=10, freq="3D")


def box(rows):
    """ESPN-like box score rows: (athlete, name, team, game number, minutes, won)."""
    out = []
    for a, name, team, g, mins, won in rows:
        out.append(dict(season=2022, season_type=2, game_id=team * 100 + g, game_date=DAYS[g - 1], athlete_id=a, athlete_display_name=name,
                        team_id=team, minutes=mins, points=10.0 if mins else None, rebounds=4.0, assists=2.0, steals=1.0, blocks=0.0,
                        turnovers=1.0, field_goals_attempted=8.0, free_throws_attempted=2.0, starter=True, team_winner=won))
    b = pd.DataFrame(out)
    b["key"] = b["athlete_display_name"].str.lower().str.replace(" ", "")
    return b


class GroupTest(unittest.TestCase):
    def test_the_notes_diagnosis_decides_first(self):
        self.assertEqual(C.group_of("Torn ACL", "region:knee"), "acl")
        self.assertEqual(C.group_of("Fracture", "region:hand"), "fracture")
        self.assertEqual(C.group_of(None, "region:ankle"), "ankle")
        self.assertIsNone(C.group_of(None, "any"))

    def test_season_of(self):
        self.assertEqual((C.season_of("2021-11-10"), C.season_of("2022-03-01")), (2022, 2022))


class GameLogTest(unittest.TestCase):
    def setUp(self):
        # player 100 plays games 1-3 and 9-10 and misses 4-8; player 200, a teammate, plays them all
        rows = [(100, "Al Bee", 1, g, 0 if 4 <= g <= 8 else 30, g % 2 == 0) for g in range(1, 11)]
        rows += [(200, "Cy Dee", 1, g, 25, g % 2 == 0) for g in range(1, 11)]
        rows += [(300, "Ed Fay", 1, g, 0 if g == 4 else 20, g % 2 == 0) for g in range(1, 11)]   # misses game 4 only
        self.b = box(rows)
        self.log = C.game_log(self.b)

    def test_a_row_for_every_team_game(self):
        mine = self.log[self.log["player_id"] == 100]
        self.assertEqual(len(mine), 10)
        self.assertEqual((mine["status"] == "played").sum(), 5)
        self.assertEqual(set(mine["season_type"]), {"regular-season"})

    def test_how_often_the_team_won(self):
        self.assertAlmostEqual(C.Teams(self.b).won(1, DAYS[0], DAYS[4]), 0.5)   # games 1-4: two wins

    def test_the_run_of_missed_games(self):
        logs = A.Logs(self.log)
        schedule = {(2022, 1): DAYS.to_numpy()}
        people = [dict(id=7, n="Al Bee", inj=[[str(DAYS[3].date() - pd.Timedelta(days=1)), str(DAYS[5].date()), 2022, "Ankle", "ankle",
                                               None, "Out", 5, True, 3, None, None, False, "region:ankle"]])]
        ep = C.episodes(logs, people, {(7, 2022): 100}, {(7, 2022): 1}, schedule)
        e = ep.iloc[0]
        self.assertEqual((e["last_game"], e["back"], e["games_missed"]), (DAYS[2], DAYS[8], 5))
        self.assertEqual((e["group"], bool(e["season_over"])), ("ankle", False))
        self.assertEqual(e["hurt"], DAYS[2])   # the first missed game came three days after the last one played

    def test_short_injuries_count_only_when_serious(self):
        logs = A.Logs(self.log)
        schedule = {(2022, 1): DAYS.to_numpy()}
        entry = [str(DAYS[3].date()), str(DAYS[3].date()), 2022, "Knee", "knee", None, "Out", 1, True, 1]
        args = ({(7, 2022): 300, (8, 2022): 200}, {(7, 2022): 1, (8, 2022): 1}, schedule)
        short = [dict(id=7, n="Ed Fay", inj=[entry + [None, None, False, "region:knee"]])]
        torn = [dict(id=7, n="Ed Fay", inj=[entry + ["Torn ACL", "left", True, "acl"]])]
        played_through = [dict(id=8, n="Cy Dee", inj=[entry + ["Torn ACL", "left", True, "acl"]])]
        self.assertTrue(C.episodes(logs, short, *args).empty)              # one game missed
        e = C.episodes(logs, torn, *args).iloc[0]                          # the same game, but a torn ACL
        self.assertEqual((e["group"], e["games_missed"]), ("acl", 1))
        self.assertTrue(C.episodes(logs, played_through, *args).empty)     # no game missed around the listing


class NbaTest(unittest.TestCase):
    def test_one_career_of_the_name_links_to_the_debut(self):
        b = pd.concat([box([(10, "John Smith", 1, 1, 30, True)]).assign(season=2022),
                       box([(11, "Max Ray", 2, 1, 30, True)]).assign(season=2021),
                       box([(12, "Max Ray", 3, 1, 30, True)]).assign(season=2024)])
        pro = dict(players=[dict(id=1, n="John Smith", tm=[[2023, "BOS"]]), dict(id=2, n="Max Ray", tm=[[2023, "LAL"]]),
                            dict(id=3, n="Old Hand", tm=[[2019, "NYK"]])])
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "nba.json").write_text(json.dumps(pro), encoding="utf-8")
            keep, C.PROFILES = C.PROFILES, Path(tmp)
            try:
                debuts = C.nba_debuts(b)
            finally:
                C.PROFILES = keep
        # John Smith's college career ended the season before his debut; another Max Ray was still in college after it
        self.assertEqual(debuts, {10: 2023})


if __name__ == "__main__":
    unittest.main()
