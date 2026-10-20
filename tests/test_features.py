import unittest

import numpy as np
import pandas as pd

from injury_risk import features, labels


def season_of(player, start, n, minutes=30.0, every=2, injury_at=None):
    rows = []
    for i in range(n):
        day = pd.Timestamp(start) + pd.Timedelta(days=every * i)
        absence = "injury" if injury_at is not None and i == injury_at else "played"
        rows.append(dict(player_id=player, game_id=f"{player}-{start}-{i}", game_date=day, team="AAA", season=2024,
                         absence=absence, minutes=minutes + (i % 3) if absence == "played" else 0.0, starter=True,
                         fga=10.0, fta=4.0, tov=2.0, reb=6.0, oreb=1.0, pf=2.0, blk=1.0, stl=1.0, ast=3.0,
                         reason="Injury/Illness - Left Ankle; Sprain" if absence == "injury" else None,
                         reason_class="injury" if absence == "injury" else None, report_status=None,
                         region="ankle" if absence == "injury" else None,
                         injury_type="ligament" if absence == "injury" else None))
    return pd.DataFrame(rows)


class LeakageTest(unittest.TestCase):
    def test_future_games_do_not_change_past_features(self):
        early = season_of(1, "2024-01-01", 30, injury_at=12)
        later = season_of(1, "2024-03-15", 20, injury_at=5)
        full = pd.concat([early, later], ignore_index=True)
        f_early = features.player_features(early, labels.find_onsets(early))
        f_full = features.player_features(full, labels.find_onsets(full))
        common = f_early.index
        cols = [c for c in f_early.columns if c in f_full.columns]
        pd.testing.assert_frame_equal(f_early[cols], f_full.loc[common, cols], check_dtype=False)

    def test_workload_windows_exclude_the_game_itself(self):
        d = season_of(2, "2024-01-01", 10, minutes=30.0, every=1)
        f = features.player_features(d, labels.find_onsets(d))
        self.assertTrue(np.isnan(f.iloc[0]["min_prev1"]))
        self.assertEqual(f.iloc[0]["min_7d"], 0.0)
        # day 8 (index 7): previous seven days hold games 0-6
        self.assertAlmostEqual(f.iloc[7]["min_7d"], d["minutes"].iloc[0:7].sum())
        self.assertEqual(f.iloc[7]["games_7d"], 7)

    def test_history_counts_only_earlier_injuries(self):
        d = season_of(3, "2024-01-01", 20, injury_at=10)
        f = features.player_features(d, labels.find_onsets(d))
        played = d[d["absence"] == "played"]
        before = played["game_date"] <= pd.Timestamp("2024-01-21")
        self.assertTrue((f.loc[played.index[before], "inj_365"] == 0).all())
        self.assertTrue((f.loc[played.index[~before], "inj_365"] == 1).all())
        self.assertEqual(f.loc[played.index[~before][0], "games_since_return"], 0)


if __name__ == "__main__":
    unittest.main()
