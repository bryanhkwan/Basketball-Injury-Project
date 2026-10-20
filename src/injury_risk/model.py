"""Train and evaluate injury-risk models with season-based splits.

Train on 2018-19 (from mid-January, once the report archive has run a month) to 2022-23, choose settings on
2023-24, then refit on all of them and score 2024-25 and 2025-26, which no choice ever saw. Every score is
on predicted probabilities.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

TRAIN, VALID, TEST = (2019, 2020, 2021, 2022, 2023), (2024,), (2025, 2026)
FIRST_TRAIN_DATE = "2019-01-15"   # four weeks after the report archive begins, so a game's window is labelled
HISTORY_ONLY = ["age", "inj_365", "inj_per100", "prone_shrunk", "inj_decay", "missed_inj_365", "games_since_return",
                "days_since_return", "last_games_missed"]


def scores(y: np.ndarray, p: np.ndarray) -> dict:
    base = y.mean()
    top = p >= np.quantile(p, 0.9)
    return dict(rows=int(len(y)), positives=int(y.sum()), rate=round(float(base), 4),
                auc=round(roc_auc_score(y, p), 4), avg_precision=round(average_precision_score(y, p), 4),
                brier_skill=round(1 - brier_score_loss(y, p) / (base * (1 - base)), 4),
                log_loss=round(log_loss(y, p), 4),
                top10_lift=round(float(y[top].mean() / base), 2), top10_capture=round(float(y[top].sum() / y.sum()), 3))


def auc_interval(y, p, groups, reps: int = 300, seed: int = 0) -> tuple[float, float]:
    """95% interval for AUC, resampling whole players (a player's games are not independent)."""
    rng = np.random.default_rng(seed)
    ids = np.unique(groups)
    by = {g: np.nonzero(groups == g)[0] for g in ids}
    out = []
    for _ in range(reps):
        pick = np.concatenate([by[g] for g in rng.choice(ids, len(ids), replace=True)])
        if y[pick].min() != y[pick].max():
            out.append(roc_auc_score(y[pick], p[pick]))
    return round(float(np.percentile(out, 2.5)), 4), round(float(np.percentile(out, 97.5)), 4)


def calibration(y, p, bins: int = 10) -> list[dict]:
    q = np.quantile(p, np.linspace(0, 1, bins + 1))
    idx = np.clip(np.searchsorted(q, p, "right") - 1, 0, bins - 1)
    return [dict(decile=b + 1, predicted=round(float(p[idx == b].mean()), 4), observed=round(float(y[idx == b].mean()), 4),
                 rows=int((idx == b).sum())) for b in range(bins)]


def logistic(c: float = 0.1):
    return make_pipeline(SimpleImputer(strategy="median", add_indicator=True), StandardScaler(),
                         LogisticRegression(C=c, max_iter=3000))


def gbm(**kw):
    params = dict(learning_rate=0.05, max_iter=300, max_leaf_nodes=15, min_samples_leaf=300, l2_regularization=1.0,
                  early_stopping=False, random_state=0)
    params.update(kw)
    return HistGradientBoostingClassifier(**params)


def tune_gbm(Xtr, ytr, Xva, yva, log=print) -> dict:
    """Pick learning rate, tree size, leaf size and number of trees by 2023-24 log loss."""
    best = None
    for lr in (0.03, 0.06):
        for leaves in (7, 15, 31):
            for leaf in (200, 800):
                model = gbm(learning_rate=lr, max_leaf_nodes=leaves, min_samples_leaf=leaf, max_iter=50, warm_start=True)
                for n in range(50, 801, 50):
                    model.set_params(max_iter=n)
                    model.fit(Xtr, ytr)
                    ll = log_loss(yva, model.predict_proba(Xva)[:, 1])
                    if best is None or ll < best["log_loss"]:
                        best = dict(learning_rate=lr, max_leaf_nodes=leaves, min_samples_leaf=leaf, max_iter=n, log_loss=ll)
        log(f"  lr={lr} best so far: {best}")
    return best


def tune_logistic(Xtr, ytr, Xva, yva) -> float:
    lls = {c: log_loss(yva, logistic(c).fit(Xtr, ytr).predict_proba(Xva)[:, 1]) for c in (0.003, 0.01, 0.03, 0.1, 0.3, 1.0)}
    return min(lls, key=lls.get)


def evaluate(data: pd.DataFrame, feature_sets: dict, target: str, extra_targets=(), log=print) -> dict:
    """Fit every model on train, tune on valid, refit on train+valid, score each test season and both together."""
    tr = data[data["season"].isin(TRAIN)]
    va = data[data["season"].isin(VALID)]
    trva = data[data["season"].isin(TRAIN + VALID)]
    te = data[data["season"].isin(TEST)]
    results = dict(target=target, train_rows=len(tr), valid_rows=len(va), test_rows=len(te), models={})
    base_rate = trva[target].mean()
    results["models"]["base_rate"] = dict(test=scores(te[target].to_numpy(), np.full(len(te), base_rate)))
    fitted = {}
    for name, cols in feature_sets.items():
        kind, feats = cols
        log(f"{name}: {len(feats)} features ({kind})")
        if kind == "logistic":
            c = tune_logistic(tr[feats], tr[target], va[feats], va[target])
            model = logistic(c).fit(trva[feats], trva[target])
            settings = dict(C=c)
        else:
            best = tune_gbm(tr[feats], tr[target], va[feats], va[target], log=log)
            settings = {k: v for k, v in best.items() if k != "log_loss"}
            model = gbm(**settings).fit(trva[feats], trva[target])
        p = model.predict_proba(te[feats])[:, 1]
        y = te[target].to_numpy()
        entry = dict(settings=settings, test=scores(y, p), auc_95=auc_interval(y, p, te["player_id"].to_numpy()),
                     by_season={int(s): scores(y[(te["season"] == s).to_numpy()], p[(te["season"] == s).to_numpy()]) for s in TEST},
                     calibration=calibration(y, p))
        for extra in extra_targets:
            ye = te[extra].to_numpy()
            entry[f"ranks_{extra}"] = dict(auc=round(roc_auc_score(ye, p), 4), top10_lift=round(float(ye[p >= np.quantile(p, 0.9)].mean() / ye.mean()), 2))
        results["models"][name] = entry
        fitted[name] = (model, feats, p)
        log(f"  test: {entry['test']}  auc 95%: {entry['auc_95']}")
    return results, fitted


def importance(model, X: pd.DataFrame, y: pd.Series, top: int = 20) -> list[dict]:
    r = permutation_importance(model, X, y, scoring="roc_auc", n_repeats=3, random_state=0, n_jobs=1)
    order = np.argsort(-r.importances_mean)[:top]
    return [dict(feature=X.columns[i], auc_drop=round(float(r.importances_mean[i]), 4)) for i in order]
