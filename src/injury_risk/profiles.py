"""Player profiles for the public site (outputs/profiles/*.json).

- NBA: every player in the box scores since the injury reports began (2018-19), with every injury the reports show,
  their 2025-26 season, and how often players get hurt again after each kind of injury.
- College: every Division I player Covers listed injured, 2019-20 to 2025-26. The listings are grouped into
  injuries and checked against the box scores for the games missed. Only facts are kept (dates, body part, the
  status in plain words, games missed), never Covers' own wording.
- Both: players found in college and then in the NBA, by name and timing, and whether college injuries carry on.
"""
from __future__ import annotations

import json
import re
from collections import Counter

import numpy as np
import pandas as pd

from . import college, sources
from .dashboard import reason_text
from .paths import OUTPUTS, PROCESSED

OUT = OUTPUTS / "profiles"
FIRST_SEASON = 2019          # the first season with injury reports (they start in December 2018)
SEASON = 2026                # the season the boards show
SEASON_START = pd.Timestamp("2025-10-21")
DATA_END = pd.Timestamp("2026-06-30")
FOLLOW_UP = 365              # days after a return in which another injury counts as getting hurt again
MIN_GROUP = 10               # injuries a kind of injury needs before its numbers are shown

NOT_INJURY = re.compile(r"personal|family|conditioning|influenza|illness|ilness|congestion|dental|load man|rehabilitation assign|"
                        r"appendectomy|infection", re.I)   # read after the reports' "Injury/Illness - " prefix
# care of an injury already on record ("Left Knee; Injury Recovery", "Right Achilles Repair; Management"), not a new one
FOLLOW_UP_CARE = re.compile(r"management|recovery|reconditioning|repair|surg|maintenance|post.?op|rehab|return to competition", re.I)
SAME_INJURY_DAYS = 400       # a follow-up listing this long after an injury of the same body region still belongs to it

# Kinds of injury for "what usually happens next", first match wins: (key, name, reason pattern, region, type).
# A missing pattern, region or type matches anything; an injury that matches none falls back to its body region.
KINDS = [
    ("acl", "Torn ACL", r"\bACL\b|anterior cruciate", None, None),
    ("achilles", "Achilles tear", r"achilles.*(tear|rupture|repair|surg)", None, None),
    ("meniscus", "Meniscus tear", r"menisc", None, None),
    ("mcl", "MCL sprain", r"\bMCL\b", None, None),
    ("concussion", "Concussion", None, None, "concussion"),
    ("ankle_sprain", "Ankle sprain", None, "ankle", "ligament"),
    ("hamstring", "Hamstring strain", None, "hamstring", "muscle_tendon"),
    ("calf", "Calf strain", None, "calf", "muscle_tendon"),
    ("groin", "Groin strain", None, "groin", "muscle_tendon"),
    ("foot_fracture", "Broken foot", None, "foot", "bone"),
    ("hand_fracture", "Broken hand or finger", None, "hand", "bone"),
]
REGION_NAMES = {"knee": "Knee", "ankle": "Ankle", "foot": "Foot", "hand": "Hand, wrist or finger", "back": "Back", "hip": "Hip",
                "hamstring": "Hamstring", "calf": "Calf", "groin": "Groin", "thigh": "Thigh", "achilles": "Achilles",
                "shoulder": "Shoulder", "elbow": "Elbow", "head_neck": "Head or neck", "concussion": "Concussion", "trunk": "Chest or ribs",
                "leg": "Lower leg", "other": "Other"}


def kind_of(reason: str, region: str, kind: str) -> str:
    text = str(reason or "")
    for key, _, pattern, r, k in KINDS:
        if (pattern is None or re.search(pattern, text, re.I)) and (r is None or r == region) and (k is None or k == kind):
            return key
    return f"region:{region}"


def kind_name(key: str) -> str:
    named = {k: n for k, n, *_ in KINDS}
    return named.get(key) or REGION_NAMES.get(key.split(":", 1)[-1], key.split(":", 1)[-1].replace("_", " ").capitalize())


def _day(t) -> str | None:
    return None if pd.isna(t) else pd.Timestamp(t).strftime("%Y-%m-%d")


# --- NBA ---------------------------------------------------------------------------------------------------------

# box-score absences an injury can explain while the player is out with one: "management" is how the reports list most
# of a long recovery (Lillard's 2025-26); illness, non-medical reasons and the coach's choice are not
HURT_ABSENCE = {"injury", "unknown_medical", "unknown", "management"}
CARE_JOINS = 10              # care after a return joins the injury only if it cost fewer games; a longer one is its own entry
SPLIT_RUN = 5                # games in a row listed for another body region that make a long absence two injuries


def box_missed(dates: np.ndarray, played: np.ndarray, hurt: np.ndarray, start, end=None) -> int | None:
    """Games on the player's box scores from ``start`` until the next one they played (or ``end``, the next injury),
    counting the absences an injury can explain (unlisted ones too: the reports skip players out long term); None
    when there are none (they were on no roster), so the reports' count stands."""
    after = (dates >= np.datetime64(start)) & (dates < np.datetime64(end) if end is not None and not pd.isna(end) else True)
    if not after.any():
        return None
    p, h = played[after], hurt[after]
    stop = int(np.argmax(p)) if p.any() else len(p)
    return int(h[:stop].sum())


def nba_injuries(onsets: pd.DataFrame, games: dict) -> pd.DataFrame:
    """The reports' injury onsets as injuries. A later listing of the same body region joins the injury before it
    when it is that injury or an unnamed one, within 400 days, and is either care of it or came before the player
    played again. Games missed are counted on the box scores (the reports skip players out long term), else the
    reports' count. ``games``: player id -> (sorted game dates, played that game, an absence an injury can explain,
    that game's report listing as (reason, region, type) or None)."""
    none = (np.array([], dtype="datetime64[ns]"), np.array([], dtype=bool), np.array([], dtype=bool), np.array([], dtype=object))
    played = {pid: d[p] for pid, (d, p, _, _) in games.items()}
    what = onsets["reason"].fillna("").str.replace(r"Injury/Illness\s*-\s*", "", regex=True)
    o = onsets[~what.str.contains(NOT_INJURY)].copy()
    o["text"] = o["reason"].map(reason_text)
    o["kind"] = [kind_of(r, g, k) for r, g, k in zip(o["reason"], o["region"], o["injury_type"])]
    o["care"] = what[o.index].str.contains(FOLLOW_UP_CARE)
    o = o.sort_values(["player_id", "onset_date"]).reset_index(drop=True)
    rows, latest = [], {}
    for x in o.itertuples(index=False):
        e = latest.get((x.player_id, x.region))
        if e is not None:
            first = rows[e]
            days = played.get(x.player_id, none[0])
            back_since = bool(((days > first["onset_date"].to_datetime64()) & (days < x.onset_date.to_datetime64())).any())
            same = x.kind == first["kind"] or x.kind.startswith("region:")
            care = box_missed(*games.get(x.player_id, none)[:3], x.onset_date) if back_since else 0
            care = int(x.games_missed) if care is None else care
            if same and (not back_since or (x.care and care < CARE_JOINS)) and (x.onset_date - first["onset_date"]).days <= SAME_INJURY_DAYS:
                first["report_games"] += int(x.games_missed)
                if back_since:
                    first["care_games"] += care
                else:
                    first["return_date"] = x.return_date
                first["listings"] += 1
                continue
        rows.append(dict(player_id=x.player_id, onset_date=x.onset_date, season=x.season, text=x.text, kind=x.kind, region=x.region,
                         report_games=int(x.games_missed), care_games=0, return_date=x.return_date, new_injury=bool(x.new_injury),
                         days_since_played=x.days_since_played, care=bool(x.care), listings=1))
        latest[(x.player_id, x.region)] = len(rows) - 1
    out = pd.DataFrame(rows)
    nxt = out.groupby("player_id")["onset_date"].shift(-1)   # games after the next injury began are that one's
    box = [box_missed(*games.get(pid, none)[:3], start, end) for pid, start, end in zip(out["player_id"], out["onset_date"], nxt)]
    out["games_missed"] = [(b if b is not None else r) + c for b, r, c in zip(box, out["report_games"], out["care_games"])]
    # A long absence is one onset under its first reason. Read what the reports listed while it lasted: a run of
    # SPLIT_RUN or more games listed for another body region is another injury (Thompson's left ACL, then his right
    # Achilles), and within a region the injury is named by what was listed most (Leonard's 2021 "right knee sprain"
    # was 79 games of "ACL - injury recovery"), keeping the first reason.
    out["first_text"] = out["text"]
    added = []
    for i, (pid, start, end, back) in enumerate(zip(out["player_id"], out["onset_date"], nxt, out["return_date"])):
        d, p, _, why = games.get(pid, none)
        m = d >= np.datetime64(start)
        ends = [t for t in (end, back) if not pd.isna(t)]
        if ends:
            m &= d < np.datetime64(min(ends))
        listed = [(t, w) for t, w in zip(d[m], why[m]) if w is not None]
        if len(listed) < 2:
            continue
        # pieces of the absence: it opens with its own injury; a run of another region joins it unless it is long
        parts = [[np.datetime64(start), out.at[i, "region"], []]]
        for t, w in listed:
            if w[1] == parts[-1][1]:
                parts[-1][2].append(w)
            else:
                parts.append([t, w[1], [w]])
        merged = [parts[0]]
        for part in parts[1:]:
            if part[1] == merged[-1][1]:
                merged[-1][2] += part[2]
            elif len(part[2]) >= SPLIT_RUN:
                merged.append(part)
            else:
                merged[-1][2] += part[2]   # a short run of another region stays with the injury it interrupts
        for j, (t, region, ws) in enumerate(merged):
            ws = [w for w in ws if w[1] == region]
            if not ws:
                continue
            kinds = [kind_of(*w) for w in ws]
            top = pd.Series(kinds).value_counts().index[0]
            text = pd.Series([reason_text(w[0]) for w, k in zip(ws, kinds) if k == top]).value_counts().index[0]
            if j == 0:
                if top != out.at[i, "kind"] and not top.startswith("region:"):
                    out.at[i, "kind"], out.at[i, "text"] = top, text
                continue
            before = d[p & (d < t)]
            gap = (t - before[-1]) / np.timedelta64(1, "D") if len(before) else None
            added.append(dict(player_id=pid, onset_date=pd.Timestamp(t), season=out.at[i, "season"], text=text, kind=top, region=region,
                              report_games=0, care_games=0, return_date=back if j == len(merged) - 1 else pd.NaT, new_injury=False,
                              days_since_played=gap, care=False, listings=len(ws), first_text=text))
        if len(merged) > 1:
            out.at[i, "return_date"] = pd.NaT   # a later injury took over before the player came back
    if added:
        out = pd.concat([out, pd.DataFrame(added)], ignore_index=True).sort_values(["player_id", "onset_date"], ignore_index=True)
        nxt = out.groupby("player_id")["onset_date"].shift(-1)
        box = [box_missed(*games.get(pid, none)[:3], start, end) for pid, start, end in zip(out["player_id"], out["onset_date"], nxt)]
        out["games_missed"] = [(b if b is not None else r) + c for b, r, c in zip(box, out["report_games"], out["care_games"])]
    # back: the next game they played, from the box scores (the reports' return misses comebacks in the playoffs or
    # with a new team), unless another injury began first
    back = []
    for pid, start, end, rep in zip(out["player_id"], out["onset_date"], nxt, out["return_date"]):
        days = played.get(pid)
        if days is None:
            back.append(rep)
            continue
        later = days[days > np.datetime64(start)]
        first = pd.Timestamp(later[0]) if len(later) else pd.NaT
        back.append(pd.NaT if pd.isna(first) or (not pd.isna(end) and end < first) else first)
    out["return_date"] = back
    return out


def what_happens_next(o: pd.DataFrame) -> list[dict]:
    """For each kind of injury: how many games it cost, and how often the player got hurt again within a year of
    coming back (a new injury the reports timed, not care of an old one; the same body region, or any). Only
    returns with a full year to watch count towards the second part."""
    new = o[o["new_injury"] & ~o["care"]]
    later = {pid: (g["onset_date"].to_numpy(), g["region"].to_numpy()) for pid, g in new.groupby("player_id")}
    year = np.timedelta64(FOLLOW_UP, "D")
    again_same, again_any, watched = [], [], []
    for pid, back, region in zip(o["player_id"], o["return_date"].to_numpy(), o["region"]):
        ok = not pd.isna(back) and back + year <= DATA_END.to_datetime64()
        watched.append(ok)
        days, regions = later.get(pid, (np.array([], dtype="datetime64[ns]"), np.array([])))
        hit = (days > back) & (days <= back + year) if ok else np.zeros(len(days), dtype=bool)
        again_any.append(bool(hit.any()))
        again_same.append(bool((hit & (regions == region)).any()))
    o = o.assign(watched=watched, again_any=again_any, again_same=again_same)
    o = o[(o["season"] >= FIRST_SEASON) & ~o["care"]]

    def row(key: str, name: str, x: pd.DataFrame) -> dict:
        w = x[x["watched"]]
        return dict(key=key, name=name, injuries=int(len(x)), players=int(x["player_id"].nunique()),
                    median_missed=float(x["games_missed"].median()), share_10plus=float((x["games_missed"] >= 10).mean()),
                    watched=int(len(w)), again_same=float(w["again_same"].mean()) if len(w) else None,
                    again_any=float(w["again_any"].mean()) if len(w) else None)

    out = [row("any", "Any injury", o)]
    for key, x in o.groupby("kind"):
        if len(x) >= MIN_GROUP:
            out.append(row(key, kind_name(key), x))
    return out


def season_status(pid: int, games: pd.DataFrame, inj: pd.DataFrame) -> str | None:
    """What 2025-26 looked like for a player on a roster: out all of it, out from some date, or nothing to say."""
    mine = games[games["season"] == SEASON]
    if not len(mine):
        return None
    played = int((mine["absence"] == "played").sum())
    covering = inj[(inj["onset_date"] <= DATA_END) & (inj["return_date"].isna() | (inj["return_date"] > SEASON_START))]
    if played == 0:
        named = covering[~covering["kind"].str.startswith("region:")]
        pick = named if len(named) else covering
        return f"Out all season: {pick.iloc[-1]['text']}" if len(pick) else "Didn't play in 2025-26"
    last = inj.iloc[-1] if len(inj) else None
    if last is not None and pd.isna(last["return_date"]) and last["onset_date"] >= SEASON_START and last["games_missed"] >= 5:
        return f"Out from {last['onset_date']:%b} {last['onset_date'].day}: {last['text']}"
    return None


def nba(log=print) -> dict:
    pg = pd.read_parquet(PROCESSED / "player_games.parquet",
                         columns=["player_id", "first_name", "last_name", "season", "game_date", "team", "absence", "reason", "region",
                                  "injury_type"])
    by_date = pg.sort_values("game_date")
    listing = np.array([None if pd.isna(r) else (r, g, k) for r, g, k in zip(by_date["reason"], by_date["region"], by_date["injury_type"])],
                       dtype=object)
    by_date = by_date.assign(listing=listing)
    o = nba_injuries(pd.read_parquet(PROCESSED / "onsets.parquet"),
                     {pid: (g["game_date"].to_numpy(), (g["absence"] == "played").to_numpy(), g["absence"].isin(HURT_ABSENCE).to_numpy(),
                            g["listing"].to_numpy()) for pid, g in by_date.groupby("player_id")})
    pg = pg[pg["season"] >= FIRST_SEASON]
    groups = what_happens_next(o)
    known = {g["key"] for g in groups}
    by_player = {pid: g for pid, g in o.groupby("player_id")}
    players = []
    for pid, g in pg.sort_values("game_date").groupby("player_id"):
        inj = by_player.get(pid, o.iloc[0:0])
        teams = []
        for season, team in zip(g["season"], g["team"]):
            if not teams or teams[-1] != [int(season), team]:
                teams.append([int(season), team])
        played = g[g["absence"] == "played"]
        gp = played.groupby("season").size()
        out = g[g["absence"].isin(HURT_ABSENCE)].groupby("season").size()
        # [first listed, injury, kind (for what usually happens next), body region, games missed, back on, days since their
        #  last game when first listed (only when it came after a gap, so the injury itself was earlier), listings,
        #  the reason it was first listed under when the reports later called it something else]
        entries = []
        for _, x in inj.iterrows():
            new = bool(x["new_injury"])
            entries.append([_day(x["onset_date"]), x["text"], x["kind"] if x["kind"] in known else f"region:{x['region']}",
                            x["region"], int(x["games_missed"]), _day(x["return_date"]),
                            None if new else (int(x["days_since_played"]) if pd.notna(x["days_since_played"]) else -1),
                            int(x["listings"]), x["first_text"] if x["first_text"] != x["text"] else None])
        # gp: games played by season; hurt: games missed by season with an absence an injury can explain
        players.append(dict(id=int(pid), n=f"{g['first_name'].iloc[-1]} {g['last_name'].iloc[-1]}", tm=teams,
                            gp=[[int(s), int(n)] for s, n in gp.items()], hurt=[[int(s), int(n)] for s, n in out.items()],
                            last=_day(played["game_date"].max()) if len(played) else None, st=season_status(pid, g, inj), inj=entries))
    players.sort(key=lambda p: p["n"])
    log(f"  NBA: {len(players)} players, {sum(len(p['inj']) for p in players)} injuries, {len(groups)} kinds of injury")
    return dict(players=players, groups=groups), o


# --- college -----------------------------------------------------------------------------------------------------

COLLEGE = OUTPUTS / "college_moments"
EPISODE_GAP = 21             # days between one listing and the next of the same body part that start a new injury
MATCH_DAYS = 3               # a missed-game run belongs to an injury when it overlaps its listed days, give or take this
MONTHS = {m[:3]: m.capitalize() for m in "january february march april may june july august september october november december".split()}


def plain_status(status: str | None) -> str:
    """Covers' shorthand ('Ques Sat', 'Doub Mon', 'Early March') in plain words."""
    s = str(status or "").strip().lower()
    if "season" in s:
        return "Out for the season"
    if "indef" in s:
        return "Out indefinitely"
    if s.startswith("out"):
        return "Out"
    if s.startswith("doub"):
        return "Doubtful"
    if s.startswith("ques") or s.startswith("gtd") or "game-time" in s:
        return "Questionable"
    if s.startswith("prob"):
        return "Probable"
    month = next((name for m, name in MONTHS.items() if m in s), None)
    if month:
        when = s.split()[0] if s.startswith(("early", "mid", "late")) else "in"
        return f"Expected back {when} {month}"
    return "Listed"


# The injury a college listing's note names, as a label from this list (first match wins, most specific first): a
# fact read from the note, never its wording. Kept with the side and whether surgery was mentioned.
DIAGNOSES = [
    ("Torn ACL", r"(\btorn\b|\btear\b|\btore\b|rupture).{0,30}(\bacl\b|anterior cruciate)|(\bacl\b|anterior cruciate).{0,20}(\btear\b|\btorn\b|rupture)"),
    ("ACL injury", r"\bacl\b|anterior cruciate"),
    ("Achilles tear", r"achilles.{0,40}(\btear\b|\btorn\b|rupture)|(\btorn\b|ruptured|\btore\b).{0,20}achilles"),
    ("Torn patellar tendon", r"patellar tendon"),
    ("Torn meniscus", r"menisc"),
    ("MCL injury", r"\bmcl\b|medial collateral"),
    ("Torn labrum", r"labrum"),
    ("Stress fracture", r"stress (fracture|reaction)"),
    ("Fracture", r"fractur|\bbroken\b|\bbreak\b|\bbroke\b"),
    ("Dislocation", r"dislocat"),
    ("High ankle sprain", r"high[- ]ankle"),
    ("Concussion", r"concuss"),
    ("Torn ligament or tendon", r"\btorn\b|\btear\b|\btore\b|rupture"),
]
SURGERY = re.compile(r"surgery|surgical|procedure|operat", re.I)
# the NBA kind of injury whose numbers fit a college one best, for "what usually happens next"
DIAGNOSIS_KIND = {"Torn ACL": "acl", "ACL injury": "acl", "Achilles tear": "achilles", "Torn meniscus": "meniscus", "MCL injury": "mcl",
                  "Concussion": "concussion", "High ankle sprain": "ankle_sprain"}
PART_REGION = {"ankle": "ankle", "knee": "knee", "foot": "foot", "toe": "foot", "hamstring": "hamstring", "calf": "calf", "groin": "groin",
               "achilles": "achilles", "back": "back", "hip": "hip", "wrist": "hand", "hand": "hand", "finger": "hand", "thumb": "hand",
               "shoulder": "shoulder", "concussion": "concussion", "head": "head_neck", "thigh": "thigh", "quad": "thigh"}


def diagnosis(notes: list) -> tuple[str | None, str | None, bool]:
    """The most specific injury any of an injury's notes names, the side its note gives, and whether one mentions surgery."""
    best, side = None, None
    for note in notes:
        text = str(note or "")
        for rank, (label, pattern) in enumerate(DIAGNOSES):
            if re.search(pattern, text, re.I):
                if best is None or rank < best[0]:
                    best = (rank, label)
                    m = re.search(r"\b(left|right)\b", text, re.I)
                    side = m.group(1).lower() if m else side
                break
    return (best[1] if best else None), side, any(SURGERY.search(str(n or "")) for n in notes)


def college_kind(group: str, part: str, dx: str | None) -> str:
    """The NBA kind of injury for a college one: its diagnosis when it names one, else its body part."""
    if dx in DIAGNOSIS_KIND:
        return DIAGNOSIS_KIND[dx]
    p = str(part or "").lower()
    region = next((r for word, r in PART_REGION.items() if word in p), None)
    if dx in ("Fracture", "Stress fracture") and region in ("foot", "hand"):
        return f"{region}_fracture"
    if group == "ankle" and region in (None, "ankle"):
        return "region:ankle"
    return f"region:{region}" if region else "any"


def name_from_slug(slug: str) -> str:
    words = [w for w in re.split(r"[-\s]+", str(slug or "")) if w]
    return " ".join(w.upper() if w.rstrip(".") in ("ii", "iii", "iv") else w.capitalize() for w in words)


def college_profiles(log=print) -> dict:
    """Every player with a Covers injury listing. [first listed, last listed, season, body part (Covers' word), group,
    kind (from the note), status in plain words, games missed (box scores; None when the player could not be found
    in them), back that season, days the listing was saved, the injury the notes name (DIAGNOSES) or None, its
    side, surgery mentioned, the NBA kind of injury for "what usually happens next"]."""
    every = pd.read_parquet(COLLEGE / "listings_matched.parquet")
    saved = every.assign(day=every["captured"].dt.normalize()).groupby("season")["day"].nunique()
    lst = every[every["group"].notna()].copy()   # injuries only: not illness, eligibility, suspensions or anything undisclosed
    runs = pd.read_parquet(COLLEGE / "runs.parquet", columns=["season", "team_id", "player_id", "first_date", "last_date", "games_missed",
                                                             "back"])
    boxes = pd.concat([college.box(s) for s in sources.COLLEGE_SEASONS], ignore_index=True)
    games_of = boxes.groupby(["season", "player_id"]).size()
    first_game = boxes.groupby(["season", "player_id"])["game_date"].min()
    name_of = boxes.sort_values("game_date").groupby("player_id")["clean_name"].last()
    sched = {k: np.sort(g["game_date"].to_numpy())
             for k, g in boxes.drop_duplicates(["season", "team_id", "contest_id"]).groupby(["season", "team_id"])}
    runs_of = {k: g for k, g in runs.groupby(["season", "player_id"])}
    day = pd.Timedelta(days=1)

    people = []
    for cid, g in lst.sort_values(["captured"]).groupby("covers_id"):
        g = g.assign(start=g[["note_date", "captured"]].min(axis=1))
        # a note still up the next season keeps its date: it belongs to the season it was written in (stale, not new)
        g = g.assign(season=np.where(g["start"].dt.month >= 7, g["start"].dt.year + 1, g["start"].dt.year))
        pids = g.dropna(subset=["player_id"]).astype({"player_id": "int64"}).groupby("season")["player_id"].agg(lambda s: s.mode().iloc[0])
        named = [name_of.get(pid) for pid in pids.to_numpy()[::-1] if name_of.get(pid)]
        schools = g.groupby("season")["school"].agg(lambda s: s.mode().iloc[0])
        entries = []
        for (season, grp), x in g.sort_values("start").groupby(["season", "group"]):
            # listings of one body part that season, split where the page went three weeks without one
            season_end = pd.Timestamp(f"{int(season)}-06-30")
            spans, cur = [], None
            for r in x.itertuples(index=False):
                seen = min(r.captured, season_end)
                if cur is not None and (r.start - cur["end"]).days <= EPISODE_GAP:
                    cur["end"] = max(cur["end"], seen)
                    cur["rows"].append(r)
                else:
                    cur = dict(start=r.start, end=seen, rows=[r])
                    spans.append(cur)
            for sp in spans:
                rows = sp["rows"]
                last = max(rows, key=lambda r: r.captured)
                part = pd.Series([r.part for r in rows]).mode().iloc[0]
                kinds = [r.kind for r in rows if r.kind and r.kind != "other"]
                pid = pids.get(season)
                missed, back = None, None
                team = rows[0].team_id
                dates = sched.get((season, int(team))) if pd.notna(team) else None
                if pid is not None:
                    rr = runs_of.get((season, pid))
                    if rr is not None:
                        hit = rr[(rr["last_date"] >= sp["start"] - MATCH_DAYS * day) & (rr["first_date"] <= sp["end"] + MATCH_DAYS * day)]
                        if len(hit):
                            missed, back = int(hit["games_missed"].sum()), bool(hit.sort_values("first_date")["back"].iloc[-1])
                    debut = first_game.get((season, pid))
                    if dates is not None and (debut is None or sp["start"] < debut):
                        # out before their first game of the season, which no run of missed games shows
                        before = int(((dates >= np.datetime64(sp["start"] - MATCH_DAYS * day)) &
                                      (dates < np.datetime64(debut) if debut is not None else True)).sum())
                        missed, back = (missed or 0) + before, (back if missed is not None else debut is not None)
                    if missed is None:
                        missed = 0
                elif pd.notna(rows[0].team_id) and plain_status(last.status) == "Out for the season":
                    dates = sched.get((season, int(rows[0].team_id)))
                    if dates is not None:
                        missed, back = int((dates >= np.datetime64(sp["start"])).sum()), False
                dx, side, surgery = diagnosis([r.note for r in rows])
                entries.append([_day(sp["start"]), _day(sp["end"]), int(season), part, grp, kinds[-1] if kinds else None,
                                plain_status(last.status), missed, back, len({r.captured.normalize() for r in rows}),
                                dx, side, surgery, college_kind(grp, part, dx)])
        if not entries:
            continue
        # the same absence listed the same day under a vague part ("Leg", "Upper Body") and a named one: keep the named one
        named_days = {(e[0], e[2]) for e in entries if e[4] != "other"}
        entries = [e for e in entries if e[4] != "other" or (e[0], e[2]) not in named_days]
        entries.sort(key=lambda e: e[0])
        people.append(dict(id=int(cid), n=named[0] if named else name_from_slug(g["player_slug"].iloc[-1]),
                           sch=[[int(s), schools[s]] for s in schools.index],
                           gp=[[int(s), int(games_of.get((s, pid), 0))] for s, pid in pids.items()], inj=entries,
                           ncaa={int(s): int(pid) for s, pid in pids.items()}))
    people.sort(key=lambda p: p["n"])
    log(f"  college: {len(people)} players, {sum(len(p['inj']) for p in people)} injuries")
    careers = boxes.groupby(["season", "player_id"]).agg(name=("clean_name", "last"), team=("team", "last"), games=("contest_id", "nunique"))
    careers = careers.reset_index().assign(key=lambda c: c["name"].map(college._person))
    return dict(people=people, saved=[dict(season=int(s), days=int(n)) for s, n in saved.items()]), careers


# --- college and then the NBA ------------------------------------------------------------------------------------

FIRST_ROOKIES = 2021         # NBA debuts from 2020-21, so the college seasons before them have saved injury pages
CAREER_GAP = 3               # seasons a college career may end before the NBA debut (a year or two in the G League or abroad)
WELL_SAVED = 30              # days the injury page was saved in a season for that season's listings to be fairly complete


def college_links(pro: dict, col: dict, careers: pd.DataFrame) -> dict:
    """NBA player id -> their college career and Covers profile: the same name, a college career that ended one to
    three seasons before their NBA debut, nobody else of that name on an NBA court in those debut seasons, and nobody
    of that name in college in the last college season but them or in any season after it."""
    first = {p["id"]: min(s for s, _ in p["tm"]) for p in pro["players"]}   # first season on a roster (Sorber never played)
    key = {p["id"]: college._person(p["n"]) for p in pro["players"]}
    rookies = {pid: f for pid, f in first.items() if f >= FIRST_ROOKIES}
    taken = Counter(key[pid] for pid in rookies)
    by_key = {k: g for k, g in careers.groupby("key")}
    profile = {}
    for person in col["people"]:
        for s, pid in person["ncaa"].items():
            profile[(s, pid)] = person
    links = {}
    for pid, f in rookies.items():
        g = by_key.get(key[pid])
        if g is None or taken[key[pid]] != 1 or (g["season"] >= f).any():
            continue
        g = g[g["season"].between(f - CAREER_GAP, f - 1)]
        if not len(g):
            continue
        last = g[g["season"] == g["season"].max()]
        if len(last) != 1:
            continue
        # walking back from the last season: where two have that name, theirs is the one at the school they played for
        # the season after (Jalen Williams of Santa Clara, not of Cleveland State, in 2019-20); with neither there, the
        # season is left out. The box scores' player ids change every season, so they can't tell
        mine, school = [], last["team"].iloc[0]
        for season in sorted(g["season"].unique(), reverse=True):
            rows = g[g["season"] == season]
            pick = rows if len(rows) == 1 else rows[rows["team"] == school]
            if len(pick) == 1:
                mine.append(pick)
                school = pick["team"].iloc[0]
        mine = pd.concat(mine).sort_values("season")
        person = next((profile[(int(s), int(c))] for s, c in zip(mine["season"], mine["player_id"]) if (int(s), int(c)) in profile), None)
        links[pid] = dict(school=last["team"].iloc[0], last=int(last["season"].iloc[0]), seasons=int(mine["season"].nunique()),
                          games=int(mine["games"].sum()), person=person)
    return links


def bridge(pro: dict, inj: pd.DataFrame, col: dict, careers: pd.DataFrame, log=print) -> dict:
    """Players found in college and then in the NBA (college_links). Then, exploratory: did players whose college
    injuries Covers listed get hurt more in their first two NBA seasons?"""
    links = college_links(pro, col, careers)
    rookies = sum(min(s for s, _ in p["tm"]) >= FIRST_ROOKIES for p in pro["players"])
    saved = {r["season"]: r["days"] for r in col["saved"]}

    # their first two NBA seasons: new injuries the reports timed (not care of an old one) per game played
    new = inj[inj["new_injury"] & ~inj["care"]]
    hurt = new.groupby(["player_id", "season"]).size()
    games = {p["id"]: dict(p["gp"]) for p in pro["players"]}
    rows = []
    for pid, link in links.items():
        if not any(n > 0 for n in games[pid].values()):
            continue
        f = min(s for s, n in games[pid].items() if n > 0)   # their first two seasons with games
        if f + 1 > SEASON:
            continue
        gp = games[pid].get(f, 0) + games[pid].get(f + 1, 0)
        if gp < 20:
            continue
        listed = link["person"] is not None
        rows.append(dict(pid=pid, listed=listed, games=gp, injuries=int(hurt.get((pid, f), 0) + hurt.get((pid, f + 1), 0)),
                         well_saved=saved.get(link["last"], 0) >= WELL_SAVED,
                         college_games_missed=sum(e[7] or 0 for e in link["person"]["inj"]) if listed else 0))
    t = pd.DataFrame(rows)

    def compare(x: pd.DataFrame) -> dict:
        def rate(y):
            return 100 * y["injuries"].sum() / y["games"].sum()
        a, b = x[x["listed"]], x[~x["listed"]]
        rng = np.random.default_rng(0)
        draws = []
        for _ in range(2000):
            ra, rb = a.iloc[rng.integers(0, len(a), len(a))], b.iloc[rng.integers(0, len(b), len(b))]
            if rate(rb) > 0:
                draws.append(rate(ra) / rate(rb))
        lo, hi = np.percentile(draws, [2.5, 97.5])
        return dict(listed=dict(players=int(len(a)), games=int(a["games"].sum()), injuries=int(a["injuries"].sum()), per_100=rate(a)),
                    not_listed=dict(players=int(len(b)), games=int(b["games"].sum()), injuries=int(b["injuries"].sum()), per_100=rate(b)),
                    ratio=rate(a) / rate(b), lo=float(lo), hi=float(hi))

    study = dict(matched=len(links), rookies=rookies, with_profile=sum(1 for v in links.values() if v["person"] is not None),
                 compared=int(len(t)), all=compare(t), well_saved=compare(t[t["well_saved"]]))
    log(f"  in both: {len(links)} of {rookies} NBA debuts since 2020-21 found in college, {study['with_profile']} with a college "
        f"injury listing; first two NBA seasons, listed vs not: {study['all']['ratio']:.2f}x ({study['all']['lo']:.2f}-{study['all']['hi']:.2f})")
    return dict(links=links, study=study)


def export(log=print) -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    pro, inj = nba(log)
    col, careers = college_profiles(log)
    both = bridge(pro, inj, col, careers, log)
    for p in pro["players"]:
        link = both["links"].get(p["id"])
        if link:   # [school, last college season, seasons, games, college profile id, injuries Covers listed]
            person = link["person"]
            p["col"] = [link["school"], link["last"], link["seasons"], link["games"], person["id"] if person else None,
                        len(person["inj"]) if person else 0]
    nba_of = {link["person"]["id"]: pid for pid, link in both["links"].items() if link["person"]}
    for person in col["people"]:
        person.pop("ncaa")
        if person["id"] in nba_of:
            person["nba"] = nba_of[person["id"]]
    sizes = {}
    for name, data in (("nba", pro), ("college", col), ("both", both["study"])):
        text = json.dumps(data, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        (OUT / f"{name}.json").write_text(text, encoding="utf-8")
        sizes[name] = len(text.encode())
    log(json.dumps(sizes))
    return sizes
