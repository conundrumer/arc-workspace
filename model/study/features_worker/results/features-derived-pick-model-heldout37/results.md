# Derived pick model: results

M1 saves 0.34 on C [-0.89, 1.40] (read picks 0.21, builtin picks 0.10) and -0.09 on covered [-0.99, 0.67] a form; M2 saves 1.80 on C [0.03, 3.15] (read picks -0.07, builtin picks 1.58) and 0.56 on covered [-0.52, 1.39] a form; M1 C closes 0.12 [-0.21, 0.36] of the S - DB gap (median gap 4.05 to 4.06); M1 covered closes 0.02 [-0.30, 0.28] of the S - DB gap (median gap 2.61 to 1.76); M2 C closes 0.45 [0.07, 0.79] of the S - DB gap (median gap 4.05 to 2.29); M2 covered closes 0.23 [-0.10, 0.48] of the S - DB gap (median gap 2.61 to 2.32); against the 0.78 line: M1 C: within, M2 C: within, M1 covered: below, M2 covered: within.

## Saved bits a form (S_off - S_arm), mean and median with a 95% task bootstrap

| set | arm | forms (tasks) | total mean | total median | read picks mean | builtin picks mean | op picks mean | rel_off picks: sum (forms) | mean - 0.78 |
|---|---|---|---|---|---|---|---|---|---|
| C | M1 | 41 (16) | 0.34 [-0.89, 1.40] | 1.16 [-0.62, 2.18] | 0.21 [-0.87, 1.12] | 0.10 [-0.12, 0.33] | 0.08 [-0.03, 0.24] | 13.9 (13) | -0.44 [-1.67, 0.62] |
| C | M2 | 41 (16) | 1.80 [0.03, 3.15] | 2.48 [-0.52, 3.76] | -0.07 [-1.26, 0.94] | 1.58 [1.07, 1.95] | 0.51 [0.22, 0.82] | 39.8 (13) | 1.02 [-0.75, 2.37] |
| covered | M1 | 43 (19) | -0.09 [-0.99, 0.67] | 0.42 [-0.29, 1.05] | 0.20 [-0.61, 0.88] | -0.18 [-0.34, -0.02] | 0.03 [-0.03, 0.09] | 12.6 (15) | -0.87 [-1.77, -0.11] |
| covered | M2 | 43 (19) | 0.56 [-0.52, 1.39] | 1.12 [0.68, 1.43] | -0.39 [-1.34, 0.36] | 0.88 [0.56, 1.13] | 0.27 [0.07, 0.48] | 8.3 (15) | -0.22 [-1.30, 0.61] |

## Against the S - DB gap (forms with DB)

| set | arm | forms | median S_off - DB | median S_arm - DB | sum delta / sum gap |
|---|---|---|---|---|---|
| C | M1 | 40 | 4.05 | 4.06 | 0.12 [-0.21, 0.36] |
| C | M2 | 40 | 4.05 | 2.29 | 0.45 [0.07, 0.79] |
| covered | M1 | 37 | 2.61 | 1.76 | 0.02 [-0.30, 0.28] |
| covered | M2 | 37 | 2.61 | 2.32 | 0.23 [-0.10, 0.48] |

## Checks

- C: forms 41, ok 41, errors 0. (1) S_off differs from the recorded S on 0 forms. (2) Regroup arm G on 10 forms, differs from split-steer S_on on 0. (3) invalid walks: {'off': 0, 'M1': 0, 'M2': 0}; estimates (orders.exact false): {'off': 0, 'M1': 0, 'M2': 0}. (4) order check on 6 forms, differs on 0. Non-declared relation options at picks {'M1': 0, 'M2': 0}, alt-only options {'M1': 0, 'M2': 0}.
- covered: forms 43, ok 43, errors 0. (1) S_off differs from the recorded S on 0 forms. (2) Regroup arm G on 10 forms, differs from split-steer S_on on 0. (3) invalid walks: {'off': 0, 'M1': 0, 'M2': 0}; estimates (orders.exact false): {'off': 0, 'M1': 0, 'M2': 0}. (4) order check on 6 forms, differs on 0. Non-declared relation options at picks {'M1': 0, 'M2': 0}, alt-only options {'M1': 0, 'M2': 0}.
- facts, drawn atoms and row parity (checks.py): {"n600.0of1.jsonl": {"pairs": 20, "picks": 69, "sum_ok": 69, "sum_bad": [], "text_checked": 16, "text_ok": 16, "text_bad": [], "parity_pairs": 10, "parity_picks": 36, "parity_bad": [], "seconds": 1.5, "sum_all_ok": true}, "c120.1of4.jsonl": {"pairs": 20, "picks": 79, "sum_ok": 79, "sum_bad": [], "text_checked": 66, "text_ok": 66, "text_bad": [], "parity_pairs": 10, "parity_picks": 47, "parity_bad": [], "seconds": 3.6, "sum_all_ok": true}}

## Cross-fit on the training rows (pick level, in bits; weighted means)

Read-pick rows, within the derived options (positives' share): even split 3.063, today 2.644, rank model (logit) 1.909; a positive has the largest score: today 0.383, model 0.543. Ablation (boosted ranker): None. Rows 33125.

| rows | count | today | M1 | M2 |
|---|---|---|---|---|
| all rows | 103143 | 3.073 | 2.789 | 2.437 |
| read picks | 33125 | 2.981 | 2.266 | 2.805 |
| builtin picks | 56654 | 3.366 | 3.478 | 2.347 |
| op picks | 13364 | 2.546 | 2.408 | 1.648 |
| read picks, steered | 29495 | 2.935 | 2.339 | 2.930 |
| read picks, rel_off | 3630 | 3.109 | 2.062 | 2.455 |
| c120 | 95786 | 3.054 | 2.773 | 2.421 |
| n600 | 7357 | 3.360 | 3.018 | 2.666 |
| place DET, all | 21960 | 3.178 | 2.962 | 2.711 |
| place DET, read picks | 5586 | 2.851 | 2.630 | 3.236 |
| place RULE, all | 72171 | 3.016 | 2.806 | 2.404 |
| place RULE, read picks | 23909 | 2.943 | 2.312 | 2.901 |
| place key, all | 2047 | 3.803 | 2.926 | 2.472 |
| place key, read picks | 655 | 3.164 | 1.516 | 1.924 |
| place port, all | 6965 | 3.090 | 2.614 | 2.433 |
| place port, read picks | 2975 | 3.097 | 2.181 | 2.571 |

Lambda grid: {"0.01": {"lam": 0.019440000017, "bits": 1.9185729401731906, "top1": 0.5476033446342974}, "0.1": {"lam": 0.19440000017000003, "bits": 1.9112836341005528, "top1": 0.5465638342271132}, "1.0": {"lam": 1.9440000017000003, "bits": 1.909219018275936, "top1": 0.5427962338703256}, "10.0": {"lam": 19.440000017000003, "bits": 1.9450903390112444, "top1": 0.5355806556358947}}. Gate C grid: {"0.1": 2.4368471706698713, "1.0": 2.4366362485775777, "10.0": 2.4367195477199854}.

Training counts: {"tasks": 1039, "pairs": 7829, "forms": 1626, "rows": 103143, "read-pick rows": 33125, "read rows, kind RULE": 23909, "read rows, kind INIT": 3630, "read rows, kind DET": 5586, "tasks_total": 989, "rows_by_source": {"c120": 95786, "n600": 7357}, "forms_by_source": {"c120": 1526, "n600": 100}, "read_rows_by_place_and_steer": {"RULE/steered": 23909, "port/rel_off": 2975, "DET/steered": 5586, "key/rel_off": 655}, "derived_options_per_read_row_median": 7.0, "read_rows_share_rel_off": 0.10958490566037736, "pair_kind_read_rows": {"read rows, kind RULE": 23909, "read rows, kind INIT": 3630, "read rows, kind DET": 5586}, "options": 851624, "features": 76, "weight_total": 4497.0000038, "weight_read": 1944.0000017000002}

Largest coefficients: [["share", 2.092], ["tinf", 1.613], ["blank", 1.121], ["ar1", -0.87], ["tin", -0.768], ["lmean", -0.687], ["ct:Dir8", -0.612], ["ar4", 0.555], ["sub", -0.555], ["rec", 0.553], ["x_RULE_sub", -0.515], ["dr_type", -0.495], ["ct:Nat", -0.453], ["lnrel", -0.391], ["x_r2_leaf", -0.367]]

