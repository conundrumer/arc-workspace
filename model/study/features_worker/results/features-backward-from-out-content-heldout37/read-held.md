# Held read: 1011 forms of 37 tasks, 1006 with census bits, 347 at 25 bits or more, 958 primary edges. 48 content model reads and 7 candidate model reads.

## Target by depth, tier full, bits per primary edge, against the marginal on fit tasks

| Target | Depth | Rows | Baseline bits | Conditional bits | Top-1 | Top-5 |
|---|---|---|---|---|---|---|
| comp INIT | 2 | 17 | 3.628 | 2.478 | 0.529 | 0.765 |
| comp INIT | 3 | 56 | 3.683 | 2.302 | 0.607 | 0.821 |
| comp INIT | 4+ | 134 | 3.758 | 2.275 | 0.537 | 0.784 |
| comp DET | 2 | 28 | 2.583 | 2.756 | 0.179 | 0.964 |
| comp DET | 3 | 18 | 2.675 | 2.092 | 0.444 | 0.944 |
| comp DET | 4+ | 69 | 2.392 | 1.583 | 0.638 | 0.913 |
| reads INIT | 2 | 38 | 4.222 | 3.838 | 0.263 | 0.579 |
| reads INIT | 3 | 142 | 4.282 | 4.014 | 0.211 | 0.577 |
| reads INIT | 4+ | 320 | 4.489 | 3.911 | 0.219 | 0.594 |
| reads RULE DET | 1 | 144 | 4.208 | 3.803 | 0.194 | 0.604 |
| reads RULE DET | 2 | 250 | 4.490 | 4.363 | 0.136 | 0.464 |
| reads RULE DET | 3 | 232 | 4.723 | 4.473 | 0.168 | 0.453 |
| reads RULE DET | 4+ | 1171 | 4.745 | 4.384 | 0.183 | 0.553 |
| kind | 1 | 37 | 0.786 | 0.000 | 1.000 | 1.000 |
| kind | 2 | 121 | 1.333 | 0.743 | 0.843 | 1.000 |
| kind | 3 | 152 | 1.495 | 0.926 | 0.704 | 1.000 |
| kind | 4+ | 645 | 1.246 | 0.807 | 0.772 | 1.000 |
| cols | 1 | 37 | 3.772 | 2.542 | 0.568 | 0.865 |
| cols | 2 | 121 | 4.460 | 3.570 | 0.364 | 0.777 |
| cols | 3 | 152 | 5.254 | 3.341 | 0.487 | 0.796 |
| cols | 4+ | 645 | 5.771 | 3.154 | 0.510 | 0.822 |
| geom | 1 | 37 | 2.872 | 1.529 | 0.757 | 0.892 |
| geom | 2 | 121 | 2.940 | 2.628 | 0.496 | 0.785 |
| geom | 3 | 152 | 3.224 | 2.843 | 0.461 | 0.730 |
| geom | 4+ | 645 | 3.385 | 3.032 | 0.436 | 0.704 |
| rel | 1 | 37 | 1.885 | 1.180 | 0.811 | 1.000 |
| rel | 2 | 121 | 2.251 | 2.030 | 0.595 | 0.934 |
| rel | 3 | 152 | 2.408 | 1.816 | 0.599 | 0.941 |
| rel | 4+ | 645 | 2.703 | 2.331 | 0.490 | 0.896 |

`reads` rows are per token read, so a form counts once per token. The `comp` baseline equals the census part within .01 on all rows.

## Target by tier, all depths

| Target | Rows | Marginal | out | body | body+cols, full | open | Control saved, all | Saved full, all forms | Saved full, 25 bits or more |
|---|---|---|---|---|---|---|---|---|---|
| comp INIT | 207 | 3.727 | 3.667 | 2.687 | 2.299 | 0.118 | +0.00 (-0.00 to +0.00) | +1.42 (+1.07 to +1.78) | +0.89 (+0.40 to +1.41) |
| comp DET | 115 | 2.483 | 2.330 | 1.994 | 1.948 | 1.151 | +0.00 (-0.00 to +0.00) | +0.53 (+0.13 to +0.89) | +0.27 (-0.27 to +0.75) |
| kind | 955 | 1.278 | 1.248 | 0.863 | 0.787 | 0.147 | -0.00 (-0.00 to +0.00) | +0.49 (+0.42 to +0.57) | +0.42 (+0.29 to +0.57) |
| cols | 955 | 5.445 | 5.431 | 4.282 | 3.213 | 2.838 | +0.00 (+0.00 to +0.00) | +2.24 (+2.00 to +2.48) | +1.42 (+1.03 to +1.81) |
| geom | 955 | 3.283 | 3.249 | 3.004 | 2.893 | 2.739 | +0.00 (+0.00 to +0.00) | +0.39 (+0.27 to +0.51) | +0.42 (+0.21 to +0.65) |
| rel | 955 | 2.567 | 2.550 | 2.227 | 2.166 | 2.068 | +0.00 (+0.00 to +0.00) | +0.41 (+0.31 to +0.51) | +0.34 (+0.14 to +0.55) |

## Component and relation picks on one census walk, primary number

| Tier | Saved, all forms | Saved, 25 bits or more | Forms over 25 | Taken under 25 | Tasks under 25, before | After |
|---|---|---|---|---|---|---|
| out | +0.03 (+0.01 to +0.05) | +0.03 (-0.03 to +0.10) | 347 | 1 | 0 | 0 |
| body | +0.73 (+0.50 to +0.97) | +0.77 (+0.27 to +1.32) | 347 | 12 | 0 | 0 |
| body+cols | +1.02 (+0.72 to +1.33) | +1.01 (+0.37 to +1.73) | 347 | 13 | 0 | 0 |
| full | +1.02 (+0.72 to +1.33) | +1.01 (+0.37 to +1.73) | 347 | 13 | 0 | 0 |
| open | +1.95 (+1.65 to +2.27) | +2.64 (+1.92 to +3.49) | 347 | 20 | 0 | 0 |
| control | -0.00 (-0.01 to +0.00) | -0.01 (-0.02 to +0.00) | 347 | 0 | 0 | 0 |

`body+cols` and `full` hold the same keys. `control` is the relation tilt only, with labels shuffled.

## Tier full by depth and by kind, saved bits

| Slice | All forms | Forms | 25 bits or more | Forms |
|---|---|---|---|---|
| depth 1 | +1.19 (+0.88 to +1.50) | 37 | +1.29 (+1.00 to +1.61) | 33 |
| depth 2 | +0.44 (+0.05 to +0.82) | 119 | +0.23 (-0.49 to +0.96) | 39 |
| depth 3 | +1.01 (+0.44 to +1.48) | 153 | +0.31 (-1.09 to +1.61) | 58 |
| depth 4+ | +1.20 (+0.75 to +1.70) | 644 | +1.49 (+0.38 to +2.77) | 188 |
| RULE | +0.48 (+0.33 to +0.63) | 650 | +0.26 (+0.07 to +0.45) | 180 |
| DET | +0.80 (+0.35 to +1.18) | 116 | +0.28 (-0.63 to +1.19) | 27 |
| INIT | +2.60 (+1.70 to +3.50) | 239 | +2.11 (+0.60 to +3.58) | 140 |

## Relation tilt alone

| Target | Tier | Gamma | Paid on relation picks | Saved, all forms | Saved, 25 bits or more |
|---|---|---|---|---|---|
| reads RULE DET | out | 0.0 | inf | -0.00 (-0.00 to -0.00) | -0.00 (-0.00 to -0.00) |
| reads RULE DET | body | 0.8 | inf | +0.35 (+0.25 to +0.46) | +0.36 (+0.13 to +0.60) |
| reads RULE DET | body+cols | 0.8 | inf | +0.46 (+0.31 to +0.60) | +0.23 (+0.02 to +0.44) |
| reads RULE DET | full | 0.8 | inf | +0.46 (+0.31 to +0.60) | +0.23 (+0.02 to +0.44) |
| reads RULE DET | open | 0.8 | inf | +0.72 (+0.54 to +0.90) | +0.33 (+0.05 to +0.65) |
| reads RULE DET | control | 0.8 | inf | -0.00 (-0.00 to -0.00) | -0.00 (-0.00 to -0.00) |
| reads INIT | out | 0.6 | 25.46 | -0.01 (-0.06 to +0.04) | -0.00 (-0.09 to +0.07) |
| reads INIT | body | 1.0 | 25.46 | +0.98 (+0.17 to +1.75) | +0.95 (-0.49 to +2.23) |
| reads INIT | body+cols | 1.0 | 25.46 | +1.59 (+0.72 to +2.48) | +1.64 (+0.09 to +3.17) |
| reads INIT | full | 1.0 | 25.46 | +1.59 (+0.72 to +2.48) | +1.64 (+0.09 to +3.17) |
| reads INIT | open | 1.0 | 25.46 | +2.56 (+1.70 to +3.44) | +3.10 (+1.64 to +4.55) |
| reads INIT | control | 1.0 | 25.46 | -0.01 (-0.03 to +0.01) | -0.02 (-0.05 to +0.01) |

## Which table: bits to name the read table among the candidates

| Arm | Edges | Candidates, mean | Uniform | Model | Top-1 | Top-5 | Saved |
|---|---|---|---|---|---|---|---|
| out | 929 | 31.5 | 4.748 | 4.458 | 0.260 | 0.491 | +0.29 (+0.24 to +0.34) |
| hole | 929 | 31.5 | 4.748 | 2.665 | 0.534 | 0.845 | +2.08 (+1.94 to +2.23) |
| holeb | 929 | 31.5 | 4.748 | 3.594 | 0.413 | 0.691 | +1.15 (+1.04 to +1.26) |
| both | 929 | 31.5 | 4.748 | 2.462 | 0.530 | 0.840 | +2.29 (+2.15 to +2.43) |
| both control | 929 | 31.5 | 4.748 | 4.824 | 0.075 | 0.195 | -0.08 (-0.10 to -0.06) |
| out with distractors | 929 | 49.8 | 5.493 | 5.127 | 0.223 | 0.410 | +0.36 (+0.29 to +0.45) |
| both with distractors | 929 | 49.8 | 5.493 | 2.914 | 0.453 | 0.769 | +2.58 (+2.42 to +2.74) |

| Arm | Depth | Edges | Uniform | Model | Top-1 | Top-5 |
|---|---|---|---|---|---|---|
| out | 1 | 33 | 5.188 | 0.531 | 0.970 | 0.970 |
| out | 2 | 116 | 5.153 | 4.838 | 0.216 | 0.414 |
| out | 3 | 147 | 4.700 | 4.549 | 0.231 | 0.517 |
| out | 4 | 633 | 4.662 | 4.571 | 0.239 | 0.474 |
| hole | 1 | 33 | 5.188 | 2.015 | 0.727 | 1.000 |
| hole | 2 | 116 | 5.153 | 3.196 | 0.405 | 0.750 |
| hole | 3 | 147 | 4.700 | 2.812 | 0.442 | 0.830 |
| hole | 4 | 633 | 4.662 | 2.568 | 0.569 | 0.858 |
| holeb | 1 | 33 | 5.188 | 3.323 | 0.697 | 0.879 |
| holeb | 2 | 116 | 5.153 | 3.889 | 0.353 | 0.578 |
| holeb | 3 | 147 | 4.700 | 3.982 | 0.245 | 0.578 |
| holeb | 4 | 633 | 4.662 | 3.464 | 0.449 | 0.728 |
| both | 1 | 33 | 5.188 | 0.290 | 0.939 | 1.000 |
| both | 2 | 116 | 5.153 | 2.795 | 0.491 | 0.810 |
| both | 3 | 147 | 4.700 | 2.572 | 0.469 | 0.830 |
| both | 4 | 633 | 4.662 | 2.489 | 0.529 | 0.839 |
| both control | 1 | 33 | 5.188 | 5.271 | 0.121 | 0.121 |
| both control | 2 | 116 | 5.153 | 5.221 | 0.060 | 0.095 |
| both control | 3 | 147 | 4.700 | 4.827 | 0.082 | 0.163 |
| both control | 4 | 633 | 4.662 | 4.727 | 0.074 | 0.224 |
| out with distractors | 1 | 33 | 5.776 | 0.779 | 0.970 | 0.970 |
| out with distractors | 2 | 116 | 5.771 | 5.310 | 0.198 | 0.371 |
| out with distractors | 3 | 147 | 5.497 | 5.206 | 0.218 | 0.429 |
| out with distractors | 4 | 633 | 5.426 | 5.303 | 0.190 | 0.384 |
| both with distractors | 1 | 33 | 5.776 | 0.513 | 0.909 | 1.000 |
| both with distractors | 2 | 116 | 5.771 | 3.296 | 0.457 | 0.741 |
| both with distractors | 3 | 147 | 5.497 | 3.008 | 0.415 | 0.769 |
| both with distractors | 4 | 633 | 5.426 | 2.948 | 0.438 | 0.761 |

## Candidate tilt on the census walk

The tilt moves weight among derived options only, at picks where gold reads a derived relation. It acts at the reader, not at the read form.

| Arm | Gamma | Saved, all forms | Saved, 25 bits or more | Taken under 25 |
|---|---|---|---|---|
| out | 0.6 | +0.08 (+0.04 to +0.12) | +0.09 (+0.01 to +0.17) | 3 |
| hole | 1.0 | +2.42 (+2.09 to +2.74) | +3.70 (+2.99 to +4.47) | 29 |
| holeb | 0.8 | +1.11 (+0.92 to +1.30) | +1.89 (+1.44 to +2.40) | 17 |
| both | 1.0 | +2.47 (+2.15 to +2.79) | +3.79 (+3.12 to +4.55) | 32 |

## Cost

- {"table_need_ms_median": 1.36, "table_need_ms_max": 134.3, "edge_facts_ms_median": 0.027, "edge_facts_ms_max": 1.535, "tables_per_edge_mean": 31.5}

## Notes

- `Paid on relation picks` reads `inf` for `reads RULE DET` because it takes in forms with no census bits. Saved columns leave those forms out.
- The candidate tilt has no shuffled control. `both control` reads the candidate bits only.
- `out` on depth 1 finds the paint table, which exists only when the program is done, so it isn't a search gain.
- `open` keys for `cols` and `reads RULE DET` are the `body+cols` keys plus the port and column names, with no pick, so those bounds may read low.
- Cost is facts only, on 1 process on a loaded machine. Table facts run once per table. Model scoring isn't timed.
