# Tune reads of the rank model, non-held tasks

Tasks: 50 non-held tasks with 600 s pool nodes (N600), 49 with a ready form, 82 ready forms. Static chance per opening, uses 0. Arms are named in `final_arms.py`; `h` arms are the seeded-holdout fits of `fit-jobs3.txt`.

## Real gold tables, N600, 739 tables (3 hold an Ident)

| Arm | t | Median chance per opening | Median rank, whole | Median rank RULE, INIT |
|---|---|---|---|---|
| hand | 1.0 | 9.8e-06 | 106 | 800, 139 |
| hand | .05 | 8.0e-03 | 106 | 800, 139 |
| a1h (T, both) | .5 | 1.58e-02 | 47 | 207.5, 91 |
| a5h (TS, both) | .5 | 1.85e-02 | 38.5 | 123, 178 |
| a6h (H, both) | .75 | 2.12e-02 | 44 | 80, 192 |
| c6h (shuffled labels) | .75 | 6.49e-03 | 170.5 | 1835, 1287.5 |
| d1h (depth only) | .75 | 5.93e-03 | 104.5 | 1310, 422 |

## Ident cell, seeded gold Ident tables, 120 s (S120), 162 tables

| Arm | Median rank | Top 10 | Top 100 | Median chance per opening |
|---|---|---|---|---|
| hand | 272 | 0 | .117 | 6.5e-07 |
| a1h | 18.5 | .414 | .840 | 3.2e-02 to 3.9e-02 |
| a5h | 19 | .383 | .827 | 2.9e-02 to 3.7e-02 |
| a6h | 20 | .420 | .821 | 2.8e-02 to 3.1e-02 |
| c6h | 298 | .025 | .154 | 7.0e-03 to 7.9e-03 |
| d1h | 167 | .062 | .327 | 9.1e-03 to 9.5e-03 |

Seeded tables can carry a build trait that pool nodes don't have, so the Ident cell can read above what a pool gives. The held read on H and B is the test.
