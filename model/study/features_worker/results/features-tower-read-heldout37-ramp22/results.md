# Tower read, held-out 37 and ramp 22

Design: `/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-tower-read-design/design.md`.

## Data check

- walks, 37: 37 tasks, seeds 0-15, 592 walks, 22864 steps
- walks, ramp: 22 tasks, seeds 0-15, 352 walks, 5488 steps
- walks, corpus: 989 tasks, seeds 0-3, 3956 walks, 84724 steps
- steps by kind, 37, seed 0: {'RULE': 1076, 'INIT': 221, 'DET': 130, 'RIGID_DET': 2}
- steps by kind, ramp, seed 0: {'DET': 53, 'INIT': 59, 'RULE': 231}
- tower rows: 28352 steps over 59 tasks
- held steps done, 37: 1429 rows (by pass {1: 444, 2: 985}), 37 tasks; pass-1 steps listed 444, done 444; non-OTHER steps 1429, done 1429; P_kind = 0: 0; h_joint = 0: 265; held dir /private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-tower-read-heldout37-ramp22/held
- held steps done, ramp: 343 rows (by pass {1: 241, 2: 102}), 22 tasks; pass-1 steps listed 241, done 241; non-OTHER steps 343, done 343; P_kind = 0: 0; h_joint = 0: 37; held dir /private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-tower-read-heldout37-ramp22/held


## the 37 (the verdict)

1429 done steps used, 22864 tower steps (all seeds); left out: none.

### Table 1, bits per form: the 37 (the verdict)

| model | bits mean | bits median | shape part | pattern part | saving against the proposal | saving, steps with h_joint >= 1 |
|---|---|---|---|---|---|---|
| proposal | 5.85 | 5.70 | 2.27 | 3.58 | - | - |
| M0 | 5.89 | 5.13 | 1.94 | 3.95 | -0.04 [-0.34, 0.24] | -0.02 [-0.22, 0.16] |
| M1 | 5.71 | 4.77 | 1.81 | 3.90 | 0.14 [-0.16, 0.41] | 0.16 [-0.03, 0.34] |
| M2A | 5.77 | 4.64 | 1.82 | 3.94 | 0.08 [-0.25, 0.39] | 0.19 [-0.01, 0.37] |
| M2B | 5.62 | 4.64 | 1.82 | 3.80 | 0.23 [-0.08, 0.51] | 0.24 [0.05, 0.42] |
| M2M | 5.62 | 4.63 | 1.83 | 3.79 | 0.23 [-0.06, 0.49] | 0.25 [0.05, 0.43] |
| M3 | 5.58 | 4.61 | 1.88 | 3.70 | 0.27 [-0.06, 0.56] | 0.31 [0.10, 0.51] |

### Table 2, the state: the 37 (the verdict)

Gain = bits of the first model minus bits of the second, in bits per form. "All steps" is every step of every walk seed 0 to 15 (equal weights); "done steps" is seed 0 with the weights of Table 1. Read-time shuffle: the gain with `prev` permuted within each task-seed walk (steps t >= 1), mean of 20 permutations. Fit-time shuffle: the gain with the second model fit on walks whose `prev` is permuted, scored with the true `prev`.

| gain | all steps | done steps | read-time shuffle, all steps | fit-time shuffle, all steps |
|---|---|---|---|---|
| M1 - M2A | -0.006 [-0.044, 0.028] | -0.053 [-0.150, 0.026] | -0.588 [-0.657, -0.530] | -0.042 [-0.069, -0.018] |
| M1 - M2B | 0.093 [0.076, 0.110] | 0.094 [0.046, 0.138] | -1.241 [-1.359, -1.134] | -0.046 [-0.063, -0.028] |
| M1 - M2M | 0.092 [0.064, 0.119] | 0.091 [0.039, 0.145] | - | - |
| M2M - M3 | 0.024 [-0.021, 0.064] | 0.039 [-0.043, 0.114] | - | - |

### Verdict: the 37 (the verdict)

- Saving: M2A saves 0.08 [-0.25, 0.39] bits per form against the proposal, M2B 0.23 [-0.08, 0.51]. A tower-conditioned proposal saves: **no** (M2A interval includes or is below 0).
- State: M1 - M2A -0.006 [-0.044, 0.028], M1 - M2B 0.093 [0.076, 0.110] (all steps); the larger gain is meaning B; read-time-shuffled gain -1.241 [-1.359, -1.134]. The state carries information: **yes** (interval above 0 for at least one meaning: True; gain of .05 or more: True; shuffled gain 0 or below: True).
- Source of the M2A saving (0.08 bits per form, done steps): set facts (proposal - M0) -0.04 (-49%), the last built (M0 - M1) 0.18 (213%), the state (M1 - M2A) -0.05 (-64%).
- Where: share of saved bits by place: chain step 372%, root 35%, top join 30%, join -337%. Places with half or more of the saved bits: chain step. Largest saving per form: top join (1.05 bits).

### Table 4, by place of gold's form

Steps = done / total (non-OTHER steps of the seed-0 walks). Bits are weighted means; the saving is the proposal minus M2A, with an interval by task; the share is the cell's part of all saved bits.

| place | f's mode | steps | proposal | M1 | M2A | M2B | saving of M2A | share of saved bits |
|---|---|---|---|---|---|---|---|---|
| root | all | 133 / 133 | 3.55 | 3.25 | 3.24 | 3.21 | 0.32 [0.02, 0.61] | 35% |
|  | JUMP | 133 / 133 | 3.55 | 3.25 | 3.24 | 3.21 | 0.32 [0.02, 0.61] | 35% |
| chain step | all | 591 / 591 | 5.58 | 4.85 | 4.83 | 4.80 | 0.75 [0.45, 1.01] | 372% |
|  | EXTEND | 356 / 356 | 5.29 | 3.79 | 3.76 | 3.77 | 1.53 [1.28, 1.75] | 456% |
|  | BACKTRACK | 64 / 64 | 7.26 | 7.15 | 7.09 | 6.79 | 0.17 [-0.78, 0.90] | 9% |
|  | JUMP | 171 / 171 | 5.56 | 6.22 | 6.21 | 6.19 | -0.65 [-1.48, -0.00] | -94% |
| join | all | 671 / 671 | 6.51 | 6.95 | 7.11 | 6.82 | -0.60 [-1.11, -0.13] | -337% |
|  | EXTEND | 443 / 443 | 6.21 | 6.10 | 6.18 | 6.01 | 0.03 [-0.44, 0.43] | 10% |
|  | BACKTRACK | 95 / 95 | 8.30 | 10.44 | 11.14 | 10.04 | -2.84 [-4.72, -1.13] | -227% |
|  | JUMP | 133 / 133 | 6.23 | 7.32 | 7.31 | 7.20 | -1.08 [-1.80, -0.52] | -121% |
| top join | all | 34 / 34 | 6.54 | 5.73 | 5.49 | 5.63 | 1.05 [-0.67, 2.46] | 30% |
|  | EXTEND | 32 / 32 | 6.52 | 5.50 | 5.30 | 5.43 | 1.23 [-0.62, 2.67] | 33% |
|  | JUMP | 2 / 2 | 6.85 | 9.53 | 8.64 | 8.88 | -1.79 [-4.95, 1.37] | -3% |

### Table 5, by outcome (weighted medians of bits)

| outcome | steps | proposal | M2A |
|---|---|---|---|
| gold mode6 EXTEND | 831 | 5.46 | 3.83 |
| gold mode6 JUMP+ | 306 | 5.70 | 5.66 |
| gold mode6 JUMP0 | 133 | 3.10 | 2.33 |
| gold mode6 BT1 | 120 | 7.57 | 6.87 |
| gold mode6 BT2 | 26 | 9.16 | 9.22 |
| gold mode6 BT3+ | 13 | 7.57 | 10.01 |
| gold shape RULE|0|- | 676 | 5.07 | 3.86 |
| gold shape RULE|1|- | 316 | 5.70 | 4.16 |
| gold shape DET|0|- | 125 | 3.83 | 4.16 |
| gold shape INIT|0|key-plain | 70 | 8.15 | 6.65 |
| gold shape RULE|2|- | 61 | 6.83 | 6.79 |
| gold shape INIT|0|nokey | 60 | 7.41 | 7.65 |
| gold shape INIT|1|key-ident | 41 | 9.46 | 5.82 |
| gold shape INIT|1|nokey | 28 | 8.15 | 10.11 |
| gold shape RULE|3+|- | 23 | 7.57 | 12.02 |
| gold shape INIT|1|key-plain | 12 | 9.73 | 12.16 |

### Table 6, context: 37

| model | alpha shape | alpha pattern | CV bits on the corpus (shape + pattern) | held bits, all steps seeds 0-15 | spread over seeds (sd, min, max) of held bits |
|---|---|---|---|---|---|
| M0 | 128 | 128 | 5.088 (1.618 + 3.470) | 5.853 | 0.048, 5.748, 5.949 |
| M1 | 128 | 128 | 4.959 (1.527 + 3.431) | 5.664 | 0.042, 5.572, 5.724 |
| M2A | 128 | 128 | 4.932 (1.529 + 3.402) | 5.670 | 0.051, 5.578, 5.766 |
| M2B | 128 | 128 | 4.879 (1.529 + 3.350) | 5.571 | 0.045, 5.457, 5.637 |
| M2M | 128 | 128 | 4.881 (1.533 + 3.348) | 5.572 | 0.044, 5.475, 5.643 |
| M3 | 128 | 128 | 4.836 (1.548 + 3.289) | 5.548 | 0.055, 5.434, 5.637 |

- Mean `walk_bits` per step (the cost of the order that neither side pays): 0.773 on 37 walks (all seeds), 0.717 on the corpus walks.
- Steps left out: 0 of kind OTHER in the seed-0 walk, 0 done steps with P_kind = 0 (kind not admitted or outside KIND_TOK).
- Done steps with h_joint = 0 (the proposal's bits are a lower bound there): 265 of 1429 (19% weighted, 19% raw).
- The saving of M2A with the h_joint = 0 steps left out: 0.19 [-0.01, 0.37] (1164 steps).

## the ramp (a second, weak read: relR4_o has the ramp in its train rows)

343 done steps used, 5488 tower steps (all seeds); left out: none.

### Table 1, bits per form: the ramp (a second, weak read: relR4_o has the ramp in its train rows)

| model | bits mean | bits median | shape part | pattern part | saving against the proposal | saving, steps with h_joint >= 1 |
|---|---|---|---|---|---|---|
| proposal | 5.01 | 4.76 | 1.94 | 3.06 | - | - |
| M0 | 4.58 | 3.96 | 1.51 | 3.07 | 0.42 [0.05, 0.67] | 0.45 [0.32, 0.57] |
| M1 | 4.52 | 3.82 | 1.49 | 3.03 | 0.48 [0.08, 0.78] | 0.55 [0.38, 0.72] |
| M2A | 4.52 | 3.89 | 1.51 | 3.01 | 0.48 [0.06, 0.79] | 0.58 [0.39, 0.76] |
| M2B | 4.49 | 3.78 | 1.51 | 2.98 | 0.52 [0.07, 0.82] | 0.60 [0.43, 0.78] |
| M2M | 4.42 | 3.79 | 1.51 | 2.91 | 0.58 [0.20, 0.85] | 0.64 [0.47, 0.80] |
| M3 | 4.45 | 3.75 | 1.53 | 2.92 | 0.55 [0.22, 0.79] | 0.59 [0.39, 0.77] |

### Table 2, the state: the ramp (a second, weak read: relR4_o has the ramp in its train rows)

Gain = bits of the first model minus bits of the second, in bits per form. "All steps" is every step of every walk seed 0 to 15 (equal weights); "done steps" is seed 0 with the weights of Table 1. Read-time shuffle: the gain with `prev` permuted within each task-seed walk (steps t >= 1), mean of 20 permutations. Fit-time shuffle: the gain with the second model fit on walks whose `prev` is permuted, scored with the true `prev`.

| gain | all steps | done steps | read-time shuffle, all steps | fit-time shuffle, all steps |
|---|---|---|---|---|
| M1 - M2A | 0.045 [0.006, 0.078] | 0.001 [-0.050, 0.051] | -1.008 [-1.155, -0.863] | -0.060 [-0.082, -0.038] |
| M1 - M2B | 0.054 [0.037, 0.073] | 0.036 [-0.021, 0.092] | -1.829 [-2.083, -1.579] | -0.057 [-0.077, -0.036] |
| M1 - M2M | 0.076 [0.042, 0.109] | 0.097 [0.024, 0.159] | - | - |
| M2M - M3 | -0.004 [-0.049, 0.038] | -0.027 [-0.126, 0.053] | - | - |

### Verdict: the ramp (a second, weak read: relR4_o has the ramp in its train rows)

- Saving: M2A saves 0.48 [0.06, 0.79] bits per form against the proposal, M2B 0.52 [0.07, 0.82]. A tower-conditioned proposal saves: **yes** (M2A interval above 0).
- State: M1 - M2A 0.045 [0.006, 0.078], M1 - M2B 0.054 [0.037, 0.073] (all steps); the larger gain is meaning B; read-time-shuffled gain -1.829 [-2.083, -1.579]. The state carries information: **yes** (interval above 0 for at least one meaning: True; gain of .05 or more: True; shuffled gain 0 or below: True).
- Source of the M2A saving (0.48 bits per form, done steps): set facts (proposal - M0) 0.42 (87%), the last built (M0 - M1) 0.06 (13%), the state (M1 - M2A) 0.00 (0%).
- Where: share of saved bits by place: chain step 52%, root 17%, top join 17%, join 14%. Places with half or more of the saved bits: chain step. Largest saving per form: top join (1.63 bits).

### Table 4, by place of gold's form

Steps = done / total (non-OTHER steps of the seed-0 walks). Bits are weighted means; the saving is the proposal minus M2A, with an interval by task; the share is the cell's part of all saved bits.

| place | f's mode | steps | proposal | M1 | M2A | M2B | saving of M2A | share of saved bits |
|---|---|---|---|---|---|---|---|---|
| root | all | 66 / 66 | 3.01 | 2.53 | 2.58 | 2.57 | 0.43 [0.18, 0.71] | 17% |
|  | JUMP | 66 / 66 | 3.01 | 2.53 | 2.58 | 2.57 | 0.43 [0.18, 0.71] | 17% |
| chain step | all | 150 / 150 | 4.75 | 4.17 | 4.17 | 4.12 | 0.58 [0.28, 0.86] | 52% |
|  | EXTEND | 98 / 98 | 4.10 | 3.07 | 3.05 | 3.07 | 1.05 [0.70, 1.40] | 62% |
|  | BACKTRACK | 17 / 17 | 6.80 | 5.79 | 5.66 | 5.48 | 1.14 [0.09, 1.99] | 12% |
|  | JUMP | 35 / 35 | 5.56 | 6.46 | 6.57 | 6.39 | -1.01 [-1.69, -0.48] | -21% |
| join | all | 110 / 110 | 6.52 | 6.29 | 6.31 | 6.24 | 0.21 [-1.06, 1.05] | 14% |
|  | EXTEND | 76 / 76 | 6.17 | 5.03 | 5.00 | 4.95 | 1.17 [0.63, 1.68] | 54% |
|  | BACKTRACK | 17 / 17 | 8.30 | 11.30 | 11.92 | 11.38 | -3.63 [-12.50, 0.83] | -37% |
|  | JUMP | 17 / 17 | 6.32 | 6.93 | 6.56 | 6.88 | -0.25 [-0.83, 0.43] | -3% |
| top join | all | 17 / 17 | 5.19 | 3.88 | 3.56 | 3.82 | 1.63 [0.48, 2.62] | 17% |
|  | EXTEND | 16 / 16 | 5.22 | 3.57 | 3.24 | 3.51 | 1.99 [1.30, 2.66] | 19% |
|  | JUMP | 1 / 1 | 4.68 | 8.76 | 8.75 | 8.75 | -4.07 [-4.07, -4.07] | -2% |

### Table 5, by outcome (weighted medians of bits)

| outcome | steps | proposal | M2A |
|---|---|---|---|
| gold mode6 EXTEND | 190 | 4.76 | 3.17 |
| gold mode6 JUMP0 | 66 | 2.79 | 2.23 |
| gold mode6 JUMP+ | 53 | 5.70 | 6.24 |
| gold mode6 BT1 | 28 | 7.57 | 6.02 |
| gold mode6 BT3+ | 3 | 7.57 | 8.21 |
| gold mode6 BT2 | 3 | 9.16 | 10.93 |
| gold shape RULE|0|- | 215 | 4.66 | 3.39 |
| gold shape DET|0|- | 51 | 2.79 | 1.82 |
| gold shape INIT|0|nokey | 23 | 7.41 | 6.74 |
| gold shape RULE|1|- | 16 | 4.66 | 4.69 |
| gold shape INIT|0|key-plain | 13 | 6.93 | 5.63 |
| gold shape INIT|1|nokey | 11 | 9.73 | 8.24 |
| gold shape INIT|1|key-ident | 7 | 7.41 | 4.14 |
| gold shape INIT|1|key-plain | 4 | 9.73 | 11.38 |
| gold shape DET|1|- | 2 | 6.34 | 5.43 |
| gold shape INIT|2|key-ident | 1 | 9.73 | 7.07 |

### Table 6, context: ramp

| model | alpha shape | alpha pattern | CV bits on the corpus (shape + pattern) | held bits, all steps seeds 0-15 | spread over seeds (sd, min, max) of held bits |
|---|---|---|---|---|---|
| M0 | 128 | 128 | 5.088 (1.618 + 3.470) | 4.426 | 0.057, 4.343, 4.585 |
| M1 | 128 | 128 | 4.959 (1.527 + 3.431) | 4.323 | 0.072, 4.236, 4.522 |
| M2A | 128 | 128 | 4.932 (1.529 + 3.402) | 4.278 | 0.078, 4.171, 4.521 |
| M2B | 128 | 128 | 4.879 (1.529 + 3.350) | 4.269 | 0.075, 4.163, 4.486 |
| M2M | 128 | 128 | 4.881 (1.533 + 3.348) | 4.247 | 0.068, 4.129, 4.425 |
| M3 | 128 | 128 | 4.836 (1.548 + 3.289) | 4.251 | 0.071, 4.135, 4.452 |

- Mean `walk_bits` per step (the cost of the order that neither side pays): 0.635 on ramp walks (all seeds), 0.717 on the corpus walks.
- Steps left out: 0 of kind OTHER in the seed-0 walk, 0 done steps with P_kind = 0 (kind not admitted or outside KIND_TOK).
- Done steps with h_joint = 0 (the proposal's bits are a lower bound there): 37 of 343 (11% weighted, 11% raw).
- The saving of M2A with the h_joint = 0 steps left out: 0.58 [0.39, 0.76] (306 steps).

## Walks

### Table 3, share of steps in each state (t >= 1; the state is the mode of the step before)

Held sets: seed 0, then mean over seeds 0 to 15 with the standard deviation over seeds. Corpus: mean over seeds 0 to 3.

| set | read | EXTEND | BT1 | BT2 | BT3+ | JUMP0 | JUMP+ | BACKTRACK | JUMP | A: prev = EXTEND | B: prev on the chain |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 37 | seed 0 | 57.1% | 8.6% | 1.9% | 0.9% | 9.6% | 21.9% | 11.4% | 31.5% | 57.1% | 68.5% |
| 37 | mean over 16 seeds | 57.2% (1.0) | 7.8% (0.5) | 1.9% (0.3) | 1.0% (0.2) | 9.6% (0.0) | 22.5% (1.3) | 10.7% (0.6) | 32.1% (1.3) | 57.2% (1.0) | 67.9% (1.3) |
| ramp | seed 0 | 52.3% | 8.7% | 0.9% | 0.9% | 20.6% | 16.5% | 10.6% | 37.1% | 52.3% | 62.9% |
| ramp | mean over 16 seeds | 52.8% (1.6) | 7.4% (1.3) | 1.3% (0.6) | 0.6% (0.3) | 20.6% (0.0) | 17.3% (1.9) | 9.3% (0.9) | 37.9% (1.9) | 52.8% (1.6) | 62.1% (1.9) |
| corpus | mean over 4 seeds | 54.4% (0.3) | 7.4% (0.1) | 1.8% (0.1) | 0.8% (0.0) | 14.8% (0.0) | 20.8% (0.4) | 10.0% (0.1) | 35.6% (0.4) | 54.4% (0.3) | 64.4% (0.4) |

#### Transitions, P(mode_t | state), seed 0 for the held sets, all corpus seeds for the corpus

**37**

| state | steps | EXTEND | BT1 | BT2 | BT3+ | JUMP0 | JUMP+ |
|---|---|---|---|---|---|---|---|
| EXTEND | 795 | 71.2% | 10.9% | 2.9% | 1.1% | 2.5% | 11.3% |
| BT1 | 120 | 50.8% | 20.0% | 0.8% | 2.5% | 0.8% | 25.0% |
| BT2 | 26 | 50.0% | 23.1% | 3.8% | 3.8% | 0.0% | 19.2% |
| BT3+ | 13 | 53.8% | 23.1% | 7.7% | 0.0% | 0.0% | 15.4% |
| JUMP0 | 133 | 30.1% | 0.0% | 0.0% | 0.0% | 45.9% | 24.1% |
| JUMP+ | 305 | 47.2% | 0.0% | 0.0% | 0.0% | 4.6% | 48.2% |

**ramp**

| state | steps | EXTEND | BT1 | BT2 | BT3+ | JUMP0 | JUMP+ |
|---|---|---|---|---|---|---|---|
| EXTEND | 168 | 67.9% | 13.7% | 1.2% | 1.2% | 8.3% | 7.7% |
| BT1 | 28 | 57.1% | 10.7% | 3.6% | 3.6% | 0.0% | 25.0% |
| BT2 | 3 | 66.7% | 33.3% | 0.0% | 0.0% | 0.0% | 0.0% |
| BT3+ | 3 | 66.7% | 33.3% | 0.0% | 0.0% | 0.0% | 0.0% |
| JUMP0 | 66 | 40.9% | 0.0% | 0.0% | 0.0% | 34.8% | 24.2% |
| JUMP+ | 53 | 54.7% | 0.0% | 0.0% | 0.0% | 13.2% | 32.1% |

**corpus**

| state | steps | EXTEND | BT1 | BT2 | BT3+ | JUMP0 | JUMP+ |
|---|---|---|---|---|---|---|---|
| EXTEND | 43963 | 70.9% | 10.7% | 3.2% | 1.2% | 3.6% | 10.4% |
| BT1 | 5972 | 55.8% | 16.4% | 1.4% | 1.2% | 2.0% | 23.4% |
| BT2 | 1482 | 56.7% | 13.6% | 0.8% | 0.9% | 1.1% | 26.9% |
| BT3+ | 613 | 54.5% | 12.4% | 0.8% | 0.8% | 0.5% | 31.0% |
| JUMP0 | 11948 | 33.8% | 0.0% | 0.0% | 0.0% | 47.1% | 19.1% |
| JUMP+ | 16790 | 48.9% | 0.0% | 0.0% | 0.0% | 3.8% | 47.2% |


## Limits
- The read measures the draw distribution of `Sampler.clause`, not the best-first search's order or its visit end.
- Both sides score gold's form at the step the walk gives. Neither pays for the order, which is `walk_bits` a step. The walk is the round-0 walk of `walk.md`. A refit `theta` changes the steps and asks for a rerun.
- The pattern counts reads by place on the tower. It doesn't say which form of a class f reads. The shape is the head shape, not the body.
- The proposal's bits are a lower bound at steps with `h_joint = 0`.
- `relR4_o.pkl` holds the ramp in its train rows, so the ramp read is held out for the priors only. The corpus copy is of 21:49 on Nov 1, and the priors were fit earlier.
- `models-kr` is `7dafa0ce` plus `key_rel`. With `KEY_IDENT` unset, `key_rel` has no effect. So this bundle differs from `models-tk` by `col` in `ORDER_FREE`, its `COL_TYPE` table and `choice5_o`.
- Alpha is chosen from {0.5, 2, 8, 32, 128}. A choice at 128 is at the edge of that grid.
- The shuffles permute `prev` within a walk over the steps t >= 1 and leave START at step 0 in place.

