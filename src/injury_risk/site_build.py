"""The public site in docs/, for GitHub Pages.

- docs/data/*.json: what the pages read. board.json and players.json hold the 2025-26 risk board and each player's risk
  game by game, with NBA players by name (the league's injury reports are public); study.json holds the summary tables
  of the model check, the risk factors and the injury types. Nothing names a college player.
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
import shutil
import subprocess
import tempfile
import threading
from collections import Counter, defaultdict
from datetime import date
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from string import Template

from .paths import OUTPUTS
from .report_site import AUTHOR, DOCS, REPO_URL, SEASONS, SITE, SITE_URL
from . import report_site

DATA = DOCS / "data"
ASSETS = ("site.css", "app.css", "charts.js", "site.js", "overview.js", "dashboard.js")
MODES = {"before": dict(label="Before tip-off", question="a new injury in the next 5 games", short="next 5 games",
                        none="No new injury in the next 5 games"),
         "after": dict(label="After the game", question="missing the next game with a new injury", short="next game",
                       none="No new injury next game")}
OPENING_NIGHT = "2025-10-21"
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
    moments = {n: _read("moments_dashboard", n) for n in ("facts", "nba_patterns")}
    return _round(dict(
        model=dict(scores=_read("dashboard", "model_scores"), seasons=_read("dashboard", "season_scores"),
                   calibration=_read("dashboard", "calibration"), drivers=_read("dashboard", "drivers"),
                   coverage=_read("dashboard", "coverage")),
        factors=dict(risk=_read("dashboard", "risk_factors"), early=_read("dashboard", "early_exits"),
                     trend=_read("dashboard", "injury_trend"), mix=_read("dashboard", "injury_mix"),
                     prone=_read("dashboard", "prone_players")),
        causes={n: _read("causes", n) for n in ("facts", "groups", "months", "situations", "traits")},
        moments=dict(facts={r["metric"]: r["value"] for r in moments["facts"] if not r["metric"].startswith("college")},
                     patterns=moments["nba_patterns"])))


def write_data(log=print) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    board = board_data()
    for name, obj in (("board", board), ("players", players_data(board)), ("study", study_data())):
        text = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
        (DATA / f"{name}.json").write_text(text, encoding="utf-8")
        log({"data": f"docs/data/{name}.json", "bytes": len(text.encode())})


def load() -> dict:
    return {n: json.loads((DATA / f"{n}.json").read_text(encoding="utf-8")) for n in ("board", "players", "study")}


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


def outcome_cells(row: list, mode: dict) -> str:
    """The 'what happened' cell: the injury report's words, split into the injury and the games it cost."""
    if not row[6]:
        return '<td class="outcome none">No new injury</td>'
    injury, _, cost = row[7].partition(" (")
    cost = cost.rstrip(")")
    return (f'<td class="outcome hurt"><span class="dot" aria-hidden="true"></span><span class="what">{esc(injury)}'
            f'<span class="sub">{esc(cost)}</span></span></td>')


def board_rows(night: list, mode: dict, limit: int = LIVE_ROWS) -> str:
    out = []
    for rank, row in enumerate(night[:limit], start=1):
        out.append(f'<tr><td class="n rank">{rank}</td><td class="who"><b>{esc(row[1])}</b>'
                   f'<span class="sub">{esc(row[2])} vs {esc(row[3])}</span></td>'
                   f'<td class="n chance">{row[4] / 10:.0f}%</td>{outcome_cells(row, mode)}</tr>')
    return "".join(out)


KINDS = [("any", "Any injury"), ("muscle", "Pulled muscles"), ("sprain", "Sprained ankles"), ("contact", "Knocks"),
         ("knee", "Knees"), ("back", "Backs"), ("other", "Other aches")]
BANDS = 6   # findings shown per kind on the overview


def finding_bands(causes: dict) -> tuple[str, str]:
    """The overview's list: one tab per kind of injury, and its strongest findings that held in both halves."""
    rows = causes["situations"] + causes["traits"]
    groups = {g["group"]: g for g in causes["groups"]}
    total = causes["facts"]
    injuries = next(f["value"] for f in total if f["metric"] == "injuries")
    tabs, panels = [], []
    for i, (key, short) in enumerate(KINDS):
        found = sorted((r for r in rows if r["group"] == key and r["headline"]), key=lambda r: -abs(r["ratio"] - 1))[:BANDS]
        count = groups[key]["injuries"] if key in groups else injuries
        state = ' aria-selected="true"' if i == 0 else ' aria-selected="false" tabindex="-1"'
        tabs.append(f'<button type="button" role="tab" id="kind-{key}" aria-controls="panel-{key}"{state}>'
                    f'<b>{esc(short)}</b><span>{count:,.0f} injuries</span></button>')
        bands = []
        for r in found:
            up = r["ratio"] >= 1
            versus = r.get("versus") or "everyone else"
            bands.append(f'<li class="band {"up" if up else "down"}"><span class="figure num">{times_text(r["ratio"])}</span>'
                         f'<span class="what"><b>{esc(r["label"])}</b><span class="note">compared with {esc(versus)}</span></span>'
                         f'<span class="verdict">{esc(r["verdict"])}</span></li>')
        g = groups.get(key)
        if g:
            side = (f'<p class="side-figure num">{g["games_lost_per_team_season"]:.0f}</p>'
                    f'<p class="side-note">games a team loses to {esc(g["name"].lower())} each season. '
                    f'{round(100 * g["share_5plus"])}% of them kept the player out five games or more, and '
                    f'{round(100 * g["repeat_share"])}% hit the same body part again within a year.</p>')
        else:
            lost = next(f["value"] for f in total if f["metric"] == "games_lost_per_team_season")
            side = (f'<p class="side-figure num">{lost:.0f}</p><p class="side-note">games a team loses to new injuries each '
                    f'season, about {next(f["value"] for f in total if f["metric"] == "injuries_per_team_season"):.0f} '
                    f'injuries. These are the findings that held in both halves of the seasons.</p>')
        hidden = "" if i == 0 else " hidden"
        panels.append(f'<div class="kind-panel" role="tabpanel" id="panel-{key}" aria-labelledby="kind-{key}"{hidden}>'
                      f'<div class="kind-side">{side}</div><ol class="bands">{"".join(bands)}</ol></div>')
    return "".join(tabs), "".join(panels)


def render_overview(d: dict) -> str:
    board, study = d["board"], d["study"]
    before = board["modes"]["before"]
    nights = dict((day, rows) for day, rows in before["nights"])
    opening = nights[OPENING_NIGHT]
    hurt = sum(r[6] for r in opening)
    check = board["check"]["before"]
    coverage = {r["metric"]: r["value"] for r in study["model"]["coverage"]}
    facts = {r["metric"]: r["value"] for r in study["causes"]["facts"]}
    scores = {(r["question"], r["model"]): r for r in study["model"]["scores"]}
    main = scores[("pregame_g5", "full_gbm")]
    tabs, panels = finding_bands(study["causes"])
    today = date.today()
    credits = json.loads((DOCS / "assets" / "img" / "credits.json").read_text(encoding="utf-8"))
    credit_html = "; ".join(
        f'<a href="{esc(c["page"])}">“{esc(c["title"])}”</a> by {esc(c["creator"])}, '
        f'<a href="{esc(c["licenseUrl"])}">{esc(c["license"])}</a>' for c in credits)
    values = dict(
        site_url=SITE_URL, repo_url=REPO_URL, author=AUTHOR, seasons=SEASONS, updated=f"{today:%B} {today.year}",
        description=(f"A model that reads seven seasons of official NBA injury reports and ranks who is most likely to get "
                     f"hurt next, checked against what happened in 2025-26, plus why and when players get hurt."),
        live_day=OPENING_NIGHT, live_date=day_label(OPENING_NIGHT), live_short=short_day(OPENING_NIGHT), live_rows=board_rows(opening, before),
        live_sum=f"{hurt} of these {len(opening)} had a new injury within 5 games.",
        live_count=str(len(before["nights"])),
        ratio=f"{check['top']['rate'] / check['bottom']['rate']:.1f}", top_rate=pct(check["top"]["rate"]),
        all_rate=pct(check["all"]["rate"]), bottom_rate=pct(check["bottom"]["rate"]),
        top_label=esc(check["top"]["label"]), bottom_label=esc(check["bottom"]["label"]),
        top_w=f"{100 * check['top']['rate'] / check['top']['rate']:.1f}", all_w=f"{100 * check['all']['rate'] / check['top']['rate']:.1f}",
        bottom_w=f"{100 * check['bottom']['rate'] / check['top']['rate']:.1f}",
        auc=f"{main['auc']:.2f}", top10=f"{main['top10_lift']:.1f}",
        reports=f"{coverage['report_days']:,.0f}", lines=f"{coverage['report_rows']:,.0f}", matched=pct(coverage["matched_share"]),
        injuries=f"{facts['injuries']:,.0f}", player_games=f"{facts['player_games']:,.0f}",
        out_per_night=f"{facts['players_out_per_game']:.1f}",
        kind_tabs=tabs, kind_panels=panels, credits=credit_html)
    return Template((SITE / "overview.html").read_text(encoding="utf-8")).substitute(values)


CARD = (1336, 700)   # the link preview's window; at 2x it is 2672x1400, LinkedIn's 1.91:1


def social_card(log=print) -> Path | None:
    """The link preview for the overview and the dashboards: the overview's first screen (opening night's board) in the
    light theme, at 2x with headless Chrome."""
    from .linkedin import _chrome
    try:
        chrome = _chrome()
    except RuntimeError as e:
        log({"card": f"skipped: {e}"})
        return None
    from PIL import Image, ImageStat   # installed with pdfplumber
    jpg = DOCS / "assets" / "social-site.jpg"

    class Quiet(SimpleHTTPRequestHandler):
        protocol_version = "HTTP/1.1"   # keep-alive: the HTTP/1.0 default drops connections under Chrome's parallel requests

        def log_message(self, *args):   # noqa: D401 - keep the build log clean
            pass

    def photo_drawn(png: Path) -> bool:
        """The arena photograph fills the bottom-left tile; a failed load leaves a flat tile with its alt text."""
        im = Image.open(png).convert("L")
        w, h = im.size
        tile = im.crop((int(w * 0.06), int(h * 0.72), int(w * 0.46), int(h * 0.92)))
        return ImageStat.Stat(tile).stddev[0] > 25

    # served over http, as on GitHub Pages, so the page's script can load its data
    server = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(DOCS)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        for attempt in range(3):
            with tempfile.TemporaryDirectory() as tmp:
                png = Path(tmp) / "card.png"
                subprocess.run([chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run", "--no-default-browser-check",
                                f"--user-data-dir={Path(tmp) / 'profile'}", f"--window-size={CARD[0]},{CARD[1]}", "--force-device-scale-factor=2",
                                "--blink-settings=preferredColorScheme=1", "--virtual-time-budget=20000", f"--screenshot={png}",
                                f"http://127.0.0.1:{server.server_address[1]}/index.html"], check=True, timeout=180, capture_output=True)
                if not png.exists():
                    raise RuntimeError("Chrome did not write the link preview")
                if photo_drawn(png):
                    # a photograph: as JPEG it is a third of the PNG
                    Image.open(png).convert("RGB").save(jpg, quality=84, optimize=True, progressive=True)
                    break
        else:
            raise RuntimeError("the link preview's photograph did not load in three tries")
    finally:
        server.shutdown()
    log({"card": "docs/assets/social-site.jpg", "bytes": jpg.stat().st_size, "tries": attempt + 1})
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
