# Proposals

For proposing and staging changes to `.dl` style and primitives. Not a changelog or a notes file. If a proposal is implemented, it is removed from this doc.

## `ConcatPipeline` — unequal-sized rectilinear tiles

`ConcatPipeline` derives per-tile dims and per-edge cumulative offsets, then composes via `compose`. Cumulative offsets are what unequal tiles need, because each row/column has its own extent. The uniform family — `divide` / `divide_2d` / `divide_by_size_2d` forward, `concat` / `concat_slab` / `concat_2d` inverse — takes one tile size, so its per-tile step is constant.

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

## `Ordinal.rev` — opposite-end readout of an index set

The order anti-isomorphism of `idx_set`: element-valued, pairing each element with its opposite-end counterpart, with as many elements below k as above k2. A site picks between it and `rank_desc` by what the consumer reads: `rev` where consumption stays in the element domain (each element takes its counterpart's property, and no rank number crosses the interface); `rank_desc` where the rank value flows downstream into a table join or comparison anchored at the top end, and `rev` would route through a phantom counterpart. Layout sites use neither: placing ascending ranks from the opposite edge stays the one encoding of a descending layout.

```
.decl rev(key: Key, k: number, k2: number)
rev(Ky, K, K2) :- rank(Ky, K, R), rank_desc(Ky, K2, R).
```

Home: `Ordinal` — it owns `idx_set`; a readout beside `rank` and `rank_desc`.

**Task-local home (protocol step 1).** `rev` — 85c4e7cd reverses its ring colors: `rev` over ring indices pairs ring K with the ring as deep from the center as K is from the border.

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

    // Position in the induced frame.
    .decl pos(key: Key, p: Position, p_pos: Position)
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

## Dir8-wide primitives — widen the base relations, retire the twins

`dir8_jump_delta` / `dir8_step_delta` (in lib) are a third parallel family: the `diag_*` relations twin the cardinal ones, and the `dir8_*` pair twins both again. Widening the base relations to `Dir8` retires the twins: a corner is its two cardinal edges, so a functor that lets a `DiagDir` match either of its corner's dirs makes the existing single clauses compute the diagonal cases unchanged.

- `@keep_dir(sel, target, v)`: a `DiagDir` sel matches both of its corner's cardinal targets. `edge_delta(d: Dir8, k, p)` then carries k at a corner's two edges — the equal-k case of the proposed `diag_edge_delta`.
- `opposite(d: Dir8, opp: Dir8)` gains the four corner rows; `diag_opposite` folds in.
- `jump_delta` and `step_delta` widen with their clauses unchanged: for `DIAG_TL`, `edge_delta(DIAG_TL, -K)` composed with `edge_delta(DIAG_BR, K)` is the diagonal jump. `diag_jump_delta`, `diag_step_delta`, `dir8_jump_delta`, and `dir8_step_delta` retire.
- The widened relations stay single functor clauses that bind nothing, so sites that enumerate all eight — `dir8_step_delta(_, S)` today — ground through a `dir8_elem` enum: `dir8_elem(D), step_delta(D, S)`.

Discrimination sits in the functor layer, so no calling rule multiplies IR paths — the cost the two-clause `dir8_*` form carries.

Bounds: `dist` / `diag_dist` and the unequal-k `diag_edge_delta` differ in arity across the branches and stay per-branch; `Ray` / `DiagRay` collapse only at the cost of a length domain. `turn` widens the same way — rotation carries corners to corners — but has no site.

Caveat: Souffle's union typing is static, with no runtime filtering, so a caller that grounds its direction from the widened `opposite` instead of feeding one in enumerates eight rows. Implementation sweeps `opposite`'s callers for unbound-d use.

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

**The `Axis4` union.** Lib's `Dir8` recurs on the undirected half:
`Axis` and `DiagAxis` together are the four lines through a cell, and
`same_dist` and `same_diag` are two branches of one relation — p and q
on a common line of that kind. The name follows `Dir8` in counting the
branch union's elements; `Line` collides with the `lines` concept term.
Keying is open: a unified relation keys by the line's own axis
throughout, while `same_dist` keys by a `Dir` and states collinearity
along the *perpendicular* axis, so its convention and its callers move
with the merge.

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

## `Sym` — D4 subgroups as a value type

D4 has exactly ten subgroups, so a symmetry group is a closed value like a
`Dir` or a `D4` element, not an open set. The type names the ten;
`sym_member` fixes each one's elements as lib data; `sym_elem` enumerates
them for universals. A stored group is then one value in a fact or GRID
cell, and fill validity is structural: only the ten have names. Lib
target: type beside `D4`, constants in a fresh range, both relations
beside `d4_elem`.

```
.type Sym <: number

#define SYM_1   70
#define SYM_LR  71
#define SYM_TB  72
#define SYM_HT  73
#define SYM_DG  74
#define SYM_AD  75
#define SYM_BOX 76
#define SYM_X   77
#define SYM_C4  78
#define SYM_D4  79

.decl sym_elem(s: Sym)
.decl sym_member(s: Sym, d: D4)
```

- Order-2 groups are named by their non-identity element. `SYM_BOX` is
  the axis-aligned Klein group, `SYM_X` the diagonal one, `SYM_C4` the
  rotations; these three names are open.
- Under grid relabeling, values conjugate the way directions rotate: a
  mirrored sibling edits `SYM_LR` to `SYM_TB`; `SYM_BOX`, `SYM_X`,
  `SYM_C4`, `SYM_D4` are normal subgroups and stay fixed.
- `c4_elem` is the `SYM_C4` rows and can become
  `c4_elem(D) :- sym_member(SYM_C4, D).`
- The patterns.md section "Stored symmetry sets as full subgroups"
  describes the element-list encoding this type replaces.
- Fitting a stored group: `KeyedSetCompare<Key, Sym, D4>` with
  `sym_member` as the pattern catalog; `equals` names the observed set.
- A containment readout (`sym_leq`) is derivable from `sym_member` by
  defect negation; add on first need.

**Task-local home (protocol step 1).** 0934a4d8 (`SymTable` comp):
per-tile mosaic symmetry as GRID values; its Fit names each tile's
unbroken set via `equals`.

**Second home (protocol step 1).** 44f52bb0: `syms` and the
`mapping_sym` entries store subgroups as element lists; each collapses to
one `Sym` value.
