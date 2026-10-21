# Basketball Injury Project

What public data can say about when, and why, basketball players get hurt. The project has three parts:

- **Injury risk:** an NBA injury-risk model.
- **Injury types:** a study of who gets which injuries, and when.
- **Injury moments:** a test that finds the plays that come right before injuries in NBA play-by-play, then
  checks them in college basketball against a plan written down before any college results.

**See it live:** https://bryanhkwan.github.io/Basketball-Injury-Project/

- **Overview** (`docs/index.html`): what the project found, with the risk board for any night of 2025-26.
- **Dashboards** (`docs/dashboard.html`): the nightly risk board, the model check, what raises risk, when and who gets
  hurt, injury types, how each injury happened (from the news), what an injury does to a career, NBA vs college (every
  play before every kind of injury, in both leagues), and a profile for every NBA player since 2018-19 and every
  college player Covers listed injured, with what the news says about each injury.
- **Report** (`docs/moments.html`): the injury-moment study, with its conclusions.

`python -m injury_risk site` builds all three.

## How the repository works

Everything is one Python package, `src/injury_risk/`. Each step is a command: `python -m injury_risk <step>`.

| Stage | Steps | What they do |
|---|---|---|
| Data | `fetch-data`, `fetch-reports`, `parse-reports`, `fetch-college` | Download the public sources into `data/`, which is not in the repository (see below) |
| Risk model | `build`, `train`, `board` | Labels and features, the model and its scores, and a nightly risk board |
| Injury types | `causes` | Who gets which injuries, and when |
| Injury moments | `moments`, `college-moments` | The NBA test, then the college test |
| Player profiles | `profiles` | Every NBA player's injury history, the college players Covers listed, and the players found in both (after `college-moments`) |
| Injury news | `news-targets`, `news-fetch`, `news-research`, `news-audit`, `news-check`, `news-summary` | The injuries worth looking up in the news, a page reader that obeys each site's robots.txt, filing the research a batch at a time, an audit sample of each batch, the checks on what it finds (`specs/injury-news.md`), and how the injuries happened, in numbers |
| Checks | `validate` | The play-by-play patterns and the model checked against what the news says happened |
| Careers | `aftermath` | What happened after each injury: time out, how players came back, getting hurt again and staying in the league |
| Site | `dashboard`, `moments-dashboard`, `site` | The dashboards' and the report's data in `outputs/`, then the public site in `docs/` (`report-site` rebuilds the report alone) |

Where things are:

- `docs/`: the public site (overview, dashboards, report) and its data in `docs/data/`, the college test plan with its
  SHA-256 fingerprint, and a hand-read sample of college cases.
- `DESIGN.md`: the site's design system (colours, type, layout, components and rules).
- `AGENTS.md` and `specs/`: instructions for coding agents working here, and the specs of work in progress.
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

- **What's published:** statistics computed from these sources, in the site and `outputs/`. The site also has player
  profiles (`docs/data/`): each NBA player's injuries as the official reports list them, and for 2025-26 their model
  risk game by game; and each college player Covers listed injured, with only the listings' facts (dates, body part,
  the status in plain words) and the games missed from the box scores. Covers' own wording, the listings and the
  pages themselves are never published.
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

The public dashboards (`docs/dashboard.html`) are built from three data files that `site` writes to `docs/data/`:
- `python -m injury_risk dashboard` writes the risk model's data to `outputs/dashboard/` (accuracy, calibration, the
  nightly risk board, player timelines and risk factors). It stays local; `site` publishes a compact copy as
  `board.json`, `players.json` and part of `study.json`.
- `causes` and `moments-dashboard` write the injury types' and the injury moments' data, which go into `study.json`.

## Why players get hurt (injury types)

`python -m injury_risk causes` (`src/injury_risk/causes.py`) groups new injuries the way coaches talk
about them (pulled muscles, sprained ankles and feet, knocks and collisions, knee, back, other aches) and
asks, for 2019-20 to 2025-26:

- **When**: each player compared with their own games in the same month (Mantel-Haenszel over player-month
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

## Results (October 21, 2026)

Full tables, calibration and feature importance: `outputs/RESULTS.md`. Test seasons 2024-25 and 2025-26,
never used for any choice:

| Target | Base rate | Age + injury history | Best model (gradient boosting) |
|---|---|---|---|
| New injury in the team's next 5 games (`g5`) | 16.0% | AUC 0.669 | **AUC 0.703** (0.689-0.719), top 10% of scores 2.3x the average rate |
| Same, injuries costing 3+ games (`g5_3plus`) | 6.6% | AUC 0.619 | AUC 0.649 (0.629-0.668), top 10% 1.9x |
| New injury in the next 14 days (`y14`) | 18.9% | AUC 0.670 | AUC 0.726 (0.712-0.739), top 10% 2.3x |

- Calibrated: on the test seasons each decile of predicted risk lands within about 2 points of what
  happened (top decile 38.3% predicted, 37.0% observed).
- Risk board (`python -m injury_risk board --date 2026-03-10`): over the held-out 2025-26 season, each
  night's 15 highest-risk players had a new injury within 5 games 26.3% of the time against 15.5% for all
  players (3+ game injuries 9.0% against 6.2%); each night's 15 lowest, 5.2%.
- Where the signal is (2023-24 ablation): injury history carries most of it (alone AUC 0.678), then
  workload (0.645). Schedule, body size and playing style add little once those are in. Logistic regression
  scores the same as boosting: the signal is mostly additive.
- Plain rates, 2019-20 to 2025-26: a player in the first 2 games back from an injury has a 23% chance of a
  new one within 5 games (1.6x average); 4+ injuries in the past year, 27% (1.8x); 32+ minutes a game,
  22%; no injury on record, 6%. The second night of a back-to-back shows no extra risk, and the acute to
  chronic minutes ratio no clear pattern.
- Same-day injury report status adds almost nothing (AUC +0.002): games played while listed in the
  previous three weeks already carry it.
- **It flags who gets hurt, not how** (`python -m injury_risk validate`). On the test seasons it ranks the games before
  a strain (AUC 0.695, 242 injuries) no better than those before a knock or a concussion (0.702, 193), and the news's
  non-contact injuries (0.570, 17) no better than its contact ones (0.715, 52). Its signal is exposure (who plays a
  lot) and fragility (who has been hurt), which bring collisions and fractures as surely as strains: rest can't be
  expected to prevent what it flags.

### Play-by-play (added October 19, 2026)

Every play lists the ten players on the floor, so each player-game gets its stints (count, longest,
average), fourth-quarter and overtime minutes, rim attacks and dunks, transition chances on the floor,
possessions on the floor, and whether a starter left a close game before the fourth quarter
(`src/injury_risk/pbp.py`; minutes rebuilt this way match the box score to a median 0.02 minutes).

- **Before the game it adds nothing**: next-5-games AUC 0.703 with or without it (2023-24 validation
  0.7044 to 0.7049; test 0.7027 to 0.7027). Longest stint tracks minutes, which the model already has, and
  rim attacks, transition, overtime and close games carry no extra injury signal.
- **Right after the game it adds a lot.** A starter who leaves a close game early misses the next game
  with an injury 17% of the time, against 3.9% for other starters, but 77% of early leavers play the next
  game and are then at no higher risk. The signal is an injury that has already happened, so it answers a
  different question: who is likely to miss the next game? On the test seasons:

| Miss the team's next game with a new injury (3.7%) | AUC (95% CI) | Avg precision | Top 10% catches |
|---|---|---|---|
| Scored before the game | 0.704 (0.690-0.719) | 0.096 | 27% |
| Scored right after it, with its play-by-play | **0.764 (0.750-0.777)** | 0.223 | 39% |

  Calibrated (top decile 14.6% predicted, 14.3% observed); 0.767 in 2024-25 and 0.761 in 2025-26. Its
  main input is when the player was last on the floor. The game's own play-by-play (`CURRENT` features)
  never enters a before-the-game score; a test guards that.
- A three-pointer never counts as a rim attack. Until October 19, 2026 it could: threes with no distance in
  the description have distance 0, not missing, so about 1 in 6 "rim attempts" were threes. After the fix
  the after-game AUC moved from 0.7617 to 0.7623, and "attacks the rim the most" in the injury-type study
  from 1.21x to 1.24x (knee injuries now show it too: 1.34x).
- A long reason that wraps past the foot of a report page is read whole. From the 2023 playoffs to October 20,
  2026 its last words went to the first player on the next page (Haliburton's "Right Achilles Tendon; Tear" became
  "Right Achilles Tendon;", and the next player's concussion, "Tear Injury/Illness - ...", read as an illness), and
  words next to a "NOT YET SUBMITTED" line were dropped. 992 reasons got their words back. 82 new-injury labels came
  out and 21 went in (some are the same injury on a corrected date), and 118 injuries regained 1,413 games missed,
  all in 2023-24 to 2025-26. Test AUCs: next 5 games 0.7037 to 0.7032; 3+ games 0.6513 to 0.6526 (top 10% 1.92x
  to 2.03x); 14 days 0.7244 to 0.7248; after the game 0.7623 to 0.7615.
- A listing is sorted by the body part the team names before its semicolon, and a word inside another word no
  longer counts. Until October 21, 2026 "whiplash" was the hip, "discomfort" a spinal disc, "Tear" an ear and a
  "Gastrocnemius" (calf) strain a stomach illness. 110 of the 176 reasons with no body part found one. 58 reasons
  that are not injuries (personal reasons, the G League, reconditioning, flu, infections, an appendectomy, a medical
  condition; 286 report rows) stopped counting as injuries, 17 that name an injury beside an illness started to (32
  rows), and "Injury Recovery" stopped counting as a surgery (2,744 rows). New injuries went from 7,222 to 7,194. Test AUCs: next 5 games 0.7032 to 0.7027; 3+ games 0.6526 to 0.6487 (top 10% 2.03x to 1.89x,
  inside its interval; with play-by-play the same target went 0.6546 to 0.6550); 14 days 0.7248 to 0.7264; after
  the game 0.7615 to 0.7638.

## What players were doing when they got hurt (play-by-play test)

`python -m injury_risk moments` (`src/injury_risk/moments.py`) asks whether the play-by-play can show what
a player was doing when they got hurt.

- **Injury exit:** the player left a competitive game early for good (6+ minutes left, within 15 points, not ejected
  or fouled out), finished under 60% of their usual minutes, and the team's next game was the first they missed
  with a new injury.
- **Comparison:** each injury exit against the same player's ordinary exits that season, the plays they were
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

- **How many can be pinned:** 985 of 6,470 new injuries (15%) end in an injury exit. The pattern turns up
  before 17.3% of new injuries, against 3.7% of games followed by a normal game, so about 79% are beyond
  chance. Most are first-half injuries (about 84% in Q1-Q2). Ankle (19%) and head (26%) injuries show up most.
- **Established:**
  - Ankle injuries after being fouled: 9.1% vs 2.2%, OR 4.8, and 2.4 against other injury exits.
  - A steal, for all injuries together: 4.0% vs 1.6%, OR 2.5. It fits the break or scramble after it.
  - Hand, wrist, finger and arm injuries while the other team attacked the rim: 52% vs 32%, OR 2.2, on 71
    exits.
- **A lead:** pulled muscles after a drive or cut. 11.1% vs 6.2%, OR 1.9, q 0.046, on 22 exits.
- **Not shown:** ankle injuries after rebounds, the NCAA research's top activity. 13.8% vs 10.0%, OR 1.5,
  q 0.16.
- **Signs of an injury, not causes:** a take foul to stop play, and losing the ball or traveling.
- **Checked against the news** (`python -m injury_risk validate`, `outputs/validation/summary.json`): 129 pinned exits
  have a news report naming the play the injury came on. Where the play-by-play shows the player was fouled in the 30
  seconds before, the reports say the injury came on a foul in 6 of 19, against 5 of 110 otherwise (OR 9.7, p 0.001);
  a rebound, 7 of 17 against 6 of 112 (OR 12.4, p 0.0002). After their own steal, the reports describe the break or
  scramble that followed in 10 of 12 (OR 6.2, p 0.01), the steal itself in 1. Rim attacks by the other team (OR 4.2,
  p 0.06) and drives (OR 2.5, p 0.11) point the same way on fewer cases. Ankle injuries after a foul were mostly
  landing on someone's foot.
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

- **Power:** at the NBA's effect sizes, power was 99% (H1), 85% (H2), 48% (H3) and 16% (H4).
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
  - leaving at a stoppage the log doesn't record, probably officials stopping play for them: 40% vs 18%,
    OR 3.1, and no different after early exits with no injury;
  - being the only player the team took out: 66% vs 45%;
  - a teammate shooting the free throws of a foul the player drew: 2.4% vs 0.0%.
- **Every play, both leagues (exploratory):**
  - 141 play-and-injury pairs can be estimated in both leagues (30 seconds before the exit, against the same
    players' other exits).
  - Of the 33 with a clear NBA signal (a range that stays on one side of 1×), 28 point the same way in college.
  - All 11 that are clear in both leagues agree.
  - For any injury, where both leagues have the most cases, the two leagues' log odds ratios correlate at 0.72
    across 20 plays; across all 141 pairs, 0.29.
  - The pairs overlap (any injury includes the ankle ones, and a play and no play are opposites), so this is a
    pattern to test next, not a result. It is the dashboards' NBA vs college view.
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
seconds after it. Anything that only news reports show is marked "reports say". The public report tells the four NBA
stories; college players are on their own profiles.

## Player profiles

`python -m injury_risk profiles` (`src/injury_risk/profiles.py`) writes `outputs/profiles/`: `nba.json`, `college.json`
and `both.json`. It needs the processed NBA data and `outputs/college_moments/`.

**NBA: every player in the box scores since 2018-19 (1,326), not only the 2025-26 players the model scored.**
Players out all season (Kyrie Irving, Tyrese Haliburton, Fred VanVleet, Damian Lillard) had no profile before. Their
injuries come from the official reports' onsets, with these rules:
- A later listing of the same body region joins the injury before it if it is care of that injury ("Injury
  Recovery", "Management", "Repair") or came before the player played again.
- A long absence is named by what the reports listed most while it lasted. Leonard's 2021 "right knee sprain" was
  79 games of "ACL - injury recovery".
- A run of 5 or more games listed for another body region is a second injury. Thompson's left ACL, then his right
  Achilles, were one absence.
- Games missed are counted on the box scores until the next game played: injury, management and unlisted absences
  count, while illness, non-medical absences and coach's decisions don't (Irving's 2021-22 absences don't). The
  reports skip players out long term, so they undercount: Lillard's Achilles tear cost 89 games, and his listings
  show 10.
- Back is the next game played. The reports' return misses comebacks in the playoffs and with new teams.

"What usually happens next" gives, for each kind of injury:
- how many games it cost;
- how often players hurt the same body region again within a year of coming back, counting only returns with a
  full year to watch and only new injuries, not care of the old one.

For example, after a torn ACL (25 since 2018-19) the median was 85 games missed, and 6 of 16 players hurt the knee
again within a year of coming back (35% for any injury).

**College: every player Covers listed injured (1,788 players, 2,556 injuries).**
- Listings of one body part are grouped into one injury unless three weeks pass between them.
- A note left up into the next season stays with the season it was written in.
- A vague same-day listing ("Leg") joins the named one ("Knee").
- Games missed are the team games the player didn't play while listed, including those before their first game of a
  season.
- 385 injuries get a diagnosis from a fixed list, read from Covers' notes: 97 torn ACLs, 97 concussions, 93
  fractures and more, with the side and whether surgery was mentioned. That's the fact only, never the note's words.
- Covers' page was saved on 2 to 76 days a season, and each profile shows its seasons' counts.

**Both:** an NBA debut since 2020-21 is matched to a college career by these rules:
- the same name;
- a college career that ended 1 to 3 seasons before the debut;
- nobody else of that name in the NBA debut seasons, or in college in that final season or later;
- in an earlier season with two of that name, theirs is the one at the school they played for the season after (the
  box scores' player ids change every season). Until October 21, 2026 the earliest such season decided, which gave
  Jalen Williams of Santa Clara the Cleveland State Jalen Williams's college injury.

Common names like Jalen Johnson are left unmatched. 467 of 640 debuts were matched, 137 of them with a college
injury listing.

Exploratory finding: where the player's last college season was saved on 30 or more days, players with a college
injury on record had 3.2 new injuries per 100 games in their first two NBA seasons, against 2.1 for the others.
- That is 1.51× (1.05 to 2.09, resampling players), across 113 players.
- Across every season it is 1.17× (0.95 to 1.45). In thinly saved seasons, injured players count as never hurt.
- Not adjusted for position, age or minutes.

## What the news says about each injury

The injury reports often name only a body part ("Left knee soreness"). `specs/injury-news.md` sets out how each
injury worth it was looked up in the news: the injury itself, how it happened, surgery and timelines, every fact with
the quote and source behind it (`outputs/news/facts.jsonl`; the quotes stay local). Codex did the research in batches
of 150; each batch was checked by `news-check` and audited on a random 15 by someone who didn't research it, and four
batches that failed their audit were corrected. Finished October 21, 2026:

| Injuries | Researched | Diagnosis confirmed or reported | Vague listings now named | The game it happened in | How it happened |
|---|---|---|---|---|---|
| NBA, 10+ games or a major injury | 1,291 | 891 (45 more where reports and listing disagree) | 194 of 381 | 695 | 292 |
| NBA concussions | 143 | 105 | | 104 | 87 |
| College players now in the NBA | 201 | 67 | 51 of 172 | 96 | 47 |

College players who never reached the NBA (1,428 injuries) were left out: little was written about them, nothing in 8
of 8 tried, and they are students. One college row stays unfiled (a source misspells the player's name).

`python -m injury_risk news-summary` (`src/injury_risk/news_summary.py`) counts how the NBA injuries happened, by kind of
injury (`outputs/news/summary.json`): contact or not, the cause, what the player was doing, and what the vague listings
turned out to be. Each count says how many injuries it rests on; the news covers stars and long injuries best. The
dashboards' **How it happened** view shows it, and each player profile opens an injury to its facts and sources. Two
findings:
- **Ankle sprains come from someone’s foot.** 33 of the 58 with a known cause came from landing on or being stepped on
  by another player's foot, and 44 of 45 involved contact.
- **A torn Achilles happens alone.** 15 of 16 involved no contact, and so did 15 of 19 pulled muscles. Concussions,
  broken hands and shoulder injuries all came from contact.

## What an injury does to a career

`python -m injury_risk aftermath` (`src/injury_risk/aftermath.py`) asks what happened to players after an injury: how
long it kept them out, whether they came back the same, whether they got hurt again, and whether they stayed in the
league. It writes `outputs/aftermath/summary.json` and needs the processed NBA data, `outputs/profiles/` and the news
research.

**Which injuries.** Every NBA injury since 2018-19 that cost 10 or more games, every torn ACL, Achilles and meniscus
whatever it cost, and every concussion: 1,350 absences. 1,174 of them (510 players) had a year of games before them to
compare against.
- Listings that follow each other before the player plays again are one absence ("Right lower leg", then "Right
  Achilles surgery").
- The diagnosis is the news's where the research named it, else the listing's.
- 16 absences held two injuries in different parts of the body that each cost 10+ games (Klay Thompson's torn ACL,
  then torn Achilles). They count in the totals but not by diagnosis.

**How it compares.**
- Time out runs from the game the news says they were hurt in (else their last game, when the listing followed within
  ten days) to the next game they played. Days include any offseason in between, so a late-season injury looks longer
  in days than in games. Injuries with no return yet count as still out (Kaplan-Meier).
- Came back the same: the year before the injury against the first and second years back, in regular-season games,
  each with 15+ games and 200+ minutes. Players who never came back, or barely played, count in time out and careers
  but not here.
- Each change is set against the change over the same dates for the ten players most like them the day they were hurt:
  age, minutes, production per 36 minutes, and the share of their team's games they played. Those ten played within
  ten days of that day and in the years compared, so aging and league-wide trends drop out.
- A straight line fitted across everyone playing that day corrects what is left of the gap between the injured player
  and their ten (bias-corrected matching).
- Durability and careers use ten players matched the same way, whether or not they played on.
- Intervals are 95%, resampling players with all their injuries.

**Checks.**
- The injured and their matched players were alike on age, minutes and production (standardized differences 0.02 to
  0.06). On share of games played it was 75% against 71% (0.21), which the correction handles.
- Placebo: for each injury, five players who weren't hurt went through the same steps over the same dates. There was
  nothing to find, and the method found nothing:
  - minutes a game -0.03 (-0.27 to +0.20);
  - production per 36 +0.11 (-0.05 to +0.27);
  - hurt again in that body region -1.2 points (-2.3 to +0.1);
  - still playing two seasons on +0.8 points (-1.1 to +2.7).
- There are 13 diagnoses and about 30 measures each, so some intervals will miss zero by chance. The findings below
  hold across diagnoses or are large.

**What it found** (games through June 13, 2026):
- **Players come back to fewer minutes, not worse play.**
  - In the first year back they played 1.1 fewer minutes a game than players like them (0.8 to 1.5 fewer). They
    started 4.6 points less often.
  - In the second year back the gap was 0.6 minutes (0.1 to 1.1).
  - Production per 36 minutes barely moved: -0.2 (-0.4 to 0.0). True shooting dipped 0.6 points in the first year
    (0.3 to 0.9).
- **The same body part goes again.** 26% were hurt again in the same body region within a year of coming back,
  against 16% of players like them (+10.5 points, +7.8 to +13.5). After a muscle strain it was 29% against 10%.
- **After a concussion, more injuries of other kinds.** Concussions cost a median of 3 games and changed nothing in how
  players played. In the year back, though, players had 2.65 new injuries against 2.05 for players like them (+0.61,
  +0.20 to +1.03), most of them elsewhere in the body (+0.53, +0.12 to +0.96). Teams listing players more carefully
  after a concussion could explain part of it.
- **A torn Achilles is the one that shortens careers.**
  - There were 15 since 2018-19. Players were out a median 373 days, and 37% were back within a year.
  - In the first year back they played 2.9 fewer minutes a game (0.8 to 5.2), with true shooting 3.1 points lower
    (0.9 to 5.5).
  - Three seasons on, 4 of 9 were still in the league, against 76% of players like them (-32 points, -60 to -4).
- **A torn ACL: a long road back, then the same player per minute.**
  - There were 27 since 2018-19, out a median 89 games and 413 days. 21% were back within a year, 90% within two.
  - In the first year back they played 4.3 fewer minutes a game (2.3 to 6.3) and started 40% of their games (58%
    before). Production per 36 held: +0.7 (-0.2 to +1.6).
  - Three seasons on, 61% were still playing, against 78% of players like them (18 injuries; not significant).
- **Staying in the league.** Across every injury, 80% were still playing two seasons later, against 83% of players
  like them (-2.9 points, -5.8 to -0.3).
- **Moving teams.** Injured players were no more likely to be on a new team in the year back (39% against 41%).
- **Teams' first timelines run short.** Of 83 injuries where the team first gave a return in weeks and the player came
  back without a break in the season between, 36 came back later than the longest estimate (a median 1.5 weeks late),
  36 within it and 11 sooner. After a muscle strain it was 11 of 14 late.

| Injury | Injuries | Median games missed | Median days out | Back within a year | Minutes a game, first year back | Production per 36, first year back | Hurt there again within a year (vs players like them) |
|---|---|---|---|---|---|---|---|
| Every injury followed | 1,174 | 16 | 46 | 93% | -1.1 (-1.5 to -0.8) | -0.2 (-0.4 to 0.0) | 26% vs 16% |
| Torn ACL | 27 | 89 | 413 | 21% | -4.3 (-6.3 to -2.3) | +0.7 (-0.2 to +1.6) | 33% vs 23% |
| Torn Achilles | 15 | 67 | 373 | 37% | -2.9 (-5.2 to -0.8) | -0.7 (-2.3 to +1.3) | 11% vs 7% |
| Torn meniscus | 22 | 28 | 149 | 82% | -1.5 (-4.1 to +1.8) | -1.2 (-2.7 to +0.6) | 41% vs 41% |
| Knee sprain or bone bruise | 60 | 15 | 39 | 96% | -0.6 (-2.0 to +0.8) | -0.2 (-1.1 to +0.7) | 30% vs 23% |
| Broken foot | 20 | 35 | 97 | 91% | -2.8 (-5.0 to -0.7) | +0.3 (-1.0 to +1.7) | 13% vs 17% |
| Stress fracture or reaction | 30 | 33 | 217 | 85% | -3.9 (-6.0 to -1.7) | +0.4 (-1.1 to +1.9) | 32% vs 17% |
| Broken leg, knee or ankle | 16 | 23 | 182 | 87% | -4.6 (-8.0 to -1.5) | -1.8 (-3.6 to -0.2) | 36% vs 16% |
| Broken hand, finger or wrist | 59 | 15 | 37 | 100% | 0.0 (-1.2 to +1.2) | 0.0 (-0.8 to +0.9) | 15% vs 14% |
| Ankle sprain | 120 | 16 | 41 | 96% | -0.8 (-1.7 to -0.1) | -0.4 (-1.2 to +0.3) | 33% vs 29% |
| Muscle strain | 183 | 15 | 38 | 98% | -1.5 (-2.1 to -0.9) | -0.2 (-0.7 to +0.4) | 29% vs 10% |
| Back injury | 40 | 16 | 126 | 88% | -3.3 (-5.3 to -1.5) | -0.2 (-1.5 to +0.9) | 12% vs 16% |
| Shoulder injury | 44 | 20 | 61 | 100% | +0.3 (-1.2 to +1.6) | -0.7 (-1.4 to +0.2) | 14% vs 10% |
| Concussion | 120 | 3 | 8 | 99% | 0.0 (-0.8 to +0.8) | 0.0 (-0.6 to +0.6) | 11% vs 4% |

Minutes and production are the change against players like them. Production per 36 counts points, rebounds,
assists, steals and blocks, less turnovers. `summary.json` has the rest: the second year back, every measure, the
durability and career outcomes, and each ACL, Achilles, meniscus and broken-foot injury one by one. The dashboards'
**After an injury** view draws it for every kind of injury, and each player profile shows how they came back.

Not yet: contracts and salaries. That needs a salary source whose terms allow it.

## The public site

`python -m injury_risk site` (`src/injury_risk/site_build.py`) builds everything in `docs/`:

- `docs/data/`: `board.json` (each night's 2025-26 board, before tip-off and after the game, with what happened),
  `players.json` (every player's risk game by game and their new injuries) and `study.json` (the model check, the risk
  factors, the injury types, the injury moments' NBA patterns, the college check's totals, every play's ratio
  in both leagues with how well they agree, and whether college injuries carry into the NBA). It needs
  `outputs/dashboard/`; in a fresh clone the step keeps the published files and rebuilds the pages from them.
  With `outputs/profiles/` it also writes the profiles: `history.json` (every NBA player), `college.json` (every
  listed college player) and `people.json` (the search box's index of both). With `outputs/aftermath/` and
  `outputs/news/` it writes `careers.json` (the career study) and `details.json` (each injury's facts from the news and
  how the player came back, for the profiles), and adds how injuries happened and the checks against the news to
  `study.json`. The news facts are facts and their sources only: no report's own words, NBA.com's pages without a link
  (its terms forbid linking to it), and college players only once they reach the NBA.
- `docs/index.html`: the overview, from `src/injury_risk/site/overview.html` with every figure filled in from
  `docs/data/`. It is always dark, in the same family as the portfolio (bryanhkwan.github.io/portfolio).
- `docs/dashboard.html` and `docs/assets/`: the dashboards and the shared styles and scripts (`site.css` for the
  tokens and the overview, `app.css` for the dashboards, `charts.js`, `site.js`, `overview.js`, `dashboard.js`).
  `charts.js` is adapted from tasteskill's chart helpers (MIT); its licence is at the end of the file.
- `docs/moments.html`: the injury-moment report (`report_site.py`), one page with its charts, tables and data inline.
- `docs/assets/social-site.jpg`: the overview's link preview, rendered with headless Chrome.
  `python -m injury_risk linkedin` renders the report's (`social-card.png`) and the sharing images, which stay local.

- **Publishing:** push the repository and turn on GitHub Pages (Settings > Pages > Deploy from a branch > `main`,
  `/docs`).
- **Links:** they assume the repository is `bryanhkwan/Basketball-Injury-Project`. Otherwise change `REPO_URL` and
  `SITE_URL` in `report_site.py` (and the two addresses in `site/dashboard.html`) and rebuild.
- **Design:** `DESIGN.md` describes the system the pages follow.

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
