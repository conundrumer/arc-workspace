# `nearer_eq` — p at or nearer a side than q

Two positions compared toward one of the eight directions, equality allowed: p sits at q's level toward d, or nearer that side. `nearer` states the strict comparison over the same two readings — the edge distance at a cardinal, the corner's taxicab distance at a corner — and its clauses introduce those distances, so a caller cannot negate it to reach the non-strict one. The known sites write two `dist` atoms and a `<=` instead.

```
.decl nearer_eq(d: Dir8, p: Position, q: Position) inline
nearer_eq(D, P, Q) :- dir_elem(D), dist(P, D, K), dist(Q, D, K2), K <= K2.
nearer_eq(D, P, Q) :-
    diag_dir_elem(D), corner_dist(P, D, K), corner_dist(Q, D, K2), K <= K2.
```

Not: `nearer` (the strict comparison); `same_dist` and `same_line` (equality alone); one position's distances toward two directions compared (which side of a midline or a diagonal it sits on); two step counts along a walk compared (`Ray`, `Slide`); `geq` (pointwise over the four edges at once).

Match: a rule holding two `dist` atoms, or two `corner_dist` atoms, that share a direction and feed one `<=` or `>=`. Loose tier: a relation with a Dir8 direction column whose rules take `dist` under `dir_elem` and `corner_dist` under `diag_dir_elem`.

Survey: 2026-09-08 19:59
Survey: 2026-09-08 20:14, over the solvers at or after the first survey's time

The Dir8 coordinate readout that both comparisons read has one site in the corpus, and that site never reads it for its value: both of its consuming atoms sit in one `<=`. Five further rules write the comparison out of two `dist` atoms, each at a cardinal direction the rule already holds, so a Dir8 comparison covers them and the corner case at once. The operation the corpus witnesses is the comparison, not the coordinate.

The second survey covered 0dfd9992, 42a50994, 52fd389e, 538b439f, and 89565ca0. It found no caller, and no near-miss that reads one position's distance against another's, so it leaves the spec question where the first survey left it.

Survey: 2026-09-08 22:06, over the solvers at or after the second survey's time

The third survey covered the twenty-four solvers whose file time is at or after 20:14, and found no caller. One of its near-misses bears on the spec question: `54dc2872` `moves` calls lib `nearer` at a DiagDir the rule derives, so it wants the comparison at a corner and would have no use for a bare Dir8 coordinate readout.

Near-misses: `49d1d64f` `out` and `1478ab18` `right_angle` hold a `dist` atom beside a `corner_dist` atom, but each branch knows its direction's kind, and the `corner_dist` read is a corner-cell test at K = 0. `35ab12c3` `edge` and `1b8318e3` `run` carry a Dir8 column beside a number, and that number is a `Ray` step count. `46c35fc7` `moved` and `b60334d2` `halo` dispatch on the direction kind to pick a sense or a color, with no distance read. `4aab4007` `Parse.corner_dists` reads a corner's two edge distances, which is `diag_dist`. `34cfa167` `from_corner.cand` and `c1990cce` `echo` read `corner_dist` as a coordinate, at a DiagDir the rule holds. `89565ca0` `seat` compares a position's edge distance against an `Order` rank with `<=`, which is a distance against a count.

Spec question: whether the non-strict peer belongs beside `nearer` as its own relation, or whether lib should expose the Dir8 coordinate that both comparisons read and let the caller compare. Only 52df9849 needs the corner branch; the other five sites are cardinal.

Survey: 2026-09-08 22:28, over the solvers at or after the third survey's time

The fourth survey read the five solvers whose file time is at or after 22:06. It found no caller, and no rule in them compares two positions, so it leaves the spec question where the third survey left it. Its near-misses are `5587a8d0` `nest.before`, a count against a count, and three rules that carry a direction column beside a step count or an extent.

Callers:

- 52df9849 — `reaches`: some cell of a color lies at p's level toward d or nearer that side, and the two directions of an axis fold into the color's extent.
- 1da012fc — `behind` (line 74): some cell of one component at or behind some cell of another toward d, consumed by `ahead` under negation.
- 20a9e565 — `target` (line 236): a slot that starts at or before the marker window and ends at or after it.
- 29c11459 — `walk` (line 44): the two advancing fronts kept in order.
- 3979b1a8 — `out` (line 82): a cell at or back across a marker.
- 3d588dc9 — `short` (line 95): a key's box no further toward an edge than a wedge's.
- 5545f144 — `blunt` (line 71): some cell of a symmetric set at the candidate tip's level toward d or past it, consumed under negation to leave the tips that are strictly furthest.
