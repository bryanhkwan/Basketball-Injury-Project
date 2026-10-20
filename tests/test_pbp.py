import unittest

import numpy as np

from injury_risk import features
from injury_risk.pbp import _elapsed, _transition_shots


class ClockTest(unittest.TestCase):
    def test_elapsed_time_through_overtime(self):
        t, end = _elapsed(np.array([1, 4, 5, 6]), np.array([720.0, 0.0, 300.0, 100.0]))
        self.assertEqual(t.tolist(), [0.0, 2880.0, 2880.0, 3380.0])
        self.assertEqual(end.tolist(), [720, 2880, 3180, 3480])


class TransitionTest(unittest.TestCase):
    def run_plays(self, plays):
        """plays: [(team, seconds elapsed, action_type, description, is field goal)]"""
        team, t, atype, desc, fg = zip(*plays)
        return _transition_shots(np.zeros(len(plays)), np.array(team), np.array(t, dtype=float),
                                 np.array(atype, dtype=object), np.array(desc, dtype=object), np.array(fg)).tolist()

    def test_defensive_rebound_then_quick_shot(self):
        out = self.run_plays([(1, 10, "Missed Shot", "MISS A 3PT", True), (2, 11, "Rebound", "B REBOUND", False),
                              (2, 16, "Made Shot", "C Layup", True)])
        self.assertEqual(out, [False, False, True])

    def test_offensive_rebound_is_not_transition(self):
        out = self.run_plays([(1, 10, "Missed Shot", "MISS A", True), (1, 11, "Rebound", "A REBOUND", False),
                              (1, 13, "Made Shot", "A Putback", True)])
        self.assertEqual(out, [False, False, False])

    def test_steal_counts_and_slow_offense_does_not(self):
        out = self.run_plays([(2, 50, "", "D STEAL (1 STL)", False), (2, 54, "Made Shot", "D Dunk", True),
                              (1, 60, "Missed Shot", "MISS E", True), (2, 61, "Rebound", "F REBOUND", False),
                              (2, 75, "Missed Shot", "MISS F 3PT", True)])
        self.assertEqual(out, [False, True, False, False, False])


class SeparationTest(unittest.TestCase):
    def test_game_itself_never_feeds_a_before_game_score(self):
        before = set(features.ALL) | set(features.PBP) | set(features.PREGAME)
        self.assertFalse(before & set(features.CURRENT))


if __name__ == "__main__":
    unittest.main()
