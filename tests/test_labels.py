import unittest

import pandas as pd

from injury_risk import labels


def games(player, rows, team="AAA", season=2024):
    """rows: [(date, absence, reason_or_None)]"""
    out = []
    for i, (day, absence, reason) in enumerate(rows):
        out.append(dict(player_id=player, game_date=pd.Timestamp(day), game_id=f"{player}-{i}", team=team, season=season,
                        absence=absence, reason=reason, region="ankle" if absence == "injury" else None,
                        injury_type="ligament" if absence == "injury" else None))
    return pd.DataFrame(out)


class OnsetTest(unittest.TestCase):
    def test_simple_injury_run(self):
        pg = games(1, [("2024-01-01", "played", None), ("2024-01-03", "played", None),
                       ("2024-01-05", "injury", "Injury/Illness - Left Ankle; Sprain"), ("2024-01-07", "injury", None),
                       ("2024-01-09", "played", None)])
        o = labels.find_onsets(pg)
        self.assertEqual(len(o), 1)
        self.assertEqual(o.loc[0, "onset_date"], pd.Timestamp("2024-01-05"))
        self.assertEqual(o.loc[0, "games_missed"], 2)
        self.assertEqual(o.loc[0, "return_date"], pd.Timestamp("2024-01-09"))
        self.assertTrue(o.loc[0, "new_injury"])

    def test_continuing_absence_is_not_new(self):
        pg = games(2, [("2024-01-01", "injury", "x"), ("2024-01-03", "injury", "x")])
        o = labels.find_onsets(pg)
        self.assertFalse(o.loc[0, "new_injury"])

    def test_late_scratch_moves_onset_back_one_game(self):
        pg = games(3, [("2024-01-01", "played", None), ("2024-01-03", "unknown", None), ("2024-01-05", "injury", "x")])
        o = labels.find_onsets(pg)
        self.assertEqual(o.loc[0, "onset_date"], pd.Timestamp("2024-01-03"))
        self.assertEqual(o.loc[0, "games_missed"], 2)

    def test_long_gap_since_playing_is_not_new(self):
        pg = games(4, [("2024-01-01", "played", None), ("2024-01-21", "injury", "x")])
        self.assertFalse(labels.find_onsets(pg).loc[0, "new_injury"])

    def test_coach_decision_breaks_a_run(self):
        pg = games(5, [("2024-01-01", "played", None), ("2024-01-03", "coach", None), ("2024-01-05", "injury", "x")])
        o = labels.find_onsets(pg)
        self.assertEqual(o.loc[0, "onset_date"], pd.Timestamp("2024-01-05"))

    def test_unknown_absences_alone_are_not_injuries(self):
        pg = games(6, [("2024-01-01", "played", None), ("2024-01-03", "unknown", None), ("2024-01-05", "played", None)])
        self.assertEqual(len(labels.find_onsets(pg)), 0)


class TargetTest(unittest.TestCase):
    def test_window_counts_onsets_after_the_game_only(self):
        pg = games(1, [("2024-01-01", "played", None), ("2024-01-03", "played", None),
                       ("2024-01-05", "injury", "x"), ("2024-01-20", "played", None)])
        onsets = labels.find_onsets(pg)
        rows = pg[pg["absence"] == "played"]
        y2 = labels.targets(rows, onsets, pg, horizon=2)
        y7 = labels.targets(rows, onsets, pg, horizon=7)
        self.assertEqual(y2.tolist(), [0, 1, 0])     # 2024-01-03 is 2 days before the onset
        self.assertEqual(y7.tolist(), [1, 1, 0])
        obs = labels.observable(rows, pg, horizon=7)
        self.assertEqual(obs.tolist(), [True, True, False])   # nothing follows 2024-01-20

    def test_window_in_team_games(self):
        pg = games(1, [("2024-01-01", "played", None), ("2024-01-03", "played", None), ("2024-01-04", "played", None),
                       ("2024-01-05", "injury", "x"), ("2024-01-07", "played", None), ("2024-01-09", "played", None)])
        onsets = labels.find_onsets(pg)
        rows = pg[pg["absence"] == "played"]
        y1, seen1 = labels.targets_in_games(rows, onsets, pg, 1)
        y3, seen3 = labels.targets_in_games(rows, onsets, pg, 3)
        self.assertEqual(y1.tolist(), [0, 0, 1, 0, 0])        # only the game right before the injury
        self.assertEqual(y3.tolist(), [1, 1, 1, 0, 0])
        self.assertEqual(seen3.tolist(), [True, True, True, False, False])    # three later games needed


if __name__ == "__main__":
    unittest.main()
