# Proposals

For proposing and staging changes to `.dl` style and primitives. Not a changelog or a notes file. If a proposal is implemented, it is removed from this doc.

An entry's first sentence is its index line, read under the entry's title: it stands alone, and criteria and guards start after it.

## `ConcatPipeline` — unequal-sized rectilinear tiles

`ConcatPipeline` derives per-tile dims and per-edge cumulative offsets, then composes via `compose`; cumulative offsets are what unequal tiles need, because each row/column has its own extent. The uniform family — `divide` / `divide_2d` / `divide_by_size_2d` forward, `concat` / `concat_slab` / `concat_2d` inverse — takes one tile size, so its per-tile step is constant.

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

## `KeyedSetCompare` extensions — set-relationship lattice

Extensions of `KeyedSetCompare<Key, Pat, Member>` beyond its `covers` / `equals` / `pattern_size`, each derived from the three counts it already computes (`|pattern|`, `|observed|`, `overlap`). Add one when a real task needs it, not preemptively (lib-addition protocol):

- `within(observed, pattern)` — observed ⊆ pattern (`overlap == observed_size`)
- `disjoint(observed, pattern)` — `overlap == 0`
- `intersects(observed, pattern)` — `overlap > 0`
- `observed_size(observed, n)`, `overlap_size(observed, pattern, n)` — projections that unlock nearest / best-overlap selection

**Scope.** This component owns set-relationship derivation. Ranking policy (`best_covered`, `nearest`) and approximate / multiset / payload matching sit outside it, solver-local or in a separate component. Current hints: 3618c87e → an `unmatched` negative; 44f52bb0 → `best_covered`.

## `Reframe.extents` — how big the outer is

The `BoxFrame.extents` shape on an outer that is a stored box rather than a derived one: 4522001f reads `sq.inner(L, P), axis_dims(P, A, K1, K2)`. A `Reframe.extents` peer would cover it, and waits for a second site.

## `Ordinal.rev` — opposite-end readout of an index set

The order anti-isomorphism of `idx_set`: element-valued, pairing each element with its opposite-end counterpart, with as many elements below k as above k2. A site picks between it and `rank_desc` by what the consumer reads: `rev` where consumption stays in the element domain (each element takes its counterpart's property, and no rank number crosses the interface); `rank_desc` where the rank value flows downstream into a table join or comparison anchored at the top end, and `rev` would route through a phantom counterpart. Layout sites use neither: placing ascending ranks from the opposite edge stays the one encoding of a descending layout.

```
.decl rev(key: Key, k: number, k2: number)
rev(Ky, K, K2) :- rank(Ky, K, R), rank_desc(Ky, K2, R).
```

Home: `Ordinal` — it owns `idx_set`; a readout beside `rank` and `rank_desc`.

**Task-local home (protocol step 1).** `rev` — 85c4e7cd reverses its ring colors: `rev` over ring indices pairs ring K with the ring as deep from the center as K is from the border.

## `diag_edge_delta` — edge delta at a corner

The DiagDir peer of `edge_delta`: a Position holding extents at the two edges of corner `diag`, axis-tagged — k1 at the edge on axis a, k2 across. It grows toward a corner, where `step_delta` at the same corner moves toward it. It is the delta counterpart of the `diag_dist` readout.

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

## `Wallpaper<Key, Val>` — lattice-quotiented isometry detection

The isometry peer of `ShiftInvariance`: which isometries of the frame — a
D4 element composed with a shift — fix a keyed valued cell set, given the
set's per-axis periods. Candidates are quotiented by the translation
lattice: one representative per coset, its shift drawn from the lattice's
fundamental domain, and square-checked against the lattice where the kind
squares to the identity (a symmetry's square is a translation, and the
group's translations are the lattice). `ShiftInvariance.period` feeds the
`period` input directly. Lib target: body comp beside `ShiftInvariance`;
`Gen` moves beside it.

```
.type Gen = [d: D4, delta: Shift]

.comp Wallpaper<Key, Val> {
    .decl kind(d: D4)                           // input
    .decl cell(key: Key, p: Position, v: Val)   // input
    .decl grid(key: Key, p: Position)           // input
    .decl period(key: Key, a: Axis, k: number)  // input

    // Witnessed, uncontradicted coset representatives.
    .decl sym(key: Key, g: Gen)

    // Kinds with an admitted representative; the identity kind whenever a
    // lattice exists. A Sym-naming Fit reads this.
    .decl kind_used(key: Key, d: D4)

    // One step along an admitted isometry or a lattice shift, over the
    // full grid — the map an orbit closure walks.
    .decl step(key: Key, p: Position, q: Position)
}
```

- A representative needs a witness — some cell pair it maps one onto the
  other; vacuous overlap is no evidence. The rest of its coset arrives by
  composition with the lattice in the caller's closure.
- The internal canonical corner for fundamental-domain shifts is
  unobservable: every corner yields the same cosets and maps.
- An axis without a period contributes only the zero shift, so an
  aperiodic grid degrades to center-anchored D4 detection.

**Task-local home (protocol step 1).** 0dfd9992: wallpaper repair —
`Parse` feeds detected per-axis periods and the stored point group's
kinds; `out` closes survivor colors over `step`; its Fit names the
kinds every example uses as a `point_group` Sym value.

## `Peel<Key>` — erosion depth of a keyed cell set

The depth peer of `Reach`'s membership: ring 0 is the cells with an 8-neighbor outside the set, off-frame counting as outside, and each step inward is one ring deeper. It equals the Chebyshev distance to the set's complement minus one. Non-convex depth has no counter-free encoding, so the arithmetic sits behind the comp boundary. Lib target: body comp beside `Reach`.

```
.comp Peel<Key> {
    .decl cell(key: Key, p: Position)  // input

    // Some 8-neighbor lies outside the set — off-frame counts as outside.
    .decl edge(key: Key, p: Position)
    edge(Ky, P) :-
        cell(Ky, P),
        dir8_elem(D), step_delta(D, S), compose(P, S, Q), !cell(Ky, Q).

    // The shortest inward walk from the boundary.
    .decl ring(key: Key, p: Position, k: number)
    ring(Ky, P, 0) :- edge(Ky, P).
    ring(Ky, P, K2) :-
        ring(Ky, Q, K), K2 = K + 1,
        dir8_elem(D), step_delta(D, S), compose(Q, S, P), cell(Ky, P).
    ring(Ky, P, K) <= ring(Ky, P, K2) :- K2 < K.
}
```

**Task-local home (protocol step 1).** 13e47133 (`Peel` comp): region
rings that a repeating marker palette paints. The solver pairs it against a
$Sight rival — depth as the min ray-cast distance to the outside (`Ray` +
`Extremes`). The two metrics agree wherever every wall is a straight run; a
lone wall cell splits them (its knight's-move cells read deeper under
sight).

Prior special cases the comp would cover: 85c4e7cd's ring (min edge
distance — the convex-frame case) and 135a2760's panel frame (ring 0 of a
rectangular panel).
## `RIGID(C4, ...)` — chiral rigid assemblies

The rotation-subgroup variant of `RIGID`: the closure ranges `c4_elem` in place of `d4_elem`, so the hand becomes data — a stored chart of the wrong hand has an orbit that misses the observed instances, and the fit diffs — while rotation stays gauge. Closing a rotate-only task over D4 instead over-generates placements the task forbids and lets the fit accept a mirrored chart.

The rest of the machinery is group-agnostic: C4's elements are D4 elements, so placed column types and the column actions are unchanged, and the fit compare groups rows by whatever pose labels both sides emit — both sides close through the same generated rule. The change is the elem atom in the expansion plus the group argument in the parser.

A task treating both hands as distinct pieces needs no new group: that is an id-keyed C4 chart with one id per hand.

Gate: a site whose pieces rotate but do not reflect.
