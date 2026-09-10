# `near_edge` — a position's nearer edge on one axis, with its distance

The edge of the axis half a position sits in, paired with the distance to it: which side the position anchors to, and how deep it lies from that side. It is the Dir-carrying peer of the `axis_near` functor, which yields the distance alone, and the sorted readout of `dist_pair`, which yields both distances in a fixed direction order. The known sites write a `dist_pair` atom and order its two distance columns against each other.

```
.decl near_edge(p: Position, d: Dir, k: number) inline
near_edge(P, D, K) :- dist_pair(P, D, K, K2), K <= K2.
```

A centered position lies in both halves of its axis, so it yields both edges of that axis, each at the same distance.

Not: `nearer` and the `nearer_eq` proposal (two positions compared toward one direction, not one position's own two edges); `edge_depth` (the least over all four edges, with no direction); `corner_shell` and its `corner_near_far` question (the two edges of one corner, one per axis); `dist_pair` (both distances in a fixed direction order, with no pick); `DiagPlacement.nearer` (the strict side test, without the distance, inside a comp about quadrants and rings).

Match: a rule holding `dist_pair`, or two `dist` atoms at a direction and its opposite, whose two distance variables feed one `<`, `<=`, `>`, or `>=` against each other. Grep `dist_pair` and confirm the comparison.

Survey: 2026-09-08 23:15

Result: over the corpus as of 2026-09-08 23:15, the signature matches 24 rules in 23 files, none of them a `// family:` sibling. Two rules keep the distance that the comparison picks, and they are the operation. Of the rest, 13 rules bind the two distances only to name the half the position sits in and drop the distance, 5 read the far end, 3 compare distances on two different axes, and 3 compare one position's distances against another position's.

Near-misses:

- The strict side test with the distance discarded — `dist_pair(P, D, K, K2), K < K2` read for `D` alone — stands at 13 sites in 12 solvers: `1bfc4729`, `2204b7a8`, `27a77e38`, `29c11459`, `2faf500b`, `48634b99`, `4e45f183`, `705a3229`, `ce9e57f2`, `e7dd8335`, `f25ffba3`. `27a77e38` states in a comment that the centered line is in neither half, so the non-strict boundary is wrong there.
- Far-edge readings pick the distance this operation does not yield, at the opposite direction: `18419cfa` `far_cell` and `3a25b0d8` `off_side` (both under a universal, as defect witnesses), `230f2e48` `fold_dir`, `4e469f39` `arm_dir`, and `342dd610` `move`, which pairs a Shift's lean direction with its far distance.
- Two edges on different axes: `1478ab18` `right_angle` and `212895b5` `place` (corner sidedness and a wedge), and `539a4f51` `shell`, which the `corner_shell` entry claims.
- Two positions compared: `0a938d79` `lead`, `2ccd9fef` `drag`, and `5545f144` `blunt`, which the `nearer_eq` entry claims.
- Both distances with no pick — a repeated variable, a disequality, or a fixed direction order: `00576224`, `212895b5`, `27a77e38`, `29c11459`, `31f7f899`, `3bdb4ada`, `3cd86f4f`, `4290ef0e`, `4e7e0eb9`, `54d82841`, `8d5021e8`, `c48954c1`, `d23f8c26`, `e633a9e5`. `20981f0e` `clear_step` tests each distance against 0 separately.

Spec question: the sites argue for no change. The non-strict boundary is the load-bearing part of the interface, and both callers depend on it — 57edb29d states that a centered mark anchors to both edges, and dce56571 reads a centered cell of an odd-extent line at its own distance. The survey instead raises the `DiagPlacement.nearer` exclusion: the strict, distance-free side test is hand-written at 13 sites across 12 solvers, and lib holds it only inside a comp about quadrants and rings that those solvers have no other use for. That operation is not this one, and the exclusion stands, but its solvers are evidence for a separate entry. Two of those sites need it under negation, so a form whose clauses introduce the distances would not serve them, as lib records on `nearer`.

Survey: 2026-09-09 21:41

Result: delta over the 299 solvers `since "2026-09-08 23:15"` lists. No new caller: the signature matched 16 rules in 15 files, and only 57edb29d `anchor` keeps the distance the comparison picks. No reimplementation of a lib primitive. The spec is unchanged.

New near-misses, in the existing classes:

- The strict, distance-free side test gains `642248e4` `tail` (line 24), so that shape stands at 14 sites in 13 solvers corpus-wide.
- Two positions compared: `3d588dc9` `short` (line 95), and `52df9849` `nearer_eq` (lines 23–25), which states the non-strict two-position comparison as its own inline relation; the `nearer_eq` entry claims both.
- `25d487eb` `margins` (line 45) takes an extremum over one Position's four edge distances through `ArgExtremes` and reads the direction alone — the four-edge, distance-free shape the `edge_depth` exclusion names.

Callers:

- 57edb29d — `anchor`, a mark's distance to the nearer edge of its own panel on each axis, which a target panel's cell repeats on both axes to place the design.
- dce56571 — `center_line`, the distance from a cell of the across-centered line to the nearer edge of the task axis, read as the cell's centrality and fed to an `Order` over the line's cells.
