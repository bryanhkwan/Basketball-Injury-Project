# NCAA injury-moment test: plan fixed in advance

Written October 19, 2026, before any college injury exit was compared with anything. At that point only
data structure, coverage and matching had been looked at: the play-by-play's columns, how substitutions
and fouls are logged, rebuilt minutes against the box score, and how Covers teams match ESPN teams. No play
flag had been computed for any college injury.

## Question

Do the patterns found in the NBA (`docs` of `src/injury_risk/moments.py`, README "What players were doing
when they got hurt") show up in Division I men's college basketball?

## Data

- Play-by-play: the NCAA's official play-by-play as mirrored by sportsdataverse (`ncaa_mbb_pbp`), seasons
  2019-20 to 2025-26. Substitutions are logged as "Enters Game" / "Leaves Game" with player ids, a fouled
  player as "Draw Foul", shots with descriptors (driving layup, tip-in, floater, dunk...), and the five
  players of each team on the floor for every play.
- Minutes: the NCAA box score from the same source (`ncaa_mbb_player_box`). A player missing from a
  team's box score did not play.
- Injuries: the 191 in-season saved copies of Covers' NCAAB injury page (Wayback Machine, 2019-20 to
  2025-26), each listing player, school, body part, status, a dated note and its text.
- Teams are matched from Covers to ESPN team ids (normalized names, then an alias list checked by hand),
  players by name within team and season.

## Injuries and injury exits

- **Missed-game run:** consecutive team games a player did not play, after a game he played.
- **New injury:** a run is a new injury of a body part if a Covers listing for him with a named body part
  (not Undisclosed, Personal, Illness, Eligibility, Suspension, Redshirt, Academics, Not Injury Related,
  Disciplinary, Transfer or Coach's decision) was saved while the run was going on, or carries a note
  dated from 3 days before the game before the run to 14 days after its first missed game.
- **Injury exit (the case):** his last exit in the game before the first missed game was early in a
  competitive game, and he finished well under his usual minutes. Early means 6+ minutes of the game
  left; competitive means within 15 points at that moment. He must not have been ejected and must have
  had fewer than 5 fouls (college fouls out at 5). Well under means under 60% of his usual minutes: the
  mean of his previous 10 games played, at least 3 of them, which must be 12 or more.
- **Exits:** "Leaves Game" events, timed by the event. A player who does not start a half leaves at the
  end of the one before. A player who goes out and back in at one stoppage never left.

## Comparisons (same as the NBA test)

- **Main:** injury exits against the same player's ordinary exits that season. Ordinary exits are exits
  he came back from, with 6+ minutes left and within 15 points, in games not followed by any missed game.
- **Statistic:** Mantel-Haenszel odds ratio over player-season strata with the RBG interval.
- **Checks:**
  - within the same kind of stoppage;
  - against null exits (a random moment on the floor, then the first dead ball);
  - each injury group against all other injury exits;
  - early exits with no injury (he played the next game) against ordinary exits.

## Plays in the 30 seconds before an exit (t - 30, t], inside the half

- His own plays:
  - offensive or defensive rebound;
  - shot at the rim: any layup or dunk, including tip-ins and alley-oops;
  - drive: a driving layup, a floater, or a fast-break shot at the rim;
  - dunk; tip-in;
  - jump shot: two- and three-point jumpers and hooks;
  - drew a foul ("Draw Foul");
  - committed a defensive foul; offensive foul;
  - block; steal;
  - lost the ball, traveled or a dribbling violation; any other turnover.
- On the floor for:
  - any rebound;
  - a rebound of a miss in the paint;
  - an opponent's shot at the rim while he was defending.

## Groups (Covers body part; injury type from the note text)

- **Ankle:** ankle.
- **Ankle sprain:** ankle, with "sprain" or "rolled" in the note.
- **Knee:** knee.
- **Foot and toe:** foot, toe, heel.
- **Pulled muscles:** hamstring, calf, groin, Achilles, thigh or quad. "Leg" counts only when the note says
  strain, pull or tight.
- **Back and hip:** back, hip, abdominal, core, ribs, chest.
- **Hand, wrist, finger and arm:** hand, wrist, finger, thumb, arm, elbow.
- **Head:** head, face, eye, nose, jaw, neck, concussion.
- **Shoulder:** shoulder, collarbone.
- **Other:** everything else with a named body part.

## Primary hypotheses (each: odds ratio above 1, 30-second window, main comparison)

- H1. Ankle injuries come right after he drew a foul.
- H2. Injuries of any kind come right after his own steal.
- H3. Hand, wrist, finger and arm injuries come while he was defending an opponent's shot at the rim.
- H4. Pulled muscles come right after a drive.

## Decision rule for each primary hypothesis

| Result | Verdict |
|---|---|
| Holm-adjusted two-sided p < 0.05 across H1-H4, and OR > 1 | Replicates |
| OR > 1, adjusted p >= 0.05 | Same direction, not shown |
| OR <= 1 | Does not replicate |

For each one, also report:
- the two halves (2019-20 to 2021-22, and 2022-23 to 2025-26);
- every check;
- the 15-, 60- and 120-second windows.

## Secondary, not decisive

- H5. Ankle injuries come right after his own rebound.
- **Expected markers of an injury, not causes:** losing the ball or traveling just before leaving.

## Exploratory

- The full play-by-group table, with Benjamini-Hochberg q-values. A finding there needs q < 0.05, at least
  10 exposed injury exits, and the same direction in both halves.
- Anything new found this way is a lead for the next season's data, not a result.

## Quality checks reported with the results

- Rebuilt minutes against the box score.
- How many Covers teams and players matched.
- A hand-read sample of injury exits and of matched injury listings.
- Case counts by group, and the share of injury runs pinned to an exit.
- Because college injuries are listed less fully than NBA ones (sparse saved copies in some seasons), the
  case counts and the power they give are reported before the results.

## Addendum, before any results (October 19, 2026)

Rebuilt minutes depend on the NCAA log's lineups, which are missing for most plays in about 17% of games
(2024-25). Only games where at least 90% of player-games' rebuilt minutes are within 2 minutes of the box
score are kept, for injury exits and comparisons alike: 81% of 2024-25 games, in which 97.5% of
player-games are within 1 minute. An injury whose game before the run fails this check cannot be pinned,
and the share pinned is reported among injuries whose game before the run passes it. This uses no injury
result. Nothing else in the plan changes.
