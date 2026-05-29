# Proposals

Forward-looking changes to `.dl` style and primitives — a working draft.

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

## `Ordinal` — sparse → dense rank

Pattern: turn a sparse numeric set into a dense ordinal-position mapping. `rank(K, R)` where R is the count of elements strictly less than K. For input `{2, 5, 7}` → `{2→0, 5→1, 7→2}`.

```
.comp Ordinal {
    .decl idx_set(k: number)

    .decl rank(k: number, r: number)
    rank(K, R) :-
        idx_set(K),
        R = count : { idx_set(K2), K2 < K }.
}
```

**Task-local home (protocol step 1).** f8ff0b80 ranks non-bg colors by cell
count and lays them out along an axis. Its `color_rank` is exactly this
operation; it carries a solver-local `Ordinal` comp fed by the distinct color
counts (`o.idx_set(N) :- color_count(_, N)`), with `color_rank` joining color →
count → rank. Ranking the *distinct counts* (rather than competition-ranking the
colors, which skips ranks on ties and drives DirFrame's opposite-edge distance
negative) keeps `dist_set` dense.

Composes with `DirFrame`: Ordinal does sparse → dense; DirFrame keeps its dense-input contract and places indices in axis-only Positions.

```
.init o = Ordinal
.init col = DirFrame

o.idx_set(K) :- some_sparse_indices(K).
col.dir(TOP).
col.dist_set(R) :- o.rank(_, R).

out(P, ...) :- some_sparse_indices(K), o.rank(K, R), col.pos(R, P).
```

**Direction.** Default is ascending (`K2 < K`). When the rank is purely
positional — it only feeds a frame placement — a descending layout falls out by
placing from the opposite edge (flip `DirFrame.dir` to `opposite(anchor)`), no
negation needed; f8ff0b80 does this to seat the largest count at its anchor
edge while ranking ascending. Upstream negation is only needed when the rank
*value* itself flows downstream (a color lookup, an arithmetic step), where the
magnitude must invert.

**Ties.** `idx_set` is a set — duplicate K values dedupe. Distinct items mapping to the same K share that K's rank. Useful for grouping; if unique placement is needed, break ties upstream. The dedupe keeps the output rank set dense even under ties, so a `DirFrame` fed from it stays valid; the collision is two items at one Position, not a sparse frame.

**Naming.** "Rank" in pure math means matrix rank / set rank — different concepts. "Ordinal" sidesteps that misappropriation while naming the output (an ordinal position). The operation itself (count of strictly-less-than over a set) matches CS / stats / SQL "dense rank."
