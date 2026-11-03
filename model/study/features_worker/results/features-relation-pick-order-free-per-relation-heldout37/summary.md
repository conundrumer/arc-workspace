# Read on the 37 held tasks

RULE atoms, bits saved per left-out atom against the marginal among the options.

| Model | Atoms | Baseline bits | Saved | Keys passing net 1 bit |
|---|---|---|---|---|
| Primary: other atoms as a set, their count, join structure | 1809 | 5.216 | +0.944 (+0.726 to +1.184) | 12 |
| Primary on shuffled labels | 1809 | 5.528 | -0.090 (-0.140 to -0.043) | 0 |
| Scope only, no atom of the body | 1809 | 5.216 | +0.226 (+0.148 to +0.316) | 1 |
| Other atoms as a set and their count | 1809 | 5.216 | +0.722 (+0.526 to +0.930) | 8 |
| Primary plus open labels and unread forms | 1809 | 5.216 | +1.252 (+1.031 to +1.491) | 13 |
| Primary plus written order | 1809 | 5.216 | +1.309 (+1.108 to +1.531) | 12 |
| A random subset of the other atoms | 1809 | 5.216 | +0.512 (+0.374 to +0.663) | 5 |
| Atoms written before, as a set | 1809 | 5.216 | +1.004 (+0.858 to +1.164) | 10 |
| Atoms written before, plus index and last head | 1809 | 5.216 | +1.056 (+0.911 to +1.215) | 10 |

By class, primary and the same with order:

| Class | Atoms | Baseline | Saved, primary | Saved, with order | Saved, scope only |
|---|---|---|---|---|---|
| derived | 899 | 4.974 | +0.564 (+0.327 to +0.828) | +0.707 (+0.470 to +0.982) | +0.214 (+0.085 to +0.349) |
| lib | 257 | 7.000 | +1.803 (+1.189 to +2.381) | +2.356 (+1.796 to +2.894) | +0.177 (-0.072 to +0.429) |
| fact | 169 | 3.071 | +0.529 (+0.088 to +0.932) | +0.652 (+0.189 to +1.066) | -0.150 (-0.247 to -0.046) |
| macro | 173 | 6.776 | +1.992 (+1.533 to +2.537) | +2.770 (+2.316 to +3.273) | +0.187 (-0.092 to +0.494) |
| NOT | 190 | 3.501 | +0.336 (-0.241 to +0.876) | +0.958 (+0.427 to +1.443) | +0.284 (+0.055 to +0.517) |
| comparison | 121 | 6.682 | +1.978 (+1.313 to +2.435) | +2.928 (+2.356 to +3.342) | +0.917 (+0.610 to +1.103) |

The relation inside a NOT, a further pick not counted above: 190 picks, baseline 4.038, saved +0.031 (-0.319 to +0.384).

Written order, on the same rows:

- All other atoms: 0.944 with no order, 1.309 with it. Order adds 0.365, 28% of the larger gain.
- Same context sizes: 0.512 for a random subset, 1.004 for the atoms written before, 1.056 with index and last head. Order adds 0.545, 52% of the larger gain.

Body over scope, primary: 0.717.

## INIT

1261 atoms on 37 tasks, baseline 5.190, saved +1.978 (+1.685 to +2.281), scope and slot facts alone +0.895 (+0.683 to +1.111), control -0.024 (-0.091 to +0.039). Keys passing net 1 bit: derived-init, step_offset, margin, op:NOT, dir_elem, diag_dir_elem, axis_elem, ex_input, derived-proposer, neighbor.

Key bodies: 360 atoms, baseline 5.155, saved +1.356 (+0.978 to +1.760). Port bodies: 901 atoms, baseline 5.203, saved +2.227 (+1.912 to +2.541).

| Class | Atoms | Baseline | Saved |
|---|---|---|---|
| derived | 658 | 4.885 | +1.567 (+1.360 to +1.782) |
| lib | 261 | 6.291 | +3.258 (+2.506 to +3.916) |
| fact | 165 | 3.513 | +1.406 (+0.930 to +1.907) |
| macro | 63 | 7.684 | +2.733 (+1.174 to +4.094) |
| NOT | 73 | 4.256 | +1.838 (+1.239 to +2.378) |
| comparison | 41 | 7.638 | +1.831 (+0.482 to +3.330) |

## DET

257 atoms on 21 tasks, baseline 4.493, saved +0.540 (+0.271 to +0.859), scope and slot facts alone +0.133 (+0.028 to +0.256), control -0.061 (-0.229 to +0.129). Keys passing net 1 bit: derived-init, dir_elem.

| Class | Atoms | Baseline | Saved |
|---|---|---|---|
| derived | 80 | 5.346 | +0.312 (-0.454 to +1.246) |
| lib | 32 | 6.348 | +0.917 (+0.227 to +1.425) |
| fact | 65 | 2.964 | +0.653 (+0.362 to +0.966) |
| macro | 22 | 6.021 | +1.031 (+0.759 to +1.546) |
| NOT | 42 | 2.897 | +0.327 (-0.184 to +0.919) |
| comparison | 16 | 4.822 | +0.360 (-1.081 to +1.731) |

## Keys of the primary that pass 1 bit net

A key is read where it has 8 held tasks or 50 held atoms. 19 keys are read. 397 atoms of 1809 have a passing key as their label, a share of 0.219.

| Key | Atoms | Tasks | Saved at label | Net per label | Net 95% | Net total bits |
|---|---|---|---|---|---|---|
| op:= | 55 | 17 | +3.47 | +2.64 | +1.55 to +3.10 | +145.1 |
| inside | 34 | 18 | +3.23 | +3.43 | +2.62 to +4.56 | +116.6 |
| neighbor | 57 | 21 | +2.21 | +1.69 | +1.18 to +2.21 | +96.0 |
| relative | 30 | 16 | +2.79 | +2.64 | +1.49 to +3.60 | +79.1 |
| margin | 29 | 14 | +2.53 | +2.12 | +1.58 to +2.89 | +61.6 |
| op:!= | 52 | 15 | +2.04 | +1.02 | -0.26 to +1.63 | +52.9 |
| opposite | 26 | 15 | +2.71 | +1.87 | +1.15 to +2.55 | +48.5 |
| compose | 35 | 18 | +1.91 | +1.35 | +0.34 to +2.46 | +47.2 |
| axis_of | 29 | 10 | +2.57 | +1.48 | -1.26 to +2.87 | +42.9 |
| perp | 13 | 11 | +2.98 | +2.58 | +1.54 to +3.74 | +33.5 |
| dir_elem | 26 | 15 | +2.24 | +1.09 | -0.56 to +1.99 | +28.4 |
| same_dist | 11 | 8 | +2.53 | +1.70 | +0.00 to +3.28 | +18.7 |

The control passes 0 keys: none.

