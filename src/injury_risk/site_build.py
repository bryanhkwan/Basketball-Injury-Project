"""The public site in docs/, for GitHub Pages.

- docs/data/*.json: what the pages read. board.json and players.json hold the 2025-26 risk board and each player's risk
  game by game, with NBA players by name (the league's injury reports are public); study.json holds the summary tables
  of the model check, the risk factors, the injury types, how injuries happened (from the news) and the checks against
  the news; careers.json the career study; details.json each injury's facts from the news (facts and links, never the
  reports' words) and how the player came back.
- docs/index.html: the overview page, from site/overview.html with its figures filled in from docs/data.
- docs/dashboard.html and docs/assets/*.css|js: the dashboards, copied from site/ as they are.
- docs/moments.html: the injury-moment report (report_site.py).

write_data() needs the analysis outputs (outputs/dashboard, outputs/causes, outputs/moments_dashboard); the pages are
rendered from docs/data, so a fresh clone can rebuild them without the private downloads.
"""
from __future__ import annotations

import functools
import html
import json
import math
import shutil
import statistics
import subprocess
import tempfile
import threading
from collections import Counter, defaultdict
from datetime import date
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from string import Template
from urllib.parse import urlparse

from .paths import OUTPUTS
from .report_site import AUTHOR, DOCS, REPO_URL, SEASONS, SITE, SITE_URL
from . import report_site

DATA = DOCS / "data"
PROFILES = OUTPUTS / "profiles"
AFTERMATH = OUTPUTS / "aftermath"
NEWS = OUTPUTS / "news"
ASSETS = ("site.css", "app.css", "charts.js", "site.js", "overview.js", "dashboard.js")
MODES = {"before": dict(label="Before tip-off", question="a new injury in the next 5 games", short="next 5 games",
                        none="No new injury in the next 5 games"),
         "after": dict(label="After the game", question="missing the next game with a new injury", short="next game",
                       none="No new injury next game")}
OPENING_NIGHT = "2025-10-21"
PORTFOLIO_URL = "https://bryanhkwan.github.io/portfolio/"
LINKEDIN_URL = "https://www.linkedin.com/in/bryanhkwan"
LIVE_ROWS = 5        # rows of the overview's board; the dashboard shows all of them
esc = html.escape


def _read(folder: str, name: str):
    return json.loads((OUTPUTS / folder / f"{name}.json").read_text(encoding="utf-8"))


def _round(obj, digits: int = 4):
    """Floats to a few decimals, so the published files stay small."""
    if isinstance(obj, float):
        return round(obj, digits)
    if isinstance(obj, list):
        return [_round(v, digits) for v in obj]
    if isinstance(obj, dict):
        return {k: _round(v, digits) for k, v in obj.items()}
    return obj


# ---- data -----------------------------------------------------------------------------------------------------------

def board_data() -> dict:
    """Each night's board in both modes: [player id, name, team, opponent, risk per mille, drivers, injured, outcome].
    A driver is [index into drivers, value as shown], e.g. [0, "4.3"] for "Recent-injury score: 4.3"."""
    rows, risk = _read("dashboard", "board"), _read("dashboard", "player_risk")
    ids = {}
    for r in risk:
        ids.setdefault(r["player"], r["player_id"])
    labels: list[str] = []

    def driver(text: str) -> list:
        label, _, value = text.rpartition(": ") if ": " in text else (text, "", "")   # a flag has no value
        if label not in labels:
            labels.append(label)
        return [labels.index(label), value]

    modes = {}
    for mode, meta in MODES.items():
        nights = defaultdict(list)
        for r in rows:
            if r["mode"] == mode:
                nights[r["date"]].append(r)
        modes[mode] = dict(meta, nights=[
            [day, [[ids.get(r["player"]), r["player"], r["team"], r["opponent"], round(r["risk"] * 1000),
                    [driver(t) for t in r["drivers"].split(" · ")], r["injured"], r["outcome"] if r["injured"] else ""]
                   for r in sorted(nights[day], key=lambda r: r["rank"])]]
            for day in sorted(nights)])
    check = defaultdict(dict)
    for r in _read("dashboard", "board_check"):
        check[r["mode"]][r["group"]] = dict(label=r["label"], rate=r["rate"], rows=r["rows"], outcome=r["outcome"])
    return _round(dict(drivers=labels, modes=modes, check=check))


def players_data(board: dict) -> dict:
    """Every player scored in 2025-26: risk per mille on each game day (indices into dates), teams, new injuries."""
    risk, injuries = _read("dashboard", "player_risk"), _read("dashboard", "player_injuries")
    dates = sorted({r["date"] for r in risk})
    at = {d: i for i, d in enumerate(dates)}
    by_player, by_day = defaultdict(list), defaultdict(list)
    for r in risk:
        by_player[r["player_id"]].append(r)
        by_day[r["date"]].append(r["risk"])
    on_board = Counter(row[0] for _, night in board["modes"]["before"]["nights"] for row in night)
    hurt = defaultdict(list)
    for r in sorted(injuries, key=lambda r: r["onset_date"]):
        hurt[r["player_id"]].append([r["onset_date"], r["reason"], r["games_missed"]])
    players = []
    for pid, games in by_player.items():
        games.sort(key=lambda r: r["date"])
        teams = []
        for g in games:
            if not teams or teams[-1][1] != g["team"]:
                teams.append([at[g["date"]], g["team"]])
        players.append(dict(id=pid, n=games[0]["player"], tm=teams, d=[at[g["date"]] for g in games],
                            r=[round(g["risk"] * 1000) for g in games], inj=hurt.get(pid, []), b=on_board.get(pid, 0)))
    players.sort(key=lambda p: p["n"])
    return dict(dates=dates, avg=[round(1000 * sum(by_day[d]) / len(by_day[d])) for d in dates], players=players)


def study_data() -> dict:
    moments = {n: _read("moments_dashboard", n) for n in ("facts", "nba_patterns", "college_tests")}
    # the college check's results (the players behind them are on their own profiles, from the listings' facts)
    college = [{k: t[k] for k in ("key", "order", "label", "group", "times", "lo", "hi", "nba_key", "nba_times", "verdict",
                                  "verdict_label", "primary", "injury_exits", "with_play")} for t in moments["college_tests"]]
    carry = json.loads((PROFILES / "both.json").read_text(encoding="utf-8")) if (PROFILES / "both.json").exists() else None
    return _round(dict(
        model=dict(scores=_read("dashboard", "model_scores"), seasons=_read("dashboard", "season_scores"),
                   calibration=_read("dashboard", "calibration"), drivers=_read("dashboard", "drivers"),
                   coverage=_read("dashboard", "coverage")),
        factors=dict(risk=_read("dashboard", "risk_factors"), early=_read("dashboard", "early_exits"),
                     trend=_read("dashboard", "injury_trend"), mix=_read("dashboard", "injury_mix"),
                     prone=_read("dashboard", "prone_players")),
        causes={n: _read("causes", n) for n in ("facts", "groups", "months", "situations", "traits")},
        moments=dict(facts={r["metric"]: r["value"] for r in moments["facts"]}, patterns=moments["nba_patterns"],
                     college=college),
        compare=compare_data(), carry=carry, **{k: json.loads(v.read_text(encoding="utf-8")) for k, v in
                                                (("news", NEWS / "summary.json"), ("checks", OUTPUTS / "validation" / "summary.json"))
                                                if v.exists()}))


# the NBA-vs-college comparison: the same injury-moment test in both leagues, as totals only
PLAYS = {"rebound": "Rebound", "off_rebound": "Offensive rebound", "def_rebound": "Defensive rebound",
         "rim": "Shot at the rim", "drive": "Drove or cut to the basket", "dunk": "Dunk", "putback": "Tip-in or putback",
         "jumper": "Jump shot", "fouled": "Was fouled", "foul_def": "Committed a defensive foul",
         "foul_off": "Offensive foul or charge", "block": "Blocked a shot", "steal": "Steal",
         "tov_handle": "Lost the ball or traveled", "tov_pass": "Bad pass or other turnover",
         "scramble": "On the floor for a rebound", "scramble_close": "On the floor near the basket",
         "opp_rim": "Defending a rim attack", "any_play": "Any play of their own", "no_play": "No play of their own"}
GROUPS = {"any": "Any injury", "ankle": "Ankle", "knee": "Knee", "foot": "Foot and toe", "muscle": "Pulled muscle",
          "back_hip": "Back and hip", "hand": "Hand and arm", "head": "Head and face", "shoulder": "Shoulder",
          "other": "Everything else"}


def compare_data() -> dict:
    nba = json.loads((OUTPUTS / "moments" / "summary.json").read_text(encoding="utf-8"))
    col = json.loads((OUTPUTS / "college_moments" / "summary.json").read_text(encoding="utf-8"))

    def main(s: dict) -> dict:
        """The main comparison: 30 seconds before the exit, injury exits against the same players' other exits."""
        return {(r["group"], r["play"]): r for r in s["table"]
                if r["window"] == 30 and r["against"] == "exit" and r["case_role"] == "case" and not r["by_stoppage"]
                and r["short"] == 0.6}

    def cut(r: dict) -> list:
        return [r["odds_ratio"], r["lo"], r["hi"], r["case_share"], r["comparison_share"], r["cases"]]

    def estimable(r: dict) -> bool:
        """A play no injured player made has no ratio (NaN in the summaries); leave it out rather than draw it."""
        return all(isinstance(v, (int, float)) and math.isfinite(v) and v > 0 for v in (r["odds_ratio"], r["lo"], r["hi"]))

    n, c = main(nba), main(col)
    plays = [dict(group=g, play=p, label=PLAYS[p], nba=cut(n[(g, p)]), col=cut(c[(g, p)]))
             for (g, p) in sorted(n) if g in GROUPS and p in PLAYS and (g, p) in c
             and estimable(n[(g, p)]) and estimable(c[(g, p)])]
    ng, cg = {g["group"]: g for g in nba["groups"]}, {g["group"]: g for g in col["groups"]}
    groups = [dict(group=g, name=name, nba=[ng[g]["injuries"], ng[g]["pinned_share"]],
                   col=[cg[g]["injuries"], cg[g]["evaluable"], cg[g]["pinned"], cg[g]["pinned_share"]])
              for g, name in GROUPS.items() if g in ng and g in cg]
    after = col["added_after_results"]
    return _round(dict(
        plays=plays, groups=groups, agreement=agreement(plays),
        stoppages={"nba": {k: nba["stoppages"][k] for k in ("injury exits", "ordinary exits")},
                   "col": {k: col["stoppages"][k] for k in ("injury exits", "ordinary exits")}},
        seasons=[{k: s[k] for k in ("season", "games", "games_kept", "player_games_kept")} for s in col["quality"]["seasons"]],
        listings=dict(named=col["quality"]["listings"]["named_injury_listings"],
                      matched=col["quality"]["listings"]["matched_to_a_player"]),
        pooled=after["pooled"]["correlated"], power=after["power"], versus=after["versus_nba"]))


def agreement(plays: list) -> dict:
    """How the two leagues line up across every play before every kind of injury. Exploratory: the pairs overlap (any
    injury includes the ankle ones; a play and no play are opposites), so this describes a pattern and is not a test."""
    def clear(v: list) -> bool:
        return v[1] > 1 or v[2] < 1

    def same(p: dict) -> bool:
        return (p["nba"][0] - 1) * (p["col"][0] - 1) > 0

    def r(rows: list) -> float:
        return statistics.correlation([math.log(p["nba"][0]) for p in rows], [math.log(p["col"][0]) for p in rows])

    nba_clear = [p for p in plays if clear(p["nba"])]
    both = [p for p in nba_clear if clear(p["col"])]
    any_injury = [p for p in plays if p["group"] == "any"]
    return dict(pairs=len(plays), nba_clear=len(nba_clear), nba_clear_same=sum(map(same, nba_clear)),
                both_clear=len(both), both_clear_same=sum(map(same, both)),
                any_plays=len(any_injury), r_any=r(any_injury), r_all=r(plays))


def profiles_data() -> dict:
    """Every NBA player's injury history since 2018-19 and every college player Covers listed injured
    (outputs/profiles), with a small index of both for the search box: [id, name, team or school, injuries, league],
    college ids starting with "c"."""
    nba, college = (json.loads((PROFILES / f"{n}.json").read_text(encoding="utf-8")) for n in ("nba", "college"))
    nba["saved"] = college["saved"]   # an NBA profile's college card says how often its last college season was saved
    people = ([[p["id"], p["n"], p["tm"][-1][1], len(p["inj"]), "nba"] for p in nba["players"]]
              + [[f"c{p['id']}", p["n"], p["sch"][-1][1], len(p["inj"]), "college"] for p in college["people"]])
    return dict(history=nba, college=college, people=people)


def source(s: dict) -> list:
    """A citation as the profiles show it: [outlet, published, headline, url, official]. NBA.com's pages go without
    their link: its terms forbid linking to it for public use without permission."""
    host = urlparse(s["url"]).hostname or ""
    return [s["outlet"], s.get("published"), s.get("headline"), None if host == "nba.com" or host.endswith(".nba.com") else s["url"],
            bool(s.get("official"))]


def _facts(f: dict) -> dict:
    """A fact row without its empty fields, and its sources as citations."""
    def keep(v):
        if isinstance(v, dict):
            v = {k: keep(x) for k, x in v.items()}
            return {k: x for k, x in v.items() if x not in (None, {}, [])} or None
        return v
    out = {k: keep(f.get(k)) for k in ("status", "diagnosis", "side", "grade", "setting", "game", "contact", "mechanism", "surgery",
                                       "expected")}
    out = {k: v for k, v in out.items() if v not in (None, {}, [])}
    out["sources"] = [source(s) for s in f.get("sources") or []]
    return out


def details_data() -> dict:
    """What each injury was and how the player came back, keyed as the profiles' injuries:
    - news: the research's facts (outputs/news/facts.jsonl), NBA as '<id>:<first listed>:<region>' and, for college
      players now in the NBA, 'c<id>:<first listed>:<part>' (the others are students, and little was written about them);
    - after: the career study's row (outputs/aftermath/players.json), as '<id>:<first listed>'."""
    targets = {t["id"]: t for t in map(json.loads, (NEWS / "targets.jsonl").read_text(encoding="utf-8").splitlines()) if t}
    news = {}
    for line in (NEWS / "facts.jsonl").read_text(encoding="utf-8").splitlines():
        f = json.loads(line) if line.strip() else None
        t = targets.get(f["target"]) if f else None
        if not t or f["status"] == "not_found" or (t["league"] == "college" and not t.get("nba_profile")):
            continue
        league, pid, first, part = f["target"].split(":")
        news[f"{'c' if league == 'college' else ''}{pid}:{first}:{part}"] = _facts(f)
    after = json.loads((AFTERMATH / "players.json").read_text(encoding="utf-8")) if (AFTERMATH / "players.json").exists() else {}
    return _round(dict(news=news, after=after))


def write_data(log=print) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    board = board_data()
    files = [("board", board), ("players", players_data(board)), ("study", study_data())]
    if (PROFILES / "nba.json").exists():
        files += list(profiles_data().items())
    if (AFTERMATH / "summary.json").exists():
        files.append(("careers", json.loads((AFTERMATH / "summary.json").read_text(encoding="utf-8"))))
    if (NEWS / "targets.jsonl").exists():
        files.append(("details", details_data()))
    for name, obj in files:
        text = json.dumps(obj, ensure_ascii=False, separators=(",", ":"), allow_nan=False)   # browsers can't parse NaN
        (DATA / f"{name}.json").write_text(text, encoding="utf-8")
        log({"data": f"docs/data/{name}.json", "bytes": len(text.encode())})


def load() -> dict:
    return {n: json.loads((DATA / f"{n}.json").read_text(encoding="utf-8")) for n in ("board", "players", "study", "careers")
            if n != "careers" or (DATA / f"{n}.json").exists()}


# ---- the overview page --------------------------------------------------------------------------------------------

def pct(v: float, digits: int = 1) -> str:
    return f"{100 * v:.{digits}f}%"


def day_label(iso: str, weekday: bool = True) -> str:
    d = date.fromisoformat(iso)
    return f"{d:%A}, {d:%B} {d.day}, {d.year}" if weekday else f"{d:%b} {d.day}, {d.year}"


def short_day(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d:%a}, {d:%b} {d.day}"


def times_text(ratio: float) -> str:
    """2.51 -> '2.5×'; below 1 the fall in words: 0.82 -> '18% less'."""
    return f"{ratio:.1f}×" if ratio >= 1 else f"{round(100 * (1 - ratio))}% less"


def board_rows(night: list, limit: int = LIVE_ROWS) -> str:
    """The hero's board: rank, player, team and what happened, and the chance as a number and a bar."""
    top = max(r[4] for r in night) or 1
    out = []
    for rank, row in enumerate(night[:limit], start=1):
        if row[6]:
            injury, _, cost = row[7].partition(" (")
            what = f'<span class="out hurt">{esc(injury)}, {esc(cost.rstrip(")"))}</span>'
        else:
            what = '<span class="out">No new injury</span>'
        out.append(f'<li class="bc-row{" is-hurt" if row[6] else ""}"><span class="bc-rank">{rank}</span>'
                   f'<span class="bc-who"><b>{esc(row[1])}</b><small>{esc(row[2])} vs {esc(row[3])} · {what}</small></span>'
                   f'<span class="bc-chance"><span class="bc-bar" aria-hidden="true"><i style="width:{100 * row[4] / top:.0f}%"></i></span>'
                   f'<b>{row[4] / 10:.0f}%</b></span></li>')
    return "".join(out)


KINDS = [("any", "Any injury"), ("muscle", "Muscles"), ("sprain", "Ankles"), ("contact", "Knocks"), ("knee", "Knees"),
         ("back", "Backs"), ("other", "Other")]
FINDINGS = 6   # findings shown per kind of injury on the overview


def kind_lists(causes: dict) -> tuple[str, str]:
    """One tab per kind of injury, and its strongest findings that held in both halves of the seasons."""
    rows = causes["situations"] + causes["traits"]
    groups = {g["group"]: g for g in causes["groups"]}
    facts = {f["metric"]: f["value"] for f in causes["facts"]}
    tabs, panels = [], []
    for i, (key, short) in enumerate(KINDS):
        found = sorted((r for r in rows if r["group"] == key and r["headline"]), key=lambda r: -abs(r["ratio"] - 1))[:FINDINGS]
        state = ' aria-selected="true"' if i == 0 else ' aria-selected="false" tabindex="-1"'
        tabs.append(f'<button type="button" role="tab" id="kind-{key}" aria-controls="panel-{key}"{state}>{esc(short)}</button>')
        g = groups.get(key)
        if g:
            summary = (f'{g["injuries"]:,} injuries · {g["games_lost_per_team_season"]:.0f} games lost per team each season · '
                       f'{round(100 * g["repeat_share"])}% hit the same spot again within a year')
        else:
            summary = (f'{facts["injuries"]:,.0f} injuries · {facts["games_lost_per_team_season"]:.0f} games lost per team each '
                       f'season · about {facts["players_out_per_game"]:.1f} players per team out on an average night')
        items = "".join(
            f'<li class="find {"up" if r["ratio"] >= 1 else "down"}"><span class="chip num">{times_text(r["ratio"])}</span>'
            f'<span class="find-what"><b>{esc(r["label"])}</b><small>vs {esc(r.get("versus") or "everyone else")}</small></span></li>'
            for r in found)
        hidden = "" if i == 0 else " hidden"
        panels.append(f'<div class="kind-panel" role="tabpanel" id="panel-{key}" aria-labelledby="kind-{key}"{hidden}>'
                      f'<p class="kind-sum">{summary}</p><ol class="finds">{items}</ol></div>')
    return "".join(tabs), "".join(panels)


def bar_rows(rows: list[tuple], pair: bool = False) -> str:
    """The overview's bar rows, drawn here like the dashboards' pairs: (label, note, share[, its comparison]) per row,
    each with its figure; with pair, the comparison in grey under it."""
    top = max(max(r[2:]) for r in rows) or 1
    out = []
    for label, note, *shares in rows:
        marks = [("", shares[0])] + ([(' class="cmp"', shares[1])] if pair else [])
        bars = "".join(f'<span><i{cls} style="width:{100 * v / top:.0f}%"></i>{pct(v, 0)}</span>' for cls, v in marks)
        out.append(f'<div class="pair"><span class="label">{esc(label)}<small>{esc(note)}</small></span><span class="bars">{bars}</span></div>')
    return f'<div class="pairs">{"".join(out)}</div>'


def news_values(study: dict) -> dict:
    """The overview's figures from the news research (study.json's news summary)."""
    n = study["news"]
    by = {g["key"]: g for g in n["groups"]}
    contact = [(g["name"], f'{g["contact"]["non_contact"]} of {g["contact"]["known"]}', g["contact"]["non_contact"] / g["contact"]["known"])
               for g in (by.get(k) for k in ("achilles", "muscle", "acl", "knee_sprain", "ankle", "concussion"))
               if g and g["contact"]["known"] >= 10]
    ankle, achilles = by["ankle"], by["achilles"]
    foot = dict(ankle["mechanisms"]["counts"]).get("stepped_on_foot", 0)
    return dict(news_researched=f'{n["researched"]:,}', news_named=f'{n["status"].get("confirmed", 0) + n["status"].get("reported", 0):,}',
                news_how=f'{n["all"]["mechanisms"]["known"]:,}', news_vague=f'{n["vague"]["named"]} of {n["vague"]["listed"]}',
                news_game=f'{n["game"]:,}', news_contact=bar_rows(contact),
                news_finding=(f'A torn Achilles almost never involved contact ({achilles["contact"]["non_contact"]} of '
                              f'{achilles["contact"]["known"]}); most ankle sprains came from landing on someone’s foot '
                              f'({foot} of {ankle["mechanisms"]["known"]} with a known cause).'))


def career_values(careers: dict) -> dict:
    """The overview's figures from the career study (careers.json)."""
    by = {g["key"]: g for g in careers["groups"]}
    def one(g, k):
        return next(r for r in g["year_1"] + g["outcomes"] if r.get("metric", r.get("outcome")) == k)
    again = []
    for k in ("all", "muscle", "concussion", "ankle", "hand_fracture"):
        r = one(by[k], "same_region")
        clear = r["lo"] > 0 or r["hi"] < 0
        again.append(("Every injury" if k == "all" else by[k]["name"],
                      f'{"+" if r["difference"] > 0 else "−"}{abs(100 * r["difference"]):.0f} points' + ("" if clear else ", no clear difference"),
                      r["them"], r["matched"]))
    ach = one(by["achilles"], "playing_3")
    return dict(career_followed=f'{careers["followed"]:,}', career_minutes=f'{abs(one(by["all"], "mpg")["effect"]):.1f}',
                career_achilles=(f'After a torn Achilles, {round(ach["them"] * ach["injuries"])} of {ach["injuries"]} were still in the league '
                                 f'three seasons on, against {pct(ach["matched"], 0)} of players like them.'),
                career_again=bar_rows(again, pair=True))


def render_overview(d: dict) -> str:
    board, study = d["board"], d["study"]
    before = board["modes"]["before"]
    nights = dict((day, rows) for day, rows in before["nights"])
    opening = nights[OPENING_NIGHT]
    hurt = sum(r[6] for r in opening)
    check = board["check"]["before"]
    coverage = {r["metric"]: r["value"] for r in study["model"]["coverage"]}
    facts = {r["metric"]: r["value"] for r in study["causes"]["facts"]}
    moments, agree = study["moments"]["facts"], study["compare"]["agreement"]
    scores = {(r["question"], r["model"]): r for r in study["model"]["scores"]}
    main = scores[("pregame_g5", "full_gbm")]
    tabs, panels = kind_lists(study["causes"])
    today = date.today()
    top = check["top"]["rate"]
    values = dict(
        site_url=SITE_URL, repo_url=REPO_URL, author=AUTHOR, seasons=SEASONS, updated=f"{today:%B} {today.year}",
        portfolio_url=PORTFOLIO_URL, linkedin_url=LINKEDIN_URL,
        description=("A model that reads seven seasons of official NBA injury reports and ranks who is most likely to get "
                     "hurt next, checked against what happened in 2025-26, plus why players get hurt and what an injury does "
                     "to a career."),
        live_day=OPENING_NIGHT, live_date=day_label(OPENING_NIGHT), live_short=short_day(OPENING_NIGHT),
        live_rows=board_rows(opening), live_sum=f"{hurt} of these {len(opening)} had a new injury within 5 games.",
        live_count=str(len(before["nights"])),
        ratio=f"{top / check['bottom']['rate']:.1f}", top_rate=pct(top), all_rate=pct(check["all"]["rate"]),
        bottom_rate=pct(check["bottom"]["rate"]), top_label=esc(check["top"]["label"]), bottom_label=esc(check["bottom"]["label"]),
        top_w="100", all_w=f"{100 * check['all']['rate'] / top:.1f}", bottom_w=f"{100 * check['bottom']['rate'] / top:.1f}",
        vs_all=f"{top / check['all']['rate']:.1f}",
        auc=f"{main['auc']:.2f}", auc_lo=f"{main['auc_lo']:.2f}", auc_hi=f"{main['auc_hi']:.2f}", top10=f"{main['top10_lift']:.1f}",
        test_rows=f"{main['rows']:,}",
        reports=f"{coverage['report_days']:,.0f}", lines=f"{coverage['report_rows']:,.0f}", matched=pct(coverage["matched_share"]),
        injuries=f"{facts['injuries']:,.0f}", player_games=f"{facts['player_games']:,.0f}",
        nba_injuries=f"{moments['nba_injuries']:,.0f}", nba_traced=f"{moments['nba_traced']:,.0f}",
        nba_one_in=f"1 in {round(1 / moments['nba_traced_share'])}",
        college_same=f"{moments['college_same_direction']:.0f} of {moments['college_tests']:.0f}",
        college_passed=f"{moments['college_passed']:.0f}", college_traced=f"{moments['college_traced']:,.0f}",
        pooled=f"{moments['college_pooled_times']:.1f}",
        agree_clear=str(agree["nba_clear"]), agree_same=str(agree["nba_clear_same"]),
        carry_ratio=f"{study['carry']['well_saved']['ratio']:.1f}",
        kind_tabs=tabs, kind_panels=panels, **news_values(study), **career_values(d["careers"]))
    return Template((SITE / "overview.html").read_text(encoding="utf-8")).substitute(values)


CARD = (1452, 760)   # the link preview's window, the hero's full height; at 2x it is 2904x1520, LinkedIn's 1.91:1


def social_card(log=print) -> Path | None:
    """The link preview for the overview and the dashboards: the overview's first screen (opening night's board), at 2x
    with headless Chrome, with motion off so every part is in its final place."""
    from .linkedin import _chrome
    try:
        chrome = _chrome()
    except RuntimeError as e:
        log({"card": f"skipped: {e}"})
        return None
    from PIL import Image   # installed with pdfplumber
    jpg = DOCS / "assets" / "social-site.jpg"

    class Quiet(SimpleHTTPRequestHandler):
        protocol_version = "HTTP/1.1"   # keep-alive: the HTTP/1.0 default drops connections under Chrome's parallel requests

        def log_message(self, *args):   # noqa: D401 - keep the build log clean
            pass

    # served over http, as on GitHub Pages, so the page's script can load its data
    server = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(DOCS)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with tempfile.TemporaryDirectory() as tmp:
            png = Path(tmp) / "card.png"
            subprocess.run([chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run", "--no-default-browser-check",
                            f"--user-data-dir={Path(tmp) / 'profile'}", f"--window-size={CARD[0]},{CARD[1]}", "--force-device-scale-factor=2",
                            "--force-prefers-reduced-motion", "--virtual-time-budget=20000", f"--screenshot={png}",
                            f"http://127.0.0.1:{server.server_address[1]}/index.html"], check=True, timeout=180, capture_output=True)
            if not png.exists():
                raise RuntimeError("Chrome did not write the link preview")
            Image.open(png).convert("RGB").save(jpg, quality=84, optimize=True, progressive=True)   # as JPEG: a third of the PNG
    finally:
        server.shutdown()
    log({"card": "docs/assets/social-site.jpg", "bytes": jpg.stat().st_size})
    return jpg


def build(log=print, card: bool = True) -> None:
    if (OUTPUTS / "dashboard" / "board.json").exists():
        write_data(log)
    else:
        log({"data": "outputs/dashboard is missing; keeping the published docs/data"})
    (DOCS / "assets").mkdir(parents=True, exist_ok=True)
    for name in ASSETS:
        shutil.copyfile(SITE / name, DOCS / "assets" / name)
    shutil.copyfile(SITE / "dashboard.html", DOCS / "dashboard.html")
    page = render_overview(load())
    (DOCS / "index.html").write_text(page, encoding="utf-8")
    log({"page": "docs/index.html", "bytes": len(page.encode())})
    report_site.build(log)
    if card:
        social_card(log)
