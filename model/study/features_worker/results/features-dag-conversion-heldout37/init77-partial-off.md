# INIT residual bits by part, steers off

Forms with rows: 77 of 77 (missing: []). Walks 240. The parts sum to each form's bits_mean within 0.007 bits. Form bits are means over orders and over the two seeds of the cut scope.

## Bits by part

Each cell: total bits, median per form, forms under 25 with the part at 0 bits.

| Part | all | not held | held |
|---|---|---|---|
| component | 324.0 / 3.90 / 9 of 77 | 233.2 / 3.90 / 7 of 55 | 90.8 / 3.90 / 2 of 22 |
| ports | 216.3 / 1.65 / 10 of 77 | 148.4 / 1.65 / 9 of 55 | 67.9 / 1.81 / 1 of 22 |
| key labels | 80.4 / 0.43 / 4 of 77 | 62.8 / 0.43 / 3 of 55 | 17.6 / 0.43 / 1 of 22 |
| heads | 217.2 / 0.55 / 6 of 77 | 169.0 / 0.55 / 4 of 55 | 48.2 / 1.34 / 2 of 22 |
| reads | 2912.5 / 30.71 / 76 of 77 | 2015.7 / 30.82 / 54 of 55 | 896.8 / 29.77 / 22 of 22 |
|   relation | 1494.8 / 17.28 / 35 of 77 | 1003.5 / 17.02 / 21 of 55 | 491.3 / 18.37 / 14 of 22 |
|   columns | 472.1 / 4.70 / 7 of 77 | 352.5 / 5.45 / 6 of 55 | 119.7 / 4.52 / 1 of 22 |
|   values | 423.5 / 3.37 / 8 of 77 | 279.9 / 3.37 / 7 of 55 | 143.6 / 3.14 / 1 of 22 |
|   stops | 643.7 / 8.02 / 9 of 77 | 471.9 / 8.25 / 8 of 55 | 171.8 / 6.48 / 1 of 22 |
|   join mix | -232.2 / -4.00 / 0 of 77 | -161.5 / -4.02 / 0 of 55 | -70.7 / -3.73 / 0 of 22 |
|   OR and ALL coins | 110.5 / 0.40 / 4 of 77 | 69.4 / 0.40 / 3 of 55 | 41.2 / 0.40 / 1 of 22 |

## Pairs at 0 bits, the first 12

| Pair | all | not held | held |
|---|---|---|---|
| component + reads | 77 | 55 | 22 |
| heads + reads | 77 | 55 | 22 |
| ports + reads | 76 | 54 | 22 |
| key labels + reads | 76 | 54 | 22 |
| relation + stops | 56 | 38 | 18 |
| relation + columns | 50 | 33 | 17 |
| component + relation | 47 | 30 | 17 |
| heads + relation | 46 | 31 | 15 |
| relation + values | 46 | 28 | 18 |
| ports + relation | 41 | 25 | 16 |
| key labels + relation | 39 | 23 | 16 |
| relation + OR and ALL coins | 37 | 23 | 14 |

## Reads of an earlier form

Scope = the forms of the cut scope. Cells: median count, median log2, gold in.

| Set, place | Reads | Weight | Median bits | all | unread_scope | unread_pick |
|---|---|---|---|---|---|---|
| all, key | 104 | 52.0 | 5.76 | 36.5, 5.19, 104 | 4.0, 2.0, 92 | 4.0, 2.0, 92 |
| all, port | 346 | 173.0 | 5.29 | 36.0, 5.17, 346 | 4.0, 2.0, 189 | 3.0, 1.58, 79 |
| not held, key | 78 | 39.0 | 5.74 | 36.0, 5.17, 78 | 4.0, 2.0, 70 | 4.0, 2.0, 70 |
| not held, port | 248 | 124.0 | 5.25 | 36.0, 5.17, 248 | 4.0, 2.0, 126 | 3.0, 1.58, 54 |
| held, key | 26 | 13.0 | 6.15 | 48.0, 5.58, 26 | 5.0, 2.32, 22 | 5.0, 2.32, 22 |
| held, port | 98 | 49.0 | 5.38 | 37.0, 5.21, 98 | 5.0, 2.32, 63 | 4.0, 2.0, 25 |

Forms under 25 with each read of an earlier form paying log2 of the set where gold's target is in the set: `{"all": {"all": 3, "unread_scope": 16, "unread_pick": 11}, "not held": {"all": 2, "unread_scope": 11, "unread_pick": 9}, "held": {"all": 1, "unread_scope": 5, "unread_pick": 2}}`.

## Component pick

| Set | Picks | Rows on some input: Q1, median, Q3 | Paid: sum, median | Uniform some: sum | Gold inside: some, every | Gold in earlier (scope) forms | Picks in the pool run, gold there | Under 25 at 0 / uniform some / priors some |
|---|---|---|---|---|---|---|---|---|
| all | 77 | (10.0, 16.0, 17.0) | 324.0, 3.9 | 285.1 | 77, 76 | 33.5 | 22, 21 | 9 / 2 / 5 |
| not held | 55 | (10.0, 16.0, 17.0) | 233.2, 3.9 | 203.0 | 55, 55 | 22.0 | 0, 0 | 7 / 2 / 4 |
| held | 22 | (10.0, 16.0, 18.5) | 90.8, 3.9 | 82.1 | 22, 21 | 11.5 | 22, 21 | 2 / 0 / 1 |
