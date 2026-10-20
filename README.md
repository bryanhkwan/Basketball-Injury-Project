# Basketball Injury Project

What public data can say about when, and why, basketball players get hurt. The project has three parts:

- **Injury risk:** an NBA injury-risk model.
- **Injury types:** a study of who gets which injuries, and when.
- **Injury moments:** a test that finds the plays that come right before injuries in NBA play-by-play, then
  checks them in college basketball against a plan written down before any college results.

**Read the report:** https://bryanhkwan.github.io/Basketball-Injury-Project/. Its source is `docs/index.html`,
built by `python -m injury_risk report-site`.

## How the repository works

Everything is one Python package, `src/injury_risk/`. Each step is a command: `python -m injury_risk <step>`.

| Stage | Steps | What they do |
|---|---|---|
| Data | `fetch-data`, `fetch-reports`, `parse-reports`, `fetch-college` | Download the public sources into `data/`, which is not in the repository (see below) |
| Risk model | `build`, `train`, `board` | Labels and features, the model and its scores, and a nightly risk board |
| Injury types | `causes` | Who gets which injuries, and when |
| Injury moments | `moments`, `college-moments` | The NBA test, then the college test |
| Report | `moments-dashboard`, `report-site` | The report's data in `outputs/moments_dashboard/`, then the page in `docs/` |

Where things are:

- `docs/`: the report page, the college test plan with its SHA-256 fingerprint, and a hand-read sample of college
  cases.
- `outputs/`: the aggregate results everything is built from, such as `summary.json` files, model metrics and
  `RESULTS.md`.
- `tests/`: run them with `python -m unittest discover -s tests`.

Setup: Python 3.11 or newer, `pip install -r requirements.txt`, and `PYTHONPATH=src`.

## Data sources and terms

This repository has the code and the aggregate results, not the data. `data/` holds the downloads and is never
committed; the `fetch-*` steps rebuild it on your own machine.

| Source | What it gives | How it's collected |
|---|---|---|
| The NBA's official injury reports | Why each player missed each game | The league's public PDFs, one per game day, with a pause between downloads (`report_download.py`) |
| [sportsdataverse data releases](https://github.com/sportsdataverse/sportsdataverse-data) | NBA and NCAA play-by-play, box scores, rosters and schedules | Release files downloaded from GitHub (`sources.py`) |
| Covers' college injury page, through the [Internet Archive's Wayback Machine](https://web.archive.org/) | College injuries, 2019-20 to 2025-26 | Saved copies read from archive.org, 2.5 seconds apart (`covers.py`); covers.com itself is never contacted |
| SCACCHoops' conference injury pages | The current college injury list | One pass over 31 pages, a second apart (`ncaa_injuries.py`) |

- **What's published:** only statistics computed from these sources, in the report and `outputs/`. The listings
  and pages themselves are never published.
- **Your use:** if you run the download steps, follow each source's terms.
- **Affiliation:** this project is not affiliated with the NBA, the NCAA, Covers, SCACCHoops or the sportsdataverse
  project. If you represent one of them and want something changed, please open an issue.

## The injury-risk model

Before each game, the chance that a player suffers a **new injury that makes the player miss one of the
team's next 5 games** (also scored over 14 days, and for injuries costing 3+ games), built from the NBA's
official injury reports, box scores, inactive lists and the schedule.

## Question and target

- A row is a game a player played, scored as of tip-off: only earlier games feed the features, plus facts
  about the game fixed in advance (rest, back-to-back, travel, altitude, the schedule ahead).
- The main target (`g5`) is whether an injury *onset* falls in the team's next 5 games. An onset is the
  first game of a run of missed games that the official report puts down to an injury (not illness, rest,
  load management, G League, personal or suspension), counted only if the player had played in the previous
  14 days, so a long absence is one injury, not many. Counting games rather than days keeps a busy or
  quiet stretch of schedule from deciding the answer (with a 14-day window, the number of games ahead was
  the strongest feature).
- A row without 5 later team games that season (season over, waived) is left out: a missed game could not
  be seen.

## Data

| What | Source | Seasons |
|---|---|---|
| Why a player missed a game (status, body part, injury) | Official NBA injury report PDFs, one per game day (`ak-static.cms.nba.com`) | Dec 17, 2018 to 2025-26 |
| Minutes and box score per player-game, DNP comment | stats.nba.com box scores via the [sportsdataverse data releases](https://github.com/sportsdataverse/sportsdataverse-data) | 2016-17 to 2025-26 |
| Who did not dress | stats.nba.com inactive lists (same releases) | same |
| Birth date, height, weight, position, experience | stats.nba.com team rosters (same releases) | same |
| Where each game was played (bubble, Tampa, Mexico City, Paris, Las Vegas...) | ESPN schedules (same releases) | same |
| Who was on the floor for every play (stints, late-game minutes, rim attacks, transition, early exits) | stats.nba.com play-by-play and possessions (same releases) | same |

stats.nba.com refuses scripted requests, so the mirrored releases stand in for it. Downloads check HTTPS against
the system certificate store (`src/injury_risk/net.py`), which also works behind antivirus that re-signs HTTPS.

## Run

```powershell
$env:PYTHONPATH = "src"
python -m injury_risk fetch-data       # season parquet files -> data/raw/sportsdataverse
python -m injury_risk fetch-reports    # one injury report PDF per game day -> data/raw/injury_reports
python -m injury_risk parse-reports    # -> data/interim/report_rows.parquet
python -m injury_risk build            # labels + features -> data/processed/rows.parquet
python -m injury_risk train            # before the game, next 5 games -> outputs/results_g5.json
python -m injury_risk train --target g1 --after-game   # right after the game: miss the next one?
python -m injury_risk board --date 2026-03-10            # highest-risk players that night, with reasons
python -m injury_risk board --date 2026-03-10 --target g1 --after-game
python -m injury_risk causes           # injury types: who and when -> outputs/causes
python -m injury_risk moments          # what players were doing just before leaving hurt -> outputs/moments
python -m unittest discover -s tests -v
```

## Dashboards

The results were also built as private interactive dashboards for coaches and staff:
- `python -m injury_risk dashboard` writes the risk model's data: accuracy, calibration, the nightly risk board,
  player timelines and risk factors.
- `causes` and `moments-dashboard` write the data for the other two dashboards.

The public version of the findings is the report page in `docs/`.

## Why players get hurt (injury types)

`python -m injury_risk causes` (`src/injury_risk/causes.py`) groups new injuries the way coaches talk
about them (pulled muscles, sprained ankles and feet, knocks and collisions, knee, back, other aches) and
asks, for 2019-20 to 2025-26:

- **When**: each player compared with himself in the same month (Mantel-Haenszel over player-month
  strata), so who the player is and the calendar drop out. Late season uses player-season strata. First
  games back compare games 1-3 with games 4-10 after the same returns, since inside a month a return
  always follows its injury.
- **Who**: players compared with one another, intervals from resampling whole players.
- A finding counts only if its interval excludes no difference and it points the same way in 2019-22 and
  2022-26. The 7-day vs 28-day minutes ratio is left out: its swings track openers, breaks and other
  absences, and gave results no one could act on.

Results are in `outputs/causes/*.json`. They are associations, not proof.

## NCAA injury watch

`python -m injury_risk ncaa-injuries` (`src/injury_risk/ncaa_injuries.py`) takes one pass over
SCACCHoops' 31 Division I conference injury pages, which list player, injury (a body part), Out or
Questionable and rarely details, with no dates. To tell a listing left over from last season from a new
one, each is looked up in up to 12 Wayback Machine copies of its conference page from the past 400 days.
The output, `outputs/ncaa_injuries/listings.json`, stays local: it lists named players, so it isn't
committed.

The October 19, 2026 snapshot: 293 listings (41 out, 252 questionable) in 29 conferences. 139 were
already on an offseason copy of their page (most copies are from March to June 2026), so they are
probably stale. 91 are "Undisclosed" and 39 "Not injury related"; knee is the most common named injury
(46). The CAA page has no saved copies, and the newest Sun Belt and Ohio Valley copies are from October
2025. It shows current listings only: an injury history needs the pages collected every day from the
season opener.

## Evaluation

Train on 2018-19 (from January 15, a month into the report archive) to 2022-23, choose settings on
2023-24, refit on all of them and score 2024-25 and 2025-26, which no setting ever saw. Feature ideas were
judged on 2023-24 only; the test seasons were scored once at the end. Scores are on probabilities: AUC (with a 95% interval that resamples
whole players), average precision, Brier skill against the base rate, log loss, the injury rate among the
top 10% of risk scores relative to everyone, and calibration by decile. The bar to clear is a logistic
model on age and injury history alone.

## Results (October 19, 2026)

Full tables, calibration and feature importance: `outputs/RESULTS.md`. Test seasons 2024-25 and 2025-26,
never used for any choice:

| Target | Base rate | Age + injury history | Best model (gradient boosting) |
|---|---|---|---|
| New injury in the team's next 5 games (`g5`) | 16.1% | AUC 0.668 | **AUC 0.704** (0.690-0.721), top 10% of scores 2.3x the average rate |
| Same, injuries costing 3+ games (`g5_3plus`) | 6.6% | AUC 0.615 | AUC 0.651 (0.631-0.671), top 10% 1.9x |
| New injury in the next 14 days (`y14`) | 19.0% | AUC 0.668 | AUC 0.724 (0.709-0.738), top 10% 2.3x |

- Calibrated: on the test seasons each decile of predicted risk lands within about 2 points of what
  happened (top decile 37.9% predicted, 37.3% observed).
- Risk board (`python -m injury_risk board --date 2026-03-10`): over the held-out 2025-26 season, each
  night's 15 highest-risk players had a new injury within 5 games 25.9% of the time against 15.6% for all
  players (3+ game injuries 9.5% against 6.2%); each night's 15 lowest, 4.9%.
- Where the signal is (2023-24 ablation): injury history carries most of it (alone AUC 0.679), then
  workload (0.646). Schedule, body size and playing style add little once those are in. Logistic regression
  scores the same as boosting: the signal is mostly additive.
- Plain rates, 2019-20 to 2025-26: a player in the first 2 games back from an injury has a 23% chance of a
  new one within 5 games (1.6x average); 4+ injuries in the past year, 27% (1.8x); 32+ minutes a game,
  22%; no injury on record, 6%. The second night of a back-to-back shows no extra risk, and the acute to
  chronic minutes ratio no clear pattern.
- Same-day injury report status adds almost nothing (AUC +0.002): games played while listed in the
  previous three weeks already carry it.

### Play-by-play (added October 19, 2026)

Every play lists the ten players on the floor, so each player-game gets its stints (count, longest,
average), fourth-quarter and overtime minutes, rim attacks and dunks, transition chances on the floor,
possessions on the floor, and whether a starter left a close game before the fourth quarter
(`src/injury_risk/pbp.py`; minutes rebuilt this way match the box score to a median 0.02 minutes).

- **Before the game it adds nothing**: next-5-games AUC 0.704 with or without it (2023-24 validation
  0.7022 to 0.7020; test 0.7037 to 0.7044). Longest stint tracks minutes, which the model already has, and
  rim attacks, transition, overtime and close games carry no extra injury signal.
- **Right after the game it adds a lot.** A starter who leaves a close game early misses the next game
  with an injury 17% of the time, against 3.9% for other starters, but 77% of early leavers play the next
  game and are then at no higher risk. The signal is an injury that has already happened, so it answers a
  different question: who is likely to miss the next game? On the test seasons:

| Miss the team's next game with a new injury (3.7%) | AUC (95% CI) | Avg precision | Top 10% catches |
|---|---|---|---|
| Scored before the game | 0.704 (0.690-0.719) | 0.097 | 27% |
| Scored right after it, with its play-by-play | **0.762 (0.749-0.775)** | 0.222 | 39% |

  Calibrated (top decile 14.6% predicted, 14.4% observed); 0.766 in 2024-25 and 0.758 in 2025-26. Its
  main input is when the player was last on the floor. The game's own play-by-play (`CURRENT` features)
  never enters a before-the-game score; a test guards that.
- A three-pointer never counts as a rim attack. Until October 19, 2026 it could: threes with no distance in
  the description have distance 0, not missing, so about 1 in 6 "rim attempts" were threes. After the fix
  the after-game AUC moved from 0.7617 to 0.7623, and "attacks the rim the most" in the injury-type study
  from 1.21x to 1.24x (knee injuries now show it too: 1.34x).

## What players were doing when they got hurt (play-by-play test)

`python -m injury_risk moments` (`src/injury_risk/moments.py`) asks whether the play-by-play can show what
a player was doing when he got hurt.

- **Injury exit:** he left a competitive game early for good (6+ minutes left, within 15 points, not ejected
  or fouled out), finished under 60% of his usual minutes, and the team's next game was the first he missed
  with a new injury.
- **Comparison:** each injury exit against the same player's ordinary exits that season, the plays he was
  credited with in the 30 seconds before each (Mantel-Haenszel over player-seasons, Benjamini-Hochberg
  across the table).
- **A finding needs** q < 0.05, 10+ exposed exits, and the same direction in 2019-22 and 2022-26. It is
  then checked within the same kind of stoppage, against "null exits" (a random moment on the floor followed
  by the first dead ball), against other injury exits, and against early exits with no injury after them.
- **Definition checks:** for the groups with a finding (any, ankle, muscle, hand), the test is re-run with
  other minutes rules (under 50%, 75% or 80% of usual minutes, or none) and on substitution exits only. The
  hand rows were added on 2026-10-20, after the dashboard review found the page claiming checks that had not
  been run for hands. The hand result holds in all of them; the weakest is 1.43 (1.02-2.02) with no minutes
  rule. `python -m injury_risk moments --reuse` recomputes the statistics from the saved moments without
  rebuilding them from the play-by-play; every earlier number came out identical.
- **Who is on the floor** comes from each period's starters and the substitution log, with names matched
  against the box score. Minutes rebuilt this way match the box score to a median of 0.00.

Results, 2019-20 to 2025-26:

- **How many can be pinned:** 981 of 6,536 new injuries (15%) end in an injury exit. The pattern turns up
  before 17.2% of new injuries, against 3.7% of games followed by a normal game, so about 79% are beyond
  chance. Most are first-half injuries (84% in Q1-Q2). Ankle (19%) and head (25%) injuries show up most.
- **Established:**
  - Ankle injuries after being fouled: 9.2% vs 2.2%, OR 4.8, and 2.4 against other injury exits.
  - A steal, for all injuries together: 4.0% vs 1.6%, OR 2.5. It fits the break or scramble after it.
  - Hand, wrist, finger and arm injuries while the other team attacked the rim: 52% vs 32%, OR 2.2, on 71
    exits.
- **A lead:** pulled muscles after a drive or cut. 11.1% vs 6.3%, OR 1.9, q 0.049, on 22 exits.
- **Not shown:** ankle injuries after rebounds, the NCAA research's top activity. 13.9% vs 10.0%, OR 1.5,
  q 0.14.
- **Signs of an injury, not causes:** a take foul to stop play, and losing the ball or traveling.
- **Size:** the established patterns cover about 60 injuries in seven seasons, about 9 a season
  league-wide.

The play-by-play credits only plays a player is given. It cannot show landing on a foot, collisions, cuts
without the ball, or rebounds someone else won, and most injuries never end a player's night early. Results
are in `outputs/moments/summary.json`. The per-exit files (`*.parquet`) are rebuilt locally and not committed.

## The same test on college games (Division I men's basketball)

Run `python -m injury_risk fetch-college`, then `python -m injury_risk college-moments`. The code is in
`src/injury_risk/college.py` and `covers.py`. The patterns to test and the rules were fixed before any
college result: `docs/ncaa_moments_plan.md`, fingerprints in `docs/ncaa_moments_plan.sha256`. A hand-read
sample is in `docs/ncaa_moments_hand_read.md`.

- **Data:**
  - The NCAA's official play-by-play, 2019-20 to 2025-26, from the sportsdataverse mirror. Substitutions
    come with player ids, plus fouls drawn, shot descriptors and both lineups.
  - The NCAA box scores.
  - The 191 saved copies of Covers' injury page, matched to the games each player missed.
- **Quality:**
  - Games are kept when rebuilt minutes match the box score: 72-88% of games a season, with 97.5% of
    kept player-games within a minute.
  - All 394 Covers teams matched; 86% of named-injury listings matched to a player.
  - 1,746 labelled new injuries, of which 328 are injury exits (21% of those that could be checked).
  - The early-exit pattern comes before 30.3% of new injuries, against 4.7% of games followed by a normal
    one.

Results under the fixed plan (30 seconds before leaving, odds ratio against the same players' ordinary
exits, Holm across H1-H4):

| Hypothesis | College | NBA | Verdict |
|---|---|---|---|
| H1 Ankle, after drawing a foul | 12.9% vs 6.1%, 2.22 (1.09-4.53), Holm 0.085 | 4.8 | Same direction, not shown |
| H2 Any injury, after a steal | 3.0% vs 2.0%, 1.56 (0.82-2.98), Holm 0.18 | 2.5 | Same direction, not shown |
| H3 Hand, defending a shot at the rim | 44% vs 25%, 2.46 (1.09-5.58), Holm 0.085 | 2.2 | Same direction, not shown |
| H4 Pulled muscle, after a drive | 12% vs 1.7%, 8.35 (2.11-33.1), Holm 0.010 | 1.9 | Replicates (3 cases) |
| H5 Ankle, after a rebound (secondary) | 14.3% vs 9.4%, 1.75 (0.88-3.50) | 1.5 | Not shown |

What the table alone doesn't say:

- **Power:** at the NBA's effect sizes, power was 99% (H1), 86% (H2), 48% (H3) and 16% (H4).
- **H1 in college:** the college ankle-foul effect is smaller than the NBA's. It comes from players leaving
  at the whistle without shooting their own free throws (6 of 70, OR 3.4) or with a teammate shooting
  them. Shooting their own and then leaving, the NBA form, shows nothing (OR 0.4).
- **H4 rests on three fast-break finishes:**
  - Seton Hall's Myles Cale, groin;
  - UCLA's Jaylen Clark, Achilles;
  - SMU's Zhuric Phelps, quad.

  Removing any one, or using stricter labels, drops it below the bar. The exact test gives Holm 0.036.

Added after the results, not in the plan:

- **Pooled estimate:** all five patterns together give OR 1.94 (1.35-2.79), and 1.91 without H4. Together,
  the NBA patterns do show up before college injury exits, at a smaller size.
- **Signs of an injury exit:**
  - leaving at a stoppage the log doesn't record, probably officials stopping play for him: 40% vs 18%,
    OR 3.1, and no different after early exits with no injury;
  - being the only player his team took out: 66% vs 45%;
  - a teammate shooting the free throws of a foul he drew: 2.4% vs 0.0%.
- **Bugs fixed before this final run, found by an independent review:** phantom halftime exits, names with
  punctuation, and stoppage labels. The first run's verdicts were the same.

Limits:

- Covers lists far fewer injuries than the NBA reports, and the saved copies are sparse in 2022-23 and
  2024-25.
- Old-format NCAA logs (mostly 2019-21) can't show fouls drawn or drives.
- Only about a third of college injuries happen in games.

## The report's data

`python -m injury_risk moments-dashboard` (`src/injury_risk/moments_dashboard.py`) turns the NBA and college
`summary.json` files into the seven small data files in `outputs/moments_dashboard/`. The report page is built from
those files.

The eight example stories were checked against the raw play-by-play, from two minutes before each exit to 30
seconds after it. Anything that only news reports show is marked "reports say".

## The report page

`python -m injury_risk report-site` (`src/injury_risk/report_site.py`, with the page's text, styles and charts in
`src/injury_risk/site/`) builds `docs/index.html`. It is a single page with the charts, tables and data inline, built
from the same files as the dashboard, and it ends with the conclusions and the limits.

- **Publishing:** push the repository and turn on GitHub Pages (Settings > Pages > Deploy from a branch > `main`,
  `/docs`).
- **Links:** they assume the repository is `bryanhkwan/Basketball-Injury-Project`. Otherwise change `REPO_URL` and
  `SITE_URL` in `report_site.py` and rebuild.

`python -m injury_risk linkedin` (`linkedin.py`) uses headless Chrome to render the page's link-preview card,
`docs/assets/social-card.png`, along with sharing images that are kept local.

## Limits

- Listed injuries rose from 30 to about 40 per 1,000 player-games between 2019-20 and 2025-26, partly
  reporting practice (the 2023 participation policy asks teams to name a reason). Recalibrate each season.
- Many one-game "soreness" absences are probably planned rest under another name; the 3+ game target is
  the stricter test.
- An injury in a team's last game of the season cannot be seen (no game to miss).
- About 200 report reasons such as "Injury Recovery" or "Maintenance" still count as new injuries in the
  risk model's labels when the player had played recently. The play-by-play test leaves them out, along with
  a dozen non-injury reasons the parser files under "other" (personal reasons, influenza, dental).
- No practice load, wearables, per-game tracking (distance, speed) or medical detail: these are what teams
  have and the public does not, and the likely route above about 0.70.
