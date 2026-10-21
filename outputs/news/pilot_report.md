# Injury news: 50-injury pilot

Researched 2026-10-20; refiled 2026-10-20 under the rules settled in the owner's review (`specs/injury-news.md`, "Settled after the pilot"). Stopped for the owner's check of the 11 known injuries.

Each injury was looked up by an agent with an allowed search tool, and its findings filed only after `news-research` checked them against the injury, the saved page text and `news-check`'s rules. The quotes, page text, review notes and request logs stay in `data/news/`.

## What the news found

| Group | Injuries | Confirmed | Reported | Conflicting | Partial | Not found | Gained something new |
|---|---:|---:|---:|---:|---:|---:|---:|
| Known injuries (anchors) | 11 | 10 | 1 | 0 | 0 | 0 | 8 |
| NBA, a vague listing that cost 10+ games | 12 | 9 | 1 | 0 | 2 | 0 | 7 |
| NBA, a named major injury | 6 | 6 | 0 | 0 | 0 | 0 | 3 |
| NBA, a sprain or strain | 4 | 3 | 1 | 0 | 0 | 0 | 2 |
| NBA, a concussion | 2 | 1 | 1 | 0 | 0 | 0 | 2 |
| College, a player now in the NBA | 7 | 0 | 2 | 0 | 5 | 0 | 4 |
| College, out for the season or a named injury | 5 | 2 | 1 | 0 | 1 | 1 | 0 |
| College, out indefinitely or 5+ games | 3 | 0 | 0 | 0 | 1 | 2 | 0 |
| Total | 50 | 31 | 7 | 0 | 9 | 3 | 26 |

Confirmed: the team or league said it (its own page, or a quote that credits it), or two different outlets did; copies of one wire story count once. Reported: one outlet named the injury. Partial: facts but no diagnosis. *Gained something new*: a diagnosis for a listing that named only a body part, or how it happened (contact, mechanism or the play).

### By league

| League | Injuries | Found | Confirmed | Vague listings named | Gained something new |
|---|---:|---:|---:|---:|---:|
| NBA | 32 | 32 | 27 | 6 of 8 | 20 |
| College | 18 | 15 | 4 | 3 of 15 | 6 |

How often each fact was found, among the injuries with any finding:

| League | Found | diagnosis | side | setting | game date | play | contact | mechanism | surgery | season-ending | return weeks | re-evaluation |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| NBA | 32 | 30 | 28 | 23 | 20 | 11 | 10 | 9 | 16 | 4 | 5 | 3 |
| College | 15 | 8 | 7 | 12 | 9 | 1 | 1 | 4 | 5 | 5 | 2 | 0 |

The listing named only a body part for 23 injuries; the news named the injury for 9: Jarred Vanderbilt (Right foot soreness → Midfoot sprain); Tre Mann (Low back soreness → irritation of a spinal disc); Denzel Valentine (Ankle surgery - left → persistent instability of the ankle); Onyeka Okongwu (Right shoulder injury recovery → Torn labrum); Dean Wade (Right knee soreness → Torn meniscus); Kobe Bufkin (Right shoulder injury → Shoulder subluxation); Cedric Coward (Shoulder → Torn labrum); Jaylen Clark (Achilles → Achilles tear); Cooper Flagg (Ankle → Ankle sprain). A vague listing is a college listing without a diagnosis, or an NBA reason with no injury word (tear, fracture, sprain, strain, subluxation, spasm, tendinopathy, bruise, contusion, dislocation, rupture, ACL, MCL). `Hip injury` and the like only repeat the body part and don't count.

## Sources

| Kind of outlet | Citations | Injuries |
|---|---:|---:|
| wire | 19 | 16 |
| local | 16 | 14 |
| league_media | 15 | 12 |
| national | 15 | 13 |
| team | 10 | 8 |
| school | 7 | 7 |
| blog | 3 | 3 |
| aggregator | 1 | 1 |
| student | 1 | 1 |
| conference | 1 | 1 |

88 citations from 45 outlets; 18 are the team's, league's, school's or conference's own pages. Read in full: 5; from the search tool's text only: 83 (the site's robots.txt turns AI agents away or couldn't be read, or the page is behind a paywall). NBA.com turns away the agents that read pages for a person, so every nba.com page here is search text.

Most cited outlets: Associated Press (19), NBA.com (15), Sports Illustrated (5), The Washington Post (2), Milwaukee Bucks (2), Chicago Bulls (2), San Antonio Express-News (2), NBC Sports (2), On3 (2), Deseret News (2), Indiana Pacers (1), ABC7 News (1).

What didn't work:

- NBA.com's robots.txt turns away the AI agents that read pages for a person, so the most-cited site is search text only. The first pass opened ten of its pages anyway; those copies were deleted, and nothing rests on them.
- Team medical updates on nba.com load in a frame a text reader can't open. Their words reach the search index, and that is how they are cited.
- Rolling player feeds (RotoWire's, on FOX Sports) change as items are added, so they can't be cited. Two college injuries needed other sources: McCullar's came from the Kansas City Star, Neath's from Wisconsin's own release.
- A copy of a paywalled article on another site can't be cited. Kobe Julien's only report was one, so that injury is now not found.
- Paywalled papers (the Washington Post, Houston Chronicle, Minnesota Star Tribune, Kansas City Star, Los Angeles Times and San Antonio Express-News) are cited from the text they show search engines, never read past the paywall.
- The first pass's search tool couldn't read most college sites' robots.txt, and it read pages anyway. Under the settled rule only news-fetch reads pages; it read the five the facts needed, each after its robots.txt allowed it.
- School athletics sites build some pages in the browser or wrap them in a form. The first version of news-fetch missed those stories; it reads them now.

## Time and tokens

| Batch | Injuries | Minutes | Tokens | What it was |
|---|---:|---:|---:|---:|
| pilot, first pass | 50 | 20.7 | not measured | three parallel workers with OpenAI's web.run; per-injury seconds were equal shares of each batch |
| pilot, refile | 50 | not measured | not measured | the settled rules applied to the same 50; 3 web searches and 6 news-fetch reads replaced dropped sources |

Per-injury time was not measured: the first pass researched the 50 in three parallel batches, and its per-injury seconds were equal shares of each batch. Neither agent can read its own token count. Tier batches record their own time and tokens in `data/news/batches.jsonl`.

## Problems and limits

- `news-check`: 0 errors, 3 warnings.
  - Kenrich Williams: game.date 2023-10-12 is not their last game before the listing (2023-02-28)
  - Cooper Flagg: game.date 2025-03-13 is after the first listing (2025-03-12): the listing's date is probably wrong
  - Branden Carlson: a game injury without its game.date: date the game a source names (opponent, playoff game, weekday)
- The facts are what reports say. The 11 known injuries are for checking by eye; the other 39 rest on news-check's rules and the quotes behind them.
- College coverage is thin: 3 of the 15 college listings that named only a body part got a diagnosis, all of them for players now in the NBA.
- News covers stars and severe injuries best, so mechanism counts from a full tier will lean that way.

- **Jamal Murray (2021-04-14)**: The game and the landing come from the Nuggets' surgery update in the AP story: hurt on a layup drive in the last minute against Golden State on April 12.
- **Klay Thompson (2020-12-25)**: Hurt in a workout, not a game, so there is no game or play.
- **Kyrie Irving (2025-03-05)**: First listed as a left knee sprain; the MRI showed the torn ACL. Fouled by DeMar DeRozan on a drive, the right foot came down on Jonas Valanciunas's foot and the left knee gave way.
- **Kawhi Leonard (2021-06-16)**: First listed as a right knee sprain; the July surgery repaired a partial ACL tear. The Washington Post is cited from its search text: it is behind a paywall.
- **Zion Williamson (2021-10-20)**: Hurt working out in the offseason; the December update reported slow bone healing and no return date.
- **Damian Lillard (2025-04-29)**: Lunging for a long offensive rebound, with no contact.
- **Jarred Vanderbilt (2024-02-03)**: Listed as right foot soreness. The 3-4 weeks was a re-evaluation, now recorded as one.
- **Tyrese Haliburton (2025-10-23)**: Pushing off on a drive in Game 7 of the Finals, June 22, with no contact; the Game 5 calf injury is another. The later AP story says the surgery was done.
- **Tre Mann (2024-11-23)**: The Hornets' update came in a story about LaMelo Ball; only its sentence about Mann is used. Disc irritation is not a herniated disc.
- **Klay Thompson (2019-10-24)**: Game 6 of the 2019 Finals, June 13, landing hard on a breakaway dunk. The surgery reports repeat ESPN's.
- **Denzel Valentine (2018-12-15)**: Listed as left ankle surgery; the Bulls diagnosed ongoing ankle instability. They first expected four to six months (17 to 26 weeks); after the November 27 stabilization they ruled him out for the season. An April 2018 knee surgery is another injury.
- **Blake Griffin (2019-12-30)**: Listed as left knee soreness. The Pistons announced an arthroscopic debridement on January 7 but named no injury behind it: partial. Later retrospectives are outside the window.
- **Onyeka Okongwu (2021-10-21)**: About six months is 26 weeks at 4.35 weeks a month. Hurt in the 2021 playoffs; the game isn't named.
- **Devin Vassell (2023-01-04)**: Listed as left knee soreness. The Spurs announced an arthroscopic procedure but named no injury behind it: partial. The Express-News is cited from its search text: it is behind a paywall.
- **Jarrett Allen (2022-03-08)**: The listing already named the fracture; the team's season review confirms it. The original announcement's page now carries a date after the window, so it isn't used.
- **Dillon Brooks (2026-02-22)**: The team's four to six weeks was a re-evaluation, not a return (NBC's headline says out 4-6 weeks).
- **Dean Wade (2022-03-14)**: Listed as right knee soreness; surgery repaired a torn meniscus. AS dates its story March 28 though its address says 29.
- **Jordan McLaughlin (2023-11-08)**: A later roundup's November 2 date is wrong: the game against Boston was Monday, November 6. The Star Tribune is cited from its search text: it is behind a paywall.
- **Taurean Prince (2018-12-16)**: Hurt against Golden State on December 3, two weeks before the first listing (the reports skip some early-season days).
- **Kobe Bufkin (2024-10-23)**: A partial dislocation is a subluxation. This is the October practice recurrence, not the summer episode or the December recurrence and surgery.
- **DeMarcus Cousins (2019-04-18)**: The listing already named the quad tear; the news adds the game, the play and that no one touched him. Whether he fell because of the tear or tore it falling isn't said, so the mechanism stays empty.
- **Isaiah Jackson (2025-12-23)**: Two elbows to the face in the December 22 game; out from December 23, which is where the re-read reports now start the injury.
- **Norman Powell (2023-03-03)**: Hurt at Golden State on March 2. The listing said subluxation, and the label now says so too.
- **Javonte Green (2020-08-21)**: Listed as a right knee sprain; the Celtics announced a small meniscal tear, repaired August 25. Two to three weeks was for basketball activities, not games, so it isn't a timeline.
- **Reed Sheppard (2025-03-08)**: Coach Ime Udoka described the fracture as in the top joint of the thumb. Hoops Rumors repeats the Chronicle; AP reported it separately. The Chronicle is cited from its search text: it is behind a paywall.
- **Gary Harris (2022-12-02)**: The listing already named the strain; the news adds the game, against Atlanta two nights before.
- **Kenrich Williams (2023-10-25)**: Back spasms from a preseason game against Detroit on October 12, which the box scores don't have, hence the warning. A March wrist injury is another.
- **Dylan Harper (2025-11-05)**: Landing after defending a shot near the basket, in Phoenix on November 2, with no contact. A September thumb surgery is another injury.
- **Luka Samanic (2021-05-13)**: A six-to-eight-week estimate was the reporter's, not the team's, so it is left out.
- **Cedric Coward (2024-11-26)**: Hurt in a November 22 practice. Only the Spokesman-Review names the labrum (and a rotator cuff), so the diagnosis is reported; the school's notes say shoulder surgery. Four to six months is 17 to 26 weeks. Later draft profiles and the undated roster page give the side, but nothing inside the window does.
- **Jaylen Clark (2023-03-08)**: UCLA named no diagnosis inside the window, so the torn Achilles rests on reports: reported. Hurt without contact against Arizona on March 4, with surgery three days later; Fox calls the game Tuesday, but March 4 was a Saturday. The Los Angeles Times is cited from its search text: it is behind a paywall.
- **PJ Hall (2022-02-22)**: Landing on the right foot in the February 19 game against Louisville, an aggravation of a season-long injury; no report names it. A March left-foot aggravation is another.
- **Herbert Jones (2020-02-02)**: Broke the left wrist against LSU on January 29 and had surgery February 1; played one-handed after.
- **Cooper Flagg (2025-03-12)**: Covers dates the listing March 12, a day before the March 13 game: its own page shows 'Wed, Mar 12', while teammate Maliq Brown's injury from the same game shows 'Thu, Mar 13'. The listing's date is wrong; news-check warns of it. The Washington Post is cited from its search text: it is behind a paywall.
- **Adam Flagler (2021-11-18)**: Hit the hand he was coming back from, in the November 17 game; no report names the injury or its side.
- **Craig Porter Jr. (2022-12-23)**: Hurt early in the second half against Texas Southern; no report says sprain, side, contact or mechanism. A December 2021 ankle injury is another one.
- **Trayce Jackson-Davis (2022-01-19)**: A hard fall at Nebraska on January 17. The reports say only hip, which repeats the listing.
- **Kevin McCullar Jr. (2023-02-15)**: The first source was a rolling player feed; the Kansas City Star, from its search text (it is behind a paywall), replaces it. No report names the ankle injury or its side.
- **Branden Carlson (2022-02-22)**: Left the game with a right ankle injury late in the second half; the recap doesn't give the game's date or name the injury, so it isn't called a sprain.
- **Mitchell Robinson (2021-11-21)**: Both reports are AP's, so one outlet: reported. The diagnosis is the later concussion report, not the protocol entry.
- **Rj Keene (2022-09-27)**: School, national, local and student-paper searches found nothing about this shoulder injury inside the window. Odds sites only repeat the listing and aren't used.
- **Jahcobi Neath (2022-12-03)**: Listed as lower body. Early reports pointed to the knee; the school's release names hip surgery. The first source was a rolling player feed; the school's release replaces it.
- **Gavin Baxter (2021-12-02)**: A torn left ACL early in the December 1 game at Utah Valley, in two outlets; the coach called it season-ending. An earlier right-knee injury is another.
- **Earl Timberlake (2021-01-27)**: Out for the season with a left shoulder injury, per the school and the conference; neither names it: partial.
- **Marcus Hammond (2022-01-28)**: The coach said the concussion happened a few days before; that isn't turned into a game date.
- **Kobe Julien (2020-11-18)**: The only report was a copy, on another site, of a paywalled Advertiser article, which can't be cited; the original wasn't found. The December 2019 knee surgery that searches return is the season before: another injury.
- **Jacob Ognacevic (2025-10-08)**: A preseason practice injury to the foot, with surgery in early October; no report names it or its side. About three months is 13 weeks. The school's game notes replace its preview page, whose saved text doesn't name him. A March 2026 re-injury is another injury.
- **Demarcus Sharp (2021-11-25)**: Nothing ties a report to this November foot listing. A January stress-related leg injury and surgery, and a March report of a stress fracture, aren't safely the same injury.

## Validation

- `python -m injury_risk news-check`: exit 0.
- `python -m unittest discover -s tests`: exit 0 (140 tests).
- Only the 50 pilot injuries were researched. Nothing was committed or pushed.
- Refile with `PYTHONPATH=src python -m injury_risk news-research --pilot --refile`; a tier with `--tier 1`, which files the reviews present and lists the next batch in `data/news/pending.jsonl`.

## Five example rows

### Jamal Murray

```json
{
  "target": "nba:1627750:2021-04-14:knee",
  "status": "confirmed",
  "diagnosis": {
    "label": "Torn ACL",
    "detail": null
  },
  "side": "left",
  "grade": null,
  "setting": "game",
  "game": {
    "date": "2021-04-12",
    "play": "drive"
  },
  "contact": null,
  "mechanism": "landing",
  "surgery": {
    "had": true,
    "date": null
  },
  "expected": {
    "season_ending": null,
    "weeks": null,
    "reevaluate_weeks": null
  },
  "sources": [
    {
      "url": "https://www.nba.com/news/jamal-murray-out-indefinitely-with-torn-acl-in-left-knee",
      "outlet": "Associated Press",
      "published": "2021-04-13",
      "headline": "Jamal Murray out indefinitely with torn ACL in left knee",
      "official": false
    },
    {
      "url": "https://www.nba.com/news/nuggets-guard-jamal-murray-remains-out-indefinitely-after-knee-surgery",
      "outlet": "NBA.com",
      "published": "2021-04-22",
      "headline": "Nuggets guard Jamal Murray remains out indefinitely after knee surgery",
      "official": false
    },
    {
      "url": "https://www.nba.com/news/jamal-murray-helped-off-court-after-suffering-apparent-leg-injury",
      "outlet": "NBA.com",
      "published": "2021-04-13",
      "headline": "Jamal Murray helped off court after suffering apparent leg injury",
      "official": false
    }
  ]
}
```

### Jaylen Clark

```json
{
  "target": "college:222994:2023-03-08:muscle",
  "status": "reported",
  "diagnosis": {
    "label": "Achilles tear",
    "detail": null
  },
  "side": "right",
  "grade": null,
  "setting": "game",
  "game": {
    "date": "2023-03-04",
    "play": null
  },
  "contact": "non_contact",
  "mechanism": null,
  "surgery": {
    "had": true,
    "date": "2023-03-07"
  },
  "expected": {
    "season_ending": true,
    "weeks": null,
    "reevaluate_weeks": null
  },
  "sources": [
    {
      "url": "https://www.foxnews.com/sports/jaylen-clark-ucla-loses-starting-guard-march-madness-achilles-injury-reports",
      "outlet": "Fox News",
      "published": "2023-03-08",
      "headline": "UCLA loses starting guard for March Madness with Achilles injury: reports",
      "official": false
    },
    {
      "url": "https://dailybruin.com/2023/03/08/ucla-mens-basketballs-jaylen-clark-to-miss-postseason-with-achilles-injury",
      "outlet": "Daily Bruin",
      "published": "2023-03-08",
      "headline": "UCLA men’s basketball’s Jaylen Clark to miss postseason with Achilles injury",
      "official": false
    },
    {
      "url": "https://www.latimes.com/sports/ucla/story/2023-03-29/ucla-jaylen-clark-declares-for-nba-draft-despite-serious-leg-injury",
      "outlet": "Los Angeles Times",
      "published": "2023-03-29",
      "headline": "UCLA’s Jaylen Clark declares for the NBA draft despite serious leg injury",
      "official": false
    },
    {
      "url": "https://www.si.com/college/2023/03/08/ucla-jaylen-clark-bruins-injury-tournament-hopes-march-madness-run",
      "outlet": "Sports Illustrated",
      "published": "2023-03-08",
      "headline": "Jaylen Clark’s Season-Ending Injury Is a Crushing Blow to UCLA’s Title Hopes",
      "official": false
    }
  ]
}
```

### Cooper Flagg

```json
{
  "target": "college:313631:2025-03-12:ankle",
  "status": "confirmed",
  "diagnosis": {
    "label": "Ankle sprain",
    "detail": null
  },
  "side": "left",
  "grade": null,
  "setting": "game",
  "game": {
    "date": "2025-03-13",
    "play": "rebound"
  },
  "contact": null,
  "mechanism": "landing",
  "surgery": {
    "had": null,
    "date": null
  },
  "expected": {
    "season_ending": null,
    "weeks": null,
    "reevaluate_weeks": null
  },
  "sources": [
    {
      "url": "https://www.foxsports.com/articles/cbk/ncaas-gavitt-duke-acc-tell-selection-committee-flagg-will-be-available-for-march-madness",
      "outlet": "Associated Press",
      "published": "2025-03-15",
      "headline": "NCAA's Gavitt: Duke, ACC tell selection committee Flagg will be available for March Madness",
      "official": false
    },
    {
      "url": "https://www.nbcsports.com/mens-college-basketball/news/injuries-to-freshman-star-cooper-flagg-maliq-brown-hit-at-inopportune-time-for-no-1-duke",
      "outlet": "Associated Press",
      "published": "2025-03-14",
      "headline": "Injuries to freshman star Cooper Flagg, Maliq Brown hit at inopportune time for No. 1 Duke",
      "official": false
    },
    {
      "url": "https://www.washingtonpost.com/sports/2025/03/13/duke-cooper-flagg-injured/",
      "outlet": "The Washington Post",
      "published": "2025-03-13",
      "headline": "Cooper Flagg, Duke basketball star, injured during ACC tournament game",
      "official": false
    }
  ]
}
```

### Blake Griffin

```json
{
  "target": "nba:201933:2019-12-30:knee",
  "status": "partial",
  "diagnosis": {
    "label": null,
    "detail": null
  },
  "side": "left",
  "grade": null,
  "setting": null,
  "game": {
    "date": null,
    "play": null
  },
  "contact": null,
  "mechanism": null,
  "surgery": {
    "had": true,
    "date": "2020-01-07"
  },
  "expected": {
    "season_ending": null,
    "weeks": null,
    "reevaluate_weeks": null
  },
  "sources": [
    {
      "url": "https://www.nba.com/news/blake-griffin-left-knee-debridement-out-indefinitely",
      "outlet": "NBA.com",
      "published": "2020-01-07",
      "headline": "Blake Griffin out indefinitely after left knee procedure",
      "official": false
    }
  ]
}
```

### Rj Keene

```json
{
  "target": "college:238292:2022-09-27:shoulder",
  "status": "not_found",
  "sources": []
}
```
