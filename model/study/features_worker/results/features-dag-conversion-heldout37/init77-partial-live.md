# INIT residual bits by part, steers live

Forms with rows: 77 of 77 (missing: []). Walks 240. The parts sum to each form's bits_mean within 0.006 bits. Form bits are means over orders and over the two seeds of the cut scope.

## Bits by part

Each cell: total bits, median per form, forms under 25 with the part at 0 bits.

| Part | all | not held | held |
|---|---|---|---|
| component | 324.0 / 3.90 / 9 of 77 | 233.2 / 3.90 / 6 of 55 | 90.8 / 3.90 / 3 of 22 |
| ports | 216.3 / 1.65 / 10 of 77 | 148.4 / 1.65 / 6 of 55 | 67.9 / 1.81 / 4 of 22 |
| key labels | 80.4 / 0.43 / 5 of 77 | 62.8 / 0.43 / 4 of 55 | 17.6 / 0.43 / 1 of 22 |
| heads | 217.2 / 0.55 / 6 of 77 | 169.0 / 0.55 / 4 of 55 | 48.2 / 1.34 / 2 of 22 |
| reads | 2598.5 / 28.03 / 76 of 77 | 1781.4 / 28.03 / 54 of 55 | 817.1 / 28.02 / 22 of 22 |
|   relation | 1245.8 / 14.41 / 34 of 77 | 825.6 / 14.40 / 19 of 55 | 420.2 / 15.16 / 15 of 22 |
|   columns | 592.5 / 6.42 / 13 of 77 | 445.8 / 6.63 / 10 of 55 | 146.7 / 5.54 / 3 of 22 |
|   values | 166.3 / 0.64 / 3 of 77 | 97.1 / 0.64 / 2 of 55 | 69.2 / 0.64 / 1 of 22 |
|   stops | 538.5 / 5.92 / 13 of 77 | 382.2 / 6.17 / 9 of 55 | 156.4 / 5.15 / 4 of 22 |
|   join mix | -55.2 / -0.94 / 3 of 77 | -38.7 / -0.97 / 2 of 55 | -16.5 / -0.84 / 1 of 22 |
|   OR and ALL coins | 110.5 / 0.40 / 3 of 77 | 69.4 / 0.40 / 2 of 55 | 41.2 / 0.40 / 1 of 22 |

## Pairs at 0 bits, the first 12

| Pair | all | not held | held |
|---|---|---|---|
| component + reads | 77 | 55 | 22 |
| heads + reads | 77 | 55 | 22 |
| ports + reads | 76 | 54 | 22 |
| key labels + reads | 76 | 54 | 22 |
| relation + columns | 60 | 41 | 19 |
| relation + stops | 57 | 38 | 19 |
| component + relation | 47 | 30 | 17 |
| ports + relation | 46 | 28 | 18 |
| heads + relation | 45 | 30 | 15 |
| relation + values | 42 | 25 | 17 |
| relation + OR and ALL coins | 40 | 24 | 16 |
| key labels + relation | 38 | 22 | 16 |

## Reads of an earlier form

Scope = the forms of the cut scope. Cells: median count, median log2, gold in.

| Set, place | Reads | Weight | Median bits | all | unread_scope | unread_pick |
|---|---|---|---|---|---|---|
| all, key | 104 | 52.0 | 4.87 | 36.5, 5.19, 104 | 4.0, 2.0, 92 | 4.0, 2.0, 92 |
| all, port | 346 | 173.0 | 4.22 | 36.0, 5.17, 346 | 4.0, 2.0, 189 | 3.0, 1.58, 79 |
| not held, key | 78 | 39.0 | 4.59 | 36.0, 5.17, 78 | 4.0, 2.0, 70 | 4.0, 2.0, 70 |
| not held, port | 248 | 124.0 | 4.03 | 36.0, 5.17, 248 | 4.0, 2.0, 126 | 3.0, 1.58, 54 |
| held, key | 26 | 13.0 | 5.06 | 48.0, 5.58, 26 | 5.0, 2.32, 22 | 5.0, 2.32, 22 |
| held, port | 98 | 49.0 | 4.44 | 37.0, 5.21, 98 | 5.0, 2.32, 63 | 4.0, 2.0, 25 |

Forms under 25 with each read of an earlier form paying log2 of the set where gold's target is in the set: `{"all": {"all": 0, "unread_scope": 14, "unread_pick": 7}, "not held": {"all": 0, "unread_scope": 10, "unread_pick": 6}, "held": {"all": 0, "unread_scope": 4, "unread_pick": 1}}`.

## Component pick

| Set | Picks | Rows on some input: Q1, median, Q3 | Paid: sum, median | Uniform some: sum | Gold inside: some, every | Gold in earlier (scope) forms | Picks in the pool run, gold there | Under 25 at 0 / uniform some / priors some |
|---|---|---|---|---|---|---|---|---|
| all | 77 | (10.0, 16.0, 17.0) | 324.0, 3.9 | 285.1 | 77, 76 | 33.5 | 22, 21 | 9 / 3 / 4 |
| not held | 55 | (10.0, 16.0, 17.0) | 233.2, 3.9 | 203.0 | 55, 55 | 22.0 | 0, 0 | 6 / 2 / 3 |
| held | 22 | (10.0, 16.0, 18.5) | 90.8, 3.9 | 82.1 | 22, 21 | 11.5 | 22, 21 | 3 / 1 / 1 |
