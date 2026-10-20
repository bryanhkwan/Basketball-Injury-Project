import unittest

import numpy as np
import pandas as pd

from injury_risk import college as C
from injury_risk import covers

HOME_IDS = (1, 2, 3, 4, 5)
AWAY_IDS = (11, 12, 13, 14, 15)


def game(rows, contest=100):
    """rows: (period, game_seconds, event_type, description, player, team, lineup home, lineup away[, extra dict])"""
    out = []
    for i, row in enumerate(rows):
        period, secs, event, desc, player, team, home, away = row[:8]
        extra = row[8] if len(row) > 8 else {}
        r = dict(contest_id=contest, game_date="2025-01-10", period=period, game_seconds=secs, home_score=0, away_score=0,
                 event_type=event, event_result=extra.get("result", ""), event_description=desc, player_1_id=player,
                 event_team_espn_team_id=team, home_espn_team_id=10, away_espn_team_id=20, is_paint=extra.get("paint", False),
                 is_fastbreak=extra.get("fastbreak", False), foul_class=extra.get("foul", ""), is_flagrant=False,
                 turnover_type=extra.get("tov", ""), order_index=i)
        r.update(zip(C.HOME, home))
        r.update(zip(C.AWAY, away))
        out.append(r)
    return C.prepare(pd.DataFrame(out))


H, A = HOME_IDS, AWAY_IDS
H6 = (6, 2, 3, 4, 5)   # player 6 in for player 1
PLAYS = [
    (1, 0, "Jumpball (held ball)", "", 0, 0, H, A),
    (1, 30, "Layup", "P1, 2pt drivinglayup pointsinthepaint;  made", 1, 10, H, A, {"result": "made", "paint": True}),
    (1, 50, "Two Point Jumper", "P11, 2pt floatingjumpshot  missed", 11, 20, H, A, {"result": "missed"}),
    (1, 52, "Defensive Rebound", "P2, rebound defensive", 2, 10, H, A),
    (1, 60, "Layup", "P3, 2pt tipinlayup  made", 3, 10, H, A, {"result": "made"}),
    (1, 70, "Draw Foul", "P1, foulon", 1, 10, H, A),
    (1, 70, "Commits Foul", "P12, foul personal shooting;2freethrow;", 12, 20, H, A, {"foul": "personal"}),
    (1, 70, "Leaves Game", "P1, substitution out", 1, 10, H, A),       # lineup columns still list P1
    (1, 70, "Enters Game", "P6, substitution in", 6, 10, H, A),
    (1, 80, "Turnover", "P6, turnover lostball", 6, 10, H6, A, {"tov": "lostball"}),
    (1, 80, "Steal", "P13, steal", 13, 20, H6, A),
    (1, 90, "Timeout", "Team, timeout short", 0, 10, H6, A),
    (1, 90, "Leaves Game", "P6, substitution out", 6, 10, H6, A),
    (1, 90, "Enters Game", "P1, substitution in", 1, 10, H6, A),
    (1, 100, "Three Point Jumper", "P1, 3pt jumpshot  made", 1, 10, H, A, {"result": "made"}),
    (2, 1200, "Leaves Game", "P1, substitution out", 1, 10, H, A),     # does not start the second half
    (2, 1200, "Enters Game", "P6, substitution in", 6, 10, H, A),
    (2, 1210, "Two Point Jumper", "P6, 2pt jumpshot  missed", 6, 10, H6, A, {"result": "missed"}),
    (2, 2400, "Defensive Rebound", "P11, rebound defensive", 11, 20, H6, A),
]


class CollegePlaysTest(unittest.TestCase):
    def test_play_labels(self):
        plays = C.player_plays(game(PLAYS))
        got = {(r.player_id, r.play) for r in plays.itertuples()}
        for want in [(1, "rim"), (1, "drive"), (11, "drive"), (11, "jumper"), (2, "def_rebound"), (3, "putback"), (3, "rim"),
                     (1, "fouled"), (12, "foul_def"), (6, "tov_handle"), (13, "steal"), (1, "jumper")]:
            self.assertIn(want, got)
        self.assertNotIn((11, "rim"), got)

    def test_defending_a_rim_attack(self):
        ctx = C.context_plays(game(PLAYS))
        opp = ctx[ctx["play"] == "opp_rim"]
        self.assertEqual(sorted(opp.loc[opp["t"] == 30, "player_id"]), list(A))   # P1's layup: the away five defended


class CollegeExitsTest(unittest.TestCase):
    def test_exits_breaks_and_returns(self):
        ex, st, _ = C.exits(game(PLAYS))
        one = ex[ex["player_id"] == 1].sort_values("t")
        self.assertEqual(one["t"].tolist(), [70.0, 1200.0])
        self.assertEqual(one["how"].tolist(), ["substitution", "break"])
        self.assertEqual(one["period"].tolist(), [1, 1])        # the halftime exit belongs to the first half
        self.assertEqual(one["returned"].tolist(), [True, False])
        six = ex[ex["player_id"] == 6]
        self.assertEqual(six["t"].tolist(), [90.0])
        self.assertTrue(six["returned"].iloc[0])
        self.assertEqual(dict(zip(ex["t"], ex["stoppage"]))[90.0], "own timeout")
        self.assertEqual(dict(zip(ex["t"], ex["stoppage"]))[70.0], "foul")
        minutes = st.assign(m=(st["end_t"] - st["start_t"]) / 60).groupby("player_id")["m"].sum()
        self.assertAlmostEqual(minutes[1], (70 + (1200 - 90)) / 60)
        self.assertAlmostEqual(minutes[6], (20 + 1200) / 60)

    def test_out_and_back_in_at_one_stoppage(self):
        rows = PLAYS[:8] + [(1, 70, "Enters Game", "P1, substitution in", 1, 10, H, A)] + [(1, 100, "Two Point Jumper", "x", 1, 10, H, A)]
        ex, _, _ = C.exits(game(rows))
        self.assertNotIn(70.0, ex.loc[ex["player_id"] == 1, "t"].tolist())


class CollegeRunsTest(unittest.TestCase):
    def setUp(self):
        dates = pd.to_datetime(["2025-01-01", "2025-01-04", "2025-01-08", "2025-01-11", "2025-01-15"])
        rows = []
        for k, d in enumerate(dates):
            rows.append(dict(season=2025, team_id=10, player_id=2, contest_id=k, game_date=d, mins=30.0))   # plays every game
            if k not in (2, 3):
                rows.append(dict(season=2025, team_id=10, player_id=1, contest_id=k, game_date=d, mins=30.0))
        self.boxes = pd.DataFrame(rows)

    def test_missed_game_runs(self):
        r = C.runs(self.boxes)
        self.assertEqual(len(r), 1)
        row = r.iloc[0]
        self.assertEqual((row["player_id"], row["prev_game"], row["first_missed"], row["games_missed"]), (1, 1, 2, 2))

    def test_labels(self):
        r = C.runs(self.boxes)
        listing = lambda **kw: dict(dict(season=2025, player_id=1, captured=pd.Timestamp("2025-01-09"), note_date=pd.Timestamp("2025-01-05"),  # noqa: E731
                                         part="Ankle", group="ankle", kind="ligament", status="Out", note="sprained ankle", covers_id=7), **kw)
        lab = C.label_runs(r, pd.DataFrame([listing()]))
        self.assertEqual(lab["label"].iloc[0], "injury")
        lab = C.label_runs(r, pd.DataFrame([listing(part="Personal", group=None, note="personal reasons")]))
        self.assertEqual(lab["label"].iloc[0], "not injury")
        far = listing(captured=pd.Timestamp("2025-02-20"), note_date=pd.Timestamp("2025-02-18"))
        self.assertEqual(C.label_runs(r, pd.DataFrame([far]))["label"].iloc[0], "none")


class ReviewFixesTest(unittest.TestCase):
    def test_bench_player_logged_in_and_out_at_the_half_is_not_an_exit(self):
        rows = PLAYS[:13] + [(1, 90, "Enters Game", "P1, substitution in", 1, 10, H6, A),
                             (1, 100, "Three Point Jumper", "P1, 3pt jumpshot  made", 1, 10, H, A, {"result": "made"}),
                             (2, 1200, "Enters Game", "P6, substitution in", 6, 10, H, A),      # logged in...
                             (2, 1200, "Leaves Game", "P6, substitution out", 6, 10, H, A),     # ...and straight out
                             (2, 1210, "Two Point Jumper", "P2, 2pt jumpshot  missed", 2, 10, H, A, {"result": "missed"}),
                             (2, 2400, "Defensive Rebound", "P11, rebound defensive", 11, 20, H, A)]
        ex, _, _ = C.exits(game(rows))
        six = ex[ex["player_id"] == 6].sort_values("t")
        self.assertEqual(six["t"].tolist(), [90.0])            # his real last exit, not a halftime one
        self.assertFalse(six["returned"].iloc[0])

    def test_out_and_back_in_at_the_half_is_not_an_exit(self):
        rows = PLAYS[:15] + [(2, 1200, "Leaves Game", "P2, substitution out", 2, 10, H, A),
                             (2, 1200, "Enters Game", "P2, substitution in", 2, 10, H, A),
                             (2, 1210, "Two Point Jumper", "P2, 2pt jumpshot  missed", 2, 10, H, A, {"result": "missed"}),
                             (2, 2400, "Defensive Rebound", "P11, rebound defensive", 11, 20, H, A)]
        ex, _, _ = C.exits(game(rows))
        self.assertFalse((ex["player_id"] == 2).any())

    def test_names_with_punctuation_match(self):
        self.assertEqual(C._person("N'Faly Dante"), C._person("n-faly-dante"))
        self.assertEqual(C._person("J.J. Starling"), C._person("j-j-starling"))
        self.assertEqual(C._person("Howard Fleming Jr."), C._person("howard-fleming"))

    def test_held_ball_is_a_stoppage(self):
        rows = [(1, 0, "Jumpball (held ball)", "", 0, 0, H, A),
                (1, 60, "Jumpball (held ball)", "held ball", 0, 0, H, A),
                (1, 60, "Leaves Game", "P1, substitution out", 1, 10, H, A),
                (1, 60, "Enters Game", "P6, substitution in", 6, 10, H, A),
                (1, 80, "Two Point Jumper", "P6, 2pt jumpshot  missed", 6, 10, H6, A, {"result": "missed"}),
                (2, 2400, "Defensive Rebound", "P11, rebound defensive", 11, 20, H6, A)]
        ex, _, _ = C.exits(game(rows))
        self.assertEqual(ex.loc[ex["player_id"] == 1, "stoppage"].iloc[0], "jump ball")


class StrictLabelsTest(unittest.TestCase):
    def test_one_listing_labels_one_run_and_a_reason_saved_during_the_run_wins(self):
        dates = pd.to_datetime(["2025-01-01", "2025-01-04", "2025-01-08", "2025-01-11", "2025-01-15", "2025-01-18"])
        played = {0, 2, 5}                    # two runs: game 1, then games 3-4
        rows = [dict(season=2025, team_id=10, player_id=1, contest_id=k, game_date=d, mins=30.0) for k, d in enumerate(dates) if k in played]
        rows += [dict(season=2025, team_id=10, player_id=2, contest_id=k, game_date=d, mins=30.0) for k, d in enumerate(dates)]
        r = C.runs(pd.DataFrame(rows))
        base = dict(season=2025, player_id=1, part="Knee", group="knee", kind="other", status="Out", note="knee", covers_id=7)
        knee = dict(base, captured=pd.Timestamp("2025-01-12"), note_date=pd.Timestamp("2025-01-10"))   # saved during the second run
        plan = C.label_runs(r, pd.DataFrame([knee]))
        strict = C.label_runs(r, pd.DataFrame([knee]), strict=True)
        self.assertEqual(plan["label"].tolist(), ["injury", "injury"])     # the plan's rule lets it label both
        self.assertEqual(strict["label"].tolist(), ["none", "injury"])     # strict: only the run it was saved during
        coach = dict(base, part="Coach's decision", group=None, captured=pd.Timestamp("2025-01-12"), note_date=pd.Timestamp("2025-01-12"))
        early = dict(knee, captured=pd.Timestamp("2025-01-07"), note_date=pd.Timestamp("2025-01-07"))
        strict = C.label_runs(r, pd.DataFrame([coach, early]), strict=True)
        self.assertEqual(strict["label"].iloc[1], "not injury")


class StatisticsTest(unittest.TestCase):
    def test_counts_and_exact_test(self):
        from injury_risk import causes
        rng = np.random.default_rng(3)
        strata = np.repeat(np.arange(40), 25)
        y = np.zeros(len(strata), bool)
        y[::25] = True
        x = rng.random(len(strata)) < np.where(y, 0.3, 0.1)
        odds, lo, hi = causes.mantel_haenszel(strata, x, y)
        t = pd.DataFrame({"s": strata, "y": y, "x": x})
        counts = pd.DataFrame({"a": t[t.y & t.x].groupby("s").size(), "b": t[t.y & ~t.x].groupby("s").size(),
                               "c": t[~t.y & t.x].groupby("s").size(), "d": t[~t.y & ~t.x].groupby("s").size()}).fillna(0)
        o2, lo2, hi2, _ = C.mh_counts(*(counts[k].to_numpy() for k in "abcd"))
        self.assertAlmostEqual(odds, o2)
        self.assertAlmostEqual(lo, lo2)
        e = C.exact_test(counts)
        self.assertEqual(e["observed"], int(counts["a"].sum()))
        self.assertTrue(0 < e["p_two_sided"] <= 1 and e["p_one_sided"] <= 1)


class CoversTest(unittest.TestCase):
    def test_groups_and_kinds(self):
        self.assertEqual(covers.group_of("Ankle", "sprained ankle"), "ankle")
        self.assertIsNone(covers.group_of("Undisclosed", ""))
        self.assertIsNone(covers.group_of("Personal", ""))
        self.assertEqual(covers.group_of("Leg", "strained his leg"), "muscle")
        self.assertEqual(covers.group_of("Leg", "broken leg"), "other")
        self.assertEqual(covers.kind_of("He sprained his ankle"), "ligament")
        self.assertEqual(covers.kind_of("He broke his hand"), "bone")


if __name__ == "__main__":
    unittest.main()
