# Scope loss, covered forms (control for class C): results

173 forms counted (37 measured, 62 with a read relation absent from the scope, 74 not measured); median gap 2.61 bits over the dag bits; it sits in relation pick: read (2.0 bits a form, 54%), relation pick: builtin (1.3 bits a form, 34%), op pick (0.4 bits a form, 10%): T3 0.99 [0.93, 0.99] of the gap.

## Table 1: forms

By source and arm

| source | arm | forms |
|---|---|---|
| covered | bundle_s0 | 87 |
| covered | bundle_s1 | 86 |

By status

| status | forms |
|---|---|
| covering visit of another kind | 44 |
| error | 2 |
| mapped | 43 |
| no covering opening | 10 |
| read relation not in the scope | 62 |
| replay error | 1 |
| unmapped | 11 |

## Table 2: per form

| arm | task | g | kind | source | scope_n | slot_tries | S | R | DB | S - R | S - DB | largest place | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| bundle_s0 | 135a2760 | 9 | INIT | covered | None | None | NA | NA | NA | NA | NA |  | covering visit of another kind |
| bundle_s1 | 135a2760 | 9 | INIT | covered | None | None | NA | NA | NA | NA | NA |  | covering visit of another kind |
| bundle_s0 | 142ca369 | 1 | INIT | covered | None | None | NA | NA | NA | NA | NA |  | covering visit of another kind |
| bundle_s1 | 142ca369 | 1 | INIT | covered | None | None | NA | NA | NA | NA | NA |  | covering visit of another kind |
| bundle_s1 | 142ca369 | 9 | RULE | covered | None | None | NA | NA | NA | NA | NA |  | covering visit of another kind |
| bundle_s1 | 16b78196 | 1 | INIT | covered | 11 | 84 | 17.38 | 13.47 | 13.01 (one) | 3.91 | 4.37 | relation pick: read | mapped |
| bundle_s0 | 581f7754 | 1 | INIT | covered | None | None | NA | NA | NA | NA | NA |  | covering visit of another kind |
| bundle_s0 | 581f7754 | 2 | RULE | covered | 6 | 32 | NA | NA | 3.05 (one) | NA | NA |  | unmapped |
| bundle_s0 | 581f7754 | 3 | INIT | covered | 6 | 173 | NA | NA | 8.35 (one) | NA | NA |  | read relation not in the scope |
| bundle_s1 | 581f7754 | 1 | INIT | covered | None | None | NA | NA | NA | NA | NA |  | covering visit of another kind |
| bundle_s1 | 581f7754 | 2 | RULE | covered | 6 | 57 | NA | NA | 3.05 (one) | NA | NA |  | unmapped |
| bundle_s0 | 58490d8a | 1 | INIT | covered | 6 | 52 | 9.11 | 6.16 | 6.79 (exact) | 2.95 | 2.32 | relation pick: read | mapped |
| bundle_s1 | 58490d8a | 1 | INIT | covered | 7 | 61 | 9.06 | 6.16 | 6.79 (exact) | 2.90 | 2.28 | relation pick: read | mapped |
| bundle_s0 | 5961cc34 | 1 | RULE | covered | 6 | 88 | 6.21 | 1.95 | 1.39 (one) | 4.26 | 4.82 | relation pick: read | mapped |
| bundle_s0 | 5961cc34 | 12 | RULE | covered | 6 | 54 | NA | NA | 19.72 (exact) | NA | NA |  | read relation not in the scope |
| bundle_s1 | 5961cc34 | 1 | RULE | covered | 6 | 31 | 7.04 | 1.95 | 1.39 (one) | 5.09 | 5.65 | relation pick: read | mapped |
| bundle_s1 | 5961cc34 | 12 | RULE | covered | 6 | 153 | NA | NA | 19.72 (exact) | NA | NA |  | read relation not in the scope |
| bundle_s0 | 6e453dd6 | 1 | RULE | covered | 6 | 214 | 4.96 | 2.29 | 3.01 (exact) | 2.67 | 1.95 | relation pick: builtin | mapped |
| bundle_s0 | 6e453dd6 | 3 | RULE | covered | 6 | 217 | 5.75 | 4.20 | 5.97 (exact) | 1.55 | -0.22 | relation pick: read | mapped |
| bundle_s0 | 6e453dd6 | 14 | INIT | covered | 6 | 58 | 9.30 | 6.40 | 6.79 (exact) | 2.90 | 2.51 | relation pick: read | mapped |
| bundle_s0 | 6e453dd6 | 15 | RULE | covered | None | None | NA | NA | NA | NA | NA |  | covering visit of another kind |
| bundle_s0 | 6e453dd6 | 39 | RULE | covered | 6 | 214 | NA | NA | 14.64 (exact) | NA | NA |  | read relation not in the scope |
| bundle_s0 | 6e453dd6 | 50 | INIT | covered | 11 | 20 | NA | NA | 11.48 (exact) | NA | NA |  | read relation not in the scope |
| bundle_s1 | 6e453dd6 | 1 | RULE | covered | None | None | NA | NA | NA | NA | NA |  | covering visit of another kind |
| bundle_s1 | 6e453dd6 | 3 | RULE | covered | 6 | 34 | 6.53 | 4.20 | 5.97 (exact) | 2.33 | 0.56 | relation pick: read | mapped |
| bundle_s1 | 6e453dd6 | 14 | INIT | covered | 6 | 129 | 9.40 | 6.40 | 6.79 (exact) | 3.00 | 2.61 | relation pick: read | mapped |
| bundle_s1 | 6e453dd6 | 15 | RULE | covered | 6 | 34 | NA | NA | 16.49 (exact) | NA | NA |  | read relation not in the scope |
| bundle_s1 | 6e453dd6 | 39 | RULE | covered | 6 | 95 | NA | NA | 14.64 (exact) | NA | NA |  | read relation not in the scope |
| bundle_s1 | 6e453dd6 | 50 | INIT | covered | 8 | 29 | 15.88 | 10.80 | 11.48 (exact) | 5.08 | 4.40 | relation pick: read | mapped |
| bundle_s0 | 80a900e0 | 11 | INIT | covered | None | None | NA | NA | NA | NA | NA |  | covering visit of another kind |
| bundle_s0 | 88bcf3b4 | 1 | INIT | covered | None | None | NA | NA | NA | NA | NA |  | covering visit of another kind |
| bundle_s0 | 88bcf3b4 | 2 | RULE | covered | 7 | 257 | 5.93 | 4.46 | 3.05 (one) | 1.47 | 2.88 | priors and code | mapped |
| bundle_s1 | 88bcf3b4 | 1 | INIT | covered | 6 | 262 | 13.74 | 9.11 | 9.46 (one) | 4.63 | 4.28 | relation pick: read | mapped |
| bundle_s1 | 88bcf3b4 | 2 | RULE | covered | 7 | 90 | 5.91 | 4.46 | 3.05 (one) | 1.45 | 2.86 | priors and code | mapped |
| bundle_s0 | 8e5c0c38 | 2 | INIT | covered | None | None | NA | NA | NA | NA | NA |  | covering visit of another kind |
| bundle_s0 | 8e5c0c38 | 3 | RULE | covered | 10 | 131 | NA | NA | 3.05 (one) | NA | NA |  | unmapped |
| bundle_s0 | 8e5c0c38 | 18 | RULE | covered | None | None | NA | NA | NA | NA | NA |  | no covering opening |
| bundle_s1 | 8e5c0c38 | 2 | INIT | covered | None | None | NA | NA | NA | NA | NA |  | covering visit of another kind |
| bundle_s1 | 8e5c0c38 | 3 | RULE | covered | 7 | 77 | NA | NA | 3.05 (one) | NA | NA |  | unmapped |
| bundle_s1 | 8e5c0c38 | 18 | RULE | covered | None | None | NA | NA | NA | NA | NA |  | no covering opening |
| bundle_s0 | a25697e4 | 1 | INIT | covered | None | None | NA | NA | NA | NA | NA |  | covering visit of another kind |
| bundle_s0 | a25697e4 | 2 | INIT | covered | 10 | 119 | NA | NA | 16.70 (one) | NA | NA |  | unmapped |
| bundle_s1 | a25697e4 | 1 | INIT | covered | None | None | NA | NA | NA | NA | NA |  | covering visit of another kind |
| bundle_s0 | a6f40cea | 5 | INIT | covered | None | None | NA | NA | NA | NA | NA |  | no covering opening |
| bundle_s0 | a6f40cea | 6 | INIT | covered | 6 | 46 | NA | NA | 31.91 (exact) | NA | NA |  | read relation not in the scope |
| bundle_s0 | a6f40cea | 12 | INIT | covered | None | None | NA | NA | NA | NA | NA |  | covering visit of another kind |
| bundle_s1 | a6f40cea | 1 | INIT | covered | 9 | 63 | 15.51 | 12.21 | 12.27 (one) | 3.30 | 3.24 | relation pick: read | mapped |
| bundle_s1 | a6f40cea | 5 | INIT | covered | 11 | 33 | NA | NA | 9.16 (one) | NA | NA |  | read relation not in the scope |
| bundle_s1 | a6f40cea | 6 | INIT | covered | 7 | 268 | NA | NA | 31.91 (exact) | NA | NA |  | read relation not in the scope |
| bundle_s1 | a6f40cea | 12 | INIT | covered | None | None | NA | NA | NA | NA | NA |  | covering visit of another kind |
| bundle_s0 | aa4ec2a5 | 2 | RULE | covered | 6 | 180 | 7.39 | 1.95 | 1.39 (one) | 5.44 | 6.00 | relation pick: builtin | mapped |
| bundle_s0 | aa4ec2a5 | 5 | RULE | covered | 6 | 180 | NA | NA | 3.01 (exact) | NA | NA |  | read relation not in the scope |
| bundle_s0 | aa4ec2a5 | 6 | INIT | covered | 8 | 110 | NA | NA | 6.69 (one) | NA | NA |  | read relation not in the scope |
| bundle_s0 | aa4ec2a5 | 11 | INIT | covered | None | None | NA | NA | NA | NA | NA |  | covering visit of another kind |
| bundle_s1 | aa4ec2a5 | 2 | RULE | covered | 6 | 78 | NA | NA | 1.39 (one) | NA | NA |  | read relation not in the scope |
| bundle_s1 | aa4ec2a5 | 5 | RULE | covered | 6 | 78 | 5.17 | 2.29 | 3.01 (exact) | 2.88 | 2.16 | relation pick: builtin | mapped |
| bundle_s1 | aa4ec2a5 | 6 | INIT | covered | 6 | 79 | NA | NA | 6.69 (one) | NA | NA |  | read relation not in the scope |
| bundle_s1 | aa4ec2a5 | 11 | INIT | covered | 6 | 79 | 11.92 | 9.52 | 9.91 (exact) | 2.40 | 2.01 | relation pick: read | mapped |
| bundle_s0 | abc82100 | 2 | RULE | covered | 6 | 168 | 10.02 | 4.80 | 4.40 (exact) | 5.22 | 5.62 | op pick | mapped |
| bundle_s0 | abc82100 | 11 | INIT | covered | 6 | 82 | NA | NA | 12.23 (exact) | NA | NA |  | read relation not in the scope |
| bundle_s0 | abc82100 | 12 | RULE | covered | 6 | 168 | 8.89 | 5.50 | 10.54 (exact) | 3.39 | -1.65 | relation pick: read | mapped |
| bundle_s1 | abc82100 | 2 | RULE | covered | 7 | 354 | 10.57 | 4.80 | 4.40 (exact) | 5.77 | 6.17 | relation pick: read | mapped |
| bundle_s1 | abc82100 | 11 | INIT | covered | 6 | 58 | NA | NA | 12.23 (exact) | NA | NA |  | read relation not in the scope |
| bundle_s0 | b10624e5 | 3 | RULE | covered | 6 | 100 | 9.27 | 9.00 | NA (status written) | 0.27 | NA |  | mapped |
| bundle_s0 | b10624e5 | 19 | INIT | covered | 9 | 63 | NA | NA | NA (status written) | NA | NA |  | read relation not in the scope |
| bundle_s1 | b10624e5 | 3 | RULE | covered | 6 | 39 | NA | NA | NA (status written) | NA | NA |  | read relation not in the scope |
| bundle_s1 | b10624e5 | 10 | INIT | covered | 6 | 12 | NA | NA | NA (status written) | NA | NA |  | read relation not in the scope |
| bundle_s0 | b5ca7ac4 | 6 | INIT | covered | 9 | 56 | NA | NA | 32.98 (exact) | NA | NA |  | read relation not in the scope |
| bundle_s0 | b5ca7ac4 | 11 | INIT | covered | None | None | NA | NA | NA | NA | NA |  | covering visit of another kind |
| bundle_s0 | b5ca7ac4 | 21 | INIT | covered | None | None | NA | NA | NA | NA | NA |  | covering visit of another kind |
| bundle_s0 | b5ca7ac4 | 25 | RULE | covered | 6 | 23 | NA | NA | 15.55 (exact) | NA | NA |  | unmapped |
| bundle_s1 | b5ca7ac4 | 6 | INIT | covered | 6 | 77 | NA | NA | 32.98 (exact) | NA | NA |  | read relation not in the scope |
| bundle_s1 | b5ca7ac4 | 11 | INIT | covered | 6 | 92 | NA | NA | 22.82 (one) | NA | NA |  | read relation not in the scope |
| bundle_s1 | b5ca7ac4 | 21 | INIT | covered | 7 | 106 | 13.45 | 9.11 | 9.46 (one) | 4.34 | 3.99 | relation pick: read | mapped |
| bundle_s1 | b5ca7ac4 | 25 | RULE | covered | 8 | 419 | NA | NA | 15.55 (exact) | NA | NA |  | replay error |
| bundle_s0 | b6f77b65 | 2 | RULE | covered | 6 | 398 | 20.24 | 14.55 | 12.72 (exact) | 5.69 | 7.52 | relation pick: builtin | mapped |
| bundle_s0 | b99e7126 | 9 | INIT | covered | None | None | NA | NA | NA | NA | NA |  | covering visit of another kind |
| bundle_s0 | b99e7126 | 25 | RULE | covered | None | None | NA | NA | NA | NA | NA |  | covering visit of another kind |
| bundle_s0 | b99e7126 | 30 | INIT | covered | None | None | NA | NA | NA | NA | NA |  | covering visit of another kind |
| bundle_s0 | b99e7126 | 41 | RULE | covered | 6 | 128 | NA | NA | NA (text differs) | NA | NA |  | read relation not in the scope |
| bundle_s1 | b99e7126 | 9 | INIT | covered | None | None | NA | NA | NA | NA | NA |  | covering visit of another kind |
| bundle_s1 | b99e7126 | 25 | RULE | covered | None | None | NA | NA | NA | NA | NA |  | covering visit of another kind |
| bundle_s1 | b99e7126 | 30 | INIT | covered | None | None | NA | NA | NA | NA | NA |  | covering visit of another kind |
| bundle_s1 | b99e7126 | 41 | RULE | covered | 6 | 115 | NA | NA | NA (text differs) | NA | NA |  | read relation not in the scope |
| bundle_s0 | b9e38dc0 | 1 | INIT | covered | None | None | NA | NA | NA | NA | NA |  | covering visit of another kind |
| bundle_s0 | b9e38dc0 | 2 | RULE | covered | 7 | 115 | NA | NA | 3.05 (one) | NA | NA |  | unmapped |
| bundle_s1 | b9e38dc0 | 1 | INIT | covered | None | None | NA | NA | NA | NA | NA |  | covering visit of another kind |
| bundle_s1 | b9e38dc0 | 2 | RULE | covered | 11 | 11 | NA | NA | 3.05 (one) | NA | NA |  | unmapped |
| bundle_s0 | bf45cf4b | 1 | INIT | covered | 6 | 122 | NA | NA | 9.46 (one) | NA | NA |  | read relation not in the scope |
| bundle_s0 | bf45cf4b | 2 | RULE | covered | 14 | 51 | NA | NA | 3.05 (one) | NA | NA |  | unmapped |
| bundle_s0 | bf45cf4b | 8 | INIT | covered | 6 | 338 | NA | NA | 25.12 (one) | NA | NA |  | read relation not in the scope |
| bundle_s1 | bf45cf4b | 1 | INIT | covered | None | None | NA | NA | NA | NA | NA |  | covering visit of another kind |
| bundle_s1 | bf45cf4b | 2 | RULE | covered | 7 | 21 | NA | NA | 3.05 (one) | NA | NA |  | unmapped |
| bundle_s1 | bf45cf4b | 8 | INIT | covered | 6 | 258 | NA | NA | 25.12 (one) | NA | NA |  | read relation not in the scope |
| bundle_s0 | c7f57c3e | 1 | INIT | covered | None | None | NA | NA | NA | NA | NA |  | covering visit of another kind |
| bundle_s0 | c7f57c3e | 41 | RULE | covered | 6 | 125 | NA | NA | 9.60 (exact) | NA | NA |  | read relation not in the scope |
| bundle_s1 | c7f57c3e | 1 | INIT | covered | None | None | NA | NA | NA | NA | NA |  | covering visit of another kind |
| bundle_s1 | c7f57c3e | 41 | RULE | covered | 6 | 138 | NA | NA | 9.60 (exact) | NA | NA |  | read relation not in the scope |
| bundle_s0 | cb2d8a2c | 3 | RULE | covered | 6 | 210 | NA | NA | NA (no record (memory)) | NA | NA |  | read relation not in the scope |
| bundle_s0 | cb2d8a2c | 7 | RULE | covered | 6 | 79 | 4.48 | 2.29 | NA (no record (memory)) | 2.19 | NA |  | mapped |
| bundle_s0 | cb2d8a2c | 8 | RULE | covered | 6 | 79 | 13.77 | 7.49 | NA (no record (memory)) | 6.28 | NA |  | mapped |
| bundle_s0 | cb2d8a2c | 9 | INIT | covered | 6 | 39 | NA | NA | NA (no record (memory)) | NA | NA |  | read relation not in the scope |
| bundle_s1 | cb2d8a2c | 7 | RULE | covered | 6 | 128 | 5.43 | 2.29 | NA (no record (memory)) | 3.14 | NA |  | mapped |
| bundle_s1 | cb2d8a2c | 8 | RULE | covered | 6 | 152 | 14.88 | 7.49 | NA (no record (memory)) | 7.39 | NA |  | mapped |
| bundle_s1 | cb2d8a2c | 9 | INIT | covered | 6 | 106 | NA | NA | NA (no record (memory)) | NA | NA |  | read relation not in the scope |
| bundle_s0 | cbebaa4b | 2 | DET | covered | 6 | 79 | NA | NA | 8.67 (one) | NA | NA |  | read relation not in the scope |
| bundle_s1 | cbebaa4b | 2 | DET | covered | 9 | 48 | NA | NA | 8.67 (one) | NA | NA |  | read relation not in the scope |
| bundle_s1 | cbebaa4b | 45 | RULE | covered | None | None | NA | NA | NA | NA | NA |  | covering visit of another kind |
| bundle_s0 | d59b0160 | 5 | RULE | covered | None | None | NA | NA | NA | NA | NA |  | no covering opening |
| bundle_s0 | d59b0160 | 7 | RULE | covered | 6 | 184 | 4.43 | 2.29 | 3.01 (exact) | 2.14 | 1.42 | relation pick: builtin | mapped |
| bundle_s0 | d59b0160 | 8 | RULE | covered | None | None | NA | NA | NA | NA | NA |  | no covering opening |
| bundle_s0 | d59b0160 | 9 | INIT | covered | 6 | 72 | NA | NA | 16.45 (exact) | NA | NA |  | read relation not in the scope |
| bundle_s0 | d59b0160 | 33 | RULE | covered | 6 | 314 | NA | NA | 16.12 (one) | NA | NA |  | read relation not in the scope |
| bundle_s1 | d59b0160 | 1 | DET | covered | None | None | NA | NA | NA | NA | NA |  | covering visit of another kind |
| bundle_s1 | d59b0160 | 5 | RULE | covered | 8 | 262 | NA | NA | 8.88 (exact) | NA | NA |  | read relation not in the scope |
| bundle_s1 | d59b0160 | 7 | RULE | covered | 6 | 115 | 4.82 | 2.29 | 3.01 (exact) | 2.53 | 1.81 | relation pick: builtin | mapped |
| bundle_s1 | d59b0160 | 8 | RULE | covered | 6 | 115 | 25.13 | 25.06 | 24.74 (exact) | 0.07 | 0.39 | relation pick: read | mapped |
| bundle_s1 | d59b0160 | 9 | INIT | covered | None | None | NA | NA | NA | NA | NA |  | covering visit of another kind |
| bundle_s1 | d59b0160 | 10 | RULE | covered | 7 | 58 | NA | NA | 8.70 (one) | NA | NA |  | read relation not in the scope |
| bundle_s0 | db0c5428 | 3 | DET | covered | 6 | 62 | NA | NA | 8.91 (one) | NA | NA |  | read relation not in the scope |
| bundle_s0 | db0c5428 | 5 | INIT | covered | 15 | 147 | 18.45 | 17.64 | 17.36 (one) | 0.81 | 1.09 | relation pick: read | mapped |
| bundle_s0 | db0c5428 | 13 | None | covered | None | None | NA | NA | NA | NA | NA |  | error |
| bundle_s0 | db0c5428 | 14 | RULE | covered | 6 | 136 | NA | NA | 20.25 (exact) | NA | NA |  | read relation not in the scope |
| bundle_s0 | db0c5428 | 15 | INIT | covered | None | None | NA | NA | NA | NA | NA |  | covering visit of another kind |
| bundle_s0 | db0c5428 | 16 | INIT | covered | 6 | 140 | NA | NA | 17.00 (one) | NA | NA |  | read relation not in the scope |
| bundle_s0 | db0c5428 | 47 | INIT | covered | None | None | NA | NA | NA | NA | NA |  | no covering opening |
| bundle_s1 | db0c5428 | 2 | INIT | covered | 10 | 101 | NA | NA | 24.26 (one) | NA | NA |  | read relation not in the scope |
| bundle_s1 | db0c5428 | 3 | DET | covered | None | None | NA | NA | NA | NA | NA |  | no covering opening |
| bundle_s1 | db0c5428 | 5 | INIT | covered | 10 | 101 | 17.94 | 17.64 | 17.36 (one) | 0.30 | 0.58 | relation pick: builtin | mapped |
| bundle_s1 | db0c5428 | 14 | RULE | covered | 6 | 137 | NA | NA | 20.25 (exact) | NA | NA |  | read relation not in the scope |
| bundle_s1 | db0c5428 | 15 | INIT | covered | None | None | NA | NA | NA | NA | NA |  | covering visit of another kind |
| bundle_s1 | db0c5428 | 16 | INIT | covered | None | None | NA | NA | NA | NA | NA |  | covering visit of another kind |
| bundle_s1 | db0c5428 | 47 | INIT | covered | 7 | 72 | NA | NA | 9.70 (one) | NA | NA |  | read relation not in the scope |
| bundle_s0 | db695cfb | 1 | DET | covered | None | None | NA | NA | NA | NA | NA |  | no covering opening |
| bundle_s0 | db695cfb | 5 | RULE | covered | 6 | 187 | 4.79 | 2.34 | 2.92 (exact) | 2.45 | 1.87 | relation pick: builtin | mapped |
| bundle_s0 | db695cfb | 18 | RULE | covered | 8 | 63 | NA | NA | 6.85 (exact) | NA | NA |  | read relation not in the scope |
| bundle_s1 | db695cfb | 1 | DET | covered | None | None | NA | NA | NA | NA | NA |  | no covering opening |
| bundle_s1 | db695cfb | 5 | RULE | covered | 6 | 262 | 5.36 | 2.34 | 2.92 (exact) | 3.02 | 2.44 | relation pick: builtin | mapped |
| bundle_s1 | db695cfb | 18 | RULE | covered | 9 | 50 | NA | NA | 6.85 (exact) | NA | NA |  | read relation not in the scope |
| bundle_s0 | dbff022c | 1 | RULE | covered | 6 | 26 | 7.84 | 1.95 | 1.39 (one) | 5.89 | 6.45 | relation pick: builtin | mapped |
| bundle_s0 | dbff022c | 2 | INIT | covered | 7 | 310 | 8.85 | 6.77 | 6.69 (one) | 2.08 | 2.16 | relation pick: read | mapped |
| bundle_s0 | dbff022c | 3 | None | covered | None | None | NA | NA | NA | NA | NA |  | error |
| bundle_s0 | dbff022c | 17 | INIT | covered | 7 | 310 | 15.36 | 9.72 | 10.13 (exact) | 5.64 | 5.23 | relation pick: read | mapped |
| bundle_s1 | dbff022c | 1 | RULE | covered | 6 | 118 | 7.83 | 1.95 | 1.39 (one) | 5.88 | 6.44 | relation pick: builtin | mapped |
| bundle_s1 | dbff022c | 17 | INIT | covered | 6 | 77 | NA | NA | 10.13 (exact) | NA | NA |  | read relation not in the scope |
| bundle_s0 | dd6b8c4b | 8 | DET | covered | 5 | 86 | NA | NA | 13.15 (exact) | NA | NA |  | read relation not in the scope |
| bundle_s1 | dd6b8c4b | 2 | DET | covered | None | None | NA | NA | NA | NA | NA |  | covering visit of another kind |
| bundle_s1 | dd6b8c4b | 8 | DET | covered | 7 | 87 | NA | NA | 13.15 (exact) | NA | NA |  | read relation not in the scope |
| bundle_s1 | dd6b8c4b | 13 | RULE | covered | 10 | 52 | NA | NA | 2.73 (exact) | NA | NA |  | unmapped |
| bundle_s0 | de809cff | 3 | RULE | covered | 6 | 507 | 7.08 | 1.95 | 1.39 (one) | 5.13 | 5.69 | relation pick: builtin | mapped |
| bundle_s0 | de809cff | 23 | INIT | covered | None | None | NA | NA | NA | NA | NA |  | covering visit of another kind |
| bundle_s1 | de809cff | 3 | RULE | covered | 6 | 576 | 6.90 | 1.95 | 1.39 (one) | 4.95 | 5.51 | relation pick: builtin | mapped |
| bundle_s1 | de809cff | 23 | INIT | covered | None | None | NA | NA | NA | NA | NA |  | covering visit of another kind |
| bundle_s0 | dfadab01 | 1 | INIT | covered | None | None | NA | NA | NA | NA | NA |  | covering visit of another kind |
| bundle_s1 | dfadab01 | 1 | INIT | covered | None | None | NA | NA | NA | NA | NA |  | covering visit of another kind |
| bundle_s0 | e3721c99 | 5 | RULE | covered | 6 | 169 | NA | NA | NA (text differs) | NA | NA |  | read relation not in the scope |
| bundle_s0 | e3721c99 | 6 | INIT | covered | 7 | 67 | 14.94 | 15.05 | NA (text differs) | -0.11 | NA |  | mapped |
| bundle_s0 | e3721c99 | 17 | RULE | covered | 8 | 52 | NA | NA | NA (text differs) | NA | NA |  | read relation not in the scope |
| bundle_s1 | e3721c99 | 5 | RULE | covered | 6 | 111 | NA | NA | NA (text differs) | NA | NA |  | read relation not in the scope |
| bundle_s1 | e3721c99 | 17 | RULE | covered | None | None | NA | NA | NA | NA | NA |  | covering visit of another kind |
| bundle_s0 | e376de54 | 3 | RULE | covered | 6 | 239 | NA | NA | 17.32 (exact) | NA | NA |  | read relation not in the scope |
| bundle_s0 | e376de54 | 45 | RULE | covered | None | None | NA | NA | NA | NA | NA |  | no covering opening |
| bundle_s1 | e376de54 | 45 | RULE | covered | 6 | 588 | NA | NA | 20.79 (exact) | NA | NA |  | read relation not in the scope |
| bundle_s0 | f560132c | 2 | DET | covered | 7 | 60 | NA | NA | NA (no record (memory)) | NA | NA |  | read relation not in the scope |
| bundle_s0 | f560132c | 3 | RULE | covered | 6 | 143 | NA | NA | NA (no record (memory)) | NA | NA |  | read relation not in the scope |
| bundle_s0 | f560132c | 4 | INIT | covered | 6 | 82 | NA | NA | NA (no record (memory)) | NA | NA |  | read relation not in the scope |
| bundle_s0 | f560132c | 8 | INIT | covered | 8 | 31 | NA | NA | NA (no record (memory)) | NA | NA |  | read relation not in the scope |
| bundle_s1 | f560132c | 1 | INIT | covered | None | None | NA | NA | NA | NA | NA |  | covering visit of another kind |
| bundle_s1 | f560132c | 2 | DET | covered | 6 | 81 | NA | NA | NA (no record (memory)) | NA | NA |  | read relation not in the scope |
| bundle_s1 | f560132c | 3 | RULE | covered | 6 | 97 | NA | NA | NA (no record (memory)) | NA | NA |  | read relation not in the scope |
| bundle_s1 | f560132c | 4 | INIT | covered | 6 | 79 | NA | NA | NA (no record (memory)) | NA | NA |  | read relation not in the scope |
| bundle_s1 | f560132c | 8 | INIT | covered | 11 | 74 | NA | NA | NA (no record (memory)) | NA | NA |  | read relation not in the scope |
| bundle_s1 | f931b4a8 | 27 | RULE | covered | 10 | 54 | 8.54 | 5.30 | 9.56 (one) | 3.24 | -1.02 | relation pick: read | mapped |

## Table 3: places (S - DB), measured forms

| place | sum of gaps (bits) | share [2.5%, 97.5%] | median gap a form | forms where largest |
|---|---|---|---|---|
| relation pick: read | 75.4 | 0.54 [0.45, 0.65] | 1.79 | 21 |
| relation pick: builtin | 46.8 | 0.34 [0.25, 0.40] | 0.89 | 13 |
| op pick | 14.4 | 0.10 [0.05, 0.16] | 0.00 | 1 |
| argument fill: read | -0.2 | 0.00 [0.00, 0.00] | 0.00 | 0 |
| argument fill: other | 1.6 | 0.01 [0.00, 0.02] | 0.00 | 0 |
| join coin | -11.4 | 0.00 [0.00, 0.00] | -0.13 | 0 |
| stop | 0.2 | 0.00 [0.00, 0.01] | 0.00 | 0 |
| proposer | 0.0 | 0.00 [0.00, 0.00] | 0.00 | 0 |
| OR and ALL | 0.0 | 0.00 [0.00, 0.00] | 0.00 | 0 |
| INIT structure | 0.0 | 0.00 [0.00, 0.00] | 0.00 | 0 |
| order sum | -0.1 | 0.00 [0.00, 0.01] | 0.00 | 0 |
| other | 0.0 | 0.00 [0.00, 0.00] | 0.00 | 0 |
| priors and code | -10.4 | 0.00 [0.00, 0.05] | -0.35 | 2 |

Top 3: relation pick: read, relation pick: builtin, op pick. T3 = 0.99 [0.93, 0.99] (37 forms, 16 tasks); bar 0.60 on the 2.5% point. Median gap 2.61 bits.

Verdict: **a few named places**

## Table 4: S - R, the scope places, forms with no DB included

| place | sum of gaps (bits) | share [2.5%, 97.5%] | median gap a form | forms where largest |
|---|---|---|---|---|
| relation pick: read | 83.3 | 0.52 [0.44, 0.63] | 1.73 | 25 |
| relation pick: builtin | 55.9 | 0.35 [0.27, 0.41] | 0.98 | 17 |
| op pick | 17.8 | 0.11 [0.05, 0.16] | 0.00 | 1 |
| argument fill: read | -0.4 | 0.00 [0.00, 0.00] | 0.00 | 0 |
| argument fill: other | 1.8 | 0.01 [0.00, 0.02] | 0.00 | 0 |
| join coin | -12.7 | 0.00 [0.00, 0.00] | -0.13 | 0 |
| stop | 0.3 | 0.00 [0.00, 0.01] | 0.00 | 0 |
| proposer | 0.0 | 0.00 [0.00, 0.00] | 0.00 | 0 |
| OR and ALL | 0.0 | 0.00 [0.00, 0.00] | 0.00 | 0 |
| INIT structure | 0.0 | 0.00 [0.00, 0.00] | 0.00 | 0 |
| order sum | -0.2 | 0.00 [0.00, 0.01] | 0.00 | 0 |
| other | 0.0 | 0.00 [0.00, 0.00] | 0.00 | 0 |

Top 3: relation pick: read, relation pick: builtin, op pick. T3 = 0.99 [0.98, 0.99] (43 forms, 19 tasks).

## Table 5: forms whose read relation is not in the scope

| arm | task | g | gold reads | relations of that gold form that the scope holds |
|---|---|---|---|---|
| bundle_s0 | 581f7754 | 3 | &r14 | none |
| bundle_s0 | 5961cc34 | 12 | &r26 | none |
| bundle_s1 | 5961cc34 | 12 | &r26 | none |
| bundle_s0 | 6e453dd6 | 39 | &r3 | none |
| bundle_s0 | 6e453dd6 | 50 | &r72 | none |
| bundle_s1 | 6e453dd6 | 15 | &r24.component | none |
| bundle_s1 | 6e453dd6 | 39 | &r3 | none |
| bundle_s0 | a6f40cea | 6 | &r3 | none |
| bundle_s1 | a6f40cea | 5 | &r6 | none |
| bundle_s1 | a6f40cea | 6 | &r3 | none |
| bundle_s0 | aa4ec2a5 | 5 | &r4 | none |
| bundle_s0 | aa4ec2a5 | 6 | &r2 | none |
| bundle_s1 | aa4ec2a5 | 2 | &r1 | none |
| bundle_s1 | aa4ec2a5 | 6 | &r2 | none |
| bundle_s0 | abc82100 | 11 | &r10 | none |
| bundle_s1 | abc82100 | 11 | &r10 | none |
| bundle_s0 | b10624e5 | 19 | &r30.value, &r26, &r3 | none |
| bundle_s1 | b10624e5 | 3 | &r2 | none |
| bundle_s1 | b10624e5 | 10 | &r9, &r10, &r11 | none |
| bundle_s0 | b5ca7ac4 | 6 | &r6 | none |
| bundle_s1 | b5ca7ac4 | 6 | &r6 | none |
| bundle_s1 | b5ca7ac4 | 11 | &r13 | none |
| bundle_s0 | b99e7126 | 41 | &r83.maximal | none |
| bundle_s1 | b99e7126 | 41 | &r83.maximal | none |
| bundle_s0 | bf45cf4b | 1 | &r0.size | none |
| bundle_s0 | bf45cf4b | 8 | &r20, &r24 | none |
| bundle_s1 | bf45cf4b | 8 | &r20, &r24 | none |
| bundle_s0 | c7f57c3e | 41 | &r73, &r49 | none |
| bundle_s1 | c7f57c3e | 41 | &r73, &r49 | none |
| bundle_s0 | cb2d8a2c | 3 | &r2 | none |
| bundle_s0 | cb2d8a2c | 9 | &r7 | none |
| bundle_s1 | cb2d8a2c | 9 | &r7 | none |
| bundle_s0 | cbebaa4b | 2 | &r3.maximal | none |
| bundle_s1 | cbebaa4b | 2 | &r3.maximal | none |
| bundle_s0 | d59b0160 | 9 | &r5 | &r9.cell |
| bundle_s0 | d59b0160 | 33 | &r41 | none |
| bundle_s1 | d59b0160 | 5 | &r4 | none |
| bundle_s1 | d59b0160 | 10 | &r9.cell, &r7 | none |
| bundle_s0 | db0c5428 | 3 | &r4.maximal | none |
| bundle_s0 | db0c5428 | 14 | &r27, &r26 | none |
| bundle_s0 | db0c5428 | 16 | &r29.size | none |
| bundle_s1 | db0c5428 | 2 | &r1.size | none |
| bundle_s1 | db0c5428 | 14 | &r27, &r26 | none |
| bundle_s1 | db0c5428 | 47 | &r72 | none |
| bundle_s0 | db695cfb | 18 | &r25, &r2 | none |
| bundle_s1 | db695cfb | 18 | &r25, &r2 | none |
| bundle_s1 | dbff022c | 17 | &r0 | none |
| bundle_s0 | dd6b8c4b | 8 | &r3, &r7 | none |
| bundle_s1 | dd6b8c4b | 8 | &r3, &r7 | none |
| bundle_s0 | e3721c99 | 5 | &r1 | none |
| bundle_s0 | e3721c99 | 17 | &r31, &r6.component | none |
| bundle_s1 | e3721c99 | 5 | &r1 | none |
| bundle_s0 | e376de54 | 3 | &r1, &r2 | none |
| bundle_s1 | e376de54 | 45 | &r57.maximal | none |
| bundle_s0 | f560132c | 2 | &r3.maximal | none |
| bundle_s0 | f560132c | 3 | &r14 | none |
| bundle_s0 | f560132c | 4 | &r15 | none |
| bundle_s0 | f560132c | 8 | &r15 | none |
| bundle_s1 | f560132c | 2 | &r3.maximal | none |
| bundle_s1 | f560132c | 3 | &r14 | none |
| bundle_s1 | f560132c | 4 | &r15 | none |
| bundle_s1 | f560132c | 8 | &r15 | none |

## C against covered

C: the C forms of the bundle arms (class C of scope-loss/forms.tsv), from forms.*of*.jsonl. Covered: this read. Both walk the gold clause under the recorded scope of one opening: C the opening with the most slot tries that held the reads with the form's kind and did not draw the form; covered the opening that opened the covering visit. Shares are positive mass shares as in table 3; the interval is the task bootstrap (2000 resamples, a task brings all its forms).

| set | entered | S and R valid | measured (with DB) | tasks | median S - DB | median S - R | median scope_n [Q1, Q3] |
|---|---|---|---|---|---|---|---|
| C | 52 | 41 | 39 | 17 | 4.13 | 3.86 | 8.00 [6.00, 10.00] |
| covered | 173 | 43 | 37 | 19 | 2.61 | 3.02 | 6.00 [6.00, 7.00] |

### Places on S - DB (measured forms)

| place | C: sum | C: median | C: share | covered: sum | covered: median | covered: share |
|---|---|---|---|---|---|---|
| relation pick: read | 92.1 | 2.04 | 0.50 | 75.4 | 1.79 | 0.54 |
| relation pick: builtin | 75.2 | 1.77 | 0.41 | 46.8 | 0.89 | 0.34 |
| op pick | 16.0 | 0.00 | 0.09 | 14.4 | 0.00 | 0.10 |
| argument fill: read | -1.4 | 0.00 | 0.00 | -0.2 | 0.00 | 0.00 |
| argument fill: other | -2.7 | 0.00 | 0.00 | 1.6 | 0.00 | 0.01 |
| join coin | -8.2 | -0.21 | 0.00 | -11.4 | -0.13 | 0.00 |
| stop | 1.5 | 0.00 | 0.01 | 0.2 | 0.00 | 0.00 |
| proposer | 0.0 | 0.00 | 0.00 | 0.0 | 0.00 | 0.00 |
| OR and ALL | 0.0 | 0.00 | 0.00 | 0.0 | 0.00 | 0.00 |
| INIT structure | 0.0 | 0.00 | 0.00 | 0.0 | 0.00 | 0.00 |
| order sum | -0.6 | 0.00 | 0.00 | -0.1 | 0.00 | 0.00 |
| other | 0.0 | 0.00 | 0.00 | 0.0 | 0.00 | 0.00 |
| priors and code | -0.1 | 0.06 | 0.00 | -10.4 | -0.35 | 0.00 |

| relation pick (read + builtin) | C | covered |
|---|---|---|
| forms | 39 | 37 |
| share of the positive mass [2.5%, 97.5%] | 0.90 [0.77, 0.96] | 0.88 [0.80, 0.94] |
| read-atom part of that share [2.5%, 97.5%] | [0.35, 0.67] | [0.45, 0.65] |
| median bits a form [2.5%, 97.5%] | 4.21 [3.43, 5.54] | 3.31 [3.01, 3.94] |
| mean bits a form | 4.29 | 3.30 |
| rank correlation of scope_n with the relation-pick gap | 0.11 | 0.08 |

C minus covered: relation-pick share [-0.13, 0.12], median relation-pick gap a form [-0.03, 2.31] bits (tasks resampled within each set).

### Places on S - R (scope places, forms with S and R)

| place | C: sum | C: median | C: share | covered: sum | covered: median | covered: share |
|---|---|---|---|---|---|---|
| relation pick: read | 96.8 | 2.04 | 0.49 | 83.3 | 1.73 | 0.52 |
| relation pick: builtin | 78.9 | 1.77 | 0.40 | 55.9 | 0.98 | 0.35 |
| op pick | 18.2 | 0.00 | 0.09 | 17.8 | 0.00 | 0.11 |
| argument fill: read | -1.1 | 0.00 | 0.00 | -0.4 | 0.00 | 0.00 |
| argument fill: other | 2.3 | 0.00 | 0.01 | 1.8 | 0.00 | 0.01 |
| join coin | -8.2 | -0.21 | 0.00 | -12.7 | -0.13 | 0.00 |
| stop | -1.5 | 0.00 | 0.00 | 0.3 | 0.00 | 0.00 |
| proposer | 0.0 | 0.00 | 0.00 | 0.0 | 0.00 | 0.00 |
| OR and ALL | 0.0 | 0.00 | 0.00 | 0.0 | 0.00 | 0.00 |
| INIT structure | 0.0 | 0.00 | 0.00 | 0.0 | 0.00 | 0.00 |
| order sum | -7.9 | 0.00 | 0.00 | -0.2 | 0.00 | 0.00 |
| other | -0.2 | 0.00 | 0.00 | 0.0 | 0.00 | 0.00 |

| relation pick (read + builtin) | C | covered |
|---|---|---|
| forms | 41 | 43 |
| share of the positive mass [2.5%, 97.5%] | 0.90 [0.79, 0.94] | 0.88 [0.83, 0.93] |
| read-atom part of that share [2.5%, 97.5%] | [0.38, 0.63] | [0.44, 0.63] |
| median bits a form [2.5%, 97.5%] | 4.21 [3.48, 5.48] | 3.31 [2.97, 3.90] |
| mean bits a form | 4.29 | 3.24 |
| rank correlation of scope_n with the relation-pick gap | 0.10 | 0.02 |

C minus covered: relation-pick share [-0.10, 0.09], median relation-pick gap a form [0.11, 2.17] bits (tasks resampled within each set).

The per-form scope_n, slot_tries and relation-pick gaps of both sets are in compare-forms.tsv.

## Checks

- 1 table check: `{"fails": [], "mapped": 43, "mapped_not_passing": []}`
- 2 walks: `{"invalid": []}`
- 3 kind: `{"not_gold_kind": [], "k_forms": []}`
- 4 sums: `{"beyond_005": [], "other_parts": {"port atom: fcol": 0.076}, "other_count": 1, "other_bits": 0.076}`
- 5 read/other split: `{"phases_without_atom_row": 0}`
- 6 R against DB (not a gate): `{"exact": {"n": 20, "median": -0.6040000000000001, "iqr": [-0.7229999999999999, -0.3949999999999996], "max_abs": 5.045, "beyond_3": ["bundle_s0 abc82100 g12 -5.04"]}, "one": {"n": 17, "median": 0.56, "iqr": [0.07999999999999918, 0.56], "max_abs": 4.260000000000001, "beyond_3": ["bundle_s1 f931b4a8 g27 -4.26"]}}`
- 7 order free: `{"n": 0, "failed": [], "items": []}`
- 8 determinism: `{"n": 0, "failed": [], "items": []}`
- 9 exact or estimate: `{"estimates": []}`

## Forms not measured, other reasons

| arm | task | g | status | how |
|---|---|---|---|---|
| bundle_s0 | 135a2760 | 9 | covering visit of another kind |  |
| bundle_s1 | 135a2760 | 9 | covering visit of another kind |  |
| bundle_s0 | 142ca369 | 1 | covering visit of another kind |  |
| bundle_s1 | 142ca369 | 1 | covering visit of another kind |  |
| bundle_s1 | 142ca369 | 9 | covering visit of another kind |  |
| bundle_s0 | 581f7754 | 1 | covering visit of another kind |  |
| bundle_s0 | 581f7754 | 2 | unmapped | &r3.maximal: ports not mapped ['Key'] [''] |
| bundle_s1 | 581f7754 | 1 | covering visit of another kind |  |
| bundle_s1 | 581f7754 | 2 | unmapped | &r3.maximal: ports not mapped ['Key'] [''] |
| bundle_s0 | 6e453dd6 | 15 | covering visit of another kind |  |
| bundle_s1 | 6e453dd6 | 1 | covering visit of another kind |  |
| bundle_s0 | 80a900e0 | 11 | covering visit of another kind |  |
| bundle_s0 | 88bcf3b4 | 1 | covering visit of another kind |  |
| bundle_s0 | 8e5c0c38 | 2 | covering visit of another kind |  |
| bundle_s0 | 8e5c0c38 | 3 | unmapped | &r4.maximal: ports not mapped ['Key'] [''] |
| bundle_s0 | 8e5c0c38 | 18 | no covering opening |  |
| bundle_s1 | 8e5c0c38 | 2 | covering visit of another kind |  |
| bundle_s1 | 8e5c0c38 | 3 | unmapped | &r4.maximal: ports not mapped ['Key'] [''] |
| bundle_s1 | 8e5c0c38 | 18 | no covering opening |  |
| bundle_s0 | a25697e4 | 1 | covering visit of another kind |  |
| bundle_s0 | a25697e4 | 2 | unmapped | &r3.maximal: ports not mapped ['Key'] [''] |
| bundle_s1 | a25697e4 | 1 | covering visit of another kind |  |
| bundle_s0 | a6f40cea | 5 | no covering opening |  |
| bundle_s0 | a6f40cea | 12 | covering visit of another kind |  |
| bundle_s1 | a6f40cea | 12 | covering visit of another kind |  |
| bundle_s0 | aa4ec2a5 | 11 | covering visit of another kind |  |
| bundle_s0 | b5ca7ac4 | 11 | covering visit of another kind |  |
| bundle_s0 | b5ca7ac4 | 21 | covering visit of another kind |  |
| bundle_s0 | b5ca7ac4 | 25 | unmapped | &r14.value: ports not mapped ['Col'] [''] |
| bundle_s1 | b5ca7ac4 | 25 | replay error | &r14.value -> &f389.maximal renamed {'Col': 'Key'} |
| bundle_s0 | b99e7126 | 9 | covering visit of another kind |  |
| bundle_s0 | b99e7126 | 25 | covering visit of another kind |  |
| bundle_s0 | b99e7126 | 30 | covering visit of another kind |  |
| bundle_s1 | b99e7126 | 9 | covering visit of another kind |  |
| bundle_s1 | b99e7126 | 25 | covering visit of another kind |  |
| bundle_s1 | b99e7126 | 30 | covering visit of another kind |  |
| bundle_s0 | b9e38dc0 | 1 | covering visit of another kind |  |
| bundle_s0 | b9e38dc0 | 2 | unmapped | &r3.maximal: ports not mapped ['Key'] [''] |
| bundle_s1 | b9e38dc0 | 1 | covering visit of another kind |  |
| bundle_s1 | b9e38dc0 | 2 | unmapped | &r3.maximal: ports not mapped ['Key'] [''] |
| bundle_s0 | bf45cf4b | 2 | unmapped | &r3.maximal: ports not mapped ['Key'] [''] |
| bundle_s1 | bf45cf4b | 1 | covering visit of another kind |  |
| bundle_s1 | bf45cf4b | 2 | unmapped | &r3.maximal: ports not mapped ['Key'] [''] |
| bundle_s0 | c7f57c3e | 1 | covering visit of another kind |  |
| bundle_s1 | c7f57c3e | 1 | covering visit of another kind |  |
| bundle_s1 | cbebaa4b | 45 | covering visit of another kind |  |
| bundle_s0 | d59b0160 | 5 | no covering opening |  |
| bundle_s0 | d59b0160 | 8 | no covering opening |  |
| bundle_s1 | d59b0160 | 1 | covering visit of another kind |  |
| bundle_s1 | d59b0160 | 9 | covering visit of another kind |  |
| bundle_s0 | db0c5428 | 13 | error | KeyError: 2362 |
| bundle_s0 | db0c5428 | 15 | covering visit of another kind |  |
| bundle_s0 | db0c5428 | 47 | no covering opening |  |
| bundle_s1 | db0c5428 | 3 | no covering opening |  |
| bundle_s1 | db0c5428 | 15 | covering visit of another kind |  |
| bundle_s1 | db0c5428 | 16 | covering visit of another kind |  |
| bundle_s0 | db695cfb | 1 | no covering opening |  |
| bundle_s1 | db695cfb | 1 | no covering opening |  |
| bundle_s0 | dbff022c | 3 | error | KeyError: 3017 |
| bundle_s1 | dd6b8c4b | 2 | covering visit of another kind |  |
| bundle_s1 | dd6b8c4b | 13 | unmapped | &r2: INIT relation &f790.1 with no known sub-name |
| bundle_s0 | de809cff | 23 | covering visit of another kind |  |
| bundle_s1 | de809cff | 23 | covering visit of another kind |  |
| bundle_s0 | dfadab01 | 1 | covering visit of another kind |  |
| bundle_s1 | dfadab01 | 1 | covering visit of another kind |  |
| bundle_s1 | e3721c99 | 17 | covering visit of another kind |  |
| bundle_s0 | e376de54 | 45 | no covering opening |  |
| bundle_s1 | f560132c | 1 | covering visit of another kind |  |
