"""The data behind the "The moment players get hurt" dashboard (outputs/moments_dashboard/*.json), from the NBA
injury-moment test (moments.py, outputs/moments) and the college test (college.py, outputs/college_moments)."""
from __future__ import annotations

import json

from .paths import OUTPUTS, RAW

OUT = OUTPUTS / "moments_dashboard"
GROUP_NAMES = {"any": "Any injury", "ankle": "Ankle", "ankle_sprain": "Ankle sprain", "knee": "Knee", "foot": "Foot and toe",
               "muscle": "Pulled muscle or Achilles", "back_hip": "Back and hip", "hand": "Hand, wrist, finger and arm",
               "head": "Head and face", "shoulder": "Shoulder", "contusion": "Knocks and bruises", "other": "Everything else"}

# the NBA plays that could be causes, in order: (group, play, plain label, verdict, what it means)
NBA_PATTERNS = [
    ("ankle", "fouled", "Ankle injury right after being fouled", "solid",
     "Fouled and sent to the line. The foul means contact on the play, such as a hard foul on a drive or a landing on a defender's foot, "
     "though the play-by-play can't say which. Holds up in every check, but only for ankles: for other injuries it doesn't survive the "
     "toughest check."),
    ("any", "steal", "Any injury right after a steal by the player", "solid",
     "Fits the sprint, finish or scramble after the steal. Holds up in every check, counting all kinds of injury together; most kinds "
     "lean the same way, though not head injuries."),
    ("hand", "opp_rim", "Hand, wrist, finger or arm injury after the other team attacked the rim", "solid",
     "The player was on defense for a layup, dunk or tip-in. Fits contesting or swiping at the ball, though the play-by-play doesn't say who "
     "contested it. Clear only for hand and arm injuries, and based on fewer cases."),
    ("muscle", "drive", "Pulled muscle or Achilles injury right after a drive or cut to the basket", "lead",
     "Fits injuries from pushing off and accelerating. Points the same way in every check, but only just clears the bar for the many plays "
     "we tested: worth checking on film."),
    ("ankle", "rebound", "Ankle injury right after a rebound", "not shown",
     "Landing from a rebound is a well-known cause of ankle sprains. Here it leans the same way but isn't proven: the play-by-play only "
     "credits the player who gets the rebound, not everyone who went up for it."),
]
VERDICTS = {"solid": "Solid", "lead": "A lead", "not shown": "Not proven"}
# NBA plays that come with an injury rather than cause one: (group, play, plain label, what it means)
NBA_SIGNS = [
    ("any", "take_foul", "Committed a take foul to stop play",
     "Not a cause: a hurt player commits a take foul to stop play and get off the floor."),
    ("any", "tov_handle", "Lost the ball or traveled",
     "Probably what the injury looks like: an ankle rolls or a muscle grabs mid-dribble and the ball goes. Early exits with no injury "
     "after them show it too, less often."),
]

COLLEGE_PLAIN = {
    "H1": ("Ankle injury right after drawing a foul",
           "Players tended to leave right at the whistle, mostly on fouls with no free throws, rather than after shooting their own free "
           "throws as most NBA players did. The NBA check could only count fouls with free throws, so the two sizes can't be compared "
           "directly."),
    "H2": ("Any injury right after a steal by the player",
           "Leans the same way as in the NBA, but weaker and not proven, though the check had a good chance of proving a link as strong as "
           "the NBA's."),
    "H3": ("Hand, wrist, finger or arm injury after the other team attacked the rim",
           "About as strong as in the NBA, but too few college cases to prove it. Read play by play, it was the least convincing of the five."),
    "H4": ("Pulled muscle or Achilles injury right after a drive or fast-break finish",
           "Passed the bar, but on three players, all on fast-break layups or dunks. Take away any one and it would not pass: treat it as a "
           "lead."),
    "H5": ("Ankle injury right after a rebound", "About as strong as in the NBA, but too few college cases to prove it."),
}
NBA_KEY = {"H1": "ankle:fouled", "H2": "any:steal", "H3": "hand:opp_rim", "H4": "muscle:drive", "H5": "ankle:rebound"}   # the NBA pattern each tests

# read from the raw play-by-play, 2 minutes before to 30 seconds after each exit; "reports say" marks what only news reports show
# (AP and NBC on Flagg; AP on Cale, whose game was a neutral-site tournament game in Fort Myers)
EXAMPLES = [
    dict(league="College", player="Jaylen Clark", team="UCLA", game="vs Arizona", date="2023-03-04", injury="Achilles (out for the season)",
         pattern="Steal, then a fast-break finish",
         story="Stole the ball and scored on the break. Arizona called timeout the same second, and Clark was the only player UCLA took out."),
    dict(league="College", player="Myles Cale", team="Seton Hall", game="vs Ohio State", date="2021-11-22", injury="Groin",
         pattern="Steal, then a fast-break finish",
         story="Stole the ball and scored on a fast-break layup to put Seton Hall up 24-19. Reports say Cale landed awkwardly and stayed "
               "down; play stopped seconds later when the arena lights went out, and Seton Hall took Cale and Bryce Aiken out."),
    dict(league="College", player="Cooper Flagg", team="Duke", game="vs Georgia Tech", date="2025-03-13", injury="Ankle sprain",
         pattern="Rebound",
         story="Went up for a defensive rebound and, reports say, came down on an opponent's foot. Called for traveling in the same second, "
               "Flagg was the only player Duke took out."),
    dict(league="College", player="Jayden Stone", team="Detroit Mercy", game="at Loyola Marymount", date="2023-12-18", injury="Ankle",
         pattern="Fouled",
         story="Drew a shooting foul and came out at that whistle, the only player Detroit Mercy took out. Teammate Tyree Davis, already on "
               "the floor, shot the free throws."),
    dict(league="NBA", player="Julius Randle", team="Knicks", game="vs Heat", date="2023-03-29", injury="Ankle sprain",
         pattern="Rebound, then fouled",
         story="Grabbed an offensive rebound and was fouled by Bam Adebayo. Randle stayed in through a Knicks timeout to shoot the free "
               "throws, then came out three seconds later when teammate Josh Hart fouled on purpose to stop play."),
    dict(league="NBA", player="Kevin Huerter", team="Kings", game="vs Grizzlies", date="2024-03-18", injury="Dislocated shoulder",
         pattern="Steal, then fouled",
         story="Stole the ball and was fouled on a shot by Desmond Bane. Huerter came out at a Kings timeout, and teammate Alex Len shot the "
               "free throws in Huerter's place."),
    dict(league="NBA", player="Jalen Johnson", team="Hawks", game="at Wizards", date="2023-11-25", injury="Broken wrist",
         pattern="Steal, then fouled",
         story="Stole the ball from Kyle Kuzma and was fouled by Kuzma on the shot. Johnson stayed in to shoot the free throws, then came out "
               "when teammate Onyeka Okongwu fouled on purpose to stop play."),
    dict(league="NBA", player="Luka Dončić", team="Mavericks", game="vs Timberwolves", date="2024-12-25", injury="Calf strain",
         pattern="No play of Dončić's own",
         story="Checked back in with 3:08 left in the second quarter and came out 37 seconds later at a Dallas timeout. No play in that "
               "stretch was credited to Dončić, so the play-by-play can't show the moment."),
]


def _row(rows: list[dict], **match) -> dict | None:
    return next((r for r in rows if all(r.get(k) == v for k, v in match.items())), None)


def _saved_pages() -> int | None:
    """How many saved copies of Covers' injury page the college test used. Counted from the downloads when they are
    here; otherwise the count already recorded is kept, so the report rebuilds the same from a fresh copy of the repo."""
    folder = RAW / "wayback" / "covers"
    if folder.exists():
        return sum(1 for f in folder.iterdir() if f.is_file())
    old = OUT / "facts.json"
    rows = json.loads(old.read_text(encoding="utf-8")) if old.exists() else []
    return next((r["value"] for r in rows if r["metric"] == "college_saved_pages"), None)


def export(log=print) -> dict:
    nba = json.loads((OUTPUTS / "moments" / "summary.json").read_text(encoding="utf-8"))
    col = json.loads((OUTPUTS / "college_moments" / "summary.json").read_text(encoding="utf-8"))
    out = {}

    g_nba = {g["group"]: g for g in nba["groups"]}
    g_col = {g["group"]: g for g in col["groups"]}
    bg_nba = {b["next"]: b for b in nba["background"]}
    bg_col = {b["next"]: b for b in col["quality"]["background"]}
    pooled = col["added_after_results"]["pooled"]["correlated"]
    same_way = sum(1 for x in col["primary"] + col["secondary"] if x["odds_ratio"] > 1)
    out["facts"] = [
        dict(metric="nba_injuries", value=g_nba["any"]["injuries"]),
        dict(metric="nba_traced", value=g_nba["any"]["pinned"]),
        dict(metric="nba_traced_share", value=g_nba["any"]["pinned_share"]),
        dict(metric="nba_beyond_chance", value=g_nba["any"]["beyond_chance"]),
        dict(metric="nba_pattern_before_injury", value=bg_nba["new injury"]["rate"]),
        dict(metric="nba_pattern_before_normal_game", value=bg_nba["played next game"]["rate"]),
        dict(metric="college_injuries_checkable", value=g_col["any"]["evaluable"]),
        dict(metric="college_traced", value=g_col["any"]["pinned"]),
        dict(metric="college_traced_share", value=g_col["any"]["pinned_share"]),
        dict(metric="college_pattern_before_injury", value=bg_col["new injury"]["rate"]),
        dict(metric="college_pattern_before_normal_game", value=bg_col["played next game"]["rate"]),
        dict(metric="college_tests", value=len(col["primary"]) + len(col["secondary"])),
        dict(metric="college_same_direction", value=same_way),
        dict(metric="college_passed", value=sum(1 for x in col["primary"] if x["verdict"] == "Replicates")),
        dict(metric="college_pooled_times", value=pooled["odds_ratio"]),
        dict(metric="college_pooled_lo", value=pooled["lo"]),
        dict(metric="college_pooled_hi", value=pooled["hi"]),
        dict(metric="college_saved_pages", value=_saved_pages()),
    ]

    rows = []
    for order, (g, play, label, verdict, explain) in enumerate(NBA_PATTERNS):
        x = _row(nba["table"], group=g, play=play)
        rows.append(dict(key=f"{g}:{play}", order=order, label=label, group=GROUP_NAMES[g], injury_share=x["case_share"],
                         normal_share=x["comparison_share"], times=x["odds_ratio"], lo=x["lo"], hi=x["hi"], q=x["q"], injury_exits=x["cases"],
                         with_play=x["exposed"], verdict=verdict, verdict_label=VERDICTS[verdict], explain=explain))
    out["nba_patterns"] = rows

    tests = []
    power = {p["hypothesis"]: p for p in col["added_after_results"]["power"]}
    versus = {v["hypothesis"]: v for v in col["added_after_results"]["versus_nba"]}
    for x in col["primary"] + col["secondary"]:
        hid = x["hypothesis"]
        label, explain = COLLEGE_PLAIN[hid]
        passed = x.get("verdict") == "Replicates"
        tests.append(dict(key=hid, order=int(hid[1:]), label=label, group=GROUP_NAMES[x["group"]], injury_share=x["case_share"],
                          normal_share=x["comparison_share"], times=x["odds_ratio"], lo=x["lo"], hi=x["hi"], injury_exits=x["cases"],
                          with_play=x["exposed"], primary=hid != "H5", verdict="passed" if passed else ("same way" if x["odds_ratio"] > 1 else "no"),
                          verdict_label=(f"Passed (on {x['exposed']} players)" if passed else "Same direction, not proven" if x["odds_ratio"] > 1
                                         else "Did not hold"),
                          nba_key=NBA_KEY[hid], nba_times=versus.get(hid, {}).get("nba"),
                          # the chance of clearing the plan's bar (Holm across H1-H4) at the NBA's odds ratio lies between these
                          power_lo=power.get(hid, {}).get("at_0.0125") if hid != "H5" else None,
                          power_hi=power.get(hid, {}).get("at_0.05") if hid != "H5" else None, explain=explain))
    out["college_tests"] = tests

    signs = []
    for key, label, explain in (("unlogged", "Left at a stop with no foul, timeout, turnover or violation logged",
                                 "Often the referees stopping play for a hurt player."),
                                ("lone_sub", "The only player the team took out", "Coaches often sub in groups; an injury takes one player out alone."),
                                ("replaced_at_line", "A teammate shot the free throws for a foul the player drew",
                                 "The player couldn't stay in to shoot them.")):
        x = _row(col["added_after_results"]["markers"], group="any", play=key, case_role="case")
        no_inj = _row(col["added_after_results"]["markers"], group="any", play=key, case_role="pseudo")
        signs.append(dict(key=f"college:{key}", league="College", label=label, injury_share=x["case_share"], normal_share=x["comparison_share"],
                          times=x["odds_ratio"], no_injury_times=no_inj["odds_ratio"] if no_inj else None, explain=explain))
    st = nba["stoppages"]
    signs.append(dict(key="nba:own_timeout", league="NBA", label="Left at the team's own timeout", injury_share=st["injury exits"].get("own timeout"),
                      normal_share=st["ordinary exits"].get("own timeout"), times=None, no_injury_times=None,
                      explain="Teams call timeout to get a hurt player off."))
    for g, play, label, explain in NBA_SIGNS:
        x = _row(nba["table"], group=g, play=play)
        signs.append(dict(key=f"nba:{play}", league="NBA", label=label, injury_share=x["case_share"], normal_share=x["comparison_share"],
                          times=x["odds_ratio"], no_injury_times=(_row(nba["no_injury_early_exits"], play=play) or {}).get("odds_ratio"),
                          explain=explain))
    out["signs"] = signs

    fade = []   # the same comparison looking back 15 seconds to 2 minutes
    for g, play, label, verdict, _ in NBA_PATTERNS:
        if verdict in ("solid", "lead"):
            for w in (15, 30, 60, 120):
                x = _row(nba["windows"], group=g, play=play, window=w)
                fade.append(dict(key=f"{g}:{play}", label=label, seconds=w, injury_share=x["case_share"], normal_share=x["comparison_share"],
                                 times=x["odds_ratio"]))
    out["fade"] = fade

    traced = []
    for league, groups in (("NBA", g_nba), ("College", g_col)):
        for gid in ("ankle", "knee", "foot", "muscle", "back_hip", "hand", "head", "shoulder"):
            g = groups.get(gid)
            if g:
                traced.append(dict(league=league, group=gid, label=GROUP_NAMES[gid], injuries=g.get("evaluable", g["injuries"]),
                                   traced=g["pinned"], share=g["pinned_share"]))
    out["traced"] = traced
    out["examples"] = [dict(e, key=f"{e['league']}:{e['player']}") for e in EXAMPLES]

    OUT.mkdir(parents=True, exist_ok=True)
    for name, rows in out.items():
        (OUT / f"{name}.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")
    log({k: len(v) for k, v in out.items()})
    return {k: len(v) for k, v in out.items()}
