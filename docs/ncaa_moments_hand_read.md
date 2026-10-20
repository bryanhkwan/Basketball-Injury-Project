# NCAA injury-moment test: hand-read sample

The plan (`ncaa_moments_plan.md`) asks for a hand-read sample of injury exits and matched injury listings
with the results. An independent review read the raw play-by-play from 120 seconds before to 30 seconds
after each exit, alongside every Covers listing for the player. It covered 102 windows:

- all 37 distinct injury exits exposed in H1-H5;
- 30 random other injury exits;
- 20 injury exits at a stoppage the log does not record;
- 15 ordinary exits.

The review used the first run. The final run adds 5 cases from fixed name matching and moves 3 halftime
exits; neither changes what is described here.

## Matching and timing

- **Listings:** every main case's listing names the matched player, with the same name and team in
  323 of 323 cases.
- **Teams:** all 64 hand-made team aliases and all 330 normalized team matches are correct.
- **Players:** a sample of 60 player matches had no wrong ones.
- **Exit times:** right in 87 of 87 injury exits read.

## Do the injury exits look like injuries?

Of the 87 injury exits read:

| Reading | Count | Share | What it looked like |
|---|---|---|---|
| Direct evidence of an in-game injury | 33 | 38% | A note saying he exited or was lifted from the game, a teammate shooting his free throws, or play stopping with nothing logged seconds after his play |
| Consistent with an injury | 35 | 40% | |
| Rotation decision or log artifact | 14 | 16% | |
| Injury he already had | 5 | 6% | Short return from an existing injury |

The background rate puts about 16% of pinned injuries down to chance early exits, which fits the
rotation-like share.

## The exposed cases behind each hypothesis

**H4, pulled muscles after a drive (the only "replicates").** All three are real in-game injuries confirmed
by public reports, and all three are fast-break finishes, not half-court drives:

- **Myles Cale** (Seton Hall vs Ohio State at a neutral site in Fort Myers, November 22, 2021, groin): a steal, then a fast-break layup
  to make it 24-19. Out 5 seconds later.
- **Jaylen Clark** (UCLA vs Arizona, March 4, 2023, Achilles): a steal and a fast-break layup, then an
  Arizona timeout at the same second. He was the only player subbed out.
- **Zhuric Phelps** (SMU vs Tulsa, February 23, 2022, quad): a missed fast-break dunk, out 12 seconds
  later.

**H1, ankle injuries after drawing a foul.** The drawn foul is a plausible moment of injury in 8 of 8.
Five have direct evidence:

- Notes say Chris Duarte (Oregon) and Johnny Juzang (UCLA) exited, and Berke Buyuktuncel (UCLA) was
  lifted from the game.
- Jayden Stone (Detroit Mercy) and Dante Harris (Memphis) drew shooting fouls, and a teammate shot their
  free throws as they left.

**H2, a steal.** Six of 10 have strong evidence. The injury comes in the sprint, finish or scramble right
after the steal, often with a foul. One example is Xavier Johnson (Indiana), "rolled up on" going for a
loose ball.

**H3, hand injuries while defending a rim attempt.** This is the weakest:

- 1 strong case: Warren Washington, a dislocated finger.
- 5 plausible.
- 2 rotation-like.
- 2 wrist injuries he already had.

The opponent's rim attempt is a plausible mechanism in about 4 of 10.

**H5, ankle injuries after a rebound.** Six of 9 have strong evidence, including Cooper Flagg's landing on
an opponent after a rebound (Duke vs Georgia Tech, March 13, 2025). One "ankle" listing turned out to be a
broken foot (Chansey Willis Jr.).

## Leaving at a stoppage the log does not record

Of 20 such injury exits read, he was the only player his team took out in 15:

- **8 look like officials stopping play for a hurt player,** with nothing logged and only him leaving,
  0-3 seconds after a made basket or a change of possession. Examples: BYU's Richie Saunders and Gavin
  Baxter (both torn ACLs).
- **6 are plausible injuries.**
- **6 are rotation changes or log artifacts:** team rebounds, a TV-timeout mass change, and a substitution
  logged before the play it followed.

## Label problems found (handled by the strict-label sensitivity check)

- **One listing labelling two absences:** for example, an ACL note labels both a one-game absence and the
  season-ending one.
- **A suspension labelled as a knee injury:** a named listing from outside the absence beat a coach's
  decision listed during it.
- **Body parts that conflict between listings:** for example, ankle, then a broken foot.

None of these was among the H1-H5 exposures except the body part noted under H5.
