import unittest
from pathlib import Path

from injury_risk.injury_reports import _rejoin_wrapped, parse_pdf
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

    @unittest.skipUnless(report(2026, "Injury-Report_2025-12-23_05_00PM.pdf").exists(), "2025-26 report not downloaded")
    def test_reason_wrapped_onto_the_next_page(self):
        res = parse_pdf(report(2026, "Injury-Report_2025-12-23_05_00PM.pdf"))
        self.assertEqual(find(res["rows"], "Haliburton, Tyrese")["reason"], "Injury/Illness - Right Achilles Tendon; Tear")
        self.assertEqual(find(res["rows"], "Jackson, Isaiah")["reason"], "Injury/Illness - N/A; Concussion")

    @unittest.skipUnless(report(2025, "Injury-Report_2025-03-20_05PM.pdf").exists(), "2024-25 report not downloaded")
    def test_wrapped_words_next_to_a_not_submitted_line(self):
        res = parse_pdf(report(2025, "Injury-Report_2025-03-20_05PM.pdf"))
        self.assertEqual(find(res["rows"], "Wiggins, Andrew")["reason"], "Injury/Illness - Right Ankle; Impingement")


class RejoinTest(unittest.TestCase):
    """Made-up reports: words a reason wrapped past the foot of a page go back to it."""

    def rejoin(self, *items):
        items = [dict(kind=kind, page=page, reason=reason) for kind, page, reason in items]
        _rejoin_wrapped(items)
        return [item["reason"] for item in items]

    def test_words_on_the_next_pages_first_row(self):
        self.assertEqual(self.rejoin(("row", 1, "Injury/Illness - Left Knee; Injury"),
                                     ("row", 2, "Recovery G League - Two-Way")),
                         ["Injury/Illness - Left Knee; Injury Recovery", "G League - Two-Way"])

    def test_words_in_front_of_an_available_players_dash(self):
        self.assertEqual(self.rejoin(("row", 3, "Injury/Illness - Right Hamstring;"), ("row", 4, "Tightness -")),
                         ["Injury/Illness - Right Hamstring; Tightness", "-"])

    def test_words_caught_by_a_not_submitted_line(self):
        self.assertEqual(self.rejoin(("row", 5, "Injury/Illness - Right Ankle;"), ("not_submitted", 6, "Impingement"),
                                     ("row", 6, "Injury/Illness - Left Ankle; Sprain")),
                         ["Injury/Illness - Right Ankle; Impingement", "", "Injury/Illness - Left Ankle; Sprain"])

    def test_an_opening_line_next_to_a_not_submitted_line_goes_to_the_row_below(self):
        self.assertEqual(self.rejoin(("row", 2, "Rest"), ("not_submitted", 2, "Injury/Illness - Left Knee;"),
                                     ("row", 2, "Soreness")),
                         ["Rest", "", "Injury/Illness - Left Knee; Soreness"])

    def test_whole_reasons_are_left_alone(self):
        rows = [("row", 1, "Injury/Illness - Left Ankle; Sprain"), ("row", 2, "Injury/Illness - Right Knee; Soreness"),
                ("row", 2, "Recovery Injury/Illness - Left Foot; Contusion")]   # same page: no wrap to undo
        self.assertEqual(self.rejoin(*rows), [r for _, _, r in rows])


if __name__ == "__main__":
    unittest.main()
