# `edge_depth` — a cell's distance to the nearest edge of its frame

The least of a position's four edge distances: its ring index, counting inward from the border at 0. A solver reading concentric rings, an erosion depth on a rectangular region, or a margin from whichever side is closest states that in one atom instead of folding a minimum over the four directions.

```
.decl edge_depth(p: Position, k: number) inline
edge_depth([T, B, L, R], K) :- K = min(min(T, B), min(L, R)).
```

Not: `Rim.depth` over a set whose shape can differ from its frame (erosion follows the set's own rim, and agrees with this only on a solid rectangle; a `Rim` whose cell set is a constructed full frame states this operation, and its site is a caller); `DiagPlacement.diag_cell`'s ring (the shared distance to one corner's two edges, not the fold over all four); `axis_near` (the nearer distance on one axis, not the fold over both); `corner_dist` (taxicab distance to a corner); `Bbox.edge_min` (a set's least distance per edge, one number per box side); a band-membership test — `dir_elem(D), dist(P, D, K)` against a bound, of which the border test at `dist(P, D, 0)` is the depth-one case — which states existence and needs no fold.

Match: an `Extremes` or `ArgExtremes` instance whose `cand` joins `dir_elem(D), dist(P, D, K)` over one cell set, read through `.low` — grep `dir_elem(.*dist(` and confirm the `.low` consumer; or a `Rim` instance whose `cell` is a full rectangular frame, read only through `.depth` — grep `= Rim` and confirm that the cell set is every cell of a frame.

Survey: 2026-09-08 17:33

Result: over the 538 solvers as of 2026-09-05, exactly four `Extremes`/`ArgExtremes` instances fold `dir_elem(D), dist(P, D, K)` over one cell set. Three read `.low` and are the operation; the fourth (25d487eb) reads `.high` for a Dir. Of the 76 rules holding `dir_elem` and `dist` together, the other 72 are border-membership tests at distance 0, per-direction data that keeps `D` as a key, or direction selection by defect negation — none folds. No site hand-writes a primitive lib already holds. A delta survey at the Survey time above, over the solvers substantively changed since that scan, found no new caller, no reimplementation, and no spec signal; 85c4e7cd now states the operation through the `Rim<Unit>` form instead of the `Extremes` fold, and stays one caller. A second delta survey, 2026-09-08 22:56, over the 46 solvers whose file time is at or after the Survey time, found no new caller, no reimplementation, and no spec signal.

Spec question: whether the `Rim.depth` exclusion names the comp or the concept. Settled 2026-09-05: it names the concept, and the `Not:` line turns on the set.

Callers:
- 85c4e7cd — `peel`, a `Rim<Unit>` over the whole input grid, read for the ring index of a concentric-ring grid.
- 45a5af55 — `peel`, the same construction over the constructed output square.
- 516b51b7 — `box_depth`, an object cell's least distance to an edge of its own bounding box, read in the box's frame through `BoxFrame.inner`. Sole evidence for the reframed reading.
- 3ee1011a — `rim`, a `Rim<Unit>` over a constructed `Frame2D` square, read only for the frame's ring index.
- 4290ef0e — `peel`, the same construction.
- 5751f35e — `peel`, a `Rim<Unit>` over the whole input grid, read for the ring index of a nest of concentric rings.

Near: 639f5a19 (`$Inset`, a band of task-given depth inside an object's own bounding box, read through `BoxFrame.inner` as the existence of an edge nearer than that depth); 25d487eb (`.high`, and the readout is a Dir); 13e47133 and 516b51b7's own `$Peel` (erosion over a set whose shape can differ from the frame); ca8de6ea (the corner-diagonal ring, read with its quadrant); 34cfa167 (`corner_dist` ranking); 13713586 (`Bbox.edge_min` over a data-selected direction set).
