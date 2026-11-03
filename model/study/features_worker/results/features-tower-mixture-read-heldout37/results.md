# Tower mixture read, held-out 37

Design: `/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-tower-mixture-read-heldout37/design.md`. Tower read: `/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-tower-read-heldout37-ramp22`.

## Data check

- Steps used: 1429 of the seed-0 walks of 37 tasks; left out: none.
- Steps with an unseen gold shape: 1. Steps with h_joint = 0: 265.
- Largest distance from 1 of the sum of the shape factor (all models) or the pattern factor (M2A, all 216 patterns): 7.1e-15.
- Largest difference of the refit tower models from `TW/tower/`: 0.00005 bits.
- Mode model fit on 84724 corpus rows of 989 stems; none in eval-tasks.txt, the ramp or the 37.

## Table 1, bits per form, the 37

Saving = proposal bits minus the row's bits. Weighted mean over the done steps of the seed-0 walk, interval by task (2,000 draws), as Table 1 of the tower read. Mixture: pi from the mode model. Oracle: pi = 1 where gold's mode is EXTEND, else 0. The tower model under EXTEND is the named model restricted to EXTEND patterns and renormalised.

| row | bits mean | saving against the proposal | saving, steps with h_joint >= 1 |
|---|---|---|---|
| proposal | 5.85 | - | - |
| mixture, M2A | 5.51 | 0.34 [0.21, 0.46] | 0.25 [0.13, 0.37] |
| oracle, M2A | 5.07 | 0.78 [0.56, 0.95] | 0.77 [0.64, 0.89] |
| M2A alone (unrestricted, for reference) | 5.77 | 0.08 [-0.25, 0.39] | - |
| mixture, M0 | 5.66 | 0.18 [0.08, 0.28] | 0.11 [0.02, 0.20] |
| oracle, M0 | 5.21 | 0.64 [0.44, 0.80] | 0.60 [0.48, 0.71] |
| M0 alone (unrestricted, for reference) | 5.89 | -0.04 [-0.34, 0.24] | - |
| mixture, M1 | 5.52 | 0.33 [0.21, 0.46] | 0.25 [0.13, 0.36] |
| oracle, M1 | 5.04 | 0.81 [0.60, 0.97] | 0.77 [0.65, 0.89] |
| M1 alone (unrestricted, for reference) | 5.71 | 0.14 [-0.16, 0.41] | - |
| mixture, M2B | 5.50 | 0.34 [0.22, 0.47] | 0.26 [0.14, 0.37] |
| oracle, M2B | 5.02 | 0.83 [0.62, 1.00] | 0.79 [0.67, 0.91] |
| M2B alone (unrestricted, for reference) | 5.62 | 0.23 [-0.08, 0.51] | - |
| mixture, M2M | 5.50 | 0.34 [0.22, 0.47] | 0.26 [0.14, 0.37] |
| oracle, M2M | 5.01 | 0.84 [0.65, 1.00] | 0.80 [0.68, 0.91] |
| M2M alone (unrestricted, for reference) | 5.62 | 0.23 [-0.06, 0.49] | - |
| mixture, M3 | 5.50 | 0.35 [0.23, 0.46] | 0.28 [0.16, 0.39] |
| oracle, M3 | 5.01 | 0.84 [0.65, 0.99] | 0.82 [0.70, 0.93] |
| M3 alone (unrestricted, for reference) | 5.58 | 0.27 [-0.06, 0.56] | - |

## Table 2, by gold's mode, M2A

| gold's mode | steps | proposal bits | mean pi | saving of the mixture | saving of the oracle |
|---|---|---|---|---|---|
| EXTEND | 831 | 5.83 | 0.66 | 1.41 [1.23, 1.58] | 1.35 [0.97, 1.66] |
| BACKTRACK | 159 | 7.88 | 0.69 | -1.78 [-1.88, -1.69] | 0.00 [0.00, 0.00] |
| JUMP | 439 | 5.16 | 0.44 | -0.94 [-1.00, -0.88] | 0.00 [0.00, 0.00] |

## Table 3, the mode model

Target: gold's mode is EXTEND. Log loss in bits per step. The constant reference is pi = the corpus EXTEND share over steps t >= 1 (0.593), and 0 at step 0.

| set | steps | log loss, mode model | log loss, constant |
|---|---|---|---|
| corpus, 5-fold CV (alpha 128) | 84724 | 0.8441 | 0.9293 |
| the 37, the 1429 read steps (seed 0, weighted) | 1429 | 0.8576 | 0.9475 |
| the 37, all steps of seeds 0 to 15 | 22864 | 0.8533 | 0.9466 |

Calibration on the read steps (raw counts):

| pi | steps | mean pi | EXTEND share |
|---|---|---|---|
| 0.0-0.1 | 37 | 0.000 | 0.000 |
| 0.1-0.2 | 26 | 0.139 | 0.077 |
| 0.2-0.3 | 26 | 0.267 | 0.231 |
| 0.3-0.4 | 66 | 0.367 | 0.288 |
| 0.4-0.5 | 250 | 0.447 | 0.436 |
| 0.5-0.6 | 295 | 0.545 | 0.546 |
| 0.6-0.7 | 187 | 0.646 | 0.620 |
| 0.7-0.8 | 376 | 0.758 | 0.742 |
| 0.8-0.9 | 166 | 0.838 | 0.837 |

## Verdict

- The mixture with M2A saves 0.34 [0.21, 0.46] bits per form against the proposal on the 37 (interval above 0). The oracle mode gives 0.78 [0.56, 0.95].

## Limits
- The read measures draw distributions at gold's step in the round-0 walk, not the search's order. Neither side pays the walk's own choice bits.
- The proposal's bits are a lower bound at steps with h_joint = 0, so the saving there is a lower bound.
- The proposal part of the mixture is the plain proposal, with its mass on EXTEND outcomes. Its draws are of gold's kind only, so these records can't restrict it to non-EXTEND outcomes.
- The oracle is pi from a perfect mode model, not the best pi at each step.
- The mode model's alpha is chosen from {0.5, 2, 8, 32, 128}. Its CV log loss by alpha: 0.5: 0.8823, 2: 0.8611, 8: 0.8493, 32: 0.8442, 128: 0.8441.
