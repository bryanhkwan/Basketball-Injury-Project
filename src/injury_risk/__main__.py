"""Command line: python -m injury_risk <step>  (run from the project root with PYTHONPATH=src)."""
from __future__ import annotations

import argparse
import json

from . import paths


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="injury_risk", description=__doc__)
    sub = parser.add_subparsers(dest="step", required=True)
    p = sub.add_parser("fetch-data", help="download season parquet files (box scores, inactive lists, schedules, rosters)")
    p.add_argument("--seasons", type=int, nargs="*", default=None)
    p = sub.add_parser("fetch-reports", help="download one official injury report per game day")
    p.add_argument("--seasons", type=int, nargs="*", default=None)
    p.add_argument("--retry-missing", action="store_true")
    p = sub.add_parser("parse-reports", help="parse every downloaded report PDF into data/interim/report_rows.parquet")
    p.add_argument("--workers", type=int, default=6)
    sub.add_parser("build", help="labels and features -> data/processed/rows.parquet")
    p = sub.add_parser("train", help="fit and score the models -> outputs/results_<target>.json")
    p.add_argument("--target", default="g5", help="g5 (next 5 team games), g1, y14 (next 14 days), y7, y28, or a variant")
    p.add_argument("--after-game", action="store_true",
                   help="score right after the game with its play-by-play (will the player miss the next games?)")
    p = sub.add_parser("board", help="highest-risk players on one game day, with drivers (and outcome if known)")
    p.add_argument("--date", required=True)
    p.add_argument("--target", default="g5")
    p.add_argument("--top", type=int, default=15)
    p.add_argument("--after-game", action="store_true", help="after that night's games: who is likely to miss the next one")
    sub.add_parser("dashboard", help="export the dashboard's datasets -> outputs/dashboard/*.json")
    sub.add_parser("causes", help="injury types: who, when, cost, repeats -> outputs/causes/*.json")
    sub.add_parser("ncaa-injuries", help="NCAA injury listings from SCACCHoops, with how long each has been up "
                                         "-> outputs/ncaa_injuries/listings.json")
    p = sub.add_parser("moments", help="what players were doing just before leaving a game they got hurt in "
                                       "-> outputs/moments/*")
    p.add_argument("--reuse", action="store_true", help="recompute the statistics from the saved moments instead of rebuilding them")
    sub.add_parser("fetch-college", help="download the college play-by-play and box scores, and any new saved Covers pages")
    sub.add_parser("college-moments", help="the injury-moment test on Division I games, to docs/ncaa_moments_plan.md "
                                           "-> outputs/college_moments/*")
    sub.add_parser("moments-dashboard", help="export the injury-moment dashboard's datasets (NBA and college results) "
                                             "-> outputs/moments_dashboard/*.json")
    sub.add_parser("report-site", help="the injury-moment report page, from the dashboard's datasets -> docs/moments.html")
    sub.add_parser("site", help="the whole public site for GitHub Pages: data, overview, dashboards and the report -> docs/")
    sub.add_parser("linkedin", help="three LinkedIn images and the report's link preview, rendered with headless Chrome "
                                    "-> outputs/linkedin/*.png, docs/assets/social-card.png")
    args = parser.parse_args(argv)
    paths.ensure_dirs()

    if args.step == "fetch-data":
        from . import sources
        results = sources.fetch(args.seasons or sources.DEFAULT_SEASONS)
        bad = [r for r in results if r["status"] not in ("cached", "downloaded")]
        print(json.dumps({"files": len(results), "problems": bad}, indent=1))
    elif args.step == "fetch-reports":
        from . import report_download
        seasons = args.seasons or range(report_download.FIRST_REPORT_SEASON, 2027)
        print(json.dumps(report_download.fetch(seasons, retry_missing=args.retry_missing)))
    elif args.step == "parse-reports":
        from . import labels
        df = labels.parse_all(workers=args.workers)
        print(json.dumps({"rows": len(df), "files": int(df["file"].nunique()) if len(df) else 0}))
    elif args.step == "build":
        from . import pipeline
        print(json.dumps(pipeline.build(), indent=1, default=str))
    elif args.step == "train":
        from . import pipeline, report
        results = pipeline.train(args.target, after_game=args.after_game)
        report.write()
        print(json.dumps({k: v.get("test") for k, v in results["models"].items()}, indent=1))
    elif args.step == "dashboard":
        from . import dashboard
        dashboard.export()
    elif args.step == "causes":
        from . import causes
        causes.export()
    elif args.step == "ncaa-injuries":
        from . import ncaa_injuries
        print(json.dumps(ncaa_injuries.export()))
    elif args.step == "moments":
        from . import moments
        print(json.dumps(moments.export(reuse=args.reuse)))
    elif args.step == "fetch-college":
        from . import covers, sources
        results = sources.fetch(sources.COLLEGE_SEASONS, kinds=list(sources.COLLEGE_FILES))
        print(json.dumps({"files": len(results), "problems": [r for r in results if r["status"] not in ("cached", "downloaded")],
                          "new_covers_copies": covers.fetch()}))
    elif args.step == "college-moments":
        from . import college
        print(json.dumps(college.export()))
    elif args.step == "moments-dashboard":
        from . import moments_dashboard
        moments_dashboard.export()
    elif args.step == "report-site":
        from . import report_site
        report_site.build()
    elif args.step == "site":
        from . import site_build
        site_build.build()
    elif args.step == "linkedin":
        from . import linkedin
        linkedin.export()
    elif args.step == "board":
        import pandas as pd
        from . import board, features
        suffix, key = ("_after_game", "after_game_gbm") if args.after_game else ("", "full_gbm")
        feats = features.ALL + features.PBP + features.CURRENT if args.after_game else features.ALL
        results = json.loads((paths.OUTPUTS / f"results_{args.target}{suffix}.json").read_text(encoding="utf-8"))
        rows = pd.read_parquet(paths.PROCESSED / "rows.parquet")
        fitted = board.fit_final(rows, args.target, results["models"][key]["settings"], feats)
        table = board.board(rows, fitted, feats, args.date, args.top, outcome=args.target)
        pd.set_option("display.width", 250)
        pd.set_option("display.max_colwidth", 110)
        print(table.assign(risk=table["risk"].map("{:.0%}".format)).to_string(index=False))


if __name__ == "__main__":
    main()
