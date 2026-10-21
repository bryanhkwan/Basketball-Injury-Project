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


HAVE_PROFILES = all((B.DATA / f"{n}.json").exists() for n in ("history", "college", "people"))


@unittest.skipUnless(HAVE_PROFILES, "needs the published profiles in docs/data")
class Profiles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.h, cls.c, cls.people = (json.loads((B.DATA / f"{n}.json").read_text(encoding="utf-8")) for n in ("history", "college", "people"))
        cls.nba = {p["id"]: p for p in cls.h["players"]}

    def test_every_2025_26_player_has_a_profile(self):
        scored = {p["id"] for p in json.loads((B.DATA / "players.json").read_text(encoding="utf-8"))["players"]}
        self.assertLessEqual(scored, set(self.nba))
        roster = {pid for pid, p in self.nba.items() if any(s == 2026 for s, _ in p["tm"])}
        self.assertGreater(len(roster), len(scored))   # the players the model could not score are there too

    def test_the_seasons_biggest_injuries_have_profiles(self):
        # out all of 2025-26, so the model never scored them: the profiles once left them out
        for pid, kind in ((202681, "acl"), (1630169, "achilles"), (1627832, "acl"), (203081, "achilles")):
            p = self.nba[pid]
            self.assertTrue(p["st"].startswith("Out all season"), p["n"])
            biggest = max(p["inj"], key=lambda e: e[4])
            self.assertEqual(biggest[2], kind, p["n"])
            self.assertGreaterEqual(biggest[4], 80, p["n"])

    def test_injuries_are_in_order_and_add_up(self):
        for p in self.nba.values():
            days = [e[0] for e in p["inj"]]
            self.assertEqual(days, sorted(days), p["n"])
            for e in p["inj"]:
                self.assertGreaterEqual(e[4], 0)
                if e[5]:
                    self.assertGreater(e[5], e[0], p["n"])   # back after it began
        groups = {g["key"] for g in self.h["groups"]}
        self.assertIn("any", groups)
        self.assertIn("acl", groups)

    def test_college_entries_are_facts(self):
        plain = {"Out for the season", "Out indefinitely", "Out", "Doubtful", "Questionable", "Probable", "Listed"}
        for p in self.c["people"]:
            for e in p["inj"]:
                self.assertLessEqual(e[0], e[1])
                self.assertTrue(e[6] in plain or e[6].startswith("Expected back"), e[6])
                self.assertTrue(e[7] is None or e[7] >= 0)

    def test_search_finds_every_profile(self):
        ids = {str(x[0]) for x in self.people}
        self.assertEqual(ids, {str(i) for i in self.nba} | {f"c{p['id']}" for p in self.c["people"]})
        linked = [p for p in self.c["people"] if "nba" in p]
        self.assertTrue(linked)
        for p in linked:
            self.assertIn(p["nba"], self.nba)


HAVE_CAREERS = all((B.DATA / f"{n}.json").exists() for n in ("careers", "details", "history", "college"))


@unittest.skipUnless(HAVE_CAREERS, "needs the published career study and injury details in docs/data")
class CareersAndDetails(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c, cls.d, cls.h, cls.col = (json.loads((B.DATA / f"{n}.json").read_text(encoding="utf-8"))
                                        for n in ("careers", "details", "history", "college"))

    def test_recovery_curves_only_fall(self):
        for g in self.c["groups"]:
            curve = g["still_out"]
            self.assertEqual(curve[0], 1, g["key"])
            self.assertTrue(all(b <= a for a, b in zip(curve, curve[1:])), g["key"])

    def test_every_estimate_sits_in_its_range(self):
        for g in self.c["groups"]:
            for r in g["year_1"] + g["year_2"]:
                self.assertTrue(r["lo"] <= r["effect"] <= r["hi"], (g["key"], r["metric"]))
            for r in g["outcomes"]:
                self.assertTrue(r["lo"] <= r["difference"] <= r["hi"], (g["key"], r["outcome"]))

    def test_nba_com_is_cited_without_a_link(self):
        for key, f in self.d["news"].items():
            for outlet, published, headline, url, official in f["sources"]:
                host = url.split("/")[2] if url else ""
                self.assertFalse(host == "nba.com" or host.endswith(".nba.com"), key)
                self.assertTrue(url is None or url.startswith("https://"), key)

    def test_details_belong_to_profile_injuries(self):
        nba = {f"{p['id']}:{e[0]}:{e[3]}" for p in self.h["players"] for e in p["inj"]}
        college = {f"c{p['id']}:{e[0]}:{e[4]}" for p in self.col["people"] for e in p["inj"]}
        firsts = {f"{p['id']}:{e[0]}" for p in self.h["players"] for e in p["inj"]}
        self.assertTrue(self.d["news"] and self.d["after"])
        self.assertEqual([k for k in self.d["news"] if k not in nba | college], [])
        self.assertEqual([k for k in self.d["after"] if k not in firsts], [])

    def test_college_news_only_for_players_now_in_the_nba(self):
        in_nba = {f"c{p['id']}" for p in self.col["people"] if p.get("nba")}
        self.assertEqual([k for k in self.d["news"] if k.startswith("c") and k.split(":")[0] not in in_nba], [])

    def test_the_overview_asks_the_new_questions(self):
        page = (DOCS / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="f5-title"', page)
        self.assertIn('id="f6-title"', page)
        self.assertIn(f"Each of {self.c['followed']:,} injured players", page)


EVIDENCE = OUTPUTS.parent / "data" / "news" / "evidence.jsonl"


@unittest.skipUnless(EVIDENCE.exists() and HAVE_CAREERS, "needs the research's local quotes and the published details")
class NewsFactsOnly(unittest.TestCase):
    def test_no_sentence_from_a_report_is_published(self):
        # the site carries facts and their sources; a run of eight words from any quote behind them is a leak, unless it
        # is in a headline, which the profiles cite
        def grams(text):
            words = re.findall(r"[a-z0-9']+", text.lower())
            return {tuple(words[i:i + 8]) for i in range(len(words) - 7)}
        details = json.loads((B.DATA / "details.json").read_text(encoding="utf-8"))
        headlines = set().union(*(grams(s[2]) for f in details["news"].values() for s in f["sources"] if s[2]))
        published = set().union(*(grams(f.read_text(encoding="utf-8")) for f in [*DOCS.glob("*.html"), *DOCS.glob("data/*.json")]))
        quotes = [json.loads(line)["quote"] for line in EVIDENCE.read_text(encoding="utf-8").splitlines() if line.strip()]
        leaks = [q for q in quotes if (grams(q) - headlines) & published]
        self.assertFalse(leaks, leaks[:3])


@unittest.skipUnless((OUTPUTS / "moments_dashboard" / "examples.json").exists() and DOCS.exists(), "needs the site and the examples")
class CollegeFactsOnly(unittest.TestCase):
    def test_covers_wording_is_never_published(self):
        # profiles carry the listings' facts (dates, body part, status in plain words), never Covers' notes
        listings = OUTPUTS / "college_moments" / "listings_matched.parquet"
        if not listings.exists():
            self.skipTest("needs outputs/college_moments")
        import pandas as pd
        notes = {n[:60] for n in pd.read_parquet(listings, columns=["note"])["note"].dropna() if len(n) >= 60}
        self.assertTrue(notes)
        for f in list(DOCS.glob("*.html")) + list(DOCS.glob("data/*.json")):
            text = f.read_text(encoding="utf-8")
            hits = [n for n in notes if n in text]
            self.assertFalse(hits, f"Covers' wording in {f.name}: {hits[:2]}")

    def test_the_report_tells_only_the_nba_stories(self):
        examples = [e for e in json.loads((OUTPUTS / "moments_dashboard" / "examples.json").read_text(encoding="utf-8"))
                    if e["league"] == "College"]
        self.assertTrue(examples)
        report = (DOCS / "moments.html").read_text(encoding="utf-8")
        for e in examples:
            self.assertNotIn(e["story"][:60], report, f"{e['player']}'s college story is in the report")


if __name__ == "__main__":
    unittest.main()
