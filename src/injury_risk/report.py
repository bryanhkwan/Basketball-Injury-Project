"""Write outputs/RESULTS.md from the results JSON files."""
from __future__ import annotations

import json

from .paths import OUTPUTS, PROCESSED

TARGET_TEXT = {
    "g5": "a new injury makes the player miss one of the team's next 5 games",
    "g1": "a new injury makes the player miss the team's next game",
    "y14": "a new injury makes the player miss a game in the next 14 days",
    "y7": "a new injury makes the player miss a game in the next 7 days",
}
MODEL_TEXT = {
    "base_rate": "Base rate (everyone gets the average)",
    "history_logistic": "Age + injury history (logistic)",
    "full_logistic": "All features (logistic)",
    "full_gbm": "All features (gradient boosting)",
    "full_gbm_plus_pbp": "All features + play-by-play load (gradient boosting)",
    "full_gbm_plus_pregame_report": "All features + that day's injury report (gradient boosting)",
    "after_game_gbm": "After the game: all features + that game's play-by-play (gradient boosting)",
}


def _table(results: dict) -> list[str]:
    lines = ["| Model | AUC (95% CI) | Avg precision | Brier skill | Top-10% lift | Top-10% catches |",
             "|---|---|---|---|---|---|"]
    for name, entry in results["models"].items():
        t = entry["test"]
        ci = entry.get("auc_95")
        auc = f"{t['auc']:.3f}" + (f" ({ci[0]:.3f}-{ci[1]:.3f})" if ci else "")
        lines.append(f"| {MODEL_TEXT.get(name, name)} | {auc} | {t['avg_precision']:.3f} | {t['brier_skill']:.3f} | "
                     f"{t['top10_lift']:.2f}x | {t['top10_capture']:.0%} |")
    return lines


def write() -> str:
    out = ["# Results", ""]
    summary_path = PROCESSED / "build_summary.json"
    if summary_path.exists():
        s = json.loads(summary_path.read_text(encoding="utf-8"))
        new = {k: v["new_injuries"] for k, v in s["onsets_by_season"].items()}
        out += [f"Built {s['built']}. Report rows {s['report_rows']:,}, of which {s['report_rows_unmatched']:,} could not "
                f"be matched to a player. New injuries by season (ending year): {new}. Median games missed: "
                f"{s['median_games_missed']:.0f}.", ""]
    for path in sorted(OUTPUTS.glob("results_*.json")):
        r = json.loads(path.read_text(encoding="utf-8"))
        target = r["target"]
        after = r.get("framing") == "after_game"
        out += [f"## Target `{target}`: {TARGET_TEXT.get(target.split('_')[0], target)}"
                + (f" ({target.split('_', 1)[1]})" if "_" in target else "")
                + (", scored right after the game with its play-by-play" if after else ""), "",
                f"Test seasons 2024-25 and 2025-26: {r['test_rows']:,} player-games, "
                f"{r['models']['base_rate']['test']['positives']:,} followed by a new injury "
                f"({r['models']['base_rate']['test']['rate']:.1%}).", ""]
        out += _table(r) + [""]
        key = "after_game_gbm" if after else "full_gbm"
        best = r["models"].get(key)
        if best:
            out += [f"{MODEL_TEXT[key]}, by test season:", "",
                    "| Season | Player-games | Injury rate | AUC | Top-10% lift |", "|---|---|---|---|---|"]
            for season, sc in best["by_season"].items():
                out.append(f"| {int(season) - 1}-{str(season)[2:]} | {sc['rows']:,} | {sc['rate']:.1%} | {sc['auc']:.3f} | {sc['top10_lift']:.2f}x |")
            out += ["", "Calibration (deciles of predicted risk):", "", "| Decile | Predicted | Observed |", "|---|---|---|"]
            out += [f"| {c['decile']} | {c['predicted']:.1%} | {c['observed']:.1%} |" for c in best["calibration"]]
            ranks = {k: v for k, v in best.items() if k.startswith("ranks_")}
            if ranks:
                out += ["", "The same scores ranked against narrower injury definitions:", ""]
                out += [f"- {k.removeprefix('ranks_')}: AUC {v['auc']:.3f}, top-10% lift {v['top10_lift']:.2f}x" for k, v in ranks.items()]
        importance = r.get(f"importance_{key}")
        if importance:
            out += ["", "What that model leans on (AUC lost when the feature is shuffled):", ""]
            out += [f"- `{i['feature']}` {i['auc_drop']:.4f}" for i in importance[:12]]
        out.append("")
    text = "\n".join(out)
    (OUTPUTS / "RESULTS.md").write_text(text, encoding="utf-8")
    return text
