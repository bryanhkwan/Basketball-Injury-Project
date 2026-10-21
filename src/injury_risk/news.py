"""The injury news layer (specs/injury-news.md): which injuries to look up, and the checks on what comes back.

The profiles know when each injury began, how long it lasted and what the injury report or Covers called it. News
reports often say more: the exact injury, how it happened, surgery and the expected return. This module

- lists the injuries worth looking up, in tiers, with a 50-injury pilot (``python -m injury_risk news-targets`` ->
  outputs/news/targets.jsonl);
- checks the research against fixed rules before the site uses any of it (``python -m injury_risk news-check``):
  every fact needs a source, and a quote kept locally that supports it; a "confirmed" diagnosis needs the team's or
  league's own word, or two different outlets; nothing may copy an article's wording; every source names the player;
  and the facts must fit the injury they are filed under.

The research itself (searching, reading and extracting) is done outside this module; see the spec.
"""
from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from datetime import date, timedelta
from urllib.parse import urlparse, urlunparse

import numpy as np
import pandas as pd

from .paths import DATA, OUTPUTS, PROCESSED

OUT = OUTPUTS / "news"
TARGETS = OUT / "targets.jsonl"
FACTS = OUT / "facts.jsonl"           # what the site may publish: facts and citations
EVIDENCE = DATA / "news" / "evidence.jsonl"   # the quotes behind them: kept on this machine, never committed
OUTLETS = OUT / "outlets.json"        # every outlet the facts cite, with its kind (kept with the facts)
PILOT = OUT / "pilot.json"            # the pilot as first drawn, so a rebuilt target list keeps the same injuries
PROFILES = OUTPUTS / "profiles"

BEFORE, AFTER = 14, 60               # days around the first listing in which to look for reports
MAJOR = {"acl", "achilles", "meniscus", "mcl", "foot_fracture", "hand_fracture"}
OUT_LONG = {"Out for the season", "Out indefinitely"}
# well-known injuries the pilot always includes, so its results can be checked by eye
ANCHORS = [("nba", "Kyrie Irving", "2025-03-05"), ("nba", "Tyrese Haliburton", "2025-10-23"), ("nba", "Kawhi Leonard", "2021-06-16"),
           ("nba", "Klay Thompson", "2019-10-24"), ("nba", "Klay Thompson", "2020-12-25"), ("nba", "Zion Williamson", "2021-10-20"),
           ("nba", "Jamal Murray", "2021-04-14"), ("nba", "Damian Lillard", "2025-04-29"),
           ("college", "Jaylen Clark", "2023-03-08"), ("college", "Cooper Flagg", "2025-03-12"), ("college", "Herbert Jones", "2020-02-02")]

# --- what a fact may say -------------------------------------------------------------------------------------------
DIAGNOSES = {   # label -> the body regions (profiles.REGION_NAMES keys) it can be filed under
    "Torn ACL": {"knee"}, "ACL sprain": {"knee"}, "Torn MCL": {"knee"}, "MCL sprain": {"knee"}, "PCL sprain": {"knee"},
    "Knee sprain": {"knee"}, "Torn meniscus": {"knee"}, "Torn patellar tendon": {"knee"}, "Torn quadriceps tendon": {"knee", "thigh"},
    "Patellar tendinopathy": {"knee"}, "Knee bone bruise": {"knee"}, "Knee hyperextension": {"knee"},
    # a break at the knee (the femoral condyles, the tibial plateau, the kneecap, the head of the fibula) sits where the
    # profiles' knee meets the lower leg they file under the calf, so reports and listings can name either
    "Knee fracture": {"knee", "calf", "leg"},
    "Achilles tear": {"achilles", "calf", "ankle", "leg"}, "Achilles tendinopathy": {"achilles", "calf", "ankle", "leg"},
    "Ankle sprain": {"ankle", "foot", "leg"}, "High ankle sprain": {"ankle", "foot", "leg"}, "Ankle fracture": {"ankle", "foot", "leg"},
    "Midfoot sprain": {"foot", "ankle"}, "Toe sprain": {"foot"},
    "Hamstring strain": {"hamstring", "thigh", "leg"}, "Calf strain": {"calf", "leg"}, "Groin strain": {"groin", "hip", "thigh"},
    "Quad strain": {"thigh", "leg"}, "Torn quadriceps": {"thigh", "leg"}, "Hip flexor strain": {"hip", "groin", "thigh"},
    "Hip injury": {"hip"},
    "Abdominal or oblique strain": {"trunk", "back", "groin", "hip"}, "Back strain or spasms": {"back", "trunk"},
    "Herniated disc": {"back", "head_neck"}, "Plantar fasciitis": {"foot", "ankle"}, "Torn plantar fascia": {"foot", "ankle"},
    # the profiles file the shin, tibia and fibula under "calf" (reasons.REGIONS), so lower-leg bone injuries fit it
    "Foot fracture": {"foot", "ankle"}, "Leg fracture": {"calf", "leg", "ankle", "knee"},
    "Stress fracture": {"foot", "ankle", "calf", "leg", "thigh", "hip", "back", "knee"},
    "Stress reaction": {"foot", "ankle", "calf", "leg", "thigh", "hip", "back", "knee"},
    "Hand or finger fracture": {"hand", "arm"}, "Wrist fracture": {"hand", "arm"}, "Wrist sprain": {"hand", "arm"},
    "Finger sprain": {"hand"}, "Finger dislocation": {"hand"}, "Torn thumb ligament": {"hand"},
    "Shoulder dislocation": {"shoulder"}, "Shoulder subluxation": {"shoulder"}, "AC joint sprain": {"shoulder"},
    "Rotator cuff injury": {"shoulder"}, "Torn labrum": {"shoulder", "hip"},
    "Elbow injury": {"elbow", "arm"}, "Concussion": {"concussion", "head_neck"}, "Facial fracture": {"head_neck", "concussion"},
    "Rib injury": {"trunk", "back"}, "Blood clot": {"calf", "leg", "trunk", "shoulder", "arm"},
    "Bone bruise": set(), "Contusion": set(), "Other": set(),   # a bruise can be anywhere (a hip pointer is a contusion)
}
GENERIC = {"Hip injury", "Elbow injury", "Rib injury"}   # labels that only repeat a body region
ANY_REGION = {"other", "any", None}   # injuries filed under no particular region accept any diagnosis
MECHANISMS = {"landing", "stepped_on_foot", "cutting_or_planting", "collision", "struck", "fall", "overextension", "overuse", "unknown"}
PLAYS = {"drive", "drew_foul", "rebound", "steal", "defending_the_rim", "jump_shot", "transition", "screen", "loose_ball", "other",
         "unknown"}
CONTACT = {"contact", "non_contact", "unknown"}
SETTINGS = {"game", "practice", "workout", "offseason", "unknown"}
STATUSES = {"confirmed", "reported", "conflicting", "partial", "not_found"}
FACT_FIELDS = ["diagnosis.label", "side", "grade", "setting", "game.date", "game.play", "contact", "mechanism", "surgery.had",
               "surgery.date", "expected.season_ending", "expected.weeks", "expected.reevaluate_weeks"]
QUOTE_MAX, DETAIL_MAX, HEADLINE_MAX = 300, 80, 200
LISTING_SLACK = 3   # days a game may fall after the first listing; past that it is another injury

# --- what a source may be -------------------------------------------------------------------------------------------
# An outlet's kind says whether its own pages are official: a team's, the league's, a school's or a conference's are;
# a wire story or the league's own newsroom (NBA.com staff) is not, even on nba.com.
OUTLET_KINDS = {"team", "league", "school", "conference", "league_media", "wire", "national", "local", "student", "blog",
                "aggregator"}
OFFICIAL_KINDS = {"team", "league", "school", "conference"}
# a quote credits someone with words like these, or with the signature of an embedded post ("— Atlanta Hawks (@ATLHawks)")
ATTRIBUTION = re.compile(r"\b(?:announc\w*|said|says?|statement|confirm\w*|according to|updated?|release[sd]?|told|tweet\w*|"
                         r"posted|disclosed|reported|revealed|shared|called|described|informed|per the|by the (?:team|club|school)|"
                         r"team (?:doctors|physicians)|PR)\b|\(@\w+\)", re.I)
# a quote that is only an entry in an injury list ("Otto Porter Jr. (left foot pain)", "OUT - Udoka Azubuike (right ankle
# sprain)"), as previews, recaps and team notes print them, is the listing again; so is one that cites the listing
STATUS_WORD = r"(?:out|questionable|doubtful|probable|available)"
LIST_ENTRY = re.compile(r"^\W*(?:" + STATUS_WORD + r"\W+)?(?:[\w.'’-]+\W+){0,5}?\([^()]{2,80}\)\W*(?:" + STATUS_WORD + r"\W*)?$", re.I)
CITES_LISTING = re.compile(r"injury report|\blisted (?:as|with)\b|\b(?:is|was) listed\b", re.I)
RUMOUR = re.compile(r"\b(?:reportedly|feared|fears|believed to|expected to (?:have|be diagnosed)|sources? (?:said|say|told)|"
                    r"per sources|according to (?:a )?sources?)\b", re.I)
TRACKING = re.compile(r"(?:^|&)(?:utm_\w+|lctg|lid|fbclid|gclid|cmpid|ocid|_gl|smid|cid|ref)=", re.I)
DEV_HOST = re.compile(r"(?:^|[.-])(?:dev|uat|qa|stage|staging|test|preview)(?:[.-]|$)|^api-hub", re.I)
FEEDS = re.compile(r"foxsports\.com/[^?#]*-player(?:[?#]|$)|rotowire\.com/[^?#]*/player", re.I)   # pages that keep changing
LISTINGS = re.compile(r"cms\.nba\.com/referee/injury/", re.I)   # the official injury report: where the listings come from
AMP = re.compile(r"/amp/|\.amp(?:\.html)?$|[?&]amp(?:=|&|$)", re.I)


def _day(t) -> str | None:
    return None if t is None or pd.isna(t) else pd.Timestamp(t).strftime("%Y-%m-%d")


def _shift(iso: str, days: int) -> str:
    return (date.fromisoformat(iso) + timedelta(days=days)).isoformat()


def _ascii(text: str | None) -> str:
    return unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode().lower()


def surname(player: str) -> str:
    """The part of a name every report uses: the last word, without Jr. or III ("jackson-davis", "valanciunas")."""
    words = [w for w in re.split(r"[\s,]+", _ascii(player)) if w and w.strip(".") not in {"jr", "sr", "ii", "iii", "iv"}]
    return words[-1] if words else ""


def canonical(url: str) -> str:
    """A page's public address: no tracking parameters or fragment, the NBA's development hosts as www.nba.com, and an
    AMP copy's leading /amp/ dropped."""
    u = urlparse(url)
    host = "www.nba.com" if u.netloc.endswith("nba.com") and DEV_HOST.search(u.netloc) else u.netloc
    query = "&".join(p for p in u.query.split("&") if p and not TRACKING.match(p))
    path = re.sub(r"^/amp/", "/", re.sub(r"(\.php)/$", r"\1", u.path))
    return urlunparse((u.scheme, host, path, "", query, ""))


def url_problems(url: str) -> list[tuple[str, str]]:
    """(error or warning, why) for an address the site would publish."""
    u = urlparse(url)
    out = []
    if u.scheme != "https" or not u.netloc:
        out.append(("error", "every source needs an https url"))
    if DEV_HOST.search(u.netloc):
        out.append(("error", f"{u.netloc} is a development server: cite the public address"))
    if TRACKING.search(u.query):
        out.append(("error", "drop the tracking parameters from the url"))
    if FEEDS.search(url):
        out.append(("error", "a rolling player feed keeps changing: cite a dated article"))
    if LISTINGS.search(url):
        out.append(("error", "the official injury report is where the listings come from, so it adds nothing: cite the news "
                             "or the team's own statement"))
    if AMP.search(url):
        out.append(("warning", "an AMP copy: cite the article's own address"))
    return out


def load_outlets(path=OUTLETS) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


NAMED = re.compile(r"tear|torn|fractur|broken|sprain|strain|subluxation|spasm|tendin|tendonitis|tendonosis|bruise|contusion|"
                   r"dislocat|rupture|stress reaction|impingement|bursitis|fasciitis|neuritis|osteitis|sesamoiditis|"
                   r"hyperextension|laceration|herniat|hernia|avulsion|menisc|labr|\b(?:ACL|MCL|PCL|LCL|UCL)\b", re.I)


def vague_listing(t: dict) -> bool:
    """The listing names only a body part: a college listing without a diagnosis, or an NBA reason with no injury in it."""
    if t["league"] == "college":
        return not t.get("diagnosis_listed")
    return t["kind"].startswith("region:") and not NAMED.search(t.get("listed_as") or "")


def gained(f: dict, t: dict) -> bool:
    """The news added what the listing lacked: the injury behind a vague listing, or how it happened."""
    label = _get(f, "diagnosis.label")
    return bool((vague_listing(t) and label and label not in GENERIC)
                or any(_get(f, k) not in (None, "unknown") for k in ("contact", "mechanism", "game.play")))


# --- targets -------------------------------------------------------------------------------------------------------

def nba_context() -> dict:
    """player id -> (sorted dates they played, the team each game) from the processed box scores, when present."""
    path = PROCESSED / "player_games.parquet"
    if not path.exists():
        return {}
    pg = pd.read_parquet(path, columns=["player_id", "game_date", "team", "absence"]).sort_values("game_date")
    return {pid: (g["game_date"].to_numpy(), g["team"].to_numpy(), (g["absence"] == "played").to_numpy())
            for pid, g in pg.groupby("player_id")}


def college_context() -> dict:
    """(Covers id, season) -> the sorted dates that player played that season, from the college box scores. The NCAA
    id is the one their injury listings name most often, as the profiles match it."""
    from . import college, profiles, sources
    path = profiles.COLLEGE / "listings_matched.parquet"
    if not path.exists():
        return {}
    m = pd.read_parquet(path, columns=["covers_id", "captured", "note_date", "group", "player_id"])
    m = m[m["group"].notna()].dropna(subset=["player_id"])
    start = m[["note_date", "captured"]].min(axis=1)
    m = m.assign(season=np.where(start.dt.month >= 7, start.dt.year + 1, start.dt.year))
    ids = m.groupby(["covers_id", "season"])["player_id"].agg(lambda s: int(s.mode().iloc[0]))
    dates = {}
    for season in sources.COLLEGE_SEASONS:
        try:
            box = college.box(season)
        except OSError:
            continue
        dates.update({(season, int(pid)): np.sort(g["game_date"].to_numpy()) for pid, g in box.groupby("player_id")})
    return {(int(cid), int(s)): dates[(int(s), int(pid))] for (cid, s), pid in ids.items() if (int(s), int(pid)) in dates}


def targets() -> list[dict]:
    """The injuries worth looking up, most valuable first, each with an id "league:player:first listed:body region".
    tier 1: NBA injuries that cost 10 or more games or are a named major injury; college injuries of players now in the NBA.
    tier 2: NBA concussions; college injuries out for the season or with a named injury.
    tier 3: the other college injuries that were out indefinitely or cost 5 or more games."""
    nba = json.loads((PROFILES / "nba.json").read_text(encoding="utf-8"))
    col = json.loads((PROFILES / "college.json").read_text(encoding="utf-8"))
    ctx = nba_context()
    out = []
    for p in nba["players"]:
        dates, teams, played = ctx.get(p["id"], (np.array([], dtype="datetime64[ns]"), np.array([]), np.array([], dtype=bool)))
        for e in p["inj"]:
            first, kind, games = e[0], e[2], e[4]
            tier = 1 if games >= 10 or (kind in MAJOR and games >= 3) else 2 if kind == "concussion" else None
            if tier is None:
                continue
            before = dates[played & (dates < np.datetime64(first))]
            last = _day(before[-1]) if len(before) else None
            here = teams[dates <= np.datetime64(first)]
            # from two weeks before the first listing, or the day before their last game if that is earlier (an
            # injury in the season's last game, first listed months later; or one they played through)
            start = min(_shift(first, -BEFORE), _shift(last, -1)) if last else _shift(first, -BEFORE)
            # to two months after it, or to their return when the absence ran longer, up to a year: what was reported
            # while they were out is about it (Cancar's broken foot, out from March 11, 2020, listed in the bubble)
            end = max(_shift(first, AFTER), min(e[5] or _shift(first, 366), _shift(first, 365)))
            out.append(dict(id=f"nba:{p['id']}:{first}:{e[3]}", league="nba", tier=tier, player=p["n"], player_id=p["id"],
                            team=str(here[-1]) if len(here) else p["tm"][-1][1], first_listed=first, last_game_before=last,
                            back=e[5], games_missed=games, listed_as=e[1], first_listed_as=e[8], region=e[3], kind=kind,
                            window=[start, end], college_profile=p["col"][4] if p.get("col") else None))
    played_in = college_context()
    for p in col["people"]:
        school = dict((s, t) for s, t in p["sch"])
        for e in p["inj"]:
            first, last_listed, season, status, missed, dx, kind = e[0], e[1], e[2], e[6], e[7], e[10], e[13]
            tier = 1 if "nba" in p else 2 if status == "Out for the season" or dx else 3 if status in OUT_LONG or (missed or 0) >= 5 else None
            if tier is None:
                continue
            region = kind.split(":", 1)[1] if kind.startswith("region:") else {"acl": "knee", "mcl": "knee", "meniscus": "knee",
                     "achilles": "achilles", "concussion": "concussion", "ankle_sprain": "ankle", "foot_fracture": "foot",
                     "hand_fracture": "hand"}.get(kind)
            # Covers was saved every few days to weeks, so an injury can be first listed long after the game it
            # happened in: the window opens at their last game before the listing, this season or the one before
            played = [d for s in (season - 1, season) for d in played_in.get((p["id"], s), [])]
            before = [d for d in played if d < np.datetime64(first)]
            last = _day(max(before)) if before else None
            start = min(_shift(first, -BEFORE), _shift(last, -1)) if last else _shift(first, -BEFORE)
            out.append(dict(id=f"college:{p['id']}:{first}:{e[4]}", league="college", tier=tier, player=p["n"], covers_id=p["id"],
                            team=school.get(season), season=season, first_listed=first, last_listed=last_listed,
                            last_game_before=last, status=status, games_missed=missed, listed_as=e[3], diagnosis_listed=dx,
                            region=region, kind=kind, window=[start, _shift(last_listed, AFTER)], nba_profile=p.get("nba")))
    out.sort(key=lambda t: (t["tier"], t["league"] != "nba", -(t["games_missed"] or 0), t["id"]))
    return out


# the pilot beyond the anchors: what each group can teach, and how many of it (39, with the 11 anchors 50)
QUOTAS = [
    ("NBA, a vague listing that cost 10+ games", lambda t: t["league"] == "nba" and t["kind"].startswith("region:") and t["games_missed"] >= 10, 12),
    ("NBA, a named major injury", lambda t: t["league"] == "nba" and t["kind"] in MAJOR, 6),
    ("NBA, a sprain or strain", lambda t: t["league"] == "nba" and t["kind"] in {"ankle_sprain", "hamstring", "calf", "groin"}, 4),
    ("NBA, a concussion", lambda t: t["league"] == "nba" and t["kind"] == "concussion", 2),
    ("College, a player now in the NBA", lambda t: t["league"] == "college" and t["tier"] == 1, 7),
    ("College, out for the season or a named injury", lambda t: t["league"] == "college" and t["tier"] == 2, 5),
    ("College, out indefinitely or 5+ games", lambda t: t["league"] == "college" and t["tier"] == 3, 3),
]


def pilot(rows: list[dict], seed: int = 0) -> list[str]:
    """The anchors, then each group's quota drawn at random, half from before July 2022 and half after where it can be."""
    by_key = {(t["league"], t["player"], t["first_listed"]): t["id"] for t in rows}
    chosen = [by_key[a] for a in ANCHORS if a in by_key]
    rng = np.random.default_rng(seed)
    for _, test, n in QUOTAS:
        pool = [t for t in rows if test(t) and t["id"] not in chosen]
        halves = [[t["id"] for t in pool if t["first_listed"] < "2022-07-01"], [t["id"] for t in pool if t["first_listed"] >= "2022-07-01"]]
        picked = []
        for i in range(n):
            half = halves[i % 2] or halves[(i + 1) % 2]
            if not half:
                break
            picked.append(half.pop(int(rng.integers(len(half)))))
        chosen += picked
    return chosen


def _days_apart(a: str, b: str) -> int:
    return abs((date.fromisoformat(a) - date.fromisoformat(b)).days)


def moved_ids(rows: list[dict], ids) -> dict[str, str | None]:
    """Each researched id -> the same injury in ``rows`` (or None): the same league and player, first listed within
    two weeks of the old date, under the same body part, else the one injury listed then. Re-reading the reports
    can move an injury's date, and re-sorting its reason can move its body part; two injuries near the date, or two
    old ids wanting one injury, are too close to call."""
    by_player: dict[tuple, list[dict]] = {}
    for t in rows:
        league, who, _, _ = t["id"].split(":")
        by_player.setdefault((league, who), []).append(t)
    out = {}
    for old in ids:
        league, who, first, part = old.split(":")
        near = [t for t in by_player.get((league, who), []) if _days_apart(t["first_listed"], first) <= 14]
        same = [t for t in near if t["id"].split(":")[3] == part] or (near if len(near) == 1 else [])
        out[old] = min(same, key=lambda t: _days_apart(t["first_listed"], first))["id"] if same else None
    wanted = Counter(new for new in out.values() if new)
    return {old: new if new and (wanted[new] == 1 or old == new) else None for old, new in out.items()}


def export_targets(log=print) -> dict:
    rows = targets()
    if PILOT.exists():   # keep the pilot already researched, wherever its injuries moved
        matched = moved_ids(rows, json.loads(PILOT.read_text(encoding="utf-8"))["ids"])
        lost = sorted(old for old, new in matched.items() if new is None)
        if lost:
            log(f"  {len(lost)} pilot injuries are no longer targets: {', '.join(lost)}")
        chosen = {new for new in matched.values() if new}
    else:
        chosen = set(pilot(rows))
        OUT.mkdir(parents=True, exist_ok=True)
        PILOT.write_text(json.dumps(dict(drawn=date.today().isoformat(), ids=sorted(chosen)), indent=1) + "\n", encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    with TARGETS.open("w", encoding="utf-8") as f:
        for t in rows:
            f.write(json.dumps({**t, "pilot": t["id"] in chosen}, ensure_ascii=False) + "\n")
    counts = pd.DataFrame(rows).groupby(["tier", "league"]).size()
    log(f"  {len(rows)} injuries to look up, {len(chosen)} in the pilot: " + ", ".join(f"tier {t} {lg} {n}" for (t, lg), n in counts.items()))
    return dict(targets=len(rows), pilot=len(chosen))


# --- checks --------------------------------------------------------------------------------------------------------

def _read_jsonl(path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _get(d: dict, field: str):
    for part in field.split("."):
        d = d.get(part) if isinstance(d, dict) else None
    return d


def _weeks_ok(weeks) -> bool:
    """[fewest, most] whole weeks; most is None for "at least N weeks"."""
    return (isinstance(weeks, list) and len(weeks) == 2 and type(weeks[0]) is int and weeks[0] >= 0
            and (weeks[1] is None or (type(weeks[1]) is int and weeks[1] >= weeks[0])))


def check(facts: list[dict], evidence: list[dict], targets_by_id: dict, outlets: dict | None = None) -> list[tuple[str, str, str]]:
    """Problems with the research as (error or warning, target id, what is wrong). Errors keep a row off the site."""
    outlets = load_outlets() if outlets is None else outlets
    problems = []
    seen = set()
    quotes = {}
    for ev in evidence:
        quotes.setdefault(ev.get("target"), []).append(ev)
        if not ev.get("quote") or len(ev["quote"]) > QUOTE_MAX:
            problems.append(("error", ev.get("target", "?"), f"evidence for {ev.get('field')} needs a quote of 1 to {QUOTE_MAX} characters"))
        if ev.get("attributed") not in (None, "team", "league"):
            problems.append(("error", ev.get("target", "?"), "evidence is attributed to the team, the league or nobody"))
    for name, kind in outlets.items():
        if kind not in OUTLET_KINDS:
            problems.append(("error", "outlets.json", f"{name}: kind {kind!r} is not one of {sorted(OUTLET_KINDS)}"))
    for f in facts:
        tid = f.get("target")
        bad = lambda msg, kind="error": problems.append((kind, tid, msg))  # noqa: E731
        t = targets_by_id.get(tid)
        if t is None:
            bad("not in outputs/news/targets.jsonl")
            continue
        if tid in seen:
            bad("filed twice")
        seen.add(tid)
        status = f.get("status")
        if status not in STATUSES:
            bad(f"status must be one of {sorted(STATUSES)}")
            continue
        sources = f.get("sources") or []
        if status == "not_found":
            if any(_get(f, k) is not None for k in FACT_FIELDS) or sources:
                bad("not_found rows carry no facts and no sources")
            continue
        if not sources:
            bad("needs at least one source")
        mine = quotes.get(tid, [])
        for ev in mine:
            if LIST_ENTRY.match(str(ev.get("quote", ""))):
                bad(f"the quote for {ev.get('field')} is an entry in an injury list, the listing again: quote the "
                    "sentence around it if a report says more, else a report that says it, or leave the fact out")
            elif CITES_LISTING.search(str(ev.get("quote", ""))):
                bad(f"the quote for {ev.get('field')} cites the listing, which confirms nothing: check that it says more",
                    "warning")
        who = surname(t["player"])
        urls = set()
        for s in sources:
            url = str(s.get("url", ""))
            for kind, why in url_problems(url):
                bad(why, kind)
            if not s.get("outlet") or not s.get("published"):
                bad("every source needs its outlet and publication date")
            elif s["published"] < t["window"][0]:
                bad(f"source published {s['published']}, before the injury window opens on {t['window'][0]}")
            if not s.get("headline"):
                bad("every source needs its headline as published")
            elif len(s["headline"]) > HEADLINE_MAX:
                bad("headline too long")
            for key in ("outlet", "via"):
                if s.get(key) and s[key] not in outlets:
                    bad(f"{key} {s[key]!r} is not in outputs/news/outlets.json: add it with its kind")
            kind = outlets.get(s.get("outlet"))
            if kind and s.get("official") is not (kind in OFFICIAL_KINDS):
                bad(f"official must be {str(kind in OFFICIAL_KINDS).lower()} for {s['outlet']} ({kind})")
            said = [ev for ev in mine if ev.get("url") == url]
            if not said:
                bad(f"{url} backs no fact: cite only the reports the facts come from")
            elif who and not any(who in _ascii(text) for text in [s.get("headline")] + [ev.get("quote") for ev in said]):
                bad(f"neither the headline nor the quotes of {url} name {t['player']}: is it about them?")
            urls.add(url)
        # enumerations
        label = _get(f, "diagnosis.label")
        for field, allowed in (("diagnosis.label", set(DIAGNOSES)), ("contact", CONTACT), ("mechanism", MECHANISMS), ("setting", SETTINGS),
                               ("game.play", PLAYS), ("side", {"left", "right"}), ("grade", {1, 2, 3})):
            v = _get(f, field)
            if v is not None and v not in allowed:
                bad(f"{field} {v!r} is not one of the allowed values")
        for field in ("expected.weeks", "expected.reevaluate_weeks"):
            if _get(f, field) is not None and not _weeks_ok(_get(f, field)):
                bad(f"{field} must be [fewest, most] whole weeks, with most null for 'at least'")
        detail = _get(f, "diagnosis.detail")
        if detail is not None and len(detail) > DETAIL_MAX:
            bad(f"diagnosis.detail must be at most {DETAIL_MAX} characters, in your own words")
        # what each status means
        if status in ("confirmed", "reported") and not label:
            bad(f"{status} needs a diagnosis; facts without one are partial")
        if status == "partial":
            if label:
                bad("partial rows have no diagnosis; with one the row is reported or confirmed")
            if all(_get(f, k) is None for k in FACT_FIELDS):
                bad("partial needs at least one fact; with none the row is not_found")
        if status == "conflicting" and not detail:
            bad("conflicting needs diagnosis.detail to say what disagrees")
        # every fact has a quote from one of its sources behind it
        for field in FACT_FIELDS:
            v = _get(f, field)
            if v is None:
                continue
            if not any(ev.get("field") == field and ev.get("value") == v and ev.get("url") in urls for ev in mine):
                bad(f"{field} = {v!r} has no supporting quote from its sources in {EVIDENCE.name}")
        if detail and len(detail) >= 30 and any(detail.lower() in str(ev.get("quote", "")).lower() for ev in mine):
            bad("diagnosis.detail copies an article's wording")
        # confirmed: the team's or league's word (its own page, or a quote that credits it) or two different outlets;
        # two copies of one story are one outlet, and a rumour counts for nothing
        if status == "confirmed" and label:
            by_url = {s.get("url"): s for s in sources}
            support = [ev for ev in mine if ev.get("field") == "diagnosis.label" and ev.get("value") == label
                       and ev.get("url") in by_url and not RUMOUR.search(str(ev.get("quote")))]
            official = any(by_url[ev["url"]].get("official") for ev in support)
            credited = [ev for ev in support if ev.get("attributed") in ("team", "league")]
            origins = {by_url[ev["url"]].get("via") or by_url[ev["url"]].get("outlet") for ev in support}
            if not (official or credited or len(origins) >= 2):
                bad("confirmed needs the diagnosis from the team or league (its own page, or a quote crediting it) "
                    "or from two different outlets; copies of one story count once and rumours not at all")
            elif not (official or len(origins) >= 2 or any(ATTRIBUTION.search(ev["quote"]) for ev in credited)):
                # the agent says the quote credits the team; no wording here shows who said it, so the audit looks
                bad("the quote credited to the team or league doesn't say who said it (said, announced, per...): check "
                    "the credit", "warning")
        # the facts must fit the injury they are filed under, unless the row says the news and the listing disagree
        if (label in DIAGNOSES and t.get("region") not in ANY_REGION and DIAGNOSES[label] and t["region"] not in DIAGNOSES[label]
                and status != "conflicting"):
            bad(f"{label} does not fit an injury listed under the {t['region']}: the wrong injury, or mark it conflicting")
        listed_side = re.search(r"\b(left|right)\b", f"{t.get('listed_as') or ''} {t.get('first_listed_as') or ''}", re.I)
        if f.get("side") and listed_side and listed_side.group(1).lower() != f["side"] and status != "conflicting":
            bad(f"side {f['side']} but the listing says {listed_side.group(1).lower()}: the wrong injury, or mark it conflicting")
        game_day = _get(f, "game.date")
        latest = min(t["window"][1], _shift(t["first_listed"], LISTING_SLACK))
        if game_day and not (t["window"][0] <= game_day <= latest):
            bad(f"game.date {game_day} falls outside {t['window'][0]} to {latest}, {LISTING_SLACK} days after the first listing")
        elif game_day and game_day > t["first_listed"]:
            bad(f"game.date {game_day} is after the first listing ({t['first_listed']}): the listing's date is probably wrong", "warning")
        elif game_day and t.get("last_game_before") and game_day != t["last_game_before"]:
            bad(f"game.date {game_day} is not their last game before the listing ({t['last_game_before']})", "warning")
        if _get(f, "setting") == "game" and not game_day:
            bad("a game injury without its game.date: date the game a source names (opponent, playoff game, weekday)", "warning")
        surgery_day = _get(f, "surgery.date")
        if surgery_day and surgery_day < t["window"][0]:
            bad(f"surgery.date {surgery_day} is before the injury window: check it is this injury's (an offseason "
                "operation whose recovery the listing is)", "warning")
    return problems


def run_check(log=print) -> dict:
    """``news-check``: the problems, then what the research found, overall and in the pilot."""
    rows = _read_jsonl(TARGETS)
    if not rows:
        raise SystemExit("run `python -m injury_risk news-targets` first")
    by_id = {t["id"]: t for t in rows}
    facts, evidence = _read_jsonl(FACTS), _read_jsonl(EVIDENCE)
    problems = check(facts, evidence, by_id)
    errors = {tid for kind, tid, _ in problems if kind == "error"}
    for kind, tid, msg in problems[:200]:
        log(f"  {kind}: {tid}: {msg}")
    if len(problems) > 200:
        log(f"  ... and {len(problems) - 200} more")
    report = {}
    groups = [("all", lambda t: True), ("pilot", lambda t: t.get("pilot"))] + [
        (f"{lg} tier {n}", lambda t, lg=lg, n=n: t["league"] == lg and t["tier"] == n) for lg, n in (("nba", 1), ("nba", 2), ("college", 1))]
    for name, member in groups:
        ids = {t["id"] for t in rows if member(t)}
        done = [f for f in facts if f.get("target") in ids]
        ok = [f for f in done if f["target"] not in errors]
        vague = [f for f in ok if vague_listing(by_id[f["target"]])]
        report[name] = dict(targets=len(ids), researched=len(done), passing=len(ok),
                            **{s: sum(f.get("status") == s for f in ok) for s in ("confirmed", "reported", "conflicting", "partial", "not_found")},
                            vague_listings=len(vague),
                            vague_listings_named=sum(_get(f, "diagnosis.label") not in (None, *GENERIC) for f in vague),
                            gained_something_new=sum(gained(f, by_id[f["target"]]) for f in ok),
                            with_mechanism=sum(_get(f, "mechanism") not in (None, "unknown") for f in ok))
    log(json.dumps({k: v for k, v in report.items() if v["researched"]}, indent=1))
    return dict(problems=len(problems), errors=len(errors), report=report)
