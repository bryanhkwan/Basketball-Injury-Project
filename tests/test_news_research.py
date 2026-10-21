import copy
import json
import tempfile
import unittest
from pathlib import Path

from injury_risk import news_research as R


# Fictional people, teams, sites and sources only.
TARGET = dict(id="nba:999:2024-01-10:knee", player="Morgan Example", team="EXM", league="nba", tier=1,
              first_listed="2024-01-10", last_game_before="2024-01-08", listed_as="Left knee soreness",
              region="knee", kind="region:knee", window=["2023-12-27", "2024-03-10"], pilot=True, games_missed=20)
URL = "https://example.org/news/medical-update"
QUOTE = "Morgan Example has a torn left meniscus, the team announced."
OUTLETS = {"Example team": "team", "Example Wire": "wire"}
FACT = dict(target=TARGET["id"], status="confirmed", diagnosis=dict(label="Torn meniscus", detail=None), side="left",
            sources=[dict(url=URL, outlet="Example team", published="2024-01-11", headline="Morgan Example medical update",
                          official=True)])
REVIEW = dict(target=TARGET["id"], fact=FACT,
              evidence=[dict(target=TARGET["id"], field=field, value=value, url=URL, quote=QUOTE, retrieved="2026-10-20")
                        for field, value in (("diagnosis.label", "Torn meniscus"), ("side", "left"))],
              notes=[], queries=["Morgan Example knee injury 2024"], elapsed_seconds=10, tokens=None)


class ReviewTest(unittest.TestCase):
    def test_valid_review(self):
        self.assertEqual(R.match_review(REVIEW, TARGET, OUTLETS), [])

    def test_every_source_must_be_about_the_player(self):
        row = copy.deepcopy(REVIEW)
        row["fact"]["sources"][0]["headline"] = "Medical update"
        for ev in row["evidence"]:
            ev["quote"] = "A torn left meniscus, the team announced."
        self.assertTrue(any("name Morgan Example" in e for e in R.match_review(row, TARGET, OUTLETS)))

    def test_both_window_bounds_and_date_validity(self):
        for day in ("2023-12-26", "2024-03-11", "2024-02-31"):
            with self.subTest(day=day):
                row = copy.deepcopy(REVIEW)
                row["fact"]["sources"][0]["published"] = day
                self.assertTrue(R.match_review(row, TARGET, OUTLETS))
        for day in TARGET["window"]:
            row = copy.deepcopy(REVIEW)
            row["fact"]["sources"][0]["published"] = day
            self.assertEqual(R.match_review(row, TARGET, OUTLETS), [])

    def test_evidence_cannot_change_injury_value_or_source(self):
        for key, value in (("target", "wrong"), ("value", "Torn ACL"), ("url", "https://other.example.org"),
                           ("field", "invented"), ("retrieved", "yesterday")):
            with self.subTest(key=key):
                row = copy.deepcopy(REVIEW)
                row["evidence"][0][key] = value
                self.assertTrue(R.match_review(row, TARGET, OUTLETS))

    def test_not_found_needs_attempted_research_and_no_facts(self):
        row = copy.deepcopy(REVIEW)
        row.update(fact=dict(target=TARGET["id"], status="not_found", sources=[]), evidence=[],
                   notes=["No matching report in the window."])
        self.assertEqual(R.match_review(row, TARGET, OUTLETS), [])
        for key, value in (("queries", []), ("notes", [])):
            bad = copy.deepcopy(row)
            bad[key] = value
            self.assertTrue(R.match_review(bad, TARGET, OUTLETS))
        row["fact"]["diagnosis"] = None
        self.assertTrue(R.match_review(row, TARGET, OUTLETS))

    def test_conflict_requires_explanation(self):
        row = copy.deepcopy(REVIEW)
        row["fact"]["status"] = "conflicting"
        self.assertTrue(R.match_review(row, TARGET, OUTLETS))
        row["fact"]["diagnosis"]["detail"] = "The listing names the opposite side"
        self.assertEqual(R.match_review(row, TARGET, OUTLETS), [])

    def test_invalid_diagnosis_is_an_error_not_a_crash(self):
        row = copy.deepcopy(REVIEW)
        row["fact"]["diagnosis"]["label"] = "Invented"
        self.assertIn("unknown diagnosis label", R.match_review(row, TARGET, OUTLETS))


class PlanTest(unittest.TestCase):
    def rows(self):
        base = dict(TARGET, pilot=False)
        return [dict(base, id="a", listed_as="Left knee sprain", kind="region:knee", last_game_before="2023-12-01", games_missed=30),
                dict(base, id="b", listed_as="Left knee soreness", last_game_before="2023-12-01", games_missed=12),
                dict(base, id="c", listed_as="Left knee sprain", last_game_before="2024-01-08", games_missed=11),
                dict(base, id="d", league="college", diagnosis_listed=None, last_game_before=None, games_missed=5),
                dict(base, id="e", league="college", tier=2, diagnosis_listed=None, last_game_before=None)]

    def test_a_tier_in_priority_order(self):
        # vague listings first, then injuries listed right after a game, then the costliest
        self.assertEqual([t["id"] for t in R.select(self.rows(), tier=1, log=lambda _: None)], ["b", "d", "c", "a"])
        self.assertEqual([t["id"] for t in R.select(self.rows(), tier=1, league="nba", log=lambda _: None)], ["b", "c", "a"])

    def test_college_tiers_past_the_first_are_left_out(self):
        said = []
        self.assertEqual(R.select(self.rows(), tier=2, log=said.append), [])   # "e" is a college tier 2 injury
        self.assertIn("outside the plan", said[0])
        self.assertEqual(R.select(self.rows(), tier=2, league="nba", log=lambda _: None), [])
        with self.assertRaisesRegex(ValueError, "--pilot or --tier"):
            R.select(self.rows())


class FileTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.targets = self.root / "targets.jsonl"
        self.facts = self.root / "facts.jsonl"
        self.local = self.root / "local"
        (self.local / "reviews").mkdir(parents=True)
        (self.local / "cache").mkdir()
        self.review_path = self.local / "reviews" / "00.json"
        self.review_path.write_text(json.dumps(REVIEW), encoding="utf-8")
        (self.local / "cache" / "page.txt").write_text(URL + "\n" + QUOTE, encoding="utf-8")
        R.write_jsonl(self.targets, [TARGET, dict(TARGET, id="nba:997:2024-01-10:knee", player="Not Pilot", pilot=False)])

    def run_pilot(self, **options):
        return R.run(pilot=True, targets_path=self.targets, facts_path=self.facts, local=self.local, outlets=OUTLETS,
                     log=lambda _: None, **options)

    def parked(self, why):
        """Run the pilot and expect its one review parked, for ``why``, and nothing filed."""
        self.assertEqual(self.run_pilot()["blocked"], 1)
        blocked = R.read_jsonl(self.local / "blocked.jsonl")
        self.assertEqual([b["target"] for b in blocked], [TARGET["id"]])
        self.assertTrue(any(why in e for e in blocked[0]["errors"]), blocked[0]["errors"])
        self.assertEqual(R.read_jsonl(self.facts), [])

    def test_parse_review_and_malformed_json(self):
        self.assertEqual(R.parse_review(self.review_path), REVIEW)
        self.review_path.write_text("{bad", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "invalid review JSON"):
            R.parse_review(self.review_path)

    def test_jsonl_reports_broken_line(self):
        self.targets.write_text('{}\n{"bad"\n', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "targets.jsonl:2"):
            R.read_jsonl(self.targets)

    def test_resume_is_idempotent_and_only_selects_pilot(self):
        self.assertEqual(self.run_pilot(), dict(selected=1, added=1, skipped=0, pending=0, refiled=0, blocked=0))
        first = self.facts.read_bytes()
        evidence = (self.local / "evidence.jsonl").read_bytes()
        self.assertEqual(self.run_pilot(), dict(selected=1, added=0, skipped=1, pending=0, refiled=0, blocked=0))
        self.assertEqual(self.facts.read_bytes(), first)
        self.assertEqual((self.local / "evidence.jsonl").read_bytes(), evidence)

    def test_refile_replaces_a_corrected_review(self):
        self.run_pilot()
        corrected = copy.deepcopy(REVIEW)
        corrected["fact"]["status"] = "reported"
        self.review_path.write_text(json.dumps(corrected), encoding="utf-8")
        self.run_pilot()   # without --refile the filed row stays
        self.assertEqual(R.read_jsonl(self.facts)[0]["status"], "confirmed")
        self.assertEqual(self.run_pilot(refile=True)["refiled"], 1)
        self.assertEqual(R.read_jsonl(self.facts)[0]["status"], "reported")
        self.assertEqual(len(R.read_jsonl(self.local / "evidence.jsonl")), 2)

    def test_pending_is_not_written_as_not_found(self):
        self.review_path.unlink()
        result = self.run_pilot()
        self.assertEqual(result["pending"], 1)
        self.assertFalse(self.facts.exists())
        self.assertEqual(R.read_jsonl(self.local / "pending.jsonl")[0]["target"], TARGET["id"])

    def test_quote_must_exist_in_saved_text(self):
        (self.local / "cache" / "page.txt").write_text("Unrelated article", encoding="utf-8")
        self.parked("quote not found")

    def test_quote_from_another_source_cannot_support_a_fact(self):
        (self.local / "cache" / "page.txt").write_text("https://unrelated.example.net/page\n" + QUOTE, encoding="utf-8")
        self.parked("quote not found")

    def test_a_page_the_search_tool_opened_cannot_back_a_fact(self):
        text = f"Medical update ({URL})\ncite turn3view0 [wordlim: 200] Source: open\n{QUOTE}"
        (self.local / "cache" / "page.txt").write_text(json.dumps(text), encoding="utf-8")
        self.parked("quote not found")
        (self.local / "cache" / "pages" / "example.org").mkdir(parents=True)   # read with fetch: allowed
        (self.local / "cache" / "pages" / "example.org" / "abc.txt").write_text(URL + "\n" + QUOTE, encoding="utf-8")
        self.assertEqual(self.run_pilot()["added"], 1)

    def test_saved_text_is_found_under_the_public_address(self):
        (self.local / "cache" / "page.txt").write_text(URL + "?utm_source=feed\n" + QUOTE, encoding="utf-8")
        self.assertEqual(self.run_pilot()["added"], 1)

    def test_search_batch_keeps_sources_separate(self):
        text = (f"Medical update ({URL})\n[cite] [wordlim: 25]\nNo diagnosis here.\n"
                f"Another article (https://unrelated.example.net/page)\n[cite] [wordlim: 25]\n{QUOTE}")
        (self.local / "cache" / "page.txt").write_text(json.dumps(text), encoding="utf-8")
        self.parked("quote not found")

    def test_a_failing_review_is_parked_and_the_rest_are_filed(self):
        other = dict(TARGET, id="nba:998:2024-01-10:knee", player="Riley Sample")
        R.write_jsonl(self.targets, [TARGET, other])
        wrong = copy.deepcopy(REVIEW)   # names a player the target isn't
        for row in [wrong, wrong["fact"]] + wrong["evidence"]:
            row["target"] = other["id"]
        (self.local / "reviews" / "01.json").write_text(json.dumps(wrong), encoding="utf-8")
        result = self.run_pilot()
        self.assertEqual((result["added"], result["blocked"]), (1, 1))
        self.assertEqual([f["target"] for f in R.read_jsonl(self.facts)], [TARGET["id"]])
        blocked = R.read_jsonl(self.local / "blocked.jsonl")
        self.assertEqual(blocked[0]["target"], other["id"])
        self.assertTrue(any("name Riley Sample" in e for e in blocked[0]["errors"]))
        wrong["fact"]["sources"][0]["headline"] = "Riley Sample medical update"   # fixed, it files on the next run
        for ev in wrong["evidence"]:
            ev["quote"] = QUOTE.replace("Morgan Example", "Riley Sample")
        (self.local / "reviews" / "01.json").write_text(json.dumps(wrong), encoding="utf-8")
        (self.local / "cache" / "page.txt").write_text(URL + "\n" + QUOTE + "\n" + ev["quote"], encoding="utf-8")
        self.assertEqual(self.run_pilot()["added"], 1)
        self.assertEqual(R.read_jsonl(self.local / "blocked.jsonl"), [])

    def test_a_filed_row_that_no_longer_passes_comes_off(self):
        self.run_pilot()
        fact = copy.deepcopy(FACT)   # the filed row is out of its window; its review is not, so it files again
        fact["sources"][0]["published"] = "2024-04-01"
        R.write_jsonl(self.facts, [fact])
        self.assertEqual(self.run_pilot()["added"], 1)
        self.assertEqual(R.read_jsonl(self.facts)[0]["sources"][0]["published"], "2024-01-11")
        broken = copy.deepcopy(REVIEW)   # when the review is wrong too, the row stays off, parked
        broken["fact"]["sources"][0]["published"] = "2024-04-01"
        self.review_path.write_text(json.dumps(broken), encoding="utf-8")
        R.write_jsonl(self.facts, [broken["fact"]])
        self.parked("outside the injury window")

    def test_a_batch_list_follows_its_injuries_new_window(self):
        R.write_jsonl(self.local / "nba-t1-01_targets.jsonl", [dict(TARGET, window=["2024-01-01", "2024-02-01"], batch_index=0)])
        self.assertEqual(R.follow_moves(targets_path=self.targets, facts_path=self.facts, local=self.local, log=lambda _: None),
                         dict(moved=0, set_aside=0))
        self.assertEqual(R.read_jsonl(self.local / "nba-t1-01_targets.jsonl"), [dict(TARGET, batch_index=0)])

    def test_research_follows_an_injury_to_its_new_id(self):
        old, gone = "nba:999:2024-01-10:other", "nba:555:2024-01-10:knee"
        self.run_pilot()
        moved = copy.deepcopy(REVIEW)   # filed when the listing had no body part; it has one now
        for row in [moved, moved["fact"]] + moved["evidence"]:
            row["target"] = old
        self.review_path.unlink()
        (self.local / "reviews" / "nba_999_2024-01-10_other.json").write_text(json.dumps(moved), encoding="utf-8")
        (self.local / "reviews" / "nba_555_2024-01-10_knee.json").write_text(
            json.dumps(dict(moved, target=gone, fact=dict(moved["fact"], target=gone), evidence=[])), encoding="utf-8")
        R.write_jsonl(self.facts, [moved["fact"], dict(moved["fact"], target=gone)])
        R.write_jsonl(self.local / "evidence.jsonl", moved["evidence"])
        R.write_jsonl(self.local / "batches.jsonl", [dict(batch="nba-t1-01", targets=[old, gone])])
        R.write_jsonl(self.local / "nba-t1-01_targets.jsonl", [dict(TARGET, id=old, region="other", batch_index=0)])
        self.assertEqual(R.follow_moves(targets_path=self.targets, facts_path=self.facts, local=self.local, log=lambda _: None),
                         dict(moved=1, set_aside=1))
        self.assertEqual([f["target"] for f in R.read_jsonl(self.facts)], [TARGET["id"]])
        self.assertEqual({e["target"] for e in R.read_jsonl(self.local / "evidence.jsonl")}, {TARGET["id"]})
        review = R.parse_review(self.local / "reviews" / "nba_999_2024-01-10_knee.json")
        self.assertEqual({review["target"], review["fact"]["target"]} | {e["target"] for e in review["evidence"]}, {TARGET["id"]})
        self.assertEqual(sorted(p.name for p in (self.local / "reviews").glob("*.json")), ["nba_999_2024-01-10_knee.json"])
        self.assertTrue((self.local / "retired" / "nba_555_2024-01-10_knee.json").exists())
        self.assertEqual(R.read_jsonl(self.local / "batches.jsonl")[0]["targets"], [TARGET["id"]])
        self.assertEqual(R.read_jsonl(self.local / "nba-t1-01_targets.jsonl"), [dict(TARGET, batch_index=0)])
        self.assertEqual(self.run_pilot()["skipped"], 1)   # and it is still filed

    def test_recovery_replaces_orphan_evidence(self):
        R.write_jsonl(self.local / "evidence.jsonl", REVIEW["evidence"])
        self.run_pilot()
        self.assertEqual(R.read_jsonl(self.local / "evidence.jsonl"), REVIEW["evidence"])

    def test_duplicate_reviews_are_rejected(self):
        (self.local / "reviews" / "01.json").write_text(json.dumps(REVIEW), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "duplicate review"):
            self.run_pilot()

    def test_an_audit_sheet_shows_each_fact_beside_its_quote(self):
        self.run_pilot()
        R.write_jsonl(self.local / "batches.jsonl", [dict(batch="nba-t1-01", targets=[TARGET["id"]])])
        path = R.audit_sheet("nba-t1-01", targets_path=self.targets, facts_path=self.facts, local=self.local)
        sheet = path.read_text(encoding="utf-8")
        self.assertIn("Morgan Example", sheet)
        self.assertIn("diagnosis.label = \"Torn meniscus\"", sheet)
        self.assertIn(QUOTE, sheet)
        self.assertEqual(R.audit_sheet("nba-t1-01", targets_path=self.targets, facts_path=self.facts, local=self.local)
                         .read_text(encoding="utf-8"), sheet)   # the same draw every time
        with self.assertRaisesRegex(ValueError, "no batch"):
            R.audit_sheet("nba-t1-99", targets_path=self.targets, facts_path=self.facts, local=self.local)

    def test_log_merge_does_not_duplicate_requests(self):
        row = dict(provider="web.run", query="fictional query", date="2026-10-20")
        R.write_jsonl(self.local / "log_worker.jsonl", [row])
        R.merge_logs(self.local)
        R.merge_logs(self.local)
        self.assertEqual(R.read_jsonl(self.local / "log.jsonl"), [row])
        updated = dict(row, outcome="returned text")
        R.write_jsonl(self.local / "log_worker.jsonl", [updated])
        R.merge_logs(self.local)
        self.assertEqual(R.read_jsonl(self.local / "log.jsonl"), [updated])


PAGE = """<html><head><title>Morgan Example update</title><script>var x = "hidden";</script></head>
<body><nav><a>Home</a></nav><h1>Morgan Example out</h1><p>Morgan Example has a <b>torn</b> meniscus.</p>
<ul><li>Out six weeks</li></ul><footer>Copyright</footer></body></html>"""


class FetchTest(unittest.TestCase):
    """A made-up site served by a fake ``get``: no request leaves the machine."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.local = Path(self.temp.name)
        self.clock, self.slept, self.asked = [1_000.0], [], []

    def fetch(self, robots, page=PAGE * 12):
        def get(url, headers=None):
            self.asked.append(url)
            self.clock[0] += 0.1
            if url.endswith("/robots.txt"):
                if isinstance(robots, Exception):
                    raise robots
                return robots if isinstance(robots, tuple) else (200, robots.encode())
            return 200, page.encode()

        def sleep(seconds):
            self.slept.append(seconds)
            self.clock[0] += seconds
        return R.fetch("https://site.example.com/news/story?utm_source=x", local=self.local, get=get,
                       now=lambda: self.clock[0], sleep=sleep)

    def test_an_allowed_page_is_saved_as_text(self):
        path, outcome = self.fetch("User-agent: *\nDisallow: /private/\n")
        self.assertEqual(outcome, "read")
        text = path.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("https://site.example.com/news/story\n"))   # its public address first
        self.assertIn("Morgan Example has a torn meniscus.", text)
        self.assertNotIn("hidden", text)
        self.assertNotIn("Copyright", text)
        self.assertEqual([r["action"] for r in R.read_jsonl(self.local / "log_fetch.jsonl")], ["robots", "fetch"])

    def test_a_site_that_turns_ai_readers_away_is_not_read(self):
        for robots in ("User-agent: ChatGPT-User\nDisallow: /\n", "User-agent: Claude-User\nDisallow: /news/\n",
                       "User-agent: *\nDisallow: /\n"):
            with self.subTest(robots=robots):
                path, outcome = self.fetch(robots)
                self.assertIsNone(path)
                self.assertIn("disallows", outcome)
        self.assertFalse(any(url.endswith("/story") for url in self.asked))   # only robots.txt was asked for

    def test_robots_that_cant_be_read_means_no_and_a_missing_one_means_yes(self):
        for robots in ((500, b""), ConnectionError("refused")):
            with self.subTest(robots=robots):
                path, outcome = self.fetch(robots)
                self.assertIsNone(path)
                self.assertIn("unreadable", outcome)
        path, outcome = self.fetch((404, b""))
        self.assertIsNotNone(path)

    def test_requests_to_one_site_are_spaced(self):
        self.fetch("User-agent: *\nAllow: /\n")
        self.assertTrue(self.slept and all(s <= R.DELAY for s in self.slept))
        self.assertGreaterEqual(sum(self.slept) + 0.1, R.DELAY)   # robots.txt, then the page, DELAY apart

    def test_a_short_or_paywalled_page_is_marked(self):
        _, outcome = self.fetch("User-agent: *\nAllow: /\n", page="<p>Subscribe to continue reading.</p>")
        self.assertIn("paywall", outcome)


if __name__ == "__main__":
    unittest.main()
