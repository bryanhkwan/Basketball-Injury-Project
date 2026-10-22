# Injury news: what each injury was and how it happened

## Goal

The profiles know when each injury began, how many games it cost and what the injury report (NBA) or Covers
(college) called it. The listings are often vague: only half of the NBA injuries that cost 30 or more games name the
injury ("left knee soreness"), and most college listings give only a body part. News reports usually say more:

- the exact injury (a torn meniscus, a high ankle sprain, the grade of a strain);
- how it happened (landing on a defender's foot, a non-contact cut, a collision);
- whether it needed surgery, and the expected return.

The job is to look up the listed injuries in the news and record what the reports say: facts with their sources,
never the articles' words. Every fact must survive `python -m injury_risk news-check`. The site shows the facts on
the player profiles and in the dashboards' How it happened view (see "The site part" below).

What the facts are for, in order: the injury behind a vague listing; how it happened (contact, mechanism, the play),
which splits injuries into the kind a workload model can hope to predict (non-contact) and the kind it can't (being
struck or stepped on); the game it happened in, which ties it to the play-by-play study; then surgery and timelines.

## Input

Run `python -m injury_risk news-targets`. It writes `outputs/news/targets.jsonl`: one injury per line, most
valuable first. It reads the full profiles in `outputs/profiles/`, which aren't committed; if they're missing, run
`python -m injury_risk profiles` first. The pilot's 50 injuries are frozen in `outputs/news/pilot.json`, so a rebuilt
target list keeps them even when re-reading the reports moves an injury's first date. The fields you'll use:

| Field | Meaning |
|---|---|
| `id` | The injury's key, `league:player:first listed:body region` (for college, Covers' body-part group). Use it as given. |
| `league`, `tier`, `pilot` | `nba` or `college`; tier 1 to 3; true for the 50 pilot injuries |
| `player`, `team` | The player's name and their team or school at the time |
| `first_listed` | The first missed game (NBA) or the first day Covers listed the injury (college) |
| `last_game_before` | NBA only: their last game before it, often the game they were hurt in |
| `listed_as`, `first_listed_as` | What the listing called it (and, if the name changed, what it was first listed as) |
| `region`, `kind` | The body region, and the kind of injury as the profiles group it |
| `games_missed`, `back` | What it cost, and the first game back |
| `window` | The dates to search: reports outside them are about something else |

Some rows show what the listings get wrong. Haliburton's 2025 Achilles tear is first listed on October 23, 2025, but
happened in his last game, June 22; the window covers both. Jaylen Clark's 2023 college injury is listed only as
"Achilles". Covers dates Cooper Flagg's 2025 ankle sprain a day before the game it happened in.

## Output

Two files, one line per injury, so a run can stop and resume; and the outlet list.

### `outputs/news/facts.jsonl`: what the site may publish (committed)

```json
{"target": "nba:999:2024-01-10:knee", "status": "confirmed",
 "diagnosis": {"label": "Torn meniscus", "detail": "a small tear, repaired"},
 "side": "left", "grade": null, "setting": "game",
 "game": {"date": "2024-01-08", "play": "rebound"},
 "contact": "non_contact", "mechanism": "landing",
 "surgery": {"had": true, "date": "2024-01-15"},
 "expected": {"season_ending": false, "weeks": [6, 8], "reevaluate_weeks": null},
 "sources": [{"url": "https://...", "outlet": "Team name", "published": "2024-01-11", "headline": "Medical update", "official": true}]}
```

(A made-up player: the shape, not anyone's injury.)

- Every field can be `null`. Use `null` whenever no report says it. Never guess.
- `status` says how well the diagnosis is supported:
  - `confirmed`: the team or the league said it, either on its own page or in a quote that credits it ("the team
    announced", "the coach said"), or two different outlets did. Copies of one wire story count as one outlet, and so
    does a story that only repeats another outlet's report. A credit covers only what it is attached to: "the coach
    said he could miss the season" credits the timeline, not a diagnosis in the article's own background. A team's
    game status ("out, according to Raptors PR") is the listing;
  - `reported`: one outlet named the injury;
  - `conflicting`: reports disagree with each other or with the listing about what the injury is or its side (say
    which in `diagnosis.detail`). The team's "bone bruise" against a listed "sprain" disagrees, unless the listings in
    the same absence come to say what the team said;
  - `partial`: facts were found (surgery, the game, the side) but no report names the injury. A symptom (soreness,
    inflammation, effusion, irritation) is not a name for it. A concussion is the exception: NBA players enter the
    concussion protocol when one is diagnosed, so "entered the concussion protocol" names a `Concussion` (confirmed
    when the team or its coach says it, reported when a reporter does), while "concussion symptoms" or "evaluated for
    a concussion" alone does not;
  - `not_found`: nothing found. These rows carry no facts, only `target`, `status` and an empty `sources`.
- `diagnosis.label` is from the list in `src/injury_risk/news.py` (`DIAGNOSES`): the most specific one that fits, and
  "Other" plus `detail` only when none does. Don't make a listing less precise: a "subluxation" is a
  `Shoulder subluxation`, not a dislocation. A PCL sprain is `PCL sprain`; `Knee sprain` is for a sprain with no
  ligament named. A torn quadriceps tendon (at the knee) is `Torn quadriceps tendon`; a torn quadriceps muscle (the
  thigh) is `Torn quadriceps`. A stress reaction is not a stress fracture. A bruise is `Contusion` (a hip pointer
  included), or `Bone bruise`. The shin, tibia and fibula are filed under the calf, so their injuries fit it. A
  fracture at the knee (a femoral condyle, the tibial plateau, the kneecap, the head of the fibula) is `Knee fracture`;
  `Leg fracture` is a break along the shin bones. Either fits a listing at the knee or the lower leg.
- `diagnosis.detail` is optional: up to 80 characters, in your own words. It must not copy a report.
- The other fields take only the values in `news.py` (all lowercase):
  - `side`: left or right.
  - `grade`: 1, 2 or 3.
  - `setting`: game, practice, workout, offseason or unknown. A pickup game is a workout.
  - `contact`: contact, non_contact or unknown.
  - `mechanism`: landing, stepped_on_foot, cutting_or_planting, collision, struck, fall, overextension, overuse or
    unknown.
  - `game.play`, what they were doing: drive, drew_foul, rebound, steal, defending_the_rim, jump_shot, transition,
    screen, loose_ball, other or unknown. A breakaway is `transition`. Fouled on their own shot, dunk or drive is
    `drew_foul`.
  - Foot on foot is `stepped_on_foot` either way: they landed on someone's foot, or someone stepped or landed on theirs.
- `game.date` is the game they were hurt in. It must fall inside the window and no more than three days after
  `first_listed` (later than `first_listed` means the listing's date is wrong: a warning, not an error). When a source
  names the game without its date ("Game 6 of the Finals", "Monday night against the Kings"), date it from the
  schedule and keep the quote that names it. Look for the date, the play and contact in every game injury.
- `surgery.date` is the day of the operation, not the day it was announced: "underwent surgery, the team said Monday"
  dates the announcement, so leave the date `null` unless a source gives the operation's day.
- `expected.weeks` is the first return timeline given for the injury, as `[fewest, most]` whole weeks: the one that
  came with the diagnosis, the MRI or the surgery, even days after the injury ("re-evaluated in four weeks" after the
  operation). A progress, rehab or setback update ("re-evaluated again", "another two weeks", "a setback in his
  rehab") neither counts nor replaces it. `most` is `null` for "at least N weeks". `expected.reevaluate_weeks` is the same for "will be re-evaluated in N weeks", which is how
  NBA teams usually announce. Months become weeks at 4.35 weeks a month, rounded ("four to six months" is `[17, 26]`);
  days at 7 a week, rounded to the nearest week and at least 1 ("7-10 days" is `[1, 1]`, "10-14 days" is `[1, 2]`).
  Keep the original words in the quote.
- `sources`: every source a fact uses, and only those. Each needs:
  - an https `url`, its public address: no tracking parameters, no development hosts (`api-hub-dev.nba.com`), no
    rolling player feeds whose content changes, and the article's own address rather than an AMP copy;
  - its `outlet`: who wrote it, named as in `outputs/news/outlets.json` (an AP story on NBA.com is "Associated Press";
    a staff story is "NBA.com"; a team release posted on nba.com is the team);
  - `via`, when the story only repeats another outlet's report: that outlet;
  - its `published` date and its `headline` as published;
  - `official`: true exactly when the outlet's kind is team, league, school or conference. `news-check` holds it to
    that.
- Every source must name the player in its headline or its quotes.

### `outputs/news/outlets.json`: who wrote what (committed)

Every outlet the facts cite, with its kind: team, league (the league office), school, conference, league_media
(NBA.com's newsroom), wire, national, local, student, blog or aggregator. Add an outlet the first time you cite it.

### `data/news/evidence.jsonl`: the quotes behind each fact (local, never committed)

```json
{"target": "nba:999:2024-01-10:knee", "field": "diagnosis.label", "value": "Torn meniscus",
 "url": "https://...", "quote": "An MRI confirmed a torn left meniscus, the team said.", "retrieved": "2026-10-21",
 "attributed": "team"}
```

- Write one row for each fact in each source that says it.
- `field` is one of the dotted names in `news.py` (`FACT_FIELDS`).
- `value` equals the fact exactly.
- `quote` is the sentence that says it, up to 300 characters, exactly as saved in `data/news/cache/`.
- `attributed` is `team` or `league` when the quote credits them. When the quote's own words don't show who said it
  ("announced", "said", "statement", "per"), `news-check` warns and the audit checks the credit. A quote with
  "reportedly", "feared", "sources said" or "expected to have" can't support `confirmed`.

## How to research

- **Where to look:** start with the team's or school's own announcements ("medical update"), then the wire
  services and national outlets, then local beat reporters. For college players, also the school's athletics site
  and the student paper.
- **Matching:** a report counts only if it is about this player and team, inside the window, and the same body
  region. Check left and right against `listed_as`. Never record a report about a different injury of the same player.
- **The final word wins:** reports change ("a sprain", then "a torn ACL" after the MRI). Record the final diagnosis,
  and its date in the source.
- **Rumours aren't facts:** "feared", "reportedly" and "is expected to" support at most `reported`. Never use them
  for `confirmed`.
- **Reading pages:** read a page only with `python -m injury_risk news-fetch URL`. It reads robots.txt first and
  reads the page only if every agent the request could count as is allowed (this project, `*`, and the AI agents that
  read pages for a person); a robots.txt that can't be read means no. It waits between requests to a site and saves
  the text, not the HTML. When it refuses, use the search tool's text only. NBA.com turns those agents away, so every
  nba.com page is search text.
- **Not the listings:** never cite the NBA's official injury report. The listings come from it, so it confirms nothing
  and adds nothing. Neither do its copies: the injury list in a preview, a recap or a team's game notes ("Otto Porter
  Jr. (left foot pain)", an opponent's included), or an article quoting the report's line, or a sentence that only
  restates who is out with what ("has missed 13 games with a bruised right heel"). When a list entry says more
  than the listing ("Malcolm Brogdon (minor plantar fascia tear, out five weeks)"), quote the sentence around it. When a
  later listing in the same absence names the injury (Lonzo Ball's "Left Meniscus; Tear"), find the report or team
  statement that says so. A row whose only facts come from the listing is `not_found`.
- **Paywalls and reprints:** don't get around a paywall or a login, and don't cite a copy of a paywalled article on
  another site; skip that source instead. The text a paywalled article shows search engines may back a fact; cite the
  article itself, and say so in the review's notes.
- **What to keep:** the text of the pages you read in `data/news/cache/`, under 500 MB, and a log of every query
  and fetch with its date (see "Recording the research" for the formats).
- **Being polite:** wait at least 2 seconds between requests to the same site. Use a search tool or API you're allowed
  to use, and record which one.
- **College players are students:** record only what the reports say happened, never commentary. Leave out any
  health detail beyond the injury itself.

The code is in `src/injury_risk/news_research.py`. `python -m injury_risk news-research --tier 1 --league nba` (or
`--pilot`) checks the reviews in `data/news/reviews/` and files them; it skips injuries already filed, so it can resume,
and `--refile` files corrected reviews again. A review that fails a check is parked in `data/news/blocked.jsonl`, with
what is wrong, and the run goes on; a filed row that no longer passes comes off and joins them. It prints its progress
and lists the next batch in `data/news/pending.jsonl`. When the analysis is rebuilt and an injury's id changes (its
first listing moved, or its reason now sorts to another body part), `news-targets` moves its research to the new id;
research whose injury is no longer a target is set aside in `data/news/retired/`. Its tests use made-up data only:
never a real player's made-up facts.

## Recording the research

All of these stay in `data/news/`, which is never committed.

- **One review per injury**, `reviews/<id, with : as _>.json`:

  ```json
  {"target": "nba:999:2024-01-10:knee",
   "fact": {"target": "nba:999:2024-01-10:knee", "status": "confirmed", "...": "the row for facts.jsonl"},
   "evidence": [{"target": "nba:999:2024-01-10:knee", "field": "diagnosis.label", "value": "Torn meniscus", "...": "..."}],
   "read": {"https://...": "search"},
   "queries": ["every query run for this injury"],
   "notes": ["the research decisions: what was left out and why, which report settled a disagreement"],
   "elapsed_seconds": 95, "tokens": null}
  ```

  `read` says how each source was read: `search` (the search tool's text) or `page` (`news-fetch`). Notes are
  decisions about the injury, not remarks about the tools. A `not_found` review has no evidence, but its queries and
  a note on what was searched.
- **The search tool's answers, whole:** save each search response exactly as the tool returned it, one file per call,
  in `cache/<batch>/search_<n>.txt`. The quote check reads the tool's own layout (each result's title and address,
  then its text), so don't trim or rewrite it. A page the search tool opens by itself doesn't count; read pages with
  `news-fetch`, which saves them in `cache/pages/`.
- **The request log:** one row per query in `log_<batch>.jsonl`:
  `{"provider": "<search tool>", "timestamp": "<ISO time>", "action": "search", "query": "...", "cache": "<file>"}`.
  `news-fetch` logs its own requests, and `news-research` merges the logs into `log.jsonl`.
- **The batch:** when a batch starts, copy its ids from `pending.jsonl` into a row of `batches.jsonl`, and complete
  the row when it is filed: `{"batch": "nba-t1-01", "league": "nba", "tier": 1, "targets": [...], "started": "...",
  "finished": "...", "minutes": 0, "tokens": null, "agent": "<agent and model>", "note": "..."}`. Tokens are the
  agent's own count if it can see one, else null.
- **The audit:** `python -m injury_risk news-audit <batch>` writes `audits/<batch>.md`: 15 of the batch's injuries,
  drawn at random, each fact beside its quote and the saved text around it. An auditor who didn't research the batch
  checks them and records a row per injury in `audits.jsonl`: `{"batch", "target", "ok", "wrong": [fields], "note"}`.

## Phases

1. **Pilot (done; refiled 2026-10-20):** the 50 injuries in `outputs/news/pilot.json`, with eleven well-known ones
   for checking by eye. `outputs/news/pilot_report.md` has the results.
2. **Every tier, one league at a time:**
   - NBA: tier 1 (`--tier 1 --league nba`: injuries that cost 10 or more games, and named major injuries), then
     tier 2 (`--tier 2 --league nba`: the concussions).
   - College: tier 1 (players now in the NBA), with `--league college`. Tiers 2 (out for the season, or a named
     injury) and 3 (out indefinitely, or 5 or more games) are left out (the owner, 2026-10-21): they are players who
     never reached the NBA, their injuries got less coverage (of 8 tried in the pilot, 3 turned up a diagnosis), they are students, and
     they were half of what remained to research.
   - Work in batches of 150 in the order `news-research` lists them: vague listings first, then injuries first listed
     within four days of the player's last game, then the costliest.
   - **Two gates:** the first NBA batch and the first college batch are audited before the rest of their league runs.
     College brings school sites, student papers and the rules for students, so it gets its own first look. A gate
     holds back only its own league's batches.
   - After a gate, batches run one after another. Each is audited after it is filed, without holding up the next; a
     batch that fails its audit is corrected and refiled.
   - A review that fails a check doesn't stop the work: it is parked and the batch goes on. Stop only at a gate, or
     when an audit finds a wrong fact in more than 1 in 10 of its injuries. Report each batch's yield too (the share
     that gained something the listing lacked: the injury behind a vague listing, or how it happened); it is not a
     stop.
3. **Then the site part,** in its own spec.

### A batch, step by step

1. `news-research --tier N --league L` writes the next 150 injuries to `data/news/pending.jsonl`. Name the batch
   (`nba-t1-01`, `college-t2-03`), copy its ids into a new row of `batches.jsonl` with its start time, and research
   exactly those, even after `pending.jsonl` changes.
2. Research each injury ("How to research"), saving the search answers and writing its review ("Recording the
   research"). Every 25 injuries or so, run `news-research` for the tier and league: it files the reviews that pass
   and parks the rest in `blocked.jsonl`, each with what is wrong.
3. Fix what is wrong with a parked review (an outlet not yet listed, a wrong field, a quote that isn't in the saved
   text, a source about another injury) and run `news-research` again. When the review is right and a rule refuses it
   anyway (a label the injury's body part doesn't allow, say), leave it parked, say so in the batch's report, and go
   on: the owner settles rules between batches. Never change a rule, the code or the tests.
4. When every injury in the batch is filed or parked: `news-check` exits 0, the tests pass, the batch's row in
   `batches.jsonl` is complete, `news-audit <batch>` has written the audit sheet, and the batch's report is added to
   `data/news/batch_reports.md`.
5. A session that ends early finishes and files the batch it is in. The next one starts from the first row in
   `batches.jsonl` with no finish time, or with a new batch.

**Running fast** (the owner's choice, 2026-10-21):

- Up to eight research workers at once. Each writes only its own review files, its own log
  (`log_<batch>_<worker>.jsonl`), its own saved searches (`cache/<batch>/search_<worker>_<n>.txt`) and its own list of
  new outlets. One coordinator merges the outlets into `outputs/news/outlets.json`, runs `news-research` (never two at
  once), and writes `batches.jsonl` and the reports. Workers move on to the next batch while the coordinator files and
  reports the last one.
- File every 50 injuries or so, and at the end of each batch.
- A batch's report is the list below. Per-injury notes stay in the reviews.
- The college gate holds only college work: research the first college batch alongside the NBA batches, say when it
  is filed, and keep going with the NBA until the owner clears it.

**A batch's report:** how many are confirmed, reported, conflicting, partial and not found; how many gained something
the listing lacked; vague listings named (k of n); how many have a game date, a play, contact and a mechanism; the
outlets added, citations by kind of outlet, and what didn't work (sites `news-fetch` refused, paywalls, anything else);
`news-check`'s warnings; each review still parked, with its errors and whether the review or a rule is at fault; the
batch's minutes, seconds per injury and tokens; every judgment call the researcher wasn't sure of, and anything in this
spec that was unclear.

## The site part (built 2026-10-21)

- nba.com sources are cited as text (outlet, headline, date) without a link: NBA.com's terms forbid linking to it for
  public use without permission. Every other source is linked.
- Every split shows how many injuries it rests on: the news covers stars and severe injuries best, so mechanism counts
  lean that way (`news_summary.py`, the dashboards' How it happened view).
- College players who never reached the NBA get no news facts: they are students, most of their injuries got little
  coverage, and their tiers were left out of the research. Players now in the NBA get them on their college profile.
- `tests/test_public_site.py` checks that no run of eight words from a quote in `data/news/evidence.jsonl` reaches the
  site outside a cited headline, and that no nba.com page is linked.

## Settled after the pilot

The owner's review of the first pilot report (2026-10-20) settled these, and the rules above now say them:

- **Official** is who is speaking, not where the page lives, and it follows the outlet's kind. The first pass marked
  AP stories on NBA.com official in some rows and not in others.
- **Robots.txt** is read before a site's first page, and a site that can't be read isn't. The first pass opened ten
  nba.com pages after reading a robots.txt that turns its agent away, and read some college pages before asking.
- **Linking to NBA.com** waits for the site part, as text.
- **Timelines:** re-evaluation intervals have their own field; months convert at a fixed rate; "at least" is allowed.
- **No diagnosis** is `partial`, so `reported` keeps its meaning.
- **Wrong listing dates** are a warning, and the status follows the diagnosis.
- **Labels added:** `Shoulder subluxation`, `Midfoot sprain`, `Torn quadriceps`.
- **The plan:** NBA first, then college. The review first left out college tiers 2 and 3 for their thin coverage;
  the owner then chose every tier (2026-10-20), so each batch reports its yield instead of stopping on it.

The first NBA batch (2026-10-21) found these gaps, now fixed in the rules and the code:

- Stress fractures and reactions fit the calf, where the profiles file the shin.
- "The team reported" credits the team.
- New labels for injuries common in the listings: `PCL sprain`, `Knee sprain`, `Torn quadriceps tendon`,
  `Stress reaction`, `Leg fracture`, `Toe sprain`, `Wrist sprain`, `Finger sprain`, `AC joint sprain`,
  `Rotator cuff injury`, `Contusion` and `Bone bruise`.
- Timelines in days convert to weeks.
- The official injury report is not a source.

Its second stop (Vassell's foot, filed under the head) led to a sweep of how every listing is sorted (2026-10-21):

- **Parked, not stopped:** a review that fails a check is parked and the batch goes on; the owner settles the rules
  the parked reviews ran into between batches, all at once.
- **Body parts:** the part the team names before the semicolon decides; the rest of the listing decides when that part
  is missing, vague ("N/A", "General") or just "Leg". Words inside other words no longer count ("whiplash" is not the
  hip, "discomfort" not a disc, "tear" not an ear), and 110 of the 176 listings with no body part found one (the
  cuneiform, the scaphoid, the anterior cruciate ligament...); 47 more were not injuries. "UCL" alone stays unplaced:
  it can be the elbow or the thumb.
- **Not injuries:** listings under "Injury/Illness" that are personal reasons, the G League, reconditioning, the flu, an
  appendectomy or a medical condition no longer count as injuries; one that names an injury and an illness counts as
  the injury.
- **Types:** "Injury Recovery" is no longer a surgery.
- **Conflicting rows** may name an injury that doesn't fit the listing's body part: the disagreement is the finding.
- **Credit:** a quote credited to the team that doesn't show who said it is a warning for the audit, not an error.

The audit of the first NBA batch (2026-10-21; 15 drawn, `data/news/audits.jsonl`) found no false fact, and the
mechanism coding held up across all 34 rows that have one. But 4 of the 15 rested on the listing in another form (an
injury list in a preview or recap, or a quote of the report), which is more than 1 in 10, so the batch is corrected
and refiled:

- **The listing's copies** can't back a fact (see "Not the listings"). `news-check` refuses a quote that is only an
  injury list's entry and warns on one that cites the listing; it parked 19 filed rows, 17 of them this batch's.
- **Symptoms** are not a diagnosis, and **a pickup game** is a workout: the researcher's own consistent choices.
- **Credit:** "what the team called" credits the team; "the team listed" doesn't, since that is the listing.

The audit of the rest of the NBA and the first college batch (2026-10-21) settled these:

- **College windows** open at the player's last game before the listing, from the college box scores, as NBA windows
  do. Covers was saved every few days to weeks, so an injury could be first listed long after it happened (Isaiah
  Crawford's second torn ACL, November 15, first listed January 14), and its reports fell outside the window. 391
  college windows now open earlier.
- **A fracture at the knee** (`Knee fracture`) and a break along the shin bones (`Leg fracture`) each fit a listing at
  the knee or the lower leg: the head of the fibula sits at both.
- **An operation before the window** (an offseason surgery whose recovery the listing is) is a warning to check, not
  an error.
- **Credit wording:** "the Suns say", "per Pacers PR", "coach Malone described", "informed the media", "by the team"
  credit the team.
- **Betting and odds sites** relay other outlets' reports and the play-by-play. When they name where a fact came from
  ("per ESPN's Shams Charania", "@hornets announced"), cite that outlet as `via`; prefer the original when you can
  find it.
- **One player, one college:** the matching of NBA players to college careers gave Jalen Williams of Santa Clara the
  Cleveland State Jalen Williams's injury. Fixed: that row is set aside, and his own (December 2020, a foot) is a
  tier 1 target.

The corrections pass (2026-10-21) checked 1,223 rows and changed 413. It read "the timeline announced with the
injury" as the very first announcement only, and removed 131 timelines. The owner restored the 82 that were the first
forecast, given with the surgery or the MRI days after the injury (Grant Williams's 9 to 12 months, Iguodala's four
weeks), and kept out the 49 progress and setback updates. The rule above now says so.

## Done means

- `python -m injury_risk news-check` exits 0.
- `python -m unittest discover -s tests` passes.
- Every review still parked in `data/news/blocked.jsonl` is in its batch's report.
- Nothing changed outside `data/news/`, `outputs/news/` and the news code and its tests, unless the owner asked.
- Nothing is committed or pushed.
