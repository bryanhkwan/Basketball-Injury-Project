"""What the news says about how NBA players got hurt, in numbers, for the dashboards (outputs/news/summary.json).

From the reviewed research (outputs/news/facts.jsonl): how much was found, what the vague listings turned out to be, and
how each kind of injury happened (contact or not, the mechanism, what the player was doing, where). The kinds are the
career study's diagnosis groups (aftermath.GROUPS), so both dashboards speak of the same injuries. Every count says
how many injuries it rests on: the news covers stars and severe injuries best, so the counts lean that way.
"""
from __future__ import annotations

import json
from collections import Counter

from . import aftermath, news, news_research
from .profiles import REGION_NAMES

OUT = news.OUT / "summary.json"
MECHANISMS = [("stepped_on_foot", "On someone’s foot"), ("landing", "Landing"), ("cutting_or_planting", "Cutting or planting"),
              ("collision", "Collision"), ("struck", "Hit by a player"), ("fall", "Fall"), ("overextension", "Bent too far"),
              ("overuse", "Overuse")]
PLAYS = [("drive", "Driving"), ("rebound", "Rebounding"), ("drew_foul", "Fouled"), ("transition", "In transition"),
         ("loose_ball", "Chasing a loose ball"), ("defending_the_rim", "Defending the rim"), ("screen", "A screen"),
         ("steal", "A steal"), ("jump_shot", "A jump shot"), ("other", "Something else")]
SETTINGS = [("game", "In a game"), ("practice", "In practice"), ("workout", "In a workout"), ("offseason", "In the offseason")]
SHOWN = 12   # vague-listing regions shown, by how many were named


def counts(values, keys) -> list:
    """[[key, count], ...] in the order of ``keys``, left out when none."""
    c = Counter(values)
    return [[k, c[k]] for k, _ in keys if c[k]]


def describe(rows: list[dict]) -> dict:
    """How a set of injuries happened, each count with the injuries it rests on."""
    def known(field, keys):
        values = [r[field] for r in rows if r[field] in dict(keys)]
        return dict(known=len(values), counts=counts(values, keys))
    contact = [r["contact"] for r in rows if r["contact"] in ("contact", "non_contact")]
    return dict(injuries=len(rows), contact=dict(known=len(contact), non_contact=contact.count("non_contact")),
                mechanisms=known("mechanism", MECHANISMS), plays=known("play", PLAYS), settings=known("setting", SETTINGS),
                surgery=sum(r["surgery"] is True for r in rows), season_ending=sum(r["season_ending"] is True for r in rows))


def summarize(facts: list[dict], targets: dict) -> dict:
    nba = [(f, targets[f["target"]]) for f in facts if f["target"] in targets and targets[f["target"]]["league"] == "nba"]
    found = [(f, t) for f, t in nba if f["status"] != "not_found"]
    rows = []
    for f, t in found:
        label = news._get(f, "diagnosis.label") if f["status"] in ("confirmed", "reported") else None
        rows.append(dict(group=aftermath.group_of(label, t["kind"], t["region"]), contact=f.get("contact"),
                         mechanism=f.get("mechanism"), play=news._get(f, "game.play"), setting=f.get("setting"),
                         surgery=news._get(f, "surgery.had"), season_ending=news._get(f, "expected.season_ending")))
    # the listings that named only a body part, and what the news called them
    vague = [(f, t) for f, t in nba if news.vague_listing(t)]
    by_region = {}
    for f, t in vague:
        r = by_region.setdefault(t["region"], dict(region=t["region"], name=REGION_NAMES.get(t["region"], t["region"]), listed=0,
                                                   named=0, labels=Counter()))
        r["listed"] += 1
        label = news._get(f, "diagnosis.label")
        if label not in (None, *news.GENERIC):
            r["named"] += 1
            r["labels"][label] += 1
    regions = sorted(by_region.values(), key=lambda r: (-r["named"], r["region"]))[:SHOWN]
    for r in regions:
        r["other"] = r["labels"].pop("Other", 0)
        r["labels"] = r["labels"].most_common()
    sources = [s for f, _ in nba for s in f.get("sources") or []]
    kinds = news.load_outlets()
    return dict(
        researched=len(nba), status=dict(Counter(f["status"] for f, _ in nba)),
        named=sum(f["status"] in ("confirmed", "reported") for f, _ in nba),
        vague=dict(listed=len(vague), named=sum(r["named"] for r in by_region.values()), regions=regions),
        game=sum(bool(news._get(f, "game.date")) for f, _ in found),
        timeline=sum(bool(news._get(f, "expected.weeks") or news._get(f, "expected.reevaluate_weeks")) for f, _ in found),
        all=describe(rows),
        groups=[dict(key=key, name=name, **describe([r for r in rows if r["group"] == key])) for key, name, *_ in aftermath.GROUPS],
        sources=dict(citations=len(sources), outlets=len({s["outlet"] for s in sources}),
                     kinds=dict(Counter(kinds.get(s["outlet"], "unknown") for s in sources).most_common())),
        labels=dict(mechanisms=dict(MECHANISMS), plays=dict(PLAYS), settings=dict(SETTINGS)))


def export(log=print) -> dict:
    out = summarize(news_research.read_jsonl(news.FACTS), {t["id"]: t for t in news_research.read_jsonl(news.TARGETS)})
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    log(f"  {out['researched']} NBA injuries researched, {out['named']} named; vague listings named "
        f"{out['vague']['named']} of {out['vague']['listed']}; contact known for {out['all']['contact']['known']}, "
        f"the mechanism for {out['all']['mechanisms']['known']}")
    return out
