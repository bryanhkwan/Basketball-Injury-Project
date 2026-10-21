"""Injury news research: file reviewed findings a tier at a time, and read pages only where each site allows it.

An agent searches with the search tool it is allowed to use and records each injury's findings in
data/news/reviews/*.json. This step checks those records against their injury, the saved page text and the rules
(news.check), then files them in outputs/news/facts.jsonl, with their quotes in data/news/evidence.jsonl. A record
that fails a check is parked in data/news/blocked.jsonl, with what is wrong, and the rest are filed. It never invents
a not_found for unfinished work. ``fetch`` reads a page for the agent only when the site's robots.txt allows every
agent the request could count as, waits between requests to one site, and keeps the page's text, not its HTML.
"""
from __future__ import annotations

import hashlib
import json
import random
import re
import time
import urllib.robotparser
from collections import Counter
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

from . import net, news

LOCAL = news.DATA / "news"
CACHE_LIMIT = 500 * 1024 * 1024
# the order of the research: every NBA tier, then the college players now in the NBA (see the spec)
PLAN = [("nba", 1), ("nba", 2), ("college", 1)]
BATCH = 150   # injuries per batch: each batch is checked, and a sample of it audited
AUDIT = 15    # injuries audited per batch
USER_AGENT = "BasketballInjuryProject/1.0 (injury research; +https://github.com/bryanhkwan/Basketball-Injury-Project)"
# a page is read only if robots.txt allows all of these: this project, any agent, and the AI agents that read pages
# for a person (an agent drives these requests, so a site that turns those away is turning this one away too)
AGENTS = ("BasketballInjuryProject", "*", "Claude-User", "ChatGPT-User", "Perplexity-User")
DELAY = 2.5   # seconds between requests to one site
PAYWALL = re.compile(r"subscribe to (?:continue|read)|already a subscriber|subscribers only|sign in to (?:continue|read)", re.I)


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError as error:
            raise ValueError(f"{path.name}:{number}: invalid JSON") from error
        if not isinstance(row, dict):
            raise ValueError(f"{path.name}:{number}: expected an object")
        rows.append(row)
    return rows


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    for attempt in range(10):   # Windows won't replace a file another program holds open, often only for a moment
        try:
            temporary.replace(path)
            return
        except PermissionError:
            if attempt == 9:
                raise
            time.sleep(0.2 * (attempt + 1))


def query_for(target: dict) -> str:
    """A starting query; the agent refines it and records every query actually used."""
    return f'"{target["player"]}" {target["team"]} {target["listed_as"]} {target["first_listed"][:4]} injury'


def priority(target: dict) -> tuple:
    """Vague listings first (the news adds most there), then injuries first listed within four days of the player's
    last game (likely hurt in it, so the game and the play can be found), then the costliest."""
    last = target.get("last_game_before")
    in_game = bool(last) and news._days_apart(target["first_listed"], last) <= 4
    return (not news.vague_listing(target), not in_game, -(target.get("games_missed") or 0), target["id"])


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def parse_review(path: Path) -> dict:
    try:
        row = json.loads(path.read_text(encoding="utf-8-sig"))
    except ValueError as error:
        raise ValueError(f"{path.name}: invalid review JSON") from error
    if not isinstance(row, dict) or not isinstance(row.get("fact"), dict):
        raise ValueError(f"{path.name}: review needs a fact object")
    for key, kind in (("evidence", list), ("notes", list), ("queries", list)):
        if not isinstance(row.get(key), kind):
            raise ValueError(f"{path.name}: review needs {key}")
    if row.get("target") != row["fact"].get("target"):
        raise ValueError(f"{path.name}: review and fact targets differ")
    return row


def source_errors(fact: dict, target: dict) -> list[str]:
    errors = []
    for source in fact.get("sources", []):
        try:
            published = date.fromisoformat(source["published"]).isoformat()
        except (KeyError, ValueError, TypeError):
            errors.append("source needs a valid publication date")
            continue
        if not target["window"][0] <= published <= target["window"][1]:
            errors.append(f"source published {published} outside the injury window")
        if type(source.get("official")) is not bool:
            errors.append("source official flag must be true or false")
    return errors


def match_review(review: dict, target: dict, outlets: dict | None = None) -> list[str]:
    """What is wrong with a review of ``target``: its sources' dates, its evidence, and the rules in news.check
    (which also asks that every source name the player)."""
    fact = review["fact"]
    errors = source_errors(fact, target)
    if review.get("target") != target["id"]:
        errors.append("wrong target")
    if fact.get("status") == "not_found":
        if set(fact) != {"target", "status", "sources"} or fact.get("sources") != []:
            errors.append("not_found must contain only target, status and empty sources")
        if review["evidence"]:
            errors.append("not_found cannot carry evidence")
        if not review["queries"] or not review["notes"]:
            errors.append("not_found needs attempted queries and an explanation")
    if news._get(fact, "diagnosis.label") == "Other" and not news._get(fact, "diagnosis.detail"):
        errors.append("Other needs a diagnosis detail")
    for field in ("game.date", "surgery.date"):
        value = news._get(fact, field)
        if value is not None:
            try:
                date.fromisoformat(value)
            except (ValueError, TypeError):
                errors.append(f"{field} needs a valid date")
    for field in ("surgery.had", "expected.season_ending"):
        value = news._get(fact, field)
        if value is not None and type(value) is not bool:
            errors.append(f"{field} must be true, false or null")
    for evidence in review["evidence"]:
        if evidence.get("target") != target["id"]:
            errors.append("evidence belongs to another target")
        if evidence.get("field") not in news.FACT_FIELDS:
            errors.append("unknown evidence field")
        elif evidence.get("value") != news._get(fact, evidence["field"]):
            errors.append("evidence value differs from the fact")
        if evidence.get("url") not in {s.get("url") for s in fact.get("sources", [])}:
            errors.append("evidence source is not cited")
        try:
            date.fromisoformat(evidence["retrieved"])
        except (KeyError, ValueError, TypeError):
            errors.append("evidence needs a valid retrieval date")
    label = news._get(fact, "diagnosis.label")
    if label is not None and label not in news.DIAGNOSES:
        errors.append("unknown diagnosis label")
    else:
        errors += [message for level, _, message in news.check([fact], review["evidence"], {target["id"]: target}, outlets)
                   if level == "error"]
    return errors


def cache_documents_of(path: Path) -> list[str]:
    """The text blocks of one saved file. Some tool responses are saved as JSON text; their text blocks count too."""
    raw = path.read_text(encoding="utf-8-sig")
    try:
        parsed = json.loads(raw)
    except ValueError:
        return [raw]

    def strings(value):
        if isinstance(value, str):
            yield value
        elif isinstance(value, list):
            for item in value:
                yield from strings(item)
        elif isinstance(value, dict):
            for item in value.values():
                yield from strings(item)
    return list(strings(parsed))


def cache_documents(directory: Path) -> list[str]:
    paths = list(directory.rglob("*")) if directory.exists() else []
    files = [p for p in paths if p.is_file()]
    if sum(p.stat().st_size for p in files) >= CACHE_LIMIT:
        raise ValueError("news cache must stay below 500 MB")
    return [text for path in files if path.suffix == ".txt" for text in cache_documents_of(path)]


def cached_texts(directory: Path) -> list[str]:
    return [normalize(text) for text in cache_documents(directory)]


def cached_sources(directory: Path) -> dict[str, list[str]]:
    """The saved text that may back a fact, by page address (public form): search-tool text, and pages read with
    ``fetch`` (cache/pages/), which obeys robots.txt. A page a search tool opened by itself doesn't count, since nothing
    checked robots.txt first. Search batches are split at their source headings: a different article cannot support
    the quote."""
    sources = {}
    heading = re.compile(r"(?m)^.*? \((https://[^\s]+)\)\n(?=[^\n]*(?:cite|wordlim))")
    opened = re.compile(r"turn\d+view\d+")   # the search tool's mark on a page it opened, not a search result
    cache_documents(directory)   # the size check
    for path in sorted(p for p in directory.rglob("*.txt") if p.is_file()) if directory.exists() else []:
        fetched = path.relative_to(directory).parts[0] == "pages"
        for text in cache_documents_of(path):
            headers = [] if fetched else list(heading.finditer(text))
            if headers:
                for i, header in enumerate(headers):
                    end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
                    if not opened.search(text[header.end():header.end() + 200]):
                        sources.setdefault(news.canonical(header[1]), []).append(normalize(text[header.start():end]))
            else:
                # a page read with fetch, or search text saved by hand, starts with its address on the first line
                first, _, body = text.partition("\n")
                if re.fullmatch(r"https://\S+", first):
                    sources.setdefault(news.canonical(first), []).append(normalize(body))
    return sources


def quote_errors(evidence: list[dict], cache: dict[str, list[str]]) -> list[str]:
    return [f"{ev.get('field')}: quote not found in saved text for its source URL" for ev in evidence
            if not any(normalize(ev.get("quote", "")) in text for text in cache.get(news.canonical(ev.get("url", "")), []))]


def merge_logs(local: Path) -> None:
    """Keep each worker's original log and build the single audit trail without duplicate entries."""
    parts = sorted(local.glob("log_*.jsonl"))
    # Rebuild from originals: a worker may later add the resolved URL or outcome to an existing request.
    rows = [row for path in parts for row in read_jsonl(path)] if parts else read_jsonl(local / "log.jsonl")
    unique = {json.dumps(row, sort_keys=True): row for row in rows}
    write_jsonl(local / "log.jsonl", list(unique.values()))


def load_reviews(local: Path) -> dict[str, dict]:
    reviews = {}
    for path in sorted((local / "reviews").glob("*.json")):
        review = parse_review(path)
        if review["target"] in reviews:
            raise ValueError(f"duplicate review: {review['target']}")
        reviews[review["target"]] = review
    return reviews


def select(targets: list[dict], *, pilot: bool = False, tier: int | None = None, league: str | None = None,
           log=print) -> list[dict]:
    """The pilot as filed, or one tier of the plan (of one league, or both) in priority order."""
    if pilot:
        return [t for t in targets if t.get("pilot")]
    if tier is None:
        raise ValueError("choose --pilot or --tier")
    mine = [t for t in targets if t["tier"] == tier and (league is None or t["league"] == league)]
    outside = sum((t["league"], tier) not in PLAN for t in mine)
    if outside:
        log(f"  {outside} tier {tier} injuries are outside the plan (specs/injury-news.md) and are skipped")
    return sorted((t for t in mine if (t["league"], tier) in PLAN), key=priority)


def filed_errors(fact: dict, evidence: list[dict], target: dict, cache: dict, outlets: dict | None = None) -> list[str]:
    """What is wrong with a row already filed: the checks a review passed to be filed, run again."""
    errors = source_errors(fact, target) + quote_errors(evidence, cache)
    return errors + [message for level, _, message in news.check([fact], evidence, {target["id"]: target}, outlets)
                     if level == "error"]


def run(*, pilot: bool = False, tier: int | None = None, league: str | None = None, refile: bool = False,
        targets_path=news.TARGETS, facts_path=news.FACTS, local=LOCAL, outlets: dict | None = None, log=print) -> dict:
    """File the reviews of the pilot or of one tier. A review that fails a check is parked in data/news/blocked.jsonl,
    with what is wrong, and the run goes on; a filed row that no longer passes (a rule or its injury changed) comes
    off and its review is checked again. Only a broken file stops the run."""
    targets = read_jsonl(targets_path)
    selected = select(targets, pilot=pilot, tier=tier, league=league, log=log)
    if not selected:
        raise ValueError("no targets selected; run news-targets first")
    facts = read_jsonl(facts_path)
    evidence = read_jsonl(local / "evidence.jsonl")
    if len({f["target"] for f in facts}) != len(facts):
        raise ValueError("facts contain duplicate targets")
    reviews = load_reviews(local)
    refiled = 0
    if refile:   # file these reviews again from scratch, after the review files were corrected
        again = {t["id"] for t in selected if t["id"] in reviews}
        stale = {f["target"] for f in facts} - {t["id"] for t in targets}   # an injury whose id moved when the reports were re-read
        if stale:
            log(f"  dropping {len(stale)} rows filed under ids that are no longer targets: {', '.join(sorted(stale))}")
        refiled = sum(f["target"] in again for f in facts)
        facts = [f for f in facts if f["target"] not in again | stale]
        evidence = [e for e in evidence if e.get("target") not in again | stale]
        write_jsonl(local / "evidence.jsonl", evidence)
        write_jsonl(facts_path, facts)
    cache = cached_sources(local / "cache")
    selected_by_id = {t["id"]: t for t in selected}
    failing = {f["target"] for f in facts if f["target"] in selected_by_id
               and filed_errors(f, [e for e in evidence if e.get("target") == f["target"]], selected_by_id[f["target"]], cache, outlets)}
    if failing:
        log(f"  taking off {len(failing)} filed rows that no longer pass, to check their reviews again: {', '.join(sorted(failing))}")
        facts = [f for f in facts if f["target"] not in failing]
        evidence = [e for e in evidence if e.get("target") not in failing]
        write_jsonl(local / "evidence.jsonl", evidence)
        write_jsonl(facts_path, facts)
    done = {f["target"] for f in facts}
    added, skipped, pending, blocked = 0, 0, [], []
    for i, target in enumerate(selected, 1):
        tid = target["id"]
        if tid in done:
            skipped += 1
            log(f"  [{i}/{len(selected)}] skip {target['player']}: already filed")
            continue
        review = reviews.get(tid)
        if review is None and tid in failing:
            blocked.append(dict(target=tid, player=target["player"], errors=["filed, no longer passes, and has no review file"]))
            continue
        if review is None:
            pending.append(dict(target=tid, player=target["player"], query=query_for(target)))
            continue
        errors = match_review(review, target, outlets)
        errors += quote_errors(review["evidence"], cache)
        if errors:
            blocked.append(dict(target=tid, player=target["player"], errors=errors))
            log(f"  [{i}/{len(selected)}] {target['player']}: parked: " + "; ".join(errors))
            continue
        # Evidence goes first: interruption may leave unused evidence, never a fact without its evidence.
        mine = [e for e in evidence if e.get("target") != tid] + review["evidence"]
        write_jsonl(local / "evidence.jsonl", mine)
        write_jsonl(facts_path, facts + [review["fact"]])
        evidence, facts = mine, facts + [review["fact"]]
        done.add(tid)
        added += 1
        log(f"  [{i}/{len(selected)}] {target['player']}: {review['fact']['status']}")
    if pending:
        log(f"  {len(pending)} injuries still to research; the next batch of {min(BATCH, len(pending))} is in "
            f"data/news/pending.jsonl")
    if blocked:
        log(f"  {len(blocked)} reviews parked, with what is wrong with each, in data/news/blocked.jsonl")
    write_jsonl(local / "pending.jsonl", pending[:BATCH])
    write_jsonl(local / "blocked.jsonl", blocked)
    merge_logs(local)
    outside = {tid for level, tid, _ in news.check(facts, evidence, {t["id"]: t for t in targets}, outlets) if level == "error"}
    if outside:   # rows of another tier: that tier's run takes them off
        log(f"  {len(outside)} filed rows outside this run fail a check; news-check lists them")
    result = dict(selected=len(selected), added=added, skipped=skipped, pending=len(pending), refiled=refiled,
                  blocked=len(blocked))
    log(json.dumps(result))
    return result


def follow_moves(*, targets_path=news.TARGETS, facts_path=news.FACTS, local=LOCAL, log=print) -> dict:
    """After news-targets: research filed under an id that is no longer a target moves to the same injury's new id
    (news.moved_ids) in the facts, the evidence, the review files and the batch lists. Research whose injury is gone
    (it is sorted as an illness now, say) comes off the facts, and its review is set aside in data/news/retired/."""
    by_id = {t["id"]: t for t in read_jsonl(targets_path)}
    facts, evidence = read_jsonl(facts_path), read_jsonl(local / "evidence.jsonl")
    review_files = {path: parse_review(path) for path in sorted((local / "reviews").glob("*.json"))}
    batches = read_jsonl(local / "batches.jsonl")
    lists = {path: read_jsonl(path) for path in sorted(local.glob("*_targets.jsonl"))}
    used = ({f["target"] for f in facts} | {e.get("target") for e in evidence} | {r["target"] for r in review_files.values()}
            | {tid for b in batches for tid in b.get("targets", [])} | {row["id"] for rows in lists.values() for row in rows})
    moves = news.moved_ids(list(by_id.values()), sorted(tid for tid in used if tid and tid not in by_id))
    new_id = lambda tid: moves.get(tid, tid)   # noqa: E731  (None: the injury is gone)
    for path, rows in lists.items():   # a batch's list follows its injuries' current rows (a window can change too)
        write_jsonl(path, [dict(row, **by_id[new_id(row["id"])]) for row in rows if new_id(row["id"])])
    if not moves:
        return dict(moved=0, set_aside=0)
    for old, new in moves.items():
        log(f"  {old} -> {new or 'no longer a target: set aside'}")
    write_jsonl(local / "evidence.jsonl", [dict(e, target=new_id(e.get("target"))) for e in evidence if new_id(e.get("target"))])
    write_jsonl(facts_path, [dict(f, target=new_id(f["target"])) for f in facts if new_id(f["target"])])
    retired = local / "retired"
    for path, review in review_files.items():
        if review["target"] not in moves:
            continue
        new = moves[review["target"]]
        dest = local / "reviews" / (new.replace(":", "_") + ".json") if new else None
        if dest is None or dest.exists():   # gone, or the new id has a review of its own already
            retired.mkdir(exist_ok=True)
            path.replace(retired / path.name)
            continue
        moved = dict(review, target=new, fact=dict(review["fact"], target=new),
                     evidence=[dict(e, target=new) for e in review["evidence"]])
        dest.write_text(json.dumps(moved, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        path.unlink()
    write_jsonl(local / "batches.jsonl", [dict(b, targets=[new_id(t) for t in b["targets"] if new_id(t)]) if "targets" in b else b
                                          for b in batches])
    gone = sum(new is None for new in moves.values())
    return dict(moved=len(moves) - gone, set_aside=gone)


# --- reading a page -------------------------------------------------------------------------------------------------

class _Text(HTMLParser):
    """The readable text of a page, one block a line: its title, headings, paragraphs, list items and the text of
    its boxes (a quoted team release is often a div)."""
    # not "form" (an ASP.NET page wraps its whole body in one) or "noscript" (pages leave it open, hiding the rest)
    SKIP = {"script", "style", "svg", "nav", "footer", "header", "aside", "button", "select", "template"}
    KEEP = {"title", "h1", "h2", "h3", "h4", "p", "li", "blockquote", "figcaption", "time", "td", "div", "section", "article"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.lines, self.skipping, self.keeping, self.buffer = [], 0, 0, []

    def handle_starttag(self, tag, attrs):
        if tag == "body":
            self.skipping = 0   # nothing left open in the head may hide the page
        if tag in self.SKIP:
            self.skipping += 1
        elif tag in self.KEEP:
            self._flush()
            self.keeping += 1
        elif tag == "br":
            self.buffer.append(" ")

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self.skipping = max(0, self.skipping - 1)
        elif tag in self.KEEP:
            self._flush()
            self.keeping = max(0, self.keeping - 1)

    def handle_data(self, data):
        if self.keeping and not self.skipping:
            self.buffer.append(data)

    def _flush(self):
        text = normalize("".join(self.buffer))
        if text and (not self.lines or self.lines[-1] != text):
            self.lines.append(text)
        self.buffer = []

    def text(self) -> str:
        self._flush()
        return "\n".join(self.lines)


def page_text(html: str) -> str:
    parser = _Text()
    parser.feed(html)
    return parser.text()


def _log_request(local: Path, now=time.time, **row) -> None:
    stamp = datetime.fromtimestamp(now(), timezone.utc).isoformat(timespec="milliseconds")
    rows = read_jsonl(local / "log_fetch.jsonl")
    write_jsonl(local / "log_fetch.jsonl", rows + [dict(provider="news-fetch", timestamp=stamp, **row)])


def _wait_for(host: str, local: Path, now=time.time, sleep=time.sleep) -> None:
    """Sleep until DELAY seconds have passed since this project's last request to ``host``."""
    last = [datetime.fromisoformat(r["timestamp"]).timestamp() for r in read_jsonl(local / "log_fetch.jsonl")
            if urlparse(r.get("url", "")).netloc == host]
    if last:
        sleep(max(0.0, max(last) + DELAY - now()))


def robots_allows(url: str, get=net.get, local=LOCAL, now=time.time, sleep=time.sleep) -> tuple[bool, str]:
    """(may the page be read, why). Every agent in AGENTS must be allowed; robots.txt that can't be read means no,
    and one that doesn't exist (404) means the site sets no rules."""
    u = urlparse(url)
    robots = f"{u.scheme}://{u.netloc}/robots.txt"
    _wait_for(u.netloc, local, now, sleep)
    try:
        status, body = get(robots, headers={"User-Agent": USER_AGENT})
    except OSError as error:
        status, body = None, b""
        why = f"robots.txt unreadable ({type(error).__name__})"
    _log_request(local, now, action="robots", url=robots, status=status)
    if status in (404, 410):
        return True, "no robots.txt"
    if status != 200:
        return False, why if status is None else f"robots.txt unreadable (HTTP {status})"
    parser = urllib.robotparser.RobotFileParser()
    parser.parse(body.decode("utf-8", "replace").splitlines())
    blocked = [agent for agent in AGENTS if not parser.can_fetch(agent, url)]
    return (False, f"robots.txt disallows {', '.join(blocked)}") if blocked else (True, "allowed")


def fetch(url: str, *, local=LOCAL, get=net.get, now=time.time, sleep=time.sleep) -> tuple[Path | None, str]:
    """(the saved text's path, or None, and why): the page's text in data/news/cache/pages/, its address first."""
    url = news.canonical(url)
    allowed, why = robots_allows(url, get, local, now, sleep)
    if not allowed:
        _log_request(local, now, action="fetch", url=url, status=None, outcome=f"not read: {why}")
        return None, f"not read: {why}; use the search tool's text only"
    _wait_for(urlparse(url).netloc, local, now, sleep)
    try:
        status, body = get(url, headers={"User-Agent": USER_AGENT})
    except OSError as error:
        status, body = None, b""
        why = type(error).__name__
    if status != 200:
        _log_request(local, now, action="fetch", url=url, status=status, outcome="failed")
        return None, f"failed ({status or why})"
    text = page_text(body.decode("utf-8", "replace"))
    outcome = "read" if len(text) > 800 and not PAYWALL.search(text) else "short or behind a paywall: don't get around it"
    path = local / "cache" / "pages" / urlparse(url).netloc / f"{hashlib.sha1(url.encode()).hexdigest()[:16]}.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{url}\n{text}", encoding="utf-8")
    _log_request(local, now, action="fetch", url=url, status=status, outcome=outcome, cache=str(path.relative_to(local)))
    return path, outcome


# --- the audit --------------------------------------------------------------------------------------------------------

def audit_sheet(batch: str, *, n: int = AUDIT, targets_path=news.TARGETS, facts_path=news.FACTS, local=LOCAL) -> Path:
    """A checklist of ``n`` filed injuries of a batch, drawn at random (the same draw every time): each fact beside the
    quote behind it and the saved text around that quote, for an auditor who didn't do the research."""
    batches = {b["batch"]: b for b in read_jsonl(local / "batches.jsonl")}
    if batch not in batches:
        raise ValueError(f"no batch {batch!r} in data/news/batches.jsonl")
    targets = {t["id"]: t for t in read_jsonl(targets_path)}
    facts = {f["target"]: f for f in read_jsonl(facts_path)}
    evidence = read_jsonl(local / "evidence.jsonl")
    filed = [tid for tid in batches[batch]["targets"] if tid in facts]
    if not filed:
        raise ValueError(f"nothing of batch {batch!r} is filed yet")
    picked = random.Random(batch).sample(filed, min(n, len(filed)))
    cache = cached_sources(local / "cache")
    lines = [f"# Audit of batch {batch}", "",
             f"{len(picked)} of the batch's {len(filed)} filed injuries, drawn at random. For each fact, check that its quote, "
             "read in its saved context, says it about this player and this injury, and that the status follows the rules. "
             "Record each injury's verdict in data/news/audits.jsonl as {batch, target, ok, wrong, note}, where wrong lists "
             "the fields that are wrong.", ""]
    for tid in picked:
        t, f = targets[tid], facts[tid]
        lines += [f"## {t['player']} ({t['team']}), first listed {t['first_listed']}: {t['listed_as']}", "",
                  f"`{tid}` · window {t['window'][0]} to {t['window'][1]} · last game before: {t.get('last_game_before')} · "
                  f"status **{f['status']}**", ""]
        for e in [e for e in evidence if e.get("target") == tid]:
            quote = normalize(e["quote"])
            text = next((x for x in cache.get(news.canonical(e["url"]), []) if quote in x), "")
            i = text.find(quote)
            around = text[max(0, i - 200): i + len(quote) + 200] if i >= 0 else "(not in the saved text)"
            src = next((s for s in f.get("sources", []) if s["url"] == e["url"]), {})
            credit = f" (credited to the {e['attributed']})" if e.get("attributed") else ""
            lines += [f"- **{e['field']} = {json.dumps(e['value'])}**{credit}",
                      f"  - {src.get('outlet')}, {src.get('published')}: \"{src.get('headline')}\" <{e['url']}>",
                      f"  - quote: {e['quote']}", f"  - around it: …{around}…"]
        lines += ["", "- [ ] right player and injury  - [ ] every fact says what its quote says  - [ ] the status is right", ""]
    path = local / "audits" / f"{batch}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


# --- the report -------------------------------------------------------------------------------------------------------

def is_anchor(target: dict) -> bool:
    """One of the well-known injuries, matched within two weeks of its date (re-reading the reports can move it)."""
    return any(target["league"] == league and target["player"] == player and news._days_apart(target["first_listed"], first) <= 14
               for league, player, first in news.ANCHORS)


def group(target: dict) -> str:
    if is_anchor(target):
        return "Known injuries (anchors)"
    for label, predicate, _ in news.QUOTAS:
        if predicate(target):
            return label
    return "Other"


def vague_listing(target: dict) -> bool:
    return news.vague_listing(target)


FIELDS_SHOWN = [("diagnosis.label", "diagnosis"), ("side", "side"), ("setting", "setting"), ("game.date", "game date"),
                ("game.play", "play"), ("contact", "contact"), ("mechanism", "mechanism"), ("surgery.had", "surgery"),
                ("expected.season_ending", "season-ending"), ("expected.weeks", "return weeks"),
                ("expected.reevaluate_weeks", "re-evaluation")]


def _table(header: list[str], rows: list[list]) -> list[str]:
    return ["| " + " | ".join(header) + " |", "|" + "|".join("---" if i == 0 else "---:" for i in range(len(header))) + "|"] + [
        "| " + " | ".join(str(c) for c in row) + " |" for row in rows]


def write_report(*, targets_path=news.TARGETS, facts_path=news.FACTS, local=LOCAL, outlets: dict | None = None,
                 report_path=news.OUT / "pilot_report.md", examples=("Jamal Murray", "Jaylen Clark", "Cooper Flagg",
                                                                     "Blake Griffin")) -> None:
    """The pilot report: what was found, by group and league; the sources by kind; time; every problem; examples."""
    outlets = news.load_outlets() if outlets is None else outlets
    everything = read_jsonl(targets_path)
    targets = [t for t in everything if t.get("pilot")]
    by_id = {t["id"]: t for t in targets}
    facts = {f["target"]: f for f in read_jsonl(facts_path) if f["target"] in by_id}
    if set(facts) != set(by_id):
        raise ValueError("finish every pilot target before writing its report")
    reviews = {r["target"]: r for r in load_reviews(local).values() if r["target"] in by_id}
    evidence = [e for e in read_jsonl(local / "evidence.jsonl") if e["target"] in by_id]
    verification_path = local / "validation.json"
    if not verification_path.exists():
        raise ValueError("record news-check and test results in data/news/validation.json first")
    verification = json.loads(verification_path.read_text(encoding="utf-8"))
    if verification.get("news_check_exit") != 0 or verification.get("tests_exit") != 0:
        raise ValueError("both news-check and the tests must pass before writing the report")
    notes_path = local / "report_notes.json"   # the researcher's own words: what didn't work, and the limits
    report_notes = json.loads(notes_path.read_text(encoding="utf-8")) if notes_path.exists() else {}
    statuses = ("confirmed", "reported", "conflicting", "partial", "not_found")
    refiled = verification.get("refiled")
    lines = ["# Injury news: 50-injury pilot", "",
             f"Researched 2026-10-20; refiled {refiled} under the rules settled in the owner's review "
             "(`specs/injury-news.md`, \"Settled after the pilot\"). Stopped for the owner's check of the 11 known injuries.", "",
             "Each injury was looked up by an agent with an allowed search tool, and its findings filed only after "
             "`news-research` checked them against the injury, the saved page text and `news-check`'s rules. "
             "The quotes, page text, review notes and request logs stay in `data/news/`.", "",
             "## What the news found", ""]
    rows = []
    groups = ["Known injuries (anchors)"] + [label for label, _, _ in news.QUOTAS]
    for label in groups + ["Total"]:
        mine = [facts[t["id"]] for t in targets if label == "Total" or group(t) == label]
        counts = Counter(f["status"] for f in mine)
        new = sum(news.gained(facts[t["id"]], t) for t in targets if label == "Total" or group(t) == label)
        rows.append([label, len(mine)] + [counts[s] for s in statuses] + [new])
    lines += _table(["Group", "Injuries", "Confirmed", "Reported", "Conflicting", "Partial", "Not found", "Gained something new"], rows)
    lines += ["", "Confirmed: the team or league said it (its own page, or a quote that credits it), or two different outlets "
              "did; copies of one wire story count once. Reported: one outlet named the injury. Partial: facts but no "
              "diagnosis. *Gained something new*: a diagnosis for a listing that named only a body part, or how it "
              "happened (contact, mechanism or the play).", "", "### By league", ""]
    rows = []
    for league, name in (("nba", "NBA"), ("college", "College")):
        mine = [t for t in targets if t["league"] == league]
        vague = [t for t in mine if news.vague_listing(t)]
        named = [t for t in vague if news._get(facts[t["id"]], "diagnosis.label") not in (None, *news.GENERIC)]
        found = [t for t in mine if facts[t["id"]]["status"] != "not_found"]
        rows.append([name, len(mine), len(found), sum(facts[t["id"]]["status"] == "confirmed" for t in mine),
                     f"{len(named)} of {len(vague)}", sum(news.gained(facts[t["id"]], t) for t in mine)])
    lines += _table(["League", "Injuries", "Found", "Confirmed", "Vague listings named", "Gained something new"], rows)
    lines += ["", "How often each fact was found, among the injuries with any finding:", ""]
    rows = []
    for league, name in (("nba", "NBA"), ("college", "College")):
        found = [facts[t["id"]] for t in targets if t["league"] == league and facts[t["id"]]["status"] != "not_found"]
        rows.append([name, len(found)] + [sum(news._get(f, k) not in (None, "unknown") for f in found) for k, _ in FIELDS_SHOWN])
    lines += _table(["League", "Found"] + [label for _, label in FIELDS_SHOWN], rows)
    vague = [t for t in targets if news.vague_listing(t)]
    named = [t for t in vague if news._get(facts[t["id"]], "diagnosis.label") not in (None, *news.GENERIC)]
    def named_as(fact):
        label = news._get(fact, "diagnosis.label")
        return news._get(fact, "diagnosis.detail").rstrip(".").lower() if label == "Other" else label
    lines += ["", f"The listing named only a body part for {len(vague)} injuries; the news named the injury for {len(named)}: "
              + "; ".join(f"{t['player']} ({t['listed_as']} → {named_as(facts[t['id']])})" for t in named)
              + ". A vague listing is a college listing without a diagnosis, or an NBA reason with no injury word "
              "(tear, fracture, sprain, strain, subluxation, spasm, tendinopathy, bruise, contusion, dislocation, rupture, "
              "ACL, MCL). `Hip injury` and the like only repeat the body part and don't count.", "",
              "## Sources", ""]
    used = [(t, s) for t in targets for s in facts[t["id"]].get("sources", [])]
    kinds = Counter(outlets.get(s["outlet"], "?") for _, s in used)
    rows = [[kind, n, sum(1 for t in targets if any(outlets.get(s["outlet"]) == kind for s in facts[t["id"]].get("sources", [])))]
            for kind, n in kinds.most_common()]
    lines += _table(["Kind of outlet", "Citations", "Injuries"], rows)
    read = Counter(how for r in reviews.values() for how in (r.get("read") or {}).values())
    lines += ["", f"{len(used)} citations from {len({s['outlet'] for _, s in used})} outlets; "
              f"{sum(s['official'] for _, s in used)} are the team's, league's, school's or conference's own pages. "
              f"Read in full: {read.get('page', 0)}; from the search tool's text only: {read.get('search', 0)} "
              "(the site's robots.txt turns AI agents away or couldn't be read, or the page is behind a paywall). "
              "NBA.com turns away the agents that read pages for a person, so every nba.com page here is search text.", "",
              "Most cited outlets: " + ", ".join(f"{name} ({n})" for name, n in
                                                Counter(s["outlet"] for _, s in used).most_common(12)) + ".", ""]
    lines += ["What didn't work:", ""] + [f"- {line}" for line in report_notes.get("did_not_work", [])] + [""]
    lines += ["## Time and tokens", ""]
    batches = read_jsonl(local / "batches.jsonl")
    if batches:
        rows = [[b["batch"], len(b.get("targets", [])), b.get("minutes") or "not measured", b.get("tokens") or "not measured",
                 b.get("note", "")] for b in batches]
        lines += _table(["Batch", "Injuries", "Minutes", "Tokens", "What it was"], rows) + [""]
    lines += ["Per-injury time was not measured: the first pass researched the 50 in three parallel batches, and its "
              "per-injury seconds were equal shares of each batch. Neither agent can read its own token count. "
              "Tier batches record their own time and tokens in `data/news/batches.jsonl`.", ""]
    lines += ["## Problems and limits", ""]
    problems = news.check(list(facts.values()), evidence, by_id, outlets)
    errors = [p for p in problems if p[0] == "error"]
    lines += [f"- `news-check`: {len(errors)} errors, {len(problems) - len(errors)} warnings."]
    lines += [f"  - {by_id[tid]['player']}: {message}" for level, tid, message in problems if level == "warning"]
    lines += [f"- {line}" for line in report_notes.get("limits", [])] + [""]
    for t in targets:
        notes = reviews.get(t["id"], {}).get("notes", [])
        if notes:
            lines.append(f"- **{t['player']} ({t['first_listed']})**: " + " ".join(notes))
    lines += ["", "## Validation", "",
              f"- `python -m injury_risk news-check`: exit {verification['news_check_exit']}.",
              f"- `python -m unittest discover -s tests`: exit {verification['tests_exit']} "
              f"({verification.get('tests_count', 'see local test log')} tests).",
              "- Only the 50 pilot injuries were researched. Nothing was committed or pushed.",
              "- Refile with `PYTHONPATH=src python -m injury_risk news-research --pilot --refile`; a tier with "
              "`--tier 1`, which files the reviews present and lists the next batch in `data/news/pending.jsonl`.",
              "", "## Five example rows", ""]
    chosen = [next(facts[t["id"]] for t in targets if t["player"] == name) for name in examples]
    chosen += [next((f for f in facts.values() if f["status"] == "not_found"), list(facts.values())[-1])]
    for fact in chosen:
        lines += [f"### {by_id[fact['target']]['player']}", "", "```json", json.dumps(fact, indent=2, ensure_ascii=False), "```", ""]
    report_path.write_text("\n".join(lines), encoding="utf-8")
