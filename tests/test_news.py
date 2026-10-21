import copy
import unittest

from injury_risk import news as N

# a made-up player and made-up sources: the checks, not anyone's real injury
TARGET = dict(id="nba:999:2024-01-10:knee", league="nba", tier=1, player="Test Player", player_id=999, team="TST",
              first_listed="2024-01-10", last_game_before="2024-01-08", back="2024-03-01", games_missed=20,
              listed_as="Left knee soreness", first_listed_as=None, region="knee", kind="region:knee",
              window=["2023-12-27", "2024-03-10"])
TEAM = "https://www.example.com/news/test-player-medical-update"
PAPER = "https://news.example.org/test-player-knee"
WIRE = "https://wire.example.net/test-player"
OUTLETS = {"Test team": "team", "Test Times": "local", "Test Wire": "wire", "Test Gazette": "local"}
FACT = dict(target=TARGET["id"], status="confirmed", diagnosis=dict(label="Torn meniscus", detail="tore it landing after a block"),
            side="left", setting="game", game=dict(date="2024-01-08", play="rebound"), contact="non_contact", mechanism="landing",
            surgery=dict(had=True, date="2024-01-15"), expected=dict(season_ending=False, weeks=[6, 8], reevaluate_weeks=None),
            sources=[dict(url=TEAM, outlet="Test team", published="2024-01-11", headline="Test Player medical update", official=True),
                     dict(url=PAPER, outlet="Test Times", published="2024-01-12", headline="Player out 6-8 weeks", official=False)])
QUOTES = {"diagnosis.label": "Torn meniscus", "side": "left", "setting": "game", "game.date": "2024-01-08", "game.play": "rebound",
          "contact": "non_contact", "mechanism": "landing", "surgery.had": True, "surgery.date": "2024-01-15",
          "expected.season_ending": False}
EVIDENCE = [dict(target=TARGET["id"], field=k, value=v, url=TEAM, quote="Test Player tore the left meniscus in the second half.",
                 retrieved="2026-10-21") for k, v in QUOTES.items()] + [
    dict(target=TARGET["id"], field="expected.weeks", value=[6, 8], url=PAPER, quote="Player will miss six to eight weeks.",
         retrieved="2026-10-21")]


def problems(fact=None, evidence=None, target=None, level="error"):
    t = target or TARGET
    return [p for p in N.check([fact or FACT], EVIDENCE if evidence is None else evidence, {t["id"]: t}, OUTLETS) if p[0] == level]


def from_the_wire(**changes):
    """The fact with its team source swapped for a wire story that says the same."""
    f = copy.deepcopy(FACT)
    f["sources"][0].update({"url": WIRE, "outlet": "Test Wire", "official": False, **changes})
    ev = [dict(e, url=WIRE) if e["url"] == TEAM else e for e in EVIDENCE]
    return f, ev


class CheckTest(unittest.TestCase):
    def test_a_sourced_confirmed_fact_passes(self):
        self.assertEqual(problems(), [])

    def test_every_fact_needs_a_quote_behind_it(self):
        ev = [e for e in EVIDENCE if e["field"] != "mechanism"]
        self.assertTrue(any("mechanism" in p[2] for p in problems(evidence=ev)))

    def test_the_quote_must_come_from_the_rows_sources(self):
        ev = [dict(e, url="https://elsewhere.example.net/x") if e["field"] == "side" else e for e in EVIDENCE]
        self.assertTrue(any("side" in p[2] for p in problems(evidence=ev)))

    def test_confirmed_needs_the_teams_word_or_two_outlets(self):
        f, ev = from_the_wire()
        self.assertTrue(any("confirmed" in p[2] for p in problems(f, ev)))
        # the wire story credits the team: confirmed, and the audit checks the credit unless the quote shows who said it
        credited = [dict(e, attributed="team") if e["field"] == "diagnosis.label" else e for e in ev]
        self.assertEqual(problems(f, credited), [])
        self.assertTrue(any("check the credit" in p[2] for p in problems(f, credited, level="warning")))
        said = [dict(e, quote="Test Player tore the left meniscus, the team announced.") if e["field"] == "diagnosis.label" else e
                for e in credited]
        self.assertEqual(problems(f, said), [])
        self.assertFalse(any("check the credit" in p[2] for p in problems(f, said, level="warning")))
        # a second outlet says it too
        second = ev + [dict(ev[0], url=PAPER, quote="Test Player has a torn meniscus.")]
        self.assertEqual(problems(f, second), [])
        f["status"] = "reported"
        self.assertEqual(problems(f, ev), [])

    def test_copies_of_one_story_and_rumours_are_not_two_outlets(self):
        f, ev = from_the_wire()
        f["sources"][1].update(via="Test Wire")   # the paper ran the wire's story
        second = ev + [dict(ev[0], url=PAPER, quote="Test Player has a torn meniscus.")]
        self.assertTrue(any("confirmed" in p[2] for p in problems(f, second)))
        f["sources"][1].pop("via")
        rumour = [dict(e, quote="Test Player reportedly has a torn meniscus.") if e["field"] == "diagnosis.label" else e for e in second]
        self.assertTrue(any("confirmed" in p[2] for p in problems(f, rumour)))

    def test_official_follows_the_outlets_kind(self):
        f = copy.deepcopy(FACT)
        f["sources"][0]["official"] = False
        self.assertTrue(any("official must be true" in p[2] for p in problems(f)))
        f, ev = from_the_wire(official=True)
        self.assertTrue(any("official must be false" in p[2] for p in problems(f, ev)))
        f = copy.deepcopy(FACT)
        f["sources"][1]["outlet"] = "Unlisted Weekly"
        self.assertTrue(any("outlets.json" in p[2] for p in problems(f)))

    def test_every_source_names_the_player_and_backs_a_fact(self):
        f = copy.deepcopy(FACT)
        f["sources"][0]["headline"] = "Medical update"
        ev = [dict(e, quote="The meniscus is torn.") if e["url"] == TEAM else e for e in EVIDENCE]
        self.assertTrue(any("name Test Player" in p[2] for p in problems(f, ev)))
        f = copy.deepcopy(FACT)
        f["sources"].append(dict(url="https://other.example.com/x", outlet="Test Gazette", published="2024-01-12",
                                 headline="Test Player out", official=False))
        self.assertTrue(any("backs no fact" in p[2] for p in problems(f)))

    def test_addresses_must_be_public_and_stable(self):
        for url, why in (("https://api-hub-dev.example.com/news/x", "development server"),
                         ("https://www.example.com/news/x?utm_source=feed", "tracking"),
                         ("https://www.foxsports.com/college-basketball/test-player-player?p=4", "rolling player feed"),
                         ("https://ak-static.cms.nba.com/referee/injury/Injury-Report_2024-01-11_05PM.pdf", "listings come from")):
            with self.subTest(url=url):
                f = copy.deepcopy(FACT)
                f["sources"][0]["url"] = url
                ev = [dict(e, url=url) if e["url"] == TEAM else e for e in EVIDENCE]
                self.assertTrue(any(why in p[2] for p in problems(f, ev)))
        f = copy.deepcopy(FACT)
        f["sources"][1]["url"] = "https://news.example.org/amp/test-player-knee"
        ev = [dict(e, url=f["sources"][1]["url"]) if e["url"] == PAPER else e for e in EVIDENCE]
        self.assertEqual(problems(f, ev), [])
        self.assertTrue(any("AMP" in p[2] for p in problems(f, ev, level="warning")))

    def test_what_each_status_means(self):
        f = copy.deepcopy(FACT)
        f["diagnosis"]["label"] = None
        ev = [e for e in EVIDENCE if e["field"] != "diagnosis.label"]
        self.assertTrue(any("partial" in p[2] for p in problems(f, ev)))
        f["status"] = "partial"
        self.assertEqual(problems(f, ev), [])
        self.assertTrue(any("partial rows have no diagnosis" in p[2] for p in problems(dict(FACT, status="partial"))))
        bare = dict(target=TARGET["id"], status="partial", diagnosis=dict(label=None, detail=None), sources=FACT["sources"])
        self.assertTrue(any("at least one fact" in p[2] for p in problems(bare, [])))
        conflict = dict(copy.deepcopy(FACT), status="conflicting")
        conflict["diagnosis"]["detail"] = None
        self.assertTrue(any("conflicting needs" in p[2] for p in problems(conflict)))

    def test_timelines_may_be_open_ended(self):
        for weeks, ok in (([4, None], True), ([4, 4], True), ([None, 4], False), ([5, 4], False), ([True, 2], False)):
            with self.subTest(weeks=weeks):
                f = copy.deepcopy(FACT)
                f["expected"]["reevaluate_weeks"] = weeks
                ev = EVIDENCE + [dict(EVIDENCE[0], field="expected.reevaluate_weeks", value=weeks)]
                self.assertEqual(not any("reevaluate_weeks must" in p[2] for p in problems(f, ev)), ok)

    def test_an_injury_list_is_the_listing_again(self):
        for quote in ("Test Player (left knee soreness)", "OUT - Test Player (torn left meniscus)",
                      "Team forward Test Player (left knee soreness): OUT", "Test Player (sore left knee – out)"):
            with self.subTest(quote=quote):
                ev = [dict(e, quote=quote) if e["field"] == "side" else e for e in EVIDENCE]
                self.assertTrue(any("injury list" in p[2] for p in problems(evidence=ev)))
        said = "Test Player (left knee soreness) will miss six to eight weeks, the team said."   # a report around it
        ev = [dict(e, quote=said) if e["field"] == "side" else e for e in EVIDENCE]
        self.assertEqual(problems(evidence=ev), [])
        cited = "Test Player was listed on the injury report with a torn left meniscus."
        ev = [dict(e, quote=cited) if e["field"] == "side" else e for e in EVIDENCE]
        self.assertEqual(problems(evidence=ev), [])
        self.assertTrue(any("cites the listing" in p[2] for p in problems(evidence=ev, level="warning")))

    def test_a_team_report_credits_the_team(self):
        f, ev = from_the_wire()
        said = [dict(e, attributed="team", quote="The team reported Sunday that Test Player tore the left meniscus.")
                if e["field"] == "diagnosis.label" else e for e in ev]
        self.assertEqual(problems(f, said), [])

    def test_lower_leg_bone_injuries_fit_the_calf(self):
        # the profiles file the shin, tibia and fibula under "calf"
        shin = dict(TARGET, listed_as="Left shin soreness", region="calf", kind="region:calf")
        for label in ("Stress fracture", "Stress reaction", "Leg fracture"):
            with self.subTest(label=label):
                f = copy.deepcopy(FACT)
                f["diagnosis"]["label"] = label
                ev = [dict(e, value=label) if e["field"] == "diagnosis.label" else e for e in EVIDENCE]
                self.assertFalse(any("does not fit" in p[2] for p in problems(f, ev, target=shin)))

    def test_a_fracture_at_the_knee_fits_the_knee_and_the_lower_leg(self):
        shin = dict(TARGET, listed_as="Left fibula fracture", region="calf", kind="region:calf")   # the head of the fibula
        for label, target, fits in (("Knee fracture", TARGET, True), ("Knee fracture", shin, True),
                                    ("Leg fracture", TARGET, True), ("Foot fracture", TARGET, False)):
            with self.subTest(label=label, region=target["region"]):
                f = copy.deepcopy(FACT)
                f["diagnosis"]["label"] = label
                ev = [dict(e, value=label) if e["field"] == "diagnosis.label" else e for e in EVIDENCE]
                self.assertEqual(not any("does not fit" in p[2] for p in problems(f, ev, target=target)), fits)

    def test_an_offseason_operation_before_the_window_is_checked_not_refused(self):
        f = copy.deepcopy(FACT)
        f["surgery"]["date"] = "2023-07-11"
        ev = [dict(e, value="2023-07-11") if e["field"] == "surgery.date" else e for e in EVIDENCE]
        self.assertEqual(problems(f, ev), [])
        self.assertTrue(any("offseason" in p[2] for p in problems(f, ev, level="warning")))

    def test_facts_must_fit_the_injury(self):
        f = copy.deepcopy(FACT)
        f["diagnosis"]["label"] = "Achilles tear"
        ev = [dict(e, value="Achilles tear") if e["field"] == "diagnosis.label" else e for e in EVIDENCE]
        self.assertTrue(any("does not fit" in p[2] for p in problems(f, ev)))
        f["status"] = "conflicting"   # the news says Achilles and the listing says knee: filed as a disagreement
        self.assertFalse(any("does not fit" in p[2] for p in problems(f, ev)))
        f = copy.deepcopy(FACT)
        f["side"] = "right"
        ev = [dict(e, value="right") if e["field"] == "side" else e for e in EVIDENCE]
        self.assertTrue(any("wrong injury" in p[2] for p in problems(f, ev)))
        f["status"] = "conflicting"
        self.assertFalse(any("wrong injury" in p[2] for p in problems(f, ev)))

    def test_dates_must_fit_the_window(self):
        f = copy.deepcopy(FACT)
        f["sources"][1]["published"] = "2023-11-01"
        self.assertTrue(any("before the injury window" in p[2] for p in problems(f)))

        def game_on(day):
            g = copy.deepcopy(FACT)
            g["game"]["date"] = day
            return g, [dict(e, value=day) if e["field"] == "game.date" else e for e in EVIDENCE]
        self.assertTrue(any("game.date" in p[2] for p in problems(*game_on("2024-02-01"))))   # weeks after: another injury
        g, ev = game_on("2024-01-12")   # two days after the first listing: the listing's date is wrong
        self.assertEqual(problems(g, ev), [])
        self.assertTrue(any("listing's date is probably wrong" in p[2] for p in problems(g, ev, level="warning")))

    def test_a_game_injury_without_its_date_is_flagged(self):
        f = copy.deepcopy(FACT)
        f["game"]["date"] = None
        ev = [e for e in EVIDENCE if e["field"] != "game.date"]
        self.assertEqual(problems(f, ev), [])
        self.assertTrue(any("without its game.date" in p[2] for p in problems(f, ev, level="warning")))

    def test_only_known_values_and_no_copied_wording(self):
        f = copy.deepcopy(FACT)
        f["mechanism"] = "bad luck"
        self.assertTrue(any("allowed values" in p[2] for p in problems(f)))
        f = copy.deepcopy(FACT)
        f["diagnosis"]["detail"] = "Test Player tore the left meniscus"
        self.assertTrue(any("copies" in p[2] for p in problems(f)))
        long_quote = [dict(e, quote="x" * (N.QUOTE_MAX + 1)) for e in EVIDENCE]
        self.assertTrue(any("quote" in p[2] for p in problems(evidence=long_quote)))
        f = copy.deepcopy(FACT)
        f["diagnosis"]["label"] = "Invented"
        ev = [dict(e, value="Invented") if e["field"] == "diagnosis.label" else e for e in EVIDENCE]
        self.assertTrue(any("allowed values" in p[2] for p in problems(f, ev)))   # an error, not a crash

    def test_not_found_carries_no_facts(self):
        self.assertEqual(problems(dict(target=TARGET["id"], status="not_found", sources=[])), [])
        self.assertTrue(problems(dict(target=TARGET["id"], status="not_found", side="left", sources=[])))

    def test_unknown_targets_and_repeats(self):
        self.assertTrue(problems(dict(FACT, target="nba:1:2024-01-01:knee")))
        both = N.check([FACT, FACT], EVIDENCE, {TARGET["id"]: TARGET}, OUTLETS)
        self.assertTrue(any("twice" in p[2] for p in both))


class HelperTest(unittest.TestCase):
    def test_public_addresses(self):
        self.assertEqual(N.canonical("https://api-hub-dev.nba.com/news/x?lctg=abc&id=7#top"), "https://www.nba.com/news/x?id=7")
        self.assertEqual(N.canonical("https://news.example.org/a/story-1.php/"), "https://news.example.org/a/story-1.php")

    def test_surnames(self):
        for name, expected in (("Test Player", "player"), ("Pat Example Jr.", "example"), ("Robin Hyphen-Name", "hyphen-name"),
                               ("Jonas Ćelić III", "celic")):
            self.assertEqual(N.surname(name), expected)

    def test_vague_listings_and_what_the_news_added(self):
        self.assertTrue(N.vague_listing(TARGET))
        self.assertFalse(N.vague_listing(dict(TARGET, listed_as="Left knee sprain")))
        self.assertTrue(N.vague_listing(dict(TARGET, league="college", diagnosis_listed=None)))
        self.assertTrue(N.gained(FACT, TARGET))
        plain = dict(diagnosis=dict(label="Hip injury"), contact=None, mechanism="unknown", game=dict(play=None))
        self.assertFalse(N.gained(plain, TARGET))


class PilotTest(unittest.TestCase):
    def test_quotas_without_repeats(self):
        rows = []
        for i in range(200):
            nba = i % 2 == 0
            rows.append(dict(id=f"t{i}", league="nba" if nba else "college", player=f"P{i}", tier=1 + (i % 3 if not nba else 0),
                             kind=["region:knee", "acl", "hamstring", "concussion"][(i // 2) % 4] if nba else "region:ankle",
                             games_missed=12, first_listed=f"20{20 + i % 6}-01-15"))
        chosen = N.pilot(rows)
        self.assertEqual(len(chosen), len(set(chosen)))
        self.assertEqual(len(chosen), sum(n for *_, n in N.QUOTAS))   # no anchors among made-up players

    def test_researched_injuries_follow_their_moves(self):
        rows = [dict(id=i, first_listed=i.split(":")[2]) for i in (
            "nba:7:2024-01-13:knee", "nba:7:2024-03-01:knee", "nba:8:2024-01-10:ankle", "nba:10:2024-01-10:ankle",
            "nba:10:2024-01-12:hip", "nba:11:2024-02-01:foot", "nba:12:2024-02-01:foot")]
        found = N.moved_ids(rows, ["nba:7:2024-01-10:knee", "nba:8:2024-01-10:knee", "nba:9:2024-01-10:knee",
                                   "nba:10:2024-01-10:other", "nba:11:2024-02-01:other", "nba:11:2024-02-03:other",
                                   "nba:12:2024-02-01:foot", "nba:12:2024-02-02:other"])
        self.assertEqual(found, {
            "nba:7:2024-01-10:knee": "nba:7:2024-01-13:knee",     # its date moved
            "nba:8:2024-01-10:knee": "nba:8:2024-01-10:ankle",    # its body part moved: the one injury listed then
            "nba:9:2024-01-10:knee": None,                        # gone
            "nba:10:2024-01-10:other": None,                      # two injuries listed then
            "nba:11:2024-02-01:other": None, "nba:11:2024-02-03:other": None,   # two ids want one injury
            "nba:12:2024-02-01:foot": "nba:12:2024-02-01:foot", "nba:12:2024-02-02:other": None})   # its own id stays


if __name__ == "__main__":
    unittest.main()
