# `inward` — the heading a box on the frame's border faces into the frame

The Dir that points from the frame's border into the frame, paired with a box flush against the opposite edge: a cell on edge T faces B, and a box flush at edge L faces R. It is the frame's own inside/outside orientation, read off a thing that touches the border. A solver that casts from the border, grows away from it, or reads a strip by the side it sits on states the placement and the heading in one atom, instead of writing an edge-contact test and reversing its direction beside it.

```
.decl inward(b: Box, d: Dir) inline
inward(B, D) :- opposite(D, D_edge), dist(B, D_edge, 0).
```

A box flush at two opposite edges faces both ways, and a corner cell faces the two headings of its two edges.

Not: a plain border test (`dir_elem(D), dist(P, D, 0)`), which states contact and carries no heading; `edge_depth`, the fold of the four edge distances; `near_edge`, the nearer edge of one axis with its distance, which reads a half and not a contact; `opposite` alone, which reverses a direction with no placement; `Abut`, the heading a cell takes off another set rather than off the frame; `Rim.rim_dir`, the direction a set's own boundary faces.

Match: one rule holding an `opposite` atom and a zero-distance `dist` atom that share a direction variable, over a Box, a Position, or a Bbox box; and the same pairing written with `diag_dirs`, `dir_of`, or `perp_dir` in place of `opposite` where the head keeps a cardinal. State the shape in prose and match it with the parser.

Survey: 2026-09-14 02:10 — every solver.

Callers:
136b0064 canvas — takes the panel flush against the edge away from the legend, so the legend direction is that panel's inward heading; its Determine comp writes the same pair at side_ok, over a candidate legend side.
195c6913 head — gives a seed the heading away from the edge it sits on.
20981f0e clear_step — steps a piece's Bbox box away from the wall it lies against.
20fb2937 band_key — keeps the header cells of the layer flush against the edge away from the swatch.
22eb0ac0 edge_match — pairs two cells of one line, one flush at each edge of the task's axis, the second contact stated through the reversal.
27a77e38 target — the target row sits on the edge away from the field; the Determine comp derives that heading at field_dir from a stamp's edge contact, as the entry's code form writes it.
36a08778 stub_flow — flows a stub on from the edge its cell touches.
3ac3eb23 seed — seeds a trail heading away from the edge the marker sits on.
5adee1b2 legend_entry — steps one cell in from the legend edge to read an entry's border color.
5b37cb25 edge_color — reads a frame edge's color at the cell whose next step in is canvas.
65b59efc legend_cell — takes the band flush against the edge away from the template side.
689c358e mark — colors the far end of a bar's line, the cell on the edge away from the side the cross points to.
6f473927 tiles — takes the tile flush at the edge away from the ink edge, with its neighbor back toward that edge.
760b3cac dir — places the far marker on the edge away from the facing side, against the near marker on the facing edge.
762cd429 grow — grows the seed box away from the edge it sits against.
7e4d4f7c out — the tail row is the output row flush at the edge away from the header; the other branch negates that same test.
8403a5d5 first_edge — casts the trail away from the edge the marker sits on, across the bar axis.
88bcf3b4 heading — heads a pole away from the edge its foot touches.
9473c6fb spans — a span's two marks, one flush at each end edge of the candidate direction.
95755ff2 source — casts content from a border cell into the grid, away from the border it sits on.
a3df8b1e trace — reflects the walk: at the edge toward the heading, the new heading is the reverse.
bbb1b8b6 piece — reads the ink of the tile flush at the edge away from the base direction.
bbc9ae5d seated — seats input content on the seed edge, away from the stacking direction.
d9f24cd1 walk — walks each mark away from the edge it sits on.
e179c5f4 launch — launches the ball away from the two edges the mark touches, one heading per axis; walk reflects it at a wall by the same pair.
e3497940 ink — folds the tile flush at the edge away from the base tile.
feca6190 seated — seats the line on the start edge, away from the sweep's stacking direction.

The signature matched 56 rules across 49 solvers. The 22 solvers above the callers are those where the reversed direction and the zero-distance contact describe one box; the rest fall into the classes below.

Near-misses:
A corner or axis selector with a plain border test, and no reversal: the rule picks a cardinal with `dir_of`, `diag_dirs`, or `perp_dir`, then tests contact on that same cardinal, so the atom pair states contact and carries no heading. 08573cc6 other_color, 1e81d6f9 region.seed, 2281f1f4 marked and selected, 291dc1e1 border, 3979b1a8 growth_mismatch, 3bd67248 wall_dir, 4a21e3da cut_dir and side, 79cce52d kept and band_cell, 7c66cb00 line_end, 8d5021e8 anchor_tile, a406ac07 line_color, on_header and agree, a3df8b1e trace (the advance rule), 47c1f68c mirror, and the 67e8384a family's mirror, counted once.
A quarter turn off the touched edge: the rule steps along the border, not into the frame, so the direction is no reversal. 30f42897 ring.succ, 880c1354 border_step, ca8de6ea border_step, 7ec998c9 leg.mark.
The reversal and the contact on different boxes: 1190bc91 seq, where the reverse feeds `exposed.rim_dir`, the direction a set's own boundary faces; 7d7772cc rest, where the reverse steps off the pen box and the contact is a far-edge test on another cell.
The touched edge stored without its box and reversed in a later rule: the producing rule keeps the contact box and exports the edge alone, so the consuming rule holds no box for the atom to take. 17b80ad2 marked with flow.dir, 20fb2937 side with fld_box.cell, 5e6bbc0b fall with far_end and beam.dir, 770cc55f bar with flow.dir, 78332cb0 port with link, e633a9e5 edge_off and axis_off, 28a6681f held with rest, 712bf12e line, where the reversal is shared with a sibling case whose direction comes from the parameters.

Spec:
Three questions stand, each from sites in the parts above. No solver writes the operation as a comp, so none of them rests on a surfacing site.

The inline declaration does not admit the complement. 7e4d4f7c out writes the contact positive in one branch and negated in the other. The clause introduces `D_edge`, and lib admits an inline relation under negation only when its clauses introduce no variable, so `!inward(P_out, H_dir)` breaks that contract. The entry should say which side it takes: keep `inline` and leave the complement as the plain pair, or drop `inline`.

The facing pair consumes no heading. 22eb0ac0 edge_match, 9473c6fb spans, 760b3cac dir, and 78332cb0 link reverse a direction to name the other edge of one axis, for a second box. The code form rewrites each of them, one contact plain and one through the operation, and the result reads as a heading where the rule means the far edge. The entry states the operation as a placement paired with a heading, and it should say whether that pair counts.

The Match line asks for statements across rules, and the cross-rule pass found a shape the interface cannot serve. At 17b80ad2, 5e6bbc0b, 770cc55f, 78332cb0, 20fb2937, and e633a9e5, a relation keyed by the touched edge carries that edge past its box, and the reversal sits where the box is out of scope. Where the unreversed edge is itself consumed, as `fall` is at 5e6bbc0b, the producing rule cannot export the heading in its place. The Match line should require the two atoms to share a box.

Reimplementations:
none.
The search ran two parser passes over the 774 solvers, through `dl.corpus.each_solver`. The first pass paired a reversal atom with a zero-distance `dist`, `dist_pair`, or `diag_dist` atom on a shared direction variable, in one rule, disjunction branches and aggregate bodies flattened; it widened the entry's reversal list with `turn`, `diag_opposite`, `flip_of`, `perp`, and `diag_perp`, and matched 56 rules in 49 solvers, 32 through `opposite`, 14 through `dir_of`, 4 through `turn`, 3 through `diag_dirs`, and 3 through `perp_dir`. The second pass took relations whose head exports the direction of a zero-distance contact and found the rules that consume one beside a reversal; it matched 16 rules in 12 solvers. Each hit was read in its rule.

Survey: 2026-09-14 02:55 — the solvers since 2026-09-14 02:10.

Callers:
9473c6fb spans — a span's two marks, one flush at each end edge of the candidate direction, the second contact stated by reversing the first.
95755ff2 source — casts content from a border cell into the grid, away from the border it sits on.
96a8c0cd heading — gives the walker the heading away from the border edge its marker sits on.

The first two stand in the result of 2026-09-14 02:10; 96a8c0cd is new. Across the 26 solvers the single-rule signature matched 3 rules in these 3 solvers, and the cross-rule pass matched none: no relation in the scope exports the direction of a zero-distance contact past its box to a rule that reverses it.

Near-misses:
A reversal off another set, not off the frame: the rule takes a heading from a cell set's own box, boundary, or contact, which the entry excludes as `Abut` and `Rim.rim_dir`. 4c3d4a41 refuted_dir reverses beside `comb_rim.rim_dir`, the direction the comb's boundary faces. 6e4f6532 wall_toward reverses a cast direction, and faces reverses that heading again to step behind a cell. 952a094c inner reverses a corner of the set's bounding box. 95990924 painted reverses the corner across which a square meets ink. 93c31fbe corner reverses the corner a mark's two arms straddle.
A reversal with no placement: `opposite` alone, reversing a direction that the parameters supply or that another rule already holds. 8abad3cf inward, edge_box, and row_box reverse `pack_dir`; 9720b24f flanked folds two sightings into an axis.
A quarter turn off a parameter direction, with no contact: 94be5b80 carry, 96a8c0cd at and deflect, 8abad3cf rest_dir and rest_sense.
A cardinal selector with a distance read, not a contact: the rule picks a cardinal with `dir_of` or `diag_dirs`, then reads a variable distance from its edge, so the atom pair measures depth and states no contact. 95a58926 anchor_dist, 9473c6fb cand, 4c3d4a41 line_cell.
A plain border test, no reversal: 8abad3cf reaches tags the frame edges a color's square touches with `dir_elem` and a zero-distance `dist`, and the head keeps the touched edge as data. Its chain reaches no reversal of that edge: short_of negates it, and rest_sense picks the rest edge by a quarter turn off `pack_dir`.
A contact with a box that is not the frame: 941d9a10 painted and corner_color test `box_corner(P_tile, ZERO, D)` against the tile frame, and 97239e3d painted tests `box_edge(P, B, D)` against a bounding box; neither reverses the direction.

Spec:
One change stands, from a site in the near-misses. 8abad3cf declares a top-level relation named `inward`: the row read from either edge, the square one place inward of another. That relation reverses `pack_dir` with no placement, so it is a different operation under the same name, and a lib relation called `inward` would collide with it. The entry should either take another name for the operation or record that the promotion renames 8abad3cf's relation.

The three callers exercise the interface as the entry writes it, and raise nothing else. 95755ff2 source and 96a8c0cd heading each consume the heading alone, which the single Dir output serves. No solver in the scope writes the operation as a comp, so no signal here is caller-only.

Reimplementations:
5545f144 blunt — two `dist` atoms on one direction with `K <= K2`, which is `!nearer(D, T, P)`.
84ba50d3 through — two `dist` atoms on one direction with `K <= K_div`, which is `!nearer(D, L, R2)`.
The search ran the two parser passes over the 26 solvers through `dl.dlparse`, on the same shapes the result of 2026-09-14 02:10 records; the first matched 3 rules, the second none. A widened scan then listed every rule in the scope holding a zero-distance contact atom or a reversal primitive beside a frame primitive, and each hit was read in its rule.
