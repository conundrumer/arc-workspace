# Proposals

For proposing and staging changes to `.dl` style and primitives. Not a changelog or a notes file. If a proposal is implemented, it is removed from this doc.

## `ConcatPipeline` — unequal-sized rectilinear tiles

`divide` / `divide_2d` / `divide_by_size_2d` (forward) and `concat` / `concat_slab` / `concat_2d` (inverse) cover uniform tiles: every tile shares a size, so the per-tile step is constant. Unequal-sized rectilinear tiles need cumulative offsets, because each row/column has its own extent. `ConcatPipeline` derives per-tile dims and per-edge cumulative offsets, then recomposes via `compose`.

The solver populates `tile_in` (dim info; the pipeline does not read the values) and `axis_gap`. The component derives per-row / per-col tile dims and cumulative per-edge offsets, assembles `tile_offset(key, p_outer, p_off)`, and exposes a one-line `concat` (lookup + `compose`). One tiling per key. `axis_gap` stays unkeyed: the gap is the instance's parameter, like `DirFrame`'s unkeyed `dir`.

```
.comp ConcatPipeline<Key> {
    .decl tile_in(key: Key, p_outer: Position, p_inner: Position)
    .decl axis_gap(a: Axis, g: number)

    // Tile dim along axis(D), indexed by tile's distance from edge D.
    // Every cell in a rectilinear tile produces the same K — set semantics dedupes.
    .decl tile_dim(key: Key, d: Dir, i: number, k: number)
    tile_dim(Ky, D, I, K) :-
        tile_in(Ky, P_outer, P_inner),
        dist(P_outer, D, I),
        axis_of(D, A), axis_dim(P_inner, A, K).

    // Cumulative offset from edge D for the tile at distance I from D.
    .decl edge_off(key: Key, d: Dir, i: number, off: number)
    edge_off(Ky, D, I, OFF) :-
        tile_dim(Ky, D, I, _),
        axis_of(D, A), axis_gap(A, G),
        OFF = (sum K : { tile_dim(Ky, D, J, K), J < I }) + I*G.

    // Tile bbox offset in grid units, assembled from the four edges.
    .decl tile_offset(key: Key, p_outer: Position, p_off: Position)
    tile_offset(Ky, [OT, BO, OL, RO], [T_off, B_off, L_off, R_off]) :-
        edge_off(Ky, DIR_T, OT, T_off),
        edge_off(Ky, DIR_B, BO, B_off),
        edge_off(Ky, DIR_L, OL, L_off),
        edge_off(Ky, DIR_R, RO, R_off).

    // Lookup + compose.
    .decl concat(key: Key, p_outer: Position, p_inner: Position, p_grid: Position) inline
    concat(Ky, P_outer, P_inner, P_grid) :-
        tile_offset(Ky, P_outer, P_off),
        compose(P_off, P_inner, P_grid).
}
```

The internals generalize via `Dir`: `tile_dim`, `edge_off`, and `tile_offset` each cover all edges/axes in one rule. Like the uniform `concat` family, the comp is shape-agnostic: `P_outer` full-2D or axis-only both flow through `compose`, so 2D and slab arrangements use the same rules.

Solver usage:

```
.init pipe = ConcatPipeline<Choice>
pipe.tile_in(Ch, P_outer, P_inner) :- tile_data(Ch, P_outer, P_inner, _).
pipe.axis_gap(A, 0) :- axis_elem(A).

out(P_grid, V, Ch) :-
    tile_data(Ch, P_outer, P_inner, V),
    pipe.concat(Ch, P_outer, P_inner, P_grid).
```

An `.init` named `concat` clashes with lib's `concat` relation; pick another instance name.

**Task-local home (protocol step 1).** e633a9e5: nonuniform scale-up, gap 0; the $Edge and $Table extent models share one Choice-keyed instance.

## `Tile2D<Key>` / `Divide2D<Key>` — 2D decomposition from per-axis dims

The divide peers of `Frame2D`: per-axis parameters as axis-tagged rows, per-axis 1D decomposition, perp-glued. The `_2d` composites make the square claim (one scalar, both axes); these make the rectangular claim. Tile2D is size-parameterized (`divide_by_size`). Divide2D is count-parameterized: the same shape with `divide(P, A, N, G, ..)` in its place. `gap` is the instance's parameter.

```
.comp Tile2D<Key> {
    .decl cell(p: Position)
    .decl dim(key: Key, a: Axis, k: number)
    .decl gap(g: number)

    .decl tile(key: Key, p: Position, p_outer: Position, p_inner: Position)
    tile(Ky, P, P_outer, P_inner) :-
        cell(P), gap(G),
        perp(A1, A2),
        dim(Ky, A1, K1), divide_by_size(P, A1, K1, G, Po1, Pi1),
        dim(Ky, A2, K2), divide_by_size(P, A2, K2, G, Po2, Pi2),
        compose(Po1, Po2, P_outer), compose(Pi1, Pi2, P_inner).
}
```

**Task-local home (protocol step 1).** Tile2D — f8b3ba0a (Unit key): the separator-lattice tiles, dims 1 (V) and 2 (H). Divide2D — no site yet; staged as the sibling.

**Proposer tie-in.** The `TileD4` proposer decomposes gaplessly and reads `empty` on separator arrangements (8e5a5113); rebuilt on this decomposition plus `D4Map`, it would cover them.

## `KeyedSetCompare` extensions — set-relationship lattice

`KeyedSetCompare<Key, Pat, Member>` (in `lib.dl`) exposes `covers` / `equals` / `pattern_size`. These extensions derive from the same three counts it already computes (`|pattern|`, `|observed|`, `overlap`). Add one when a real task needs it, not preemptively (lib-addition protocol):

- `within(observed, pattern)` — observed ⊆ pattern (`overlap == observed_size`)
- `disjoint(observed, pattern)` — `overlap == 0`
- `intersects(observed, pattern)` — `overlap > 0`
- `observed_size(observed, n)`, `overlap_size(observed, pattern, n)` — projections that unlock nearest / best-overlap selection

**Scope.** This component owns set-relationship derivation. Ranking policy (`best_covered`, `nearest`) and approximate / multiset / payload matching sit outside it, solver-local or in a separate component. Current hints: 3618c87e → an `unmatched` negative; 44f52bb0 → `best_covered`.

## `Reframe.extents` — how big the outer is

The `BoxFrame.extents` shape on an outer that is a stored box rather than a derived one: 4522001f reads `sq.inner(L, P), axis_dims(P, A, K1, K2)`. A `Reframe.extents` peer would cover it, and waits for a second site.

## `Ordinal.rev` — opposite-end pairing of an index set

The order anti-isomorphism of `idx_set`: `rev(k, k2)` pairs each element with its opposite-end counterpart, with as many elements below k as above k2. It is the descending complement of `rank`, as a pairing rather than a rank value. The Ordinal doc's descending idiom (place ranks from the opposite edge) needs a physical frame to place into; `rev` covers reversal of an abstract index sequence.

```
.decl rev(key: Key, k: number, k2: number)
rev(Ky, K, K2) :-
    idx_set(Ky, K),  R = count : { idx_set(Ky, Ka), Ka < K },
    idx_set(Ky, K2), R = count : { idx_set(Ky, Kb), K2 < Kb }.
```

Home: `Ordinal` — it owns `idx_set`; `rev` is a second readout beside `rank`.

**Task-local home (protocol step 1).** 85c4e7cd reverses its ring colors: `rev` over ring indices pairs ring K with the ring as deep from the center as K is from the border.

## `OrderFrame<Key>` — the frame a sparse position set induces

The order-canonical peer of `AxisFrame`. `AxisFrame` realizes a frame from its extent; `OrderFrame` realizes the dense frame that a sparse set of axis-only positions induces, with each member's position in it. `pos` is Position-valued and privileges no end: the directed/undirected split of `DirFrame`/`AxisFrame`, applied to order. Members order by comparing their coordinate. A member's distance toward each edge is the count of nearer members, so numbers stay inside `nearer`'s defining comparison. The comp is parallel to `Ordinal`, not built on it: `Ordinal` is the directed, number-valued readout of an index set; `OrderFrame` is the undirected, Position-valued readout of a member set. `axis` is the instance's parameter.

```
.comp OrderFrame<Key> {
    .decl axis(a: Axis)
    .decl cell(key: Key, p: Position)

    // Member p strictly nearer edge d than member q.
    .decl nearer(key: Key, d: Dir, p: Position, q: Position)
    nearer(Ky, D, P, Q) :-
        cell(Ky, P), cell(Ky, Q),
        axis(A), axis_of(D, A),
        dist(P, D, K1), dist(Q, D, K2), K1 < K2.

    // Position in the induced frame: distance toward each edge = count
    // of nearer members.
    .decl pos(key: Key, p: Position, p_pos: Position)
    pos(Ky, P, P_pos) :-
        cell(Ky, P), axis(A), axis_of(D, A), opposite(D, O),
        R1 = count : { nearer(Ky, D, Q1, P) }, edge_delta(D, R1, P1),
        R2 = count : { nearer(Ky, O, Q2, P) }, edge_delta(O, R2, P2),
        compose(P1, P2, P_pos).
}
```

**Task-local home (protocol step 1).** 505fff84: extraction placement — contributing rows keyed by Choice. (Its segments shift via Bbox + color-keyed Reframe instead: they are intervals, so their order frame is a translation, and the tighter unit was chosen.)

## `Reach` — seeded connectivity

One component from a seed: the seeded readout of the 4-adjacency closure that lib's `Components` labels in full. The seed selects the component and is the closure's base case. `Reach` fits when there is a natural anchor and one component matters; `Components` fits when every component matters. An 8-adjacency variant or a parameterized adjacency input is the obvious extension when a task needs diagonal connectivity.

```
.comp Reach<Key> {
    .decl node(key: Key, p: Position)
    .decl seed(key: Key, p: Position)

    .decl reach(key: Key, p: Position)
    reach(Ky, P)  :- seed(Ky, P).
    reach(Ky, P2) :-
        reach(Ky, P), dir_elem(D), step_delta(D, S), compose(P, S, P2),
        node(Ky, P2).
}
```

**Task-local home (protocol step 1).** 1e81d6f9: a corner-edge seed picks the L frame. The stray mask cell stays unreachable, so the following `Bbox` does not grow to span it.

**Second home (protocol step 1).** 00d62c1b: the outside — bg seeded from the grid edge, with the enclosed cells its complement.

**Third home (protocol step 1).** 00dbd492: 00d62c1b's grid-edge seed again, under $Enclose — the enclosed cells are the region the fill covers.

1e81d6f9's copy builds its step set from a `step` relation of Position literals; at promotion it takes the form above.

## `diag_edge_delta` — edge delta at a corner

The DiagDir peer of `edge_delta`: a Position holding extents at the two edges of corner `diag`, axis-tagged — k1 at the edge on axis a, k2 across. It grows toward a corner, where `diag_step_delta` moves toward a corner. It is the delta counterpart of the `diag_dist` readout.

```
.decl diag_edge_delta(diag: DiagDir, a: Axis, k1: number, k2: number, p: Position) inline
diag_edge_delta(Diag, A, K1, K2, P) :-
    diag_dirs(Diag, A, D1, D2),
    edge_delta(D1, K1, P1), edge_delta(D2, K2, P2),
    compose(P1, P2, P).
```

**Task-local home (protocol step 1).** 8618d23e (`DiagEdgeDelta` comp): $Derive's grow delta at the corner opposite the seat, the pair from the growth case.

## `divide_by_size_slab` — divide_by_size with perpendicular passthrough

The `divide_by_size` peer of `divide_slab`. Fills the one empty cell of
the {`divide`, `divide_by_size`} × {plain, slab, 2D} composite matrix.
Lib target: composite beside `divide_slab`.

```
.decl divide_by_size_slab(p: Position, a: Axis, k: number, gap: number,
                          p_outer: Position, p_inner: Position) inline
divide_by_size_slab(P, A, K, G, P_outer, P_inner) :-
    divide_by_size(P, A, K, G, P_outer, P_i_axis),
    split(P, A, _, Across),
    compose(P_i_axis, Across, P_inner).
```

**Task-local home (protocol step 1).** 7b7f7511 (`DivideBySizeSlab`
comp): $Tile's swept tiling.

## `Dir8` — direction as one type, with `Dir` and `DiagDir` as its branches

Lib's two direction families are not parallel. `diag_dist` is `dist` applied twice through `diag_dirs`; `diag_jump_delta` is two `jump_delta`s composed. A corner is a pair of edges, one per axis, so the `diag_*` names package the `Dir` layer rather than forming a second primitive layer. The missing type sits above both branches rather than beside them.

Without it, a column holding a direction that may be either kind has no type to declare, and every site that wants all eight rebuilds the set. The corpus holds three unrelated encodings: guarded twin rules over a locally declared union (045e512c), a `surround_step` delta set repeated verbatim (42a50994, d9fac9be, f0df5ff0, and inlined at the use site in ce22a75a and dc1df850), and step-set extension (`Components8`). All but the first erase the direction's identity down to a delta at the point of construction.

Lib target: type beside `Dir` and `DiagDir`, deltas beside `jump_delta` and `diag_jump_delta`.

```
.type Dir8 = Dir | DiagDir

.decl dir8_jump_delta(d: Dir8, k: number, delta: Shift) inline
dir8_jump_delta(D, K, Delta) :- dir_elem(D), jump_delta(D, K, Delta).
dir8_jump_delta(D, K, Delta) :- diag_dir_elem(D), diag_jump_delta(D, K, Delta).

.decl dir8_step_delta(d: Dir8, delta: Shift) inline
dir8_step_delta(D, Delta) :- dir8_jump_delta(D, 1, Delta).
```

The union type works because lib's constants sit in disjoint ranges: a value's range identifies its branch, which is what each clause's `dir_elem` / `diag_dir_elem` guard tests.

### What collapses

Whether a pair collapses turns on the codomain. Three pairs are `Shift`-valued and become one relation each: `opposite` / `diag_opposite`, `jump_delta` / `diag_jump_delta`, `step_delta` / `diag_step_delta`.

Where the arity differs there is nothing to write. `dist` yields one number and `diag_dist` yields two, because an edge has one edge and a corner has two. The proposed `diag_edge_delta` stays for the same reason at the input end: it takes a length per axis where `edge_delta` takes one. That is the type's limit — `Dir8` with a scalar `k` describes king moves only, and a displacement with unequal per-axis steps has no `Dir8` form.

`Ray` and `DiagRay` collapse only at a cost. Both are collinearity plus a side test in two coordinate idioms; the uniform form is "q is p displaced n steps toward d, n at least 0", which needs a length domain to enumerate where the comparison forms need none.

### Where discrimination lives

Souffle has no match construct, so any consumer that tells the branches apart re-guards with `dir_elem` / `diag_dir_elem`. Keep that in one place, the delta primitive, and let everything downstream carry `Dir8` opaquely — 045e512c's `toward` holds the column and never inspects it.

The guards also change the call convention. `jump_delta` is one clause of functors that binds nothing, so callers pair it with `dir_elem`; `dir8_jump_delta` grounds its own direction, so a caller supplies only `k`. The `surround_step` sites collapse to `surround_step(S) :- dir8_step_delta(_, S).`, and `Components8` to `c4.step(S) :- dir8_step_delta(_, S).`, one rule stating the whole adjacency instead of the diagonal half added onto the cardinal one. b60334d2 and 49d1d64f keep their split: their cardinal and diagonal arms supply different colors, so the two families are load-bearing there.

A `dir8_elem` enum, the peer of `dir_elem` and `d4_elem`, has no site. Nothing calling the deltas needs it, and the use it would have — a universal over the eight directions by defect negation — has not come up.

### The undirected peer

The same union recurs on the undirected half. `Axis` and `DiagAxis` together are the four lines through a cell, and `same_dist` and the proposed `same_diag` are two branches of one relation: p and q lie on a common line of that kind. Accepting the union for directions and refusing it for lines leaves the same gap one level down, so the two want deciding together.

Name: `Axis4`, following `Dir8` in naming the branch union by its element count, as `c4_elem` does for the rotation subgroup. `Line` collides with the `lines` concept term, which means ink along a row or column rather than the geometric line.

Keying is open. `same_diag` is keyed by the line's own axis; `same_dist` is keyed by a `Dir` and states equal distance to that edge, which is collinearity along the *perpendicular* axis. A unified relation keys by the line's own axis throughout, so `same_dist`'s convention changes and its callers move with it.

**Task-local home (protocol step 1).** 045e512c: `toward` maps each of the eight directions and each admissible length to a displacement, which the fragment's fit selects from and $Abut composes two lengths of.

**Protocol note.** A `.type` cannot live in a `.comp`, so the task-local form is a solver-scope type, which style otherwise reserves for coverage and comp instantiation.

**Open.** `dir8_jump_delta` needs two clauses, since the domain is a disjoint union, and lib's functor note says a multi-clause inline multiplies IR path count in every calling rule. A non-inline form would need both a caller-supplied length domain, which is what 045e512c's `toward` already is, and `dir8_elem` back to supply the direction.

## `corner_dist` — taxicab distance to a corner

The DiagDir peer of `dist`: L1 distance to corner `diag`, the sum of its
two edge distances. Its level sets are the diagonals on the other
diagonal axis, so it reads a cell's diagonal index with no sign or
subtraction: equality against a reference cell tests same-diagonal,
comparison tests sidedness, and a shared `stride` class tests periodic
diagonal offset. Lib target: primitive beside `diag_dist`.

```
.decl corner_dist(p: Position, diag: DiagDir, k: number) inline
corner_dist(P, Diag, K) :- diag_dist(P, Diag, _, K1, K2), K = K1 + K2.
```

**Task-local home (protocol step 1).** c1990cce (`CornerDist` comp): the
V (level with the seed toward a cone corner), the open cone (strictly
nearer both cone corners than the seed), and $Stripe's period (the
seed's stride class from the mirror corner).

## `same_diag` — same diagonal line

The DiagAxis peer of `same_dist`: p and q lie on one diagonal line of
axis da. Stepping toward a corner of the axis drops the distance to both
of its edges in lockstep, so collinearity is an equal drop on both;
either corner of the axis derives the same relation, so no corner is
privileged. It is the undirected form of `DiagRay`'s membership test —
`DiagRay` adds the side test and the mark/domain split. `corner_dist`
equality states the same relation from a corner of the perpendicular
axis; `same_diag` names the relation itself and keys it by the line's
own axis. Lib target: composite beside `same_dist`.

```
.decl same_diag(da: DiagAxis, p: Position, q: Position) inline
same_diag(DA, P, Q) :-
    diag_axis_of(Diag, DA),
    diag_dist(P, Diag, A, Pa, Pb), diag_dist(Q, Diag, A, Qa, Qb),
    Qa - Pa = Qb - Pb.
```

**Task-local home (protocol step 1).** c3f564a4 (`SameDiag` comp): $Diag
fills a noise cell from a clean cell on its stripe.

## `Partition<Key>` — a cell set decomposes into unit copies

Whether a keyed cell set partitions into disjoint translated copies of a
footprint. Strictly stronger than `Occurrences` coverage: a 2×3 rectangle is
covered by 2×2 placements but admits no partition.

In any partition, the copy covering the reading-order-first unpeeled cell
places its own reading-order-first cell there — any other alignment needs a
cell already peeled or off the set — so a greedy reading-order peel is
canonical and correct for any single footprint under translation. With D4
variants of the unit the step is not forced; out of scope.

The peel is staged deletion — each stage's remaining set negates the
previous stage's chosen copy — which Souffle's predicate-level
stratification rejects. It goes in a functor (`lib_functors.cpp`).

```
.comp Partition<Key> {
    .decl cell(key: Key, p: Position)
    .decl unit(p: Position)

    .decl partitions(key: Key)
    // functor-backed greedy reading-order peel
}
```

Open: functors take scalars, so the sets cross the interface serialized — an
ordered string fold, or a tooling convention for set-valued functor inputs.

**Motivating site.** b1fc8b8e: a $Partition detect case beside $Shape.

## `Mode<Key, Member, Witness>` — the commonest member per key

Count-and-argmax: tally the witnesses carrying each member, then keep the
members no other member outnumbers. The witness is its own column, so
multiplicity comes from a set-valued relation with no multiset encoding.
Ties keep every member at the max; a consumer needing one member either has a
task where the max is unique, or reads the tie as data.

```
.comp Mode<Key, Member, Witness> {
    .decl item(key: Key, m: Member, w: Witness)

    .decl tally(key: Key, m: Member, n: number)
    tally(Ky, M, N) :- item(Ky, M, _), N = count : { item(Ky, M, W) }.

    .decl mode(key: Key, m: Member)
    mode(Ky, M) :- tally(Ky, M, N), N = max N2 : { tally(Ky, _, N2) }.
}
```

Lib target: body component, beside `Ordinal` and `Excess`.

Sites already written as plain body relations. Commonest color over a cell
set: 73251a56 `dominant`, 7e4d4f7c `bg`, e57337a4 `canvas`, 642d658d
`grid_bg`. Argmax over a derived count: 642d658d `arm_off`, ae4f1146
`comp_winner` and `window_winner`, a87f7484 `densest`.

**Task-local home (protocol step 1).** 0607ce86: `template`, the per-cell
color vote across the copies (key = intile position, member = color, witness
= copy); and `intact`, the copy the others confirm most (member = copy,
witness = the confirming copy-and-cell pair).
