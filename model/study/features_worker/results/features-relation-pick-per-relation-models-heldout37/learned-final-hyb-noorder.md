# What the top keys learned

Keys of `final-hyb-noorder`, by net bits on held. Each row is one fact the key uses. "Gold / prior" is the count of gold at the option, divided by the prior's mass there, over fit rows: where the fact holds, then where it does not. A ratio over 1 means the prior gives the option too little. "Change" is the mean change in log odds that the model gives where the fact holds, less where it does not, weighted by the prior's mass.

## derived-init

Held: 287 gold picks, net +145.8 bits, +0.51 per gold pick (+0.38 to +0.64). Fit: 3410 gold rows, 200 trees, gold / prior 1.02 over all its rows.

| Direction | Fact | Share of prior mass where it holds | Gold / prior, holds | Gold / prior, not | Change |
|---|---|---|---|---|---|
| raises | `col0_in_scope >= 0` | 0.96 | 1.04 | 0.50 | +1.28 |
| raises | `steer >= -0.656` | 0.82 | 1.08 | 0.72 | +0.68 |
| raises | `steer >= 0.323` | 0.55 | 1.14 | 0.87 | +0.48 |
| lowers | `der_rank >= 19` | 0.07 | 0.49 | 1.06 | -0.88 |
| lowers | `rank >= 2.89` | 0.17 | 0.75 | 1.07 | -0.60 |
| lowers | `der_rank >= 4` | 0.44 | 0.89 | 1.12 | -0.42 |

## derived-rule

Held: 648 gold picks, net +128.3 bits, +0.20 per gold pick (+0.12 to +0.28). Fit: 7677 gold rows, 200 trees, gold / prior 1.07 over all its rows.

| Direction | Fact | Share of prior mass where it holds | Gold / prior, holds | Gold / prior, not | Change |
|---|---|---|---|---|---|
| raises | `nalive >= 78` | 0.41 | 1.19 | 0.98 | +0.41 |
| raises | `share_kind >= 0.707` | 0.52 | 1.12 | 1.00 | +0.30 |
| raises | `der_rank >= 2` | 0.33 | 1.25 | 0.97 | +0.32 |
| lowers | `k >= 2` | 0.63 | 0.98 | 1.21 | -0.49 |
| lowers | `ord >= 2` | 0.67 | 0.99 | 1.22 | -0.49 |
| lowers | `own >= 1` | 0.23 | 0.87 | 1.12 | -0.49 |

## op:NOT

Held: 173 gold picks, net +64.6 bits, +0.37 per gold pick (+0.20 to +0.61). Fit: 2316 gold rows, 200 trees, gold / prior 0.79 over all its rows.

| Direction | Fact | Share of prior mass where it holds | Gold / prior, holds | Gold / prior, not | Change |
|---|---|---|---|---|---|
| raises | `scope:DominantColor` | 0.50 | 0.84 | 0.74 | +0.25 |
| raises | `last:rule:input` | 0.05 | 1.19 | 0.77 | +0.52 |
| raises | `grid_object_size >= 4.67` | 0.50 | 0.86 | 0.72 | +0.23 |
| lowers | `k >= 3` | 0.50 | 0.71 | 0.87 | -0.49 |
| lowers | `k >= 4` | 0.22 | 0.64 | 0.83 | -0.40 |
| lowers | `nalive >= 13` | 0.75 | 0.77 | 0.86 | -0.38 |

## neighbor

Held: 57 gold picks, net +58.0 bits, +1.02 per gold pick (+0.60 to +1.43). Fit: 400 gold rows, 100 trees, gold / prior 1.14 over all its rows.

| Direction | Fact | Share of prior mass where it holds | Gold / prior, holds | Gold / prior, not | Change |
|---|---|---|---|---|---|
| raises | `last:dir8_elem` | 0.05 | 1.92 | 1.10 | +2.19 |
| raises | `steer >= 2.82` | 0.33 | 1.32 | 1.05 | +1.00 |
| raises | `lq >= -1.83` | 0.35 | 1.26 | 1.08 | +0.93 |
| lowers | `hit >= 2` | 0.30 | 0.58 | 1.38 | -1.18 |
| lowers | `prefix:BoundingBox.box` | 0.11 | 0.35 | 1.24 | -1.37 |
| lowers | `scope_n_Axis >= 1` | 0.18 | 0.49 | 1.29 | -1.02 |

## input

Held: 172 gold picks, net +50.2 bits, +0.29 per gold pick (+0.11 to +0.49). Fit: 3052 gold rows, 200 trees, gold / prior 0.90 over all its rows.

| Direction | Fact | Share of prior mass where it holds | Gold / prior, holds | Gold / prior, not | Change |
|---|---|---|---|---|---|
| raises | `last:none` | 0.56 | 0.96 | 0.84 | +0.50 |
| raises | `top_q >= 0.463` | 0.37 | 1.00 | 0.85 | +0.47 |
| raises | `grid_same_shape >= 1` | 0.75 | 0.96 | 0.75 | +0.51 |
| lowers | `nopts >= 77` | 0.78 | 0.86 | 1.05 | -0.72 |
| lowers | `nopts >= 91` | 0.39 | 0.75 | 1.00 | -0.60 |
| lowers | `entropy >= 2.84` | 0.60 | 0.83 | 1.02 | -0.59 |

## compose

Held: 35 gold picks, net +48.7 bits, +1.39 per gold pick (+0.74 to +2.26). Fit: 355 gold rows, 200 trees, gold / prior 1.01 over all its rows.

| Direction | Fact | Share of prior mass where it holds | Gold / prior, holds | Gold / prior, not | Change |
|---|---|---|---|---|---|
| raises | `prefix:perp` | 0.09 | 3.18 | 0.80 | +4.80 |
| raises | `gap_top >= -0.132` | 0.22 | 1.92 | 0.76 | +3.08 |
| raises | `gap_top >= -0.749` | 0.38 | 1.66 | 0.61 | +2.61 |
| lowers | `rank >= 0.693` | 0.81 | 0.79 | 1.97 | -3.22 |
| lowers | `rank >= 1.1` | 0.61 | 0.68 | 1.55 | -2.03 |
| lowers | `rank >= 1.61` | 0.43 | 0.51 | 1.40 | -1.91 |

## derived-proposer

Held: 57 gold picks, net +39.9 bits, +0.70 per gold pick (+0.33 to +0.94). Fit: 2175 gold rows, 200 trees, gold / prior 1.13 over all its rows.

| Direction | Fact | Share of prior mass where it holds | Gold / prior, holds | Gold / prior, not | Change |
|---|---|---|---|---|---|
| raises | `j_cont_o >= 1` | 0.28 | 1.43 | 1.01 | +1.52 |
| raises | `j_fan >= 0.693` | 0.31 | 1.41 | 1.00 | +1.48 |
| raises | `steer >= 0.0511` | 0.66 | 1.31 | 0.78 | +1.28 |
| lowers | `j_match_rank >= 8` | 0.74 | 1.02 | 1.46 | -1.72 |
| lowers | `j_zero >= 1` | 0.08 | 0.20 | 1.21 | -2.52 |
| lowers | `der_rank >= 1` | 0.63 | 0.98 | 1.39 | -1.30 |

## inside

Held: 36 gold picks, net +39.7 bits, +1.10 per gold pick (+0.54 to +1.78). Fit: 606 gold rows, 100 trees, gold / prior 1.24 over all its rows.

| Direction | Fact | Share of prior mass where it holds | Gold / prior, holds | Gold / prior, not | Change |
|---|---|---|---|---|---|
| raises | `prefix:BoundingBox.box` | 0.50 | 1.80 | 0.66 | +2.28 |
| raises | `gap_top >= -0.47` | 0.66 | 1.54 | 0.65 | +2.20 |
| raises | `scope:BoundingBox` | 0.75 | 1.54 | 0.35 | +2.35 |
| lowers | `rank >= 1.95` | 0.20 | 0.53 | 1.42 | -2.16 |
| lowers | `new_types >= 2` | 0.11 | 0.27 | 1.36 | -2.53 |
| lowers | `rank >= 2.71` | 0.09 | 0.48 | 1.31 | -2.12 |

## derived-det

Held: 59 gold picks, net +38.4 bits, +0.65 per gold pick (+0.22 to +1.09). Fit: 658 gold rows, 50 trees, gold / prior 0.76 over all its rows.

| Direction | Fact | Share of prior mass where it holds | Gold / prior, holds | Gold / prior, not | Change |
|---|---|---|---|---|---|
| raises | `k >= 2` | 0.65 | 0.98 | 0.35 | +1.20 |
| raises | `j_cont_o >= 1` | 0.18 | 1.43 | 0.62 | +1.25 |
| raises | `last:input` | 0.15 | 1.35 | 0.66 | +1.17 |
| lowers | `last:none` | 0.35 | 0.35 | 0.98 | -1.20 |
| lowers | `nalive >= 80` | 0.41 | 0.41 | 1.00 | -1.06 |
| lowers | `j_match_rank >= 69` | 0.73 | 0.59 | 1.22 | -1.04 |

## axis_of

Held: 29 gold picks, net +28.7 bits, +0.99 per gold pick (+0.42 to +1.75). Fit: 499 gold rows, 100 trees, gold / prior 1.07 over all its rows.

| Direction | Fact | Share of prior mass where it holds | Gold / prior, holds | Gold / prior, not | Change |
|---|---|---|---|---|---|
| raises | `steer >= 0.597` | 0.52 | 1.58 | 0.52 | +1.25 |
| raises | `steer >= 1.2` | 0.29 | 1.90 | 0.73 | +1.33 |
| raises | `lq >= -2.12` | 0.15 | 2.03 | 0.90 | +1.48 |
| lowers | `rank >= 1.39` | 0.72 | 0.81 | 1.73 | -1.14 |
| lowers | `nalive >= 66` | 0.49 | 0.76 | 1.37 | -0.73 |
| lowers | `rank >= 0.693` | 0.91 | 1.00 | 1.79 | -1.20 |

## Splits by kind of fact

| Kind | Share of tree splits |
|---|---|
| token | 0.251 |
| grid | 0.244 |
| structure | 0.167 |
| prior | 0.151 |
| content | 0.112 |
| scope and form | 0.059 |
| own key | 0.015 |

