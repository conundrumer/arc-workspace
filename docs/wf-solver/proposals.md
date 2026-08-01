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

## `KeyedSetCompare` extensions — set-relationship lattice

`KeyedSetCompare<Key, Pat, Member>` (in `lib.dl`) exposes `covers` / `equals` / `pattern_size`. These extensions derive from the same three counts it already computes (`|pattern|`, `|observed|`, `overlap`). Add one when a real task needs it, not preemptively (lib-addition protocol):

- `within(observed, pattern)` — observed ⊆ pattern (`overlap == observed_size`)
- `disjoint(observed, pattern)` — `overlap == 0`
- `intersects(observed, pattern)` — `overlap > 0`
- `observed_size(observed, n)`, `overlap_size(observed, pattern, n)` — projections that unlock nearest / best-overlap selection

**Scope.** This component owns set-relationship derivation. Ranking policy (`best_covered`, `nearest`) and approximate / multiset / payload matching sit outside it, solver-local or in a separate component. Current hints: 3618c87e → an `unmatched` negative; 44f52bb0 → `best_covered`.

## `Bbox.corner` — set cell at a bbox corner

A membership readout beside `inside`: the set's cell at corner `diag` of its own bounding box, on the box boundary toward both of the corner's edges. A tuple exists only where the set occupies that corner (an L-shape yields three). It derives from `cell` and `edge_min` only, so it lives in the comp:

```
// Set cell on the box's d-side boundary.
.decl edge_cell(key: Key, p: Position, d: Dir)
edge_cell(K, P, D) :- cell(K, P), dist(P, D, Kd), edge_min(K, D, Kd).

.decl corner(key: Key, diag: DiagDir, p: Position)
corner(K, Diag, P) :-
    dir_of(Diag, _, D1), edge_cell(K, P, D1),
    dir_of(Diag, _, D2), edge_cell(K, P, D2),
    D1 != D2.
```

**Task-local home (protocol step 1).** 66e6c45b (`shape_edge` / `shape_corner`, Unit key): $Stretch maps the corner cells to grid corners; $Explode steps them outward.

**Second home (protocol step 1).** 62b74c02 (`block_edge`, Unit key): `edge_cell` alone, without the corner readout — the boundary column the span fill copies from.

**Third home (protocol step 1).** 4522001f (`block_edge`, body rules): $Mark reads the mark cell's block corner through `diag_dirs`, then takes its opposite.

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

    .decl step(delta: Position)
    step([-1, 1, 0, 0]). step([1, -1, 0, 0]). step([0, 0, -1, 1]). step([0, 0, 1, -1]).

    .decl reach(key: Key, p: Position)
    reach(Ky, P)  :- seed(Ky, P).
    reach(Ky, P2) :- reach(Ky, P1), step(D), compose(P1, D, P2), node(Ky, P2).
}
```

**Task-local home (protocol step 1).** 1e81d6f9: a corner-edge seed picks the L frame. The stray mask cell stays unreachable, so the following `Bbox` does not grow to span it.

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

## `ShiftInvariance<Key, Val>` — per-key shift invariance of a valued cell set

The translation peer of `D4Invariance`: which axis-aligned shifts fix each keyed cell set. `cand` enumerates the shifts the key's frame admits, tagged `(axis, k)` with both directions of a magnitude sharing a tag; `broken` witnesses a violated shift — some cell whose image holds a different value. Unlike `D4Invariance`, absence is silent: an image off the frame tests nothing, so `broken` compares only where both cells exist. A fitter reads a stored period as the smallest unbroken shift; the `Period` proposer is the produce-time sibling (with one semantic difference: the proposer counts an example too small to admit a shift as breaking it).

```
.comp ShiftInvariance<Key, Val> {
    .decl cell(key: Key, p: Position, v: Val)

    // Candidate shifts: every axis-aligned delta the frame admits.
    .decl cand(key: Key, a: Axis, k: number, delta: Shift)
    cand(Ky, A, K, Delta) :-
        cell(Ky, P, _),
        axis_of(D, A), sub_extent(P, A, K),
        jump_delta(D, K, Delta).

    // Where a candidate carries each cell's value; materialized to keep
    // the disagreement test an indexed join.
    .decl shifted(key: Key, a: Axis, k: number, p: Position, v: Val)
    shifted(Ky, A, K, P2, V) :-
        cell(Ky, P, V), cand(Ky, A, K, Delta), compose(P, Delta, P2).

    .decl broken(key: Key, a: Axis, k: number)
    broken(Ky, A, K) :- shifted(Ky, A, K, P, V), cell(Ky, P, V2), V2 != V.
}
```

**Task-local home (protocol step 1).** ca8f78db (`Parse<Key>` comp, this shape): the body's $Shift repairs through unbroken shifts (`Unit` over clean cells); the Fit reads the stored period as the smallest unbroken shift per axis (`Example` over restored outputs).

**Second home (protocol step 1).** 332efdb3 (fit rules, this shape unkeyed): the stored lattice generators are the smallest unbroken shift per axis, read as deltas.
