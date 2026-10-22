import re
import unittest

from injury_risk import cards
from injury_risk import report_site as S
from injury_risk.paths import OUTPUTS

HAVE_DATA = (OUTPUTS / "moments_dashboard" / "facts.json").exists() and (OUTPUTS / "college_moments" / "summary.json").exists()


class Formats(unittest.TestCase):
    def test_pct(self):
        self.assertEqual(S.pct(0.172), "17%")
        self.assertEqual(S.pct(0.0916, 1), "9.2%")
        self.assertEqual(S.pct(0.00035, 1), "<0.1%")
        self.assertEqual(S.pct(None), "—")

    def test_times_and_one_in(self):
        self.assertEqual(S.times(4.108), "4.1×")
        self.assertEqual(S.times(69.4), "69×")
        self.assertEqual(S.one_in(0.150), "1 in 7")
        self.assertEqual(S.share_ratio({"injury_share": 0.09, "normal_share": 0.0}), None)

    def test_table_escapes_text(self):
        html = S.table("cap", ["A", "B"], [["<b>x</b>", "1"]], {1})
        self.assertIn("&lt;b&gt;x&lt;/b&gt;", html)
        self.assertIn('<td class="num">1</td>', html)


@unittest.skipUnless(HAVE_DATA, "needs outputs/moments_dashboard and the summary files")
class Page(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = S.load()
        cls.page = S.render(cls.d)

    def test_every_chart_and_section_is_there(self):
        for anchor in ("chart-nba", "chart-fade", "chart-college", "chart-signs", "chart-traced", 'id="conclusions"',
                       'id="report-data"', 'id="limits"'):
            self.assertIn(anchor, self.page)

    def test_no_placeholders_left_in_the_text(self):
        text = self.page.split("<style>")[0] + self.page.split("</style>")[1].split('<script type="application/json"')[0]
        self.assertEqual(re.findall(r"\$\{?[a-z_]+", text), [])

    def test_headline_numbers_come_from_the_data(self):
        facts = {r["metric"]: r["value"] for r in self.d["facts"]}
        self.assertIn(f"{facts['nba_injuries']:,}", self.page)
        self.assertIn(S.one_in(facts["nba_traced_share"]), self.page)

    def test_link_preview_renders_from_the_same_data(self):
        page = cards.social_card(self.d)
        self.assertIn("FULL REPORT", page)
        self.assertNotIn("—", page.split("</style>")[1])


if __name__ == "__main__":
    unittest.main()
