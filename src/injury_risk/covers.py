"""Division I men's basketball injury listings from saved copies of Covers' NCAAB injury page.

Covers lists every team's players who are out or questionable: body part, status, the date of the latest
note and the note itself, with a player id that stays with him when he transfers. The page only ever shows
today's list, so the history comes from the Wayback Machine's saved copies: 191 from November to March of
2019-20 to 2025-26, kept in data/raw/wayback/covers. Copies are sparse in some seasons (2022-23: 6;
2024-25: 2 usable, 8 more saved while the page was blank), so short injuries there are mostly missing.
"""
from __future__ import annotations

import gzip
import html
import json
import re
import time
from datetime import date, timedelta

import pandas as pd

from . import net
from .paths import INTERIM, RAW

COPIES = RAW / "wayback" / "covers"
CDX = RAW / "wayback" / "cdx_covers.json"
PAGE = "https://www.covers.com/sport/basketball/ncaab/injuries"
IN_SEASON = (11, 12, 1, 2, 3)

TEAM = re.compile(r'covers-CoversMatchups-teamName">\s*<a [^>]*href="/sport/basketball/ncaab/teams/main/([^"]+)">\s*([^<]*?)\s*<br>'
                  r'\s*<span>(.*?)</span>', re.S)
ROW = re.compile(r'<a href=["\']/sport/basketball/ncaab/players/(\d+)/([^"\']+)["\'][^>]*>\s*(.*?)\s*</a>\s*</td>\s*<td>(.*?)</td>\s*'
                 r'<td><b>(.*?)</b>(?:\s*<br>\s*\(\s*(.*?)\))?\s*</td>', re.S)
NOTE = re.compile(r'covers-CoversMatchups-injuryCopy">\s*(.*?)\s*</div>', re.S)
MONTHS = {m: i for i, m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(), 1)}

NOT_INJURY = re.compile(r"undisclosed|unknown|personal|illness|flu|virus|covid|sick|eligib|suspen|redshirt|academ|"
                        r"not injury|disciplin|transfer|coach|team decision|left team|dismiss|rest|leave|heart|"
                        r"food poisoning|infection|conditioning|fatigue|migraine|stomach|lung|appendi", re.I)
KINDS = [   # injury type from the note's own words; first match wins
    ("concussion", r"concussion"),
    ("bone", r"fractur|broken|broke\b|break\b|stress reaction"),
    ("surgery", r"surgery|procedure"),
    ("ligament", r"sprain|rolled|torn|tear\b|acl|mcl|meniscus|ligament|dislocat|sublux"),
    ("muscle_tendon", r"strain|pulled|pull\b|tight|hamstring|tendin|tendon|cramp"),
    ("impact", r"contusion|bruise|bone bruise|laceration|\bcut\b|jammed"),
    ("soreness", r"sore|discomfort|pain|ailment"),
]
PART_GROUPS = [   # group, body parts as Covers writes them (the plan's groups)
    ("ankle", r"ankle"),
    ("knee", r"knee|acl|mcl|meniscus|patell"),
    ("foot", r"foot|toe|heel"),
    ("muscle", r"hamstring|calf|groin|achilles|thigh|quad"),
    ("back_hip", r"back|hip|abdom|core|rib|chest|oblique"),
    ("hand", r"hand|wrist|finger|thumb|arm|elbow"),
    ("head", r"head|face|eye|nose|jaw|neck|concussion"),
    ("shoulder", r"shoulder|collarbone|clavicle"),
]


def clean(s: str | None) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s or "")).split())


def note_date(text: str | None, captured: date) -> date | None:
    """'Sun, Feb 4' with no year: the latest such day not after the copy."""
    m = re.search(r"([A-Z][a-z]{2})\w*\.?\s+(\d{1,2})", text or "")
    if not m or m.group(1) not in MONTHS:
        return None
    try:
        d = date(captured.year, MONTHS[m.group(1)], int(m.group(2)))
    except ValueError:
        return None
    return date(captured.year - 1, d.month, d.day) if d > captured + timedelta(days=1) else d


def kind_of(note: str | None) -> str:
    for kind, pattern in KINDS:
        if re.search(pattern, note or "", re.I):
            return kind
    return "other"


def group_of(part: str | None, note: str | None) -> str | None:
    """The plan's body-part group, or None when the listing names no injury."""
    part = part or ""
    if NOT_INJURY.search(part):
        return None
    if re.search(r"\bleg\b", part, re.I):   # "Leg" is a pulled muscle only when the note says so
        return "muscle" if re.search(r"strain|pull|tight", note or "", re.I) else "other"
    for group, pattern in PART_GROUPS:
        if re.search(pattern, part, re.I):
            return group
    return "other"


def parse(page: str, captured: date) -> list[dict]:
    """One row per listed player on one saved copy."""
    teams = [(m.start(), m.group(1), clean(m.group(2))) for m in TEAM.finditer(page)]
    out = []
    for i, (pos, slug, school) in enumerate(teams):
        end = teams[i + 1][0] if i + 1 < len(teams) else len(page)
        rows = list(ROW.finditer(page, pos, end))
        for j, r in enumerate(rows):
            nxt = rows[j + 1].start() if j + 1 < len(rows) else end
            note = NOTE.search(page, r.end(), nxt)
            status = clean(r.group(5))
            text, _, part = status.rpartition(" - ") if " - " in status else (status, "", "")
            nd = note_date(clean(r.group(6)), captured)
            out.append(dict(captured=captured, team_slug=re.sub(r"/\d{4}-\d{4}$", "", slug), school=school,
                            covers_id=int(r.group(1)), player_slug=re.sub(r"/\d{4}-\d{4}$", "", r.group(2)),
                            player=clean(r.group(3)), pos=clean(r.group(4)), status=text.strip(),
                            part=part.strip() or "Unknown", note_date=nd or captured,
                            note=clean(note.group(1)) if note else ""))
    return out


def fetch(log=print) -> int:
    """Download any in-season saved copy not yet kept (one request every few seconds)."""
    COPIES.mkdir(parents=True, exist_ok=True)
    rows = json.loads(CDX.read_text()) if CDX.exists() else []
    got = 0
    for key, stamp in sorted((k, t) for k, t in rows if int(t[4:6]) in IN_SEASON):
        target = COPIES / f"{stamp}.html"
        if target.exists():
            continue
        path = key.split(")", 1)[1]
        status, body = net.get(f"https://web.archive.org/web/{stamp}id_/https://www.covers.com{path}", timeout=120)
        if body[:2] == b"\x1f\x8b":
            body = gzip.decompress(body)
        if status == 200 and body:
            target.write_bytes(body)
            got += 1
        time.sleep(2.5)
    log(f"{got} new saved copies")
    return got


def listings(force: bool = False) -> pd.DataFrame:
    """Every listing on every saved copy, with its season (2020 = 2019-20), group and injury type."""
    cache = INTERIM / "covers_listings.parquet"
    if cache.exists() and not force:
        return pd.read_parquet(cache)
    rows = []
    for f in sorted(COPIES.glob("*.html")):
        stamp = f.name[:8]
        captured = date(int(stamp[:4]), int(stamp[4:6]), int(stamp[6:8]))
        rows += parse(f.read_text(encoding="utf-8", errors="replace"), captured)
    df = pd.DataFrame(rows)
    df["captured"] = pd.to_datetime(df["captured"])
    df["note_date"] = pd.to_datetime(df["note_date"])
    df["season"] = df["captured"].dt.year + (df["captured"].dt.month >= 7).astype(int)
    df["group"] = [group_of(p, n) for p, n in zip(df["part"], df["note"])]
    df["kind"] = [kind_of(n) for n in df["note"]]
    INTERIM.mkdir(parents=True, exist_ok=True)
    df.to_parquet(cache, index=False)
    return df
