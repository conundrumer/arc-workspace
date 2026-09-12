# `Bbox.place` — a box's place among the boxes beside it

A per-key readout on `Bbox`: the Position whose distance toward each edge is the number of distinct box-edge distances nearer that edge, counted over every key of the instance. It is where a box sits in the arrangement its siblings form — the row and column of a contact sheet, read with no end privileged and with no assumption of even spacing. Boxes level with each other share a place coordinate, so a band of them lands in one row.

```
// inside Bbox<Key>
//
// Flagged: assumes one arrangement per instance. The count runs over every
// key, so two arrangements under one instance rank against each other.
// Flagged: assumes the boxes of a lane share an extent. Each edge ranks on its
// own, so two boxes level at one edge and unequal in extent take different
// ranks at the opposite edge, and their places carry unequal per-axis extents.
.init _rank = Ordinal<Dir>
_rank.idx_set(D, K) :- edge_min(_, D, K).

.init _pack = DirPack<Key>
_pack.edge(Ky, D, R) :- edge_min(Ky, D, K), _rank.rank(D, K, R).

.decl place(key: Key, p_place: Position)
place(Ky, P) :- _pack.pos(Ky, P).
```

Not: `OrderFrame.pos` (ranks members by counting members, so two members abreast on one axis push the next member two places on); `Ordinal.rank` alone (one axis, a number, no Position); `DiagPlacement.quadrant` (which half of a joint span a box lies in, two values per axis, not a rank among the boxes); `DividerFrame.tile_of` (a cell's tile, counted off drawn dividers, not a set's own place among other sets); `margin` (the box's placement in cells).

Match: an `Ordinal` keyed by `Dir` whose `idx_set` is a per-key edge distance of a box set, feeding a `DirPack` over the same distances. Also the hand-rolled forms: a per-axis rank pair packed into a Position without `DirPack`, and a rank counted with an explicit `count` aggregate over the edge distances. `grep -n 'Ordinal<Dir>' programs/solvers/*.dl` is a starting point only; the shape is matched with the parser.

Survey: 2026-09-09 01:06

The pass read all 572 solvers: every `Ordinal`, `DirPack`, `OrderFrame`, `Order`, and `LexOrder` instance, every file reading `Bbox.edge_min`, and a parser match for two per-axis readouts of one relation composed into a Position. The corpus holds no raw `count` aggregate, so the third hand-rolled form of the match has no site.

## Callers

- `19bb5feb` — `place`: the markers' relative arrangement is the output grid, one cell per marker.
- `58f5dbd5` — `tile`: the `$Arrange()` case lays each block out at its place in the arrangement.
- `4be741c5` — `place`: ragged color bands stack along one axis. An `Extremes` takes each band's leading-line distance toward each end, an `Ordinal` ranks those distances, and the `out` rule packs the two ranks with `axis_delta`. A band's line set reaches both perpendicular edges, so a box over that set has perpendicular `edge_min` 0 for every band and the four-edge form returns the Position the solver builds by hand.

## Near-misses

- `0a1d4ef5` — `layout.pos` (`OrderFrame`). A band there is a grouping, not a level: `train0 input` holds the `8` block at rows 17-21 and the `1` block at rows 18-22 in one band, so distinct box-edge distances give four lanes where `train0 output` has three rows.
- `1990f7a8` — `quad.quadrant` (`DiagPlacement`). It reads which half of the boxes' joint span each box lies in, two values per axis. `train0 input` has box tops at rows 2, 5, 12, 13, so a rank gives a 4×4 arrangement where `train0 output` is 2×2.
- `1190e5a7`, `458e3a53`, `1be83260` — `layout.pos` / `hole_frame.pos` (`OrderFrame`, one instance per axis, composed). Their members are lines fed as `member(A, L, L)`, so there is no box set to hang a readout on.
- `e1baa8a4` — `place` (`DirPack`). A rank packed per Dir into a place Position, but the count runs over the boundaries between unlike lines and the key is a cell; the solver holds no box set.
- `291dc1e1` — `reading.rank` (`LexOrder`), and `1da012fc` — `reading.rank` (`Order`). A total order over the members, one number each, read from a privileged corner and primary axis.

## Spec

Two questions, each argued from a caller other than the surfacing solver.

- **The rank's domain.** `place` counts over every key of the instance, which fits a solver holding one arrangement. `4be741c5` holds two: its `place` is keyed `[Ch, D]`, and the two cases give different band sets, so ranks counted over the union inflate and both cases come out wrong. `Bbox<Key>` keys on the box, so a grouped reading cannot be a `Bbox` readout without folding the group into the box key, which is what breaks the count. Either the `Flagged` note above stands as the operation's assumption, or the operation moves off `Bbox` into a comp keyed by (group, member) taking each member's per-Dir edge distance as an input. `4be741c5` argues for the second form on its own: its members are line sets, its per-Dir distance comes from `Extremes.low`, and it never builds a box.
- **Unequal boxes.** Ranking each of the four edges on its own makes a box's place depend on its own extent, which the second `Flagged` note states. Both `19bb5feb` and `58f5dbd5` hold equal boxes, so neither witnesses it; `0a1d4ef5`'s blocks vary in size and band differently at their near and far edges. The alternative is to rank from one direction per axis and derive the opposite index from the lane count.

Survey: 2026-09-09 21:19

The second survey read the 104 solvers whose file time is at or after the first survey's dispatch. It found no caller beyond the two the entry lists, both edited since with the operation unchanged, and no near-miss outside the classes the `Not:` line names. To record: `668eec9a` ranks one edge's distances into a row index (`Ordinal.rank` alone), and the four-edge form is wrong there — see below; `652646ff` packs a rank pair from the occlusion order over colors, with no box set and no edge distance; `5ecac7f7` ranks shapes within their panel and panels within the grid through `OrderFrame`; `3a25b0d8` ranks box edge distances into a number that pairs holes across two figures. Both spec questions gain a second site:

- The rank's domain: `5ecac7f7`'s `shape_order` is group-keyed — the shapes of one panel rank among themselves — so under `Bbox<Key>` every panel's shapes would rank in one count. With `4be741c5` it argues for the comp keyed by (group, member); like `4be741c5`, it holds no box set and feeds its members as line sets.
- Unequal boxes: `668eec9a` witnesses the second `Flagged` note. Its four lines' bottom `edge_min` values are 0, 0, 1, 0 against top values 5, 10, 12, 15, so per-edge ranks collapse three lines into one bottom coordinate and only the top coordinate carries the arrangement. It supports ranking one direction per axis and deriving the opposite index from the lane count.

Box (2026-09-11): The readout reads `box(_, B), dir_elem(D), dist(B, D, K)` where it read `edge_min`, and `DirPack`'s readout is `box`, so the pack line is `place(Ky, P) :- _pack.box(Ky, P)`. The output column stays `Position` under the typing rule: the four ranks sum per axis to the lane count less one, so the pack carries the arrangement's own extent, and `19bb5feb` reads that extent off it with `axis_dim` to build the output frame. `19bb5feb` writes the whole construction by hand today, an `Ordinal<Dir>` over `dist` feeding a `DirPack<Ident>`. The `Not:` line's `margin` is `box`. The operation and both Spec questions stand, since neither the rank's domain nor the per-edge ranking turns on a name. See docs/wf-solver/box.md.
