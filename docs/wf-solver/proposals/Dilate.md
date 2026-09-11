# `Dilate<Key>` — the outward distance from a cell set

The depth of each cell of a domain outward from a keyed seed set: the seeds at 0, and each further cell one step more than its nearest seed-side neighbor, stepping toward the key's directions. Level sets are the rings that repeated dilation of the seeds adds, so equality names a ring and comparison ranks cells by nearness to the set. It is the outward peer of `Rim.depth`, which walks inward from a set's own rim: `Rim.depth` over the domain's complement gives these values except at the frame border, which `Rim` counts as outside. A solver picking the object or marker nearest a shape, or painting bands around a shape at successive widths, states that with one atom.

```
.comp Dilate<Key> {
    .decl seed(key: Key, p: Position)  // input
    .decl cell(key: Key, p: Position)  // input
    .decl dir(key: Key, d: Dir8)  // input

    // The shortest outward walk from the seeds.
    .decl depth(key: Key, p: Position, k: number)
    depth(Ky, P, 0) :- seed(Ky, P).
    depth(Ky, P, K2) :-
        depth(Ky, Q, K), K2 = K + 1,
        dir(Ky, D), neighbor(Q, D, P), cell(Ky, P).
    depth(Ky, P, K) <= depth(Ky, P, K2) :- K2 < K.
}
```

Call site (6df30ad6): one instance keyed by ring shape, `$Square` stepping over `dir8_elem` and `$Diamond` over `dir_elem`, both seeded by the gray shape over every grid cell; the two depths at a dot rank the dots by nearness.

Not: `Rim.depth` (erosion, inward from the set's own rim); `MinHops` (closed: fewest hops over a caller-built edge relation); `Reach` (seeded flooding with no distance); `Outset` (the band at a given width around a box, whose rings are square whatever the box holds); a one-step band around a set (`dir8_elem(D), neighbor(P, D, Q)` off a set, with no further ring), which is depth 1 alone and needs no fold; `Ray` (straight-line step counts from marks, which reach no cell off the eight lines); `Bbox.edge_min` (a set's least distance per frame edge); `corner_shell` and `edge_depth` (distances to the frame's corners and edges, not to a set).

Match: a recursive rule that derives a depth from a depth at a neighbor with `+ 1`, from a base of 0 over a set that is not the rim of the walked set, with subsumption or a min aggregate keeping the least; or an `Extremes`/`ArgExtremes` fold over such a depth. Also the unfolded form: a chain of band relations each stepping `neighbor` off the previous band and negating the earlier bands, or a repeated `neighbor` walk carrying a step count. Grep `+ 1` and `<= ` beside `neighbor(` in `programs/solvers/*.dl`, and `= Rim` sites whose cell set is a complement, then confirm the seed set and the readout with the parser (`tests/test_ast_match.py`).

Survey: 2026-09-10 01:47

Result: over the corpus, 635 solvers, no site but the surfacing one derives a depth with a step count and a minimum: `+ 1` occurs in no other solver, and the only other subsumptive clauses settle a mover's rest Position (5ffb2104, 6ad5bdfd, the `Settle` proposal). Every recursive step over `neighbor`, `jump`, or `compose` is a tile reflection, a period jump, a directional flood, a spiral or turtle walk, or a straight run. Every `.depth(` read outside the surfacing solver is `Rim.depth` walked inward from the walked set's own rim. No `Rim` instance overrides `dir`, and no `CycleWalk` builds `succ` from `neighbor`.

Near-misses:

- 13e47133 `rim`, a `Rim8` over the complement of the walls, read as `$Peel` depth. Its header states that the grid edge bounds a region like a wall, so the off-frame-as-outside reading of `Rim` is the concept there.
- 3ee1011a `rim`, 4290ef0e `peel`, 45a5af55 `peel`, 516b51b7 `rim`, 5751f35e `peel`, 639f5a19 `rim`, 85c4e7cd `peel`: `Rim.depth` walked inward from the walked set's own rim.
- 0f63c0b9 `reach`, 332202d5 `nearest`, 3490cc26 `nearest`, 13e47133 `$Sight`, 0962bcdd `$Ray`, 1b8318e3, 0ca9ddb6, 3ac3eb23: step counts along lines, `Ray`.
- f0df5ff0 `painted`, dc1df850 `halo` with its sibling 4258a5f9, a9f96cdd `halo`, 10fcaaa3 `halo`, 36fdfd69 `mark_ring`, 1b8318e3 `beside`: one step off a set, no further ring.
- 6c434453, 60a26a3e, 54d82841, 46c35fc7, d9fac9be: a universal over a cell's neighbors, the `Surround` proposal's callers.
- The `Reach` instances and the directional floods 3d6c6e23 `cone` and 5207a7b5 `region`: seeded flooding with no distance.
- 52fd389e `ring`, 5c2c9af4 `outline`: square rings from a box, `Outset` and `Concentric`.
- 52364a65 `layer`: a single-edge distance inside a bounding box.
- 2072aba6 `checker`: a lockstep closure from a corner cell that advances a two-color cycle each step, the parity of a depth with no count and no minimum; the `IndexCycle`/`CycleWalk` reading.

Spec question: whether the step directions arrive as a keyed `dir` input or by a `Dilate8` subclass, and whether `Rim.depth` derives through this comp.

- The corpus precedent for an adjacency choice is one instance per adjacency under a subclass: `Rim`/`Rim8`, `Components`/`Components8`, 239be575's `orth = Components<Unit>` beside `diag = Components8<Unit>` for a Choice over adjacency. The keyed `dir` rests on the surfacing solver alone, which keys `dir` by ring shape so that one instance serves both growths and a rule reads the other growth's depth through it. No other site steps a distance over a non-structural direction set.
- The eight `Rim.depth` sites all seed at the rim and never supply a seed, and the surfacing solver's task has no rim concept, so one comp with a supplied seed serves neither side. `Rim` can keep `depth` on its interface and derive it by nesting this comp (seed = `rim`, cell = `cell`, dir = `dir`), which removes the three duplicated rules with no call-site change; `Rim8`'s override then reaches the nested comp only through a `dir` input, for which an unkeyed `dir(d)` is enough.
- No site relies on `Rim.depth` over a complement as a route to the outward depth: 13e47133 uses the complement and wants the edge counted as a wall.

Survey: 2026-09-10 03:41

Result: over the 333 solvers `since "2026-09-10 01:47"` lists apart from the surfacing one, no new site derives a depth with a step count and a minimum. `+ 1` occurs only in 6df30ad6's `Dilate` comp; the only subsumptive clauses are that comp's and the two `Settle` sites (5ffb2104, 6ad5bdfd); no `min` aggregate appears. Every directly recursive rule stepping over `neighbor`, `jump`, or `compose` (24 rules in 22 solvers) is a tile reflection (47c1f68c), a period or panel jump (351d6448, 53fb4810, 6a980be1, 7447852a, 447fd412, 58e15b12, 4acc7107), a copy chain (045e512c, 4e34c42c), a directional flood, a spiral, turtle, beam, or wall-following walk (08573cc6, 195c6913, 212895b5, 28e73c20, 508bd3b6, 69889d6e), a mirror image (60d73be6), or a lockstep closure (1e97544e). Every rule pairing `neighbor` with a negation is a one-step test off a set. Every `.depth(` read is `Rim.depth` walked inward from the walked set's own rim. No `Rim` instance overrides `dir`; no `CycleWalk` builds `succ` from `neighbor`; the proposal comps in scope (`Wallpaper`, `Induce`, `Settle`, `Dilate` at 6df30ad6) hold no other statement of the operation.

Near-misses:

- 13e47133 `rim`, 3ee1011a `rim` (now also `core`, which nests the frames by comparing two depths), 4290ef0e `peel`, 45a5af55 `peel`, 516b51b7 `rim` in the program and a second `rim` in `Determine`, 5751f35e `peel`, 639f5a19 `rim`, 85c4e7cd `peel`: `Rim.depth` walked inward from the walked set's own rim, as before.
- 142ca369 `exposed`, 465b7d93 `field`: `Rim` over a complement (non-bg cells; the box interior minus the frame), reading `rim_dir` alone and never `depth`.
- 3d6c6e23 `cone`, 5207a7b5 `region`: directional floods with no distance, `Reach`-like.
- 1e97544e `flow`: a lockstep closure along a diagonal axis that advances a color cycle each step, the same reading as 2072aba6 `checker`: the residue of a depth with no count and no minimum.
- 89565ca0 `line`: a run extended through a hidden cell when the two cells behind it are on the line, a straight-run bridge, not a ring.
- 71e489b6 `halo`, 46c35fc7 `gap`/`ring`, 60a26a3e `ring_gap`, 6c434453 `open`, 54d82841 `walled`, 15663ba9 `faces_open`, 5034a0b5 `faces_frame`: one step off a set, no further ring.
- 516b51b7 `box_depth`: the least edge distance inside a bounding box, an `Extremes` fold over `dist`, not over a walked depth.
- 332202d5 `nearest`, 3490cc26 `nearest`: step counts along lines, `Ray`.

Spec question:

- Keyed `dir` against a `Dilate8` subclass: the scope adds no site that steps a distance over a non-structural direction set. Both callers feed `dir` a structural class: 759f3fd3 feeds `dir8_elem` under every key, so a `Dilate8` subclass would serve it with no keyed input; 6df30ad6 alone varies the class per key (`dir8_elem` under `$Square`, `dir_elem` under `$Diamond`) so one instance serves both growths. The corpus precedent in scope stays one instance per adjacency under a subclass: `Rim8` at 13e47133, 1d398264, 409aa875 (45 `Components8` against 138 `Components`), and 239be575's paired `Components`/`Components8` for a Choice over adjacency. The keyed `dir` still rests on 6df30ad6 alone: caller-only.
- `Rim.depth` through the comp: the eight `Rim.depth` readers in scope all seed at the rim and supply no seed, and the two complement-fed `Rim` instances read `rim_dir` only. Nothing in the scope relies on `Rim.depth` over a complement as a route to the outward depth, and nothing new bears on nesting the comp inside `Rim`.

Reimplementations: none found.

Callers:

- 6df30ad6 — `rings`, one instance keyed by ring shape, seeded by the gray shape over every grid cell; `first` folds `ArgExtremes` over its depth at the dots for the first ring holding a dot, and `nearest` re-reads the depth under the other key to rank that ring's dots.
- 759f3fd3 — `Parse.rings`, one `Dilate<Key>` instance seeded by the crossing of the cross, over every grid cell, stepping `dir8_elem`; its depth is the index of the concentric square ring a cell sits on, which both cases color.

Survey: 2026-09-10 19:49 — the solvers since 2026-09-10 03:41.

Callers: none.

Over the 46 solvers in scope, no site derives an outward depth from a seed set with a step count and a minimum. `+ 1` and `- 1` occur in no solver in scope; no `min` or `max` aggregate appears; no subsumptive clause appears (every `<=` is a plain bound comparison: 13e47133 `pal_len.item`, 1478ab18 `diag_dist`, 212895b5 `L`-corner sidedness, 84ba50d3 `through`, 84f2aca1 `extent_fill`, 89565ca0 `seat`). Every directly recursive rule stepping over `neighbor`, `jump`, or `compose` (045e512c `copy`, 08573cc6 `arm`, 212895b5 `turtle`, 89565ca0 `line`) is a copy chain, a spiral walk, a turtle walk, or a straight-run bridge; the other recursive rules (880c1354 `color_trail`/`obj_trail`, 0dfd9992 `out`, 97999447 `colors.succ`) are a border-cycle flood, a lattice step, and a symmetric closure. No unfolded band chain appears: every rule pairing `neighbor` with a negation is a one-step test off a set. Every `.depth(` read (13e47133 `rim`, 85c4e7cd `peel`) is `Rim.depth`. No `Rim` instance overrides `dir`; the two `CycleWalk` instances (97999447 `colors`, `slot_walk`) build `succ` from a color pair and a slot cycle, not from `neighbor`. Every `Extremes`/`ArgExtremes` fold reads a `Ray` step count (1190bc91 `nearest`, 13e47133 `sight`, 3490cc26 `nearest`) or a tally, extent, or size (045e512c `reach`, 1478ab18 `far`, 291dc1e1 `widest`, 44f52bb0 `best_id`, 84ba50d3 `widest`, 8698868d `size`, 878187ab `counts`, 89565ca0 `widest`/`ties`, 97999447 `unbroken`, b7cb93ac `pruning`/`ties`, 212895b5 `cycle`). The proposal comp in scope (`Wallpaper` at 0dfd9992) holds no statement of the operation.

Near-misses:

- 13e47133 `rim`, a `Rim8` over the open cells (the complement of the walls), read as `$Peel` depth: the header states the grid edge bounds a region like a wall, so the off-frame-as-outside reading of `Rim.depth` is the concept there, as the earlier surveys found.
- 85c4e7cd `peel`: `Rim.depth` walked inward from the walked set's own rim.
- 13e47133 `sight`, 1190bc91 `nearest`, 3490cc26 `nearest`: `Extremes`/`ArgExtremes` folds over `Ray` step counts along lines, which reach no cell off the eight lines; `Ray`.
- 880c1354 `color_trail`/`obj_trail`: a directed flood along the border cycle from a color's or object's cells to the first cell of another color, with no distance; `Reach`-like. 0d87d2a6 `reach`, 84db8fc4 `outside`, 142ca369 `Determine.flood`: `Reach` instances, seeded flooding with no distance.
- 045e512c `copy` (a copy chain by a fixed `Shift`), 08573cc6 `arm` (a spiral walk), 212895b5 `turtle` (a turtle walk), 0dfd9992 `out` (a lattice step): recursive steps with no ring and no minimum.
- 89565ca0 `line`: a run extended through a hidden cell when the two cells behind it are on the line; a straight-run bridge, not a ring.
- 142ca369 `elbow`/`no_arm`, 409aa875 `no_arm`, 264363fd `attached`, 7f4411dc `support`, 1190bc91 `seq`: one step off a set through `Rim.rim_dir`, no further ring. d9fac9be `defect`/`gap`: a universal over a cell's eight neighbors, the `Surround` proposal's caller.
- 1190bc91 `exposed`, 142ca369 `exposed`: `Rim` over the non-bg cells, reading `rim_dir` alone and never `depth`.

Spec: the scope changes nothing.

- Keyed `dir` against a `Dilate8` subclass: no site in scope steps a distance over any direction set, so nothing new bears on the keyed input. The adjacency precedent in scope stays one instance per adjacency under a subclass: `Rim8` at 13e47133 and 409aa875 beside `Rim` at 1190bc91, 142ca369, 264363fd, 7f4411dc, 85c4e7cd, d9fac9be; `Components8` at 045e512c, 2c181942, and 409aa875's `Determine` beside `Components` at 1190bc91 and 880c1354. The keyed `dir` still rests on the surfacing solver alone: caller-only.
- `Rim.depth` through the comp: the two `Rim.depth` readers in scope (13e47133, 85c4e7cd) seed at the rim and supply no seed; the two complement-fed `Rim` instances (1190bc91, 142ca369) read `rim_dir` only. No site in scope relies on `Rim.depth` over a complement as a route to the outward depth, and nothing new bears on nesting the comp inside `Rim`.

Reimplementations: none.

Survey: 2026-09-11 02:54 — the solvers since 2026-09-10 19:49.

Callers:

759f3fd3 `Parse.rings` — one `Dilate<Key>` instance seeded by the crossing of the cross (the cross cell off `cross.rim`), over every grid cell, stepping `dir8_elem` under every key; `ring` reads its depth as the index of the concentric square ring a cell sits on, which both cases color.

No second caller: over the 47 solvers in scope, no other site derives an outward depth from a seed set with a step count and a minimum. `+ 1` and `- 1` occur only in 759f3fd3's `Dilate` comp; no `min`, `max`, `count`, or `sum` aggregate appears; the only subsumptive clause is that comp's, and every other `<=` is a plain bound comparison (84ba50d3 `through`, 84f2aca1 `extent_fill`, 88bcf3b4 `nearest.cand`, 896d5239 `arm`, 8cb8642d `arm`, 8f215267's slot bound). The parser finds two directly recursive rules stepping over `neighbor`, `jump`, `compose`, or `displacement`: 759f3fd3 `Dilate.depth` and 8abad3cf `edge_off`, an offset accumulated along a row order. The other recursive rules (880c1354 `next_cell`, 88bcf3b4 `leg`/`free`/`before`, 896d5239 `arm`, 8b28cd80 `ring`, 8b7bacbf `circuit`, 8fbca751 `group.equiv`) are a border-cycle flood, a king walk toward contour cells, a chained `Ray` reach, square rings let out from a box, an object-contact closure, and a same-line closure. No unfolded band chain appears: every rule pairing a step with a negation is a one-step test off a set (84ba50d3 `off_grid`, 8886d717 `around`, 88e364bc `arrow`, 890034e9 `outline`, 891232d6 `Determine.onward_cell`, 8cb8642d `arm_end`, 8dab14c2 `dent`). Every `.depth(` read is `Rim.depth` (8dae5dfc `peel`) or the caller's own `rings.depth`. No `Rim` instance overrides `dir`; the one `CycleWalk` instance (759f3fd3 `colors`) builds `succ` from `params.ring_succ`, a color cycle. The only proposal comp in scope is `Dilate` at 759f3fd3.

Near-misses:

- 8dae5dfc `peel`, with `layer_depth`, an `Extremes` fold over it: `Rim.depth` walked inward from the walked set's own rim (the objects), ranking a layer by its outermost ring.
- 8f3a5a89 `inside`: `Rim8` over a complement (the grid minus the outside cells), reading `rim` alone and never `depth`.
- 8b28cd80 `ring`: square rings let out from the center box by `params.ring_step` through `displacement`, alternating two colors per ring; the rings are square whatever the box holds, and no count and no minimum is kept: `Outset`/`Concentric`.
- 88bcf3b4 `nearest`: the object nearest ahead of a pole's tip, ranked by `dist` along the heading, a single-edge distance and not a walked depth. 8cb8642d `nearest`: the least edge distance inside a box, an `ArgExtremes` fold over `dist`. 88bcf3b4 `reach`/`silhouette`: `ArgExtremes` folds over `dist` along one Dir.
- 896d5239 `arm`: marks within `params.reach` of an earlier arm mark along a diagonal `Ray`; step counts along lines, which reach no cell off the eight lines.
- 880c1354 `next_cell`: a flood along the border cycle to the next region cell, with no distance. 84db8fc4 `outside`, 88207623 `blob`, 8b7bacbf `box`, 8f3a5a89 `region`: `Reach` instances, seeded flooding with no distance. 8b7bacbf `circuit`: an object-contact closure with no distance.
- 88bcf3b4 `leg`/`free`/`step`: a king walk toward successive contour cells, ordered by `before`; a turtle-like walk with no ring and no minimum. 8abad3cf `edge_off`: an offset accumulated along the row order through `compose`, no ring.
- 8886d717 `around`, 890034e9 `outline`, 8dab14c2 `dent`, 8cb8642d `arm_end`, 88e364bc `arrow`, 84ba50d3 `off_grid`: one step off a set, no further ring.
- 8698868d `size`, 878187ab `counts`, 88a62173 `rarest`, 88e364bc `rarest`, 84ba50d3 `widest`, 8abad3cf `debut`: `Extremes`/`ArgExtremes` folds over an extent, a tally, or a rank, not a depth.

Spec:

- Keyed `dir` against a `Dilate8` subclass: the one caller in scope, 759f3fd3, feeds `dir` a structural class (`dir8_elem`) under every key, so a `Dilate8` subclass would serve it with no keyed input. No site in scope steps a distance over a non-structural direction set. The adjacency precedent in scope stays one instance per adjacency under a subclass: `Rim8` at 8f3a5a89 beside `Rim` at 759f3fd3, 8dab14c2, 8dae5dfc; `Components8` at 88bcf3b4, 8a6d367c, 8b7bacbf, 8e5c0c38 beside `Components` at 26 sites. The keyed `dir` still rests on the surfacing solver 6df30ad6 alone: caller-only.
- `Rim.depth` through the comp: the one `Rim.depth` reader in scope (8dae5dfc `peel`) seeds at the rim and supplies no seed; the complement-fed `Rim8` at 8f3a5a89 reads `rim` only. No site in scope relies on `Rim.depth` over a complement as a route to the outward depth, and nothing new bears on nesting the comp inside `Rim`.
- Level-set readouts: 759f3fd3 reads `depth` by equality (a ring index) and 6df30ad6 by comparison (nearness), the two readings the definition names. Nothing in scope asks for a third.

Reimplementations: none.

The parser matcher (`dl.corpus.each_solver` over the 47 stems) flagged 2 recursive stepping rules, 9 other recursive rules, and 7 step-with-negation rules, each read in its rule above; grep over the scope for `+ 1`, `- 1`, `<=`, aggregates, `.depth(`, comp instances, and `.comp` gave the lexical hits cited.
