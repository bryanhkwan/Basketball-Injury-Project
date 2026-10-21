import unittest

import numpy as np
import pandas as pd

from injury_risk import validation as V


class TwoByTwoTest(unittest.TestCase):
    def test_counts_and_direction(self):
        flagged = np.array([True] * 10 + [False] * 40)
        said = np.array([True] * 6 + [False] * 4 + [True] * 2 + [False] * 38)
        row = V.two_by_two(flagged, said)
        self.assertEqual((row["flagged"], row["flagged_said"], row["unflagged"], row["unflagged_said"]), (10, 6, 40, 2))
        self.assertGreater(row["odds_ratio"], 1)
        self.assertLess(row["p"], 0.01)

    def test_an_empty_side_gives_no_test(self):
        row = V.two_by_two(np.zeros(5, dtype=bool), np.ones(5, dtype=bool))
        self.assertTrue(np.isnan(row["p"]))


class CompareTest(unittest.TestCase):
    def test_a_kind_the_model_ranks_higher_shows_a_positive_difference(self):
        rng = np.random.default_rng(1)
        neg = rng.uniform(0, 1, 2000)
        high = pd.DataFrame(dict(player_id=np.arange(60) % 30, risk=rng.uniform(0.5, 1, 60),
                                 onset_date=pd.date_range("2025-01-01", periods=60)))
        low = pd.DataFrame(dict(player_id=100 + np.arange(60) % 30, risk=rng.uniform(0, 0.6, 60),
                                onset_date=pd.date_range("2025-01-01", periods=60)))
        row = V.compare(high, low, neg, reps=50)
        self.assertGreater(row["auc_a"], 0.7)
        self.assertLess(row["auc_b"], 0.4)
        self.assertGreater(row["lo"], 0)
        self.assertEqual(row["injuries_a"], 60)


if __name__ == "__main__":
    unittest.main()
