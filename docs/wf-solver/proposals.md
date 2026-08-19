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

## `DividerFrame<Key>` — nonuniform tiles from divider lines

The tile arrangement a divider set induces — the divider-driven cell of the decomposition matrix, beside dim-driven `Tile2D`/`Divide2D` and the uniform `divide` family, which all need equal tiles. A cell's tile position holds, toward each edge, the count of dividers between the cell and that edge — `OrderFrame.pos`'s construction, applied to cells counting dividers. The wide two-dir form keeps the part frame consistent with no arithmetic and no stored part count; divider cells get no tile; an axis with no dividers is one part. `divider` takes axis-tagged divider lines, as detection output or stored data. Exposes `part_of` (axis-only part) and `tile_of` (parts perp-glued); a within-tile position is a `Reframe` from the tile's box when a site needs it. Lib target: body comp beside `OrderFrame`.

```
.comp DividerFrame<Key> {
    .decl cell(key: Key, p: Position)              // input
    .decl divider(key: Key, a: Axis, l: Position)  // input

    // Divider distances, materialized for the counts below.
    .decl div_dist(key: Key, a: Axis, d: Dir, k: number)
    div_dist(K, A, D, K1) :- divider(K, A, L), axis_of(D, A), dist(L, D, K1).

    // p's line on axis a holds a divider.
    .decl on_divider(key: Key, p: Position, a: Axis)
    on_divider(K, P, A) :- cell(K, P), div_dist(K, A, D, K1), dist(P, D, K1).

    // p's tile index from edge d — the dividers between p and edge d.
    .decl part_idx(key: Key, p: Position, d: Dir, n: number)
    part_idx(K, P, D, N) :-
        cell(K, P), axis_of(D, A), !on_divider(K, P, A), dist(P, D, K1),
        N = count : { div_dist(K, A, D, K2), K2 < K1 }.

    // The part of axis a that p sits in, as an axis-only position: p's
    // tile index from each edge of the axis.
    .decl part_of(key: Key, p: Position, a: Axis, p_part: Position)
    part_of(K, P, A, P_part) :-
        axis_of(D, A), opposite(D, D2),
        part_idx(K, P, D, N1), part_idx(K, P, D2, N2),
        edge_delta(D, N1, Q1), edge_delta(D2, N2, Q2), compose(Q1, Q2, P_part).

    // P's tile, parts on both axes glued.
    .decl tile_of(key: Key, p: Position, p_tile: Position)
    tile_of(K, P, P_tile) :-
        part_of(K, P, A, P1), perp(A, A2), part_of(K, P, A2, P2),
        compose(P1, P2, P_tile).
}
```

**Task-local home (protocol step 1).** 0bb8deee (`DividerFrame` comp): the cross's four quadrants, one instance in `Parse<Key>` serving the body (Unit) and the Fit (Example).

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

Bounds: `dist` / `diag_dist` and the unequal-k `diag_edge_delta` differ in arity across the branches and stay per-branch. `turn` widens the same way — rotation carries corners to corners — but has no site.

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

## `Wallpaper<Key, Val>` — lattice-quotiented isometry detection

The isometry peer of `ShiftInvariance`: which isometries of the frame — a
D4 element composed with a shift — fix a keyed valued cell set, given the
set's per-axis periods. Candidates are quotiented by the translation
lattice: one representative per coset, its shift drawn from the lattice's
fundamental domain, and square-checked against the lattice where the kind
squares to the identity (a symmetry's square is a translation, and the
group's translations are the lattice). Lib target: body comp beside
`ShiftInvariance`; `Gen` moves beside it.

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

## `Closed<Key>` — the regions a cell set closes off from the edge

The regions of a keyed cell set that the grid edge cannot reach — the
entity-level half of the `enclose` prior. Enclosure is a cell property and
floods linearly (`Reach` seeded on the edge); individuation pays
`Components`' pairwise closure, so it runs over only the closed cells —
the regions the model claims. `Reach` stays the unit for cell-level
enclosure and seeded selection (00d62c1b, 1e81d6f9). Lib target: body
comp beside `Reach`.

```
.comp Closed<Key> {
    .decl cell(key: Key, p: Position)  // input

    .init flood = Reach<Key>
    flood.node(Ky, P) :- cell(Ky, P).
    flood.seed(Ky, P) :- cell(Ky, P), dir_elem(D), dist(P, D, 0).

    .init regions = Components<Key>
    regions.node(Ky, P) :- cell(Ky, P), !flood.reach(Ky, P).

    .decl region(key: Key, p: Position, id: Ident)
    region(Ky, P, Id) :- regions.label(Ky, P, Id).
}
```

**Task-local home (protocol step 1).** 0a2355a6 (`Closed` comp): both hole
frames — the bg with all ink solid (grid key), everything-but-O with one
object solid (object key).

**Second home (protocol step 1).** 00dbd492: $Enclose writes the same
composition inline — `Reach` from the grid edge, then `Components` over
the enclosed cells.