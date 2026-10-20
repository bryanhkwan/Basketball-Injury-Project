import json
import re
import unittest

from injury_risk import site_build as B
from injury_risk.paths import OUTPUTS
from injury_risk.report_site import DOCS

HAVE_SITE = all((B.DATA / f"{n}.json").exists() for n in ("board", "players", "study"))


class Formats(unittest.TestCase):
    def test_ratios_read_as_people_say_them(self):
        self.assertEqual(B.times_text(2.51), "2.5×")
        self.assertEqual(B.times_text(0.82), "18% less")

    def test_days(self):
        self.assertEqual(B.day_label("2025-10-21"), "Tuesday, October 21, 2025")
        self.assertEqual(B.short_day("2025-10-21"), "Tue, Oct 21")


@unittest.skipUnless(HAVE_SITE, "needs the published data in docs/data")
class Overview(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = B.load()
        cls.page = B.render_overview(cls.d)

    def test_no_placeholders_left(self):
        self.assertEqual(re.findall(r"\$\{?[a-z_]+", self.page), [])

    def test_the_record_comes_from_the_board_check(self):
        check = self.d["board"]["check"]["before"]
        self.assertIn(f"{check['top']['rate'] / check['bottom']['rate']:.1f}", self.page)
        self.assertIn(B.pct(check["top"]["rate"]), self.page)
        self.assertIn(B.pct(check["bottom"]["rate"]), self.page)

    def test_opening_night_is_on_the_board(self):
        nights = dict(self.d["board"]["modes"]["before"]["nights"])
        first = nights[B.OPENING_NIGHT][0]
        self.assertIn(first[1], self.page)
        self.assertEqual(self.page.count('<span class="bc-rank">'), B.LIVE_ROWS)

    def test_every_kind_of_injury_has_a_tab_and_a_panel(self):
        for key, _ in B.KINDS:
            self.assertIn(f'id="kind-{key}"', self.page)
            self.assertIn(f'id="panel-{key}"', self.page)


@unittest.skipUnless(HAVE_SITE, "needs the published data in docs/data")
class PublishedData(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = B.load()

    def test_board_nights_are_in_order_and_complete(self):
        for mode, m in self.d["board"]["modes"].items():
            days = [day for day, _ in m["nights"]]
            self.assertEqual(days, sorted(days), mode)
            for day, rows in m["nights"]:
                self.assertLessEqual(len(rows), 12)
                for r in rows:
                    self.assertEqual(len(r), 8)
                    self.assertTrue(0 < r[4] < 1000)
                    self.assertEqual(bool(r[6]), bool(r[7]))   # an outcome is written exactly when there was an injury
                risks = [r[4] for r in rows]
                self.assertEqual(risks, sorted(risks, reverse=True))

    def test_board_players_have_timelines(self):
        ids = {p["id"] for p in self.d["players"]["players"]}
        for _, rows in self.d["board"]["modes"]["before"]["nights"]:
            for r in rows:
                self.assertIn(r[0], ids)

    def test_player_series_line_up_with_the_dates(self):
        p = self.d["players"]
        for x in p["players"]:
            self.assertEqual(len(x["d"]), len(x["r"]))
            self.assertEqual(x["d"], sorted(x["d"]))
            self.assertTrue(all(0 <= i < len(p["dates"]) for i in x["d"]))
        self.assertEqual(len(p["avg"]), len(p["dates"]))

    def test_data_is_strict_json(self):
        # Python writes NaN and Infinity by default; browsers refuse the whole file.
        def refuse(token):
            raise ValueError(f"{token} in the published data")
        for name in ("board", "players", "study"):
            json.loads((B.DATA / f"{name}.json").read_text(encoding="utf-8"), parse_constant=refuse)

    def test_college_comparison_can_be_drawn(self):
        c = self.d["study"]["compare"]
        self.assertTrue(c["plays"])
        for r in c["plays"]:
            for league in ("nba", "col"):
                ratio, lo, hi = r[league][:3]
                self.assertTrue(0 < lo <= ratio <= hi, (r["group"], r["play"], league))
                self.assertGreater(r[league][5], 0)
        for g in c["groups"]:
            self.assertTrue(0 <= g["nba"][1] <= 1 and 0 <= g["col"][3] <= 1, g["group"])
        for league in ("nba", "col"):
            for kind, shares in c["stoppages"][league].items():
                self.assertAlmostEqual(sum(shares.values()), 1, delta=0.01, msg=(league, kind))
        seasons = [s["season"] for s in c["seasons"]]
        self.assertEqual(seasons, sorted(seasons))

    def test_agreement_counts_the_plays_it_shows(self):
        c = self.d["study"]["compare"]
        a, clear = c["agreement"], [p for p in c["plays"] if p["nba"][1] > 1 or p["nba"][2] < 1]
        self.assertEqual(a["pairs"], len(c["plays"]))
        self.assertEqual(a["nba_clear"], len(clear))
        self.assertEqual(a["nba_clear_same"], sum((p["nba"][0] - 1) * (p["col"][0] - 1) > 0 for p in clear))
        self.assertLessEqual(a["both_clear_same"], a["both_clear"])
        self.assertTrue(-1 <= a["r_all"] <= 1 and -1 <= a["r_any"] <= 1)
        page = (DOCS / "index.html").read_text(encoding="utf-8")
        self.assertIn(f"Of the {a['nba_clear']} with a clear NBA signal, <strong>{a['nba_clear_same']} point the same way", page)


@unittest.skipUnless((OUTPUTS / "moments_dashboard" / "examples.json").exists() and DOCS.exists(), "needs the site and the examples")
class CollegeStaysAnonymous(unittest.TestCase):
    def test_no_college_injury_is_told_by_name(self):
        # Some of these players are in the NBA now (Jaylen Clark, Cooper Flagg), so their names can appear in the 2025-26
        # NBA data; their college injuries must not appear anywhere, and the report names no college player at all.
        examples = [e for e in json.loads((OUTPUTS / "moments_dashboard" / "examples.json").read_text(encoding="utf-8"))
                    if e["league"] == "College"]
        self.assertTrue(examples)
        files = list(DOCS.glob("*.html")) + list(DOCS.glob("data/*.json"))
        self.assertTrue(files)
        for f in files:
            text = f.read_text(encoding="utf-8")
            for e in examples:
                self.assertNotIn(e["story"][:60], text, f"{e['player']}'s college story appears in {f.name}")
        report = (DOCS / "moments.html").read_text(encoding="utf-8")
        for e in examples:
            self.assertNotIn(e["player"], report)


if __name__ == "__main__":
    unittest.main()
