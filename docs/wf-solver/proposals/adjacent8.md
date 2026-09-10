# `adjacent8` — the cells one step from a position under 8-adjacency

The 8-neighborhood of a position, one cell per direction:

```
dir8_elem(D), neighbor(M, D, P)
```

A caller that clips to the grid adds `in(P, _)`.

Not: `neighbor` at one caller-bound direction; `Rim8.rim_dir` (a set cell's exposed sides); `Components8` (connectivity closure over the same steps).

Match: `dir8_elem\([A-Za-z0-9_]+\), neighbor\(`, plus layouts that split the two atoms across lines.

Closed: 2026-09-03 20:47. Lib already holds the operation: `neighbor` states the step, and Dir8 is a structural class the program enumerates with `dir8_elem`, as the Closure principle prescribes for `dir_elem` and `diag_dir_elem`. A named primitive would rename the two-atom pair and drop the direction column, which some sites bind in their heads.
