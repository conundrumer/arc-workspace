# Per-relation models on pool scopes, valid orders

Saved bits per gold-alive pick over `off` and over `live`, 95% by task. `held-wide` is an oracle context. No written-order row: every walk stands in a valid order.

| Model | held-pool, over off | held-wide, over off | held-parents, over off | held-pool, over live | held-wide, over live | held-parents, over live | Verdict (held-pool, over live) |
|---|---|---|---|---|---|---|---|
| parents (item 10 model) | +1.20 (+0.95 to +1.44) | +1.41 (+1.25 to +1.57) | +1.71 (+1.54 to +1.88) | +0.02 (-0.25 to +0.26) | -0.48 (-0.61 to -0.34) | -0.07 (-0.18 to +0.04) | closes |
| control of parents (item 10 model) | -0.00 (-0.01 to +0.00) | -0.00 (-0.01 to -0.00) | -0.01 (-0.01 to -0.00) | -1.19 (-1.50 to -0.90) | -1.89 (-2.01 to -1.78) | -1.79 (-1.92 to -1.65) |  |
| pool | +1.37 (+1.11 to +1.60) | +1.19 (+1.00 to +1.39) | not read | +0.18 (-0.16 to +0.51) | -0.70 (-0.88 to -0.51) | not read | closes |
| control of pool | +0.00 (-0.01 to +0.01) | -0.01 (-0.01 to -0.00) | not read | -1.18 (-1.50 to -0.90) | -1.90 (-2.02 to -1.78) | not read |  |
| union | +1.40 (+1.10 to +1.68) | +1.47 (+1.32 to +1.63) | +1.71 (+1.55 to +1.88) | +0.22 (-0.05 to +0.48) | -0.42 (-0.55 to -0.28) | -0.07 (-0.18 to +0.05) | closes |
| control of union | +0.01 (+0.00 to +0.01) | -0.00 (-0.01 to +0.00) | -0.00 (-0.01 to +0.00) | -1.18 (-1.49 to -0.89) | -1.89 (-2.01 to -1.77) | -1.78 (-1.92 to -1.64) |  |

## held-pool: by class and d_depth band

| Picks read | parents (item 10 model), off | parents (item 10 model), live | pool, off | pool, live | union, off | union, live |
|---|---|---|---|---|---|---|
| Derived relation in scope | +1.29 (+0.87 to +1.70) | +0.06 (-0.21 to +0.38) | +1.16 (+0.53 to +1.74) | -0.07 (-0.58 to +0.44) | +1.26 (+0.77 to +1.75) | +0.03 (-0.35 to +0.46) |
| Lib relation | +0.36 (-0.10 to +0.84) | -0.44 (-1.13 to +0.18) | +0.62 (+0.17 to +1.13) | -0.18 (-0.74 to +0.37) | +0.53 (+0.00 to +1.09) | -0.27 (-0.95 to +0.36) |
| The form's own earlier atom | +0.10 (-1.33 to +1.16) | -1.62 (-2.67 to -0.85) | +0.54 (-0.77 to +1.50) | -1.18 (-2.12 to -0.49) | +0.42 (-0.94 to +1.42) | -1.30 (-2.28 to -0.59) |
| The rest | +1.79 (+1.51 to +2.04) | +0.56 (+0.36 to +0.79) | +2.04 (+1.72 to +2.36) | +0.81 (+0.25 to +1.26) | +2.12 (+1.84 to +2.35) | +0.90 (+0.66 to +1.15) |
| D empty (band 0) | +0.89 (+0.70 to +1.05) | +0.31 (+0.11 to +0.52) | +1.17 (+0.96 to +1.40) | +0.59 (+0.31 to +0.89) | +1.09 (+0.90 to +1.29) | +0.51 (+0.27 to +0.78) |
| band 1 | +1.31 (+1.02 to +1.56) | -0.17 (-0.60 to +0.21) | +1.52 (+1.13 to +1.85) | +0.04 (-0.38 to +0.41) | +1.51 (+1.18 to +1.81) | +0.03 (-0.39 to +0.40) |
| band 2 | +1.84 (+0.67 to +2.52) | -0.30 (-0.91 to +0.21) | +1.48 (+0.94 to +2.04) | -0.67 (-1.24 to +0.24) | +2.02 (+0.82 to +2.66) | -0.13 (-0.75 to +0.33) |
| band 3 or more | +1.68 (+1.68 to +1.68) | +1.55 (+1.55 to +1.55) | +1.33 (+1.33 to +1.33) | +1.20 (+1.20 to +1.20) | +1.57 (+1.57 to +1.57) | +1.45 (+1.45 to +1.45) |

held-pool: by stratum (gold-alive picks)

| Model | Stratum | Picks | Tasks | Over off | Over live |
|---|---|---|---|---|---|
| parents (item 10 model) | holds | 692 | 16 | +1.56 (+1.13 to +1.95) | +0.28 (-0.02 to +0.54) |
| parents (item 10 model) | built | 594 | 20 | +1.33 (+0.91 to +1.79) | -0.11 (-0.30 to +0.12) |
| parents (item 10 model) | noreads | 500 | 24 | +0.68 (+0.40 to +0.97) | -0.15 (-0.86 to +0.48) |
| pool | holds | 692 | 16 | +1.61 (+1.09 to +2.02) | +0.33 (-0.20 to +0.76) |
| pool | built | 594 | 20 | +1.36 (+0.98 to +1.81) | -0.07 (-0.45 to +0.38) |
| pool | noreads | 500 | 24 | +1.10 (+0.86 to +1.35) | +0.27 (-0.38 to +0.84) |
| union | holds | 692 | 16 | +1.76 (+1.20 to +2.22) | +0.48 (+0.09 to +0.80) |
| union | built | 594 | 20 | +1.45 (+1.02 to +1.93) | +0.02 (-0.25 to +0.32) |
| union | noreads | 500 | 24 | +0.95 (+0.69 to +1.23) | +0.12 (-0.57 to +0.73) |

## held-wide: by class and d_depth band

| Picks read | parents (item 10 model), off | parents (item 10 model), live | pool, off | pool, live | union, off | union, live |
|---|---|---|---|---|---|---|
| Derived relation in scope | +2.14 (+2.00 to +2.28) | -0.39 (-0.48 to -0.28) | +2.21 (+2.06 to +2.36) | -0.31 (-0.43 to -0.18) | +2.18 (+2.04 to +2.31) | -0.35 (-0.44 to -0.24) |
| Lib relation | +0.71 (+0.23 to +1.13) | -0.43 (-0.82 to -0.05) | +0.26 (-0.28 to +0.75) | -0.88 (-1.35 to -0.44) | +0.69 (+0.21 to +1.13) | -0.45 (-0.85 to -0.06) |
| The form's own earlier atom | +1.67 (+1.29 to +2.05) | -0.57 (-0.89 to -0.33) | +1.31 (+0.90 to +1.75) | -0.93 (-1.24 to -0.66) | +1.66 (+1.27 to +2.08) | -0.58 (-0.86 to -0.34) |
| The rest | +0.11 (-0.24 to +0.47) | -0.68 (-0.93 to -0.43) | -0.60 (-1.07 to -0.08) | -1.40 (-1.81 to -0.94) | +0.27 (-0.05 to +0.62) | -0.52 (-0.78 to -0.25) |
| D empty (band 0) | +1.71 (+1.56 to +1.86) | -0.58 (-0.71 to -0.44) | +1.79 (+1.61 to +1.96) | -0.50 (-0.63 to -0.36) | +1.81 (+1.66 to +1.96) | -0.47 (-0.59 to -0.34) |
| band 1 | +1.20 (+1.01 to +1.39) | -0.46 (-0.61 to -0.29) | +0.89 (+0.65 to +1.13) | -0.77 (-0.99 to -0.53) | +1.25 (+1.07 to +1.44) | -0.40 (-0.55 to -0.24) |
| band 2 | +1.41 (+1.04 to +1.86) | -0.29 (-0.49 to -0.05) | +0.67 (+0.04 to +1.37) | -1.03 (-1.47 to -0.55) | +1.38 (+1.03 to +1.81) | -0.32 (-0.53 to -0.08) |
| band 3 or more | +0.91 (-0.28 to +2.10) | -0.36 (-1.03 to +0.18) | +0.28 (-1.69 to +2.12) | -0.98 (-2.80 to +0.30) | +0.96 (-0.15 to +2.06) | -0.31 (-1.18 to +0.36) |

held-wide: by stratum (gold-alive picks)

| Model | Stratum | Picks | Tasks | Over off | Over live |
|---|---|---|---|---|---|
| parents (item 10 model) | found | 355 | 31 | +1.15 (+0.87 to +1.41) | -0.03 (-0.29 to +0.21) |
| parents (item 10 model) | oracle | 4080 | 37 | +1.43 (+1.26 to +1.61) | -0.52 (-0.65 to -0.39) |
| pool | found | 355 | 31 | +1.36 (+1.08 to +1.61) | +0.19 (-0.13 to +0.51) |
| pool | oracle | 4080 | 37 | +1.17 (+0.96 to +1.39) | -0.79 (-0.97 to -0.59) |
| union | found | 355 | 31 | +1.36 (+1.03 to +1.66) | +0.18 (-0.08 to +0.44) |
| union | oracle | 4080 | 37 | +1.48 (+1.32 to +1.66) | -0.47 (-0.61 to -0.34) |

## held-parents: by class and d_depth band

| Picks read | parents (item 10 model), off | parents (item 10 model), live | pool, off | pool, live | union, off | union, live |
|---|---|---|---|---|---|---|
| Derived relation in scope | +1.85 (+1.64 to +2.02) | -0.01 (-0.11 to +0.09) | not read | not read | +1.82 (+1.63 to +1.99) | -0.04 (-0.14 to +0.07) |
| Lib relation | +1.97 (+1.51 to +2.42) | +0.12 (-0.27 to +0.47) | not read | not read | +2.08 (+1.58 to +2.57) | +0.22 (-0.21 to +0.63) |
| The form's own earlier atom | +1.84 (+1.49 to +2.18) | -0.11 (-0.42 to +0.21) | not read | not read | +1.76 (+1.37 to +2.12) | -0.20 (-0.48 to +0.10) |
| The rest | +1.39 (+1.12 to +1.69) | -0.21 (-0.35 to -0.04) | not read | not read | +1.43 (+1.19 to +1.72) | -0.16 (-0.33 to +0.02) |
| D empty (band 0) | +1.51 (+1.33 to +1.69) | -0.24 (-0.36 to -0.11) | not read | not read | +1.52 (+1.33 to +1.70) | -0.23 (-0.35 to -0.11) |
| band 1 | +1.86 (+1.66 to +2.05) | -0.00 (-0.12 to +0.13) | not read | not read | +1.86 (+1.67 to +2.06) | +0.00 (-0.12 to +0.14) |
| band 2 | +1.62 (+1.36 to +1.93) | -0.04 (-0.21 to +0.16) | not read | not read | +1.66 (+1.43 to +1.94) | -0.00 (-0.19 to +0.22) |
| band 3 or more | +1.60 (+0.70 to +2.41) | -0.21 (-0.73 to +0.21) | not read | not read | +1.35 (+0.55 to +2.07) | -0.47 (-0.85 to -0.06) |

## Controls

{"control of parents (item 10 model)": {"reads_zero": true, "over_off": [-0.0036452484264282783, -0.00853839245192439, 4.2473607784657385e-05]}, "control of pool": {"reads_zero": true, "over_off": [0.00097814970784285, -0.007049989895827522, 0.008313246349761789]}, "control of union": {"reads_zero": false, "over_off": [0.005185607901138776, 0.00045687231810569964, 0.01089257542932418]}}

