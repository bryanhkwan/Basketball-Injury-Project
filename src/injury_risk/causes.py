"""Why players get hurt, by kind of injury: who is at risk, when, what it costs and how often it comes back.

Injuries are grouped the way a coach talks about them. "When" compares each player with himself in the
same month (Mantel-Haenszel odds ratio over player-month strata, with the Robins-Breslow-Greenland
interval), so traits that do not change within a month (fragility, size, age, role) and the calendar
(opening weeks, the All-Star break, the late-season rise) drop out; the late-season comparison itself uses
player-season strata. A finding is a headline only if its interval excludes 1 and it points the same way
in 2019-20 to 2021-22 and in 2022-23 to 2025-26. "Who"
compares players with one another (rate ratio, interval from resampling whole players). The outcome is
the next team game being the first one missed for a new injury of that kind, so it measures the risk that
a player gets hurt in a game. Seasons 2019-20 to 2025-26, the ones the official reports cover in full.
These are associations in observational data: the within-player design removes who the player is, not
everything else that comes with a situation.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from .paths import OUTPUTS, PROCESSED

SEASONS = (2020, 2026)
SPLIT_SEASON = 2022   # robustness: 2019-20 to 2021-22 against 2022-23 to 2025-26
OUT = OUTPUTS / "causes"
GROUPS = [   # id, name, what it covers
    ("muscle", "Pulled muscles", "Hamstring, calf, groin, thigh and Achilles strains and tightness"),
    ("sprain", "Sprained ankles and feet", "Rolled ankles and foot sprains"),
    ("contact", "Knocks and collisions", "Bruises, fractures, concussions, hand and finger injuries"),
    ("knee", "Knee problems", "Knee soreness, tendinitis and sprains"),
    ("back", "Back problems", "Back spasms, strains and soreness"),
    ("other", "Other aches and pains", "Sore ankles, feet, hips and shoulders, and the rest"),
]
ALL = ("any", "Any new injury", "Every new injury")


def group_of(region: str | None, kind: str | None) -> str:
    if region in {"hamstring", "calf", "groin", "achilles", "thigh"} and kind in {"muscle_tendon", "soreness", "other", "surgery"}:
        return "muscle"
    if region in {"hip", "trunk", "leg"} and kind == "muscle_tendon":
        return "muscle"
    if region in {"ankle", "foot"} and kind == "ligament":
        return "sprain"
    if kind in {"impact", "bone", "concussion"} or region in {"hand", "head_neck", "concussion"}:
        return "contact"
    if region == "knee":
        return "knee"
    if region == "back":
        return "back"
    return "other"


def verdict(ratio: float, lo: float, hi: float) -> tuple[str, int]:
    """Plain words for a ratio and its 95% interval; 'more likely' only when the interval excludes 1."""
    if not np.isfinite(ratio) or not np.isfinite(lo) or not np.isfinite(hi):
        return "Not enough data", 0
    if lo > 1:
        if ratio >= 1.7:
            return "Much more likely", 3
        if ratio >= 1.3:
            return "More likely", 2
        return "Slightly more likely", 1
    if hi < 1:
        return "Less likely", -1
    return "No clear difference", 0


def mantel_haenszel(strata: np.ndarray, exposed: np.ndarray, injured: np.ndarray) -> tuple[float, float, float]:
    """Odds ratio over strata (each player-season its own 2x2 table) with the RBG 95% interval."""
    df = pd.DataFrame({"s": strata, "e": exposed.astype(int), "y": injured.astype(int)})
    t = df.groupby(["s", "e", "y"]).size().unstack(["e", "y"], fill_value=0)
    for col in [(1, 1), (1, 0), (0, 1), (0, 0)]:
        if col not in t.columns:
            t[col] = 0
    a, b, c, d = (t[(1, 1)].to_numpy(float), t[(1, 0)].to_numpy(float), t[(0, 1)].to_numpy(float), t[(0, 0)].to_numpy(float))
    n = a + b + c + d
    keep = n > 1
    a, b, c, d, n = a[keep], b[keep], c[keep], d[keep], n[keep]
    R, S = a * d / n, b * c / n
    P, Q = (a + d) / n, (b + c) / n
    sR, sS = R.sum(), S.sum()
    if sR <= 0 or sS <= 0:
        return np.nan, np.nan, np.nan
    odds = sR / sS
    var = (P * R).sum() / (2 * sR ** 2) + (P * S + Q * R).sum() / (2 * sR * sS) + (Q * S).sum() / (2 * sS ** 2)
    se = np.sqrt(var)
    return odds, odds * np.exp(-1.96 * se), odds * np.exp(1.96 * se)


def rate_ratio_by_player(player: np.ndarray, exposed: np.ndarray, injured: np.ndarray, reps: int = 400, seed: int = 0):
    """Rate ratio (exposed vs not) with a 95% interval from resampling whole players."""
    df = pd.DataFrame({"p": player, "e": exposed.astype(int), "y": injured.astype(int)})
    g = df.groupby(["p", "e"])["y"].agg(["sum", "size"]).unstack("e", fill_value=0)
    a = g[("sum", 1)].to_numpy(float) if ("sum", 1) in g else np.zeros(len(g))
    n1 = g[("size", 1)].to_numpy(float) if ("size", 1) in g else np.zeros(len(g))
    c = g[("sum", 0)].to_numpy(float) if ("sum", 0) in g else np.zeros(len(g))
    n2 = g[("size", 0)].to_numpy(float) if ("size", 0) in g else np.zeros(len(g))
    if n1.sum() == 0 or n2.sum() == 0 or c.sum() == 0:
        return np.nan, np.nan, np.nan
    ratio = (a.sum() / n1.sum()) / (c.sum() / n2.sum())
    rng = np.random.default_rng(seed)
    w = rng.multinomial(len(a), np.full(len(a), 1 / len(a)), size=reps).astype(float)
    with np.errstate(divide="ignore", invalid="ignore"):
        boot = ((w @ a) / (w @ n1)) / ((w @ c) / (w @ n2))
    boot = boot[np.isfinite(boot)]
    return ratio, float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))


def next_game_group(rows: pd.DataFrame, onsets: pd.DataFrame, pg: pd.DataFrame) -> pd.Series:
    """For each game a player played: the group of a new injury whose first missed game is the team's next game."""
    o = onsets[onsets["new_injury"]]
    first_missed = {(int(p), g): grp for p, g, grp in zip(o["player_id"], o["onset_game_id"], o["group"])}
    nxt = {}
    for pid, d in pg.sort_values(["player_id", "game_date"]).groupby("player_id", sort=False):
        ids = d["game_id"].to_numpy()
        for a, b in zip(ids[:-1], ids[1:]):
            nxt[(pid, a)] = b
    return pd.Series([first_missed.get((pid, nxt.get((pid, gid)))) for pid, gid in zip(rows["player_id"], rows["game_id"])],
                     index=rows.index)


def situations(d: pd.DataFrame) -> list[tuple]:
    """(id, plain label, exposed mask, comparison mask, what it is compared with)."""
    # Situations that only arise after an injury (first games back, playing through a listing) are left out
    # here: inside a player-month they always follow the injury, so the comparison would be rigged. First games
    # back are compared separately below. The 7-day vs 28-day minutes ratio is left out as well: its swings
    # mostly mark season openers, breaks and absences for other reasons, and gave results no one could act on.
    reg = d["season_type"] == "regular-season"
    above = d["min_prev1"] - d["season_min_avg"]
    known = d["season_games"] >= 5
    return [
        ("b2b", "Second night of a back-to-back", d["b2b"] == 1, d["rest_days"] >= 2, "games with a day or more of rest"),
        ("three_in_four", "Third game in four nights", d["games_4d"] >= 3, d["games_4d"] <= 2, "other games"),
        ("heavy_last_game", "Played far more minutes than usual last game", known & (above >= 8), known & (above.abs() < 8), "a usual last game"),
        ("short_last_game", "Played far fewer minutes than usual last game", known & (above <= -8), known & (above.abs() < 8), "a usual last game"),
        ("long_trip", "Flew 1,000+ miles to the game", d["travel_km"] >= 1609, d["travel_km"] < 1609, "shorter or no trips"),
        ("time_zones", "Crossed two or more time zones", d["tz_shift"] >= 2, d["tz_shift"] == 0, "no time-zone change"),
        ("altitude", "Playing at altitude (Denver, Utah)", d["alt_ft"] >= 4000, d["alt_ft"] < 4000, "other arenas"),
        ("long_stints", "Long stretches on the floor lately (10+ minutes)", d["stint_long_avg5"] >= 10, d["stint_long_avg5"] < 10, "shorter stretches"),
        ("overtime", "Played overtime in the last two weeks", d["ot_min_14d"] > 0, d["ot_min_14d"] == 0, "no recent overtime"),
        ("rested", "Three or more days of rest before the game", d["rest_days"] >= 3, d["rest_days"].isin([1, 2]), "one or two days"),
        ("late_season", "Late in the regular season (game 60 on)", reg & (d["game_no"] >= 60), reg & (d["game_no"] <= 40), "the first 40 games"),
        ("away", "Away game", d["is_home"] == 0, d["is_home"] == 1, "home games"),
    ]


def traits(d: pd.DataFrame) -> list[tuple]:
    rim_q = d["rim36_10"].quantile(0.75)
    return [
        ("age30", "Age 30 or older", d["age"] >= 30, d["age"] < 30),
        ("injury_history", "Two or more injuries in the past year", d["inj_365"] >= 2, d["inj_365"] <= 1),
        ("heavy_role", "Plays 30+ minutes a game", d["min_avg10"] >= 30, d["min_avg10"] < 30),
        ("big", "Big men (6'10\" or taller)", d["height_in"] >= 82, d["height_in"] < 82),
        ("heavy", "Heavier players (250 lb or more)", d["weight_lb"] >= 250, d["weight_lb"] < 250),
        ("guard", "Guards", (d["pos_g"] == 1) & (d["pos_f"] == 0), ~((d["pos_g"] == 1) & (d["pos_f"] == 0))),
        ("rim", "Attacks the rim the most (top quarter)", d["rim36_10"] >= rim_q, d["rim36_10"] < rim_q),
        ("young", "First or second NBA season", d["exp"] <= 1, d["exp"] >= 2),
    ]


def analyse(log=print) -> dict[str, list[dict]]:
    rows = pd.read_parquet(PROCESSED / "rows.parquet")
    onsets = pd.read_parquet(PROCESSED / "onsets.parquet")
    pg = pd.read_parquet(PROCESSED / "player_games.parquet", columns=["player_id", "game_id", "game_date", "season", "absence", "team"])
    onsets["group"] = [group_of(r, k) for r, k in zip(onsets["region"], onsets["injury_type"])]
    d = rows[rows["season"].between(*SEASONS) & rows["obs_g1"]].copy()
    d["next_group"] = next_game_group(d, onsets, pg)
    # Compare each player with himself in the same month, so the calendar (opening weeks, the All-Star break, the
    # late-season rise) cannot pose as a situation's effect; the late-season comparison itself uses the whole season.
    d["stratum_season"] = d["player_id"].astype(str) + "-" + d["season"].astype(str)
    d["stratum"] = d["stratum_season"] + "-" + d["game_date"].dt.strftime("%Y%m")
    group_ids = [g[0] for g in GROUPS]
    for gid in group_ids:
        d[f"y_{gid}"] = (d["next_group"] == gid).astype(int)
    d["y_any"] = d["next_group"].notna().astype(int)
    log(f"player-games {len(d):,}; next-game new injuries {int(d['y_any'].sum()):,}")

    labels = dict((g[0], g[1]) for g in GROUPS) | {ALL[0]: ALL[1]}
    early = (d["season"] <= SPLIT_SEASON).to_numpy()   # the same comparison in each half of the seasons
    out_sit, out_trait = [], []
    for sid, label, exp_mask, ctl_mask, versus in situations(d):
        sel = (exp_mask | ctl_mask).fillna(False).to_numpy()
        e = exp_mask.fillna(False).to_numpy()[sel]
        sub = d[sel]
        half = early[sel]
        for gid in group_ids + ["any"]:
            y = sub[f"y_{gid}"].to_numpy()
            strata = sub["stratum_season" if sid == "late_season" else "stratum"].to_numpy()
            odds, lo, hi = mantel_haenszel(strata, e, y)
            first, _, _ = mantel_haenszel(strata[half], e[half], y[half])
            second, _, _ = mantel_haenszel(strata[~half], e[~half], y[~half])
            words, level = verdict(odds, lo, hi)
            holds = bool(np.isfinite(first) and np.isfinite(second) and np.sign(first - 1) == np.sign(second - 1) == np.sign(odds - 1))
            n_e, n_c = int(e.sum()), int((~e).sum())
            r_e = y[e].mean() if n_e else np.nan
            r_c = y[~e].mean() if n_c else np.nan
            out_sit.append(dict(situation=sid, label=label, versus=versus, group=gid, group_name=labels[gid],
                                ratio=odds, lo=lo, hi=hi, verdict=words, level=level, ratio_2019_22=first, ratio_2022_26=second,
                                holds_in_both_halves=holds, headline=bool(level != 0 and holds),
                                games_exposed=n_e, games_compared=n_c,
                                injuries_exposed=int(y[e].sum()), injuries_compared=int(y[~e].sum()),
                                one_in_exposed=(1 / r_e) if r_e else None, one_in_compared=(1 / r_c) if r_c else None))
    # First games back: the injury rate per game in games 1-3 after a return against games 4-10 after returns,
    # a per-game comparison over the same returns (no stratum where the return follows the outcome).
    back = d[d["games_since_return"].between(0, 9)]
    e = (back["games_since_return"] <= 2).to_numpy()
    half = early[d["games_since_return"].between(0, 9).to_numpy()]
    for gid in group_ids + ["any"]:
        y = back[f"y_{gid}"].to_numpy()
        ratio, lo, hi = rate_ratio_by_player(back["player_id"].to_numpy(), e, y)
        parts = []
        for m in (half, ~half):
            ye, yc = y[m & e], y[m & ~e]
            parts.append((ye.mean() / yc.mean()) if len(ye) and len(yc) and yc.mean() > 0 else np.nan)
        words, level = verdict(ratio, lo, hi)
        holds = bool(np.isfinite(parts[0]) and np.isfinite(parts[1]) and np.sign(parts[0] - 1) == np.sign(parts[1] - 1) == np.sign(ratio - 1))
        r_e, r_c = y[e].mean(), y[~e].mean()
        out_sit.append(dict(situation="first_back", label="First three games back from an injury",
                            versus="games 4 to 10 after a return", group=gid, group_name=labels[gid], ratio=ratio, lo=lo, hi=hi,
                            verdict=words, level=level, ratio_2019_22=parts[0], ratio_2022_26=parts[1],
                            holds_in_both_halves=holds, headline=bool(level != 0 and holds),
                            games_exposed=int(e.sum()), games_compared=int((~e).sum()),
                            injuries_exposed=int(y[e].sum()), injuries_compared=int(y[~e].sum()),
                            one_in_exposed=(1 / r_e) if r_e else None, one_in_compared=(1 / r_c) if r_c else None))

    for tid, label, exp_mask, ctl_mask in traits(d):
        sel = (exp_mask | ctl_mask).fillna(False).to_numpy()
        e = exp_mask.fillna(False).to_numpy()[sel]
        sub = d[sel]
        half = early[sel]
        for gid in group_ids + ["any"]:
            y = sub[f"y_{gid}"].to_numpy()
            ratio, lo, hi = rate_ratio_by_player(sub["player_id"].to_numpy(), e, y)
            parts = []
            for m in (half, ~half):
                ye, yc = y[m & e], y[m & ~e]
                parts.append((ye.mean() / yc.mean()) if len(ye) and len(yc) and yc.mean() > 0 else np.nan)
            words, level = verdict(ratio, lo, hi)
            holds = bool(np.isfinite(parts[0]) and np.isfinite(parts[1]) and np.sign(parts[0] - 1) == np.sign(parts[1] - 1) == np.sign(ratio - 1))
            out_trait.append(dict(trait=tid, label=label, group=gid, group_name=labels[gid], ratio=ratio, lo=lo, hi=hi,
                                  verdict=words, level=level, ratio_2019_22=parts[0], ratio_2022_26=parts[1],
                                  holds_in_both_halves=holds, headline=bool(level != 0 and holds),
                                  games_exposed=int(e.sum()), games_compared=int((~e).sum()),
                                  injuries_exposed=int(y[e].sum()), injuries_compared=int(y[~e].sum())))

    # what each group costs, how often it comes back, when in the season
    o = onsets[onsets["new_injury"] & onsets["season"].between(*SEASONS)].sort_values("onset_date").copy()
    team_seasons = d.groupby("season")["team"].nunique().sum()
    prior = []
    for pid, x in o.groupby("player_id"):
        days = x["onset_date"].to_numpy()
        regions = x["region"].to_numpy()
        for i in range(len(x)):
            back = (days[i] - days[:i]) / np.timedelta64(1, "D")
            prior.append(bool(((back <= 365) & (regions[:i] == regions[i])).any()) if i else False)
    o["repeat_365"] = pd.Series(prior, index=o.sort_values(["player_id", "onset_date"]).index).reindex(o.index)
    groups = []
    for order, (gid, name, covers) in enumerate(GROUPS, 1):
        x = o[o["group"] == gid]
        groups.append(dict(group=gid, name=name, covers=covers, order=order, injuries=int(len(x)),
                           per_team_season=len(x) / team_seasons, games_lost_per_team_season=x["games_missed"].sum() / team_seasons,
                           median_games_missed=float(x["games_missed"].median()), share_5plus=float((x["games_missed"] >= 5).mean()),
                           repeat_share=float(x["repeat_365"].mean()), share_of_injuries=len(x) / len(o)))
    played = pg[(pg["absence"] == "played") & pg["season"].between(*SEASONS)].copy()
    played["month"] = played["game_date"].dt.month
    o["month"] = o["onset_date"].dt.month
    month_names = {10: "Oct", 11: "Nov", 12: "Dec", 1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr"}
    exposure = played[played["month"].isin(month_names)].groupby("month").size()
    months = []
    for gid in group_ids + ["any"]:
        x = o if gid == "any" else o[o["group"] == gid]
        counts = x[x["month"].isin(month_names)].groupby("month").size()
        for order, mth in enumerate([10, 11, 12, 1, 2, 3, 4], 1):
            months.append(dict(group=gid, group_name=labels[gid], month=month_names[mth], order=order,
                               per_1000=1000 * counts.get(mth, 0) / exposure[mth], injuries=int(counts.get(mth, 0))))
    team_games = len(played.drop_duplicates(["team", "game_id"]))
    facts = [
        dict(metric="players_out_per_game", label="Players per team out with a new injury on an average night",
             value=float(o["games_missed"].sum() / team_games)),
        dict(metric="injuries", label="New injuries studied", value=int(len(o))),
        dict(metric="seasons", label="Seasons", value=int(SEASONS[1] - SEASONS[0] + 1)),
        dict(metric="player_games", label="Player-games compared", value=int(len(d))),
        dict(metric="games_lost_per_team_season", label="Games lost to new injuries per team per season",
             value=float(o["games_missed"].sum() / team_seasons)),
        dict(metric="injuries_per_team_season", label="New injuries per team per season", value=float(len(o) / team_seasons)),
    ]
    return dict(groups=groups, situations=out_sit, traits=out_trait, months=months, facts=facts)


def export(log=print) -> dict[str, int]:
    tables = analyse(log)
    OUT.mkdir(parents=True, exist_ok=True)
    sizes = {}
    for name, rows in tables.items():
        clean = json.loads(pd.DataFrame(rows).to_json(orient="records", double_precision=4))
        (OUT / f"{name}.json").write_text(json.dumps(clean, separators=(",", ":")), encoding="utf-8")
        sizes[name] = len(clean)
    log(json.dumps(sizes))
    return sizes
