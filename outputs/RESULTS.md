# Results

Built 2026-10-19T18:14:31. Report rows 134,220, of which 316 could not be matched to a player. New injuries by season (ending year): {'2019': 510, '2020': 724, '2021': 810, '2022': 938, '2023': 1005, '2024': 1035, '2025': 1152, '2026': 1109}. Median games missed: 2.

## Target `g1`: a new injury makes the player miss the team's next game, scored right after the game with its play-by-play

Test seasons 2024-25 and 2025-26: 56,274 player-games, 2,081 followed by a new injury (3.7%).

| Model | AUC (95% CI) | Avg precision | Brier skill | Top-10% lift | Top-10% catches |
|---|---|---|---|---|---|
| Base rate (everyone gets the average) | 0.500 | 0.037 | -0.001 | 1.00x | 100% |
| All features (gradient boosting) | 0.704 (0.690-0.719) | 0.097 | 0.025 | 2.73x | 27% |
| After the game: all features + that game's play-by-play (gradient boosting) | 0.762 (0.748-0.775) | 0.224 | 0.102 | 3.91x | 39% |

After the game: all features + that game's play-by-play (gradient boosting), by test season:

| Season | Player-games | Injury rate | AUC | Top-10% lift |
|---|---|---|---|---|
| 2024-25 | 27,916 | 3.8% | 0.766 | 3.93x |
| 2025-26 | 28,358 | 3.6% | 0.759 | 3.85x |

Calibration (deciles of predicted risk):

| Decile | Predicted | Observed |
|---|---|---|
| 1 | 0.6% | 0.7% |
| 2 | 0.9% | 1.1% |
| 3 | 1.2% | 1.0% |
| 4 | 1.6% | 1.6% |
| 5 | 2.0% | 1.9% |
| 6 | 2.5% | 2.6% |
| 7 | 3.1% | 3.5% |
| 8 | 3.9% | 4.5% |
| 9 | 5.5% | 5.6% |
| 10 | 15.1% | 14.5% |

What that model leans on (AUC lost when the feature is shuffled):

- `cur_last_on_min` 0.0679
- `playoffs` 0.0149
- `inj_decay` 0.0101
- `game_no` 0.0085
- `cur_margin` 0.0075
- `inj_per100` 0.0065
- `min_avg10` 0.0031
- `team_inj_rate_365` 0.0022
- `season_min` 0.0016
- `b2b_next14` 0.0015
- `min_avg3` 0.0014
- `prone_shrunk` 0.0013

## Target `g5`: a new injury makes the player miss one of the team's next 5 games

Test seasons 2024-25 and 2025-26: 53,530 player-games, 8,599 followed by a new injury (16.1%).

| Model | AUC (95% CI) | Avg precision | Brier skill | Top-10% lift | Top-10% catches |
|---|---|---|---|---|---|
| Base rate (everyone gets the average) | 0.500 | 0.161 | -0.003 | 1.00x | 100% |
| Age + injury history (logistic) | 0.668 (0.652-0.686) | 0.276 | 0.049 | 2.04x | 20% |
| All features (logistic) | 0.702 (0.689-0.719) | 0.305 | 0.071 | 2.26x | 23% |
| All features (gradient boosting) | 0.704 (0.690-0.721) | 0.312 | 0.075 | 2.32x | 23% |
| All features + play-by-play load (gradient boosting) | 0.704 (0.691-0.721) | 0.313 | 0.075 | 2.30x | 23% |
| All features + that day's injury report (gradient boosting) | 0.706 (0.692-0.723) | 0.314 | 0.076 | 2.32x | 23% |

All features (gradient boosting), by test season:

| Season | Player-games | Injury rate | AUC | Top-10% lift |
|---|---|---|---|---|
| 2024-25 | 26,567 | 16.5% | 0.711 | 2.50x |
| 2025-26 | 26,963 | 15.6% | 0.697 | 2.14x |

Calibration (deciles of predicted risk):

| Decile | Predicted | Observed |
|---|---|---|
| 1 | 4.1% | 4.6% |
| 2 | 5.8% | 6.3% |
| 3 | 7.7% | 7.4% |
| 4 | 9.8% | 9.6% |
| 5 | 12.1% | 11.4% |
| 6 | 14.8% | 16.5% |
| 7 | 17.9% | 19.6% |
| 8 | 21.3% | 21.8% |
| 9 | 26.4% | 26.3% |
| 10 | 37.9% | 37.3% |

The same scores ranked against narrower injury definitions:

- g5_3plus: AUC 0.654, top-10% lift 1.89x
- g5_muscle: AUC 0.677, top-10% lift 2.19x

What that model leans on (AUC lost when the feature is shuffled):

- `inj_per100` 0.0156
- `inj_decay` 0.0108
- `playoffs` 0.0095
- `game_no` 0.0036
- `prone_shrunk` 0.0036
- `min_avg10` 0.0028
- `team_inj_rate_365` 0.0028
- `min_avg3` 0.0018
- `min_last2` 0.0016
- `season_min` 0.0013
- `listed_played_21` 0.0009
- `exp` 0.0008

## Target `g5_3plus`: a new injury makes the player miss one of the team's next 5 games (3plus)

Test seasons 2024-25 and 2025-26: 53,530 player-games, 3,524 followed by a new injury (6.6%).

| Model | AUC (95% CI) | Avg precision | Brier skill | Top-10% lift | Top-10% catches |
|---|---|---|---|---|---|
| Base rate (everyone gets the average) | 0.500 | 0.066 | -0.001 | 1.00x | 100% |
| Age + injury history (logistic) | 0.615 (0.594-0.636) | 0.095 | 0.010 | 1.70x | 17% |
| All features (logistic) | 0.639 (0.622-0.659) | 0.106 | 0.015 | 1.89x | 19% |
| All features (gradient boosting) | 0.651 (0.631-0.671) | 0.107 | 0.017 | 1.92x | 19% |
| All features + that day's injury report (gradient boosting) | 0.654 (0.634-0.673) | 0.109 | 0.018 | 1.98x | 20% |

All features (gradient boosting), by test season:

| Season | Player-games | Injury rate | AUC | Top-10% lift |
|---|---|---|---|---|
| 2024-25 | 26,567 | 7.0% | 0.645 | 2.06x |
| 2025-26 | 26,963 | 6.2% | 0.660 | 1.75x |

Calibration (deciles of predicted risk):

| Decile | Predicted | Observed |
|---|---|---|
| 1 | 2.1% | 1.7% |
| 2 | 3.1% | 3.1% |
| 3 | 4.0% | 4.3% |
| 4 | 4.8% | 4.5% |
| 5 | 5.6% | 5.7% |
| 6 | 6.4% | 6.4% |
| 7 | 7.2% | 8.4% |
| 8 | 8.3% | 8.9% |
| 9 | 9.8% | 10.2% |
| 10 | 13.2% | 12.7% |

The same scores ranked against narrower injury definitions:

- g5: AUC 0.673, top-10% lift 1.93x

What that model leans on (AUC lost when the feature is shuffled):

- `inj_per100` 0.0086
- `game_no` 0.0052
- `min_avg10` 0.0029
- `prone_shrunk` 0.0029
- `season_min_avg` 0.0028
- `min_avg3` 0.0026
- `playoffs` 0.0025
- `games_next14` 0.0021
- `season_games` 0.0020
- `weight_lb` 0.0016
- `blk36` 0.0014
- `team_inj_rate_365` 0.0013

## Target `y14`: a new injury makes the player miss a game in the next 14 days

Test seasons 2024-25 and 2025-26: 56,265 player-games, 10,704 followed by a new injury (19.0%).

| Model | AUC (95% CI) | Avg precision | Brier skill | Top-10% lift | Top-10% catches |
|---|---|---|---|---|---|
| Base rate (everyone gets the average) | 0.500 | 0.190 | -0.004 | 1.00x | 100% |
| Age + injury history (logistic) | 0.668 (0.651-0.684) | 0.311 | 0.053 | 1.95x | 20% |
| All features (logistic) | 0.724 (0.708-0.736) | 0.370 | 0.098 | 2.27x | 23% |
| All features (gradient boosting) | 0.724 (0.709-0.738) | 0.372 | 0.099 | 2.30x | 23% |
| All features + that day's injury report (gradient boosting) | 0.726 (0.711-0.739) | 0.372 | 0.100 | 2.31x | 23% |

All features (gradient boosting), by test season:

| Season | Player-games | Injury rate | AUC | Top-10% lift |
|---|---|---|---|---|
| 2024-25 | 27,913 | 19.4% | 0.732 | 2.47x |
| 2025-26 | 28,352 | 18.6% | 0.717 | 2.11x |

Calibration (deciles of predicted risk):

| Decile | Predicted | Observed |
|---|---|---|
| 1 | 3.6% | 3.8% |
| 2 | 6.1% | 6.7% |
| 3 | 8.5% | 9.4% |
| 4 | 11.2% | 10.4% |
| 5 | 14.1% | 14.1% |
| 6 | 17.5% | 17.1% |
| 7 | 21.4% | 23.2% |
| 8 | 26.2% | 28.8% |
| 9 | 33.1% | 33.1% |
| 10 | 47.8% | 43.7% |

The same scores ranked against narrower injury definitions:

- y14_3plus: AUC 0.678, top-10% lift 1.93x
- y14_muscle: AUC 0.689, top-10% lift 2.21x
- y14_lower: AUC 0.712, top-10% lift 2.30x

What that model leans on (AUC lost when the feature is shuffled):

- `games_next14` 0.0213
- `inj_per100` 0.0169
- `playoffs` 0.0129
- `inj_decay` 0.0107
- `min_avg10` 0.0045
- `game_no` 0.0043
- `team_inj_rate_365` 0.0037
- `min_avg3` 0.0036
- `prone_shrunk` 0.0030
- `season_min` 0.0025
- `b2b_next14` 0.0017
- `missed_decay` 0.0012
