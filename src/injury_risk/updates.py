"""Collect current availability separately from the frozen historical research.

The saved state and site export contain normalized facts only. A failed or incomplete
source keeps its last validated snapshot; missing players are never declared recovered.
"""
from __future__ import annotations

import copy
import hashlib
import html
import json
import re
import shutil
import unicodedata
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from zoneinfo import ZoneInfo

from . import injury_reports, ncaa_injuries, reasons
from .paths import DATA, ROOT
from .update_http import Client, SourceError

CONFIG = ROOT / "config" / "update_sources.json"
LOCAL = DATA / "updates"
LEAGUES = {"nba": "NBA", "ncaa_mbb": "NCAA men", "wnba": "WNBA", "ncaa_wbb": "NCAA women"}
STATUSES = {"out", "doubtful", "questionable", "probable", "available", "day_to_day", "out_for_season", "unknown"}
CLASSES = {"injury", "illness", "management", "non_medical", "unknown"}
ROW_FIELDS = {"id", "league", "team", "player", "game_date", "status", "category", "region", "injury_type", "conference", "first_seen", "last_seen"}
SNAPSHOT_FIELDS = {"report_at", "observed_at", "sha256", "rows", "not_submitted", "pages_checked"}
SOURCE_FIELDS = {"league", "name", "scope", "status", "message", "checked_at", "last_success_at", "max_age_hours", "snapshot"}
PDF = re.compile(r"https://ak-static\.cms\.nba\.com/referee/injury/Injury-Report_(\d{4}-\d{2}-\d{2})_(\d{2})(?:_(\d{2}))?(AM|PM)\.pdf")
ET = ZoneInfo("America/New_York")


def stamp(value):
    return value.astimezone(timezone.utc).isoformat(timespec="seconds")


def instant(value):
    out = datetime.fromisoformat(value)
    if out.tzinfo is None:
        raise ValueError("timestamp has no timezone")
    return out


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n", encoding="utf-8")
    temp.replace(path)


def load_config(path=CONFIG):
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("schema_version") != 1 or not config.get("sources"):
        raise ValueError("unsupported or empty source configuration")
    ids = set()
    for source in config["sources"]:
        if source["id"] in ids or source["league"] not in LEAGUES:
            raise ValueError("duplicate source or unknown league")
        ids.add(source["id"])
        if source["enabled"] and (source["kind"] not in COLLECTORS or not source.get("policy_reviewed")):
            raise ValueError("enabled source needs a collector and a recorded policy review")
        if not 1 <= source["max_age_hours"] <= 168:
            raise ValueError("invalid source freshness limit")
    return config["sources"]


def normalize(text):
    return " ".join(unicodedata.normalize("NFKC", text).split())


def row(source, *, player, team, status, category="unknown", region=None, injury_type=None, game_date=None, conference=None):
    player, team = normalize(player), normalize(team)
    key = "|".join([source["id"], source["league"], team.casefold(), player.casefold(), game_date or ""])
    return dict(id=hashlib.sha256(key.encode()).hexdigest()[:24], league=source["league"], player=player, team=team,
                game_date=game_date, status=status, category=category, region=region, injury_type=injury_type, conference=conference)


def report_links(page, now):
    found = []
    for m in PDF.finditer(html.unescape(page)):
        day, hour, minute, ampm = m.groups()
        when = datetime.strptime(f"{day} {hour}:{minute or '00'}{ampm}", "%Y-%m-%d %I:%M%p").replace(tzinfo=ET)
        if when <= now + timedelta(minutes=5):
            found.append((when, m.group()))
    return sorted(set(found), reverse=True)


def nba_report(source, client, now):
    local = now.astimezone(ET)
    start = local.year if local.month >= 7 else local.year - 1
    url = source["url"].format(start=start, end=str(start + 1)[-2:])
    body, _, _ = client.get(url)
    links = report_links(body.decode("utf-8", "replace"), now)
    if not links:
        raise SourceError("no dated report links found; check the season URL or page layout")
    when, pdf_url = links[0]
    return read_nba_pdf(source, client, now, when, pdf_url)


def nba_daily_report(source, client, now):
    """The documented 5 PM ET snapshot, with a 30-minute publication allowance.

    This public PDF host permits collection. It does not require crawling the
    separate report-index site, which currently refuses this project's reader.
    """
    local = now.astimezone(ET)
    when = local.replace(hour=17, minute=0, second=0, microsecond=0)
    if local < when + timedelta(minutes=30):
        when -= timedelta(days=1)
    return read_nba_pdf(source, client, now, when, source["url"].format(day=when.date().isoformat()))


def read_nba_pdf(source, client, now, when, pdf_url):
    body, path, digest = client.get(pdf_url)
    if not body.startswith(b"%PDF"):
        raise SourceError("report URL did not return a PDF")
    parsed = injury_reports.parse_pdf(path, team_names=source.get("team_names"))
    if parsed["problems"] or not parsed["stamp"]:
        raise SourceError("report layout or team mapping failed validation")
    report_time = datetime.fromisoformat(parsed["stamp"]).replace(tzinfo=ET)
    if abs((report_time - when).total_seconds()) > 60:
        raise SourceError("report header does not match the linked timestamp")
    rows = []
    for r in parsed["rows"]:
        facts = reasons.classify(r["reason"])
        category = facts["reason_class"]
        if category not in CLASSES:
            category = "unknown"
        # Keep the broad body region and type, never the report's prose.
        rows.append(row(source, player=r["player"], team=r["team"] or "", status=r["status"].lower(),
                        game_date=r["game_date"], category=category, region=facts["region"], injury_type=facts["injury_type"]))
    if not rows and not parsed["not_submitted"]:
        raise SourceError("empty report without an explicit coverage statement")
    return dict(report_at=stamp(report_time), observed_at=stamp(now), sha256=digest, rows=rows,
                not_submitted=parsed["not_submitted"], pages_checked=1)


def scac_status(text):
    value = normalize(text).lower()
    if re.search(r"out (?:for |the )?season|out indefinitely", value):
        return "out_for_season" if "season" in value else "out"
    if value.startswith("out"):
        return "out"
    if "day-to-day" in value or "day to day" in value:
        return "day_to_day"
    if value in STATUSES:
        return value
    if "game time" in value or "game-time" in value or value == "gtd":
        return "questionable"
    raise SourceError("unrecognized availability status in conference listing")


def scac(source, client, now):
    body, _, digest = client.get(source["url"])
    page = body.decode("utf-8", "replace")
    first_page, first_digest = page, digest
    groups = re.findall(r'<option[^>]*value="(injuries\.asp[^"]*)"[^>]*>([^<]*)</option>', page, re.I)
    if not 20 <= len(groups) <= 64 or len(set(name for _, name in groups)) != len(groups):
        raise SourceError("conference directory is incomplete or its format changed")
    rows, hashes = [], []
    for path, name in groups:
        url = urljoin(source["url"], html.unescape(path))
        if url != source["url"]:
            body, _, digest = client.get(url)
            page = body.decode("utf-8", "replace")
        else:
            page, digest = first_page, first_digest
        hashes.append(digest)
        conference = normalize(html.unescape(name))
        listings = ncaa_injuries.parse(page, conference)
        if not listings and "no injuries to report" not in page.lower():
            raise SourceError("conference page has neither listings nor an explicit empty report")
        for r in listings:
            group = ncaa_injuries.group_of(r["injury"])
            category = {"Not injury related": "non_medical", "Undisclosed": "unknown", "Illness": "illness"}.get(group, "injury")
            if group == "Other":
                category = "unknown"
            facts = reasons.classify("Injury/Illness - " + r["injury"]) if category == "injury" else {}
            rows.append(row(source, player=r["player"], team=r["team"], status=scac_status(r["status"]), category=category,
                            region=facts.get("region"), injury_type=facts.get("injury_type"), conference=conference))
    return dict(report_at=None, observed_at=stamp(now), sha256=hashlib.sha256("".join(hashes).encode()).hexdigest(),
                rows=rows, not_submitted=[], pages_checked=len(groups))


COLLECTORS = {"nba_report": nba_report, "nba_daily_report": nba_daily_report, "scac": scac}


def validate_snapshot(snapshot, league, now, *, check_game_window=True):
    if set(snapshot) != SNAPSHOT_FIELDS:
        raise ValueError("snapshot contains unsupported or missing fields")
    for field in ("report_at", "observed_at"):
        if snapshot[field] and instant(snapshot[field]) > now + timedelta(minutes=5):
            raise ValueError("source timestamp is in the future")
    if not re.fullmatch(r"[a-f0-9]{64}", snapshot["sha256"]):
        raise ValueError("invalid content hash")
    if not isinstance(snapshot["rows"], list) or len(snapshot["rows"]) > 15000:
        raise ValueError("invalid row count")
    ids = set()
    for r in snapshot["rows"]:
        if set(r) - ROW_FIELDS or not ROW_FIELDS - {"first_seen", "last_seen"} <= set(r):
            raise ValueError("row contains unsupported or missing fields")
        if r["id"] in ids or not re.fullmatch(r"[a-f0-9]{24}", r["id"]):
            raise ValueError("duplicate or invalid listing identity")
        ids.add(r["id"])
        if r["league"] != league or r["status"] not in STATUSES or r["category"] not in CLASSES:
            raise ValueError("invalid league, availability or category")
        if r["region"] not in {None, "other", *(k for k, _ in reasons.REGIONS)} or r["injury_type"] not in {None, "other", *(k for k, _ in reasons.TYPES)}:
            raise ValueError("invalid normalized injury category")
        if any(not isinstance(r[k], str) or not 2 <= len(r[k]) <= 120 for k in ("team", "player")):
            raise ValueError("missing or invalid team/player")
        if r["game_date"]:
            game = date.fromisoformat(r["game_date"])
            published = instant(snapshot["report_at"] or snapshot["observed_at"]).date()
            if check_game_window and abs((game - published).days) > 14:
                raise ValueError("game is outside the report window")
        for field in ("first_seen", "last_seen"):
            if field in r:
                instant(r[field])
    for r in snapshot["not_submitted"]:
        if set(r) != {"game_date", "matchup", "team"} or not r["game_date"] or not r["team"]:
            raise ValueError("invalid unsubmitted team report")


def read_state(path, now):
    if not path.exists():
        return dict(schema_version=1, generated_at=None, sources={}, events=[])
    state = json.loads(path.read_text(encoding="utf-8"))
    validate_state(state, now)
    return state


def validate_state(state, now):
    if set(state) != {"schema_version", "generated_at", "sources", "events"} or state["schema_version"] != 1:
        raise ValueError("unsupported saved state")
    if state["generated_at"] and instant(state["generated_at"]) > now + timedelta(minutes=5):
        raise ValueError("saved state is from the future")
    for source in state["sources"].values():
        if set(source) != SOURCE_FIELDS or source["league"] not in LEAGUES:
            raise ValueError("invalid saved source")
        if source["status"] not in {"not_enabled", "paused", "ok", "stale", "error"}:
            raise ValueError("invalid source health")
        instant(source["checked_at"])
        if source["last_success_at"]:
            instant(source["last_success_at"])
        if source["snapshot"]:
            validate_snapshot(source["snapshot"], source["league"], now)
    for event in state["events"]:
        if set(event) != {"at", "source", "kind", "row"} or event["kind"] not in {"first_observed", "changed", "not_in_latest_report"}:
            raise ValueError("invalid change event")
        if set(event["row"]) != ROW_FIELDS:
            raise ValueError("event contains unsupported row fields")
        instant(event["at"])
        validate_snapshot(dict(report_at=event["at"] if event["row"]["game_date"] else None, observed_at=event["at"],
                               sha256="0" * 64, rows=[event["row"]], not_submitted=[], pages_checked=1),
                          event["row"]["league"], now, check_game_window=False)


def changed_rows(old, new, source_id, now):
    before = {r["id"]: r for r in old["rows"]} if old else {}
    events = []
    for r in new["rows"]:
        was = before.pop(r["id"], None)
        r["first_seen"] = was["first_seen"] if was else stamp(now)
        r["last_seen"] = stamp(now)
        meaningful = ROW_FIELDS - {"first_seen", "last_seen"}
        if not was or any(was[k] != r[k] for k in meaningful):
            events.append(dict(at=stamp(now), source=source_id, kind="changed" if was else "first_observed", row=copy.deepcopy(r)))
    for r in before.values():
        events.append(dict(at=stamp(now), source=source_id, kind="not_in_latest_report", row=r))
    return events


def collect(sources, previous, now, client, *, collectors=None, log=print):
    collectors = collectors or COLLECTORS
    state = copy.deepcopy(previous)
    state["generated_at"] = stamp(now)
    state["events"] = [e for e in state["events"] if instant(e["at"]) >= now - timedelta(days=90)]
    state["sources"] = {k: v for k, v in state["sources"].items() if k in {s["id"] for s in sources}}
    for spec in sources:
        old = state["sources"].get(spec["id"], {})
        source = dict(league=spec["league"], name=spec["name"], scope=spec["scope"], max_age_hours=spec["max_age_hours"],
                      checked_at=stamp(now), last_success_at=old.get("last_success_at"), snapshot=old.get("snapshot"),
                      status="not_enabled", message=spec.get("reason", ""))
        active = now.astimezone(ET).month in spec.get("active_months", range(1, 13))
        if spec["enabled"] and not active:
            source.update(status="paused", message="Collection is paused outside the configured May–October window. This is a polling schedule, not a statement about player availability.")
        elif spec["enabled"]:
            try:
                fresh = collectors[spec["kind"]](spec, client, now)
                validate_snapshot(fresh, spec["league"], now)
                was = source["snapshot"]
                if was and was["report_at"] and fresh["report_at"] and instant(fresh["report_at"]) < instant(was["report_at"]):
                    raise SourceError("source returned an older report; keeping the last validated one")
                # A mass disappearance without a new report is suspicious, not a recovery wave.
                if was and len(was["rows"]) >= 20 and len(fresh["rows"]) < len(was["rows"]) * 0.2 and spec["kind"] == "scac":
                    raise SourceError("conference listings dropped by over 80%; review the source before replacing the snapshot")
                events = changed_rows(was, fresh, spec["id"], now)
                source.update(snapshot=fresh, last_success_at=stamp(now), status="ok", message="")
                if now - instant(fresh["report_at"] or fresh["observed_at"]) > timedelta(hours=spec["max_age_hours"]):
                    source.update(status="stale", message="The source's latest report is older than the freshness limit.")
                state["events"].extend(events)
            except Exception as error:
                # Third-party PDF parsers have their own exception types. One bad
                # document must not stop other sources or leak its text into the site.
                message = str(error) if isinstance(error, (SourceError, ValueError)) else f"Parser failed ({type(error).__name__}); previous snapshot retained."
                source.update(status="error", message=message[:220])
        state["sources"][spec["id"]] = source
        log(f"{spec['id']}: {source['status']} ({len(source['snapshot']['rows']) if source['snapshot'] else 0} saved listings)", flush=True)
    validate_state(state, now)
    return state


def public_data(state):
    # The field allowlist is deliberate: raw reason strings and article text never enter state.
    return dict(schema_version=1, generated_at=state["generated_at"], leagues=LEAGUES, sources=state["sources"],
                changes=state["events"][-1000:], history_days=90,
                note="Listings are source observations, not newly diagnosed injuries. A missing listing does not establish recovery.")


def write_site_data(destination):
    """A normal site build can use local observations or keep its published snapshot."""
    state_path = LOCAL / "state.json"
    if state_path.exists():
        write_json(destination, public_data(read_state(state_path, datetime.now(timezone.utc))))
    elif not destination.exists():
        sources = {}
        for s in load_config():
            sources[s["id"]] = dict(league=s["league"], name=s["name"], scope=s["scope"], max_age_hours=s["max_age_hours"],
                                    status="not_enabled", message=s.get("reason", "No collection has been published yet."),
                                    checked_at=None, last_success_at=None, snapshot=None)
        write_json(destination, public_data(dict(generated_at=None, sources=sources, events=[])))


def archive_run(state, archive, *, now=None):
    """Add a factual observation file without replacing an earlier collection.

    Latest state is mutable and its change list is bounded. These dated files are
    permanent evidence of what was observed, including later source corrections.
    """
    validate_state(state, now or datetime.now(timezone.utc))
    if not state["generated_at"]:
        raise ValueError("cannot archive a collection that has not run")
    payload = dict(schema_version=1, generated_at=state["generated_at"], sources=state["sources"])
    body = (json.dumps(payload, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    digest = hashlib.sha256(body).hexdigest()
    when = instant(state["generated_at"]).astimezone(timezone.utc)
    path = archive / when.strftime("%Y/%m") / f"{when:%dT%H%M%SZ}-{digest[:16]}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != body:
            raise ValueError("archive collision; refusing to overwrite an observation")
    else:
        with path.open("xb") as stream:
            stream.write(body)
    return path


def seed_state(published, now):
    """Keep the reviewed baseline on the very first cloud run."""
    if not published.exists():
        return dict(schema_version=1, generated_at=None, sources={}, events=[])
    data = json.loads(published.read_text(encoding="utf-8"))
    if not data.get("generated_at"):
        return dict(schema_version=1, generated_at=None, sources={}, events=[])
    state = dict(schema_version=data["schema_version"], generated_at=data["generated_at"],
                 sources=data["sources"], events=data["changes"])
    validate_state(state, now)
    return state


def export(state_path=LOCAL / "state.json", output=LOCAL / "site", config=CONFIG, *, archive=LOCAL / "archive", now=None):
    now = now or datetime.now(timezone.utc)
    sources = load_config(config)
    previous = read_state(state_path, now) if state_path.exists() else seed_state(ROOT / "docs/data/updates.json", now)
    if previous["generated_at"]:
        archive_run(previous, archive, now=now)
    hosts = {h for s in sources if s["enabled"] for h in s["hosts"]}
    state = collect(sources, previous, now, Client(hosts, LOCAL / "raw"))
    archive_run(state, archive, now=now)
    write_json(state_path, state)
    write_json(output / "data" / "updates.json", public_data(state))
    summary = ["## Availability update", f"Checked: {stamp(now)}", ""]
    for s in state["sources"].values():
        n = len(s["snapshot"]["rows"]) if s["snapshot"] else 0
        summary.append(f"- {s['name']}: **{s['status']}**, {n} saved listings. {s['message']}")
    (output / "update-summary.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    return state


def stage_site(output, state_path=LOCAL / "state.json"):
    """Package published history plus the current snapshot, without rerunning any models."""
    now = datetime.now(timezone.utc)
    state = read_state(state_path, now)
    if not state["generated_at"]:
        raise ValueError("collect updates before staging the site")
    output = output.resolve()
    allowed = LOCAL.resolve()
    if output.parent != allowed or output.name != "site":
        raise ValueError("staged site must be in a dedicated folder under data/updates")
    shutil.copytree(ROOT / "docs", output, dirs_exist_ok=True)
    site = ROOT / "src" / "injury_risk" / "site"
    shutil.copyfile(site / "dashboard.html", output / "dashboard.html")
    for name in ("dashboard.js", "app.css", "updates.js"):
        shutil.copyfile(site / name, output / "assets" / name)
    write_json(output / "data" / "updates.json", public_data(state))
    (output / ".nojekyll").touch()
    return output
