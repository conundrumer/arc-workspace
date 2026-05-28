# Proposals

Forward-looking changes to `.dl` style and primitives — a working draft.

## 3. Primitive proposals

`divide` is the 1D forward primitive already in lib. Add 2D and 1D-passthrough wrappers for the forward direction (`divide_2d`, `divide_1d`). For the inverse, two pieces:

- `concat_sym` — closed-form 1D fast path for uniform tiles. Mirrors `divide`.
- `ConcatPipeline` — component for the general (rectilinear) case. Solver populates the input relation; component derives per-tile bbox offsets; `compose` is the recompose.

Asymmetry vs forward: divide has two distinct orchestrations (two-divides + compose vs divide + passthrough), so it needs `divide_2d` and `divide_1d`. The component's inverse has one orchestration (lookup + compose); `compose`'s shape-agnosticism handles 2D and slab uniformly, so a single `concat` inside the component covers both.

### 3.4 `ConcatPipeline` — inverse component

Solver populates `tile_in` (dim info; values aren't read by the pipeline) and `gap`. The component derives per-row / per-col tile dims, cumulative per-edge offsets, assembles `tile_offset(p_outer, p_off)`, and exposes a one-liner `concat` (lookup + `compose`).

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

Internals collapse via `Dir`: `axis_dim`, `edge_off`, and `tile_offset` each generalize across edges/axes in a single rule.

Solver usage:

```
.init concat = ConcatPipeline
concat.tile_in(P_outer, P_inner) :- tile_data(P_outer, P_inner, _).
concat.gap(0, 0).

out(P_grid, V) :-
    tile_data(P_outer, P_inner, V),
    concat.concat(P_outer, P_inner, P_grid).
```

Handles all three arrangements via shape-agnostic `compose`:

- **2D**: `P_outer` full 2D → `tile_offset` returns full 2D `P_off` → compose with full 2D `P_inner`.
- **Slab V**: `P_outer` V-only → `tile_offset` returns V-only `P_off` (`left_off(0, 0)` and `right_off(0, 0)` from the single-column `col_width(0, full_width)`) → compose with full 2D `P_inner` passes H through unchanged.
- **Slab H**: symmetric.

Uniform falls out: when all rows share `I_v`, the `sum` aggregations collapse to `OT * (I_v + G_v)` etc. — same rules, no separate fast path needed.

The convention name disappears from lib: solvers name their input relation freely (e.g., `tile_data` above), and connect it to the pipeline via `concat.tile_in(...) :- tile_data(...)`. Lib-side, only the component's internal relation names are fixed.

### 3.5 `KeyedSetCompare` extensions — set-relationship lattice

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
constant `0: number` key. A `.type Unit = U {}` singleton keyed on `$U()` would state
"exactly one observed set" in the type instead of faking it with a dummy int.

### 3.6 `Ordinal` — sparse → dense rank

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

Composes with `DirFrame`: Ordinal does sparse → dense; DirFrame keeps its dense-input contract and places indices in axis-only Positions.

```
.init o = Ordinal
.init col = DirFrame

o.idx_set(K) :- some_sparse_indices(K).
col.dir(TOP).
col.dist_set(R) :- o.rank(_, R).

out(P, ...) :- some_sparse_indices(K), o.rank(K, R), col.pos(R, P).
```

**Direction.** Default is ascending (`K2 < K`). Descending requires upstream negation.

**Ties.** `idx_set` is a set — duplicate K values dedupe. Distinct items mapping to the same K share that K's rank. Useful for grouping; if unique placement is needed, break ties upstream.

**Naming.** "Rank" in pure math means matrix rank / set rank — different concepts. "Ordinal" sidesteps that misappropriation while naming the output (an ordinal position). The operation itself (count of strictly-less-than over a set) matches CS / stats / SQL "dense rank."

