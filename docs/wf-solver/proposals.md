# Proposals

For proposing and staging changes to `.dl` style and primitives. Not a changelog or general notes.
If a proposal is implemented, it is removed from this doc.

## `ConcatPipeline` — unequal-sized rectilinear tiles

`divide` / `divide_2d` / `divide_by_size_2d` (forward) and `concat` /
`concat_slab` / `concat_2d` (inverse) cover uniform tiles: every tile shares a
size, so the per-tile step is constant. Unequal-sized rectilinear tiles need
cumulative offsets — each row/column carries its own extent. `ConcatPipeline`
derives per-tile dims and per-edge cumulative offsets, then recomposes via
`compose`.

Solver populates `tile_in` (dim info; values aren't read by the pipeline) and
`axis_gap`. The component derives per-row / per-col tile dims, cumulative
per-edge offsets, assembles `tile_offset(key, p_outer, p_off)`, and exposes a
one-liner `concat` (lookup + `compose`). One tiling per key; `axis_gap` stays
unkeyed — the gap is the instance's parameter, per `DirFrame`'s unkeyed `dir`.

```
.comp ConcatPipeline<Key> {
    .decl tile_in(key: Key, p_outer: Position, p_inner: Position)
    .decl axis_gap(a: Axis, g: number)

    // Tile dim along axis(D), indexed by tile's distance from edge D.
    // Every cell in a rectilinear tile produces the same K — set semantics dedupes.
    .decl axis_dim(key: Key, d: Dir, i: number, k: number)
    axis_dim(Ky, D, I, K) :-
        tile_in(Ky, P_outer, P_inner),
        dist(P_outer, D, I),
        opposite(D, D2),
        dist(P_inner, D, Near), dist(P_inner, D2, Far),
        K = Near + Far + 1.

    // Cumulative offset from edge D for the tile at distance I from D.
    .decl edge_off(key: Key, d: Dir, i: number, off: number)
    edge_off(Ky, D, I, OFF) :-
        axis_dim(Ky, D, I, _),
        axis_of(D, A), axis_gap(A, G),
        OFF = (sum K : { axis_dim(Ky, D, J, K), J < I }) + I*G.

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

Internals collapse via `Dir`: `axis_dim`, `edge_off`, and `tile_offset` each
generalize across edges/axes in a single rule. Like the uniform `concat` family,
it's shape-agnostic — `P_outer` full-2D or axis-only both flow through `compose`,
so 2D and slab arrangements use the same rules.

Solver usage:

```
.init pipe = ConcatPipeline<Choice>
pipe.tile_in(Ch, P_outer, P_inner) :- tile_data(Ch, P_outer, P_inner, _).
pipe.axis_gap(A, 0) :- axis_elem(A).

out(P_grid, V, Ch) :-
    tile_data(Ch, P_outer, P_inner, V),
    pipe.concat(Ch, P_outer, P_inner, P_grid).
```

An `.init` named `concat` clashes with lib's `concat` relation; pick another
instance name.

**Task-local home (protocol step 1).** e633a9e5: nonuniform scale-up, gap 0
— the $Edge and $Table extent models share one Choice-keyed instance.

## `Tile2D<Key>` / `Divide2D<Key>` — 2D decomposition from per-axis dims

The divide peers of `Frame2D`: per-axis parameters as axis-tagged rows,
per-axis 1D decomposition, perp-glued. The `_2d` composites carry the
square claim — one scalar, both axes; these carry the rectangular claim.
Tile2D is size-parameterized (`divide_by_size`); Divide2D is
count-parameterized (`divide`), the same shape with `divide(P, A, N, G, ..)`
in its place. `gap` is the instance's parameter; single-set sites key on
Unit.

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

**Task-local home (protocol step 1).** Tile2D — f8b3ba0a (Unit key): the
separator-lattice tiles, dims 1 (V) and 2 (H). Divide2D — no site yet;
staged as the sibling.

## `KeyedSetCompare` extensions — set-relationship lattice

`KeyedSetCompare<Key, Member>` (in `lib.dl`) exposes `covers` / `equals` / `pattern_size`.
These extensions derive from the same three counts it already computes (`|pattern|`,
`|observed|`, `overlap`); add one when a real task needs it, not preemptively
(lib-addition protocol):

- `within(observed, pattern)` — observed ⊆ pattern (`overlap == observed_size`)
- `disjoint(observed, pattern)` — `overlap == 0`
- `intersects(observed, pattern)` — `overlap > 0`
- `observed_size(observed, n)`, `overlap_size(observed, pattern, n)` — projections that
  unlock nearest / best-overlap selection

**Scope.** This component owns set-relationship derivation. Ranking policy (`best_covered`,
`nearest`) and approximate / multiset / payload matching sit at or past the edge —
solver-local or a separate component. Current hints: 3618c87e → an `unmatched` negative,
44f52bb0 → `best_covered`.

**Global observed set.** When the observed set is global — one set, no
meaningful key (44f52bb0's invariance set, 27a28665's silhouette) — the call
keys on `Unit` (`$U()`, in lib).

## `Bbox.corner` — set cell at a bbox corner

A membership readout beside `inside`: the set's cell seated at corner `diag`
of its own bounding box — on the box boundary toward both of the corner's
edges. A tuple exists only where the set occupies that corner (an L-shape
yields three). Derives from `cell` and `edge_min` only, so it lives in the
comp:

```
// Set cell on the box's d-side boundary.
.decl edge_cell(key: Key, p: Position, d: Dir)
edge_cell(K, P, D) :- cell(K, P), dir_elem(D), dist(P, D, Kd), edge_min(K, D, Kd).

.decl corner(key: Key, diag: DiagDir, p: Position)
corner(K, Diag, P) :-
    dir_of(Diag, _, D1), edge_cell(K, P, D1),
    dir_of(Diag, _, D2), edge_cell(K, P, D2),
    D1 != D2.
```

**Task-local home (protocol step 1).** 66e6c45b (`shape_edge` / `shape_corner`,
Unit key): $Stretch maps the corner cells to grid corners; $Explode steps them
outward.

## `Between<Key>` — cells between two keyed marks on a line

The two-sided fold of `Ray` (`lib.dl`). Demoted from lib in the `Ray`
factoring — the fold is one rule and lives solver-local until it re-earns
comp form.

```
.comp Between<Key> {
    .decl axis(a: Axis)
    .decl cell(p: Position)            // domain tested
    .decl mark(key: Key, p: Position)

    .init rays = Ray<Key>
    rays.dir(D)     :- axis(A), axis_of(D, A).   // cast both ways
    rays.cell(P)    :- cell(P).
    rays.mark(K, P) :- mark(K, P).

    .decl between(key: Key, p: Position)
    between(K, P) :- rays.ray(K, P, D), opposite(D, O), rays.ray(K, P, O).
}
```

A mark is between under its own key — Ray's inclusive reach; 22168020
paints mark cells through this.

**Task-local homes (protocol step 1).** Solver-local folds: 22168020
(Color key), 22eb0ac0 $Span (Color), a699fb00 $Span (Unit), aa18de87
$Axis and $Iso (Unit, $Iso casting all four dirs).

## Keyed `Ordinal` / `DirFrame` — rank-and-place across cases

Both lib comps hold one relation set per instance, so a solver whose cases
share the rank-and-place pipeline shatters at the comp boundary: per-case
instances plus dispatch rules that differ only in the case name. f8b3ba0a
carries three count models through one drop-dominant → rank → place pipeline;
its choice-keyed relations (`count_of`, `minority_count`) flow through single
rules, then `Ordinal` and `DirFrame` force three `.init`s each and rule
triplets (`minority_rank`, `dist_set`, `out`), including three identical
`dir` rules.

A `Key` type param collapses each triplet to one instance and one rule,
following `Bbox<Key>` / `KeyedSetCompare<Key, Member>`:

```
.comp Ordinal<Key> {
    .decl idx_set(key: Key, k: number)

    .decl rank(key: Key, k: number, r: number)
    rank(Ky, K, R) :-
        idx_set(Ky, K),
        R = count : { idx_set(Ky, K2), K2 < K }.
}

.comp DirFrame<Key> {
    .decl dir(d: Dir)
    .decl dist_set(key: Key, k: number)

    .decl extent(key: Key, n: number)
    extent(Ky, N) :- dist_set(Ky, _), N = count : { dist_set(Ky, K) }.

    .decl pos(key: Key, k: number, p: Position) inline
    pos(Ky, K, P) :-
        dist_set(Ky, K), dir(D), opposite(D, D_opp), extent(Ky, N),
        edge_delta(D, K, P_d), edge_delta(D_opp, N-1-K, P_o),
        compose(P_d, P_o, P).
}
```

`dir` stays unkeyed — the frame direction is the instance's parameter; key it
only when a task places per-key directions.

Single-set callers key on `Unit`. Callers to update: f8ff0b80 (both), d406998b
(`Ordinal`), f8b3ba0a (both, collapsing the triplets).

## `Ordinal.rev` — opposite-end pairing of an index set

The order anti-isomorphism of `idx_set`: `rev(k, k2)` pairs each element
with its opposite-end counterpart — as many elements below k as above k2.
The descending complement of `rank` as a pairing rather than a rank value.
The Ordinal doc's descending idiom (place ranks from the opposite edge)
needs a physical frame to place into; `rev` covers reversal of an abstract
index sequence.

```
.decl rev(k: number, k2: number)
rev(K, K2) :-
    idx_set(K),  R = count : { idx_set(Ka), Ka < K },
    idx_set(K2), R = count : { idx_set(Kb), K2 < Kb }.
```

Home: `Ordinal` — it owns `idx_set`; `rev` is a second readout beside
`rank`.

**Task-local home (protocol step 1).** 85c4e7cd reverses its ring colors:
`rev` over ring indices pairs ring K with the ring as deep from the center
as K is from the border.

## `CycleWalk` — advance along a directed cycle by a count

The walk readout of a Z/n cycle. `succ` takes the cycle's edges — explicit
data, or a builder like `IndexCycle` (below); `walk(p0, n, p)` advances a
start node n successor steps. The edge set carries no basepoint, so the cycle
is recoverable content but any single node is an arbitrary reference — `walk`
(a step count, the torsor difference) is basepoint-free; the absolute node is
not. `step` declares the advance counts in use — raw solver data; the comp
closes them downward into the recursion bound.

```
.comp CycleWalk<T> {
    .decl succ(p: T, p_next: T)
    .decl step(n: number)               // advance counts in use

    // Downward closure of step — the walk's recursion bound.
    .decl bound(n: number)
    bound(N) :- step(M), N = range(0, M+1).

    .decl walk(p0: T, n: number, p: T)  // p = p0 advanced n steps along succ
    walk(P0, 0, P0) :- succ(P0, _).
    walk(P0, N1, P2) :-
        walk(P0, N, P1), succ(P1, P2),
        bound(N1), N1 = N + 1.
}
```

**Consumer half only.** It walks a cycle; it never builds one. A solver whose
advance is lockstep with another step (one slot per spatial cell) consumes
`succ` directly and skips this comp.

**Task-local homes (protocol step 1).** ca8de6ea: the output's 8-cell ring,
`succ` as explicit edge data — an irregular spatial cycle whose cyclic order
is the data itself, so no builder applies; walked by per-ring shifts.
6d1d5c90: row indices closed into a cycle by `IndexCycle`, walked by the
marker's shift. 25ff71a9 $Cycle: the row cycle, walked by c.shift_k.

```
.init ring = CycleWalk<Position>
ring.succ(P, P_next) :- c.ring_succ(P, P_next).   // the ring cycle
ring.step(N)         :- c.ring_shift(_, N).        // shifts in use

out(P_out, ...) :- ..., ring.walk(P_corner, Shift, P_out).
```

## `IndexCycle` — Z/N successor over a dense index set

The builder half: a dense 0-based index set closed into a cycle — increment,
with the max wrapping to 0. Every dense cycle is Z/N up to relabeling, and
spatial substrates conjugate through seating the lib already owns (`dist`
reads an index off a position, `DirFrame.pos` seats one back), so no
per-substrate cycle builder is needed: an earlier `DirCycle` staging (line of
positions + a Dir) dissolved into this composition — 6d1d5c90 measures rows
from `opposite(shift_dir)`, so ascending index runs toward the shift and the
wrap lands on the shift edge.

```
.comp IndexCycle {
    .decl idx(k: number)

    .decl succ(k: number, k2: number)
    succ(K, K+1) :- idx(K), idx(K+1).
    succ(K, 0)   :- idx(K), !idx(K+1).   // wrap from the max
}
```

Consumers split by how they advance: a lockstep closure reads `succ` raw; a
count advance feeds it to `CycleWalk`.

**Task-local homes (protocol step 1).** 97999447: the ray's mask-slot cycle,
advanced one slot per spatial step (lockstep, no walk). 6d1d5c90: the row
cycle, walked by count via `CycleWalk`. 25ff71a9 $Cycle: the row cycle,
walked by count via `CycleWalk`.

## `Reach` — seeded connectivity

One component from a seed — the seeded readout of the 4-adjacency closure
that lib's `Components` labels in full. The seed selects the component and is
the closure's base case: `Reach` fits when there's a natural anchor and one
component matters; `Components` fits when every component counts. An
8-adjacency variant or a parameterized adjacency input is the obvious
extension when a task needs diagonal connectivity.

```
.comp Reach {
    .decl node(p: Position)
    .decl seed(p: Position)

    .decl step(delta: Position)
    step([-1, 1, 0, 0]). step([1, -1, 0, 0]). step([0, 0, -1, 1]). step([0, 0, 1, -1]).

    .decl reach(p: Position)
    reach(P)  :- seed(P).
    reach(P2) :- reach(P1), step(D), compose(P1, D, P2), node(P2).
}
```

**Task-local home (protocol step 1).** 1e81d6f9: a corner-edge seed picks the
L frame — the stray mask cell stays unreachable, so the following `Bbox`
doesn't inflate to span it.

## `diag_step_delta` — unit step toward a corner

The DiagDir peer of `step_delta`: the corner's two cardinal unit steps
composed. Single-clause inline, per the lib's dispatch convention.

```
.decl diag_step_delta(diag: DiagDir, delta: Position) inline
diag_step_delta(Diag, Delta) :-
    dir_of(Diag, AXIS_V, Dv), dir_of(Diag, AXIS_H, Dh),
    step_delta(Dv, Sv), step_delta(Dh, Sh),
    compose(Sv, Sh, Delta).
```

**Task-local homes (protocol step 1).** 05269061 carries it as a `DiagStep`
comp: the along-stripe generator of its color-propagation closure is the
delta toward each corner of `c.stripe_axis`. 66e6c45b $Explode: the outward
step of each shape-corner cell.

## `diag_edge_delta` — edge delta at a corner

The DiagDir peer of `edge_delta`: a Position carrying extents at the two
edges of corner `diag`, axis-tagged — k1 at the edge on axis a, k2
across. Grow-toward-a-corner, where `diag_step_delta` is
move-toward-a-corner. The delta counterpart of the `diag_dist` readout.

```
.decl diag_edge_delta(diag: DiagDir, a: Axis, k1: number, k2: number, p: Position) inline
diag_edge_delta(Diag, A, K1, K2, P) :-
    diag_dirs(Diag, A, D1, D2),
    edge_delta(D1, K1, P1), edge_delta(D2, K2, P2),
    compose(P1, P2, P).
```

**Task-local home (protocol step 1).** 8618d23e (`DiagEdgeDelta` comp):
$Derive's grow delta at the corner opposite the seat, the pair from the
growth case.

## `c4_elem` — the rotation subgroup enum

The C4 subset of `d4_elem`: the four rotations. For closures that apply
every rotation — where a reflection would be wrong, not merely unused.
Lib target: a fact set beside `d4_elem`.

```
.decl c4_elem(d: D4)
c4_elem(D4_ID). c4_elem(D4_CW). c4_elem(D4_HT). c4_elem(D4_CC).
```

**Task-local home (protocol step 1).** 46442a0e (`RotElems` comp): $Rot's
quarter-turn closure, applied jointly to anchor tile position and content.

## `D4Invariance<Key, Val>` — per-key D4 invariance of a valued cell set

Which D4 elements fix each keyed cell set. `broken` witnesses a violated
transform — some cell whose image under d carries a different value;
`has_sym` is invariance under some nontrivial element. `cell` must be total
over each key's domain (the negation reads absence as difference). The keyed
generalization of 44f52bb0's unkeyed `non_invariant` / `input_inv` body
rules; that solver is a promotion-time caller (`Unit` key).

```
.comp D4Invariance<Key, Val> {
    .decl cell(key: Key, p: Position, v: Val)

    .decl broken(key: Key, d: D4)
    broken(K, D) :- cell(K, P, V), d4_elem(D), apply(D, P, P2), !cell(K, P2, V).

    .decl has_sym(key: Key)
    has_sym(K) :- cell(K, _, _), d4_elem(D), D != D4_ID, !broken(K, D).
}
```

**Task-local home (protocol step 1).** 662c240a keys tiles by slab index:
`$Shared` reads `broken` at `c.sym`; `$Asym` negates `has_sym`.

## `ReadOrder` — reading order over a cell set

Scan-like-text order given a corner and a primary axis: `before` compares
lexicographically (strictly nearer along the primary dir; or primary tie and
strictly nearer along the secondary), `rank` counts predecessors. The
primitive boundary is unsettled: one comp owning both, or a split — a
rank-over-input-order comp (`RelOrdinal<T>`, subsuming `Ordinal` at `<` on
numbers) fed by a lexicographic `before` supplier.

**Task-local home (protocol step 1).** ff28f65a carries it as body rules
(`read_before`, `fill_rank`); `$Fill` marks X cells with rank below the count.

**Second home (protocol step 1).** a68b268e $Scan carries `before` as body
rules (`scan_before`) over tile positions; no rank readout.
