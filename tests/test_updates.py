import copy
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock

from injury_risk import updates as U
from injury_risk import injury_reports
from injury_risk.update_http import Client, Robots, SourceError

NOW = datetime(2026, 11, 3, 22, tzinfo=timezone.utc)
SPEC = dict(id="test-nba", name="Test source", league="nba", scope="Test games", kind="fake", enabled=True, max_age_hours=36)


def snapshot(status="out", stamp=None):
    return dict(report_at=stamp or U.stamp(NOW), observed_at=U.stamp(NOW), sha256="a" * 64,
                rows=[U.row(SPEC, player="Test Player", team="BOS", status=status, category="injury", region="knee", game_date="2026-11-03")],
                not_submitted=[], pages_checked=1)


def empty():
    return dict(schema_version=1, generated_at=None, sources={}, events=[])


def run(previous=None, fresh=None, now=NOW, error=None):
    fn = Mock(side_effect=error, return_value=fresh or snapshot())
    return U.collect([SPEC], previous or empty(), now, None, collectors={"fake": fn}, log=lambda *a, **k: None)


class StateTest(unittest.TestCase):
    def test_archive_preserves_old_observations_when_status_changes(self):
        first = run()
        second = run(first, snapshot("available"), now=NOW + timedelta(days=1))
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            a = U.archive_run(first, root, now=NOW)
            before = a.read_bytes()
            b = U.archive_run(second, root, now=NOW + timedelta(days=1))
            self.assertNotEqual(a, b)
            self.assertEqual(a.read_bytes(), before)
            self.assertEqual(U.archive_run(first, root, now=NOW), a)
            self.assertEqual(len(list(root.rglob('*.json'))), 2)
            self.assertEqual(json.loads(before)['sources']['test-nba']['snapshot']['rows'][0]['status'], 'out')

    def test_archive_keeps_old_observations_after_the_working_log_expires(self):
        first = run()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            old = U.archive_run(first, root, now=NOW)
            before = old.read_bytes()
            later = run(first, now=NOW + timedelta(days=100), error=SourceError('unavailable'))
            self.assertEqual(later['events'], [])
            self.assertEqual(old.read_bytes(), before)

    def test_first_cloud_run_keeps_the_reviewed_published_baseline(self):
        original = run()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'updates.json'
            U.write_json(path, U.public_data(original))
            self.assertEqual(U.seed_state(path, NOW), original)

    def test_offseason_skips_network_without_claiming_no_injuries(self):
        spec = dict(SPEC, league="wnba", active_months=[5, 6, 7, 8, 9, 10])
        fn = Mock()
        state = U.collect([spec], empty(), NOW, None, collectors={"fake": fn}, log=lambda *a, **k: None)
        self.assertEqual(state["sources"][spec["id"]]["status"], "paused")
        fn.assert_not_called()

    def test_repeated_pull_is_idempotent_and_first_observation_is_not_an_onset(self):
        first = run()
        second = run(first, now=NOW + timedelta(hours=6))
        self.assertEqual(len(first["events"]), 1)
        self.assertEqual(first["events"][0]["kind"], "first_observed")
        self.assertEqual(len(second["events"]), 1)
        self.assertEqual(first["sources"]["test-nba"]["snapshot"]["rows"][0]["first_seen"],
                         second["sources"]["test-nba"]["snapshot"]["rows"][0]["first_seen"])

    def test_failure_keeps_previous_good_snapshot_and_records_failure(self):
        first = run()
        second = run(first, error=SourceError("HTTP 403"), now=NOW + timedelta(hours=6))
        a, b = first["sources"]["test-nba"], second["sources"]["test-nba"]
        self.assertEqual(a["snapshot"], b["snapshot"])
        self.assertEqual(a["last_success_at"], b["last_success_at"])
        self.assertEqual(b["status"], "error")
        self.assertNotEqual(a["checked_at"], b["checked_at"])

    def test_unexpected_document_error_is_parked_without_publishing_source_text(self):
        state = run(run(), error=RuntimeError('Private PDF text'))
        source = state["sources"]["test-nba"]
        self.assertEqual(source["status"], "error")
        self.assertIsNotNone(source["snapshot"])
        self.assertNotIn('Private PDF text', json.dumps(U.public_data(state)))

    def test_one_failure_does_not_block_other_sources(self):
        bad = dict(SPEC, id="failed", kind="broken")
        state = U.collect([bad, SPEC], empty(), NOW, None,
                          collectors={"broken": Mock(side_effect=SourceError("blocked")), "fake": Mock(return_value=snapshot())},
                          log=lambda *a, **k: None)
        self.assertEqual(state["sources"]["failed"]["status"], "error")
        self.assertEqual(state["sources"]["test-nba"]["status"], "ok")

    def test_removal_is_not_recovery(self):
        first = run()
        fresh = snapshot()
        fresh["rows"] = []
        second = run(first, fresh)
        self.assertEqual(second["events"][-1]["kind"], "not_in_latest_report")
        self.assertEqual(second["events"][-1]["row"]["status"], "out")

    def test_status_changes_are_logged(self):
        second = run(run(), snapshot("available"))
        self.assertEqual(second["events"][-1]["kind"], "changed")
        self.assertEqual(len(second["events"]), 2)

    def test_source_date_not_fetch_date_controls_freshness(self):
        state = run(fresh=snapshot(stamp=U.stamp(NOW - timedelta(days=2))))
        self.assertEqual(state["sources"]["test-nba"]["status"], "stale")

    def test_older_report_does_not_roll_state_back(self):
        state = run(run(), snapshot(stamp=U.stamp(NOW - timedelta(hours=1))))
        source = state["sources"]["test-nba"]
        self.assertEqual(source["status"], "error")
        self.assertEqual(source["snapshot"]["report_at"], U.stamp(NOW))

    def test_duplicate_or_raw_text_quarantines_the_source(self):
        for change in (lambda s: s["rows"].append(copy.deepcopy(s["rows"][0])),
                       lambda s: s["rows"][0].update(reason="Private report wording"),
                       lambda s: s["rows"][0].update(region="Private report wording")):
            s = snapshot()
            change(s)
            result = run(fresh=s)
            self.assertEqual(result["sources"]["test-nba"]["status"], "error")
            self.assertIsNone(result["sources"]["test-nba"]["snapshot"])

    def test_leagues_and_teams_are_not_merged_by_name(self):
        a = U.row(SPEC, player="Same Name", team="BOS", status="out")
        b = U.row(dict(SPEC, league="wnba"), player="Same Name", team="BOS", status="out")
        c = U.row(SPEC, player="Same Name", team="LAL", status="out")
        self.assertEqual(len({a["id"], b["id"], c["id"]}), 3)

    def test_corrupt_state_fails_instead_of_starting_over(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "state.json"
            path.write_text('{"schema_version": 99}', encoding="utf-8")
            with self.assertRaises(ValueError):
                U.read_state(path, NOW)

    def test_no_raw_evidence_in_public_export(self):
        result = U.public_data(run())
        text = json.dumps(result)
        self.assertNotIn('"reason":', text)
        self.assertNotIn('"detail":', text)
        self.assertNotIn('"quote":', text)


class ReportTest(unittest.TestCase):
    def test_wnba_team_mapping_is_separate(self):
        state = dict(away="WAS", home="CON", team=None)
        cells = {"team": [{"text": "WashingtonMystics", "top": 10, "x0": 50}]}
        problems = []
        injury_reports._apply_group(state, cells, problems, 1, {"WAS": "Washington Mystics", "CON": "Connecticut Sun"})
        self.assertEqual(state["team"], "WAS")
        self.assertEqual(problems, [])
        injury_reports._apply_group(state, cells, problems, 1, {"WAS": "Washington Wizards"})
        self.assertTrue(problems)

    def test_daily_snapshot_waits_for_publication_and_uses_eastern_date(self):
        from unittest.mock import patch
        spec = dict(SPEC, url="https://example.com/{day}.pdf")
        with patch.object(U, 'read_nba_pdf') as read:
            U.nba_daily_report(spec, None, datetime(2026, 11, 3, 22, 10, tzinfo=timezone.utc))
            self.assertEqual(read.call_args.args[-1], 'https://example.com/2026-11-02.pdf')
            U.nba_daily_report(spec, None, datetime(2026, 11, 3, 22, 40, tzinfo=timezone.utc))
            self.assertEqual(read.call_args.args[-1], 'https://example.com/2026-11-03.pdf')

    def test_nba_links_are_sorted_by_eastern_time_not_html_order(self):
        urls = ['https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-03_04_00PM.pdf',
                'https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-03_11_00AM.pdf',
                'https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-03_09_00PM.pdf']
        links = U.report_links(' '.join(urls), NOW)
        self.assertEqual([url for _, url in links], urls[:2])

    def test_status_does_not_infer_medical_diagnosis(self):
        r = U.row(dict(SPEC, league="ncaa_wbb"), player="Example Player", team="Example University", status="out")
        self.assertEqual(r["category"], "unknown")
        self.assertIsNone(r["injury_type"])

    def test_unknown_status_is_not_silently_filed(self):
        with self.assertRaises(SourceError):
            U.scac_status("New status layout")


class RobotsTest(unittest.TestCase):
    def test_wildcards_and_longest_allow_rule(self):
        r = Robots('User-agent: *\nDisallow: /\nAllow: /reports/\nDisallow: /*?token=*\n')
        self.assertTrue(r.policy('BasketballInjuryProject', '/reports/latest.pdf')[0])
        self.assertFalse(r.policy('BasketballInjuryProject', '/account')[0])
        self.assertFalse(r.policy('BasketballInjuryProject', '/page?token=secret')[0])

    def test_specific_bot_block_and_delay(self):
        r = Robots('User-agent: *\nAllow: /\nCrawl-delay: 5\nUser-agent: ChatGPT-User\nDisallow: /\n')
        self.assertFalse(r.policy('ChatGPT-User', '/report')[0])
        self.assertEqual(r.policy('BasketballInjuryProject', '/report'), (True, 5))

    def test_html_is_not_a_valid_access_policy(self):
        with self.assertRaises(SourceError):
            Robots('<!doctype html><html>Application shell</html>')

    def test_redirect_destination_is_checked_before_it_is_fetched(self):
        c = Client(['example.com'], Path('unused'), sleep=lambda _: None)
        c._policy = Mock(return_value=0)
        c._request = Mock(side_effect=[(302, {'Location': 'http://127.0.0.1/private'}, b'')])
        # Use the real host validation at the redirect's policy boundary.
        c._policy = lambda url: (c._address(url) and 0)
        with self.assertRaises(SourceError):
            c.get('https://example.com/report')
        self.assertEqual(c._request.call_count, 1)

    def test_rate_limit_does_not_trigger_unbounded_retries(self):
        c = Client(['example.com'], Path('unused'), sleep=lambda _: None)
        c._policy = Mock(return_value=0)
        c._request = Mock(return_value=(429, {'Retry-After': '3600'}, b''))
        with self.assertRaises(SourceError):
            c.get('https://example.com/report')
        self.assertEqual(c._request.call_count, 1)


if __name__ == '__main__':
    unittest.main()
