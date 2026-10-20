"""Build the modelling table from the season files and the parsed injury reports, then train and score."""
from __future__ import annotations

import json
from datetime import datetime

import pandas as pd

from . import features, games, labels, model, pbp
from .paths import INTERIM, OUTPUTS, PROCESSED

DATA_SEASONS = tuple(range(2017, 2027))    # box scores from 2016-17 for workload history
FIRST_LABEL_SEASON = 2019                  # official reports start in 2018-19
HORIZONS = (7, 14, 28)


def build(log=print) -> dict:
    sched = games.build_schedule(DATA_SEASONS)
    pg = games.build_player_games(DATA_SEASONS, sched)
    log(f"schedule {len(sched):,} games, player-games {len(pg):,}")
    load_path = INTERIM / "pbp_load.parquet"
    load = pd.read_parquet(load_path) if load_path.exists() else pbp.build(DATA_SEASONS, log=log)
    pg = pg.merge(load.drop(columns="season"), on=["game_id", "player_id"], how="left")
    report = pd.read_parquet(INTERIM / "report_rows.parquet")
    report = labels.match_players(report, pg, sched)
    entries = labels.best_entries(report)
    pg = labels.classify_absences(pg, entries)
    onsets = labels.find_onsets(pg)
    onsets = onsets[onsets["season"] >= FIRST_LABEL_SEASON].reset_index(drop=True)
    rows = features.build(pg, onsets, sched, DATA_SEASONS)
    rows = rows[rows["season"] >= FIRST_LABEL_SEASON].reset_index(drop=True)
    for h in HORIZONS:
        rows[f"y{h}"] = labels.targets(rows, onsets, pg, h)
        rows[f"obs{h}"] = labels.observable(rows, pg, h)
    rows["y14_3plus"] = labels.targets(rows, onsets, pg, 14, where=lambda o: o["games_missed"] >= 3)
    rows["y14_muscle"] = labels.targets(rows, onsets, pg, 14, where=lambda o: o["injury_type"] == "muscle_tendon")
    rows["y14_lower"] = labels.targets(rows, onsets, pg, 14, where=lambda o: o["region"].isin(labels.LOWER_BODY))
    # the same question counted in team games, so a busy or quiet stretch of schedule does not change the odds
    rows["g5"], rows["obs_g5"] = labels.targets_in_games(rows, onsets, pg, 5)
    rows["g5_3plus"], _ = labels.targets_in_games(rows, onsets, pg, 5, where=lambda o: o["games_missed"] >= 3)
    rows["g5_muscle"], _ = labels.targets_in_games(rows, onsets, pg, 5, where=lambda o: o["injury_type"] == "muscle_tendon")
    rows["g1"], rows["obs_g1"] = labels.targets_in_games(rows, onsets, pg, 1)

    PROCESSED.mkdir(parents=True, exist_ok=True)
    rows.to_parquet(PROCESSED / "rows.parquet", index=False)
    onsets.to_parquet(PROCESSED / "onsets.parquet", index=False)
    pg.to_parquet(PROCESSED / "player_games.parquet", index=False)

    labelled = pg[pg["season"] >= FIRST_LABEL_SEASON]
    absent = labelled[labelled["absence"] != "played"]
    summary = dict(
        built=datetime.now().isoformat(timespec="seconds"),
        report_rows=len(report), report_rows_unmatched=int(report["player_id"].isna().sum()),
        report_match_methods=report["match"].fillna("none").value_counts().to_dict(),
        absences_by_class=absent["absence"].value_counts().to_dict(),
        onsets_by_season=onsets.groupby("season")["new_injury"].agg(["sum", "count"]).rename(
            columns={"sum": "new_injuries", "count": "injury_runs"}).to_dict("index"),
        new_injury_regions=onsets.loc[onsets["new_injury"], "region"].value_counts().to_dict(),
        new_injury_types=onsets.loc[onsets["new_injury"], "injury_type"].value_counts().to_dict(),
        median_games_missed=float(onsets.loc[onsets["new_injury"], "games_missed"].median()),
        rows=len(rows), rows_by_season=rows["season"].value_counts().sort_index().to_dict(),
        target_rates={f"y{h}": round(float(rows.loc[rows[f'obs{h}'], f'y{h}'].mean()), 4) for h in HORIZONS})
    (PROCESSED / "build_summary.json").write_text(json.dumps(summary, indent=1, default=str), encoding="utf-8")
    return summary


def observable_column(target: str) -> str:
    base = target.split("_")[0]
    return f"obs_{base}" if base.startswith("g") else f"obs{base[1:]}"


VARIANTS = {"y14": ["y14_3plus", "y14_muscle", "y14_lower"], "g5": ["g5_3plus", "g5_muscle"], "g5_3plus": ["g5"]}


def train(target: str = "g5", after_game: bool = False, log=print) -> dict:
    """Before-the-game models; with ``after_game``, the after-the-game question (scored once the game is over,
    using its play-by-play) next to the before-the-game model it should beat."""
    rows = pd.read_parquet(PROCESSED / "rows.parquet")
    data = rows[rows[observable_column(target)] & rows["season"].isin(model.TRAIN + model.VALID + model.TEST)
                & (rows["game_date"] >= model.FIRST_TRAIN_DATE)].copy()
    cols = features.ALL + features.PREGAME + features.PBP + (features.CURRENT if after_game else [])
    data[cols] = data[cols].astype(float)
    if after_game:
        sets = {
            "full_gbm": ("gbm", features.ALL),
            "after_game_gbm": ("gbm", features.ALL + features.PBP + features.CURRENT),
        }
    else:
        sets = {
            "history_logistic": ("logistic", model.HISTORY_ONLY),
            "full_logistic": ("logistic", features.ALL),
            "full_gbm": ("gbm", features.ALL),
            "full_gbm_plus_pbp": ("gbm", features.ALL + features.PBP),
            "full_gbm_plus_pregame_report": ("gbm", features.ALL + features.PREGAME),
        }
    extras = VARIANTS.get(target, [])
    results, fitted = model.evaluate(data, sets, target, extra_targets=extras, log=log)
    results["framing"] = "after_game" if after_game else "before_game"
    key = "after_game_gbm" if after_game else "full_gbm"
    gbm_model, feats, _ = fitted[key]
    test = data[data["season"].isin(model.TEST)]
    results[f"importance_{key}"] = model.importance(gbm_model, test[feats], test[target])
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    name = f"results_{target}_after_game.json" if after_game else f"results_{target}.json"
    (OUTPUTS / name).write_text(json.dumps(results, indent=1), encoding="utf-8")
    return results
