# `near_half` — which half of its axis a position lies in

The edge of the axis a position lies strictly nearer, with no distance: the side the position sits on, where the centered line sits on neither side. It is the strict, distance-free peer of the `near_edge` proposal.

```
.decl near_half(p: Position, d: Dir) inline
near_half(P, D) :- dist_pair(P, D, K, K2), K < K2.
```

The distances stay out of the signature. Known sites read the test under negation, and lib records on `nearer` that a form whose clauses introduce the distances cannot sit under negation.

Not: `near_edge` (the non-strict pick, which keeps the distance it picks); `nearer` and the `nearer_eq` proposal (two positions compared toward one direction, not one position's own two edges); `DiagPlacement.nearer` read from an instance that also reads `quadrant` or `diag_cell` (the same test, inside a comp the task instantiates for its quadrants and rings); an instance read for `nearer` alone is this operation.

Match: a rule holding `dist_pair(P, D, K, K2)` whose two distance variables feed one `<` and nothing else. Grep `dist_pair` and confirm that neither distance variable appears elsewhere in the rule.

A grep over the corpus finds the shape in `1bfc4729`, `2204b7a8`, `27a77e38`, `29c11459`, `2faf500b`, `342dd610`, `48634b99`, `4e45f183`, `642248e4`, `705a3229`, `ce9e57f2`, `e7dd8335`, `f25ffba3`.

Survey: 2026-09-09 16:53

Survey: 2026-09-10 02:09

Result: over the corpus as of 2026-09-10 02:09 (641 solvers), the strict, distance-discarding test stands at 17 solvers, none a `// family:` sibling. It is applied to frame cells, box-inner cells, tile-arrangement positions, and `Bbox.margin` Positions; on a margin it reads which edge the box hugs, the same operation with no separate interface. Two callers read the far edge (`K > K2`), which `near_half(P, D_near), opposite(D_near, D)` states.

Near-misses:

- Distance kept: `342dd610` `move` (the kept distance feeds `jump_delta`), `57edb29d` `anchor` and `dce56571` `center_line` (non-strict, `near_edge`).
- The complement as a defect witness, `K >= K2` under a universal: `18419cfa` `far_cell`, `3a25b0d8` `off_side`.
- Off-center with no edge named, `K1 != K2`: `c48954c1` `axis_off`, `00576224` `out($Mid())`.
- Perpendicular edges compared: `1478ab18` `right_angle`, `212895b5` `place`.
- `ca8de6ea` reads `DiagPlacement.nearer` from an instance that also reads `diag_cell`.

Spec question: no caller negates the bare test; every negation sits on a materialized wrapper with other atoms, and the two defect-witness sites write the complement positively. The callers justify the distance-free signature on their own. `8618d23e` instantiates `DiagPlacement` for `nearer` alone, with no quadrant or ring concept in the task; the `Not:` line's `DiagPlacement.nearer` exclusion should cover only an instance that also reads `quadrant` or `diag_cell`, which makes `8618d23e` a caller.

Callers:

- 1bfc4729 — `half`, the grid half a cell lies in along `params.axis`.
- 2204b7a8 — `out`, a marker takes the color of the edge line it lies nearer.
- 27a77e38 — `tally.item($Half())`, the cells strictly on the field's side of the split.
- 29c11459 — `owner` and `out($Half())`.
- 2faf500b — `moved($Midline())`.
- 48634b99 — `filled($Half())`.
- 4e45f183 — `lean($Reach())` on a `Bbox.margin`, and `mark_side`.
- 642248e4 — `tail`, the edge line a mark grows toward.
- 689c358e — `points($Nearer())` on a `Bbox.margin`, and `points($Pointer())`.
- 6f473927 — `Parse.ink_edge`, the edge the ink's `Bbox.margin` lies nearer on `params.axis`.
- 705a3229 — `cast`, the strictly nearer edge on each axis, fed to `Ray.dir`.
- ce9e57f2 — `marked`, bar cells strictly nearer the base end.
- e7dd8335 — `half`, ink strictly in the box half toward `params.dir`.
- f25ffba3 — `Determine.data_dir`, the edge the data slab's margin hugs.
- 8618d23e — `side`, through a `DiagPlacement` instance read for `nearer` alone.
- 230f2e48 — `fold_dir($Inward())`, the far-edge reading.
- 4e469f39 — `arm_dir`, the far-edge reading.
