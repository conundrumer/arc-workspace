# `Settle<Key, Body>` — rigid bodies coming to rest against one another

The displacement each body of a keyed set takes when every body travels toward one heading and stops where it first meets the frame edge, a blocked cell, or a body at rest ahead of it: gravity over rigid bodies. A body's cells all carry the same displacement, so the body rests at the least room its cells leave it, and that room reads the rest of the body ahead — the minimum and the mutual blocking sit in one recursion, which no aggregate or stratified negation states. A subsumption clause settles the minimum, comparing two travels along the heading as `nearer` over the shifts themselves, and subsumption is not program style, so the operation enters as a proposal comp:

```
.comp Settle<Key, Body> {
    // The cells of each body, per key.
    .decl cell(key: Key, b: Body, p: Position)  // input

    // The heading every body travels, per key.
    .decl dir(key: Key, d: Dir)  // input

    // Cells no body may enter, per key: the static floor.
    .decl blocked(key: Key, p: Position)  // input

    // What one cell of a body leaves it room for.
    .decl room(key: Key, b: Body, delta: Shift)
    room(Ky, B, Delta) :-
        cell(Ky, B, P), dir(Ky, D),
        ( dist(P, D, K), jump_delta(D, K, Delta)                            // travel to the frame edge
        ; axis_of(D, A), same_line(A, P, Q), nearer(D, Q, P),               // a cell ahead in the line
          ( blocked(Ky, Q), Q2 = Q                                          // a static cell, in place
          ; cell(Ky, B2, Q), B != B2,                                       // another body's cell
            rest(Ky, B2, Delta2), compose(Q, Delta2, Q2)                    // where that cell rests
          ),
          opposite(D, D2), neighbor(Q2, D2, P2), displacement(P, P2, Delta) // travel to just behind it
        ).

    // Where a body rests: the least room its cells leave it.
    .decl rest(key: Key, b: Body, delta: Shift)
    rest(Ky, B, Delta) :- room(Ky, B, Delta).
    rest(Ky, B, Delta) <= rest(Ky, B, Delta2) :- dir(Ky, D), nearer(D, Delta, Delta2).
}
```

Every body has the edge room from the first iteration, so a body publishes a rest before its blockers have settled. Such a rest is too far along the heading, the room it yields a follower is too large in turn, and the room read off the blocker's own rest subsumes it; the fixpoint descends to the physical rest and stops there. Where two bodies block each other in different lines, the descent still terminates, on a configuration that has no gravity reading.

`blocked` is the static floor, as `Ray.blocked` is: a body rests behind a blocked cell as it rests behind a settled body, and a blocked cell never travels. Fed the edge line of a wall, it lets bodies pile against the wall instead of onto it.

Not: `Dock` (one mover against a stopper set fixed before the travel, with the rest found by a step-by-step walk over the frame's displacements; with one body per key and `blocked` as its stoppers, Settle computes the same rest); lib `Slide` (a point mover resting on the last free node of a set); per-line packing by rank, where the movers are cells rather than rigid bodies and each line packs on its own (1e0a9b12, 3906de3d); `CoverForcing` and `PlacementPruning` (pieces placed by elimination, with no heading and no travel); a settling that a global order over the bodies sequences, each body placed against those already down; a translation read off a named target with `displacement`.

Match: a recursion over object displacements — a relation carrying one object's travel whose rule reads another object's travel — or a solver that moves several objects toward one heading and derives each object's travel from a contact test against the moved cells of the others. Grep `rest(`, `room(`, `settle`, `pile`, `stack`, and `<=` at a clause head over `programs/solvers/`. Also `// keywords:` lines carrying both `objects` and `move`, and headers naming gravity, piling, or stacking.

Survey: 2026-09-09 04:18

Result: no second caller, over all 590 solvers. A `<=` clause head occurs once corpus-wide, in this comp. `room(` matches this solver alone; `rest(` matches thirteen files, and every other one reads a lib `Slide` instance, walks a single mover, probes a seat, or names something unrelated. Nineteen relations in sixteen files carry a Shift column and reach themselves positively, and each is a single mover's step walk, a chain a named order sequences, or a growth walk — none derives one body's travel from another's. Thirty-five solvers carry both `objects` and `move` on their concept line, and this one alone states mutual blocking; header prose naming gravity, piling, falling, or coming to rest turns up cell-level and line-level packing only.

Callers:

- 5ffb2104 — every non-background object of one color slides toward one edge and piles against the objects ahead of it.
- 6ad5bdfd — objects of several colors slide toward the edge a wall line fills and pile against the wall and one another; the wall cells feed `blocked`.

Near-misses:

- 17829a00, 05f2a901, 11dc524f — a mover walks and halts, with the stopper set fixed before the travel and no mover reading another's rest. `Dock`.
- 4c3d4a41 — a line's contents move as one rigid body onto a named seat cell, and `displacement` reads the travel.
- 234bbc79 — a true recursion over object displacements toward one heading, sequenced by a global chain order, each piece's destination read off its predecessor's joint with `displacement`.
- 16b78196, 5dbc8537 — recursions over object displacements whose pieces interlock by face fit and survive by refutation, with no heading and no travel.
- 025d127b — several shapes under one heading, with blocking propagating between them, but the movers are cells tested one at a time rather than bodies carrying a displacement.
- 4df5b0ae, 4acc7107, 25c199f5 — rigid bodies coming to rest side by side, each given its slot by a global rank, with no contact read.
- 320afe60, 5623160b — a body jumping flush to the frame edge in one hop off `box.edge_min`.
- 05a7bcf2, 9c56f360 — per-line packing by rank, where the movers are cells.

Spec question: should a fixed stopper input, in the manner of `Ray.blocked`, join the interface, so that a body can rest against static content? `room`'s first branch takes the frame edge as the only floor. Five near-misses rest against static content that way, and every one of them holds a single body per key, so the recursion that distinguishes this operation would sit inert in each; the input would make this comp subsume `Dock` and lib `Slide`, which the `Not:` line separates it from, and would gain no site whose travel needs the recursion. Two further signals rest on the one caller: `dir` is one heading per key rather than per body, and it is typed `Dir`, so the settling is axis-aligned.

Survey: 2026-09-09 04:39, over the solvers at or after the first survey's time

That pass read the four solvers whose file time is at or after 04:18. It found no caller: no `<=` clause head occurs outside this comp, and the delta's four self-recursive travel relations are the one `Dock` step walk written three times, each advancing a single mover's own displacement against a stopper set fixed before the travel. The pass adds one detail to the spec question. `17829a00` travels several bodies under one heading, so it is the corpus's nearest multi-body traveler; it keys each body by its own `Ident`, and its stoppers are the cells abutting the colored border, so no body there reads another's rest and the recursion would still sit inert.

The 6ad5bdfd site answers the spec question: it is a multi-body pile whose floor is static content, so `blocked` joins the interface there, and the recursion is live at the only site that feeds it.

Survey: 2026-09-10 00:57, over the solvers at or after the second survey's time, with `blocked` in the spec

That pass read the 318 solvers in the delta. It found no third caller. A subsumption clause head occurs twice in the scope, both the comp's own `rest` clause (5ffb2104, 6ad5bdfd). Forty relations in 33 files carry a `Shift` or `Position` column and reach themselves positively while composing a displacement; apart from the two `Settle` copies, each is a single mover's step walk, a ray or spiral cast, a growth or reflection walk, a lattice, or a join chain with no heading. Five files instantiate lib `Slide`; one moves a point (18286ef8), and the other four walk a body's own shift domain against a stopper set fixed before the travel. Thirty-one solvers carry both `objects` and `move` on their concept line, and the two `Settle` sites alone state mutual blocking.

Near-misses:

- 4e34c42c — a recursion over object displacements that composes joins along fit edges, with no heading and no travel.
- 1caeab9d — every block's front line aligns to the anchor block's front line with `displacement`, and a block may cross the anchor's line.
- 182e5d0f, 494ef9d7, 54dc2872, 581f7754, 18447a8d, 2c181942, 67c52801 — a body or cell lands on a named seat, by `displacement`, a neighbor read, or a fitted margin.
- 234bbc79, 4acc7107, 291dc1e1, 20818e16, 25c199f5, 4df5b0ae, 652646ff, 668eec9a — bodies stacked by a global order or rank, each placed against the ones already down, with no contact read.
- 337b420f — one shape slides the shortest distance that clears an overlap: it travels until free, not until blocked.
- 5e6bbc0b, 3d6c6e23 — per-line packing of cells by count, the movers being cells.
- 1acc24af, 6a1e5592 — pieces placed by fit over a notch, with no travel.
- 045e512c, 53fb4810, 5587a8d0 — a body's copies march or rings grow along a step; a growth walk, not a rest.

Dock-shaped near-misses, a single body per key against a stopper set fixed before the travel, whose rest `Settle` computes with `blocked` fed that set:

- 17829a00 — `Slide<Ident>`: several bodies, each under its own key, each walking toward the border of its own color. No pair or test input puts two same-heading bodies in one line, so the recursion would sit inert.
- 05f2a901 — `Slide<Choice>`: one mover against the anchor's cells, the contact varying per case.
- 11dc524f — `Slide<Unit>`: one shape against the mirror block's edge.
- 56dc2b01 — `Slide<Unit>`: one shape against a full-grid line.
- 4c3d4a41 — each line's contents move as one body onto the seat one step past the comb's high end, read with `displacement`.
- 320afe60, 5623160b, 62593bfd — several bodies jump flush to the frame edge by `box.edge_min`, with no stopper set but the edge; no two same-heading bodies share a line, so none witnesses a pile.

Spec: the delta's static-floor sites all hold one body per key, and 17829a00's several bodies never share a line, so the only site where `blocked` and the recursion are live together is 6ad5bdfd. Two details from that call site: `dir` is derived there, as the cardinal the wall does not stand off, and `blocked` is fed the whole wall, not its edge line.
