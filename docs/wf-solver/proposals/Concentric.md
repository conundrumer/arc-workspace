# `Concentric<Key>` — the boxes one repeated inset generates

The family of boxes a seed box generates under one repeated inset, per key: each box is the one before it let out by that inset, and the run ends where a box covers no cell of the domain. A solver that draws rings at a fixed spacing, or that reads which ring a cell sits on under such a family, names the family in one instance instead of closing the inset in a rule of its own.

Solver-local form (5c2c9af4), where the seed is the center cell as a degenerate box, the inset carries the center out to the innermost ring, and the clip is mutual recursion with `BoxCells` — the run continues from a box that still draws a cell:

```
.decl outline(b: Position)
outline(B) :- center(B).
outline(B2) :- bcells.on_edge(B, _, _), spread(V), compose(B, V, B2).

.init bcells = BoxCells<Position>
bcells.box(B, B) :- outline(B).
bcells.cell(B, P) :- outline(B), in(P, _).
```

Comp form:

```
.comp Concentric<Key> {
    // The box the family runs from, per key.
    .decl seed(key: Key, b: Position)  // input

    // The inset from each box to the next, per key.
    .decl step(key: Key, v: Inset)     // input

    // The cells the family is read over, per key.
    .decl cell(key: Key, p: Position)  // input

    // The seed, and every box the step reaches from it. A box covering no
    // cell ends the run, and so does every box beyond it.
    .decl box(key: Key, b: Position)
}
```

Not: `Outset` (one box let out, with the band between the two read off it); `LatticeOrbit` (a translation lattice over frame cells, whose `(axis, period)` generator states a shift and cannot state an inset); `BoxCells` (the cells of one box); `edge_depth` and `corner_shell` (a cell's ring index under a family anchored on the frame or on a corner, with no seed and no spacing); `Rim.depth` (rings that follow a set's own shape); one inset with no closure over it.

Match: a head-recursive rule over a Position read as margins whose step composes a fixed `Inset`. Grep: `uniform_delta`, `compose(` and `displacement(` sites whose box argument comes from `Bbox.margin` or from a relation the same rule heads. Shape: a rule whose head relation occurs in its body, where the recursive Position column also feeds `BoxCells.box`, `Bbox.margin`, `BoxCells.hole`, or `geq` as margins.

Spec questions:

- Whether `box` carries a ring index beside the box, for a caller that colors or selects per ring.
- Whether the run goes both ways from the seed, or one way along the inset as written.
- Whether the clip is "the box covers a domain cell" or a margin test against the frame.

Survey: 2026-09-09 02:56

The survey read the whole corpus, 584 solvers. A head-recursion test alone misses 5c2c9af4, whose recursion passes through its `BoxCells` instance, so the shape matcher collapsed each comp instance to one node, took the recursive cycles over that graph, and kept the cycles holding a step atom together with a box-as-margins consumer. That signature matched 12 files. Besides 5c2c9af4, three of them close a step over a box or over a box's placement — 4522001f `fit_box`, 28e73c20 `walk`, and 16b78196 `seat_step` — and each is a near-miss below. The remaining eight close over cells. Of the 10 `uniform_delta` lines in the corpus, every one but 28e73c20's is a single placement or a depth-to-box conversion with no closure. Of the 27 rules holding a box margin together with `compose` or `displacement`, every one but 5c2c9af4's two translates a box by a Shift, seats content in a box frame, or reads the offset between two boxes.

Near:

- 28e73c20 `walk` closes `params.inset` over the spiral's turn box, one inset per cycle. The box family is the walk's own state, and the consumer needs each box paired with the walk step standing on it, which a `box` set with neither index nor successor cannot give.
- 4522001f `fit_box` writes the spec's rule shape exactly — a seed from `sq.margin`, a recursive `compose` of one fixed delta, and a clip — but the delta is a Shift built from two `jump_delta`s, so the family marches along the diagonal at constant size instead of nesting. Its `grow_box` is the same rule with the recursion dropped.
- 5587a8d0 `covers` grows a nested-ring family from a degenerate seed at ORIGIN, by a `dir8_elem` dilation over a set of Shifts rather than an inset onto a box, and its run length is the patch count along `nest.next` rather than a clip.
- 16b78196 `seat_step` composes `box.margin` with a placement delta and clips by `geq(M2, ORIGIN)`, but its recursion carries that delta rather than the box, and the step varies per host-and-piece contact, so no single delta generates the run.
- 5751f35e `layer` converts a `Rim` depth into a box with `uniform_delta` and reads cells off it with `geq` — the closest the corpus comes to `box` as a readout — with no seed, no spacing, and no closure.
- The classes the `Not:` line already names: one box let out with no closure (3a301edc, 52fd389e, 543a7ed5, 58f5dbd5, 49d1d64f, 412b6263, ed74f2f2); rings at spacing 1 off the frame or a set's own shape (85c4e7cd, 45a5af55, 3ee1011a, 4290ef0e, 5751f35e `peel`, 516b51b7, 13e47133, 52364a65, 522fdd07); nested L-shells at a corner (539a4f51) and rings about a corner (ca8de6ea); `BoxCells` over one box per key (1a6449f1, 1c786137, 4c7dc4dd, 5b526a93); a box-shaped cell set translated once (2b9ef948); and a nest that arrives as data (40f6cd08, 3befdf3e).

Spec: every signal the three questions could take rests on the one caller. On a ring index, the two sites that would need the family ordered are 28e73c20 and 5587a8d0, and each is a near-miss on an independent ground, so neither becomes a caller if the index is added. No site in the corpus runs a box family both ways. On the clip, 4522001f is the one other clipped box run and it writes the margin test, but its Shift step rules it out; 5c2c9af4's own outlines continue past the grid edge and draw partial rings, which `geq(B, ORIGIN)` would cut short.

Survey: 2026-09-09 03:12

A delta over the eight solvers written or edited after the first survey's time — 5daaa586, 5d588b4d, 4ff4c9da, 5dbc8537, bdad9b1f, 22eb0ac0, 137f0df0, 5e6bbc0b. No caller, no reimplementation, and no signal on the three questions: no site in that scope runs a box family, and no recursion cycle in it carries a Position. Its nearest site is 5daaa586's `box`, a `BoxCells<Unit>` fed from `crop.margin` — the caller's own wiring, over a single box with no step to repeat, so it joins the `BoxCells` class the `Not:` line names.

Callers:

- `programs/solvers/5c2c9af4.dl` — `outline` with its `BoxCells<Position>` instance. The seed is the center cell as a degenerate box, the inset carries the center out to the innermost ring, and the run ends where an outline draws no grid cell.
