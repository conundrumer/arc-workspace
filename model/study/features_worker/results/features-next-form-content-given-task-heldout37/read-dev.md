# Read on dev: 1535 forms of 62 tasks, 1519 with census bits, 390 at 25 bits or more. 50 model reads.

## Target entropy, bits per form or read

| Target | Forms | Fit marginal | Census paid | Tier | Model | Top-1 | Top-5 | Saved, all forms | Saved, 25 bits or more |
|---|---|---|---|---|---|---|---|---|---|
| comp INIT | 387 | 3.647 | 3.637 | need | 3.632 | 0.160 | 0.724 | +0.02 (-0.06 to +0.09) | -0.02 (-0.14 to +0.10) |
| comp INIT | 387 | 3.647 | 3.637 | foundset | 3.453 | 0.289 | 0.695 | +0.18 (+0.07 to +0.29) | +0.02 (-0.12 to +0.16) |
| comp INIT | 387 | 3.647 | 3.637 | need+foundset | 3.438 | 0.289 | 0.711 | +0.21 (+0.09 to +0.33) | +0.02 (-0.14 to +0.18) |
| comp INIT | 387 | 3.647 | 3.637 | all | 3.008 | 0.382 | 0.757 | +0.65 (+0.49 to +0.81) | +0.38 (+0.18 to +0.58) |
| comp INIT | | | | shuffled | | | | +0.00 (+0.00 to +0.00) | +0.00 (+0.00 to +0.00) |
| comp DET | 174 | 3.584 | 3.622 | need | 3.212 | 0.420 | 0.741 | +0.41 (+0.20 to +0.59) | +0.46 (-0.35 to +0.67) |
| comp DET | 174 | 3.584 | 3.622 | foundset | 3.297 | 0.425 | 0.695 | +0.33 (+0.15 to +0.48) | +0.87 (+0.28 to +1.06) |
| comp DET | 174 | 3.584 | 3.622 | need+foundset | 3.115 | 0.460 | 0.730 | +0.51 (+0.28 to +0.72) | +0.89 (+0.08 to +1.12) |
| comp DET | 174 | 3.584 | 3.622 | all | 2.902 | 0.466 | 0.701 | +0.72 (+0.52 to +0.91) | +0.93 (+0.45 to +1.15) |
| comp DET | | | | shuffled | | | | -0.00 (-0.00 to +0.00) | +0.00 (+0.00 to +0.00) |
| geom | 1534 | 2.941 |  | need | 2.835 | 0.420 | 0.774 | +0.11 (+0.06 to +0.15) | +0.07 (-0.01 to +0.15) |
| geom | 1534 | 2.941 |  | foundset | 2.713 | 0.428 | 0.812 | +0.23 (+0.15 to +0.31) | +0.20 (+0.04 to +0.38) |
| geom | 1534 | 2.941 |  | need+foundset | 2.647 | 0.441 | 0.821 | +0.29 (+0.21 to +0.38) | +0.24 (+0.05 to +0.43) |
| geom | 1534 | 2.941 |  | all | 2.225 | 0.578 | 0.876 | +0.72 (+0.60 to +0.85) | +0.44 (+0.22 to +0.68) |
| geom | | | | shuffled | | | | +0.00 (-0.00 to +0.00) | +0.00 (-0.00 to +0.00) |
| rel | 1534 | 2.350 |  | need | 2.332 | 0.527 | 0.849 | +0.02 (-0.02 to +0.06) | +0.01 (-0.05 to +0.07) |
| rel | 1534 | 2.350 |  | foundset | 2.235 | 0.519 | 0.877 | +0.12 (+0.06 to +0.18) | +0.15 (+0.04 to +0.29) |
| rel | 1534 | 2.350 |  | need+foundset | 2.228 | 0.523 | 0.874 | +0.12 (+0.06 to +0.20) | +0.14 (+0.03 to +0.31) |
| rel | 1534 | 2.350 |  | all | 1.942 | 0.568 | 0.924 | +0.41 (+0.33 to +0.50) | +0.25 (+0.10 to +0.44) |
| rel | | | | shuffled | | | | +0.00 (+0.00 to +0.00) | +0.00 (+0.00 to +0.00) |
| coarse cols | 1534 | 5.439 |  | need | 5.436 | 0.168 | 0.450 | +0.00 (-0.01 to +0.02) | +0.02 (-0.01 to +0.05) |
| coarse cols | 1534 | 5.439 |  | foundset | 4.816 | 0.194 | 0.533 | +0.63 (+0.51 to +0.75) | +0.46 (+0.31 to +0.61) |
| coarse cols | 1534 | 5.439 |  | need+foundset | 4.814 | 0.191 | 0.538 | +0.63 (+0.51 to +0.76) | +0.47 (+0.33 to +0.63) |
| coarse cols | 1534 | 5.439 |  | all | 4.026 | 0.329 | 0.671 | +1.42 (+1.25 to +1.61) | +0.70 (+0.49 to +0.93) |
| coarse cols | | | | shuffled | | | | +0.00 (+0.00 to +0.00) | +0.00 (+0.00 to +0.00) |
| cols | 1534 | 5.693 |  | need | 5.683 | 0.154 | 0.437 | +0.01 (-0.00 to +0.02) | +0.02 (-0.01 to +0.04) |
| cols | 1534 | 5.693 |  | foundset | 5.198 | 0.212 | 0.493 | +0.50 (+0.40 to +0.59) | +0.31 (+0.18 to +0.43) |
| cols | 1534 | 5.693 |  | need+foundset | 5.193 | 0.217 | 0.490 | +0.50 (+0.40 to +0.60) | +0.32 (+0.18 to +0.45) |
| cols | 1534 | 5.693 |  | all | 4.506 | 0.317 | 0.615 | +1.20 (+1.04 to +1.37) | +0.56 (+0.35 to +0.77) |
| cols | | | | shuffled | | | | +0.00 (+0.00 to +0.00) | +0.00 (+0.00 to +0.00) |
| shape | 1534 | 4.656 |  | need | 4.629 | 0.196 | 0.497 | +0.03 (+0.01 to +0.05) | -0.01 (-0.06 to +0.04) |
| shape | 1534 | 4.656 |  | foundset | 4.478 | 0.235 | 0.516 | +0.18 (+0.13 to +0.23) | +0.09 (+0.01 to +0.19) |
| shape | 1534 | 4.656 |  | need+foundset | 4.461 | 0.237 | 0.522 | +0.20 (+0.14 to +0.25) | +0.08 (-0.03 to +0.19) |
| shape | 1534 | 4.656 |  | all | 3.849 | 0.368 | 0.660 | +0.81 (+0.69 to +0.93) | +0.34 (+0.11 to +0.59) |
| shape | | | | shuffled | | | | +0.00 (+0.00 to +0.00) | +0.00 (+0.00 to +0.00) |
| content | 1534 | 5.272 |  | need | 5.249 | 0.357 | 0.499 | +0.02 (+0.01 to +0.04) | +0.07 (+0.04 to +0.10) |
| content | 1534 | 5.272 |  | foundset | 4.953 | 0.367 | 0.521 | +0.32 (+0.26 to +0.38) | +0.29 (+0.22 to +0.35) |
| content | 1534 | 5.272 |  | need+foundset | 4.936 | 0.367 | 0.517 | +0.34 (+0.27 to +0.40) | +0.34 (+0.27 to +0.40) |
| content | 1534 | 5.272 |  | all | 4.292 | 0.392 | 0.639 | +0.98 (+0.83 to +1.15) | +0.60 (+0.47 to +0.72) |
| content | | | | shuffled | | | | +0.00 (+0.00 to +0.00) | +0.00 (+0.00 to +0.00) |

Saved is against the census part for the two component rows and against the fit marginal for the rest.

## Read sets

| Target | Reads | Tier | Marginal per read | Model per read | Top-1 | Top-5 | Bag saved per form, 25 bits or more | Gamma | Paid on relation picks | Tilt saved, all forms | Tilt saved, 25 bits or more |
|---|---|---|---|---|---|---|---|---|---|---|---|
| reads RULE DET | 2634 | need | 4.583 | 4.576 | 0.105 | 0.454 | +0.06 (-0.03 to +0.14) | 1.0 | 11.55 | +0.03 (+0.02 to +0.04) | +0.11 (+0.03 to +0.18) |
| reads RULE DET | 2634 | foundset | 4.583 | 4.440 | 0.138 | 0.481 | +0.22 (+0.02 to +0.43) | 0.6 | 11.55 | +0.13 (+0.07 to +0.17) | +0.01 (-0.15 to +0.16) |
| reads RULE DET | 2634 | need+foundset | 4.583 | 4.434 | 0.143 | 0.478 | +0.27 (+0.04 to +0.51) | 0.6 | 11.55 | +0.14 (+0.09 to +0.19) | +0.07 (-0.09 to +0.23) |
| reads RULE DET | 2634 | all | 4.583 | 3.977 | 0.282 | 0.601 | +0.85 (+0.46 to +1.26) | 0.8 | 11.55 | +0.76 (+0.63 to +0.90) | +0.51 (+0.23 to +0.81) |
| reads RULE DET | 2634 | control | 4.583 | 4.583 | 0.092 | 0.450 | +0.00 (+0.00 to +0.00) | 0.6 | 11.55 | -0.00 (-0.00 to -0.00) | -0.00 (-0.00 to -0.00) |
| reads INIT | 910 | need | 4.160 | 4.122 | 0.190 | 0.560 | +0.13 (+0.00 to +0.26) | 0.5 | 22.31 | +0.07 (-0.01 to +0.14) | +0.09 (-0.03 to +0.21) |
| reads INIT | 910 | foundset | 4.160 | 3.921 | 0.227 | 0.602 | +0.66 (+0.41 to +0.89) | 0.6 | 22.31 | +0.30 (+0.12 to +0.49) | +0.29 (-0.00 to +0.63) |
| reads INIT | 910 | need+foundset | 4.160 | 3.913 | 0.224 | 0.602 | +0.69 (+0.44 to +0.94) | 0.6 | 22.31 | +0.32 (+0.12 to +0.53) | +0.32 (-0.00 to +0.69) |
| reads INIT | 910 | all | 4.160 | 3.657 | 0.324 | 0.642 | +1.37 (+1.01 to +1.70) | 1.0 | 22.31 | +1.35 (+0.88 to +1.84) | +1.64 (+0.84 to +2.55) |
| reads INIT | 910 | control | 4.160 | 4.160 | 0.182 | 0.535 | -0.00 (-0.00 to +0.00) | 0.6 | 22.31 | +0.00 (-0.00 to +0.00) | -0.00 (-0.00 to +0.00) |

## Component and relation picks on one census walk

| Tier | Saved, all forms | Saved, 25 bits or more | Forms over 25 | Taken under 25 | Tasks under 25, before | After |
|---|---|---|---|---|---|---|
| need | +0.09 (+0.05 to +0.13) | +0.10 (-0.02 to +0.22) | 390 | 6 | 0 | 0 |
| foundset | +0.25 (+0.17 to +0.34) | +0.21 (+0.01 to +0.42) | 390 | 8 | 0 | 0 |
| need+foundset | +0.29 (+0.21 to +0.38) | +0.26 (+0.04 to +0.49) | 390 | 9 | 0 | 0 |
| all | +1.16 (+0.95 to +1.37) | +1.37 (+0.88 to +1.92) | 390 | 18 | 0 | 0 |
| shuffled, tilt only | -0.00 (-0.00 to +0.00) | -0.00 (-0.00 to +0.00) | | | | |

## Share of the saving at forms of 25 bits or more

- t1 census unit: need facts alone 0.105, found set alone 0.211, both 0.255; need facts add 0.173 of both.
- content: need facts alone 0.067, found set alone 0.286, both 0.338; need facts add 0.154 of both.

## Pool gap: log2 of gold's marginal over the pool's share, in the kind

- coarse cols: all forms +1.94 (+1.63 to +2.26), 25 bits or more +2.82 (+2.21 to +3.43).
- geom: all forms +0.31 (+0.17 to +0.46), 25 bits or more +0.25 (+0.00 to +0.52).
- rel: all forms +0.53 (+0.40 to +0.66), 25 bits or more +0.54 (+0.24 to +0.80).

## Cost per state and rows by gold source

- {"need_ms_median": 0.539, "need_ms_max": 8.753, "table_facts_ms_median": 0.646, "table_facts_ms_max": 393.997, "bucket_ms_mean": 0.047}
- T1 saved at 25 bits or more, need and found set, by source of the text: {"census:helper": [0.271, 0.023, 0.531, 345, 54], "census:round 50": [0.128, -0.209, 0.525, 45, 8]}
