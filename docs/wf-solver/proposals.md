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
per-edge offsets, assembles `tile_offset(p_outer, p_off)`, and exposes a
one-liner `concat` (lookup + `compose`).

```
.comp ConcatPipeline {
    .decl tile_in(p_outer: Position, p_inner: Position)
    .decl axis_gap(a: Axis, g: number)

    // Tile dim along axis(D), indexed by tile's distance from edge D.
    // Every cell in a rectilinear tile produces the same K — set semantics dedupes.
    .decl axis_dim(d: Dir, i: number, k: number)
    axis_dim(D, I, K) :-
        tile_in(P_outer, P_inner),
        dist(P_outer, D, I),
        opposite(D, D2),
        dist(P_inner, D, Near), dist(P_inner, D2, Far),
        K = Near + Far + 1.

    // Cumulative offset from edge D for the tile at distance I from D.
    .decl edge_off(d: Dir, i: number, off: number)
    edge_off(D, I, OFF) :-
        axis_dim(D, _, _),
        axis_of(D, A), axis_gap(A, G),
        OFF = (sum K : { axis_dim(D, J, K), J < I }) + I*G.

    // Tile bbox offset in grid units, assembled from the four edges.
    .decl tile_offset(p_outer: Position, p_off: Position)
    tile_offset([OT, BO, OL, RO], [T_off, B_off, L_off, R_off]) :-
        edge_off(TOP,    OT, T_off),
        edge_off(BOTTOM, BO, B_off),
        edge_off(LEFT,   OL, L_off),
        edge_off(RIGHT,  RO, R_off).

    // Lookup + compose.
    .decl concat(p_outer: Position, p_inner: Position, p_grid: Position) inline
    concat(P_outer, P_inner, P_grid) :-
        tile_offset(P_outer, P_off),
        compose(P_off, P_inner, P_grid).
}
```

Internals collapse via `Dir`: `axis_dim`, `edge_off`, and `tile_offset` each
generalize across edges/axes in a single rule. Like the uniform `concat` family,
it's shape-agnostic — `P_outer` full-2D or axis-only both flow through `compose`,
so 2D and slab arrangements use the same rules.

Solver usage:

```
.init concat = ConcatPipeline
concat.tile_in(P_outer, P_inner) :- tile_data(P_outer, P_inner, _).
concat.axis_gap(VERTICAL, 0). concat.axis_gap(HORIZONTAL, 0).

out(P_grid, V) :-
    tile_data(P_outer, P_inner, V),
    concat.concat(P_outer, P_inner, P_grid).
```

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

**Scope.** The component owns set-relationship derivation. Ranking policy (`best_covered`,
`nearest`) and approximate / multiset / payload matching sit at or past the edge —
solver-local or a separate component. Current hints: 3618c87e → an `unmatched` negative,
44f52bb0 → `best_covered`.

**Global observed set.** When the observed set is global — one set, no
meaningful key (44f52bb0's invariance set, 27a28665's silhouette) — the call passes a
constant `0: number` key, which is what lib landed on. A `.type Unit = U {}` singleton
keyed on `$U()` remains a possible tightening — it would state "exactly one observed
set" in the type instead of a dummy int.

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

Single-set callers pass a constant `0: number` key, the convention
`KeyedSetCompare` landed on. Callers to update: f8ff0b80 (both), d406998b
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

## `Cycle` — directed cycle with basepoint-free rotation

The Z/n cycle species made first-class. `succ` declares a directed cycle by its
edges; `walk(p0, n, p)` advances a start cell n successor steps. The edge set
carries no basepoint, so the cycle is recoverable content but any single
position is an arbitrary reference — `walk` (a step count, the torsor
difference) is basepoint-free; the absolute position is not.

```
.comp Cycle<T> {
    .decl succ(p: T, p_next: T)
    .decl step(n: number)               // advance counts in use (bounds the walk)

    .decl walk(p0: T, n: number, p: T)  // p = p0 advanced n steps along succ
    walk(P0, 0, P0) :- succ(P0, _).
    walk(P0, N1, P2) :-
        walk(P0, N, P1), succ(P1, P2),
        step(N1), N1 = N + 1.
}
```

**Bound.** `walk` over a finite cycle never terminates unbounded — n grows past
the cycle length. `step` enumerates the advance counts the solver needs and caps
the recursion. Alternative: have the component count cycle length L and expose
the full Z/L (`walk` for n in 0..L-1) — more machinery, unneeded when a solver
applies only a few shifts. `DirCycle` (below) takes that alternative for a dense
axis — it counts L from its nodes, so its caller hands it no step set.

**Task-local home (protocol step 1).** ca8de6ea collapses a 5×5 X onto a dense
3×3. The output's 8-cell ring is a CW `Cycle`; each X-arm cell maps to the ring
cell at its own diagonal, advanced by a per-ring shift — corner ring 0, inner
ring +1.

```
.init ring = Cycle<Position>
ring.succ(P, P_next) :- c.ring_succ(P, P_next).   // the ring cycle
ring.step(N)         :- c.ring_shift(_, N).        // shifts in use

out(P_out, ...) :- ..., ring.walk(P_corner, Shift, P_out).
```

**Second home (protocol step 1).** 6d1d5c90's rows are a `Cycle` built by
`DirCycle` (below). Where ca8de6ea enumerates an irregular ring as `succ` data,
6d1d5c90 *derives* `succ` from axis adjacency — the abstraction's two ends.

## `DirCycle` — a dense line closed into a cycle

The 1D-cycle peer of `DirFrame`, same `dir(d: Dir)` parameter: where `DirFrame`
seats an index in a line measured from an edge, `DirCycle` walks a line closed into
a loop advancing toward an edge. Given a node set on an axis it builds the cyclic
`succ` — linear step toward `dir`, plus a wrap from the `dir`-extreme back to the
far extreme — counts its own length, and exposes `walk`.

```
.comp DirCycle {
    .decl node(p: Position)
    .decl dir(d: Dir)                    // advance direction

    .decl succ(p: Position, q: Position)
    succ(P, Q) :- node(P), dir(D), step_delta(D, S), compose(P, S, Q), node(Q).    // step toward dir
    succ(P, Q) :- node(P), dir(D), dist(P, D, 0),                                  // wrap:
                  node(Q), opposite(D, O), dist(Q, O, 0).                          //  dir extreme -> far extreme

    .init cyc = Cycle<Position>
    cyc.succ(P, Q) :- succ(P, Q).
    cyc.step(N)    :- L = count : { node(_) }, N = range(0, L).   // every advance the cycle allows

    .decl walk(p0: Position, n: number, p: Position)
    walk(P0, N, P) :- cyc.walk(P0, N, P).
}
```

**Composed, not new machinery.** `step_delta` (lib) supplies adjacency;
`Cycle` supplies `walk`; `DirCycle` adds only the wrap edge and the length count.

**Dense line.** Like `DirFrame`'s dense `dist_set`, `DirCycle` assumes the nodes
form a contiguous line — the unit-step `succ` needs each interior node's neighbor
present. A sparse set dead-ends mid-line (a covering-relation `succ` would be the
sparse variant); a cyclic shift is dense, so this contract fits.

**Task-local home (protocol step 1).** 6d1d5c90: `node` is each row (an `in` cell
split onto the shift axis), `dir` the shift direction, `walk(row, M)` the rotation.

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
    dir_of(Diag, VERTICAL, Dv), dir_of(Diag, HORIZONTAL, Dh),
    step_delta(Dv, Sv), step_delta(Dh, Sh),
    compose(Sv, Sh, Delta).
```

**Task-local home (protocol step 1).** 05269061 carries it as a `DiagStep`
comp: the along-stripe generator of its color-propagation closure is the
delta toward each corner of `c.stripe_axis`.

## `jump_delta` — K-cell displacement toward an edge

Scaled `step_delta`: -K at edge d, +K at its opposite. `step_delta` is the
K = 1 slice and can be redefined through it on promotion. Without it, a body
needing a longer displacement negates K itself — arithmetic the primitive
absorbs.

```
.decl jump_delta(d: Dir, k: number, delta: Position) inline
jump_delta(D, K, Delta) :-
    edge_delta(D, -K, Nd), opposite(D, O), edge_delta(O, K, No),
    compose(Nd, No, Delta).
```

**Task-local home (protocol step 1).** 05269061 carries it as a `Jump` comp:
the wallpaper's period-length translations are `jump_delta(D, period, _)` on
the four cardinals, generating the color-propagation closure.

## `Between<Key>` — cell between two keyed marks on its line

A cell with a mark of key K at or beyond it on both sides of its line along
`axis`. `mark_side` is the one-sided reach; `between` folds the two sides.
Reach is inclusive (`<=`), so a mark is between under its own key; on a
mark-free domain, inclusive and strict reach coincide, so callers that exclude
marks (a bg-only domain) get the strict semantics for free.

```
.comp Between<Key> {
    .decl axis(a: Axis)
    .decl cell(p: Position)            // domain tested
    .decl mark(key: Key, p: Position)

    // A key-K mark at or beyond p toward edge d, in p's line.
    .decl mark_side(key: Key, p: Position, d: Dir)
    mark_side(K, P, D) :-
        cell(P), mark(K, Q),
        axis(A), split(P, A, _, Ac), split(Q, A, _, Ac),
        axis_of(D, A), dist(P, D, Kp), dist(Q, D, Kq), Kq <= Kp.

    .decl between(key: Key, p: Position)
    between(K, P) :- mark_side(K, P, D), opposite(D, O), mark_side(K, P, O).
}
```

**Task-local home (protocol step 1).** 22168020 carries it as body rules
(`mark_side`, `fill`), keyed by mark color: each color's span fills with that
color.

**Second home (protocol step 1).** a699fb00's `$Span` (`dot_beyond`,
`spanned`): unit key (the one dot color), domain restricted to bg cells —
the strict-reach caller.

## `ReadOrder` — reading order over a cell set

Scan-like-text order given a corner and a primary axis: `before` compares
lexicographically (strictly nearer along the primary dir; or primary tie and
strictly nearer along the secondary), `rank` counts predecessors. The
primitive boundary is unsettled: one comp owning both, or a split — a
rank-over-input-order comp (`RelOrdinal<T>`, subsuming `Ordinal` at `<` on
numbers) fed by a lexicographic `before` supplier.

**Task-local home (protocol step 1).** ff28f65a carries it as body rules
(`read_before`, `fill_rank`); `$Fill` marks X cells with rank below the count.
