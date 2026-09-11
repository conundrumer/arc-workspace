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
- 88bcf3b4 — `nearest.cand` (line 78): a target cell at the pole tip's level toward the worm's side or nearer that side, so the object across the pole's line from the worm is not a target.

Survey: 2026-09-10 20:40 — the solvers since 2026-09-08 22:28.

**Callers**

The fifth survey of `nearer_eq` — two positions compared toward one of the eight directions with equality allowed — covered the seventy solvers it was given (045e512c through fafffa47 in stem order), with a parser matcher over every rule that feeds two `dist` or two `corner_dist` atoms sharing a direction into one `<=` or `>=`, and a second sweep over every ordering comparison in the scope with the atoms that feed it.

Callers:

- 84ba50d3 — `through` (line 105): a stopped row, displaced, at the divider line's level toward the fall direction or past it; `fall.node` consumes it under negation to keep the displacements that leave the row short of the divider.
- 88bcf3b4 — `nearest.cand` (line 78): already on the list; the site still writes the two-`dist` form at the worm's side, positively, as an `ArgExtremes` input.

No third caller: the tight signature matched only these two rules across the scope, and no rule in the scope reads `corner_dist` for a value (its four reads, `08573cc6` `corner_color` and `Determine.marker_corner`, `291dc1e1` `Parse.mark_corner`, `1478ab18` `right_angle`, `bbc9ae5d` `anchor_color`, are corner-cell tests at K = 0). The loose tier found no relation whose rules take `dist` under `dir_elem` and `corner_dist` under `diag_dir_elem`.

**Near-misses**

- `212895b5` `Determine.before` (line 108): two arm cells compared with `<=` on both edge distances of a corner at once, read off `place`, whose `diag_dist` readout also serves a wedge test (`S <= O`). The exclusion is `geq`: this is a pointwise order over a corner's two edges, not a comparison toward one direction, and the rule reads the coordinates for their value as well.
- `212895b5` `Determine.place` (line 103) and `1478ab18` `right_angle` (line 102): one position's two distances toward a corner's edges compared, which side of the corner's diagonal it sits on.
- `13e47133` `pal_len.item` (line 89): a `Rim` depth against a marked depth, a count against a count.
- `89565ca0` `seat` (line 97) and `out` (lines 107–108): a row index against an `Order` rank, and an edge distance against a `Tally`, each a distance or index against a count.
- `08573cc6` `arm_cell` (line 79) and `1190bc91` `arm.blocked` (line 64): two `Ray` step counts, or two sequence indices, compared.
- `20981f0e` `landing`, `8731374e` `covered`, `846bdb03` `interior.cell`, `84f2aca1` `region`, `8698868d` `interior.cell`: `geq` or `gt` over the four edges at once, box containment.
- `84ba50d3` `pierced` (line 133) and `88bcf3b4` `toward` (lines 107, 109): lib `nearer`, the strict comparison, at a cardinal.

**Spec**

Both callers in this scope compare at a cardinal direction the rule already holds, so this survey adds no site to the corner branch, which still rests on 52df9849 alone. Both callers need the non-strict comparison as a positive atom: `nearest.cand` feeds an `ArgExtremes` input and cannot negate anything there, and `through` is itself the relation that `fall.node` negates, so writing it through `nearer` would need a second named relation with the roles flipped. That supports keeping the non-strict peer as its own relation, in the form the entry gives. `212895b5` `Determine.before` is a corner-pointwise order, a two-edge peer of `geq`, which neither reading of the spec question covers; it is one site, so it is reported as caller-only for a different operation, not as a change to this one.

**Reimplementations**

Reimplementations: none.

Survey: 2026-09-10 21:13 — the solvers since 2026-09-10 20:40.

Callers:

896d5239 filled (line 56): the wedge cell Q is no deeper toward D than some arm mark G, written as two `dist` atoms at D and `Kq >= Kg`, a positive atom that `nearer_eq(D, G, Q)` states. The same solver's `outside` (line 51) names lib `nearer` at a corner the rule derives so that `filled` can negate it: `!outside(A, D, Q)` is Q at the apex's level toward each of D's two corners or nearer, which is `nearer_eq` at a DiagDir, reached through a named relation because `nearer` cannot sit under negation.
84ba50d3 through (line 105): a stopped row, displaced, at the divider line's level toward the fall direction or past it, written as two `dist` atoms and `K <= K_div`; `fall.node` negates it. Already on the list.
88bcf3b4 nearest.cand (line 75): a target cell at the pole tip's level toward the worm's side or nearer that side, written as two `dist` atoms and `K_s <= K_tip`, feeding an `ArgExtremes` input. Already on the list.

No further caller: the tight signature (two bare `dist` or two `corner_dist` atoms sharing a direction term, their distance variables feeding one `<=` or `>=`) matched exactly these three rules across the twenty-seven solvers, and no rule in the scope reads `corner_dist` at all. The loose tier found no relation whose rules take `dist` under `dir_elem` and `corner_dist` under `diag_dir_elem`.

Near-misses:

84ba50d3 pierced (line 133), 88bcf3b4 nearest.cand (line 78) and toward (lines 107, 109), 896d5239 outside (line 51): lib `nearer`, the strict comparison, at a direction the rule holds. `toward` compares at two cardinals and pairs them into a corner through `diag_dirs`; `outside` is the negation carrier reported under the 896d5239 caller.
846bdb03 interior.cell (line 39), 84f2aca1 region (line 55), 8698868d interior.cell (line 98), 8731374e covered (line 22): `gt` or `geq` over the four edges at once, box containment.
896d5239 arm (line 41): a `Ray` step count against the `reach` parameter, a step count against a bound.
88bcf3b4 body (line 147): an `Order` rank against a `Tally`, a count against a count.
8698868d fewer (line 79): two `Tally` counts compared.
84f2aca1 Determine.extent_fill (line 128): a box's two `Bbox.extents` readouts compared, which picks the short and long extent of one box.
759f3fd3 Dilate.depth (line 57) and Parse.ring_cycle (line 118): a walk depth against a walk depth, in a subsumption clause and in a ring-adjacency test.

Spec:

The scope adds one new caller, 896d5239, and it bears on the corner branch: `filled` compares at a cardinal, positively, in the two-`dist` form, and `outside` exists only so that `filled` can negate a strict `nearer` at a corner. With `nearer_eq` at a DiagDir, `filled` would state the corner condition directly (`nearer_eq(Diag, Q, A)` for each of D's corners) and `outside` would go, so this site is the second in the corpus that wants the comparison at a corner, beside 52df9849. That supports the entry's form, a Dir8 relation with the corner branch, over a cardinal-only relation. The three sites in the scope all need the non-strict comparison as a positive atom or as the body of a relation that another rule negates, which matches the surveys of 2026-09-08 22:06 and 2026-09-10 20:40: the non-strict peer is its own relation, and no site reads the Dir8 coordinate for its value. Nothing in the scope argues for a change to the interface or the definition.

Reimplementations: none.

Hit counts: the parser matcher over the twenty-seven solvers found 3 tight hits, 8 other ordering comparisons (read above as near-misses), 10 reads of `nearer`, `geq`, or `gt`, no read of `corner_dist`, `diag_dist`, `dist_pair`, or `same_dist`, and no loose-tier relation.

Survey: 2026-09-11 02:24 — the solvers since 2026-09-10 21:13.

Callers:

84ba50d3 through (line 108): a stopped row, displaced, at the divider line's level toward the fall direction or past it, written as two `dist` atoms at `fall_dir` and `K <= K_div`; `fall.node` negates `through`, so the site needs the non-strict comparison as the body of a named relation. Already on the list.
88bcf3b4 nearest.cand (line 79): a target cell at the pole tip's level toward the worm's side or nearer that side, written as two `dist` atoms at S and `K_s <= K_tip`, a positive atom feeding an `ArgExtremes` input. Already on the list.
896d5239 filled (line 59): the wedge cell Q no deeper toward D than some arm mark G, written as two `dist` atoms at D and `Kq >= Kg`, a positive atom; the same rule negates `outside` (line 51), which names lib `nearer` at a corner so that `filled` can reach the non-strict corner comparison. Already on the list.

No further caller: the tight signature (two bare `dist` atoms, or two `corner_dist` atoms, sharing a direction term, their distance variables feeding one `<=` or `>=`) matched exactly these three rules across the forty-six solvers, and no rule in the scope reads `corner_dist`. The loose tier found no relation whose rules take `dist` under `dir_elem` and `corner_dist` under `diag_dir_elem`. Thirty-three of the forty-six solvers hold no ordering comparison and no read of `nearer`, `geq`, `gt`, `dist_pair`, `corner_dist`, `diag_dist`, or `same_dist` at all.

Near-misses:

84ba50d3 pierced (line 133), 88bcf3b4 nearest.cand (line 78) and toward (lines 107, 109), 896d5239 outside (line 51), 8a371977 screened (line 83), 8ba14f53 before (line 99): lib `nearer`, the strict comparison, at a cardinal the rule holds or derives. `screened` and `before` are positive strict comparisons that want no equality. `toward` compares at two cardinals and pairs them into a corner through `diag_dirs`; `outside` is the negation carrier reported under the 896d5239 caller.
8cb8642d arm (lines 68–69): one position's distances toward each of a corner's two directions compared against the opposite edge's, `K <= K1, K <= K2` off two `dist_pair` atoms, which side of the midlines the cell sits on; the exclusion is one position's distances toward two directions compared.
846bdb03 interior.cell (line 39), 84f2aca1 region (line 55), 8698868d interior.cell (line 98), 8731374e covered (line 22), 8a6d367c cell (line 53), 8f215267 cell (line 89): `gt` or `geq` over the four edges at once, box containment.
8698868d fewer (line 79), 88bcf3b4 body (line 147), 8ba14f53 block (line 85), 8abad3cf row.before (lines 73, 85), 8dae5dfc nest.before (line 46): `Tally`, `Order` rank, `Extremes` low, or area side against another of those, a count against a count.
759f3fd3 Dilate.depth (line 57) and Determine.ring_cycle (line 118): a walk depth against a walk depth.
896d5239 arm (line 36): a `Ray` step count against the `reach` parameter, a step count against a bound.
84f2aca1 Determine.extent_fill (line 128): a box's two `Bbox.extents` readouts compared, the short and long extent of one box.
8f215267 kept (line 97): a `stride` index against a `Tally`, an index against a count.

Spec:

The scope adds no caller beyond the three the survey of 2026-09-10 21:13 already listed, and the sites read as they did then: every one needs the non-strict comparison as a positive atom or as the body of a relation that another rule negates, and none reads a Dir8 coordinate for its value. The two new `nearer` sites, 8a371977 `screened` and 8ba14f53 `before`, are strict and positive at a cardinal, so they confirm that the strict form and the non-strict form are consumed separately and neither can be written through the other's negation. The corner branch still rests on 52df9849 and 896d5239 `outside`. 8cb8642d `arm` is the one-position two-direction shape that the `Not:` line excludes, and it is one site, so it reports as caller-only for a different operation. Nothing in the scope argues for a change to the interface or the definition.

Reimplementations: none.

Hit counts: the parser matcher over the forty-six solvers found 3 tight hits, 13 other ordering comparisons (read above as near-misses), 7 reads of `nearer`, 6 reads of `geq` or `gt`, 3 reads of `dist_pair`, no read of `corner_dist`, `diag_dist`, or `same_dist`, and no loose-tier relation. Every hit was read in its rule.
