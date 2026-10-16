# `ahead` — one position ahead of another along its line

Two positions on one line of a cardinal axis, ordered by the direction one lies toward from the other: q sits ahead of p toward d, at any distance. Nothing between the two is tested, so the relation is a sighting through whatever stands in the way, and it carries no distance and no set membership.

```
.decl ahead(d: Dir, p: Position, q: Position) inline
ahead(D, P, Q) :- axis_of(D, A), same_line(A, P, Q), nearer(D, Q, P).
```

Not: `nearer` alone (which side of p q lies on, with no line test); `neighbor` and `jump` (a step of a fixed length); `Ray.ray` and `Slide.run` (a cast from a keyed mark set, which a blocker stops and which reports the step count and the source); `toward` (the king heading from p to a goal, diagonals included); `same_line` alone (no order); `Between.between` (a fold of two sightings against a mark set).

Match: a rule that states `same_line` on an axis beside `nearer` on a direction of that axis, over the same two positions, in either argument order. The direction may be free, may come from `axis_of` on a stored axis, or may be read from a parameter; the two atoms may sit in different lines or in a helper rule. The `dist`-written form also states it: one `dist` pair equal across the perpendicular axis beside a `<` comparison of the two `dist` values on the direction's axis. Match with the parser.

Survey: 2026-09-14 02:54 — every solver.

Callers:
29c11459 pair — pairs the two marks of one row, naming which lies ahead of the other toward d: `same_line` on the stored axis beside `nearer` on a direction of that axis.
2faf500b moved — the `$Marks` rule reads the helper `cut_cell`, which holds `same_line(A, P, M)`, then adds `axis_of(D, A), nearer(D, P, M)`: the ordinary cell lies past its own shape's mark toward d. The two atoms sit in two rules, which the entry's search signature admits.
5ffb2104 room — inside the shared `Settle` proposal comp: a cell ahead of a body cell in the heading's line, which the body may come to rest behind. The rule's own comment names the cell "ahead".
6ad5bdfd room — the same site, in the same `Settle` comp text.
84ba50d3 pierced — a divider cell a shape passed: a landed cell lies ahead of the divider cell along the fall direction, the axis read from a relation and the direction from a parameter.
8a371977 screened — another tile's cell sits ahead of a cell of this tile toward d, so d is screened for that tile.
9720b24f sees — a container cell sits ahead of an inked cell toward d.
88bcf3b4 toward — the first branch of the `toward` helper is the sighting: `axis_of(D, A), same_line(A, P, G)` under the frame's `nearer(D, G, P)`. A call would keep the frame's `nearer` atom, which the second branch also needs. The `toward` proposal entry claims this same site for its own operation.

Negative evidence over the scope: 779 solvers hold `nearer` in 75 files and `same_line` in 84; 19 files hold both. A matcher over the parsed corpus put line evidence (`same_line`, `same_dist`, `slab_anchor`, or a `dist` pair sharing one distance variable) beside order evidence (`nearer`, or a `dist` pair under a comparison) on one position pair in one rule, and returned 12 rules in 12 files. The 19 files were then read by hand for the cross-rule form. Eight solvers state the operation.

Near-misses:
5207a7b5 out, dc433765 axis_step, 28e73c20 walk — each holds the line test and the order test in two exclusive branches of one disjunction, so the two never conjoin. In 5207a7b5 the `nearer` branch paints the side of a bar and carries no line test; in dc433765 the branches choose a step or no step on one axis; in 28e73c20 the order test compares a walker against a box margin, not against a cell on its line. The exclusion is `nearer` alone.
2dd70a9a target_side, 3e6067c3 seq.before, 7e576d6e seq.before, 4a21e3da side — `nearer` with no line test at all. 4a21e3da is the closest: `on_cut` holds `same_line` on the cut's axis, but `side` orders cells on the perpendicular axis, so the two do not compose. The exclusion is `nearer` alone.
3e6067c3 corridor — holds both, but the order partner is a bounding box side (`bbox.box`) while the line partners are label cells, so no one pair carries both tests. The exclusion is `nearer` alone.
689c358e mark, 7e576d6e elbow and span.axis — `same_line` with no order test. The exclusion is `same_line` alone.
54dc2872 moves — the `$Slide` rule states `same_line` on a diagonal axis beside `nearer` on the matching corner direction, the shape exactly, over the diagonal line family. The exclusion is the entry's cardinal axis.
c1990cce arm and within — `same_line` on a diagonal axis in one rule, `nearer` on two corner directions in another, over different partners. The exclusion is the cardinal axis and `nearer` alone.
3979b1a8 out — `same_line` on the arm's axis beside `dist(P, O, Kp), dist(M, O, Km), Kp <= Km`. The comparison is non-strict, so the rule admits the cell level with M, which the strict operation excludes. The exclusion is the strict order; `nearer_eq` names this comparison.
52df9849 sweep — the order test is the solver-local `nearer_eq`, non-strict, and its partner cell is quantified apart from the `same_line` partner.
1da012fc behind, 20a9e565 target, 29c11459 walk, 2bcee788 short_of, 3d588dc9 short, 5545f144 blunt, 84ba50d3 through, 88bcf3b4 nearest.cand, 896d5239 filled — the non-strict comparison written from two `dist` atoms, with no line test. A scan for a `dist` pair on one direction under a comparison returned 13 rules corpus-wide, and every one of them is non-strict. These belong to `nearer_eq`.
0ca9ddb6 ring_cell (in Determine), 11e1fe23 sees, 1d398264, 253bf280 between, 256b0a75, 264363fd, 272f95fa tile_ink, 2b9ef948 ink, 6e19193c trail — each instantiates `Ray`, populates no `blocked` fact, reads none of `clear`, `clear_cast`, `stop`, and reads the cast as `ray(Ky, P, D, K, Src), K != 0`. The step count serves strictness alone. The exclusion is `Ray.ray`.
0f63c0b9 beaten — compares two `Ray` step counts, which the cast reports as data. 271d71e2 ahead — a relation under the operation's own name, but a `Ray` cast with a blocker. The exclusion is `Ray.ray`.

Spec:
The cardinal restriction should go. Lib already carries the wider domain: `same_line` takes an `Axis4`, `nearer` takes a `Dir8` and compares corner distances at a corner, and `axis4_of` pairs the two. Widening the signature to `ahead(d: Dir8, p: Position, q: Position)`, with `axis4_of` in place of `axis_of`, changes no cardinal caller and adds 54dc2872 `moves`, which writes the diagonal instance in full. The diagonal sighting is exercised beyond that one site: c1990cce holds diagonal line and order tests, and 11e1fe23 `sees` casts a diagonal sighting through `Ray`. This rests on sites in both parts, not on the surfacing solver.

The `Ray.ray` exclusion should name the property, not the relation. The Not line rules `Ray.ray` out as "a cast from a keyed mark set, which a blocker stops and which reports the step count and the source". At the nine sites listed above, none of those three properties holds: no `blocked` fact is fed, and `k` is read only as `!= 0`. Under the current wording a survey reads them as excluded by relation name, while the stated ground does not reach them. The exclusion should state that a `Ray` instance with a blocker, or one whose `k` or `src` is read as a value, is the cast and not the sighting. Whether the remaining `Ray` sites then count as callers is the judgment the entry has to record; the wording change is what the sites argue for.

Strictness needs no change. Every non-strict site the scan met falls to `nearer_eq`, whose entry already holds that comparison and its sites.

Reimplementations:
20a9e565 slot — `sbox.box(Id, B), dist(B, Td, T), axis_line(Lg), dist(Lg, Td, T)` states that the box and the line agree on the distance toward the trail direction, which `same_dist` holds.
ca8f78db out — two `split` atoms sharing the along component put the clean source cell on the corrupted cell's line, which `same_line` holds. The second `split` also supplies `Across2` for the `pattern_row` test, so the atom stands for a further read.

The matchers, the `Ray` scan, and their output are under the scratch path the brief gave. Search method: four parser matchers over `dl.corpus.each_solver`, plus hand reading of the 19 files that hold both `same_line` and `nearer` and of every hit above. Hit counts: 12 rules for the one-rule shape, 13 for the `dist` comparison form, 1 for a hand-written `same_dist`, 1 for a `split`-shared line, 50 `Ray` instances with no blocker of which 9 read `k != 0`.
