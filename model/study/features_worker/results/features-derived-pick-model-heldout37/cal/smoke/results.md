# Derived pick model: results

M1 saves -2.36 on covered [-8.12, 2.02] a form; M2 saves -1.78 on covered [-5.98, 1.69] a form; M2s saves -2.39 on covered [-5.98, 0.00] a form; M1 covered closes -0.80 [-2.83, 0.52] of the S - DB gap (median gap 2.86 to 2.35); M2 covered closes -0.60 [-2.08, 0.39] of the S - DB gap (median gap 2.86 to 2.68); M2s covered closes -0.81 [-2.08, 0.00] of the S - DB gap (median gap 2.86 to 4.37); against the 0.78 line: M1 covered: within, M2 covered: within, M2s covered: below.

## Saved bits a form (S_off - S_arm), mean and median with a 95% task bootstrap

| set | arm | forms (tasks) | total mean | total median | read picks mean | builtin picks mean | op picks mean | rel_off picks: sum (forms) | mean - 0.78 |
|---|---|---|---|---|---|---|---|---|---|
| covered | M1 | 5 (3) | -2.36 [-8.12, 2.02] | 1.08 [-8.12, 2.02] | -1.93 [-7.07, 2.03] | -0.23 [-0.64, 0.07] | -0.13 [-0.33, 0.00] | 4.6 (3) | -3.14 [-8.90, 1.24] |
| covered | M2 | 5 (3) | -1.78 [-5.98, 1.69] | 0.66 [-5.98, 1.69] | -2.12 [-7.07, 2.07] | 0.44 [0.21, 0.79] | 0.05 [-0.34, 0.30] | 3.8 (3) | -2.56 [-6.76, 0.91] |
| covered | M2s | 5 (3) | -2.39 [-5.98, 0.00] | 0.00 [-5.98, 0.00] | -2.83 [-7.07, 0.00] | 0.32 [0.00, 0.79] | 0.12 [0.00, 0.30] | 0.0 (3) | -3.17 [-6.76, -0.78] |

## M2 against M2s: the saving that comes from acting at rel_off picks too (mean over forms of the saving of M2 minus that of M2s, 95% task bootstrap)

| set | forms | total | read picks | builtin picks | op picks |
|---|---|---|---|---|---|
| covered | 5 | 0.62 [0.00, 1.69] | 0.70 [0.00, 2.07] | 0.13 [0.00, 0.23] | -0.07 [-0.34, 0.00] |

## Against the S - DB gap (forms with DB)

| set | arm | forms | median S_off - DB | median S_arm - DB | sum delta / sum gap |
|---|---|---|---|---|---|
| covered | M1 | 5 | 2.86 | 2.35 | -0.80 [-2.83, 0.52] |
| covered | M2 | 5 | 2.86 | 2.68 | -0.60 [-2.08, 0.39] |
| covered | M2s | 5 | 2.86 | 4.37 | -0.81 [-2.08, 0.00] |

## Checks

- C: forms 0, ok 0, errors 0. (1) S_off differs from the recorded S on 0 forms. (2) Regroup arm G on 0 forms, differs from split-steer S_on on 0. (3) invalid walks: {'off': 0, 'M1': 0, 'M2': 0, 'M2s': 0}; estimates (orders.exact false): {'off': 0, 'M1': 0, 'M2': 0, 'M2s': 0}. (4) order check on 0 forms, differs on 0. Non-declared relation options at picks {'M1': 0, 'M2': 0, 'M2s': 0}, alt-only options {'M1': 0, 'M2': 0, 'M2s': 0}.
- covered: forms 5, ok 5, errors 0. (1) S_off differs from the recorded S on 0 forms. (2) Regroup arm G on 0 forms, differs from split-steer S_on on 0. (3) invalid walks: {'off': 0, 'M1': 0, 'M2': 0, 'M2s': 0}; estimates (orders.exact false): {'off': 0, 'M1': 0, 'M2': 0, 'M2s': 0}. (4) order check on 0 forms, differs on 0. Non-declared relation options at picks {'M1': 0, 'M2': 0, 'M2s': 0}, alt-only options {'M1': 0, 'M2': 0, 'M2s': 0}.
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

