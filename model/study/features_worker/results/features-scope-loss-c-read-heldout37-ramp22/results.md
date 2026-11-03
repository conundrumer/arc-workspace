# Scope loss, class C: results

53 forms counted (40 measured, 5 with a read relation absent from the scope, 8 not measured); median gap 4.05 bits over the dag bits; it sits in relation pick: read (2.4 bits a form, 51%), relation pick: builtin (1.9 bits a form, 40%), op pick (0.4 bits a form, 9%): T3 0.99 [0.87, 1.00] of the gap.

## Table 1: forms

By source and arm

| source | arm | forms |
|---|---|---|
| C | bundle_s0 | 8 |
| C | bundle_s1 | 9 |
| both | bundle_s0 | 17 |
| both | bundle_s1 | 18 |
| frontier | bundle_s0 | 1 |

By status

| status | forms |
|---|---|
| mapped | 42 |
| no replayable scope | 2 |
| read relation not in the scope | 5 |
| replay error | 2 |
| unmapped | 2 |

## Table 2: per form

| arm | task | g | kind | source | scope_n | slot_tries | S | R | DB | S - R | S - DB | largest place | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| bundle_s0 | 142ca369 | 3 | RULE | both | 6 | 381 | 6.94 | 1.95 | 1.39 (one) | 4.99 | 5.55 | relation pick: builtin | mapped |
| bundle_s0 | 142ca369 | 9 | RULE | both | 6 | 381 | 20.05 | 15.01 | 13.14 (one) | 5.04 | 6.91 | relation pick: builtin | mapped |
| bundle_s1 | 142ca369 | 2 | RULE | C | 10 | 25 | NA | NA | 19.13 (exact) | NA | NA |  | read relation not in the scope |
| bundle_s1 | 142ca369 | 3 | RULE | both | 6 | 315 | 7.41 | 1.95 | 1.39 (one) | 5.46 | 6.02 | relation pick: builtin | mapped |
| bundle_s0 | 16b78196 | 1 | INIT | both | 6 | 74 | 16.39 | 13.47 | 13.01 (one) | 2.92 | 3.38 | relation pick: read | mapped |
| bundle_s0 | 58490d8a | 2 | RULE | both | 9 | 35 | 16.93 | 11.38 | 11.32 (exact) | 5.55 | 5.61 | relation pick: read | mapped |
| bundle_s1 | 58490d8a | 2 | RULE | both | 10 | 20 | 15.29 | 11.38 | 11.32 (exact) | 3.91 | 3.97 | relation pick: builtin | mapped |
| bundle_s0 | 5961cc34 | 2 | INIT | both | 8 | 114 | 37.56 | 32.01 | 28.82 (one) | 5.55 | 8.74 | relation pick: read | mapped |
| bundle_s0 | 5961cc34 | 13 | RULE | C | 13 | 41 | 21.65 | 14.70 | 16.38 (exact) | 6.95 | 5.27 | relation pick: read | mapped |
| bundle_s0 | 5961cc34 | 20 | INIT | frontier | 13 | 41 | 9.72 | 6.77 | 6.69 (one) | 2.95 | 3.03 | relation pick: read | mapped |
| bundle_s1 | 5961cc34 | 2 | INIT | both | 6 | 238 | 39.76 | 32.01 | 28.82 (one) | 7.75 | 10.94 | relation pick: read | mapped |
| bundle_s1 | a25697e4 | 2 | INIT | both | 8 | 13 | NA | NA | 16.70 (one) | NA | NA |  | unmapped |
| bundle_s0 | a6f40cea | 1 | INIT | both | 7 | 372 | 15.94 | 12.21 | 12.27 (one) | 3.73 | 3.67 | relation pick: read | mapped |
| bundle_s0 | a6f40cea | 30 | RULE | C | 6 | 111 | NA | NA | NA (text differs) | NA | NA |  | unmapped |
| bundle_s1 | a6f40cea | 30 | RULE | C | 6 | 220 | 20.69 | 18.99 | NA (text differs) | 1.70 | NA |  | mapped |
| bundle_s0 | aa4ec2a5 | 12 | RULE | C | 7 | 12 | 9.99 | 10.52 | 11.67 (one) | -0.53 | -1.68 | relation pick: builtin | mapped |
| bundle_s1 | aa4ec2a5 | 7 | RULE | C | 7 | 8 | 18.12 | 15.84 | 17.16 (exact) | 2.28 | 0.96 | relation pick: builtin | mapped |
| bundle_s1 | aa4ec2a5 | 12 | RULE | C | 11 | 20 | 11.55 | 10.52 | 11.67 (one) | 1.03 | -0.12 | relation pick: read | mapped |
| bundle_s1 | abc82100 | 12 | RULE | C | 7 | 354 | 13.14 | 5.50 | 10.54 (exact) | 7.64 | 2.60 | relation pick: read | mapped |
| bundle_s0 | b5ca7ac4 | 22 | INIT | both | 9 | 174 | NA | NA | 9.29 (one) | NA | NA |  | read relation not in the scope |
| bundle_s1 | b5ca7ac4 | 22 | INIT | both | 8 | 8 | NA | NA | 9.29 (one) | NA | NA |  | read relation not in the scope |
| bundle_s0 | b6f77b65 | 3 | RULE | both | 6 | 505 | 14.76 | 11.29 | 12.05 (exact) | 3.47 | 2.71 | relation pick: builtin | mapped |
| bundle_s0 | b6f77b65 | 6 | RULE | both | 6 | 398 | 17.51 | 14.44 | 13.66 (exact) | 3.07 | 3.85 | relation pick: builtin | mapped |
| bundle_s0 | b6f77b65 | 21 | RULE | both | 6 | 398 | 19.53 | 16.43 | 17.05 (exact) | 3.10 | 2.48 | relation pick: builtin | mapped |
| bundle_s1 | b6f77b65 | 2 | RULE | both | 8 | 145 | 21.65 | 14.55 | 12.72 (exact) | 7.10 | 8.93 | relation pick: builtin | mapped |
| bundle_s1 | b6f77b65 | 3 | RULE | both | 8 | 145 | 17.97 | 11.29 | 12.05 (exact) | 6.68 | 5.91 | relation pick: builtin | mapped |
| bundle_s1 | b6f77b65 | 6 | RULE | both | 8 | 145 | 20.64 | 14.44 | 13.66 (exact) | 6.20 | 6.98 | relation pick: builtin | mapped |
| bundle_s1 | b6f77b65 | 21 | RULE | both | 8 | 145 | 23.69 | 16.43 | 17.05 (exact) | 7.26 | 6.64 | relation pick: builtin | mapped |
| bundle_s1 | c4d067a0 | 2 | INIT | C | None | None | NA | NA | NA | NA | NA |  | no replayable scope |
| bundle_s0 | c7f57c3e | 19 | DET | both | 10 | 51 | 11.97 | 8.41 | 8.50 (exact) | 3.56 | 3.47 | relation pick: read | mapped |
| bundle_s1 | c7f57c3e | 19 | DET | both | 10 | 62 | 12.08 | 8.41 | 8.50 (exact) | 3.67 | 3.58 | relation pick: read | mapped |
| bundle_s1 | cb2d8a2c | 3 | RULE | C | None | None | NA | NA | NA | NA | NA |  | no replayable scope |
| bundle_s0 | cbebaa4b | 3 | INIT | both | 6 | 121 | 29.96 | 31.71 | 31.46 (exact) | -1.75 | -1.50 | stop | mapped |
| bundle_s1 | cbebaa4b | 3 | INIT | both | 8 | 52 | 29.59 | 31.71 | 31.46 (exact) | -2.12 | -1.87 | priors and code | mapped |
| bundle_s0 | d59b0160 | 3 | RULE | both | 10 | 120 | 15.45 | 13.72 | 16.18 (exact) | 1.73 | -0.73 | relation pick: read | mapped |
| bundle_s1 | d59b0160 | 3 | RULE | C | 6 | 30 | 14.41 | 13.72 | 16.18 (exact) | 0.69 | -1.77 | relation pick: read | mapped |
| bundle_s0 | db0c5428 | 6 | DET | C | 14 | 24 | 21.90 | 16.41 | 17.00 (exact) | 5.49 | 4.90 | relation pick: read | mapped |
| bundle_s1 | db0c5428 | 1 | INIT | both | 6 | 22 | 18.56 | 14.45 | 14.43 (one) | 4.11 | 4.13 | relation pick: read | mapped |
| bundle_s0 | db695cfb | 2 | DET | both | 9 | 58 | 19.85 | 12.91 | 10.70 (exact) | 6.94 | 9.15 | relation pick: builtin | mapped |
| bundle_s0 | db695cfb | 6 | INIT | C | 11 | 36 | 46.55 | 42.69 | 40.33 (one) | 3.86 | 6.22 | relation pick: builtin | mapped |
| bundle_s1 | db695cfb | 2 | DET | both | 6 | 80 | 19.76 | 12.91 | 10.70 (exact) | 6.85 | 9.06 | relation pick: builtin | mapped |
| bundle_s1 | db695cfb | 6 | INIT | both | 8 | 120 | 45.67 | 42.69 | 40.33 (one) | 2.98 | 5.34 | priors and code | mapped |
| bundle_s0 | dbff022c | 18 | RULE | C | 13 | 22 | NA | NA | 11.56 (exact) | NA | NA |  | read relation not in the scope |
| bundle_s1 | dbff022c | 2 | INIT | C | 11 | 19 | 10.25 | 6.77 | 6.69 (one) | 3.48 | 3.56 | relation pick: read | mapped |
| bundle_s1 | dbff022c | 18 | RULE | both | 8 | 52 | NA | NA | 11.56 (exact) | NA | NA |  | read relation not in the scope |
| bundle_s0 | dd6b8c4b | 14 | RULE | both | 6 | 432 | 31.12 | 19.67 | 18.86 (bound) | 11.45 | 12.26 | relation pick: builtin | mapped |
| bundle_s1 | dd6b8c4b | 14 | RULE | both | 10 | 176 | 29.56 | 19.67 | 18.86 (bound) | 9.89 | 10.70 | relation pick: read | mapped |
| bundle_s0 | de809cff | 24 | DET | both | 9 | 57 | NA | NA | 7.58 (one) | NA | NA |  | replay error |
| bundle_s1 | de809cff | 24 | DET | both | 8 | 46 | NA | NA | 7.58 (one) | NA | NA |  | replay error |
| bundle_s0 | f560132c | 10 | RULE | C | 7 | 21 | 89.27 | 85.65 | NA (no record (memory)) | 3.62 | NA |  | mapped |
| bundle_s0 | f931b4a8 | 1 | INIT | both | 12 | 150 | 19.81 | 14.83 | 15.67 (exact) | 4.98 | 4.14 | relation pick: read | mapped |
| bundle_s0 | f931b4a8 | 27 | RULE | C | 8 | 21 | 8.80 | 5.30 | 9.56 (one) | 3.50 | -0.76 | relation pick: read | mapped |
| bundle_s1 | f931b4a8 | 1 | INIT | both | 6 | 557 | 18.18 | 14.83 | 15.67 (exact) | 3.35 | 2.51 | relation pick: read | mapped |

## Table 3: places (S - DB), measured forms

| place | sum of gaps (bits) | share [2.5%, 97.5%] | median gap a form | forms where largest |
|---|---|---|---|---|
| relation pick: read | 95.1 | 0.51 [0.36, 0.68] | 2.07 | 20 |
| relation pick: builtin | 75.2 | 0.40 [0.26, 0.49] | 1.74 | 17 |
| op pick | 16.0 | 0.09 [0.02, 0.13] | 0.00 | 0 |
| argument fill: read | -1.4 | 0.00 [0.00, 0.00] | 0.00 | 0 |
| argument fill: other | -2.7 | 0.00 [0.00, 0.00] | 0.00 | 0 |
| join coin | -8.2 | 0.00 [0.00, 0.00] | -0.19 | 0 |
| stop | 1.5 | 0.01 [0.00, 0.03] | 0.00 | 1 |
| proposer | 0.0 | 0.00 [0.00, 0.00] | 0.00 | 0 |
| OR and ALL | 0.0 | 0.00 [0.00, 0.00] | 0.00 | 0 |
| INIT structure | 0.0 | 0.00 [0.00, 0.00] | 0.00 | 0 |
| order sum | -0.6 | 0.00 [0.00, 0.01] | 0.00 | 0 |
| other | 0.0 | 0.00 [0.00, 0.00] | 0.00 | 0 |
| priors and code | -0.0 | 0.00 [0.00, 0.12] | 0.06 | 2 |

Top 3: relation pick: read, relation pick: builtin, op pick. T3 = 0.99 [0.87, 1.00] (40 forms, 16 tasks); bar 0.60 on the 2.5% point. Median gap 4.05 bits.

Verdict: **a few named places**

## Table 4: S - R, the scope places, forms with no DB included

| place | sum of gaps (bits) | share [2.5%, 97.5%] | median gap a form | forms where largest |
|---|---|---|---|---|
| relation pick: read | 99.7 | 0.50 [0.39, 0.64] | 2.07 | 20 |
| relation pick: builtin | 78.9 | 0.40 [0.25, 0.50] | 1.74 | 19 |
| op pick | 18.2 | 0.09 [0.03, 0.14] | 0.00 | 0 |
| argument fill: read | -1.1 | 0.00 [0.00, 0.01] | 0.00 | 0 |
| argument fill: other | 2.3 | 0.01 [0.00, 0.08] | 0.00 | 1 |
| join coin | -8.2 | 0.00 [0.00, 0.01] | -0.19 | 0 |
| stop | -1.5 | 0.00 [0.00, 0.03] | 0.00 | 2 |
| proposer | 0.0 | 0.00 [0.00, 0.00] | 0.00 | 0 |
| OR and ALL | 0.0 | 0.00 [0.00, 0.00] | 0.00 | 0 |
| INIT structure | 0.0 | 0.00 [0.00, 0.00] | 0.00 | 0 |
| order sum | -7.9 | 0.00 [0.00, 0.01] | 0.00 | 0 |
| other | -0.2 | 0.00 [0.00, 0.00] | 0.00 | 0 |

Top 3: relation pick: read, relation pick: builtin, op pick. T3 = 0.99 [0.90, 1.00] (42 forms, 17 tasks).

## Table 5: forms whose read relation is not in the scope

| arm | task | g | gold reads | relations of that gold form that the scope holds |
|---|---|---|---|---|
| bundle_s1 | 142ca369 | 2 | &r1.exposed | none |
| bundle_s0 | b5ca7ac4 | 22 | &r33.maximal | none |
| bundle_s1 | b5ca7ac4 | 22 | &r33.maximal | none |
| bundle_s0 | dbff022c | 18 | &r33.enclosed | none |
| bundle_s1 | dbff022c | 18 | &r33.enclosed | none |

## Checks

- 1 table check: `{"fails": [], "mapped": 42, "mapped_not_passing": []}`
- 2 walks: `{"invalid": []}`
- 3 kind: `{"not_gold_kind": [], "k_forms": ["bundle_s0 5961cc34 g20 visit RULE gold INIT"]}`
- 4 sums: `{"beyond_005": [], "other_parts": {"top atom: op": 54.555}, "other_count": 1, "other_bits": 54.555}`
- 5 read/other split: `{"phases_without_atom_row": 1}`
- 6 R against DB (not a gate): `{"exact": {"n": 23, "median": -0.5850000000000009, "iqr": [-0.8439999999999994, 0.25200000000000244], "max_abs": 5.045, "beyond_3": ["bundle_s1 abc82100 g12 -5.04"]}, "one": {"n": 15, "median": 0.46000000000000085, "iqr": [-0.019999999999999574, 2.1149999999999993], "max_abs": 4.260000000000001, "beyond_3": ["bundle_s0 5961cc34 g2 3.19", "bundle_s1 5961cc34 g2 3.19", "bundle_s0 f931b4a8 g27 -4.26"]}, "bound": {"n": 2, "median": 0.8140000000000001, "iqr": [0.8140000000000001, 0.8140000000000001], "max_abs": 0.8140000000000001, "beyond_3": []}}`
- 7 order free: `{"n": 0, "failed": [], "items": []}`
- 8 determinism: `{"n": 0, "failed": [], "items": []}`
- 9 exact or estimate: `{"estimates": ["bundle_s0 f560132c g10 S", "bundle_s0 f560132c g10 R"]}`

## Forms not measured, other reasons

| arm | task | g | status | how |
|---|---|---|---|---|
| bundle_s1 | a25697e4 | 2 | unmapped | &r3.maximal: ports not mapped ['Key'] [''] |
| bundle_s0 | a6f40cea | 30 | unmapped | &r63: INIT relation &f9.0 with no known sub-name |
| bundle_s1 | c4d067a0 | 2 | no replayable scope |  |
| bundle_s1 | cb2d8a2c | 3 | no replayable scope |  |
| bundle_s0 | de809cff | 24 | replay error | &r33.minimal -> &f48 renamed {'N': 'K'} |
| bundle_s1 | de809cff | 24 | replay error | &r33.minimal -> &f1753 renamed {'N': 'K'} |
