import unittest

from injury_risk import news_summary as S


def target(tid, kind, region, listed, league="nba"):
    return dict(id=tid, league=league, kind=kind, region=region, listed_as=listed)


def fact(tid, status, label=None, **more):
    f = dict(target=tid, status=status, sources=[dict(url="https://example.org/a", outlet="Example Times")] if status != "not_found" else [])
    if label:
        f["diagnosis"] = dict(label=label)
    f.update(more)
    return f


class SummarizeTest(unittest.TestCase):
    def setUp(self):
        targets = [target("nba:1:2024-01-10:ankle", "ankle_sprain", "ankle", "Left ankle sprain"),
                   target("nba:2:2024-02-10:achilles", "achilles", "achilles", "Right Achilles tendon rupture"),
                   target("nba:3:2024-03-10:knee", "region:knee", "knee", "Left knee soreness"),
                   target("nba:4:2024-04-10:knee", "region:knee", "knee", "Right knee soreness"),
                   target("college:5:2022-01-10:knee", "region:knee", "knee", "Knee", league="college")]
        facts = [fact("nba:1:2024-01-10:ankle", "confirmed", "Ankle sprain", contact="contact", mechanism="stepped_on_foot",
                      game=dict(date="2024-01-08", play="rebound"), setting="game"),
                 fact("nba:2:2024-02-10:achilles", "reported", "Achilles tear", contact="non_contact", mechanism="cutting_or_planting",
                      surgery=dict(had=True)),
                 fact("nba:3:2024-03-10:knee", "confirmed", "Torn meniscus"),
                 fact("nba:4:2024-04-10:knee", "not_found"),
                 fact("college:5:2022-01-10:knee", "confirmed", "Torn ACL")]
        self.s = S.summarize(facts, {t["id"]: t for t in targets})

    def test_counts_the_nba_only(self):
        self.assertEqual(self.s["researched"], 4)
        self.assertEqual(self.s["named"], 3)
        self.assertEqual(self.s["game"], 1)

    def test_vague_listings_and_what_they_were(self):
        self.assertEqual((self.s["vague"]["listed"], self.s["vague"]["named"]), (2, 1))
        knee = self.s["vague"]["regions"][0]
        self.assertEqual((knee["region"], knee["name"], knee["labels"]), ("knee", "Knee", [("Torn meniscus", 1)]))

    def test_how_each_kind_happened(self):
        groups = {g["key"]: g for g in self.s["groups"]}
        self.assertEqual(groups["ankle"]["mechanisms"], dict(known=1, counts=[["stepped_on_foot", 1]]))
        self.assertEqual(groups["achilles"]["contact"], dict(known=1, non_contact=1))
        self.assertEqual(groups["achilles"]["surgery"], 1)
        self.assertEqual(self.s["all"]["contact"], dict(known=2, non_contact=1))
        self.assertEqual(self.s["all"]["plays"]["counts"], [["rebound", 1]])


if __name__ == "__main__":
    unittest.main()
