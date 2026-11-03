# Pairs and sets that carry the keys

Rates are labels at the key over the marginal's mass there, on RULE atoms. "Fit" is the fit tasks, "held" the 37 held tasks. A pair stands as a set where the first rate is over 1 and over the second, in both directions. "Written before" is the share of rows holding both where the second relation is written before the left-out one.

| Left out | Other atom | Fit: rows with it, labels | Fit rate with it | Fit rate without | Held: rows with it, labels | Held rate with it | Held rate without | Written before, fit |
|---|---|---|---|---|---|---|---|---|
| `compose` | `perp` | 989, 102 | 6.61 | 0.68 | 59, 4 | 4.68 | 1.30 | 0.99 of 102 |
| `perp` | `compose` | 1414, 97 | 7.39 | 0.55 | 126, 4 | 3.84 | 0.62 | 0.01 of 97 |
| `neighbor` | `dir8_elem` | 141, 39 | 12.79 | 0.83 | 15, 5 | 21.49 | 1.89 | 1.00 of 39 |
| `dir8_elem` | `neighbor` | 1401, 39 | 12.91 | 0.15 | 198, 4 | 10.48 | 0.36 | 0.03 of 39 |
| `inside` | `BoundingBox.box` | 2653, 464 | 6.64 | 0.24 | 116, 20 | 7.25 | 0.36 | 1.00 of 464 |
| `BoundingBox.box` | `inside` | 2482, 459 | 3.45 | 0.49 | 126, 19 | 3.48 | 0.37 | 0.02 of 459 |

## `op:=`

Held: 55 atoms on 17 tasks, net +2.64 per label (+1.55 to +3.10).

| Direction | Fact | Fit labels with it | Fit rate with it | Fit rate without | Held labels with it | Held rate with it |
|---|---|---|---|---|---|---|
| raises | `derived-rule` is elsewhere in the body | 345 | 4.46 | 0.12 | 52 | 10.18 |
| raises | the atom sits under or | 325 | 3.74 | 0.18 | 52 | 10.65 |
| raises | `input` is elsewhere in the body | 228 | 5.00 | 0.42 | 13 | 6.18 |
| raises | the atom sits under if | 63 | 12.44 | 0.77 | 0 | nan |
| raises | an atom names column `input.Col` | 185 | 1.70 | 0.64 | 10 | 2.26 |
| lowers | `derived-rule` is another atom | 57 | 0.31 | 1.37 | 11 | 0.81 |
| lowers | `input` is another atom | 3 | 0.02 | 1.33 | 0 | 0.00 |

## `inside`

Held: 34 atoms on 18 tasks, net +3.43 per label (+2.62 to +4.56).

| Direction | Fact | Fit labels with it | Fit rate with it | Fit rate without | Held labels with it | Held rate with it |
|---|---|---|---|---|---|---|
| raises | an atom names column `BoundingBox.box.B` | 468 | 6.27 | 0.24 | 20 | 6.90 |
| raises | `BoundingBox.box` is another atom | 464 | 6.64 | 0.24 | 20 | 7.25 |
| raises | an atom names column `derived-rule.B` | 65 | 2.52 | 0.85 | 6 | 3.07 |
| raises | `input` is another atom | 345 | 1.62 | 0.58 | 21 | 2.20 |
| raises | an atom names column `same_dist.P1` | 78 | 3.65 | 0.82 | 4 | 3.52 |
| lowers | two atoms share a label: `BoundingBox.box~inside` | 32 | 0.75 | 0.93 | 4 | 2.53 |
| lowers | `inside` is another atom | 38 | 0.58 | 0.95 | 2 | 0.67 |

## `neighbor`

Held: 57 atoms on 21 tasks, net +1.69 per label (+1.18 to +2.21).

| Direction | Fact | Fit labels with it | Fit rate with it | Fit rate without | Held labels with it | Held rate with it |
|---|---|---|---|---|---|---|
| raises | an atom names column `dir_elem.D` | 106 | 5.79 | 0.70 | 14 | 7.78 |
| raises | `dir_elem` is another atom | 99 | 6.01 | 0.72 | 11 | 8.00 |
| raises | `dir8_elem` is another atom | 39 | 12.79 | 0.83 | 5 | 21.49 |
| raises | an atom names column `dir8_elem.D` | 39 | 11.59 | 0.83 | 7 | 17.75 |
| raises | two atoms share a label: `Ray.end~Ray.ray` | 25 | 62.72 | 0.86 | 3 | 64.16 |
| lowers | two atoms share a label: `Ray.ray~derived-rule` | 2 | 0.24 | 0.93 | 0 | 0.00 |
| lowers | `BoundingBox.box` is another atom | 14 | 0.30 | 0.99 | 2 | 1.10 |

## `relative`

Held: 30 atoms on 16 tasks, net +2.64 per label (+1.49 to +3.60).

| Direction | Fact | Fit labels with it | Fit rate with it | Fit rate without | Held labels with it | Held rate with it |
|---|---|---|---|---|---|---|
| raises | `inside` is another atom | 328 | 6.84 | 0.27 | 13 | 5.87 |
| raises | an atom names column `inside.A` | 328 | 6.18 | 0.28 | 13 | 5.17 |
| raises | an atom names column `inside.B` | 326 | 6.23 | 0.28 | 13 | 5.67 |
| raises | two atoms share a label: `BoundingBox.box~inside` | 268 | 8.52 | 0.39 | 9 | 7.71 |
| raises | `BoundingBox.box` is another atom | 297 | 5.77 | 0.35 | 12 | 5.90 |
| lowers | two atoms share a label: `inside~relative` | 33 | 1.33 | 0.89 | 2 | 2.28 |
| lowers | `relative` is another atom | 40 | 1.00 | 0.91 | 0 | 0.00 |

## `margin`

Held: 29 atoms on 14 tasks, net +2.12 per label (+1.58 to +2.89).

| Direction | Fact | Fit labels with it | Fit rate with it | Fit rate without | Held labels with it | Held rate with it |
|---|---|---|---|---|---|---|
| raises | an atom names column `dir_elem.D` | 87 | 4.29 | 0.77 | 9 | 4.52 |
| raises | `dir_elem` is another atom | 83 | 4.55 | 0.77 | 9 | 5.91 |
| raises | an atom names column `DirDomain.D` | 104 | 4.71 | 0.73 | 4 | 6.15 |
| raises | `DirDomain` is another atom | 100 | 4.93 | 0.74 | 3 | 4.56 |
| raises | an atom reads a form that reads `same_dist` | 60 | 4.90 | 0.81 | 5 | 5.67 |
| lowers | two atoms share a label: `margin~margin` | 14 | 1.41 | 0.90 | 0 | 0.00 |
| lowers | an atom names column `input.Col` | 64 | 0.51 | 1.06 | 1 | 0.20 |

## `op:!=`

Held: 52 atoms on 15 tasks, net +1.02 per label (-0.26 to +1.63).

| Direction | Fact | Fit labels with it | Fit rate with it | Fit rate without | Held labels with it | Held rate with it |
|---|---|---|---|---|---|---|
| raises | two atoms share a label: `derived-rule~derived-rule` | 114 | 1.61 | 0.72 | 26 | 4.59 |
| raises | `Ray.ray` is another atom | 44 | 4.71 | 0.80 | 0 | 0.00 |
| raises | an atom names column `Ray.ray.K` | 37 | 7.25 | 0.81 | 0 | 0.00 |
| raises | two atoms share a label: `derived-rule~op:!=` | 40 | 5.52 | 0.81 | 18 | 13.20 |
| raises | an atom names column `op:!=.` | 57 | 3.94 | 0.78 | 20 | 9.65 |
| lowers | an atom names column `derived-rule.P` | 107 | 0.87 | 0.94 | 24 | 2.91 |
| lowers | `derived-rule` is under NOT in the body | 30 | 0.48 | 1.01 | 11 | 2.48 |

## `opposite`

Held: 26 atoms on 15 tasks, net +1.87 per label (+1.15 to +2.55).

| Direction | Fact | Fit labels with it | Fit rate with it | Fit rate without | Held labels with it | Held rate with it |
|---|---|---|---|---|---|---|
| raises | an atom names column `derived-rule.D` | 139 | 4.14 | 0.57 | 12 | 3.20 |
| raises | two atoms share a label: `axis_inset~axis_of` | 68 | 19.93 | 0.73 | 4 | 21.08 |
| raises | an atom names column `DirDomain.D` | 65 | 4.10 | 0.76 | 3 | 6.43 |
| raises | `axis_inset` is another atom | 68 | 12.68 | 0.73 | 4 | 15.81 |
| raises | an atom names column `axis_inset.D` | 68 | 12.36 | 0.73 | 4 | 15.81 |
| lowers | an atom names column `opposite.Opp` | 36 | 1.57 | 0.87 | 2 | 1.14 |
| lowers | an atom names column `opposite.D` | 36 | 1.57 | 0.87 | 2 | 1.14 |

## `compose`

Held: 35 atoms on 18 tasks, net +1.35 per label (+0.34 to +2.46).

| Direction | Fact | Fit labels with it | Fit rate with it | Fit rate without | Held labels with it | Held rate with it |
|---|---|---|---|---|---|---|
| raises | an atom reads a form that reads `axis_inset` | 91 | 12.34 | 0.70 | 4 | 14.95 |
| raises | an atom names column `derived-rule.B` | 109 | 7.13 | 0.66 | 4 | 3.46 |
| raises | an atom reads a form that reads `relative` | 93 | 3.38 | 0.73 | 7 | 3.27 |
| raises | an atom names column `derived-rule.V` | 51 | 6.17 | 0.80 | 5 | 8.10 |
| raises | two atoms share a label: `derived-rule~perp` | 94 | 11.09 | 0.69 | 4 | 6.46 |
| lowers | `derived-rule` is under NOT in the body | 14 | 0.19 | 1.08 | 4 | 0.76 |
| lowers | `compose` is another atom | 27 | 1.29 | 0.89 | 4 | 2.40 |

## `axis_of`

Held: 29 atoms on 10 tasks, net +1.48 per label (-1.26 to +2.87).

| Direction | Fact | Fit labels with it | Fit rate with it | Fit rate without | Held labels with it | Held rate with it |
|---|---|---|---|---|---|---|
| raises | two atoms share a label: `axis_inset~opposite` | 76 | 14.54 | 0.78 | 4 | 13.34 |
| raises | an atom names column `DirDomain.D` | 82 | 3.27 | 0.80 | 1 | 1.36 |
| raises | `DirDomain` is another atom | 79 | 3.43 | 0.81 | 1 | 1.34 |
| raises | an atom names column `same_dist.D` | 73 | 5.45 | 0.80 | 4 | 4.49 |
| raises | an atom reads a form that reads `same_dist` | 60 | 4.32 | 0.83 | 4 | 4.00 |
| lowers | `axis_of` is another atom | 36 | 0.75 | 0.93 | 2 | 0.81 |
| lowers | an atom names column `axis_of.D` | 44 | 0.84 | 0.92 | 2 | 0.77 |

## `perp`

Held: 13 atoms on 11 tasks, net +2.58 per label (+1.54 to +3.74).

| Direction | Fact | Fit labels with it | Fit rate with it | Fit rate without | Held labels with it | Held rate with it |
|---|---|---|---|---|---|---|
| raises | an atom names column `derived-rule.A` | 124 | 7.76 | 0.44 | 9 | 8.48 |
| raises | two atoms share a label: `box_extent~box_extent` | 26 | 14.23 | 0.81 | 2 | 16.39 |
| raises | two atoms share a label: `compose~derived-rule` | 90 | 9.65 | 0.57 | 4 | 5.01 |
| raises | an atom reads a form that reads `axis_inset` | 77 | 16.70 | 0.61 | 4 | 23.91 |
| raises | an atom reads a form that reads `opposite` | 79 | 6.26 | 0.62 | 6 | 5.34 |
| lowers | an atom names column `perp.A` | 2 | 0.19 | 0.95 | 0 | 0.00 |
| lowers | an atom names column `perp.A2` | 2 | 0.19 | 0.95 | 0 | 0.00 |

## `dir_elem`

Held: 26 atoms on 15 tasks, net +1.09 per label (-0.56 to +1.99).

| Direction | Fact | Fit labels with it | Fit rate with it | Fit rate without | Held labels with it | Held rate with it |
|---|---|---|---|---|---|---|
| raises | an atom names column `margin.D` | 83 | 3.40 | 0.69 | 9 | 6.47 |
| raises | an atom names column `margin.B` | 83 | 3.40 | 0.69 | 9 | 6.47 |
| raises | `margin` is another atom | 75 | 3.41 | 0.71 | 9 | 6.75 |
| raises | an atom names column `neighbor.D` | 89 | 4.62 | 0.66 | 11 | 4.60 |
| raises | `neighbor` is another atom | 87 | 4.95 | 0.66 | 10 | 4.50 |
| lowers | an atom names column `dir_elem.D` | 2 | 0.16 | 0.95 | 2 | 1.66 |
| lowers | at least 4 other atoms | 97 | 0.73 | 1.06 | 17 | 1.83 |

## `same_dist`

Held: 11 atoms on 8 tasks, net +1.70 per label (+0.00 to +3.28).

| Direction | Fact | Fit labels with it | Fit rate with it | Fit rate without | Held labels with it | Held rate with it |
|---|---|---|---|---|---|---|
| raises | an atom names column `inside.A` | 79 | 4.41 | 0.49 | 4 | 4.72 |
| raises | an atom names column `inside.B` | 78 | 4.42 | 0.49 | 4 | 5.17 |
| raises | `inside` is another atom | 75 | 4.64 | 0.51 | 4 | 5.36 |
| raises | an atom names column `axis_of.A` | 70 | 4.50 | 0.54 | 4 | 5.14 |
| raises | an atom names column `axis_of.D` | 70 | 4.49 | 0.54 | 4 | 5.14 |
| lowers | an atom reads a form that reads `axis_of` | 8 | 0.45 | 0.97 | 0 | 0.00 |
| lowers | an atom names column `input.Col` | 23 | 0.54 | 1.04 | 0 | 0.00 |
