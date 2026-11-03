# Relation pick, per-relation models on pool scopes: summary

Each number is generated from `read-*.json` and `compare.jsonl`. Saved bits are against the steered prior on the same rows, with 95% task intervals. Gold is `gold-v3-extended-cut/view-pass1` on pool rows and `gold-v3-helper-forms-a036da074` base view on census rows.

## Saved bits per gold-alive pick

| Model | Pool rows, 920 picks, 32 tasks | Same forms, parents scope, 248 picks | Wide pool rows, oracle context with junk, 4,726 picks | Wide parents, 2,434 picks | Census parents, 1,761 picks |
|---|---|---|---|---|---|
| Primary as fit on parents rows, reads written order | -0.07 (-0.25 to +0.09) | -0.01 (-0.23 to +0.18) | +0.02 (-0.05 to +0.10) | +0.10 (+0.03 to +0.18) | +0.39 (+0.31 to +0.47) |
| Refit on parents rows, no lexical order | -0.09 (-0.21 to +0.02) | -0.05 (-0.20 to +0.08) | not read | not read | +0.32 (+0.25 to +0.40) |
| Refit on pool rows and parents rows, no lexical order | +0.32 (+0.13 to +0.47) | not read | +0.30 (+0.24 to +0.36) | +0.18 (+0.11 to +0.24) | not read |
| The same without facts of a form's text | +0.28 (+0.11 to +0.42) | not read | +0.30 (+0.25 to +0.36) | not read | not read |
| Control of the primary as fit | -0.00 (-0.01 to +0.01) | not read | not read | not read | not read |
| Control of the refit on parents rows | +0.00 (-0.01 to +0.03) | not read | not read | not read | not read |
| Control of the refit on pool rows | -0.02 (-0.07 to -0.00) | not read | not read | not read | not read |

## Random atom order, gold-alive picks

| Model | Pool rows in random order, 566 picks, 26 tasks | Census forms in random order, 640 picks, 36 tasks |
|---|---|---|
| Refit on pool rows, random order fit rows | +0.52 (+0.30 to +0.77) | +0.12 (+0.00 to +0.23) |
| Control of that refit | -0.02 (-0.05 to +0.01) | not read |
| Refit on pool rows and parents rows, written order fit rows | +0.01 (-0.31 to +0.32) | not read |
| Refit on parents rows, written order fit rows | -0.39 (-0.60 to -0.17) | +0.06 (-0.03 to +0.14) |
| Primary as fit, reads written order | not read | +0.05 (-0.01 to +0.12) |

## By class and position on pool rows, gold-alive picks

| Picks read | Picks | Prior bits | Primary as fit, reads written order | Refit on parents rows | Refit on pool rows | Census parents read: primary as fit | Census parents read: refit on parents rows |
|---|---|---|---|---|---|---|---|
| Gold alive | 920 | 3.66 | -0.07 (-0.25 to +0.09) | -0.09 (-0.21 to +0.02) | +0.32 (+0.13 to +0.47) | +0.39 (+0.31 to +0.47) | +0.32 (+0.25 to +0.40) |
| Derived relation in scope | 249 | 3.11 | +0.56 (+0.22 to +0.85) | +0.43 (+0.17 to +0.64) | +0.36 (-0.07 to +0.76) | +0.40 (+0.31 to +0.50) | +0.37 (+0.30 to +0.45) |
| Lib relation | 193 | 6.68 | -0.79 (-1.18 to -0.48) | -0.63 (-0.96 to -0.37) | -0.55 (-0.87 to -0.30) | +0.83 (+0.45 to +1.18) | +0.76 (+0.40 to +1.09) |
| The form's own earlier atom | 83 | 4.03 | +0.22 (-0.39 to +0.64) | -0.13 (-0.73 to +0.28) | +0.54 (+0.14 to +0.80) | +0.05 (-0.15 to +0.24) | -0.06 (-0.22 to +0.09) |
| The rest | 395 | 2.45 | -0.17 (-0.39 to +0.02) | -0.13 (-0.33 to +0.04) | +0.67 (+0.50 to +0.85) | +0.32 (+0.22 to +0.42) | +0.23 (+0.12 to +0.33) |
| First atom | 401 | 3.76 | +0.02 (-0.22 to +0.25) | +0.04 (-0.16 to +0.22) | +0.49 (+0.27 to +0.71) | +0.25 (+0.14 to +0.36) | +0.30 (+0.21 to +0.39) |
| Second atom | 265 | 3.89 | -0.37 (-0.71 to -0.05) | -0.40 (-0.70 to -0.10) | -0.03 (-0.49 to +0.38) | +0.42 (+0.31 to +0.55) | +0.35 (+0.24 to +0.47) |
| Third atom | 127 | 3.27 | -0.13 (-0.66 to +0.31) | +0.00 (-0.35 to +0.32) | +0.37 (+0.07 to +0.66) | +0.45 (+0.34 to +0.58) | +0.37 (+0.28 to +0.48) |
| Later atoms | 127 | 3.21 | +0.36 (-0.15 to +0.65) | +0.06 (-0.39 to +0.33) | +0.46 (+0.24 to +0.72) | +0.43 (+0.30 to +0.55) | +0.30 (+0.16 to +0.43) |

Each model's full table, with class by position, is in `table-*.md`. The parents read of the first record, at all picks of the census, is in its `table-final-hyb-noorder.md`. This table reads gold-alive picks.

## Keys, per form and cost

- Refit on pool rows, pool rows: keys past 1 bit net [('derived-proposer', 1.36, 103), ('derived-init', 1.26, 64)], 15.6% of picks. Per walk, saved +0.85 (+0.38 to +1.30); at 25 bits or more, +0.69 (-0.26 to +1.58) on 68 walks. Under 25: 333 to 337 of 401, 5 taken under, 1 pushed over.
- Primary as fit, pool rows: keys past 1 bit net [], 0.0% of picks. Per walk, saved -0.21 (-0.70 to +0.23); at 25 bits or more, -1.27 (-2.60 to +0.05) on 68 walks. Under 25: 333 to 335 of 401, 4 taken under, 2 pushed over.
- Refit on pool rows, wide pool rows: keys past 1 bit net [('derived-proposer', 2.56, 142), ('derived-det', 2.33, 110)], 5.0% of picks. Per walk, saved +0.87 (+0.67 to +1.09); at 25 bits or more, +0.97 (+0.57 to +1.38) on 481 walks. Under 25: 1300 to 1330 of 1781, 49 taken under, 19 pushed over.
- Random order refit, random order pool rows: keys past 1 bit net [('derived-init', 1.39, 53)], 8.6% of picks. Per walk, saved +0.97 (+0.29 to +1.84); at 25 bits or more, +0.48 (-0.92 to +2.36) on 31 walks. Under 25: 203 to 199 of 234, 0 taken under, 4 pushed over.
- Cost, final-orderfree-union on held-pool: 0.13 ms per pick in a batch, 44 ms alone, 87 options per pick; content facts 13 ms per pick.
- Cost, final-orderfree-union on held-wide-pool: 0.24 ms per pick in a batch, 51 ms alone, 115 options per pick; content facts 114 ms per pick.

## Compare lines

- final-orderfree-on-census-shuffled minus final-orderfree-on-held, 191 forms: -0.24 (-0.39 to -0.12).
- asfit-final-hyb-noorder-on-census-shuffled minus asfit-final-hyb-noorder-on-held, 191 forms: -0.26 (-0.40 to -0.15).
- final-orderfree-on-held-pool, stratum built: +0.09 (-0.23 to +0.35), 286 picks, 38 forms, 20 tasks.
- final-orderfree-on-held-pool, stratum holds: +0.01 (-0.16 to +0.19), 326 picks, 33 forms, 16 tasks.
- final-orderfree-on-held-pool, stratum noreads: -0.36 (-0.50 to -0.22), 308 picks, 44 forms, 24 tasks.
- asfit-final-hyb-noorder-on-held-pool, stratum built: +0.11 (-0.30 to +0.41), 286 picks, 38 forms, 20 tasks.
- asfit-final-hyb-noorder-on-held-pool, stratum holds: +0.15 (-0.09 to +0.35), 326 picks, 33 forms, 16 tasks.
- asfit-final-hyb-noorder-on-held-pool, stratum noreads: -0.46 (-0.63 to -0.28), 308 picks, 44 forms, 24 tasks.
- final-orderfree-on-held-pool minus final-orderfree-on-held-parents, 108 forms: -0.04 (-0.15 to +0.08).
- final-orderfree-on-census-shuffled, stratum moved: +0.04 (-0.10 to +0.16), 407 picks, 110 forms, 32 tasks.
- final-orderfree-on-census-shuffled, stratum unmoved: +0.10 (+0.00 to +0.22), 233 picks, 81 forms, 30 tasks.
- asfit-final-hyb-noorder-on-census-shuffled, stratum moved: +0.01 (-0.09 to +0.11), 407 picks, 110 forms, 32 tasks.
- asfit-final-hyb-noorder-on-census-shuffled, stratum unmoved: +0.13 (+0.02 to +0.26), 233 picks, 81 forms, 30 tasks.
- final-orderfree-union-on-held-pool, stratum built: +0.31 (+0.01 to +0.57), 286 picks, 38 forms, 20 tasks.
- final-orderfree-union-on-held-pool, stratum holds: +0.39 (+0.09 to +0.62), 326 picks, 33 forms, 16 tasks.
- final-orderfree-union-on-held-pool, stratum noreads: +0.25 (+0.08 to +0.43), 308 picks, 44 forms, 24 tasks.
- final-orderfree-union-on-held-pool minus final-orderfree-on-held-pool, 108 forms: +0.40 (+0.26 to +0.55).
- final-orderfree-union-on-held-wide-pool minus final-orderfree-union-on-held-wide-parents, 833 forms: +0.14 (+0.11 to +0.18).
- asfit-final-hyb-noorder-on-held-wide-pool minus asfit-final-hyb-noorder-on-held-wide-parents, 833 forms: -0.06 (-0.10 to -0.03).
- final-orderfree-union-on-held-wide-pool, stratum found: +0.34 (+0.12 to +0.53), 403 picks, 97 forms, 29 tasks.
- final-orderfree-union-on-held-wide-pool, stratum oracle: +0.30 (+0.23 to +0.37), 4323 picks, 805 forms, 34 tasks.
- final-orderfree-union-on-held-pool minus asfit-final-hyb-noorder-on-held-pool, 108 forms: +0.38 (+0.24 to +0.55).
- final-orderfree-shuffled-on-held-pool-shuffled, stratum moved: +0.17 (-0.14 to +0.48), 209 picks, 25 forms, 15 tasks.
- final-orderfree-shuffled-on-held-pool-shuffled, stratum unmoved: +0.72 (+0.43 to +1.06), 357 picks, 39 forms, 21 tasks.
- Order, census, refit with no lexical order, moved forms, 110: random +0.04 (-0.10 to +0.16), written +0.42 (+0.26 to +0.58), difference -0.38 (-0.61 to -0.20).
- Order, census, refit with no lexical order, unmoved forms, 81: random +0.10 (+0.00 to +0.22), written +0.10 (+0.00 to +0.22), difference +0.00 (+0.00 to +0.00).
- Order, census, model as fit, moved forms, 110: random +0.01 (-0.09 to +0.11), written +0.43 (+0.27 to +0.60), difference -0.42 (-0.63 to -0.24).
- Order, census, model as fit, unmoved forms, 81: random +0.13 (+0.02 to +0.25), written +0.13 (+0.02 to +0.25), difference +0.00 (+0.00 to +0.00).
- Order, pool rows, refit with no lexical order, moved forms, 25: random -0.59 (-1.00 to -0.17), written -0.06 (-0.35 to +0.22), difference -0.54 (-1.03 to +0.04).
- Order, pool rows, refit with no lexical order, unmoved forms, 39: random -0.28 (-0.51 to -0.06), written -0.28 (-0.51 to -0.06), difference +0.00 (+0.00 to +0.00).
- Order, pool rows, refit on pool rows, moved forms, 25: random -0.30 (-0.81 to +0.20), written +0.08 (-0.31 to +0.36), difference -0.37 (-0.97 to +0.33).
- Order, pool rows, refit on pool rows, unmoved forms, 39: random +0.19 (-0.11 to +0.46), written +0.19 (-0.11 to +0.46), difference +0.00 (+0.00 to +0.00).
- final-orderfree-union-on-held-pool-shuffled, stratum moved: -0.30 (-0.82 to +0.20), 209 picks, 25 forms, 15 tasks.
- final-orderfree-union-on-held-pool-shuffled, stratum unmoved: +0.19 (-0.11 to +0.47), 357 picks, 39 forms, 21 tasks.
- final-orderfree-shuffled-on-held-pool-shuffled minus final-orderfree-union-on-held-pool-shuffled, 64 forms: +0.51 (+0.22 to +0.80).

## Held reads

One line per read, in `reads.log`.

