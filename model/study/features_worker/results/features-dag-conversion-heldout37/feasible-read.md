# Value join set at the relation pick, held-parents RULE forms, steers off

Rows: 2880 probe rows; 2401 gold-alive probed picks on 18 tasks and 180 forms (173 forms complete). RULE points of held-parents: {'complete': 173, 'partial': 7, 'none probed': 249, 'no finished walk': 4}. Probed weight 724.1 of 1976.5 in the pick table. Largest gap of the probe row's prior to the pick table 0.0 bits.

The forms that the read leaves out are listed in feasible-left-out.tsv: states `no finished walk` and `none probed` have no pick in the read, `partial` has the picks that were probed.

Escape weights: none. probe-test rows do not exist yet, so no number with an escape weight is written.

| Picks | Count | Alive: Q1, median, Q3 | any | all | keep | One example at a time |
|---|---|---|---|---|---|---|
| all picks | 2401 | 54.0, 68.0, 81.0 | 37.0, 53.0, 72.0 | 35.0, 52.0, 71.0 | 39.0, 54.0, 72.0 | 36.0, 52.0, 71.0 |
| band empty | 502 | 82.0, 92.0, 109.0 | 78.0, 87.0, 103.0 | 78.0, 87.0, 102.0 | 78.0, 87.0, 103.0 | 78.0, 87.0, 103.0 |
| band 1 | 1180 | 48.0, 61.0, 71.0 | 31.0, 46.0, 58.0 | 31.0, 44.0, 57.0 | 34.0, 47.0, 59.0 | 31.0, 44.8, 57.0 |
| band 2 | 652 | 53.0, 62.0, 73.0 | 36.8, 48.0, 59.0 | 33.0, 48.0, 59.0 | 40.0, 51.0, 60.0 | 34.8, 48.0, 59.0 |
| band 3+ | 67 | 63.0, 70.0, 82.0 | 40.0, 60.0, 69.5 | 40.0, 60.0, 68.0 | 52.0, 61.0, 70.0 | 40.0, 60.0, 69.0 |

Gold in the set, all probed picks:

| Set | Prior | Picks | Gold in set | Share | Picks read | Prior bits, same picks | Uniform over alive | Uniform over set | Prior in set | Saved by the prior in set, 95% by task |
|---|---|---|---|---|---|---|---|---|---|---|
| any | off | 2401 | 2331 | 0.9722 | 2331 | 5.143 | 5.959 | 5.555 | 4.666 | +0.477 (+0.397 to +0.549) |
| any | live | 2401 | 2331 | 0.9722 | 2331 | 3.386 | 5.959 | 5.555 | 3.192 | +0.193 (+0.160 to +0.235) |
| all | off | 2401 | 2266 | 0.9475 | 2266 | 5.144 | 5.966 | 5.544 | 4.655 | +0.489 (+0.410 to +0.558) |
| all | live | 2401 | 2266 | 0.9475 | 2266 | 3.396 | 5.966 | 5.544 | 3.176 | +0.220 (+0.186 to +0.262) |
| keep | off | 2401 | 2350 | 0.9841 | 2350 | 5.154 | 5.954 | 5.677 | 4.734 | +0.420 (+0.352 to +0.481) |
| keep | live | 2401 | 2350 | 0.9841 | 2350 | 3.384 | 5.954 | 5.677 | 3.236 | +0.148 (+0.123 to +0.177) |

Gold in the set, picks of complete forms:

| Set | Prior | Picks | Gold in set | Share | Picks read | Prior bits, same picks | Uniform over alive | Uniform over set | Prior in set | Saved by the prior in set, 95% by task |
|---|---|---|---|---|---|---|---|---|---|---|
| any | off | 2263 | 2196 | 0.9715 | 2196 | 5.149 | 5.949 | 5.543 | 4.66 | +0.489 (+0.408 to +0.560) |
| any | live | 2263 | 2196 | 0.9715 | 2196 | 3.348 | 5.949 | 5.543 | 3.15 | +0.197 (+0.163 to +0.240) |
| all | off | 2263 | 2131 | 0.9457 | 2131 | 5.151 | 5.956 | 5.533 | 4.649 | +0.502 (+0.423 to +0.570) |
| all | live | 2263 | 2131 | 0.9457 | 2131 | 3.357 | 5.956 | 5.533 | 3.132 | +0.225 (+0.191 to +0.268) |
| keep | off | 2263 | 2213 | 0.9835 | 2213 | 5.163 | 5.944 | 5.668 | 4.729 | +0.434 (+0.368 to +0.492) |
| keep | live | 2263 | 2213 | 0.9835 | 2213 | 3.347 | 5.944 | 5.668 | 3.194 | +0.153 (+0.127 to +0.182) |

Set any, by class:

| Cell | Picks | Tasks | Gold in any | Prior bits | Prior in set | Saved in set off | Saved in set live | Saved with escape off |
|---|---|---|---|---|---|---|---|---|
| derived | 970 | 18 | 931 | 5.115 | 4.617 | +0.498 (+0.419 to +0.566) | +0.177 (+0.134 to +0.242) |  |
| lib | 315 | 16 | 313 | 6.525 | 6.148 | +0.376 (+0.287 to +0.458) | +0.134 (+0.104 to +0.163) |  |
| own | 364 | 17 | 354 | 5.396 | 4.8 | +0.596 (+0.474 to +0.705) | +0.276 (+0.162 to +0.424) |  |
| macro | 233 | 16 | 233 | 7.189 | 6.653 | +0.535 (+0.318 to +0.785) | +0.177 (+0.121 to +0.228) |  |
| NOT | 242 | 17 | 242 | 4.146 | 3.668 | +0.478 (+0.377 to +0.557) | +0.323 (+0.227 to +0.433) |  |
| fact | 165 | 17 | 153 | 3.048 | 2.718 | +0.330 (+0.251 to +0.435) | +0.072 (+0.050 to +0.093) |  |
| comparison | 112 | 11 | 105 | 3.293 | 2.937 | +0.357 (+0.271 to +0.474) | +0.198 (+0.155 to +0.289) |  |

Set any, by band:

| Cell | Picks | Tasks | Gold in any | Prior bits | Prior in set | Saved in set off | Saved in set live | Saved with escape off |
|---|---|---|---|---|---|---|---|---|
| empty | 502 | 18 | 502 | 4.921 | 4.726 | +0.195 (+0.151 to +0.234) | +0.010 (+0.004 to +0.022) |  |
| 1 | 1180 | 18 | 1128 | 5.182 | 4.544 | +0.638 (+0.536 to +0.728) | +0.264 (+0.223 to +0.316) |  |
| 2 | 652 | 17 | 634 | 5.231 | 4.726 | +0.505 (+0.369 to +0.629) | +0.269 (+0.199 to +0.373) |  |
| 3+ | 67 | 7 | 67 | 5.966 | 5.538 | +0.429 (+0.241 to +0.578) | +0.241 (+0.052 to +0.575) |  |

Set any, by class band:

| Cell | Picks | Tasks | Gold in any | Prior bits | Prior in set | Saved in set off | Saved in set live | Saved with escape off |
|---|---|---|---|---|---|---|---|---|
| derived, empty | 324 | 18 | 324 | 5.157 | 4.994 | +0.164 (+0.121 to +0.205) | +0.011 (+0.004 to +0.026) |  |
| derived, 1 | 482 | 18 | 450 | 4.971 | 4.197 | +0.773 (+0.646 to +0.892) | +0.305 (+0.235 to +0.388) |  |
| derived, 2 | 152 | 16 | 145 | 5.357 | 4.594 | +0.763 (+0.475 to +1.034) | +0.340 (+0.187 to +0.658) |  |
| derived, 3+ | 12 | 6 | 12 | 6.011 | 5.503 | +0.508 (+0.181 to +1.096) | +0.164 (+0.043 to +0.393) |  |
| lib, empty | 51 | 14 | 51 | 6.936 | 6.93 | +0.006 (+0.002 to +0.014) | +0.000 (+0.000 to +0.001) |  |
| lib, 1 | 170 | 13 | 170 | 6.52 | 5.98 | +0.540 (+0.434 to +0.653) | +0.198 (+0.148 to +0.242) |  |
| lib, 2 | 84 | 15 | 82 | 6.18 | 5.856 | +0.324 (+0.238 to +0.439) | +0.102 (+0.074 to +0.135) |  |
| lib, 3+ | 10 | 6 | 10 | 6.684 | 6.535 | +0.149 (+0.092 to +0.262) | +0.053 (+0.030 to +0.081) |  |
| own, empty | 36 | 11 | 36 | 6.089 | 5.061 | +1.028 (+1.020 to +1.034) | +0.026 (+0.015 to +0.039) |  |
| own, 1 | 170 | 17 | 165 | 4.954 | 4.364 | +0.591 (+0.439 to +0.727) | +0.210 (+0.172 to +0.259) |  |
| own, 2 | 140 | 15 | 135 | 5.63 | 5.175 | +0.455 (+0.289 to +0.707) | +0.354 (+0.164 to +0.558) |  |
| own, 3+ | 18 | 3 | 18 | 6.16 | 5.396 | +0.764 (+0.225 to +1.008) | +0.795 (+0.088 to +2.274) |  |

Gold out of the `any` set:

- gold's atom reads no bound label: 46
- NOT: gold's atom removes all on some examples and none on the others: 8
- comparison: gold's atom removes no row on any train example: 7
- gold's atom gives no table: no probe token: 5
- NOT: gold's atom removes and keeps a row, and no map shows it: 3
- NOT: gold's atom removes every row: 1

Gold in the `any` set against the source record (feasible-read.json, written-order walks): {"derived": {"picks": 970, "share_gold_in_any": 0.96, "source_share": 0.962}, "lib": {"picks": 315, "share_gold_in_any": 0.994, "source_share": 1.0}, "own": {"picks": 364, "share_gold_in_any": 0.973, "source_share": 0.978}, "macro": {"picks": 233, "share_gold_in_any": 1.0, "source_share": 1.0}, "NOT": {"picks": 242, "share_gold_in_any": 1.0, "source_share": 1.0}, "fact": {"picks": 165, "share_gold_in_any": 0.927, "source_share": 0.906}, "comparison": {"picks": 112, "share_gold_in_any": 0.938, "source_share": 0.911}}; all classes {'share': 0.9708, 'source_share': 0.9675}.
