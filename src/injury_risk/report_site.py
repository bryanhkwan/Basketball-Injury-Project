"""The injury-moment report (docs/moments.html): one self-contained page of the public site, built from the
injury-moment results. Every number on it comes from outputs/moments_dashboard (written by moments_dashboard.py) and
the NBA and college summary.json files. The page's text, styles and chart code are in site/. The rest of the site is
built by site_build.py."""
from __future__ import annotations

import html
import json
from datetime import date
from pathlib import Path
from string import Template

from .paths import OUTPUTS, ROOT

SITE = Path(__file__).parent / "site"
DOCS = ROOT / "docs"
AUTHOR = "Bryan Kwan"
REPO_URL = "https://github.com/bryanhkwan/Basketball-Injury-Project"   # change both if the repository gets another name
SITE_URL = "https://bryanhkwan.github.io/Basketball-Injury-Project/"
SEASONS = "2019-20 to 2025-26"
PAGE = "moments.html"
FOREST = (0.5, 40.0)   # the college chart's log scale

TAGS = {"solid": dict(cls="solid", icon="✓", text="Solid"),
        "lead": dict(cls="lead", icon="◐", text="A lead"),
        "not shown": dict(cls="not", icon="○", text="Not proven")}
SHORT = {"ankle:fouled": "Ankle injury, after being fouled", "any:steal": "Any injury, after a steal",
         "hand:opp_rim": "Hand or arm injury, after a rim attack", "muscle:drive": "Pulled muscle or Achilles, after a drive",
         "ankle:rebound": "Ankle injury, after a rebound"}
COLLEGE_SHORT = {"H1": "Ankle injury, after drawing a foul", "H2": "Any injury, after a steal",
                 "H3": "Hand or arm injury, after a rim attack",
                 "H4": "Pulled muscle or Achilles, after a drive or fast-break finish", "H5": "Ankle injury, after a rebound"}
WHEN = {15: "15 s", 30: "30 s", 60: "1 min", 120: "2 min"}
esc = html.escape


def pct(v: float | None, digits: int = 0) -> str:
    if v is None:
        return "—"
    if 0 < v < 0.0005:
        return "<0.1%"
    return f"{100 * v:.{digits}f}%"


def times(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{v:.0f}×" if v >= 10 else f"{v:.1f}×"


def one_in(share: float) -> str:
    return f"1 in {round(1 / share)}"


def share_ratio(r: dict) -> float | None:
    return r["injury_share"] / r["normal_share"] if r.get("normal_share") else None


def odds(r: dict, key: str = "times") -> str:
    return f"{r[key]:.1f} ({r['lo']:.1f} to {r['hi']:.1f})"


def table(caption: str, head: list[str], rows: list[list[str]], numeric: set[int]) -> str:
    cls = lambda i: ' class="num"' if i in numeric else ""   # noqa: E731
    out = [f"<table><caption>{esc(caption)}</caption><thead><tr>"]
    out += [f'<th scope="col"{cls(i)}>{esc(h)}</th>' for i, h in enumerate(head)]
    out.append("</tr></thead><tbody>")
    for row in rows:
        out.append("<tr>" + "".join(f"<td{cls(i)}>{esc(c)}</td>" for i, c in enumerate(row)) + "</tr>")
    out.append("</tbody></table>")
    return "".join(out)


def _day(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d:%b} {d.day}, {d.year}"


def load() -> dict:
    d = {n: json.loads((OUTPUTS / "moments_dashboard" / f"{n}.json").read_text(encoding="utf-8"))
         for n in ("facts", "nba_patterns", "college_tests", "signs", "fade", "traced", "examples")}
    d["nba_summary"] = json.loads((OUTPUTS / "moments" / "summary.json").read_text(encoding="utf-8"))
    d["college_summary"] = json.loads((OUTPUTS / "college_moments" / "summary.json").read_text(encoding="utf-8"))
    d["covers_copies"] = next((r["value"] for r in d["facts"] if r["metric"] == "college_saved_pages"), None)
    return d


def render(d: dict) -> str:
    """The whole page as one HTML string, from the data load() returns."""
    facts = {r["metric"]: r["value"] for r in d["facts"]}
    patterns = sorted(d["nba_patterns"], key=lambda r: r["order"])
    by_key = {r["key"]: r for r in patterns}
    tests = sorted(d["college_tests"], key=lambda r: r["order"])
    signs = {r["key"]: r for r in d["signs"]}
    nba_s, col_s = d["nba_summary"], d["college_summary"]
    holm = {x["hypothesis"]: x.get("holm_p") for x in col_s["primary"]}
    added = col_s["added_after_results"]
    first, last = nba_s["settings"]["seasons"]
    n_seasons = last - first + 1
    n_tests = sum(1 for r in nba_s["table"] if r["play"] != "no_play")
    solid = [r for r in patterns if r["verdict"] == "solid"]
    # injury exits the solid patterns account for beyond chance: exits with the play x (1 - 1 / odds ratio)
    attributable = sum(r["with_play"] * (1 - 1 / r["times"]) for r in solid)
    passed = [t for t in tests if t["verdict"] == "passed"]
    primaries = [t for t in tests if t["primary"]]

    # ---- chart data -----------------------------------------------------------------------------------------
    nba_rows = []
    for r in patterns:
        ratio = share_ratio(r)
        nba_rows.append(dict(
            key=r["key"], label=r["label"], tag=TAGS[r["verdict"]], ratio=ratio,
            bars=[dict(name="Injury exits", value=r["injury_share"], text=pct(r["injury_share"], 1), series="nba"),
                  dict(name="Normal subs", value=r["normal_share"], text=pct(r["normal_share"], 1), series="normal")],
            tip=[["Injury exits with the play", f"{r['with_play']} of {r['injury_exits']:,}"],
                 ["Before injury exits", pct(r["injury_share"], 1)], ["Before normal substitutions", pct(r["normal_share"], 1)],
                 ["Odds ratio (likely range)", odds(r)]],
            aria=f"{r['label']}: {pct(r['injury_share'], 1)} of injury exits against {pct(r['normal_share'], 1)} of normal "
                 f"substitutions, {times(ratio)} as often. {TAGS[r['verdict']]['text']}."))

    fade_groups = []
    for key in [r["key"] for r in patterns if r["verdict"] in ("solid", "lead")]:
        points = [dict(when=WHEN[x["seconds"]], ratio=share_ratio(x), injury_share=x["injury_share"], normal_share=x["normal_share"],
                       odds=x["times"]) for x in sorted((x for x in d["fade"] if x["key"] == key), key=lambda x: x["seconds"])]
        fade_groups.append(dict(key=key, label=SHORT[key], points=points,
                                aria=f"{SHORT[key]}, times as often: " + ", ".join(f"{p['when']} {times(p['ratio'])}" for p in points)))

    college_rows = []
    for t in tests:
        n = by_key[t["nba_key"]]
        if t["verdict"] == "passed":
            tag = dict(cls="passed", icon="◐", text=f"Passed, on {t['with_play']} players")
        elif t["verdict"] == "same way":
            tag = dict(cls="same", icon="○", text="Same direction, not proven" if t["primary"] else "Same direction, side check")
        else:
            tag = dict(cls="not", icon="○", text="Did not hold")
        chance = "No bar set" if t["power_lo"] is None else f"{pct(t['power_lo'])} to {pct(t['power_hi'])}"
        college_rows.append(dict(
            key=t["key"], label=COLLEGE_SHORT[t["key"]], tag=tag,
            college={"or": t["times"], "lo": t["lo"], "hi": t["hi"]}, nba={"or": n["times"], "lo": n["lo"], "hi": n["hi"]},
            extra=[["College exits with the play", f"{t['with_play']} of {t['injury_exits']}"],
                   ["Chance of clearing the bar at the NBA's size", chance]],
            aria=f"{COLLEGE_SHORT[t['key']]}: college odds ratio {odds(t)}, NBA {odds(n)}. {tag['text']}."))

    sign_rows = []
    for s in sorted(d["signs"], key=lambda s: s["league"] != "NBA"):
        ratio = share_ratio(s)
        tip = [["Injury exits", pct(s["injury_share"], 1)], ["Normal substitutions", pct(s["normal_share"], 1)]]
        if s["times"] is not None:
            tip.append(["Odds ratio, same players", f"{s['times']:.1f}"])
        if s["no_injury_times"] is not None:
            tip.append(["Same, early exits with no injury after", f"{s['no_injury_times']:.1f}"])
        sign_rows.append(dict(
            key=s["key"], chip=s["league"], label=s["label"], ratio=ratio, tip=tip,
            bars=[dict(name="Injury exits", value=s["injury_share"], text=pct(s["injury_share"], 1),
                       series="nba" if s["league"] == "NBA" else "college"),
                  dict(name="Normal subs", value=s["normal_share"], text=pct(s["normal_share"], 1), series="normal")],
            aria=f"{s['league']}, {s['label']}: {pct(s['injury_share'], 1)} of injury exits against {pct(s['normal_share'], 1)} "
                 f"of normal substitutions."))

    traced = {(r["league"], r["group"]): r for r in d["traced"]}
    groups = sorted({r["group"] for r in d["traced"]}, key=lambda g: -traced.get(("NBA", g), {}).get("share", 0))
    traced_rows = []
    for g in groups:
        nb, co = traced.get(("NBA", g)), traced.get(("College", g))
        label = (nb or co)["label"]
        bars, tip = [], []
        for league, r, series in (("NBA", nb, "nba"), ("College", co, "college")):
            if r:
                bars.append(dict(name=league, value=r["share"], text=pct(r["share"]), series=series))
                tip.append([f"{league} injuries traced", f"{r['traced']:,} of {r['injuries']:,} ({pct(r['share'])})"])
        traced_rows.append(dict(key=g, label=label, bars=bars, tip=tip,
                                aria=f"{label}: " + ", ".join(f"{b['name']} {b['text']}" for b in bars) + " traced."))

    data = dict(nba=nba_rows, fade=fade_groups, college=college_rows, signs=sign_rows, traced=traced_rows,
                forest_domain=list(FOREST))

    # ---- tables (every chart's numbers, readable without the chart) -----------------------------------------
    table_nba = table(
        f"NBA, {SEASONS}: the 30 seconds before injury exits against the same players' normal substitutions.",
        ["Pattern", "Exits with the play", "Before injury exits", "Before normal subs", "Times as often", "Odds ratio (likely range)",
         "Verdict"],
        [[r["label"], f"{r['with_play']} of {r['injury_exits']:,}", pct(r["injury_share"], 1), pct(r["normal_share"], 1),
          times(share_ratio(r)), odds(r), r["verdict_label"]] for r in patterns], {1, 2, 3, 4, 5})
    table_fade = table(
        "NBA: the same comparison, looking back 15 seconds to 2 minutes before the exit.",
        ["Pattern", "Looking back", "Before injury exits", "Before normal subs", "Times as often", "Odds ratio"],
        [[g["label"], p["when"], pct(p["injury_share"], 1), pct(p["normal_share"], 1), times(p["ratio"]), f"{p['odds']:.1f}"]
         for g in fade_groups for p in g["points"]], {2, 3, 4, 5})
    table_college = table(
        "Division I men's basketball under the plan fixed in advance; the bar was a Holm-adjusted p below 0.05 for the four main checks.",
        ["Pattern", "College exits with the play", "College: injury exits vs normal subs", "College odds ratio (likely range)",
         "Holm-adjusted p", "NBA odds ratio (likely range)", "Chance of clearing the bar at the NBA's size", "Verdict"],
        [[COLLEGE_SHORT[t["key"]], f"{t['with_play']} of {t['injury_exits']}", f"{pct(t['injury_share'], 1)} vs {pct(t['normal_share'], 1)}",
          odds(t), f"{holm[t['key']]:.3f}" if holm.get(t["key"]) is not None else "No bar set", odds(by_key[t["nba_key"]]),
          r["extra"][1][1], r["tag"]["text"]] for t, r in zip(tests, college_rows)], {1, 3, 4, 5, 6})
    table_signs = table(
        "How injury exits differ from normal substitutions. The college signs were found after the plan.",
        ["League", "Sign", "Injury exits", "Normal substitutions", "Times as often", "Odds ratio"],
        [[s["league"], s["label"], pct(s["injury_share"], 1), pct(s["normal_share"], 1), times(share_ratio(s)),
          "—" if s["times"] is None else f"{s['times']:.1f}"] for s in sorted(d["signs"], key=lambda s: s["league"] != "NBA")],
        {2, 3, 4, 5})
    table_traced = table(
        "New injuries traced to an injury exit, by body part.",
        ["Kind of injury", "NBA traced", "NBA share", "College traced", "College share"],
        [[(traced.get(("NBA", g)) or traced[("College", g)])["label"]]
         + [v for league in ("NBA", "College") for v in (
             (f"{traced[(league, g)]['traced']:,} of {traced[(league, g)]['injuries']:,}", pct(traced[(league, g)]["share"]))
             if (league, g) in traced else ("—", "—"))] for g in groups], {1, 2, 3, 4})

    # college athletes stay anonymous on the public site: their results appear only as totals
    cards = "\n".join(
        f'      <article class="card"><span class="chip">{esc(e["league"])}</span><h3>{esc(e["player"])}</h3>'
        f'<p class="meta">{esc(e["team"])} {esc(e["game"])} · {_day(e["date"])} · {esc(e["injury"])}</p>'
        f'<p class="play">{esc(e["pattern"])}</p><p class="story">{esc(e["story"])}</p></article>'
        for e in d["examples"] if e["league"] == "NBA")

    today = date.today()
    values = dict(
        description=f"{one_in(facts['nba_traced_share'])} NBA injuries traced to the half-minute before the player left the game: the "
                    f"plays that come right before injuries, tested across {n_seasons} NBA seasons and checked in college basketball.",
        author=AUTHOR, site_url=SITE_URL, page_url=f"{SITE_URL}{PAGE}", repo_url=REPO_URL, seasons=SEASONS,
        updated=f"{today:%B} {today.year}",
        nba_injuries=f"{facts['nba_injuries']:,}", nba_traced=f"{facts['nba_traced']:,}", nba_one_in=one_in(facts["nba_traced_share"]),
        solid_count=str(len(solid)), college_same=f"{facts['college_same_direction']} of {facts['college_tests']}",
        before_injury=pct(facts["nba_pattern_before_injury"]), before_normal=pct(facts["nba_pattern_before_normal_game"]),
        beyond=pct(facts["nba_beyond_chance"]), chance_share=one_in(1 - facts["nba_beyond_chance"]), n_tests=f"{n_tests:,}",
        covers_copies=f"{d['covers_copies']} " if d["covers_copies"] else "", college_traced=f"{facts['college_traced']:,}",
        college_passed=f"{facts['college_passed']} of {len(primaries)}", h4_players=str(passed[0]["with_play"]) if passed else "—",
        pooled=times(facts["college_pooled_times"]), pooled_plain=f"{facts['college_pooled_times']:.1f}",
        pooled_range=f"{facts['college_pooled_lo']:.1f} to {facts['college_pooled_hi']:.1f}",
        pooled_without=times(added["pooled_without_h4"]["correlated"]["odds_ratio"]),
        unlogged_injury=pct(signs["college:unlogged"]["injury_share"]), unlogged_normal=pct(signs["college:unlogged"]["normal_share"]),
        timeout_injury=pct(signs["nba:own_timeout"]["injury_share"]), timeout_normal=pct(signs["nba:own_timeout"]["normal_share"]),
        ankle_ratio=times(share_ratio(by_key["ankle:fouled"])), steal_ratio=times(share_ratio(by_key["any:steal"])),
        hand_injury=pct(by_key["hand:opp_rim"]["injury_share"]), hand_normal=pct(by_key["hand:opp_rim"]["normal_share"]),
        attributable=f"{round(attributable, -1):.0f}", per_season=f"{attributable / n_seasons:.0f}",
        table_nba=table_nba, table_fade=table_fade, table_college=table_college, table_signs=table_signs, table_traced=table_traced,
        cards=cards, css=(SITE / "report.css").read_text(encoding="utf-8"), js=(SITE / "report.js").read_text(encoding="utf-8"),
        data=json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
    return Template((SITE / "report.html").read_text(encoding="utf-8")).substitute(values)


def build(log=print) -> Path:
    page = render(load())
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / "assets").mkdir(exist_ok=True)
    (DOCS / ".nojekyll").touch()   # GitHub Pages serves the files as they are
    out = DOCS / PAGE
    out.write_text(page, encoding="utf-8")
    log({"page": str(out), "bytes": len(page.encode())})
    return out
