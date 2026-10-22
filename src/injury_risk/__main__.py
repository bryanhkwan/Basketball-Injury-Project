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
    sub.add_parser("validate", help="the play-by-play patterns and the model checked against the news "
                                    "-> outputs/validation/summary.json")
    sub.add_parser("aftermath", help="what an injury does to a career: time out, coming back, durability and staying in "
                                     "the league, against matched players -> outputs/aftermath/summary.json")
    sub.add_parser("college-aftermath", help="the same for Division I players: time out, coming back, the next season and "
                                             "the NBA -> outputs/college_aftermath/summary.json")
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
    sub.add_parser("profiles", help="player profiles: NBA injury histories, college players Covers listed, and players in both "
                                    "-> outputs/profiles/*.json")
    sub.add_parser("news-targets", help="the injuries worth looking up in the news, in tiers, with a 50-injury pilot "
                                        "-> outputs/news/targets.jsonl (see specs/injury-news.md)")
    sub.add_parser("news-check", help="check the news research (outputs/news/facts.jsonl, data/news/evidence.jsonl) "
                                      "against the rules, and report what it found")
    sub.add_parser("news-summary", help="how NBA players got hurt, from the news research, in numbers "
                                        "-> outputs/news/summary.json")
    p = sub.add_parser("news-research", help="check and file the reviewed injury news (data/news/reviews) for the pilot or a tier")
    which = p.add_mutually_exclusive_group(required=True)
    which.add_argument("--pilot", action="store_true", help="the 50 pilot injuries")
    which.add_argument("--tier", type=int, choices=(1, 2, 3), help="one tier of the plan, in priority order (specs/injury-news.md)")
    p.add_argument("--league", choices=("nba", "college"), help="with --tier: only this league")
    p.add_argument("--refile", action="store_true", help="file the selected reviews again after correcting them")
    p.add_argument("--report", action="store_true", help="write the pilot report after recorded validation passes")
    p = sub.add_parser("news-fetch", help="read pages into data/news/cache, only where robots.txt allows; text, not HTML")
    p.add_argument("urls", nargs="+")
    p = sub.add_parser("news-audit", help="an audit sheet for a random sample of one research batch -> data/news/audits/")
    p.add_argument("batch", help="the batch's name in data/news/batches.jsonl")
    p.add_argument("--n", type=int, default=15)
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
    elif args.step == "validate":
        from . import validation
        validation.export()
    elif args.step == "aftermath":
        from . import aftermath
        aftermath.export()
    elif args.step == "college-aftermath":
        from . import college_aftermath
        college_aftermath.export()
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
    elif args.step == "profiles":
        from . import profiles
        profiles.export()
    elif args.step == "news-targets":
        from . import news, news_research
        news.export_targets()
        print(json.dumps(news_research.follow_moves()))
    elif args.step == "news-check":
        from . import news
        result = news.run_check()
        raise SystemExit(1 if result["errors"] else 0)
    elif args.step == "news-summary":
        from . import news_summary
        news_summary.export()
    elif args.step == "news-research":
        from . import news_research
        try:
            result = news_research.run(pilot=args.pilot, tier=args.tier, league=args.league, refile=args.refile)
            if args.report:
                if result["pending"] or not args.pilot:
                    raise SystemExit("the report covers the finished pilot; see data/news/pending.jsonl")
                news_research.write_report()
        except ValueError as error:
            raise SystemExit(str(error)) from error
    elif args.step == "news-fetch":
        from . import news_research
        refused = 0
        for url in args.urls:
            path, outcome = news_research.fetch(url)
            refused += path is None
            print(f"{url}\n  {outcome}" + (f": {path}" if path else ""))
        raise SystemExit(1 if refused else 0)
    elif args.step == "news-audit":
        from . import news_research
        try:
            print(news_research.audit_sheet(args.batch, n=args.n))
        except ValueError as error:
            raise SystemExit(str(error)) from error
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
