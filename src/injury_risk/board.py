"""Risk board: for one game day, the players at highest risk and what drives each score."""
from __future__ import annotations

import numpy as np
import pandas as pd

LABELS = {
    "days_since_return": "days since returning from injury", "games_since_return": "games since returning",
    "inj_365": "injuries in the last year", "inj_per100": "injuries per 100 games", "missed_inj_365": "games missed (year)",
    "last_games_missed": "games missed last injury", "listed_played_21": "games played while listed (3 wk)",
    "min_7d": "minutes last 7 days", "min_28d": "minutes last 28 days", "acwr": "7-day vs 28-day load",
    "season_min_avg": "minutes per game (season)", "min_avg10": "minutes per game (last 10)", "age": "age",
    "b2b": "second night of back-to-back", "games_next14": "team games next 14 days", "rest_days": "days of rest",
    "fta36": "free throws per 36", "usage36": "usage per 36", "reb36": "rebounds per 36", "weight_lb": "weight",
    "travel_7d": "km travelled (7 days)", "mgmt_60": "rest/management absences (60 days)", "days_since_onset": "days since last injury",
    "inj_decay": "recent-injury score", "prone_shrunk": "injury-prone rating", "season_min": "season minutes",
    "ill_60": "illness absences (60 days)", "inj_60": "injuries (60 days)", "inj_120": "injuries (120 days)",
    "soreness_365": "soreness absences (year)", "missed_decay": "recent games missed score", "heavy_14d": "36+ minute games (14 days)",
    "min_last2": "minutes last 2 games", "team_inj_rate_365": "team injury rate", "game_no": "team game number",
    "cur_early_exit": "left a close game early tonight", "cur_min_drop": "minutes tonight vs usual",
    "cur_last_on_min": "last on the floor at minute", "cur_minutes": "minutes tonight", "cur_longest_stint": "longest stint tonight",
    "cur_q4ot_min": "4th-quarter minutes tonight", "cur_n_stints": "stints tonight", "cur_margin": "final margin",
    "min_avg3": "minutes per game (last 3)", "b2b_next14": "back-to-backs in the next 14 days",
}


def board(rows: pd.DataFrame, model, feats: list[str], day: str, top: int = 15, outcome: str | None = None) -> pd.DataFrame:
    """Highest predicted risk among players who played on ``day``, with the three features pushing it up most.
    With ``outcome`` (a target column), also say whether the injury came, for days already in the past."""
    sel = rows[rows["game_date"] == pd.Timestamp(day)].copy()
    if sel.empty:
        return sel
    X = sel[feats].astype(float)
    sel["risk"] = model.predict_proba(X)[:, 1]
    sel = sel.sort_values("risk", ascending=False).head(top)
    drivers = _drivers(model, sel[feats].astype(float), feats)
    sel["drivers"] = drivers
    sel["player"] = sel["first_name"].str.cat(sel["last_name"], sep=" ")
    cols = ["player", "team", "opponent", "risk", "drivers"] + ([outcome] if outcome else [])
    return sel[cols]


def fit_final(rows: pd.DataFrame, target: str, settings: dict, feats: list[str]):
    """The tuned model refit on every season before the test seasons (rows whose outcome window is visible)."""
    from . import model as M
    from .pipeline import observable_column
    data = rows[rows["season"].isin(M.TRAIN + M.VALID) & (rows["game_date"] >= M.FIRST_TRAIN_DATE)
                & rows[observable_column(target)]]
    return M.gbm(**settings).fit(data[feats].astype(float), data[target])


def _drivers(model, X: pd.DataFrame, feats: list[str]) -> list[str]:
    try:
        import shap
        values = shap.TreeExplainer(model).shap_values(X)
        values = values[1] if isinstance(values, list) else values
    except Exception:   # no explainer for this model: fall back to nothing rather than guess
        return [""] * len(X)
    out = []
    for i in range(len(X)):
        order = np.argsort(-values[i])[:3]
        parts = []
        for j in order:
            if values[i][j] <= 0:
                continue
            name, v = LABELS.get(feats[j], feats[j]), X.iloc[i, j]
            if feats[j] in FLAGS:
                parts.append(name if v == 1 else f"not {name}")
            elif pd.isna(v):
                parts.append(f"{name}: none on record")
            else:
                parts.append(f"{name}: {v:.1f}" if abs(v) < 10 and abs(v - round(v)) > 0.05 else f"{name}: {v:.0f}")
        out.append("; ".join(parts))
    return out


FLAGS = {"b2b", "cur_early_exit", "early_exit_prev1", "is_home", "playoffs", "pregame_listed", "pregame_questionable",
         "pos_g", "pos_f", "pos_c"}
