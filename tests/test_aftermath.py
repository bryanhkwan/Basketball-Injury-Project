import unittest

import numpy as np
import pandas as pd

from injury_risk import aftermath as A


def league(players=30, start="2019-01-01", end="2021-12-31"):
    """Every player plays every other day, 30 minutes, the same line."""
    days = pd.date_range(start, end, freq="2D")
    pg = pd.DataFrame([dict(player_id=pid, game_date=d, season=d.year, season_type="regular-season", status="played", team="AAA",
                            minutes=30.0, pts=15.0, reb=6.0, ast=3.0, stl=1.0, blk=1.0, tov=2.0, fga=12.0, fta=4.0, starter=True,
                            rim_fga=4.0, dunk_fga=1.0) for pid in range(1, players + 1) for d in days])
    return pg


def births(logs):
    return np.array([np.datetime64("1995-01-01") + np.timedelta64(int(pid) * 20, "D") for pid in logs.ids], dtype="datetime64[ns]")


class GroupTest(unittest.TestCase):
    def test_the_news_label_comes_first(self):
        self.assertEqual(A.group_of("Torn ACL", "region:knee", "knee"), "acl")

    def test_without_a_label_the_listing_decides(self):
        self.assertEqual(A.group_of(None, "ankle_sprain", "ankle"), "ankle")
        self.assertEqual(A.group_of("Hip injury", "groin", "groin"), "muscle")

    def test_a_bruise_is_not_a_fracture(self):
        self.assertIsNone(A.group_of("Bone bruise", "hand_fracture", "hand"))

    def test_other_falls_back_only_on_a_named_injury(self):
        self.assertEqual(A.group_of("Other", "acl", "knee"), "acl")
        self.assertIsNone(A.group_of("Other", "foot_fracture", "foot"))

    def test_a_label_can_need_its_body_region(self):
        self.assertEqual(A.group_of("Torn labrum", "region:shoulder", "shoulder"), "shoulder")
        self.assertIsNone(A.group_of("Torn labrum", "region:hip", "hip"))


class MetricsTest(unittest.TestCase):
    def test_rates(self):
        totals = dict(minutes=60, pts=30, reb=10, ast=6, stl=2, blk=1, tov=3, fga=20, fta=10, starter=1, rim_fga=4, dunk_fga=1,
                      pbp_minutes=30)
        m = A.metrics(2, [totals[k] for k in A.STATS]).iloc[0]
        self.assertAlmostEqual(m["mpg"], 30)
        self.assertAlmostEqual(m["starter"], 0.5)
        self.assertAlmostEqual(m["pts36"], 18)
        self.assertAlmostEqual(m["ts"], 30 / (2 * (20 + 4.4)))
        self.assertAlmostEqual(m["rim36"], 4.8)   # per 36 of the minutes with play-by-play
        self.assertAlmostEqual(m["production36"], 36 * (30 + 10 + 6 + 2 + 1 - 3) / 60)

    def test_no_minutes_gives_no_rates(self):
        m = A.metrics(0, np.zeros(len(A.STATS))).iloc[0]
        self.assertTrue(np.isnan(m["mpg"]) and np.isnan(m["pts36"]) and np.isnan(m["ts"]))


class LogsTest(unittest.TestCase):
    def setUp(self):
        rows = [(1, "2020-01-01", "played", "regular-season", "AAA"), (1, "2020-01-03", "inactive", "regular-season", "AAA"),
                (1, "2020-01-05", "played", "regular-season", "AAA"), (1, "2020-04-20", "played", "playoffs", "AAA"),
                (1, "2020-11-01", "played", "regular-season", "BBB"), (2, "2020-01-02", "played", "regular-season", "CCC")]
        pg = pd.DataFrame([dict(player_id=p, game_date=pd.Timestamp(d), status=s, season_type=t, team=tm,
                                season=2020 if d < "2020-07-01" else 2021, minutes=20.0, pts=10.0, reb=0.0, ast=0.0, stl=0.0,
                                blk=0.0, tov=0.0, fga=8.0, fta=0.0, starter=False, rim_fga=np.nan, dunk_fga=np.nan)
                           for p, d, s, t, tm in rows])
        self.logs = A.Logs(pg)

    def test_totals_count_regular_season_games_played(self):
        games, totals = self.logs.totals(pd.Timestamp("2020-01-01"), pd.Timestamp("2020-12-31"), [0])
        self.assertEqual(games[0], 3)
        self.assertEqual(totals[0, A.STATS.index("pts")], 30)
        games, _ = self.logs.totals(pd.Timestamp("2020-01-02"), pd.Timestamp("2020-01-05"), [0])
        self.assertEqual(games[0], 0)   # the end day is left out

    def test_rostered_and_appeared(self):
        self.assertEqual(self.logs.rostered(pd.Timestamp("2020-01-01"), pd.Timestamp("2020-02-01"), [0])[0], 3)
        self.assertEqual(self.logs.appeared(pd.Timestamp("2020-04-01"), pd.Timestamp("2020-05-01"), [0])[0], 1)

    def test_season_team_and_career(self):
        self.assertEqual(self.logs.season_of(1, pd.Timestamp("2020-04-20")), 2020)
        self.assertEqual(self.logs.new_team(1, pd.Timestamp("2020-01-05"), pd.Timestamp("2020-04-20")), 1.0)
        self.assertEqual(self.logs.plays_in(1, 2021), 1.0)
        self.assertEqual(self.logs.plays_in(2, 2021), 0.0)


class EpisodesTest(unittest.TestCase):
    def setUp(self):
        dates = ["2020-01-01", "2020-01-03", "2021-01-10", "2021-01-12", "2021-03-01", "2021-12-01"]
        pg = pd.DataFrame([dict(player_id=7, game_date=pd.Timestamp(d), status="played", season_type="regular-season", team="AAA",
                                season=2020, minutes=20.0, pts=0.0, reb=0.0, ast=0.0, stl=0.0, blk=0.0, tov=0.0, fga=0.0, fta=0.0,
                                starter=False, rim_fga=np.nan, dunk_fga=np.nan) for d in dates])
        self.logs = A.Logs(pg)

    def profile(self, *inj):
        return dict(players=[dict(id=7, n="Seven", inj=[list(e) + [None, None, 1, None] for e in inj])])

    def test_a_vague_listing_then_the_diagnosis_is_one_injury(self):
        ep = A.episodes(self.logs, self.profile(("2020-01-05", "Right lower leg", "region:calf", "calf", 2),
                                                ("2020-01-08", "Right achilles surgery", "achilles", "achilles", 40)), {})
        self.assertEqual(len(ep), 1)
        e = ep.iloc[0]
        self.assertEqual((e["group"], e["games_missed"], e["two_injuries"]), ("achilles", 42, False))
        self.assertEqual(e["first_listed"], "2020-01-05")
        self.assertEqual((e["last_game"], e["hurt"], e["back"]), (pd.Timestamp("2020-01-03"),) * 2 + (pd.Timestamp("2021-01-10"),))

    def test_two_parts_of_the_body_are_two_injuries(self):
        ep = A.episodes(self.logs, self.profile(("2020-01-05", "Left knee sprain", "region:knee", "knee", 12),
                                                ("2020-06-01", "Right achilles surgery", "achilles", "achilles", 30)), {})
        self.assertTrue(ep.iloc[0]["two_injuries"])

    def test_care_and_short_injuries_are_left_out(self):
        ep = A.episodes(self.logs, self.profile(("2021-01-14", "Right achilles injury recovery", "achilles", "achilles", 3),
                                                ("2021-03-03", "Left ankle sprain", "ankle_sprain", "ankle", 4)), {})
        self.assertTrue(ep.empty)

    def test_the_news_dates_the_injury(self):
        said = {"nba:7:2021-03-03:knee": ("Torn meniscus", "2021-02-27", [4, 6])}
        ep = A.episodes(self.logs, self.profile(("2021-03-03", "Left knee soreness", "region:knee", "knee", 20)), said)
        e = ep.iloc[0]
        self.assertEqual((e["group"], e["hurt"], e["last_game"]), ("meniscus", pd.Timestamp("2021-02-27"), pd.Timestamp("2021-03-01")))
        self.assertEqual((e["forecast_lo"], e["forecast_hi"]), (4, 6))   # the team's first timeline

    def test_a_listing_long_after_the_last_game_has_no_day(self):
        ep = A.episodes(self.logs, self.profile(("2020-06-01", "Torn right ACL", "acl", "knee", 50)), {})
        self.assertTrue(pd.isna(ep.iloc[0]["hurt"]))


class TimeToReturnTest(unittest.TestCase):
    def test_kaplan_meier(self):
        r = A.time_to_return([10, 20, 30, 40], [True, True, False, True])
        self.assertEqual(r["median_days"], 20)
        self.assertAlmostEqual(r["back_within_a_year"], 1.0)

    def test_nobody_back(self):
        r = A.time_to_return([100, 200], [False, False])
        self.assertIsNone(r["median_days"])
        self.assertEqual(r["back_within_a_year"], 0)


class CurveTest(unittest.TestCase):
    def test_the_share_still_out_each_week(self):
        r = A.time_to_return([3, 10, 20, 400], [True, True, True, False])
        curve = r["still_out"]
        self.assertEqual(len(curve), A.WEEKS + 1)
        self.assertEqual(curve[0], 1.0)
        self.assertTrue(all(b <= a for a, b in zip(curve, curve[1:])))
        self.assertAlmostEqual(curve[1], 0.75)   # one of four back by day 7
        self.assertAlmostEqual(curve[3], 0.25)   # three back by day 21; the fourth, still out, counts until it leaves


class TimelineTest(unittest.TestCase):
    def frame(self, rows):
        return pd.DataFrame([dict(first_listed=f, back=pd.Timestamp(b), forecast_lo=lo, forecast_hi=hi, crosses_break=brk)
                             for f, b, lo, hi, brk in rows])

    def test_sooner_within_and_later(self):
        x = self.frame([("2024-01-01", "2024-01-29", 3, 5, False),    # 4 weeks: within 3 to 5
                        ("2024-01-01", "2024-03-11", 3, 5, False),    # 10 weeks: later
                        ("2024-01-01", "2024-01-08", 3, 5, False),    # 1 week: sooner
                        ("2024-01-01", "2024-02-26", 4, 6, False),    # 8 weeks: later
                        ("2024-01-01", "2024-02-05", 5, 5, False),    # 5 weeks: within
                        ("2024-03-01", "2024-10-25", 2, 4, True),     # waited out the offseason: left out
                        ("2024-01-01", "2024-03-01", 4, None, False)])   # "at least 4 weeks": left out
        t = A.timelines(x)
        self.assertEqual((t["injuries"], t["sooner"], t["within"], t["later"]), (5, 1, 2, 2))
        self.assertAlmostEqual(t["late_by"], 3.5)   # 5 and 2 weeks past the longest estimate

    def test_too_few_gives_nothing(self):
        self.assertIsNone(A.timelines(self.frame([("2024-01-01", "2024-01-29", 3, 5, False)])))


class BreakTest(unittest.TestCase):
    def test_a_long_stretch_without_games(self):
        days = pd.to_datetime(["2024-04-10", "2024-04-12", "2024-04-14", "2024-10-22", "2024-10-24"]).to_numpy()
        self.assertTrue(A.crosses_break(pd.Timestamp("2024-04-11"), pd.Timestamp("2024-10-24"), days))
        self.assertFalse(A.crosses_break(pd.Timestamp("2024-04-10"), pd.Timestamp("2024-04-14"), days))
        self.assertFalse(A.crosses_break(pd.Timestamp("2024-04-10"), pd.NaT, days))


class CorrectedTest(unittest.TestCase):
    def test_a_straight_line_closes_the_gap(self):
        rng = np.random.default_rng(0)
        pool = pd.DataFrame(dict(age=rng.uniform(20, 34, 200), mpg=rng.uniform(10, 36, 200), production36=rng.uniform(15, 40, 200),
                                 played_share=rng.uniform(0.3, 1, 200)))
        values = 2 * pool["age"] - 0.5 * pool["mpg"]
        me = dict(age=21.0, mpg=30.0, production36=25.0, played_share=0.9)
        pick = np.argsort(np.abs(pool["age"] - 30).to_numpy())[:10]   # matched players nine years older
        self.assertAlmostEqual(A.corrected(me, pool, pick, values), 2 * 21 - 0.5 * 30, places=6)


class IntervalTest(unittest.TestCase):
    def test_players_are_resampled_with_all_their_injuries(self):
        lo, hi = A.interval([10.0] * 9 + [0.0], ["a"] * 9 + ["b"], reps=400)
        self.assertEqual((lo, hi), (0.0, 10.0))


class FollowTest(unittest.TestCase):
    def test_an_injured_player_back_to_fewer_minutes(self):
        pg = league()
        hurt = pg["player_id"] == 1
        out = hurt & pg["game_date"].between("2020-01-01", "2020-03-01")
        pg.loc[out, "status"] = "inactive"
        pg.loc[out, [c for c in A.STATS[:-1] if c != "starter"]] = np.nan
        after = hurt & (pg["game_date"] > "2020-03-01")
        for c in ["minutes", "pts", "reb", "ast", "stl", "blk", "tov", "fga", "fta", "rim_fga", "dunk_fga"]:
            pg.loc[after, c] *= 2 / 3   # 20 minutes a game, the same per minute
        logs = A.Logs(pg)
        played = pg.loc[hurt & (pg["status"] == "played"), "game_date"]
        ep = pd.DataFrame([dict(player_id=1, player="One", first_listed="2020-01-01", listed_as="Right knee", kind="region:knee",
                                region="knee", label=None, group=None, games_missed=30, two_injuries=False,
                                last_game=played[played < "2020-01-01"].max(), hurt=played[played < "2020-01-01"].max(),
                                back=played[played > "2020-03-01"].min())])
        onsets = pd.DataFrame([dict(player_id=1, onset_date=pd.Timestamp("2020-01-01"), end_date=pd.Timestamp("2020-03-01"),
                                    games_missed=30, new_injury=True, reason="Injury/Illness - Right knee", region="knee")])
        f, stand_ins = A.follow(logs, births(logs), ep, onsets, pg["game_date"].max())
        r = f.iloc[0]
        self.assertAlmostEqual(r["y1_effect_mpg"], -10, places=6)
        self.assertAlmostEqual(r["y1_effect_production36"], 0, places=6)
        self.assertAlmostEqual(r["played_share"], r["matched_played_share"])
        self.assertEqual((r["playing_2"], r["new_team"]), (1.0, 0.0))
        self.assertEqual(len(stand_ins), A.STAND_INS)
        self.assertTrue(np.allclose(stand_ins["y1_effect_mpg"], 0))
        # the profile's row for it
        ep["crosses_break"] = False
        row = A.by_injury(ep, f)["1:2020-01-01"]
        self.assertEqual(row["days"], (ep.at[0, "back"] - ep.at[0, "hurt"]).days)
        before, after, matched = row["year_1"]["mpg"]
        self.assertAlmostEqual((before, after, matched), (30, 20, 0), places=6)


if __name__ == "__main__":
    unittest.main()
