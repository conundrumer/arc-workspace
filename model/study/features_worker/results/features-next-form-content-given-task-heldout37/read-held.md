# Read on held: 1011 forms of 37 tasks, 1006 with census bits, 347 at 25 bits or more. 50 model reads.

## Target entropy, bits per form or read

| Target | Forms | Fit marginal | Census paid | Tier | Model | Top-1 | Top-5 | Saved, all forms | Saved, 25 bits or more |
|---|---|---|---|---|---|---|---|---|---|
| comp INIT | 240 | 3.733 | 3.724 | need | 3.654 | 0.167 | 0.679 | +0.07 (-0.01 to +0.15) | +0.09 (-0.05 to +0.24) |
| comp INIT | 240 | 3.733 | 3.724 | foundset | 3.611 | 0.275 | 0.629 | +0.12 (-0.09 to +0.31) | -0.08 (-0.29 to +0.13) |
| comp INIT | 240 | 3.733 | 3.724 | need+foundset | 3.539 | 0.279 | 0.633 | +0.19 (-0.01 to +0.39) | +0.01 (-0.22 to +0.24) |
| comp INIT | 240 | 3.733 | 3.724 | all | 3.162 | 0.408 | 0.742 | +0.56 (+0.34 to +0.79) | +0.26 (-0.04 to +0.54) |
| comp INIT | | | | shuffled | | | | +0.00 (-0.01 to +0.01) | +0.00 (-0.01 to +0.01) |
| comp DET | 116 | 2.477 | 2.467 | need | 2.120 | 0.629 | 0.845 | +0.35 (+0.15 to +0.52) | +0.73 (+0.55 to +0.85) |
| comp DET | 116 | 2.477 | 2.467 | foundset | 2.220 | 0.621 | 0.845 | +0.25 (-0.05 to +0.50) | +0.98 (+0.87 to +1.05) |
| comp DET | 116 | 2.477 | 2.467 | need+foundset | 2.162 | 0.621 | 0.845 | +0.30 (-0.01 to +0.58) | +1.08 (+0.99 to +1.15) |
| comp DET | 116 | 2.477 | 2.467 | all | 1.959 | 0.629 | 0.853 | +0.51 (+0.29 to +0.72) | +1.14 (+1.07 to +1.20) |
| comp DET | | | | shuffled | | | | +0.00 (+0.00 to +0.00) | +0.00 (+0.00 to +0.00) |
| geom | 1008 | 3.251 |  | need | 3.210 | 0.373 | 0.705 | +0.04 (-0.03 to +0.11) | +0.04 (-0.05 to +0.12) |
| geom | 1008 | 3.251 |  | foundset | 3.127 | 0.381 | 0.737 | +0.12 (+0.03 to +0.22) | +0.07 (-0.10 to +0.23) |
| geom | 1008 | 3.251 |  | need+foundset | 3.101 | 0.403 | 0.745 | +0.15 (+0.03 to +0.27) | +0.09 (-0.10 to +0.29) |
| geom | 1008 | 3.251 |  | all | 2.554 | 0.532 | 0.845 | +0.70 (+0.50 to +0.88) | +0.47 (+0.27 to +0.67) |
| geom | | | | shuffled | | | | +0.00 (+0.00 to +0.00) | +0.00 (+0.00 to +0.00) |
| rel | 1008 | 2.560 |  | need | 2.530 | 0.452 | 0.867 | +0.03 (+0.00 to +0.06) | +0.01 (-0.04 to +0.05) |
| rel | 1008 | 2.560 |  | foundset | 2.539 | 0.444 | 0.868 | +0.02 (-0.04 to +0.09) | +0.10 (+0.04 to +0.18) |
| rel | 1008 | 2.560 |  | need+foundset | 2.523 | 0.446 | 0.872 | +0.04 (-0.03 to +0.11) | +0.11 (+0.03 to +0.20) |
| rel | 1008 | 2.560 |  | all | 2.154 | 0.503 | 0.927 | +0.41 (+0.29 to +0.55) | +0.44 (+0.20 to +0.70) |
| rel | | | | shuffled | | | | -0.00 (-0.00 to +0.00) | +0.00 (-0.00 to +0.00) |
| coarse cols | 1008 | 5.490 |  | need | 5.498 | 0.134 | 0.419 | -0.01 (-0.03 to +0.01) | -0.01 (-0.03 to +0.02) |
| coarse cols | 1008 | 5.490 |  | foundset | 4.900 | 0.156 | 0.526 | +0.59 (+0.40 to +0.77) | +0.31 (+0.07 to +0.52) |
| coarse cols | 1008 | 5.490 |  | need+foundset | 4.908 | 0.156 | 0.527 | +0.58 (+0.39 to +0.77) | +0.30 (+0.06 to +0.52) |
| coarse cols | 1008 | 5.490 |  | all | 4.024 | 0.324 | 0.689 | +1.47 (+1.22 to +1.70) | +0.69 (+0.41 to +0.96) |
| coarse cols | | | | shuffled | | | | +0.00 (+0.00 to +0.00) | +0.00 (+0.00 to +0.00) |
| cols | 1008 | 5.387 |  | need | 5.386 | 0.133 | 0.475 | +0.00 (-0.01 to +0.01) | +0.00 (-0.01 to +0.02) |
| cols | 1008 | 5.387 |  | foundset | 4.911 | 0.231 | 0.532 | +0.47 (+0.32 to +0.63) | +0.25 (+0.06 to +0.41) |
| cols | 1008 | 5.387 |  | need+foundset | 4.913 | 0.231 | 0.541 | +0.47 (+0.31 to +0.63) | +0.25 (+0.05 to +0.41) |
| cols | 1008 | 5.387 |  | all | 4.216 | 0.332 | 0.660 | +1.17 (+0.95 to +1.38) | +0.44 (+0.19 to +0.67) |
| cols | | | | shuffled | | | | +0.00 (+0.00 to +0.00) | +0.00 (+0.00 to +0.00) |
| shape | 1008 | 5.033 |  | need | 5.024 | 0.155 | 0.441 | +0.01 (-0.02 to +0.03) | -0.01 (-0.06 to +0.04) |
| shape | 1008 | 5.033 |  | foundset | 4.946 | 0.178 | 0.462 | +0.09 (+0.01 to +0.16) | +0.02 (-0.14 to +0.17) |
| shape | 1008 | 5.033 |  | need+foundset | 4.943 | 0.181 | 0.462 | +0.09 (+0.00 to +0.18) | +0.01 (-0.18 to +0.18) |
| shape | 1008 | 5.033 |  | all | 4.327 | 0.305 | 0.589 | +0.71 (+0.55 to +0.86) | +0.50 (+0.20 to +0.81) |
| shape | | | | shuffled | | | | +0.00 (+0.00 to +0.00) | +0.00 (+0.00 to +0.00) |
| content | 1008 | 4.881 |  | need | 4.871 | 0.435 | 0.552 | +0.01 (-0.01 to +0.03) | +0.06 (+0.03 to +0.09) |
| content | 1008 | 4.881 |  | foundset | 4.561 | 0.431 | 0.576 | +0.32 (+0.25 to +0.39) | +0.25 (+0.14 to +0.35) |
| content | 1008 | 4.881 |  | need+foundset | 4.561 | 0.431 | 0.578 | +0.32 (+0.25 to +0.39) | +0.29 (+0.17 to +0.41) |
| content | 1008 | 4.881 |  | all | 3.991 | 0.473 | 0.679 | +0.89 (+0.71 to +1.09) | +0.67 (+0.45 to +0.89) |
| content | | | | shuffled | | | | +0.00 (+0.00 to +0.00) | +0.00 (+0.00 to +0.00) |

Saved is against the census part for the two component rows and against the fit marginal for the rest.

## Read sets

| Target | Reads | Tier | Marginal per read | Model per read | Top-1 | Top-5 | Bag saved per form, 25 bits or more | Gamma | Paid on relation picks | Tilt saved, all forms | Tilt saved, 25 bits or more |
|---|---|---|---|---|---|---|---|---|---|---|---|
| reads RULE DET | 1834 | need | 4.513 | 4.510 | 0.115 | 0.490 | +0.04 (+0.00 to +0.10) | 1.0 | 13.52 | +0.01 (-0.01 to +0.03) | +0.06 (+0.01 to +0.11) |
| reads RULE DET | 1834 | foundset | 4.513 | 4.394 | 0.135 | 0.507 | +0.23 (-0.01 to +0.47) | 0.6 | 13.52 | +0.10 (+0.04 to +0.15) | +0.09 (-0.02 to +0.21) |
| reads RULE DET | 1834 | need+foundset | 4.513 | 4.393 | 0.141 | 0.511 | +0.28 (+0.01 to +0.53) | 0.6 | 13.52 | +0.11 (+0.05 to +0.17) | +0.13 (+0.01 to +0.25) |
| reads RULE DET | 1834 | all | 4.513 | 3.994 | 0.279 | 0.602 | +0.26 (-0.16 to +0.64) | 0.8 | 13.52 | +0.66 (+0.47 to +0.82) | +0.00 (-0.36 to +0.36) |
| reads RULE DET | 1834 | control | 4.513 | 4.513 | 0.110 | 0.488 | +0.00 (+0.00 to +0.00) | 0.6 | 13.52 | -0.00 (-0.00 to -0.00) | -0.00 (-0.00 to -0.00) |
| reads INIT | 589 | need | 4.275 | 4.269 | 0.178 | 0.520 | -0.03 (-0.23 to +0.14) | 0.5 | 25.66 | +0.03 (-0.08 to +0.13) | -0.01 (-0.19 to +0.19) |
| reads INIT | 589 | foundset | 4.275 | 4.084 | 0.202 | 0.581 | +0.41 (+0.17 to +0.67) | 0.6 | 25.66 | +0.23 (+0.01 to +0.47) | +0.13 (-0.22 to +0.51) |
| reads INIT | 589 | need+foundset | 4.275 | 4.091 | 0.200 | 0.576 | +0.38 (+0.12 to +0.65) | 0.6 | 25.66 | +0.22 (-0.01 to +0.46) | +0.10 (-0.27 to +0.48) |
| reads INIT | 589 | all | 4.275 | 3.898 | 0.273 | 0.591 | +0.71 (+0.25 to +1.24) | 1.0 | 25.66 | +0.61 (-0.11 to +1.41) | +0.09 (-1.05 to +1.38) |
| reads INIT | 589 | control | 4.275 | 4.275 | 0.158 | 0.508 | -0.00 (-0.00 to +0.00) | 0.6 | 25.66 | -0.00 (-0.00 to +0.00) | -0.00 (-0.00 to +0.00) |

## Component and relation picks on one census walk

| Tier | Saved, all forms | Saved, 25 bits or more | Forms over 25 | Taken under 25 | Tasks under 25, before | After |
|---|---|---|---|---|---|---|
| need | +0.07 (+0.02 to +0.11) | +0.13 (-0.01 to +0.26) | 347 | 2 | 0 | 0 |
| foundset | +0.19 (+0.07 to +0.30) | +0.15 (-0.04 to +0.36) | 347 | 6 | 0 | 0 |
| need+foundset | +0.21 (+0.10 to +0.33) | +0.20 (-0.01 to +0.43) | 347 | 8 | 0 | 0 |
| all | +0.84 (+0.56 to +1.12) | +0.23 (-0.32 to +0.88) | 347 | 14 | 0 | 0 |
| shuffled, tilt only | -0.00 (-0.00 to +0.00) | -0.00 (-0.00 to +0.00) | | | | |

## Share of the saving at forms of 25 bits or more

- t1 census unit: need facts alone 0.127, found set alone 0.150, both 0.201; need facts add 0.254 of both.
- content: need facts alone 0.059, found set alone 0.252, both 0.295; need facts add 0.146 of both.

## Pool gap: log2 of gold's marginal over the pool's share, in the kind

- coarse cols: all forms +2.05 (+1.45 to +2.70), 25 bits or more +3.22 (+1.92 to +4.51).
- geom: all forms +0.60 (+0.34 to +0.92), 25 bits or more +0.99 (+0.33 to +1.78).
- rel: all forms +0.67 (+0.41 to +1.00), 25 bits or more +1.20 (+0.61 to +1.91).

## Cost per state and rows by gold source

- {"need_ms_median": 0.591, "need_ms_max": 2.748, "table_facts_ms_median": 0.452, "table_facts_ms_max": 494.52, "bucket_ms_mean": 0.053}
- T1 saved at 25 bits or more, need and found set, by source of the text: {"census:cover": [0.34, -0.206, 0.938, 85, 10], "census:helper": [0.318, 0.076, 0.541, 138, 15], "census:round 50": [-0.025, -0.34, 0.398, 124, 12]}
