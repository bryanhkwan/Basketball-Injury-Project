import unittest

import numpy as np
import pandas as pd

from injury_risk import moments as M

A = (1, 2, 3, 4, 5, 11, 12, 13, 14, 15)   # player 1 on the floor
B = (6, 2, 3, 4, 5, 11, 12, 13, 14, 15)   # player 6 in for player 1


def game(rows, game_id="0022400001"):
    """rows: (period, seconds left, action_type, sub_type, description, team_id, person_id, is field goal, distance, lineup)"""
    out = []
    for i, (period, left, action, sub, desc, team, person, fg, dist, lineup) in enumerate(rows):
        r = dict(game_id=game_id, order_index=i, period=period, seconds_remaining=float(left), score_home="", score_away="",
                 action_type=action, sub_type=sub, description=desc, team_id=team, is_field_goal=fg, shot_distance=dist,
                 shot_value=3 if "3PT" in desc else (2 if fg else np.nan), person_id=person,
                 player_name=f"P{person}" if 0 < person < 100 else "", player_name_i="")
        r.update(zip(M.ON_COURT, lineup))
        out.append(r)
    return M.prepare(pd.DataFrame(out))


SUB_AND_BACK = [
    (1, 720, "period", "", "Start", 0, 0, 0, np.nan, A),
    (1, 700, "Missed Shot", "Jump Shot", "MISS P11 Jumper", 20, 11, 1, 18, A),
    (1, 698, "Rebound", "Unknown", "P1 REBOUND (Off:0 Def:1)", 10, 1, 0, np.nan, A),
    (1, 690, "Foul", "Personal", "P12 P.FOUL (P1.T1)", 20, 12, 0, np.nan, A),
    (1, 690, "Substitution", "", "SUB: P6 FOR P1", 10, 1, 0, np.nan, A),   # lineup columns still list P1
    (1, 680, "Missed Shot", "Driving Layup Shot", "MISS P2 Driving Layup", 10, 2, 1, 1, A),
    (1, 679, "Rebound", "Unknown", "P2 REBOUND (Off:1 Def:0)", 10, 2, 0, np.nan, B),
    (1, 600, "Timeout", "Regular", "Timeout: Regular", 10, 10, 0, np.nan, B),
    (1, 600, "Substitution", "", "SUB: P1 FOR P6", 10, 6, 0, np.nan, B),
    (1, 590, "Made Shot", "Jump Shot", "P1 18' Jump Shot", 10, 1, 1, 18, A),
    (1, 0, "period", "", "End", 0, 0, 0, np.nan, A),
    (2, 720, "period", "", "Start", 0, 0, 0, np.nan, B),                    # P1 does not start the second period
    (2, 700, "Missed Shot", "Jump Shot", "MISS P6 Jumper", 10, 6, 1, 18, B),
    (2, 0, "period", "", "End", 0, 0, 0, np.nan, B),
]


class PlaysTest(unittest.TestCase):
    def test_rebounds_shots_and_fouls(self):
        plays = M.player_plays(game(SUB_AND_BACK))
        got = {(r.player_id, r.play) for r in plays.itertuples()}
        self.assertIn((1, "def_rebound"), got)      # the other team missed
        self.assertIn((2, "off_rebound"), got)      # his own team missed
        self.assertIn((2, "rim"), got)
        self.assertIn((2, "drive"), got)
        self.assertIn((1, "jumper"), got)
        self.assertIn((12, "foul_def"), got)
        self.assertNotIn((2, "jumper"), got)

    def test_a_three_with_no_distance_is_not_a_rim_shot(self):
        p = game([(1, 720, "period", "", "Start", 0, 0, 0, np.nan, A),
                  (1, 700, "Missed Shot", "Jump Shot", "MISS P3 3PT Jump Shot", 10, 3, 1, 0, A),
                  (1, 0, "period", "", "End", 0, 0, 0, np.nan, A)])
        plays = M.player_plays(p)
        self.assertEqual(plays.loc[plays["player_id"] == 3, "play"].tolist(), ["jumper"])

    def test_fouled_take_fouls_and_turnover_kinds(self):
        p = game([
            (1, 720, "period", "", "Start", 0, 0, 0, np.nan, A),
            (1, 650, "Foul", "Shooting", "P11 S.FOUL", 20, 11, 0, np.nan, A),
            (1, 650, "Free Throw", "Free Throw 1 of 2", "P3 Free Throw 1 of 2", 10, 3, 0, np.nan, A),
            (1, 650, "Free Throw", "Free Throw 2 of 2", "MISS P3 Free Throw 2 of 2", 10, 3, 0, np.nan, A),
            (1, 640, "Free Throw", "Free Throw Technical", "P4 Free Throw Technical", 10, 4, 0, np.nan, A),
            (1, 630, "", "", "P5 STEAL (1 STL)", 10, 5, 0, np.nan, A),
            (1, 620, "Turnover", "Lost Ball", "P2 Lost Ball Turnover", 10, 2, 0, np.nan, A),
            (1, 610, "Turnover", "Bad Pass", "P2 Bad Pass Turnover", 10, 2, 0, np.nan, A),
            (1, 600, "Foul", "Personal Take", "P12 Personal Take Foul", 20, 12, 0, np.nan, A),
            (1, 0, "period", "", "End", 0, 0, 0, np.nan, A),
        ])
        plays = M.player_plays(p)
        by = lambda k: plays.loc[plays["play"] == k, "player_id"].tolist()  # noqa: E731
        self.assertEqual(by("fouled"), [3])
        self.assertEqual(by("steal"), [5])
        self.assertEqual(by("tov_handle"), [2])
        self.assertEqual(by("tov_pass"), [2])
        self.assertEqual(by("take_foul"), [12])
        self.assertEqual(by("foul_def"), [11])


class ExitsTest(unittest.TestCase):
    def test_exit_times_come_from_substitutions_and_breaks(self):
        ex, _ = M.exits(game(SUB_AND_BACK))
        ex = ex.sort_values(["player_id", "t"])
        one = ex[ex["player_id"] == 1]
        self.assertEqual(one["t"].tolist(), [30.0, 720.0])            # the substitution row, then the end of period 1
        self.assertEqual(one["how"].tolist(), ["substitution", "break"])
        self.assertEqual(one["returned"].tolist(), [True, False])
        six = ex[ex["player_id"] == 6]
        self.assertEqual(six["t"].tolist(), [120.0])
        self.assertTrue(six["returned"].iloc[0])                      # started the second period
        self.assertFalse(ex["player_id"].isin([2, 3, 4, 5, 11]).any())  # played throughout: no exits

    def test_out_and_back_in_at_one_stoppage_is_not_an_exit(self):
        rows = [r for r in SUB_AND_BACK]
        rows.insert(5, (1, 690, "Substitution", "", "SUB: P1 FOR P6", 10, 6, 0, np.nan, A))   # straight back in
        ex, _ = M.exits(game(rows))
        self.assertNotIn(30.0, ex.loc[ex["player_id"] == 1, "t"].tolist())

    def test_a_return_the_lineup_columns_miss_still_counts(self):
        rows = [r for r in SUB_AND_BACK[:4]] + [
            (1, 690, "Substitution", "", "SUB: P6 FOR P1", 10, 1, 0, np.nan, A),
            (1, 600, "Substitution", "", "SUB: Unknown FOR P6", 10, 6, 0, np.nan, B),   # name the log cannot match
            (1, 590, "Made Shot", "Jump Shot", "P1 18' Jump Shot", 10, 1, 1, 18, B),    # but P1 is back: he scores
            (1, 500, "Substitution", "", "SUB: P6 FOR P1", 10, 1, 0, np.nan, B),
            (1, 0, "period", "", "End", 0, 0, 0, np.nan, B),
            (2, 720, "period", "", "Start", 0, 0, 0, np.nan, B),
            (2, 0, "period", "", "End", 0, 0, 0, np.nan, B)]
        ex, _ = M.exits(game(rows))
        one = ex[ex["player_id"] == 1].sort_values("t")
        self.assertEqual(one["t"].tolist(), [30.0, 220.0])
        self.assertEqual(one["returned"].tolist(), [True, False])     # his last exit is the later one
        self.assertEqual(ex.loc[ex["player_id"] == 6, "t"].tolist(), [120.0])   # the player going out keeps his exit

    def test_names_match_without_accents_and_from_the_roster(self):
        rows = [(1, 720, "period", "", "Start", 0, 0, 0, np.nan, A),
                (1, 700, "Made Shot", "Jump Shot", "P1 Jumper", 10, 1, 1, 18, A),
                (1, 690, "Substitution", "", "SUB: Jokic FOR P1", 10, 1, 0, np.nan, A),
                (1, 600, "Substitution", "", "SUB: P1 FOR Jokic", 10, 6, 0, np.nan, B),
                (1, 0, "period", "", "End", 0, 0, 0, np.nan, A),
                (2, 720, "period", "", "Start", 0, 0, 0, np.nan, A),
                (2, 0, "period", "", "End", 0, 0, 0, np.nan, A)]
        roster = pd.DataFrame({"game_id": ["0022400001"], "team_id": [10], "player_id": [6], "first_name": ["Nikola"],
                               "last_name": ["Jokić"]})
        ex, st = M.exits(game(rows), roster)
        self.assertEqual(ex.loc[ex["player_id"] == 6, "t"].tolist(), [120.0])
        six = st[st["player_id"] == 6]
        self.assertEqual((six["end_t"] - six["start_t"]).sum(), 90.0)

    def test_in_and_straight_back_out_is_not_an_exit(self):
        rows = [(1, 720, "period", "", "Start", 0, 0, 0, np.nan, A),
                (1, 690, "Substitution", "", "SUB: P6 FOR P1", 10, 1, 0, np.nan, A),
                (1, 690, "Substitution", "", "SUB: P7 FOR P6", 10, 6, 0, np.nan, A),
                (1, 0, "period", "", "End", 0, 0, 0, np.nan, A)]
        ex, _ = M.exits(game(rows))
        self.assertNotIn(6, ex["player_id"].tolist())

    def test_stoppage_labels(self):
        rows = [(1, 720, "period", "", "Start", 0, 0, 0, np.nan, A),
                (1, 650, "Foul", "Shooting", "P11 S.FOUL", 20, 11, 0, np.nan, A),
                (1, 650, "Free Throw", "Free Throw 1 of 2", "MISS P3 Free Throw 1 of 2", 10, 3, 0, np.nan, A),
                (1, 650, "Rebound", "Normal Rebound", "Team Rebound", 10, 1610612700, 0, np.nan, A),
                (1, 650, "Substitution", "", "SUB: P6 FOR P1", 10, 1, 0, np.nan, A),     # between free throws
                (1, 600, "Substitution", "", "SUB: P1 FOR P6", 10, 6, 0, np.nan, B),
                (1, 600, "Timeout", "Regular", "Timeout: Regular", 10, 0, 0, np.nan, B),  # logged after the substitution
                (1, 0, "period", "", "End", 0, 0, 0, np.nan, A),
                (2, 720, "period", "", "Start", 0, 0, 0, np.nan, A),
                (2, 0, "period", "", "End", 0, 0, 0, np.nan, A)]
        ex, _ = M.exits(game(rows))
        got = dict(zip(ex["player_id"], ex["stoppage"]))
        self.assertEqual(got[1], "free throws")
        self.assertEqual(got[6], "own timeout")

    def test_replacement_shooter_marks_a_foul_he_could_not_shoot(self):
        rows = [(1, 720, "period", "", "Start", 0, 0, 0, np.nan, A),
                (1, 650, "Foul", "Shooting", "P11 S.FOUL", 20, 11, 0, np.nan, A),
                (1, 650, "Substitution", "", "SUB: P6 FOR P1", 10, 1, 0, np.nan, A),
                (1, 650, "Free Throw", "Free Throw 1 of 2", "P6 Free Throw 1 of 2", 10, 6, 0, np.nan, B),
                (1, 0, "period", "", "End", 0, 0, 0, np.nan, B),
                (2, 720, "period", "", "Start", 0, 0, 0, np.nan, B),
                (2, 0, "period", "", "End", 0, 0, 0, np.nan, B)]
        ex, _ = M.exits(game(rows))
        one = ex[ex["player_id"] == 1].iloc[0]
        self.assertTrue(one["replaced_shooter"])
        self.assertEqual(one["stoppage"], "foul")


class NullExitTest(unittest.TestCase):
    def test_first_dead_ball_after_the_moment(self):
        p = game(SUB_AND_BACK)
        moments = pd.DataFrame({"game_id": ["0022400001"] * 2, "player_id": [2, 2], "period": [1, 2], "t": [5.0, 730.0],
                                "season": [2025, 2025], "team": [10, 10]})
        n = M.null_exits(p, moments)
        self.assertEqual(n["t"].tolist(), [30.0, 1440.0])   # the foul at 690 left; no dead ball in period 2: its end
        self.assertEqual(n["stoppage"].tolist(), ["foul", "break"])


class TimelineTest(unittest.TestCase):
    def test_counts_and_last_play_match_brute_force(self):
        rng = np.random.default_rng(1)
        n = 400
        events = pd.DataFrame({"game_id": rng.choice(["g1", "g2"], n), "player_id": rng.integers(1, 6, n),
                               "period": rng.integers(1, 3, n), "t": rng.integers(0, 1440, n) / 1.0,
                               "order_index": np.arange(n)})
        moments = pd.DataFrame({"game_id": rng.choice(["g1", "g2", "g3"], 300), "player_id": rng.integers(1, 7, 300),
                                "period": rng.integers(1, 3, 300), "t": rng.integers(0, 1440, 300) / 1.0})
        line = M.Timeline(events)
        for width in (30, 120):
            got = line.count(moments, width)
            for i, m in moments.iterrows():
                e = events[(events["game_id"] == m["game_id"]) & (events["player_id"] == m["player_id"])
                           & (events["period"] == m["period"])]["t"]
                self.assertEqual(got[i], ((e <= m["t"]) & (e > m["t"] - width)).sum())   # (t - W, t]: the edge is out
        when, order = line.last(moments, 120)
        for i, m in moments.iterrows():
            e = events[(events["game_id"] == m["game_id"]) & (events["player_id"] == m["player_id"])
                       & (events["period"] == m["period"]) & (events["t"] <= m["t"]) & (events["t"] > m["t"] - 120)]
            if len(e):
                best = e.sort_values(["t", "order_index"]).iloc[-1]
                self.assertEqual((when[i], order[i]), (int(best["t"] * 10), best["order_index"]))
            else:
                self.assertEqual(when[i], -1)


class RulesTest(unittest.TestCase):
    def test_injury_exit_rules(self):
        base = dict(t=1200.0, game_end=2880.0, margin=5.0, ejected=False, fouls=2, usual=30.0, minutes=12.0)
        rows = pd.DataFrame([base,
                             {**base, "t": 2700.0},           # under 6 minutes left
                             {**base, "margin": 20.0},        # blowout
                             {**base, "fouls": 6},            # fouled out
                             {**base, "minutes": 25.0},       # not a short game
                             {**base, "usual": 8.0}])         # a deep reserve
        self.assertEqual(M.is_injury_exit(rows).tolist(), [True, False, False, False, False, False])
        self.assertEqual(M.early_exit_rules(rows, None).tolist(), [True, False, False, False, True, False])

    def test_benjamini_hochberg(self):
        q = M.benjamini_hochberg([0.01, 0.04, 0.03, np.nan, 0.5])
        self.assertTrue(np.allclose(q[[0, 1, 2, 4]], [0.04, 0.16 / 3, 0.16 / 3, 0.5]))   # 0.03 takes 0.04's q
        self.assertTrue(np.isnan(q[3]))


if __name__ == "__main__":
    unittest.main()
