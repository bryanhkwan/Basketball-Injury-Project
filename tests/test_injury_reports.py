import unittest
from pathlib import Path

from injury_risk.injury_reports import parse_pdf
from injury_risk.paths import REPORTS_RAW


def report(season: int, name: str) -> Path:
    return REPORTS_RAW / str(season) / name


def find(rows, player):
    return next(r for r in rows if r["player"] == player)


class ParserTest(unittest.TestCase):
    """Checked against the PDFs by eye; skipped until the reports are downloaded (data/ is not in git)."""

    @unittest.skipUnless(report(2019, "Injury-Report_2019-01-15_05PM.pdf").exists(), "2018-19 report not downloaded")
    def test_2018_19_layout_with_category_column(self):
        res = parse_pdf(report(2019, "Injury-Report_2019-01-15_05PM.pdf"))
        cov = find(res["rows"], "Covington, Robert")
        self.assertEqual((cov["team"], cov["matchup"], cov["status"]), ("MIN", "MIN@PHI", "Out"))
        self.assertEqual(cov["reason"], "Injury/Illness - Right Knee Bone Bruise")
        self.assertEqual(find(res["rows"], "Rose, Derrick")["team"], "MIN")      # "Timberwolves" wraps to a second line
        self.assertEqual(find(res["rows"], "Fultz, Markelle")["team"], "PHI")
        self.assertEqual(find(res["rows"], "Terrell, Jared")["reason"], "G League Team")
        self.assertEqual(res["problems"], [])

    @unittest.skipUnless(report(2022, "Injury-Report_2022-01-15_05PM.pdf").exists(), "2021-22 report not downloaded")
    def test_2021_22_layout(self):
        res = parse_pdf(report(2022, "Injury-Report_2022-01-15_05PM.pdf"))
        self.assertEqual(find(res["rows"], "Holiday, Jrue")["reason"], "Injury/Illness - Left Ankle; Soreness")
        self.assertEqual(find(res["rows"], "Trent Jr., Gary")["status"], "Doubtful")
        self.assertEqual(find(res["rows"], "Lillard, Damian")["team"], "POR")
        self.assertEqual(res["problems"], [])

    @unittest.skipUnless(report(2026, "Injury-Report_2026-01-15_05_00PM.pdf").exists(), "2025-26 report not downloaded")
    def test_2025_26_layout_with_wrapped_reasons(self):
        res = parse_pdf(report(2026, "Injury-Report_2026-01-15_05_00PM.pdf"))
        self.assertEqual(find(res["rows"], "Clarke, Brandon")["reason"], "Injury/Illness - Right Calf; Strain")
        self.assertEqual(find(res["rows"], "Edey, Zach")["reason"], "Injury/Illness - Left Ankle; Stress Reaction")
        self.assertEqual(find(res["rows"], "Pippen Jr., Scotty")["reason"], "Injury/Illness - Left Great Toe; Surgery Recovery")
        self.assertEqual(find(res["rows"], "Suggs, Jalen")["reason"], "Injury/Illness - Right Knee; MCL contusion")
        self.assertEqual(find(res["rows"], "Castleton, Colin")["team"], "ORL")
        self.assertEqual(res["problems"], [])


if __name__ == "__main__":
    unittest.main()
