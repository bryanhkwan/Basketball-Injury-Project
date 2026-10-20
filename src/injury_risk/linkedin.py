"""Images for sharing the injury-moment project: three LinkedIn images (outputs/linkedin/0*.png, 2400x1350), a one-image
version (outputs/linkedin/single.png, 2160x2700) and the report page's link preview (docs/assets/social-card.png, 2400x1260). Each is drawn as HTML (site/linkedin.css) and rendered with
headless Chrome; the numbers come from the same files as the report page."""
from __future__ import annotations

import html
import math
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from .paths import OUTPUTS
from .report_site import DOCS, SEASONS, SITE, SITE_URL, load, one_in, pct, share_ratio, times

OUT = OUTPUTS / "linkedin"
FOREST = (0.5, 40.0)
CHROME = [os.environ.get("CHROME", ""), r"C:\Program Files\Google\Chrome\Application\chrome.exe",
          r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", "google-chrome", "chromium", "msedge"]
FONTS = ("https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@700;800"
         "&family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,600;9..40,700&display=block")
COURT = ('<svg class="court" viewBox="-10 -10 520 490" aria-hidden="true"><rect x="0" y="0" width="500" height="470"/>'
         '<rect x="170" y="0" width="160" height="190"/><circle cx="250" cy="190" r="60"/><line x1="220" y1="40" x2="280" y2="40"/>'
         '<circle cx="250" cy="52.5" r="7.5"/><path d="M210 52.5 A40 40 0 0 0 290 52.5"/>'
         '<path d="M30 0 V140 A237.5 237.5 0 0 0 470 140 V0"/><path d="M190 470 A60 60 0 0 1 310 470"/></svg>')
FOREST_LABEL = {"H1": "Ankle · after drawing a foul", "H2": "Any injury · after a steal", "H3": "Hand or arm · after a rim attack",
                "H4": "Muscle or Achilles · after a drive", "H5": "Ankle · after a rebound"}
SOLID_LABEL = {"ankle:fouled": "Ankle injury, right after being fouled", "any:steal": "Any injury, right after a steal",
               "hand:opp_rim": "Hand or arm injury, after a rim attack"}
esc = html.escape


def _page(kicker: str, title: str, sub: str, body: str, credit: str, kind: str = "") -> str:
    link = SITE_URL.removeprefix("https://").rstrip("/")
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><link rel="stylesheet" href="{FONTS}">'
            f'<style>{(SITE / "linkedin.css").read_text(encoding="utf-8")}</style></head>'
            f'<body{f" class={kind}" if kind else ""}><div class="frame">{COURT}<p class="kicker">{kicker}</p>'
            f'<h1 class="title">{title}</h1><p class="sub">{sub}</p>{body}'
            f'<div class="footer"><p class="link"><b>FULL REPORT</b>{esc(link)}</p><p class="credit">{credit}</p></div>'
            f'</div></body></html>')


def _stats(d: dict, chip: bool = True) -> str:
    rows = {r["key"]: r for r in d["nba_patterns"]}
    cards = []
    for key, label in SOLID_LABEL.items():
        r = rows[key]
        cards.append(f'<div class="stat"><div class="num">{times(share_ratio(r))}</div><div class="as">as often</div>'
                     f'<div class="what">{esc(label)}</div><div class="detail">{pct(r["injury_share"], 1)} of injury exits vs '
                     f'{pct(r["normal_share"], 1)} of the same players’ normal substitutions</div>'
                     + ('<span class="verdict">✓ Held up in every check</span>' if chip else "") + '</div>')
    return f'<div class="stats">{"".join(cards)}</div>'


def findings(d: dict, card: bool = False) -> str:
    facts = {r["metric"]: r["value"] for r in d["facts"]}
    how = ('<div class="how"><div class="how-step key"><b>The 30 seconds before</b><span>What was happening?</span></div>'
           '<div class="arrow">→</div><div class="how-step"><b>Leaves the game for good</b>'
           '<span>A competitive game, well under usual minutes</span></div><div class="arrow">→</div>'
           '<div class="how-step"><b>Misses the next game injured</b><span>A new injury on the official report</span></div></div>')
    return _page(
        f"NBA play-by-play · {SEASONS} · {facts['nba_injuries']:,} new injuries",
        "The moment players <em>get hurt</em>",
        f"<b>{one_in(facts['nba_traced_share'])}</b> NBA injuries can be traced to the half-minute before the player left the game "
        f"for good. Compared with the same players’ normal substitutions, three plays kept showing up there:",
        _stats(d) + ("" if card else how),
        "Data: the NBA’s official injury reports; NBA play-by-play from the sportsdataverse releases.", kind="card" if card else "")


def _panels(d: dict, labels: dict, cls: str = "pnl", room: float = 0.86) -> str:
    """Small multiples of how much more often each play came before injury exits, 15 seconds to 2 minutes back."""
    fade = [x for x in d["fade"] if x["key"] in labels]
    top = max(share_ratio(x) for x in fade) / room
    panels = []
    for key, label in labels.items():
        pts = sorted((x for x in fade if x["key"] == key), key=lambda x: x["seconds"])
        cols = "".join(f'<div class="col" style="height:{100 * share_ratio(x) / top:.2f}%"><span>{times(share_ratio(x))}</span></div>'
                       for x in pts)
        ticks = "".join(f"<span>{w}</span>" for w in ("15 s", "30 s", "1 min", "2 min"))
        panels.append(f'<div class="{cls}"><div class="pnl-title">{esc(label)}</div><div class="pnl-plot">{cols}'
                      f'<div class="ref-line" style="bottom:{100 / top:.2f}%"></div></div><div class="pnl-ticks">{ticks}</div></div>')
    return "".join(panels)


def timing(d: dict) -> str:
    legend = ('<div class="legend"><span><i class="sw" style="background:#3987e5"></i>Times as often as before a normal substitution'
              '</span><span><i class="sw-ref"></i>No difference</span></div>')
    return _page(
        f"NBA · {SEASONS} · looking back from the moment the player left",
        "It happens in the <em>last few seconds</em>",
        "The closer to the moment a player left, the stronger the link. Two minutes back it’s almost gone, which points to the "
        "play itself, not a long, tiring shift.",
        legend + f'<div class="panels">{_panels(d, SOLID_LABEL)}</div>',
        "Data: the NBA’s official injury reports; NBA play-by-play from the sportsdataverse releases.")


def _forest(d: dict) -> str:
    """NBA and college odds ratios with their likely ranges, one row per pattern, on a log scale."""
    nba = {r["key"]: r for r in d["nba_patterns"]}
    lo, hi = FOREST
    x = lambda v: 100 * (math.log(v) - math.log(lo)) / (math.log(hi) - math.log(lo))   # noqa: E731
    ticks = (0.5, 1, 2, 4, 8, 16, 32)

    def est(series: str, e: dict) -> str:
        a, b = x(max(e["lo"], lo)), x(min(e["hi"], hi))
        return (f'<div class="f-est {series}"><div class="f-whisker" style="left:{a:.2f}%;width:{b - a:.2f}%"></div>'
                f'<div class="f-dot" style="left:{x(e["times"]):.2f}%"></div></div>')

    rows = []
    for t in sorted(d["college_tests"], key=lambda t: t["order"]):
        verdict = (f'<small class="pass">◐ Passed, on {t["with_play"]} players</small>' if t["verdict"] == "passed"
                   else f'<small>○ Same direction{", side check" if not t["primary"] else ", not proven"}</small>')
        grid = "".join(f'<div class="{"f-ref" if tk == 1 else "f-grid"}" style="left:{x(tk):.2f}%"></div>' for tk in ticks)
        rows.append(f'<div class="f-row"><div class="f-label">{esc(FOREST_LABEL[t["key"]])}{verdict}</div>'
                    f'<div class="f-plot">{grid}{est("nba", nba[t["nba_key"]])}{est("college", t)}</div></div>')
    axis = "".join(f'<span class="f-tick" style="left:{x(tk):.2f}%">{tk:g}</span>' for tk in ticks)
    return (f'<div class="forest">{"".join(rows)}<div class="f-axis">{axis}<span class="f-axis-label">Odds ratio vs. the same players’ '
            f'normal subs, likely range, log scale</span></div></div>')


def _calls(d: dict) -> str:
    facts = {r["metric"]: r["value"] for r in d["facts"]}
    tests = d["college_tests"]
    passed = [t for t in tests if t["verdict"] == "passed"]
    primaries = [t for t in tests if t["primary"]]
    return (f'<div class="calls"><div class="call"><b>{facts["college_same_direction"]} of {facts["college_tests"]}</b>'
            f'<span>leaned the same way as in the NBA</span></div>'
            f'<div class="call"><b>{facts["college_passed"]} of {len(primaries)}</b><span>main checks cleared the bar I set in advance, '
            f'on just {passed[0]["with_play"] if passed else "—"} players</span></div>'
            f'<div class="call"><b>{times(facts["college_pooled_times"])}</b><span>the odds, all five combined (likely '
            f'{facts["college_pooled_lo"]:.1f} to {facts["college_pooled_hi"]:.1f}). Same direction, not yet proof.</span></div></div>')


COLLEGE_LEGEND = ('<div class="legend"><span><i class="sw dot" style="background:#3987e5"></i>NBA</span><span><i class="sw dot" '
                  'style="background:#c98500"></i>College</span><span><i class="sw-ref"></i>No difference</span></div>')


def college(d: dict) -> str:
    facts = {r["metric"]: r["value"] for r in d["facts"]}
    return _page(
        f"NCAA Division I men’s basketball · {facts['college_traced']:,} injury exits · plan written before the results",
        "Does it hold <em>in college?</em>",
        "Before seeing any college results, I wrote down five NBA patterns and the bar the main four had to clear, then checked "
        "them against seven seasons of Division I injury exits.",
        COLLEGE_LEGEND + f'<div class="college-grid">{_forest(d)}{_calls(d)}</div>',
        "Data: NCAA play-by-play (sportsdataverse); Covers injury pages (Wayback Machine).")


MINI_LABEL = {"ankle:fouled": "Ankle · after being fouled", "any:steal": "Any injury · after a steal",
              "hand:opp_rim": "Hand or arm · rim attack"}


def single(d: dict) -> str:
    """The whole story on one 4:5 image (1080x1350): the three plays, how the link fades, and the college chart."""
    facts = {r["metric"]: r["value"] for r in d["facts"]}
    body = (_stats(d, chip=False)
            + f'<div class="block"><h2 class="block-h">It happens in the <em>last few seconds</em></h2>'
              f'<p class="block-sub">Times as often as before a normal substitution, looking back from the moment the player left. '
              f'Dashed line: no difference.</p><div class="mini-panels">{_panels(d, MINI_LABEL, "mini-pnl", 0.8)}</div></div>'
            + f'<div class="block"><h2 class="block-h">Does it hold <em>in college?</em></h2>'
              f'<p class="block-sub">{facts["college_traced"]:,} Division I injury exits, tested against a plan written before any college '
              f'results.</p>{COLLEGE_LEGEND}<div class="college-grid">{_forest(d)}{_calls(d)}</div></div>')
    return _page(
        f"NBA play-by-play · {SEASONS} · {facts['nba_injuries']:,} new injuries",
        "The moment players <em>get hurt</em>",
        f"<b>{one_in(facts['nba_traced_share'])}</b> NBA injuries can be traced to the half-minute before the player left the game. "
        f"Against the same players’ normal substitutions, three plays held up in every check:",
        body, "Data: NBA injury reports and play-by-play; NCAA play-by-play (sportsdataverse); Covers via the Wayback Machine.",
        kind="tall")


def _chrome() -> str:
    for c in CHROME:
        if c and (Path(c).exists() or shutil.which(c)):
            return c
    raise RuntimeError("No Chrome or Edge found; set the CHROME environment variable to one.")


def render(page: str, png: Path, width: int, height: int) -> Path:
    """Screenshot an HTML page at 2x with headless Chrome (fonts load before the shot)."""
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "page.html"
        src.write_text(page, encoding="utf-8")
        png.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([_chrome(), "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
                        "--no-default-browser-check", f"--user-data-dir={Path(tmp) / 'profile'}", f"--window-size={width},{height}",
                        "--force-device-scale-factor=2", "--virtual-time-budget=20000", f"--screenshot={png}", src.as_uri()],
                       check=True, timeout=180, capture_output=True)
    return png


def export(log=print) -> dict:
    d = load()
    OUT.mkdir(parents=True, exist_ok=True)
    made = {
        "01-the-moment": render(findings(d), OUT / "01-the-moment.png", 1200, 675),
        "02-last-few-seconds": render(timing(d), OUT / "02-last-few-seconds.png", 1200, 675),
        "03-college": render(college(d), OUT / "03-college.png", 1200, 675),
        "single": render(single(d), OUT / "single.png", 1080, 1350),
        "social-card": render(findings(d, card=True), DOCS / "assets" / "social-card.png", 1200, 630),
    }
    for name, page in (("01-the-moment", findings(d)), ("02-last-few-seconds", timing(d)), ("03-college", college(d)),
                       ("single", single(d))):
        (OUT / f"{name}.html").write_text(page, encoding="utf-8")   # kept so an image can be tweaked and re-rendered
    log({k: str(v) for k, v in made.items()})
    return made
