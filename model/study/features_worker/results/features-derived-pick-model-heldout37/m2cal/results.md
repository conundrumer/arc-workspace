# Derived pick model: results

M1 saves 0.21 on C [-1.00, 1.15] (read picks 0.35, builtin picks 0.06) and -0.25 on covered [-1.40, 0.62] a form; M2 saves 1.87 on C [0.18, 3.19] (read picks -0.14, builtin picks 1.71) and 0.38 on covered [-0.94, 1.31] a form; M2s saves 1.02 on C [0.01, 1.89] (read picks -0.24, builtin picks 1.13) and 0.30 on covered [-0.79, 1.11] a form; M1 C closes 0.10 [-0.20, 0.31] of the S - DB gap (median gap 4.05 to 3.85); M1 covered closes -0.04 [-0.44, 0.28] of the S - DB gap (median gap 2.61 to 1.99); M2 C closes 0.44 [0.05, 0.75] of the S - DB gap (median gap 4.05 to 2.00); M2 covered closes 0.17 [-0.23, 0.47] of the S - DB gap (median gap 2.61 to 2.36); M2s C closes 0.24 [0.01, 0.41] of the S - DB gap (median gap 4.05 to 3.46); M2s covered closes 0.15 [-0.13, 0.36] of the S - DB gap (median gap 2.61 to 2.61); against the 0.78 line: M1 C: within, M2 C: within, M2s C: within, M1 covered: below, M2 covered: within, M2s covered: within.

## Saved bits a form (S_off - S_arm), mean and median with a 95% task bootstrap

| set | arm | forms (tasks) | total mean | total median | read picks mean | builtin picks mean | op picks mean | rel_off picks: sum (forms) | mean - 0.78 |
|---|---|---|---|---|---|---|---|---|---|
| C | M1 | 42 (17) | 0.21 [-1.00, 1.15] | 0.99 [-1.07, 1.92] | 0.35 [-0.69, 1.18] | 0.06 [-0.18, 0.28] | -0.01 [-0.30, 0.20] | 11.0 (13) | -0.57 [-1.78, 0.37] |
| C | M2 | 42 (17) | 1.87 [0.18, 3.19] | 2.26 [0.37, 3.58] | -0.14 [-1.40, 0.77] | 1.71 [1.23, 2.10] | 0.67 [0.30, 1.07] | 38.4 (13) | 1.09 [-0.60, 2.41] |
| C | M2s | 42 (17) | 1.02 [0.01, 1.89] | 0.40 [0.00, 2.09] | -0.24 [-1.03, 0.34] | 1.13 [0.63, 1.69] | 0.43 [0.14, 0.83] | 0.0 (13) | 0.24 [-0.77, 1.11] |
| covered | M1 | 43 (19) | -0.25 [-1.40, 0.62] | 0.31 [-0.30, 0.88] | 0.03 [-1.03, 0.81] | -0.17 [-0.33, -0.02] | 0.03 [-0.03, 0.09] | 11.4 (15) | -1.03 [-2.18, -0.16] |
| covered | M2 | 43 (19) | 0.38 [-0.94, 1.31] | 1.06 [0.59, 1.64] | -0.59 [-1.75, 0.27] | 0.90 [0.59, 1.15] | 0.29 [0.09, 0.50] | 7.7 (15) | -0.40 [-1.72, 0.53] |
| covered | M2s | 43 (19) | 0.30 [-0.79, 1.11] | 0.38 [0.00, 1.46] | -0.64 [-1.57, 0.02] | 0.75 [0.50, 0.99] | 0.31 [0.13, 0.51] | 0.0 (15) | -0.48 [-1.57, 0.33] |

## M2 against M2s: the saving that comes from acting at rel_off picks too (mean over forms of the saving of M2 minus that of M2s, 95% task bootstrap)

| set | forms | total | read picks | builtin picks | op picks |
|---|---|---|---|---|---|
| C | 42 | 0.85 [-0.35, 2.16] | 0.10 [-0.75, 0.72] | 0.58 [0.13, 1.07] | 0.24 [0.00, 0.57] |
| covered | 43 | 0.09 [-0.50, 0.49] | 0.05 [-0.51, 0.46] | 0.15 [-0.01, 0.33] | -0.02 [-0.06, 0.00] |

## Against the S - DB gap (forms with DB)

| set | arm | forms | median S_off - DB | median S_arm - DB | sum delta / sum gap |
|---|---|---|---|---|---|
| C | M1 | 40 | 4.05 | 3.85 | 0.10 [-0.20, 0.31] |
| C | M2 | 40 | 4.05 | 2.00 | 0.44 [0.05, 0.75] |
| C | M2s | 40 | 4.05 | 3.46 | 0.24 [0.01, 0.41] |
| covered | M1 | 37 | 2.61 | 1.99 | -0.04 [-0.44, 0.28] |
| covered | M2 | 37 | 2.61 | 2.36 | 0.17 [-0.23, 0.47] |
| covered | M2s | 37 | 2.61 | 2.61 | 0.15 [-0.13, 0.36] |

## Checks

- C: forms 42, ok 42, errors 0. (1) S_off differs from the recorded S on 1 forms. (2) Regroup arm G on 0 forms, differs from split-steer S_on on 0. (3) invalid walks: {'off': 0, 'M1': 0, 'M2': 0, 'M2s': 0}; estimates (orders.exact false): {'off': 1, 'M1': 1, 'M2': 1, 'M2s': 1}. (4) order check on 6 forms, differs on 0. Non-declared relation options at picks {'M1': 0, 'M2': 0, 'M2s': 0}, alt-only options {'M1': 0, 'M2': 0, 'M2s': 0}.
    - off_differs: [('bundle_s0', 'f560132c', 10, 89.27, 89.31)]
- covered: forms 43, ok 43, errors 0. (1) S_off differs from the recorded S on 0 forms. (2) Regroup arm G on 0 forms, differs from split-steer S_on on 0. (3) invalid walks: {'off': 0, 'M1': 0, 'M2': 0, 'M2s': 0}; estimates (orders.exact false): {'off': 0, 'M1': 0, 'M2': 0, 'M2s': 0}. (4) order check on 6 forms, differs on 0. Non-declared relation options at picks {'M1': 0, 'M2': 0, 'M2s': 0}, alt-only options {'M1': 0, 'M2': 0, 'M2s': 0}.
- facts, drawn atoms and row parity (checks.py): {"n600.0of1.jsonl": {"pairs": 20, "picks": 69, "sum_ok": 69, "sum_bad": [], "text_checked": 16, "text_ok": 16, "text_bad": [], "parity_pairs": 10, "parity_picks": 36, "parity_bad": [], "seconds": 1.5, "sum_all_ok": true}, "c120.1of4.jsonl": {"pairs": 20, "picks": 79, "sum_ok": 79, "sum_bad": [], "text_checked": 66, "text_ok": 66, "text_bad": [], "parity_pairs": 10, "parity_picks": 47, "parity_bad": [], "seconds": 3.6, "sum_all_ok": true}}

## Cross-fit on the training rows (pick level, in bits; weighted means)

Read-pick rows, within the derived options (positives' share): even split 3.063, today 2.644, rank model (logit) 2.014; a positive has the largest score: today 0.383, model 0.681. Ablation (boosted ranker): None. Rows 33125.

| rows | count | today | M1 | M2 |
|---|---|---|---|---|
| all rows | 103143 | 3.073 | 2.835 | 2.479 |
| read picks | 33125 | 2.981 | 2.373 | 2.908 |
| builtin picks | 56654 | 3.366 | 3.478 | 2.342 |
| op picks | 13364 | 2.546 | 2.408 | 1.646 |
| read picks, steered | 29495 | 2.935 | 2.446 | 3.036 |
| read picks, rel_off | 3630 | 3.109 | 2.166 | 2.549 |
| c120 | 95786 | 3.054 | 2.822 | 2.466 |
| n600 | 7357 | 3.360 | 3.025 | 2.672 |
| place DET, all | 21960 | 3.178 | 2.996 | 2.743 |
| place DET, read picks | 5586 | 2.851 | 2.728 | 3.334 |
| place RULE, all | 72171 | 3.016 | 2.851 | 2.448 |
| place RULE, read picks | 23909 | 2.943 | 2.420 | 3.007 |
| place key, all | 2047 | 3.803 | 3.036 | 2.559 |
| place key, read picks | 655 | 3.164 | 1.721 | 2.109 |
| place port, all | 6965 | 3.090 | 2.657 | 2.464 |
| place port, read picks | 2975 | 3.097 | 2.264 | 2.646 |

Lambda grid: {"1.0": {"lam": 1.9440000017000003, "bits": 2.0144103904053856, "top1": 0.6814285397504655}}. Gate C grid: {"0.1": 2.4789419279856357, "1.0": 2.478724021659878, "10.0": 2.4788038715640774}.

Training counts: {"tasks": 1039, "pairs": 7829, "forms": 1626, "rows": 103143, "read-pick rows": 33125, "read rows, kind RULE": 23909, "read rows, kind INIT": 3630, "read rows, kind DET": 5586, "tasks_total": 989, "rows_by_source": {"c120": 95786, "n600": 7357}, "forms_by_source": {"c120": 1526, "n600": 100}, "read_rows_by_place_and_steer": {"RULE/steered": 23909, "port/rel_off": 2975, "DET/steered": 5586, "key/rel_off": 655}, "derived_options_per_read_row_median": 7.0, "read_rows_share_rel_off": 0.10958490566037736, "pair_kind_read_rows": {"read rows, kind RULE": 23909, "read rows, kind INIT": 3630, "read rows, kind DET": 5586}, "options": 851624, "features": 74, "weight_total": 4497.0000038, "weight_read": 1944.0000017000002}

Largest coefficients: [["share", 2.118], ["tinf", 1.609], ["blank", 1.071], ["ar1", -0.855], ["tin", -0.793], ["ct:Dir8", -0.566], ["ct:Nat", -0.552], ["ar4", 0.53], ["dr_type", -0.509], ["lnrel", -0.491], ["sub", -0.491], ["x_RULE_sub", -0.477], ["lmean", -0.474], ["x_r2_leaf", -0.367], ["ct:Sym", -0.326]]


## Training cross-fit by pick type and by steered / rel_off (X/cal)

```
== cache
check rel_off picks: options with rf != 1 at rel_off rows: 0 of 70966; max |ZB - TB| at rel_off rows 0.00e+00; rows 9012
cross-fit bits (weighted means) | rows | today | M1 | M1 steered only | M2 | M2 steered only
all picks      all      | 103143 | 3.073 | 2.789 | 2.908 | 2.437 | 2.606
all picks      steered  |  94131 | 3.033 | 2.822 | 2.822 | 2.436 | 2.436
all picks      rel_off  |   9012 | 3.216 | 2.669 | 3.216 | 2.440 | 3.216
read picks     all      |  33125 | 2.981 | 2.266 | 2.542 | 2.805 | 2.977
read picks     steered  |  29495 | 2.935 | 2.339 | 2.339 | 2.930 | 2.930
read picks     rel_off  |   3630 | 3.109 | 2.062 | 3.109 | 2.455 | 3.109
builtin picks  all      |  56654 | 3.366 | 3.478 | 3.478 | 2.347 | 2.514
builtin picks  steered  |  52658 | 3.446 | 3.583 | 3.583 | 2.403 | 2.403
builtin picks  rel_off  |   3996 | 3.011 | 3.011 | 3.011 | 2.096 | 3.011
op picks       all      |  13364 | 2.546 | 2.408 | 2.408 | 1.648 | 1.814
op picks       steered  |  11978 | 2.174 | 2.005 | 2.005 | 1.275 | 1.275
op picks       rel_off  |   1386 | 4.179 | 4.179 | 4.179 | 3.288 | 4.179
saved vs today (today - arm), all picks: M1 0.284, M1 steered only 0.165, M2 0.636, M2 steered only 0.467
read rows: gate cost -log2(sigma) mean 0.892; M1 within-D bits 1.913
== cache-norec
check rel_off picks: options with rf != 1 at rel_off rows: 0 of 70966; max |ZB - TB| at rel_off rows 0.00e+00; rows 9012
cross-fit bits (weighted means) | rows | today | M1 | M1 steered only | M2 | M2 steered only
all picks      all      | 103143 | 3.073 | 2.835 | 2.942 | 2.479 | 2.639
all picks      steered  |  94131 | 3.033 | 2.866 | 2.866 | 2.478 | 2.478
all picks      rel_off  |   9012 | 3.216 | 2.724 | 3.216 | 2.480 | 3.216
read picks     all      |  33125 | 2.981 | 2.373 | 2.621 | 2.908 | 3.055
read picks     steered  |  29495 | 2.935 | 2.446 | 2.446 | 3.036 | 3.036
read picks     rel_off  |   3630 | 3.109 | 2.166 | 3.109 | 2.549 | 3.109
builtin picks  all      |  56654 | 3.366 | 3.478 | 3.478 | 2.342 | 2.512
builtin picks  steered  |  52658 | 3.446 | 3.583 | 3.583 | 2.400 | 2.400
builtin picks  rel_off  |   3996 | 3.011 | 3.011 | 3.011 | 2.082 | 3.011
op picks       all      |  13364 | 2.546 | 2.408 | 2.408 | 1.646 | 1.817
op picks       steered  |  11978 | 2.174 | 2.005 | 2.005 | 1.279 | 1.279
op picks       rel_off  |   1386 | 4.179 | 4.179 | 4.179 | 3.256 | 4.179
saved vs today (today - arm), all picks: M1 0.238, M1 steered only 0.131, M2 0.594, M2 steered only 0.434
read rows: gate cost -log2(sigma) mean 0.888; M1 within-D bits 2.019
```

