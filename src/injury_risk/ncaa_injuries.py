"""NCAA men's injury listings from SCACCHoops (one page per conference), plus how long each has been listed.

The site shows player, injury (a body part, "Undisclosed" or "Not Injury Related"), status and an often empty
details column, with no dates. A snapshot is one polite pass over the 31 conference pages. To tell a fresh
listing from one left over from last season, each entry is also looked up in the Wayback Machine's saved
copies of the same conference page: the earliest saved copy that already lists the same player and injury
is when it was first seen.
"""
from __future__ import annotations

import html
import json
import re
import time
from datetime import datetime, timezone
from urllib.parse import quote

from . import net
from .paths import OUTPUTS, RAW

BASE = "https://www.scacchoops.com/"
OUT = OUTPUTS / "ncaa_injuries"
CACHE = RAW / "scacchoops"

GROUPS = [   # (group, words in the injury text) -- the site lists body parts, not injury types
    ("Not injury related", r"not injury related|personal|suspen|academic|eligib|transfer|redshirt|coach"),
    ("Undisclosed", r"undisclosed|unknown|n/a"),
    ("Illness", r"illness|sick|flu|virus"),
    ("Head / concussion", r"concussion|head|face|facial|nose|eye|jaw"),
    ("Knee", r"knee|acl|mcl|meniscus|patella"),
    ("Ankle", r"ankle"),
    ("Foot / toe", r"foot|toe|heel|achilles|plantar"),
    ("Leg muscle", r"hamstring|calf|groin|quad|thigh|leg|shin|adductor"),
    ("Back / hip / core", r"back|hip|abdom|core|oblique|rib|pelvi"),
    ("Hand / wrist / arm", r"hand|wrist|finger|thumb|arm|elbow"),
    ("Shoulder", r"shoulder|clavicle|collarbone"),
]


def group_of(injury: str) -> str:
    for name, pattern in GROUPS:
        if re.search(pattern, injury or "", re.I):
            return name
    return "Other"


def conferences() -> list[tuple[str, str]]:
    status, body = net.get(BASE + "injuries.asp?Conference=Mid%2DAmerican", timeout=60)
    if status != 200:
        raise RuntimeError(f"conference list: HTTP {status}")
    opts = re.findall(r'<option[^>]*value="(injuries\.asp[^"]*)"[^>]*>([^<]*)</option>', body.decode("utf-8", "replace"), re.I)
    return [(html.unescape(name).strip(), path) for path, name in opts]


def parse(page: str, conference: str) -> list[dict]:
    rows = []
    for team, table in re.findall(r"<p><b>(.*?)</b></p>\s*<div[^>]*>\s*(<table.*?</table>)", page, re.S | re.I):
        for cells in re.findall(r"<tr[^>]*>\s*<td>(.*?)</td>\s*<td>(.*?)</td>\s*<td>(.*?)</td>\s*<td>(.*?)</td>\s*</tr>", table, re.S | re.I):
            player, injury, status, details = (html.unescape(re.sub(r"<[^>]+>", "", c)).strip() for c in cells)
            m = re.match(r"^(.*?)\s*\(([^)]+)\)\s*$", player)
            name, position = (m.group(1), m.group(2)) if m else (player, "")
            rows.append(dict(conference=conference, team=html.unescape(team).strip(), player=name, position=position,
                             injury=injury or "Unknown", group=group_of(injury), status=status or "Unknown", details=details))
    return rows


def snapshot(pause: float = 1.0, log=print) -> list[dict]:
    """Every conference's current listings, as of now."""
    CACHE.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rows = []
    for name, path in conferences():
        status, body = net.get(BASE + path, timeout=60)
        time.sleep(pause)
        if status != 200:
            log(f"  {name}: HTTP {status}")
            continue
        page = body.decode("utf-8", "replace")
        (CACHE / f"{stamp}_{re.sub(r'[^A-Za-z0-9]+', '_', name)}.html").write_text(page, encoding="utf-8")
        got = parse(page, name)
        for r in got:
            r["source_url"] = BASE + path
        rows += got
        log(f"  {name}: {len(got)} listings")
    return rows


ALSO_SAVED_AS = {"ACC": ["https://www.scacchoops.com/acc-mens-basketball-injury-report"]}   # older address, same table


def _get(url: str, tries: int = 4, pause: float = 1.5) -> tuple[int, bytes]:
    """GET with a pause after each call and a growing wait after a refused or dropped connection."""
    for attempt in range(tries):
        try:
            status, body = net.get(url, timeout=60)
            time.sleep(pause)
            return status, body
        except OSError:
            time.sleep(10 * (attempt + 1))
    return 0, b""


def first_seen(rows: list[dict], window_days: int = 400, sample: int = 12, log=print) -> None:
    """Add first_seen (the earliest sampled saved copy already listing the same player and injury) and
    latest_copy (the newest saved copy) from the Wayback Machine. Up to ``sample`` copies per conference page,
    spread over the last ``window_days`` days, so the date is "listed since at least", not exact."""
    pages = {}
    for r in rows:
        pages.setdefault(r["source_url"], []).append(r)
    since = (datetime.now(timezone.utc).date().toordinal() - window_days)
    for url, items in pages.items():
        conference = items[0]["conference"]
        copies = []   # (stamp, address)
        for address in [url] + ALSO_SAVED_AS.get(conference, []):
            target = address.replace("https://", "")
            status, body = _get(f"https://web.archive.org/cdx/search/cdx?url={quote(target, safe='/?=&.')}&output=json"
                                f"&fl=timestamp,statuscode&filter=statuscode:200&collapse=timestamp:8")
            stamps = [s for s, _ in json.loads(body)[1:]] if status == 200 and body.strip() else []
            copies += [(s, address) for s in stamps if datetime.strptime(s[:8], "%Y%m%d").date().toordinal() >= since]
        recent = sorted(copies)
        if len(recent) > sample:   # evenly spread, always keeping the newest
            step = (len(recent) - 1) / (sample - 1)
            recent = sorted({recent[round(i * step)] for i in range(sample)})
        seen: dict[tuple, str] = {}
        for stamp, address in recent:   # oldest first
            s, b = _get(f"https://web.archive.org/web/{stamp}id_/{address}")
            if s != 200:
                continue
            for old in parse(b.decode("utf-8", "replace"), conference):
                seen.setdefault((old["team"], old["player"], old["injury"]), f"{stamp[:4]}-{stamp[4:6]}-{stamp[6:8]}")
        recent = [s for s, _ in recent]
        latest = f"{recent[-1][:4]}-{recent[-1][4:6]}-{recent[-1][6:8]}" if recent else None
        for r in items:
            r["first_seen"] = seen.get((r["team"], r["player"], r["injury"]))
            r["latest_copy"] = latest
            r["copies_checked"] = len(recent)
        log(f"  {conference}: {len(recent)} saved copies checked (newest {latest}); "
            f"{sum(1 for r in items if r['first_seen'])} of {len(items)} listings already there")


def age(row: dict) -> tuple[str, str]:
    """(age group, plain label) for how long a listing has been up. Most saved copies are from the offseason,
    so a listing on one was already up then (left over from last season); one missing from the newest copy
    was added after it."""
    seen, latest = row.get("first_seen"), row.get("latest_copy")
    month = lambda day: datetime.strptime(day, "%Y-%m-%d").strftime("%b %Y")  # noqa: E731
    if seen:
        return "old", f"Listed by {month(seen)}"
    if latest:
        return "new", f"Added since {month(latest)}"
    return "unknown", "Can't tell"


def finish(rows: list[dict], as_of: str) -> list[dict]:
    for r in rows:
        r["as_of"] = as_of
        r["age_group"], r["listed_since"] = age(r)
    return rows


def export(log=print) -> dict:
    as_of = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rows = snapshot(log=log)
    first_seen(rows, log=log)
    finish(rows, as_of)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "listings.json").write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    log(f"{len(rows)} listings written")
    return {"listings": len(rows)}
