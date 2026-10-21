# Results

Built 2026-10-21T08:28:37. Report rows 134,220, of which 316 could not be matched to a player. New injuries by season (ending year): {'2019': 500, '2020': 718, '2021': 808, '2022': 932, '2023': 1002, '2024': 1018, '2025': 1132, '2026': 1084}. Median games missed: 2.

## Target `g1`: a new injury makes the player miss the team's next game, scored right after the game with its play-by-play

Test seasons 2024-25 and 2025-26: 56,274 player-games, 2,076 followed by a new injury (3.7%).

| Model | AUC (95% CI) | Avg precision | Brier skill | Top-10% lift | Top-10% catches |
|---|---|---|---|---|---|
| Base rate (everyone gets the average) | 0.500 | 0.037 | -0.001 | 1.00x | 100% |
| All features (gradient boosting) | 0.704 (0.690-0.719) | 0.096 | 0.026 | 2.70x | 27% |
| After the game: all features + that game's play-by-play (gradient boosting) | 0.764 (0.750-0.777) | 0.223 | 0.102 | 3.87x | 39% |

After the game: all features + that game's play-by-play (gradient boosting), by test season:

| Season | Player-games | Injury rate | AUC | Top-10% lift |
|---|---|---|---|---|
| 2024-25 | 27,916 | 3.8% | 0.767 | 3.90x |
| 2025-26 | 28,358 | 3.6% | 0.761 | 3.84x |

Calibration (deciles of predicted risk):

| Decile | Predicted | Observed |
|---|---|---|
| 1 | 0.7% | 0.7% |
| 2 | 1.0% | 1.0% |
| 3 | 1.3% | 1.1% |
| 4 | 1.6% | 1.6% |
| 5 | 2.0% | 1.8% |
| 6 | 2.5% | 2.3% |
| 7 | 3.0% | 3.6% |
| 8 | 3.9% | 4.5% |
| 9 | 5.3% | 5.9% |
| 10 | 14.5% | 14.3% |

What that model leans on (AUC lost when the feature is shuffled):

- `cur_last_on_min` 0.0687
- `playoffs` 0.0159
- `inj_decay` 0.0124
- `game_no` 0.0078
- `cur_margin` 0.0076
- `inj_per100` 0.0066
- `min_avg3` 0.0024
- `min_avg10` 0.0021
- `team_inj_rate_365` 0.0019
- `cur_q4ot_min` 0.0017
- `b2b_next14` 0.0014
- `exp` 0.0010

## Target `g5`: a new injury makes the player miss one of the team's next 5 games

Test seasons 2024-25 and 2025-26: 53,530 player-games, 8,553 followed by a new injury (16.0%).

| Model | AUC (95% CI) | Avg precision | Brier skill | Top-10% lift | Top-10% catches |
|---|---|---|---|---|---|
| Base rate (everyone gets the average) | 0.500 | 0.160 | -0.003 | 1.00x | 100% |
| Age + injury history (logistic) | 0.669 (0.653-0.685) | 0.275 | 0.049 | 2.08x | 21% |
| All features (logistic) | 0.701 (0.688-0.718) | 0.303 | 0.070 | 2.25x | 22% |
| All features (gradient boosting) | 0.703 (0.689-0.719) | 0.310 | 0.074 | 2.31x | 23% |
| All features + play-by-play load (gradient boosting) | 0.703 (0.689-0.719) | 0.310 | 0.074 | 2.29x | 23% |
| All features + that day's injury report (gradient boosting) | 0.704 (0.690-0.720) | 0.313 | 0.075 | 2.32x | 23% |

All features (gradient boosting), by test season:

| Season | Player-games | Injury rate | AUC | Top-10% lift |
|---|---|---|---|---|
| 2024-25 | 26,567 | 16.5% | 0.711 | 2.47x |
| 2025-26 | 26,963 | 15.5% | 0.695 | 2.15x |

Calibration (deciles of predicted risk):

| Decile | Predicted | Observed |
|---|---|---|
| 1 | 3.9% | 4.6% |
| 2 | 5.7% | 6.2% |
| 3 | 7.6% | 7.2% |
| 4 | 9.8% | 9.7% |
| 5 | 12.1% | 11.9% |
| 6 | 14.7% | 15.4% |
| 7 | 17.7% | 20.5% |
| 8 | 21.3% | 21.1% |
| 9 | 26.5% | 26.2% |
| 10 | 38.3% | 37.0% |

The same scores ranked against narrower injury definitions:

- g5_3plus: AUC 0.654, top-10% lift 1.89x
- g5_muscle: AUC 0.673, top-10% lift 2.25x

What that model leans on (AUC lost when the feature is shuffled):

- `inj_per100` 0.0155
- `inj_decay` 0.0120
- `playoffs` 0.0088
- `game_no` 0.0034
- `prone_shrunk` 0.0033
- `team_inj_rate_365` 0.0029
- `min_avg10` 0.0027
- `min_avg3` 0.0024
- `season_min` 0.0019
- `min_last2` 0.0016
- `exp` 0.0013
- `listed_played_21` 0.0012

## Target `g5_3plus`: a new injury makes the player miss one of the team's next 5 games (3plus)

Test seasons 2024-25 and 2025-26: 53,530 player-games, 3,541 followed by a new injury (6.6%).

| Model | AUC (95% CI) | Avg precision | Brier skill | Top-10% lift | Top-10% catches |
|---|---|---|---|---|---|
| Base rate (everyone gets the average) | 0.500 | 0.066 | -0.001 | 1.00x | 100% |
| Age + injury history (logistic) | 0.619 (0.600-0.640) | 0.097 | 0.010 | 1.76x | 18% |
| All features (logistic) | 0.641 (0.624-0.661) | 0.108 | 0.015 | 1.92x | 19% |
| All features (gradient boosting) | 0.649 (0.629-0.668) | 0.107 | 0.016 | 1.89x | 19% |
| All features + play-by-play load (gradient boosting) | 0.655 (0.636-0.674) | 0.109 | 0.018 | 1.94x | 19% |
| All features + that day's injury report (gradient boosting) | 0.654 (0.635-0.674) | 0.111 | 0.018 | 1.95x | 20% |

All features (gradient boosting), by test season:

| Season | Player-games | Injury rate | AUC | Top-10% lift |
|---|---|---|---|---|
| 2024-25 | 26,567 | 7.0% | 0.642 | 1.90x |
| 2025-26 | 26,963 | 6.2% | 0.658 | 1.87x |

Calibration (deciles of predicted risk):

| Decile | Predicted | Observed |
|---|---|---|
| 1 | 2.1% | 1.8% |
| 2 | 3.2% | 2.8% |
| 3 | 4.0% | 4.3% |
| 4 | 4.8% | 5.1% |
| 5 | 5.5% | 5.3% |
| 6 | 6.3% | 7.2% |
| 7 | 7.2% | 8.0% |
| 8 | 8.3% | 9.2% |
| 9 | 9.9% | 10.0% |
| 10 | 13.5% | 12.5% |

The same scores ranked against narrower injury definitions:

- g5: AUC 0.670, top-10% lift 1.89x

What that model leans on (AUC lost when the feature is shuffled):

- `inj_per100` 0.0149
- `game_no` 0.0043
- `min_avg3` 0.0031
- `season_min_avg` 0.0028
- `missed_decay` 0.0028
- `games_next14` 0.0025
- `bmi` 0.0023
- `min_avg10` 0.0022
- `prone_shrunk` 0.0022
- `season_games` 0.0019
- `playoffs` 0.0018
- `missed_inj_365` 0.0014

## Target `y14`: a new injury makes the player miss a game in the next 14 days

Test seasons 2024-25 and 2025-26: 56,265 player-games, 10,647 followed by a new injury (18.9%).

| Model | AUC (95% CI) | Avg precision | Brier skill | Top-10% lift | Top-10% catches |
|---|---|---|---|---|---|
| Base rate (everyone gets the average) | 0.500 | 0.189 | -0.004 | 1.00x | 100% |
| Age + injury history (logistic) | 0.669 (0.652-0.685) | 0.311 | 0.053 | 1.97x | 20% |
| All features (logistic) | 0.723 (0.709-0.736) | 0.368 | 0.097 | 2.26x | 23% |
| All features (gradient boosting) | 0.726 (0.712-0.739) | 0.375 | 0.101 | 2.33x | 23% |
| All features + play-by-play load (gradient boosting) | 0.723 (0.707-0.736) | 0.369 | 0.096 | 2.33x | 23% |
| All features + that day's injury report (gradient boosting) | 0.726 (0.711-0.739) | 0.374 | 0.101 | 2.35x | 24% |

All features (gradient boosting), by test season:

| Season | Player-games | Injury rate | AUC | Top-10% lift |
|---|---|---|---|---|
| 2024-25 | 27,913 | 19.3% | 0.732 | 2.52x |
| 2025-26 | 28,352 | 18.5% | 0.721 | 2.14x |

Calibration (deciles of predicted risk):

| Decile | Predicted | Observed |
|---|---|---|
| 1 | 3.7% | 3.6% |
| 2 | 6.2% | 7.0% |
| 3 | 8.5% | 8.4% |
| 4 | 11.1% | 11.4% |
| 5 | 14.1% | 13.1% |
| 6 | 17.4% | 16.6% |
| 7 | 21.1% | 24.3% |
| 8 | 25.8% | 28.1% |
| 9 | 32.6% | 32.8% |
| 10 | 47.3% | 44.1% |

The same scores ranked against narrower injury definitions:

- y14_3plus: AUC 0.681, top-10% lift 1.96x
- y14_muscle: AUC 0.690, top-10% lift 2.34x
- y14_lower: AUC 0.715, top-10% lift 2.31x

What that model leans on (AUC lost when the feature is shuffled):

- `games_next14` 0.0220
- `inj_per100` 0.0144
- `playoffs` 0.0125
- `inj_decay` 0.0111
- `min_avg10` 0.0041
- `game_no` 0.0038
- `team_inj_rate_365` 0.0038
- `min_avg3` 0.0032
- `prone_shrunk` 0.0029
- `season_min` 0.0025
- `b2b_next14` 0.0018
- `exp` 0.0017
