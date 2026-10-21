"""Two checks of earlier results against what the news says happened (outputs/news/facts.jsonl).

The play-by-play study pins injury exits to plays the player was credited with in the 30 seconds before. Where the news
names the play an injury came on, does it agree? Each pattern is a two-by-two table over the pinned exits that have
both: the play-by-play flag against the reported play, with Fisher's exact test.

The before-the-game model predicts a new injury in the team's next five games. Does it flag the injuries a workload
model can hope to see (strains, non-contact) more than the ones it can't (knocks, contact)? On the test seasons, the
model refit as `train` fits it, each kind of upcoming injury is scored against the games with no injury after them
(AUC), and the difference between two kinds is resampled by player.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
from scipy.stats import fisher_exact
from sklearn.metrics import roc_auc_score

from . import features, model, news, news_research, pipeline
from .paths import OUTPUTS, PROCESSED

OUT = OUTPUTS / "validation"
# a play-by-play flag in the 30 seconds before an injury exit, and the play a report would call it
PAIRS = [("fouled_30", "drew_foul", "Fouled"), ("steal_30", "steal", "Their own steal"),
         ("opp_rim_30", "defending_the_rim", "The other team attacked the rim"), ("drive_30", "drive", "A drive"),
         ("rebound_30", "rebound", "A rebound")]
BREAK = {"transition", "drive", "drew_foul", "loose_ball"}   # the break or scramble that follows a steal
REPS = 400


def two_by_two(flagged: np.ndarray, said: np.ndarray) -> dict:
    """Counts, odds ratio and Fisher's exact p for a flag against a report saying the same."""
    a, b = int((flagged & said).sum()), int((flagged & ~said).sum())
    c, d = int((~flagged & said).sum()), int((~flagged & ~said).sum())
    odds, p = fisher_exact([[a, b], [c, d]]) if a + b and c + d else (float("nan"), float("nan"))
    return dict(flagged=a + b, flagged_said=a, unflagged=c + d, unflagged_said=c, odds_ratio=float(odds), p=float(p))


def news_rows() -> pd.DataFrame:
    """The filed NBA facts with their player: game, play, contact, mechanism and the listing they explain."""
    targets = {t["id"]: t for t in news_research.read_jsonl(news.TARGETS)}
    rows = []
    for f in news_research.read_jsonl(news.FACTS):
        t = targets.get(f["target"])
        if t is None or t["league"] != "nba" or f["status"] == "not_found":
            continue
        rows.append(dict(player_id=int(t["player_id"]), first_listed=t["first_listed"], game_date=news._get(f, "game.date"),
                         play=news._get(f, "game.play"), contact=news._get(f, "contact"), mechanism=news._get(f, "mechanism"),
                         label=news._get(f, "diagnosis.label"), status=f["status"]))
    return pd.DataFrame(rows)


def moments_vs_news(log=print) -> dict:
    inj = pd.read_parquet(OUTPUTS / "moments" / "injuries.parquet")
    flags = [flag for flag, _, _ in PAIRS]
    mom = pd.read_parquet(OUTPUTS / "moments" / "moments.parquet", columns=["game_id", "player_id", "role"] + flags)
    games = pd.read_parquet(PROCESSED / "player_games.parquet", columns=["game_id", "game_date"]).drop_duplicates("game_id")
    date_of = dict(zip(games["game_id"], games["game_date"].dt.strftime("%Y-%m-%d")))
    reported = news_rows().dropna(subset=["game_date"])
    # a pinned exit whose report names the game: the exit's game is the one before the injury's onset
    exits = inj[inj["pinned"]].assign(game_date=lambda x: x["prev_game"].map(date_of)).astype({"player_id": "int64"})
    exits = exits.merge(reported, on=["player_id", "game_date"], how="inner")
    cases = mom[mom["role"] == "case"].drop_duplicates(["player_id", "game_id"]).astype({"player_id": "int64"})
    exits = exits.merge(cases, left_on=["player_id", "prev_game"], right_on=["player_id", "game_id"], how="inner")
    both = exits[exits["play"].notna() & (exits["play"] != "unknown")]
    play = both["play"].to_numpy()
    out = dict(pinned_exits_with_a_reported_game=int(len(exits)), with_a_reported_play=int(len(both)),
               plays=both["play"].value_counts().to_dict(), patterns=[])
    for flag, said, name in PAIRS:
        row = dict(pattern=name, flag=flag, play=said, **two_by_two(both[flag].to_numpy() > 0, play == said))
        out["patterns"].append(row)
        log(f"  {name}: news says {said} after {row['flagged_said']} of {row['flagged']} flagged exits, "
            f"{row['unflagged_said']} of {row['unflagged']} others (OR {row['odds_ratio']:.1f}, p {row['p']:.3g})")
    # the steal finding reads as the break after it: is that what the news describes?
    row = dict(pattern="The break or scramble after their own steal", flag="steal_30", play="transition, drive, drew_foul, loose_ball",
               **two_by_two(both["steal_30"].to_numpy() > 0, np.isin(play, list(BREAK))))
    out["patterns"].append(row)
    log(f"  after a steal, the news describes the break or a scramble in {row['flagged_said']} of {row['flagged']}, "
        f"{row['unflagged_said']} of {row['unflagged']} others (OR {row['odds_ratio']:.1f}, p {row['p']:.3g})")
    ankle = exits[(exits["fouled_30"] > 0) & (exits["coarse"] == "ankle")]
    out["ankle_after_a_foul_mechanisms"] = ankle["mechanism"].fillna("not reported").value_counts().to_dict()
    return out


def test_risk(log=print) -> pd.DataFrame:
    """Each test-season player-game with the before-the-game model's risk, the model refit as `train` fits it."""
    rows = pd.read_parquet(PROCESSED / "rows.parquet")
    data = rows[rows[pipeline.observable_column("g5")] & rows["season"].isin(model.TRAIN + model.VALID + model.TEST)
                & (rows["game_date"] >= model.FIRST_TRAIN_DATE)]
    feats = features.ALL
    settings = json.loads((OUTPUTS / "results_g5.json").read_text(encoding="utf-8"))["models"]["full_gbm"]["settings"]
    trva = data[data["season"].isin(model.TRAIN + model.VALID)]
    te = data[data["season"].isin(model.TEST)]
    fit = model.gbm(**settings).fit(trva[feats].astype(float), trva["g5"])
    out = te[["player_id", "game_date", "season", "g5"]].astype({"player_id": "int64"}).copy()
    out["risk"] = fit.predict_proba(te[feats].astype(float))[:, 1]
    log(f"  refit: test AUC {roc_auc_score(out['g5'], out['risk']):.4f}")
    return out


def upcoming(risk: pd.DataFrame) -> pd.DataFrame:
    """The games with a new injury in the next five, each with that injury: its kind from the listing, and contact
    from the news."""
    on = pd.read_parquet(PROCESSED / "onsets.parquet")
    on = on[on["new_injury"]].astype({"player_id": "int64"}).sort_values("onset_date")
    on = on[["player_id", "onset_date", "injury_type"]].rename(columns={"injury_type": "kind"})
    pos = pd.merge_asof(risk[risk["g5"] == 1].sort_values("game_date").reset_index(drop=True), on, left_on="game_date",
                        right_on="onset_date", by="player_id", direction="forward", allow_exact_matches=False)
    reported = news_rows()
    contact = dict(zip(zip(reported["player_id"], reported["first_listed"]), reported["contact"]))
    pos["contact"] = [contact.get((p, d.strftime("%Y-%m-%d"))) if pd.notna(d) else None
                      for p, d in zip(pos["player_id"], pos["onset_date"])]
    return pos


def auc_against(pos: np.ndarray, neg: np.ndarray) -> float:
    return float(roc_auc_score(np.r_[np.ones(len(pos)), np.zeros(len(neg))], np.r_[pos, neg]))


def compare(a: pd.DataFrame, b: pd.DataFrame, neg: np.ndarray, reps: int = REPS, seed: int = 0) -> dict:
    """AUC of two kinds of upcoming injury against games with none, and their difference resampled by player."""
    rng = np.random.default_rng(seed)
    ga = [g["risk"].to_numpy() for _, g in a.groupby("player_id")]
    gb = [g["risk"].to_numpy() for _, g in b.groupby("player_id")]
    diffs = []
    for _ in range(reps):
        sa = np.concatenate([ga[i] for i in rng.integers(0, len(ga), len(ga))])
        sb = np.concatenate([gb[i] for i in rng.integers(0, len(gb), len(gb))])
        diffs.append(auc_against(sa, neg) - auc_against(sb, neg))
    lo, hi = np.percentile(diffs, [2.5, 97.5])
    ra, rb = auc_against(a["risk"].to_numpy(), neg), auc_against(b["risk"].to_numpy(), neg)
    return dict(auc_a=round(ra, 4), injuries_a=int(a["onset_date"].nunique()), auc_b=round(rb, 4),
                injuries_b=int(b["onset_date"].nunique()), difference=round(ra - rb, 4), lo=round(float(lo), 4), hi=round(float(hi), 4))


def model_by_kind(log=print) -> dict:
    risk = test_risk(log)
    pos = upcoming(risk)
    neg = risk.loc[risk["g5"] == 0, "risk"].to_numpy()
    kinds = {k: dict(auc=round(auc_against(g["risk"].to_numpy(), neg), 4), injuries=int(g["onset_date"].nunique()))
             for k, g in pos.groupby("kind")}
    out = dict(test_auc=round(roc_auc_score(risk["g5"], risk["risk"]), 4), by_kind=kinds, comparisons=[])
    for name, a, b in (("Strains against knocks and concussions (the listing's words)", pos[pos["kind"] == "muscle_tendon"],
                        pos[pos["kind"].isin(["impact", "concussion"])]),
                       ("Non-contact against contact (the news)", pos[pos["contact"] == "non_contact"], pos[pos["contact"] == "contact"])):
        row = dict(comparison=name, **compare(a, b, neg))
        out["comparisons"].append(row)
        log(f"  {name}: {row['auc_a']:.3f} ({row['injuries_a']} injuries) against {row['auc_b']:.3f} ({row['injuries_b']}); "
            f"difference {row['difference']:+.3f} ({row['lo']:+.3f} to {row['hi']:+.3f})")
    return out


def export(log=print) -> dict:
    log("the play-by-play patterns against the news")
    plays = moments_vs_news(log)
    log("the model, by kind of injury")
    kinds = model_by_kind(log)
    OUT.mkdir(parents=True, exist_ok=True)
    summary = dict(moments_vs_news=plays, model_by_kind=kinds)
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    return summary
