"""Export the datasets the dashboard draws from (outputs/dashboard/*.json, one array of row objects each)."""
from __future__ import annotations

import json
import re

import numpy as np
import pandas as pd

from . import board, features, model as M
from .labels import LOWER_BODY  # noqa: F401  (kept for readers of this module)
from .paths import OUTPUTS, PROCESSED

OUT = OUTPUTS / "dashboard"
SEASON = 2026                       # the held-out season the boards and player timelines show
BOARD_SIZE = {"before": 12, "after": 10}

QUESTIONS = {
    "pregame_g5": ("results_g5.json", "New injury in the next 5 games, before tip-off"),
    "serious_g5": ("results_g5_3plus.json", "Injury costing 3+ games, in the next 5 games"),
    "pregame_y14": ("results_y14.json", "New injury in the next 14 days, before tip-off"),
    "aftergame_g1": ("results_g1_after_game.json", "Misses the next game, scored right after a game"),
}
MODELS = {
    "history_logistic": "Age + injury history",
    "full_logistic": "All features (logistic)",
    "full_gbm": "All features (boosted trees)",
    "full_gbm_plus_pbp": "+ play-by-play load",
    "full_gbm_plus_pregame_report": "+ that day's injury report",
    "after_game_gbm": "+ that game's play-by-play",
}
FEATURE_LABELS = {
    **board.LABELS,
    "min_prev1": "minutes last game", "min_avg10": "minutes per game (last 10)", "min_std10": "minutes swing (last 10)",
    "min_14d": "minutes last 14 days", "games_7d": "games last 7 days", "games_14d": "games last 14 days",
    "min_spike": "minutes last game vs season average", "season_games": "games this season",
    "prev_season_min": "minutes last season", "prev_season_games": "games last season", "days_since_played": "days since last game",
    "starter_rate10": "starts (last 10)", "oreb36": "offensive rebounds per 36", "pf36": "fouls per 36", "blk36": "blocks per 36",
    "stl36": "steals per 36", "ast36": "assists per 36", "games_4d": "team games in 4 days", "games_7d_team": "team games in 7 days",
    "travel_km": "km travelled to this game", "tz_shift": "time zones crossed", "alt_ft": "arena altitude (ft)",
    "prev_alt_ft": "last arena altitude (ft)", "is_home": "home game", "playoffs": "playoff game", "month": "month",
    "height_in": "height (in)", "bmi": "BMI", "exp": "years in the league", "pos_g": "guard", "pos_f": "forward", "pos_c": "center",
    "muscle_365": "muscle injuries (year)", "lower_365": "lower-body injuries (year)", "games_since_return": "games since returning",
    "pregame_listed": "on today's injury report", "pregame_questionable": "listed questionable today",
    "stint_long_prev1": "longest stint last game", "stint_long_avg5": "longest stint (last 5)", "stints_avg5": "stints per game (last 5)",
    "q4ot_avg5": "4th-quarter minutes (last 5)", "ot_min_14d": "overtime minutes (14 days)", "rim36_10": "rim attacks per 36",
    "dunk36_10": "dunks per 36", "trans36_10": "transition chances per 36", "pace48_10": "possessions per 48",
    "early_exit_prev1": "left a close game early last time", "early_exit_10": "early exits (last 10)",
    "early_exit_30d": "early exits (30 days)", "close_10": "close games (last 10)",
    "cur_last_on_min": "last on the floor (game minute)", "team_inj_rate_365": "team injuries per game (past year)",
}
board.LABELS.update(FEATURE_LABELS)   # the board's driver text uses the same names


def label(feature: str) -> str:
    text = FEATURE_LABELS.get(feature, feature.replace("_", " "))
    return text[:1].upper() + text[1:]


def reason_text(reason) -> str:
    """'Injury/Illness - Left Finger; Sprain Injury/Illness - Lower Left Leg; Contusion' -> 'Left finger sprain, lower left leg contusion'."""
    parts = []
    for part in re.split(r"Injury/Illness\s*-\s*", str(reason or "")):
        words = [w.strip() for w in part.split(";") if w.strip() and w.strip().upper() != "N/A"]
        if words:
            parts.append(" ".join(words).lower())
    text = re.sub(r"\s+", " ", ", ".join(parts)).strip()
    text = re.sub(r"\b(acl|mcl|lcl|pcl|ucl)\b", lambda m: m.group(1).upper(), text)
    return (text[:1].upper() + text[1:]) if text else "Injury"


def season_label(season: int) -> str:
    return f"{season - 1}-{str(season)[2:]}"


def write(name: str, rows: list[dict]) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    clean = json.loads(pd.DataFrame(rows).to_json(orient="records", double_precision=4))
    (OUT / f"{name}.json").write_text(json.dumps(clean, separators=(",", ":")), encoding="utf-8")
    return len(clean)


def model_tables() -> dict[str, list[dict]]:
    scores, seasons, calib, drivers = [], [], [], []
    for qid, (fname, qlabel) in QUESTIONS.items():
        r = json.loads((OUTPUTS / fname).read_text(encoding="utf-8"))
        for mid, entry in r["models"].items():
            if mid == "base_rate":
                continue
            t = entry["test"]
            ci = entry.get("auc_95") or [None, None]
            mlabel = "Before the game (same features)" if (qid == "aftergame_g1" and mid == "full_gbm") else MODELS.get(mid, mid)
            scores.append(dict(question=qid, question_label=qlabel, model=mid, model_label=mlabel, auc=t["auc"],
                               auc_lo=ci[0], auc_hi=ci[1], avg_precision=t["avg_precision"], brier_skill=t["brier_skill"],
                               top10_lift=t["top10_lift"], top10_capture=t["top10_capture"], rows=t["rows"],
                               positives=t["positives"], rate=t["rate"]))
        key = "after_game_gbm" if r.get("framing") == "after_game" else "full_gbm"
        best = r["models"][key]
        for s, sc in best["by_season"].items():
            seasons.append(dict(question=qid, model=key, season=season_label(int(s)), rows=sc["rows"], rate=sc["rate"],
                                auc=sc["auc"], top10_lift=sc["top10_lift"]))
        if qid in ("pregame_g5", "aftergame_g1"):
            calib += [dict(question=qid, model=key, decile=c["decile"], predicted=c["predicted"], observed=c["observed"],
                           rows=c["rows"]) for c in best["calibration"]]
            imp = r.get(f"importance_{key}") or []
            drivers += [dict(question=qid, rank=i + 1, feature=d["feature"], label=label(d["feature"]), auc_drop=d["auc_drop"])
                        for i, d in enumerate(imp[:12])]
    return dict(model_scores=scores, season_scores=seasons, calibration=calib, drivers=drivers)


def risk_factor_table(rows: pd.DataFrame) -> list[dict]:
    d = rows[rows["obs_g5"] & rows["season"].between(2020, 2026)]
    overall = d["g5"].mean()
    specs = [
        ("games_since_return", "Games since returning from an injury",
         pd.cut(d["games_since_return"].fillna(999), [-1, 2, 5, 10, 20, 998, 1000],
                labels=["0-2", "3-5", "6-10", "11-20", "21+", "No injury on record"])),
        ("inj_365", "Injuries in the past year", pd.cut(d["inj_365"], [-1, 0, 1, 2, 3, 99], labels=["0", "1", "2", "3", "4+"])),
        ("min_avg10", "Minutes per game (last 10)", pd.cut(d["min_avg10"], [-1, 15, 25, 32, 60], labels=["Under 15", "15-25", "25-32", "32+"])),
        ("age", "Age", pd.cut(d["age"], [0, 23, 27, 31, 35, 50], labels=["Under 23", "23-26", "27-30", "31-34", "35+"])),
        ("listed_played_21", "Played while listed injured (past 3 weeks)",
         pd.cut(d["listed_played_21"], [-1, 0, 2, 100], labels=["Never", "1-2 games", "3+ games"])),
        ("acwr", "Last 7 days' minutes vs the 28-day norm",
         pd.cut(d["acwr"], [0, 0.8, 1.0, 1.2, 1.5, 10], labels=["Under 0.8", "0.8-1.0", "1.0-1.2", "1.2-1.5", "1.5+"])),
        ("b2b", "Second night of a back-to-back", d["b2b"].map({0: "No", 1: "Yes"})),
    ]
    out = [dict(factor="overall", factor_label="All player-games", bucket="All player-games", bucket_order=0,
                rows=int(len(d)), rate=float(overall), serious_rate=float(d["g5_3plus"].mean()), vs_avg=1.0)]
    for fid, flabel, groups in specs:
        g = d.groupby(groups, observed=True).agg(rows=("g5", "size"), rate=("g5", "mean"), serious_rate=("g5_3plus", "mean"))
        for order, (bucket, r) in enumerate(g.iterrows(), 1):
            out.append(dict(factor=fid, factor_label=flabel, bucket=str(bucket), bucket_order=order, rows=int(r["rows"]),
                            rate=float(r["rate"]), serious_rate=float(r["serious_rate"]), vs_avg=float(r["rate"] / overall)))
    return out


def injury_tables(pg: pd.DataFrame, onsets: pd.DataFrame) -> dict[str, list[dict]]:
    o = onsets[onsets["new_injury"] & onsets["season"].between(2020, 2026)]
    played = pg[(pg["absence"] == "played") & pg["season"].between(2020, 2026)]
    games = played.groupby("season").size()
    n = o.groupby("season").size()
    trend = [dict(season=season_label(int(s)), season_end=int(s), new_injuries=int(n.get(s, 0)), player_games=int(games[s]),
                  per_1000=float(1000 * n.get(s, 0) / games[s])) for s in sorted(games.index)]
    mix = []
    type_names = {"soreness": "Soreness", "ligament": "Sprain or ligament", "muscle_tendon": "Muscle or tendon strain",
                  "impact": "Contusion or impact", "bone": "Fracture or bone", "concussion": "Concussion",
                  "surgery": "Surgery or recovery", "other": "Other"}
    for dim, col, names in (("type", "injury_type", type_names), ("region", "region", {})):
        g = o.groupby(col)["games_missed"].agg(["size", "median", "mean"]).sort_values("size", ascending=False)
        for key, r in g.iterrows():
            mix.append(dict(dimension=dim, key=str(key), label=names.get(key, str(key).replace("_", " / ").capitalize()),
                            injuries=int(r["size"]), median_games_missed=float(r["median"]), mean_games_missed=float(r["mean"])))
    gp = played.groupby("player_id").size()
    names = pg.drop_duplicates("player_id").set_index("player_id")
    tab = pd.DataFrame({"games": gp, "injuries": o.groupby("player_id").size()}).fillna(0)
    tab = tab[tab["games"] >= 200]
    tab["per_100"] = 100 * tab["injuries"] / tab["games"]
    top = tab.sort_values("per_100", ascending=False).head(15)
    prone = [dict(player=f"{names.at[pid, 'first_name']} {names.at[pid, 'last_name']}", games=int(r["games"]),
                  injuries=int(r["injuries"]), per_100=float(r["per_100"])) for pid, r in top.iterrows()]
    prone.append(dict(player="Median of 200+ game players", games=int(tab["games"].median()), injuries=int(tab["injuries"].median()),
                      per_100=float(tab["per_100"].median())))
    return dict(injury_trend=trend, injury_mix=mix, prone_players=prone)


def early_exit_table(pg: pd.DataFrame, rows: pd.DataFrame) -> list[dict]:
    s = pg.sort_values(["player_id", "game_date"]).copy()
    s["next"] = s.groupby("player_id")["absence"].shift(-1)
    s = s[(s["starter_pbp"] == True) & s["season"].between(2020, 2026)]  # noqa: E712
    left, other = s[s["early_exit"] == 1], s[s["early_exit"] == 0]
    d = rows[rows["obs_g5"] & rows["season"].between(2020, 2026) & (rows["starter_rate10"] >= 0.5)]
    after = d[d["early_exit_prev1"] == 1]
    rest = d[d["early_exit_prev1"] == 0]
    return [
        dict(question="next_game", group="left_early", label="Starter left a close game early", rate=float((left["next"] == "injury").mean()), n=int(len(left))),
        dict(question="next_game", group="other", label="Other starter games", rate=float((other["next"] == "injury").mean()), n=int(len(other))),
        dict(question="played_next", group="left_early", label="Left early, then played the next game", rate=float(after["g5"].mean()), n=int(len(after))),
        dict(question="played_next", group="other", label="Other games by regular starters", rate=float(rest["g5"].mean()), n=int(len(rest))),
        dict(question="share_played", group="left_early", label="Left early and played the next game", rate=float((left["next"] == "played").mean()), n=int(len(left))),
    ]


def boards_and_players(rows: pd.DataFrame, onsets: pd.DataFrame, pg: pd.DataFrame) -> dict[str, list[dict]]:
    r5 = json.loads((OUTPUTS / "results_g5.json").read_text(encoding="utf-8"))
    r1 = json.loads((OUTPUTS / "results_g1_after_game.json").read_text(encoding="utf-8"))
    rows = rows.copy()
    rows["player"] = rows["first_name"].str.cat(rows["last_name"], sep=" ")
    pre_feats = features.ALL
    post_feats = features.ALL + features.PBP + features.CURRENT
    pre = board.fit_final(rows, "g5", r5["models"]["full_gbm"]["settings"], pre_feats)
    post = board.fit_final(rows, "g1", r1["models"]["after_game_gbm"]["settings"], post_feats)

    season = rows[rows["season"] == SEASON]
    s5 = season[season["obs_g5"]].copy()
    s5["risk"] = pre.predict_proba(s5[pre_feats].astype(float))[:, 1]
    s1 = season[season["obs_g1"]].copy()
    s1["risk"] = post.predict_proba(s1[post_feats].astype(float))[:, 1]

    # what happened: the next new injury after each game, with its reason and length
    o = onsets[onsets["new_injury"]].sort_values("onset_date")
    games = pg[["player_id", "game_id", "game_date"]].sort_values(["player_id", "game_date"])
    pos = {pid: {gid: i for i, gid in enumerate(d["game_id"])} for pid, d in games.groupby("player_id")}
    onset_pos = {}
    for _, x in o.iterrows():
        i = pos.get(x["player_id"], {}).get(x["onset_game_id"])
        if i is not None:
            onset_pos.setdefault(x["player_id"], []).append((i, x))

    def outcome(row, within: int) -> tuple[int, str]:
        i = pos.get(row["player_id"], {}).get(row["game_id"])
        for j, x in onset_pos.get(row["player_id"], []):
            if i is not None and i < j <= i + within:
                missed = int(x["games_missed"])
                return 1, f"{reason_text(x['reason'])} (missed {missed} game{'s' if missed != 1 else ''})"
        return 0, "No new injury in the next 5 games" if within > 1 else "No new injury next game"

    boards, checks = [], []
    for mode, frame, feats, model_, target, within in (("before", s5, pre_feats, pre, "g5", 5), ("after", s1, post_feats, post, "g1", 1)):
        size = BOARD_SIZE[mode]
        top = frame.sort_values("risk", ascending=False).groupby("game_date").head(size).copy()
        top["rank"] = top.groupby("game_date")["risk"].rank(ascending=False, method="first").astype(int)
        top["drivers"] = board._drivers(model_, top[feats].astype(float), feats)
        for _, x in top.sort_values(["game_date", "rank"]).iterrows():
            hit, text = outcome(x, within)
            boards.append(dict(mode=mode, date=x["game_date"].strftime("%Y-%m-%d"), rank=int(x["rank"]), player=x["player"],
                               team=x["team"], opponent=x["opponent"], risk=float(x["risk"]), drivers=_pretty(x["drivers"]),
                               injured=hit, outcome=text))
        nightly = 15 if mode == "before" else 10
        hi = frame.sort_values("risk", ascending=False).groupby("game_date").head(nightly)
        lo = frame.sort_values("risk").groupby("game_date").head(nightly)
        what = "a new injury within 5 games" if mode == "before" else "missed the next game with a new injury"
        checks += [dict(mode=mode, group="top", label=f"Each night's top {nightly}", rate=float(hi[target].mean()), rows=int(len(hi)), outcome=what),
                   dict(mode=mode, group="all", label="All players", rate=float(frame[target].mean()), rows=int(len(frame)), outcome=what),
                   dict(mode=mode, group="bottom", label=f"Each night's lowest {nightly}", rate=float(lo[target].mean()), rows=int(len(lo)), outcome=what)]

    players = [dict(player_id=int(x["player_id"]), player=x["player"], team=x["team"], date=x["game_date"].strftime("%Y-%m-%d"),
                    risk=round(float(x["risk"]), 3)) for _, x in s5.sort_values(["player", "game_date"]).iterrows()]
    names = rows.drop_duplicates("player_id").set_index("player_id")["player"]
    so = o[o["season"] == SEASON]
    injuries = [dict(player_id=int(x["player_id"]), player=names.get(x["player_id"], ""), onset_date=x["onset_date"].strftime("%Y-%m-%d"),
                     reason=reason_text(x["reason"]), games_missed=int(x["games_missed"])) for _, x in so.iterrows()
                if x["player_id"] in set(s5["player_id"])]
    return dict(board=boards, board_check=checks, player_risk=players, player_injuries=injuries)


def _pretty(drivers: str) -> str:
    """'recent-injury score: 5; age: 37' -> 'Recent-injury score: 5 · Age: 37'."""
    parts = [p.strip() for p in str(drivers or "").split(";") if p.strip()]
    return " · ".join(p[:1].upper() + p[1:] for p in parts)


def coverage(onsets: pd.DataFrame) -> list[dict]:
    s = json.loads((PROCESSED / "build_summary.json").read_text(encoding="utf-8"))
    r5 = json.loads((OUTPUTS / "results_g5.json").read_text(encoding="utf-8"))
    from .report_download import load_manifest
    days = sum(1 for r in load_manifest().values() if r["status"] == "ok")
    return [
        dict(metric="report_days", label="Official injury reports read (game days)", value=days),
        dict(metric="report_rows", label="Injury report lines", value=s["report_rows"]),
        dict(metric="matched_share", label="Report lines matched to a player", value=1 - s["report_rows_unmatched"] / s["report_rows"]),
        dict(metric="new_injuries", label="New injuries found, Dec 2018 to June 2026", value=int(onsets["new_injury"].sum())),
        dict(metric="test_rows", label="Player-games in the two test seasons", value=r5["test_rows"]),
    ]


def export(log=print) -> dict[str, int]:
    rows = pd.read_parquet(PROCESSED / "rows.parquet")
    onsets = pd.read_parquet(PROCESSED / "onsets.parquet")
    pg = pd.read_parquet(PROCESSED / "player_games.parquet",
                         columns=["player_id", "game_id", "game_date", "season", "absence", "first_name", "last_name",
                                  "starter_pbp", "early_exit"])
    tables = {}
    tables.update(model_tables())
    tables["risk_factors"] = risk_factor_table(rows)
    tables.update(injury_tables(pg, onsets))
    tables["early_exits"] = early_exit_table(pg, rows)
    tables["coverage"] = coverage(onsets)
    log("fitting the final models for the boards...")
    tables.update(boards_and_players(rows, onsets, pg))
    sizes = {name: write(name, data) for name, data in tables.items()}
    log(json.dumps(sizes))
    return sizes
