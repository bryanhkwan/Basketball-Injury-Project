"""The report page's link preview (docs/assets/social-card.png, 2400x1260), drawn as HTML in the site's navy and gold
(site/cards.css) from the same files as the report page, and rendered with headless Chrome. `python -m injury_risk card`
redraws it."""
from __future__ import annotations

import html
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from .report_site import DOCS, SEASONS, SITE, SITE_URL, load, one_in, pct, share_ratio, times

CHROME = [os.environ.get("CHROME", ""), r"C:\Program Files\Google\Chrome\Application\chrome.exe",
          r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", "google-chrome", "chromium", "msedge"]
FONTS = ("https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@700;800"
         "&family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,600;9..40,700&display=block")
COURT = ('<svg class="court" viewBox="-10 -10 520 490" aria-hidden="true"><rect x="0" y="0" width="500" height="470"/>'
         '<rect x="170" y="0" width="160" height="190"/><circle cx="250" cy="190" r="60"/><line x1="220" y1="40" x2="280" y2="40"/>'
         '<circle cx="250" cy="52.5" r="7.5"/><path d="M210 52.5 A40 40 0 0 0 290 52.5"/>'
         '<path d="M30 0 V140 A237.5 237.5 0 0 0 470 140 V0"/><path d="M190 470 A60 60 0 0 1 310 470"/></svg>')
SOLID_LABEL = {"ankle:fouled": "Ankle injury, right after being fouled", "any:steal": "Any injury, right after a steal",
               "hand:opp_rim": "Hand or arm injury, after a rim attack"}
esc = html.escape


def _page(kicker: str, title: str, sub: str, body: str, credit: str, kind: str = "", css: str = "") -> str:
    """A card: the navy frame with its kicker, title, subtitle, ``body`` and footer, styled by site/cards.css and any
    extra ``css``."""
    link = SITE_URL.removeprefix("https://").rstrip("/")
    cls = f' class="{kind}"' if kind else ""
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><link rel="stylesheet" href="{FONTS}">'
            f'<style>{(SITE / "cards.css").read_text(encoding="utf-8")}{css}</style></head>'
            f'<body{cls}><div class="frame">{COURT}<p class="kicker">{kicker}</p>'
            f'<h1 class="title">{title}</h1><p class="sub">{sub}</p>{body}'
            f'<div class="footer"><p class="link"><b>FULL REPORT</b>{esc(link)}</p><p class="credit">{credit}</p></div>'
            f'</div></body></html>')


def _stats(d: dict) -> str:
    rows = {r["key"]: r for r in d["nba_patterns"]}
    cards = []
    for key, label in SOLID_LABEL.items():
        r = rows[key]
        cards.append(f'<div class="stat"><div class="num">{times(share_ratio(r))}</div><div class="as">as often</div>'
                     f'<div class="what">{esc(label)}</div><div class="detail">{pct(r["injury_share"], 1)} of injury exits vs '
                     f'{pct(r["normal_share"], 1)} of the same players’ normal substitutions</div>'
                     '<span class="verdict">✓ Held up in every check</span></div>')
    return f'<div class="stats">{"".join(cards)}</div>'


def social_card(d: dict) -> str:
    """The report page's link preview (1200x630): the three plays that held up."""
    facts = {r["metric"]: r["value"] for r in d["facts"]}
    return _page(
        f"NBA play-by-play · {SEASONS} · {facts['nba_injuries']:,} new injuries",
        "The moment players <em>get hurt</em>",
        f"<b>{one_in(facts['nba_traced_share'])}</b> NBA injuries can be traced to the half-minute before the player left the game "
        f"for good. Compared with the same players’ normal substitutions, three plays kept showing up there:",
        _stats(d), "Data: the NBA’s official injury reports; NBA play-by-play from the sportsdataverse releases.", kind="card")


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


def export(log=print) -> Path | None:
    """Draw the report's link preview into docs/assets/, or say why not when there is no Chrome or Edge."""
    try:
        png = render(social_card(load()), DOCS / "assets" / "social-card.png", 1200, 630)
    except RuntimeError as e:
        log({"card": f"skipped: {e}"})
        return None
    log({"card": str(png)})
    return png
